"""Data e hora: o banco guarda tudo em UTC; telas, pastas de imagens e turnos usam o horário de Brasília."""
from __future__ import annotations

import re
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")   # no Windows, o pacote tzdata fornece a tabela de fusos
_FAIXA = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")


def agora_utc() -> datetime:
    """Data e hora atuais em UTC, com fuso (o banco recusa data/hora sem fuso)."""
    return datetime.now(timezone.utc)


def para_utc(momento: datetime) -> datetime:
    """Converte para UTC. Data/hora sem fuso é tratada como horário local DESTE computador (a Fase 1 usa
    datetime.now() sem fuso)."""
    if momento.tzinfo is None:
        momento = momento.astimezone()
    return momento.astimezone(timezone.utc)


def para_local(momento: datetime) -> datetime:
    """Converte para o horário de Brasília (exibição, pastas por dia e turnos)."""
    return para_utc(momento).astimezone(FUSO)


def _hora(h: str, m: str, texto: str) -> time:
    if int(h) > 23 or int(m) > 59:
        raise ValueError(f"Horário inválido em {texto!r}")
    return time(int(h), int(m))


def validar_turnos(turnos: dict) -> dict[str, tuple[time, time]]:
    """Converte {"1": "06:00-14:00", ...} em {"1": (06:00, 14:00), ...}; levanta ValueError se o formato estiver errado."""
    faixas = {}
    for nome, texto in (turnos or {}).items():
        achado = _FAIXA.match(str(texto).strip())
        if not achado:
            raise ValueError(f"Turno {nome!r}: use o formato HH:MM-HH:MM (ex.: \"22:00-06:00\"), não {texto!r}")
        h1, m1, h2, m2 = achado.groups()
        faixas[str(nome)] = (_hora(h1, m1, texto), _hora(h2, m2, texto))
    return faixas


def turno_de(momento: datetime, turnos: dict) -> str | None:
    """Nome do turno em que `momento` cai (horário de Brasília), ou None se nenhum turno cobrir esse horário.

    Um turno que atravessa a meia-noite (ex.: 22:00-06:00) vale das 22:00 até as 05:59 do dia seguinte.
    """
    hora = para_local(momento).time()
    for nome, (inicio, fim) in validar_turnos(turnos).items():
        if inicio <= fim:
            if inicio <= hora < fim:
                return nome
        elif hora >= inicio or hora < fim:
            return nome
    return None
