"""Ocorrências (RF22): lista com filtros e paginação, detalhes, validação manual e exclusão; imagens em /midia (RF24)."""
from __future__ import annotations

import csv
import io
import uuid as uuid_mod
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import String, cast, func, select

from app.auth import UsuarioSessao, auditar, exigir_admin, exigir_csrf, usuario_liberado
from app.models import EPIS_CONHECIDOS, VALIDACOES, Camera, Ocorrencia, Usuario
from app.storage import ErroArmazenamento
from app.tempo import agora_utc, inicio_do_dia_utc, para_local

rotas = APIRouter(tags=["ocorrências"])
POR_PAGINA = 20
SEM_CACHE = {"Cache-Control": "no-store, private"}


def _uuid_valido(texto: str) -> str:
    try:
        return str(uuid_mod.UUID(texto))
    except ValueError as erro:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ocorrência não encontrada.") from erro


def ocorrencia_json(oc: Ocorrencia, nome_posto: str, validador: str | None = None) -> dict:
    """Como uma ocorrência aparece para as telas (datas em UTC e também em horário de Brasília)."""
    return {
        "uuid": oc.uuid, "camera_id": oc.camera_id, "posto": nome_posto,
        "data_hora": oc.data_hora.isoformat(), "data_hora_local": para_local(oc.data_hora).strftime("%d/%m/%Y %H:%M"),
        "turno": oc.turno, "track_id": oc.track_id, "epis_faltantes": oc.epis_faltantes,
        "epis_indeterminados": oc.epis_indeterminados, "situacao": oc.situacao,
        "mascara_levantada": oc.mascara_levantada, "arco_ativo": oc.arco_ativo, "confianca_media": oc.confianca_media,
        "fracao_nao_conforme": oc.fracao_nao_conforme, "validacao": oc.validacao, "origem": oc.origem,
        "validado_por": validador,
        "validado_em": para_local(oc.validado_em).strftime("%d/%m/%Y %H:%M") if oc.validado_em else None,
        "tem_imagem": oc.caminho_imagem is not None,
        "imagem_url": f"/midia/{oc.uuid}?tipo=imagem" if oc.caminho_imagem else None,
        "thumb_url": f"/midia/{oc.uuid}?tipo=thumb" if oc.caminho_thumb else None,
    }


@dataclass
class Filtros:
    """Filtros da tela de Ocorrências (T04), iguais na lista e na exportação CSV (RD10)."""

    do_periodo: list            # período, posto, EPI e turno (o resumo do período usa só estes)
    todos: list                 # + validação
    descricao: dict             # para a auditoria da exportação


def filtros_da_tela(inicio: date | None = Query(None, description="primeiro dia (AAAA-MM-DD, horário de Brasília)"),
                    fim: date | None = Query(None, description="último dia, inclusive"),
                    camera_id: int | None = None,
                    epi: str | None = Query(None, description="EPI faltante (ex.: mascara)"),
                    turno: str | None = None,
                    validacao: str | None = Query(None, description="PENDENTE, CONFIRMADA ou FALSO_POSITIVO")) -> Filtros:
    if epi is not None and epi not in EPIS_CONHECIDOS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"epi deve ser um de {EPIS_CONHECIDOS}")
    if validacao is not None and validacao not in VALIDACOES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"validacao deve ser uma de {VALIDACOES}")
    filtros = []
    if inicio:
        filtros.append(Ocorrencia.data_hora >= inicio_do_dia_utc(inicio))
    if fim:
        filtros.append(Ocorrencia.data_hora < inicio_do_dia_utc(fim + timedelta(days=1)))
    if camera_id is not None:
        filtros.append(Ocorrencia.camera_id == camera_id)
    if epi:
        filtros.append(cast(Ocorrencia.epis_faltantes, String).like(f'%"{epi}"%'))
    if turno:
        filtros.append(Ocorrencia.turno == turno)
    todos = filtros + ([Ocorrencia.validacao == validacao] if validacao else [])
    descricao = {"inicio": inicio.isoformat() if inicio else None, "fim": fim.isoformat() if fim else None,
                 "camera_id": camera_id, "epi": epi, "turno": turno, "validacao": validacao}
    return Filtros(filtros, todos, {k: v for k, v in descricao.items() if v is not None})


