"""Ambiente do Alembic: liga as migrações às tabelas de app/models.py e ao banco do .env (DATABASE_URL)."""
from logging.config import fileConfig

from alembic import context

from app.database import Base, criar_engine
import app.models  # noqa: F401 (registra as tabelas em Base.metadata)

config = context.config

# Pelo terminal (`alembic upgrade head`), o log vem do alembic.ini. Pelo sistema (app/database.py), o sistema já
# configurou o próprio log e pede para não mexer nele.
if config.config_file_name is not None and config.attributes.get("configurar_log", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def renderizar_tipo(tipo: str, objeto, autogen_context):
    """Nas migrações geradas, DataHoraUTC vira sa.DateTime (a conversão para UTC é feita no Python, não no banco)."""
    if tipo == "type" and isinstance(objeto, app.models.DataHoraUTC):
        return "sa.DateTime()"
    return False


def url_do_banco() -> str:
    """A URL passada pelo sistema ou, se vazia (uso pelo terminal), a do .env."""
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    from app.config import carregar_ajustes
    return carregar_ajustes().database_url


def run_migrations_offline() -> None:
    """Gera o SQL sem conectar ao banco (`alembic upgrade head --sql`)."""
    context.configure(url=url_do_banco(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, render_as_batch=True,
                      render_item=renderizar_tipo)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migrações no banco. render_as_batch: no SQLite, alterar uma tabela exige recriá-la (o Alembic faz
    isso sozinho nesse modo)."""
    engine = criar_engine(url_do_banco())
    try:
        with engine.connect() as conexao:
            context.configure(connection=conexao, target_metadata=target_metadata, render_as_batch=True,
                              compare_type=True, render_item=renderizar_tipo)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
