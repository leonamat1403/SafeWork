"""Configurações (tela T06, só ADMIN): postos e câmeras e a máscara por posto (RD05), zona de interesse (RD06) e os
ajustes do sistema. Tudo vale sem reiniciar (a câmera afetada é religada) e fica na auditoria ("alterar_config").

O sistema verifica só a máscara de solda (decisão de 15/10/2026): a aba "EPIs por posto" trata só dela.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app import sistema
from app.auth import UsuarioSessao, auditar, exigir_admin, exigir_csrf
from app.config import RAIZ, epis_padrao
from app.models import Camera, ConfigEpiCamera, Ocorrencia
from app.tempo import para_local

rotas = APIRouter(prefix="/api", tags=["configurações"])
EXTENSOES_VIDEO = (".mp4", ".avi", ".mkv", ".mov")
MAX_PONTOS_ZONA = 30


# --------------------------------------------------------------------------------------------------- postos
class DadosCamera(BaseModel):
    nome_posto: str
    processo_solda: Literal["MIG_MAG", "TIG", "ELETRODO", "CORTE", "OUTRO"]
    tipo: Literal["webcam", "rtsp", "arquivo"]
    origem: str
    ativa: bool = True


def _erro(mensagem: str, codigo: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(codigo, mensagem)


def _validar_camera(dados: DadosCamera) -> tuple[str, str]:
    """Nome e endereço conferidos. A senha da câmera IP nunca entra no banco (F2-D10)."""
    nome, origem = dados.nome_posto.strip(), dados.origem.strip()
    if not 2 <= len(nome) <= 100:
        raise _erro("O nome do posto deve ter de 2 a 100 caracteres.")
    if dados.tipo == "webcam":
        if not origem.isdigit() or int(origem) > 20:
            raise _erro("Webcam: informe o número dela no computador (0 para a primeira, 1 para a segunda...).")
    elif dados.tipo == "rtsp":
        partes = urlsplit(origem)
        if partes.scheme not in ("rtsp", "rtsps") or not partes.hostname:
            raise _erro("Câmera IP: informe o endereço RTSP, por exemplo rtsp://10.0.3.21:554/stream1.")
        if "@" in partes.netloc:
            raise _erro("Não coloque usuário e senha no endereço: eles ficam no arquivo .env (RTSP_USUARIO e "
                        "RTSP_SENHA), nunca no banco.")
    else:
        caminho = Path(origem) if Path(origem).is_absolute() else RAIZ / origem
        if caminho.suffix.lower() not in EXTENSOES_VIDEO or not caminho.is_file():
            raise _erro("Arquivo de vídeo não encontrado (use um .mp4, .avi, .mkv ou .mov da pasta do projeto).")
    return nome, origem


def _mascara(camera: Camera) -> ConfigEpiCamera | None:
    return next((e for e in camera.epis if e.epi == "mascara"), None)


def mascara_json(linha: ConfigEpiCamera | None) -> dict | None:
    if linha is None:
        return None
    extra = linha.parametros_extra or {}
    return {"exigido": linha.exigido, "conf_min": linha.conf_min, "persistencia_s": linha.persistencia_s,
            "fracao_minima": linha.fracao_minima, "cobertura_min": float(extra.get("cobertura_min", 0.30)),
            "levantada_nao_conforme": bool(extra.get("levantada_nao_conforme", False))}


def camera_json(camera: Camera, ocorrencias: int) -> dict:
    return {"id": camera.id, "nome_posto": camera.nome_posto, "processo_solda": camera.processo_solda,
            "tipo": camera.tipo, "origem": camera.origem, "ativa": camera.ativa, "zona": camera.roi_poligono,
            "ocorrencias": ocorrencias, "criado_em": para_local(camera.criado_em).strftime("%d/%m/%Y"),
            "mascara": mascara_json(_mascara(camera))}


def _contagem_ocorrencias(sessao) -> dict[int, int]:
    return dict(sessao.execute(select(Ocorrencia.camera_id, func.count()).group_by(Ocorrencia.camera_id)).all())


def _buscar_camera(sessao, camera_id: int) -> Camera:
    camera = sessao.get(Camera, camera_id)
    if camera is None:
        raise _erro("Posto não encontrado.", status.HTTP_404_NOT_FOUND)
    return camera


def _nome_repetido(sessao, nome: str, outro_que: int | None = None) -> bool:
    consulta = select(Camera.id).where(func.lower(Camera.nome_posto) == nome.lower())
    if outro_que is not None:
        consulta = consulta.where(Camera.id != outro_que)
    return sessao.scalar(consulta) is not None


@rotas.get("/config/cameras")
def listar_postos(request: Request, _: UsuarioSessao = Depends(exigir_admin)) -> list[dict]:
    """Postos com tudo o que a aba "Postos e câmeras" mostra (inclusive o endereço, sem senha)."""
    with request.app.state.ctx.fabrica() as sessao:
        contagem = _contagem_ocorrencias(sessao)
        return [camera_json(c, contagem.get(c.id, 0)) for c in sessao.scalars(select(Camera).order_by(Camera.id))]


@rotas.post("/cameras", status_code=status.HTTP_201_CREATED, dependencies=[Depends(exigir_csrf)])
def criar_posto(dados: DadosCamera, request: Request, admin: UsuarioSessao = Depends(exigir_admin)) -> dict:
    ctx = request.app.state.ctx
    nome, origem = _validar_camera(dados)
    with ctx.fabrica() as sessao:
        if _nome_repetido(sessao, nome):
            raise _erro(f"Já existe um posto chamado {nome}.", status.HTTP_409_CONFLICT)
        camera = Camera(nome_posto=nome, processo_solda=dados.processo_solda, tipo=dados.tipo, origem=origem,
                        ativa=dados.ativa, epis=[ConfigEpiCamera(**linha) for linha in epis_padrao(ctx.config_yaml)])
        sessao.add(camera)
        sessao.commit()
        resposta = camera_json(camera, 0)
    auditar(ctx.fabrica, admin.id, "alterar_config", {"alvo": "posto", "acao": "criar", "id": resposta["id"],
                                                       "nome": nome, "tipo": dados.tipo})
    ctx.cameras.reiniciar(resposta["id"])
    return resposta


@rotas.put("/cameras/{camera_id}", dependencies=[Depends(exigir_csrf)])
def editar_posto(camera_id: int, dados: DadosCamera, request: Request,
                 admin: UsuarioSessao = Depends(exigir_admin)) -> dict:
    ctx = request.app.state.ctx
    nome, origem = _validar_camera(dados)
    with ctx.fabrica() as sessao:
        camera = _buscar_camera(sessao, camera_id)
        if _nome_repetido(sessao, nome, camera_id):
            raise _erro(f"Já existe um posto chamado {nome}.", status.HTTP_409_CONFLICT)
        antes = {"nome": camera.nome_posto, "processo": camera.processo_solda, "tipo": camera.tipo,
                 "origem": camera.origem, "ativa": camera.ativa}
        if (camera.tipo, camera.origem) != (dados.tipo, origem):
            camera.roi_poligono = None   # outra câmera, outra imagem: a zona antiga não vale mais
        camera.nome_posto, camera.processo_solda, camera.tipo = nome, dados.processo_solda, dados.tipo
        camera.origem, camera.ativa = origem, dados.ativa
        sessao.commit()
        resposta = camera_json(camera, _contagem_ocorrencias(sessao).get(camera_id, 0))
    auditar(ctx.fabrica, admin.id, "alterar_config", {"alvo": "posto", "acao": "editar", "id": camera_id,
                                                       "antes": antes, "depois": {k: resposta[k] for k in (
                                                           "nome_posto", "processo_solda", "tipo", "origem", "ativa")}})
    ctx.cameras.reiniciar(camera_id)
    return resposta


@rotas.delete("/cameras/{camera_id}", dependencies=[Depends(exigir_csrf)])
def remover_posto(camera_id: int, request: Request, admin: UsuarioSessao = Depends(exigir_admin)) -> dict:
    """Só remove um posto sem ocorrências: o histórico não pode sumir (F2-D18). Com ocorrências, desative."""
    ctx = request.app.state.ctx
    with ctx.fabrica() as sessao:
        camera = _buscar_camera(sessao, camera_id)
        if _contagem_ocorrencias(sessao).get(camera_id):
            raise _erro("Este posto tem ocorrências registradas e não pode ser removido: desative-o (o histórico "
                        "continua disponível).", status.HTTP_409_CONFLICT)
        nome = camera.nome_posto
        sessao.delete(camera)
        sessao.commit()
    auditar(ctx.fabrica, admin.id, "alterar_config", {"alvo": "posto", "acao": "remover", "id": camera_id,
                                                       "nome": nome})
    ctx.cameras.reiniciar(camera_id)   # para a câmera, se estava ligada
    return {"removido": camera_id}


# --------------------------------------------------------------------------------------------------- máscara por posto
class DadosMascara(BaseModel):
    exigido: bool
    conf_min: float
    persistencia_s: float
    fracao_minima: float
    cobertura_min: float
    levantada_nao_conforme: bool


LIMITES_MASCARA = {"conf_min": (0.05, 0.95, "confiança mínima"), "persistencia_s": (1, 30, "tempo em falta"),
                   "fracao_minima": (0.5, 1.0, "fração mínima"), "cobertura_min": (0.1, 0.9, "cobertura mínima")}


@rotas.get("/cameras/{camera_id}/epis")
def ver_mascara(camera_id: int, request: Request, _: UsuarioSessao = Depends(exigir_admin)) -> dict:
    with request.app.state.ctx.fabrica() as sessao:
        return {"mascara": mascara_json(_mascara(_buscar_camera(sessao, camera_id))),
                "limites": {k: [a, b] for k, (a, b, _) in LIMITES_MASCARA.items()}}


@rotas.put("/cameras/{camera_id}/epis", dependencies=[Depends(exigir_csrf)])
def salvar_mascara(camera_id: int, dados: DadosMascara, request: Request,
                   admin: UsuarioSessao = Depends(exigir_admin)) -> dict:
    """Regras da máscara no posto (RF13): exigir ou não, confiança, persistência (4 s / 75%), cobertura da cabeça e se
    a máscara levantada conta como falta."""
    ctx = request.app.state.ctx
    for campo, (minimo, maximo, nome) in LIMITES_MASCARA.items():
        if not minimo <= getattr(dados, campo) <= maximo:
            raise _erro(f"A {nome} deve ficar entre {minimo:g} e {maximo:g}.")
    with ctx.fabrica() as sessao:
        camera = _buscar_camera(sessao, camera_id)
        linha = _mascara(camera)
        if linha is None:
            linha = ConfigEpiCamera(epi="mascara", conf_min=dados.conf_min)
            camera.epis.append(linha)
        antes = mascara_json(linha) if linha.id else None
        linha.exigido, linha.conf_min = dados.exigido, dados.conf_min
        linha.persistencia_s, linha.fracao_minima = dados.persistencia_s, dados.fracao_minima
        linha.parametros_extra = {**(linha.parametros_extra or {}), "cobertura_min": dados.cobertura_min,
                                  "levantada_nao_conforme": dados.levantada_nao_conforme}
        sessao.commit()
        depois = mascara_json(linha)
    auditar(ctx.fabrica, admin.id, "alterar_config", {"alvo": "mascara", "id": camera_id, "antes": antes,
                                                       "depois": depois})
    ctx.cameras.reiniciar(camera_id)
    return {"mascara": depois}


# --------------------------------------------------------------------------------------------------- zona (RD06)
class DadosZona(BaseModel):
    pontos: list[tuple[float, float]] | None = None


@rotas.put("/cameras/{camera_id}/roi", dependencies=[Depends(exigir_csrf)])
def salvar_zona(camera_id: int, dados: DadosZona, request: Request,
                admin: UsuarioSessao = Depends(exigir_admin)) -> dict:
    """Zona de interesse do posto: pontos (x, y) de 0 a 1 (fração da imagem). Sem pontos = a imagem toda."""
    ctx = request.app.state.ctx
    pontos = dados.pontos or None
    if pontos is not None:
        if not 3 <= len(pontos) <= MAX_PONTOS_ZONA:
            raise _erro(f"A zona precisa de 3 a {MAX_PONTOS_ZONA} pontos.")
        if any(not (0 <= x <= 1 and 0 <= y <= 1) for x, y in pontos):
            raise _erro("Os pontos da zona precisam ficar dentro da imagem.")
        pontos = [[round(x, 4), round(y, 4)] for x, y in pontos]
    with ctx.fabrica() as sessao:
        camera = _buscar_camera(sessao, camera_id)
        camera.roi_poligono = pontos
        sessao.commit()
    auditar(ctx.fabrica, admin.id, "alterar_config", {"alvo": "zona", "id": camera_id,
                                                       "pontos": len(pontos) if pontos else 0})
    ctx.cameras.reiniciar(camera_id)
    return {"zona": pontos}


# --------------------------------------------------------------------------------------------------- sistema
def _mascarar(texto: str) -> str:
    """Mostra só o final do segredo, para o ADMIN saber qual está configurado sem expô-lo na tela."""
    return "" if not texto else "••••" + texto[-4:] if len(texto) > 8 else "••••"


def uso_do_disco(pasta: Path) -> dict:
    usado = sum(arquivo.stat().st_size for arquivo in pasta.rglob("*") if arquivo.is_file())
    total, _, livre = shutil.disk_usage(pasta)
    return {"usado_bytes": usado, "livre_bytes": livre, "total_bytes": total}


@rotas.get("/config/sistema")
def ver_sistema(request: Request, _: UsuarioSessao = Depends(exigir_admin)) -> dict:
    ctx = request.app.state.ctx
    return {
        "valores": sistema.valores_atuais(ctx.config_base, ctx.ajustes),
        "padrao": sistema.valores_atuais(ctx.config_yaml, ctx.ajustes_yaml),   # o que está no config.yaml
        "limites": {k: [a, b] for k, (_, a, b) in sistema.CAMPOS.items() if a is not None},
        "telegram": {"configurado": bool(ctx.ajustes.telegram_token and ctx.ajustes.telegram_chat_id),
                     "token": _mascarar(ctx.ajustes.telegram_token), "chat_id": _mascarar(ctx.ajustes.telegram_chat_id)},
        "disco": {**uso_do_disco(ctx.ajustes.data_dir), "minimo_mb": ctx.ajustes.espaco_minimo_mb},
    }


@rotas.post("/config/telegram/teste", dependencies=[Depends(exigir_csrf)])
def testar_telegram(request: Request, admin: UsuarioSessao = Depends(exigir_admin)) -> dict:
    """Manda uma mensagem de teste (sem foto) para conferir o token e a conversa do .env."""
    ctx = request.app.state.ctx
    try:
        ctx.notificador.testar()
    except Exception as erro:
        raise _erro(f"Mensagem não enviada: {erro}.", status.HTTP_502_BAD_GATEWAY) from erro
    auditar(ctx.fabrica, admin.id, "alterar_config", {"alvo": "telegram", "acao": "teste"})
    return {"enviado": True}


@rotas.put("/config/sistema", dependencies=[Depends(exigir_csrf)])
def salvar_sistema(novos: dict, request: Request, admin: UsuarioSessao = Depends(exigir_admin)) -> dict:
    """Muda só os campos enviados. As câmeras são religadas com os valores novos."""
    ctx = request.app.state.ctx
    atuais = sistema.valores_atuais(ctx.config_base, ctx.ajustes)
    try:
        limpos = sistema.validar(novos, atuais)
    except sistema.ErroSistema as erro:
        raise _erro(str(erro)) from erro
    mudou = {k: v for k, v in limpos.items() if atuais.get(k) != v}
    if mudou:
        sistema.salvar(ctx.fabrica, mudou, admin.id)
        auditar(ctx.fabrica, admin.id, "alterar_config", {"alvo": "sistema", "antes": {k: atuais[k] for k in mudou},
                                                           "depois": mudou})
        sistema.atualizar_contexto(ctx)
    return {"valores": sistema.valores_atuais(ctx.config_base, ctx.ajustes), "alterados": sorted(mudou)}
