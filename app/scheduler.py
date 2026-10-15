"""Rotinas automáticas (APScheduler, no mesmo processo do sistema): retenção, backup do banco e limpeza de uploads.

Horários (Brasília):  02:00 backup do banco  |  03:00 retenção  |  a cada 15 min, limpeza dos uploads temporários.
Cada rotina também pode ser chamada diretamente (testes, ou para rodar na hora).
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Ajustes
from app.models import Auditoria, Ocorrencia
from app.storage import ErroArmazenamento, Storage
from app.tempo import FUSO, agora_utc, para_local

log = logging.getLogger("epi_solda.rotinas")

PREFIXO_BACKUP = "epi_"


def apagar_ocorrencias_antigas(fabrica_sessoes: sessionmaker[Session], storage: Storage, dias: int,
                               agora: datetime | None = None) -> int:
    """Retenção (RF29): apaga as ocorrências com mais de `dias` dias. Primeiro as imagens, depois os registros, e
    grava a ação na auditoria. Devolve quantas foram apagadas."""
    agora = agora or agora_utc()
    limite = agora - timedelta(days=dias)
    with fabrica_sessoes() as sessao:
        antigas = sessao.scalars(select(Ocorrencia).where(Ocorrencia.data_hora < limite)).all()
        if not antigas:
            return 0
        for oc in antigas:
            for caminho in (oc.caminho_imagem, oc.caminho_thumb):
                if caminho:
                    try:
                        storage.apagar(caminho)
                    except ErroArmazenamento as erro:   # um arquivo com problema não trava a retenção
                        log.warning("Retenção: não foi possível apagar %s (%s)", caminho, erro)
        for oc in antigas:
            sessao.delete(oc)
        sessao.add(Auditoria(usuario_id=None, acao="retencao", data_hora=agora,
                             detalhes={"apagadas": len(antigas), "dias": dias, "anteriores_a": limite.isoformat()}))
        sessao.commit()
    log.info("Retenção: %d ocorrência(s) com mais de %d dias apagada(s)", len(antigas), dias)
    return len(antigas)


def fazer_backup(caminho_banco: Path, pasta_backups: Path, manter: int = 7, agora: datetime | None = None) -> Path:
    """Cópia do SQLite com a API de backup do sqlite3 (segura mesmo com o sistema gravando). Mantém as `manter`
    cópias mais recentes."""
    pasta_backups.mkdir(parents=True, exist_ok=True)
    destino = pasta_backups / f"{PREFIXO_BACKUP}{para_local(agora or agora_utc()):%Y%m%d_%H%M%S}.sqlite3"
    with closing(sqlite3.connect(caminho_banco)) as origem, closing(sqlite3.connect(destino)) as copia:
        origem.backup(copia)
    copias = sorted(pasta_backups.glob(f"{PREFIXO_BACKUP}*.sqlite3"))
    for antiga in copias[:-manter]:
        antiga.unlink()
    log.info("Backup do banco: %s (%d cópia(s) mantida(s))", destino.name, min(len(copias), manter))
    return destino


def limpar_uploads(pasta_uploads: Path, idade_max_s: float, agora_ts: float | None = None) -> int:
    """Apaga arquivos e pastas de uploads mais antigos que `idade_max_s` segundos (máximo de 1 h no prompt)."""
    if not pasta_uploads.exists():
        return 0
    agora_ts = time.time() if agora_ts is None else agora_ts
    apagados = 0
    for item in pasta_uploads.iterdir():
        if agora_ts - item.stat().st_mtime <= idade_max_s:
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)
        apagados += 1
    if apagados:
        log.info("Uploads temporários apagados: %d", apagados)
    return apagados


def _protegida(nome: str, funcao, *args, **kwargs) -> None:
    """Uma rotina com erro não pode derrubar o sistema: registra no log e tenta de novo no próximo horário."""
    try:
        funcao(*args, **kwargs)
    except Exception:
        log.exception("Falha na rotina %s", nome)


def mudar_retencao(agendador: BackgroundScheduler, fabrica_sessoes: sessionmaker[Session], storage: Storage,
                   dias: int) -> None:
    """Novo prazo de retenção definido na tela de Configurações (vale a partir da próxima execução, às 03:00)."""
    agendador.modify_job("retencao", args=["retenção", apagar_ocorrencias_antigas, fabrica_sessoes, storage, dias])


def iniciar_agendador(ajustes: Ajustes, fabrica_sessoes: sessionmaker[Session], storage: Storage) -> BackgroundScheduler:
    """Agenda as rotinas e inicia o agendador em segundo plano (pare com agendador.shutdown())."""
    agendador = BackgroundScheduler(timezone=FUSO)
    opcoes = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 3600}
    if ajustes.caminho_sqlite is not None:
        agendador.add_job(_protegida, CronTrigger(hour=2, minute=0, timezone=FUSO), id="backup",
                          args=["backup", fazer_backup, ajustes.caminho_sqlite, ajustes.data_dir / "backups",
                                ajustes.backups_manter], **opcoes)
    else:
        log.warning("Banco não é SQLite: o backup automático não está ativo (use a ferramenta do próprio banco).")
    agendador.add_job(_protegida, CronTrigger(hour=3, minute=0, timezone=FUSO), id="retencao",
                      args=["retenção", apagar_ocorrencias_antigas, fabrica_sessoes, storage, ajustes.retencao_dias],
                      **opcoes)
    agendador.add_job(_protegida, IntervalTrigger(minutes=15), id="uploads",
                      args=["limpeza de uploads", limpar_uploads, ajustes.data_dir / "uploads_temp",
                            ajustes.uploads_max_idade_s], **opcoes)
    agendador.start()
    log.info("Rotinas agendadas: backup 02:00, retenção 03:00 (%d dias), uploads a cada 15 min",
             ajustes.retencao_dias)
    return agendador