@rotas.get("/api/ocorrencias")
def listar(request: Request, filtros: Filtros = Depends(filtros_da_tela), pagina: int = Query(1, ge=1),
           _: UsuarioSessao = Depends(usuario_liberado)) -> dict:
    """Ocorrências da mais recente para a mais antiga, 20 por página (T04)."""
    with request.app.state.ctx.fabrica() as sessao:
        total = sessao.scalar(select(func.count()).select_from(Ocorrencia).where(*filtros.todos))
        linhas = sessao.execute(
            select(Ocorrencia, Camera.nome_posto).join(Camera).where(*filtros.todos)
            .order_by(Ocorrencia.data_hora.desc(), Ocorrencia.id.desc())
            .offset((pagina - 1) * POR_PAGINA).limit(POR_PAGINA)).all()
        por_validacao = dict(sessao.execute(select(Ocorrencia.validacao, func.count()).where(*filtros.do_periodo)
                                            .group_by(Ocorrencia.validacao)).all())
    resumo = {"total": sum(por_validacao.values()), "pendentes": por_validacao.get("PENDENTE", 0),
              "confirmadas": por_validacao.get("CONFIRMADA", 0),
              "falsos_positivos": por_validacao.get("FALSO_POSITIVO", 0)}
    return {"total": total, "pagina": pagina, "por_pagina": POR_PAGINA, "paginas": max(1, -(-total // POR_PAGINA)),
            "resumo": resumo, "itens": [ocorrencia_json(oc, posto) for oc, posto in linhas]}


COLUNAS_CSV = ["Data e hora", "Turno", "Posto", "Pessoa no vídeo", "Falta", "Motivo", "Arco aceso",
               "Confiança da máscara", "Em falta na janela de 4 s", "Indeterminados", "Validação", "Validado por",
               "Validado em", "Origem", "Código"]
TEXTO_VALIDACAO = {"PENDENTE": "Pendente", "CONFIRMADA": "Confirmada", "FALSO_POSITIVO": "Falso positivo"}
TEXTO_ORIGEM = {"ao_vivo": "Câmera ao vivo", "upload": "Arquivo enviado"}


def _celula(valor) -> str:
    """Texto da célula; um valor que começa com = + - @ vira texto puro (o Excel não executa fórmulas do arquivo)."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


def _decimal(valor: float | None) -> str:
    return "" if valor is None else f"{valor:.2f}".replace(".", ",")


@rotas.get("/api/ocorrencias/exportar.csv")
def exportar_csv(request: Request, filtros: Filtros = Depends(filtros_da_tela),
                 usuario: UsuarioSessao = Depends(usuario_liberado)) -> Response:
    """Todas as ocorrências dos filtros da tela, para o Excel (RD10): separador ";", vírgula decimal e acentos
    certos. Sem imagens e sem nada que identifique a pessoa. Fica na auditoria."""
    ctx = request.app.state.ctx
    with ctx.fabrica() as sessao:
        linhas = sessao.execute(
            select(Ocorrencia, Camera.nome_posto, Usuario.nome).join(Camera)
            .outerjoin(Usuario, Usuario.id == Ocorrencia.validado_por).where(*filtros.todos)
            .order_by(Ocorrencia.data_hora.desc(), Ocorrencia.id.desc())).all()
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(COLUNAS_CSV)
    for oc, posto, validador in linhas:
        escritor.writerow([_celula(v) for v in (
            para_local(oc.data_hora).strftime("%d/%m/%Y %H:%M:%S"), oc.turno or "", posto, oc.track_id,
            "Máscara levantada" if oc.mascara_levantada else "Sem máscara",
            "; ".join((oc.situacao or {}).values()), "Sim" if oc.arco_ativo else "Não",
            _decimal((oc.confianca_media or {}).get("mascara")),
            _decimal((oc.fracao_nao_conforme or {}).get("mascara")),
            ", ".join(oc.epis_indeterminados or []), TEXTO_VALIDACAO.get(oc.validacao, oc.validacao), validador or "",
            para_local(oc.validado_em).strftime("%d/%m/%Y %H:%M") if oc.validado_em else "",
            TEXTO_ORIGEM.get(oc.origem, oc.origem), oc.uuid)])
    auditar(ctx.fabrica, usuario.id, "exportar", {"formato": "csv", "linhas": len(linhas), **filtros.descricao})
    nome = f"ocorrencias_{para_local(agora_utc()):%Y%m%d_%H%M}.csv"
    return Response("\ufeff" + saida.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={**SEM_CACHE, "Content-Disposition": f'attachment; filename="{nome}"'})


@rotas.get("/api/ocorrencias/resumo")
def resumo_geral(request: Request, _: UsuarioSessao = Depends(usuario_liberado)) -> dict:
    """Quantas ocorrências esperam validação (número ao lado de "Ocorrências" na barra lateral)."""
    with request.app.state.ctx.fabrica() as sessao:
        pendentes = sessao.scalar(select(func.count()).select_from(Ocorrencia)
                                  .where(Ocorrencia.validacao == "PENDENTE"))
    return {"pendentes": pendentes}


def _buscar(sessao, uuid: str) -> tuple[Ocorrencia, str]:
    linha = sessao.execute(select(Ocorrencia, Camera.nome_posto).join(Camera)
                           .where(Ocorrencia.uuid == _uuid_valido(uuid))).first()
    if linha is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ocorrência não encontrada.")
    return linha[0], linha[1]


@rotas.get("/api/ocorrencias/{uuid}")
def detalhes(uuid: str, request: Request, _: UsuarioSessao = Depends(usuario_liberado)) -> dict:
    """Todos os dados de uma ocorrência (modal da T04)."""
    with request.app.state.ctx.fabrica() as sessao:
        oc, posto = _buscar(sessao, uuid)
        validador = sessao.get(Usuario, oc.validado_por).nome if oc.validado_por else None
    return ocorrencia_json(oc, posto, validador)


class Validacao(BaseModel):
    validacao: Literal["CONFIRMADA", "FALSO_POSITIVO", "PENDENTE"]


@rotas.post("/api/ocorrencias/{uuid}/validacao", dependencies=[Depends(exigir_csrf)])
def validar(uuid: str, dados: Validacao, request: Request, usuario: UsuarioSessao = Depends(usuario_liberado)) -> dict:
    """Confirmada / Falso positivo (alimenta a precisão real do sistema). Auditado (RF25)."""
    ctx = request.app.state.ctx
    with ctx.fabrica() as sessao:
        oc, posto = _buscar(sessao, uuid)
        anterior = oc.validacao
        oc.validacao = dados.validacao
        oc.validado_por = usuario.id if dados.validacao != "PENDENTE" else None
        oc.validado_em = agora_utc() if dados.validacao != "PENDENTE" else None
        sessao.commit()
    auditar(ctx.fabrica, usuario.id, "validar", {"uuid": oc.uuid, "de": anterior, "para": dados.validacao})
    return ocorrencia_json(oc, posto, usuario.nome if oc.validado_por else None)


@rotas.delete("/api/ocorrencias/{uuid}", dependencies=[Depends(exigir_csrf)])
def excluir(uuid: str, request: Request, usuario: UsuarioSessao = Depends(exigir_admin)) -> dict:
    """Exclusão manual (só ADMIN): apaga a imagem, a miniatura e o registro. Auditado (RF25)."""
    ctx = request.app.state.ctx
    with ctx.fabrica() as sessao:
        oc, _ = _buscar(sessao, uuid)
        for caminho in (oc.caminho_imagem, oc.caminho_thumb):
            if caminho:
                try:
                    ctx.storage.apagar(caminho)
                except ErroArmazenamento:
                    pass
        sessao.delete(oc)
        sessao.commit()
    auditar(ctx.fabrica, usuario.id, "excluir", {"uuid": oc.uuid, "data_hora": oc.data_hora.isoformat()})
    return {"excluida": oc.uuid}


@rotas.get("/midia/{uuid}", response_class=Response, responses={200: {"content": {"image/jpeg": {}}}})
def midia(uuid: str, request: Request, tipo: Literal["imagem", "thumb"] = "imagem",
          _: UsuarioSessao = Depends(usuario_liberado)) -> Response:
    """Imagem (sempre borrada) ou miniatura de uma ocorrência. Só com login, nunca pela pasta static/ (RF24)."""
    ctx = request.app.state.ctx
    with ctx.fabrica() as sessao:
        oc, _ = _buscar(sessao, uuid)
    caminho = oc.caminho_imagem if tipo == "imagem" else oc.caminho_thumb
    if not caminho:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esta ocorrência não tem imagem (disco cheio na hora).")
    try:
        conteudo = ctx.storage.ler(caminho)
    except ErroArmazenamento as erro:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Imagem não encontrada.") from erro
    return Response(conteudo, media_type="image/jpeg", headers=SEM_CACHE)
