"""Ajustes do sistema feitos na tela de Configurações (RD05, aba Sistema).

Ficam na tabela `config_sistema`, por cima do config.yaml (F2-D8: o sistema nunca reescreve o config.yaml), e valem
sem reiniciar: as câmeras são religadas com os novos valores (o cordão do turno é mantido).
"""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Ajustes
from app.models import ConfigSistema
from app.scheduler import mudar_retencao
from app.tempo import validar_turnos
from src.config import Config

log = logging.getLogger("epi_solda.sistema")

# chave -> (tipo, mínimo, máximo); None nos limites = sem faixa (booleanos e turnos)
CAMPOS: dict[str, tuple[type, float | None, float | None]] = {
    "cooldown_s": (float, 0, 3600),                 # intervalo mínimo entre ocorrências da mesma pessoa
    "retencao_dias": (int, 1, 3650),                # imagens e registros mais antigos são apagados às 03:00
    "imgsz": (int, 320, 1280),                      # tamanho da imagem no detector de máscara (múltiplo de 32)
    "limiar_brilho": (int, 200, 255),               # filtro do arco: brilho de um pixel "estourado"
    "fracao_max_saturada": (float, 0.05, 0.5),      # filtro do arco: acima disso o quadro é ignorado
    "detectar_solda_ativa": (bool, None, None),     # RD03
    "fracao_min_maos": (float, 0.005, 0.5),         # RD03
    "exigir_mascara_somente_com_arco": (bool, None, None),   # RD03
    "turnos": (dict, None, None),
    "telegram_ativo": (bool, None, None),           # RD09 (só funciona com o token no .env)
}


class ErroSistema(ValueError):
    """Valor recusado na aba Sistema (a mensagem vai para a tela)."""


def valores_atuais(config: Config, ajustes: Ajustes) -> dict[str, Any]:
    """Os valores em uso agora (config.yaml + o que já foi mudado na tela)."""
    arco = config.arco
    return {"cooldown_s": config.ocorrencias.cooldown_s, "retencao_dias": ajustes.retencao_dias,
            "imgsz": config.deteccao.imgsz, "limiar_brilho": arco.limiar_brilho,
            "fracao_max_saturada": arco.fracao_max_saturada, "detectar_solda_ativa": arco.detectar_solda_ativa,
            "fracao_min_maos": arco.fracao_min_maos,
            "exigir_mascara_somente_com_arco": arco.exigir_mascara_somente_com_arco,
            "turnos": dict(ajustes.turnos), "telegram_ativo": ajustes.telegram_ativo}


def validar(novos: dict[str, Any], atuais: dict[str, Any]) -> dict[str, Any]:
    """Confere os campos enviados (os que faltam ficam como estão). Levanta ErroSistema com a explicação."""
    limpos = {}
    for chave, valor in novos.items():
        if chave not in CAMPOS:
            raise ErroSistema(f"Campo desconhecido: {chave}.")
        tipo, minimo, maximo = CAMPOS[chave]
        if tipo is bool:
            if not isinstance(valor, bool):
                raise ErroSistema(f"{chave} deve ser verdadeiro ou falso.")
        elif tipo is dict:
            if not isinstance(valor, dict) or not 1 <= len(valor) <= 6:
                raise ErroSistema("Informe de 1 a 6 turnos.")
            valor = {str(nome).strip(): str(faixa).strip() for nome, faixa in valor.items()}
            if any(not 1 <= len(nome) <= 10 for nome in valor):
                raise ErroSistema("O nome de cada turno deve ter de 1 a 10 caracteres.")
            try:
                validar_turnos(valor)
            except ValueError as erro:
                raise ErroSistema(str(erro)) from erro
        else:
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise ErroSistema(f"{chave} deve ser um número.")
            if tipo is int and valor != int(valor):
                raise ErroSistema(f"{chave} deve ser um número inteiro.")
            if not minimo <= valor <= maximo:
                raise ErroSistema(f"{chave} deve ficar entre {minimo:g} e {maximo:g}.")
            valor = tipo(valor)
        limpos[chave] = valor
    if limpos.get("imgsz", 32) % 32:
        raise ErroSistema("O tamanho da imagem deve ser múltiplo de 32 (ex.: 640, 960).")
    final = {**atuais, **limpos}
    if final["exigir_mascara_somente_com_arco"] and not final["detectar_solda_ativa"]:
        raise ErroSistema("Para exigir a máscara só com o arco aceso, a detecção de solda ativa precisa estar ligada.")
    return limpos


def ler_banco(fabrica: sessionmaker[Session]) -> dict[str, Any]:
    with fabrica() as sessao:
        return {linha.chave: linha.valor for linha in sessao.scalars(select(ConfigSistema))}


def salvar(fabrica: sessionmaker[Session], valores: dict[str, Any], usuario_id: int | None) -> None:
    with fabrica() as sessao:
        for chave, valor in valores.items():
            linha = sessao.get(ConfigSistema, chave)
            if linha is None:
                sessao.add(ConfigSistema(chave=chave, valor=valor, atualizado_por=usuario_id))
            else:
                linha.valor, linha.atualizado_por = valor, usuario_id
        sessao.commit()


def aplicar(config_yaml: Config, ajustes_yaml: Ajustes, valores: dict[str, Any]) -> tuple[Config, Ajustes]:
    """Config e Ajustes com os valores do banco por cima dos do config.yaml. Um valor inválido no banco (editado à
    mão) é ignorado com aviso no log, para o sistema não deixar de iniciar."""
    try:
        valores = validar({k: v for k, v in valores.items() if k in CAMPOS},
                          valores_atuais(config_yaml, ajustes_yaml))
    except ErroSistema as erro:
        log.warning("Ajustes do banco (config_sistema) ignorados: %s", erro)
        return config_yaml, ajustes_yaml
    v = {**valores_atuais(config_yaml, ajustes_yaml), **valores}
    config = replace(config_yaml,
                     ocorrencias=replace(config_yaml.ocorrencias, cooldown_s=v["cooldown_s"]),
                     deteccao=replace(config_yaml.deteccao, imgsz=v["imgsz"]),
                     arco=replace(config_yaml.arco, limiar_brilho=v["limiar_brilho"],
                                  fracao_max_saturada=v["fracao_max_saturada"],
                                  detectar_solda_ativa=v["detectar_solda_ativa"], fracao_min_maos=v["fracao_min_maos"],
                                  exigir_mascara_somente_com_arco=v["exigir_mascara_somente_com_arco"]))
    ajustes = replace(ajustes_yaml, retencao_dias=v["retencao_dias"], turnos=v["turnos"],
                      telegram_ativo=v["telegram_ativo"])
    return config, ajustes


def atualizar_contexto(ctx) -> None:
    """Recalcula a configuração com o que está no banco e entrega para quem a usa: câmeras (religadas, mantendo o
    cordão do turno), análise de arquivos, registro de ocorrências (turnos) e a rotina de retenção."""
    config, ajustes = aplicar(ctx.config_yaml, ctx.ajustes_yaml, ler_banco(ctx.fabrica))
    ctx.config_base, ctx.ajustes = config, ajustes
    ctx.registrador.turnos = ajustes.turnos
    ctx.uploads.config_base, ctx.uploads.ajustes = config, ajustes
    ctx.cameras.config_base, ctx.cameras.ajustes = config, ajustes
    if ctx.agendador is not None:
        mudar_retencao(ctx.agendador, ctx.fabrica, ctx.storage, ajustes.retencao_dias)
    ctx.cameras.reiniciar()
