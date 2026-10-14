"""Conexão com o banco (SQLAlchemy) e migrações (Alembic).

SQLite por padrão; para PostgreSQL basta trocar a DATABASE_URL no .env. O esquema é sempre criado e atualizado pelas
migrações do Alembic (pasta alembic/), nunca por create_all, para que o banco de produção e o dos testes sejam iguais.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

RAIZ = Path(__file__).resolve().parent.parent

# Nomes fixos para índices e restrições: o Alembic precisa deles para alterar tabelas no SQLite
CONVENCAO_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base de todas as tabelas (app/models.py)."""

    metadata = MetaData(naming_convention=CONVENCAO_NOMES)


def criar_engine(url: str) -> Engine:
    """Engine do SQLAlchemy. No SQLite: chaves estrangeiras ligadas, modo WAL e espera de até 30 s se o arquivo
    estiver ocupado (as câmeras e as telas gravam ao mesmo tempo)."""
    if not url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True)
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _pragmas(conexao, _registro) -> None:
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    return engine


def criar_fabrica_sessoes(engine: Engine) -> sessionmaker[Session]:
    """Fábrica de sessões: `with fabrica() as sessao: ...`. Os objetos continuam legíveis depois do commit."""
    return sessionmaker(engine, expire_on_commit=False)


def aplicar_migracoes(url: str) -> None:
    """Cria ou atualiza as tabelas até a última migração (equivale a `alembic upgrade head`)."""
    from alembic import command
    from alembic.config import Config as ConfigAlembic

    if url.startswith("sqlite:///"):
        Path(url[len("sqlite:///"):]).parent.mkdir(parents=True, exist_ok=True)
    cfg = ConfigAlembic(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configurar_log"] = False   # o sistema já configurou o log (app/config.py)
    command.upgrade(cfg, "head")
