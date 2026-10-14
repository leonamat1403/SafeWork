"""[FASE 2] Banco: migrações do Alembic iguais aos models, restrições e datas em UTC."""
from datetime import datetime, timezone

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, StatementError

from app.database import Base
from app.models import Camera, ConfigEpiCamera, Ocorrencia, Usuario

TABELAS = {"usuarios", "cameras", "config_epi_camera", "ocorrencias", "metricas_sessao", "auditoria", "config_sistema"}


def usuario(login="ana", perfil="SUPERVISOR"):
    return Usuario(nome="Ana", login=login, senha_hash="x", perfil=perfil)


def ocorrencia(camera_id, **extra):
    dados = dict(uuid="00000000-0000-0000-0000-000000000001", camera_id=camera_id,
                 data_hora=datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc), track_id=1, epis_faltantes=["mascara"])
    return Ocorrencia(**{**dados, **extra})


def test_migracoes_criam_as_tabelas_iguais_aos_models(banco):
    engine, _ = banco
    assert TABELAS <= set(inspect(engine).get_table_names())
    indices = {i["name"] for i in inspect(engine).get_indexes("ocorrencias")}
    assert {"ix_ocorrencias_data_hora", "ix_ocorrencias_camera_id", "ix_ocorrencias_validacao"} <= indices
    with engine.connect() as conexao:
        diferencas = compare_metadata(MigrationContext.configure(conexao, opts={"compare_type": True}), Base.metadata)
    assert diferencas == [], "app/models.py mudou: gere uma migração (alembic revision --autogenerate)"


def test_login_unico(fabrica):
    with fabrica() as s:
        s.add_all([usuario(), usuario()])
        with pytest.raises(IntegrityError):
            s.commit()


def test_perfil_so_admin_ou_supervisor(fabrica):
    with fabrica() as s:
        s.add(usuario(perfil="GERENTE"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_mesmo_epi_duas_vezes_na_mesma_camera(fabrica, camera_id):
    with fabrica() as s:
        s.add(ConfigEpiCamera(camera_id=camera_id, epi="mascara", conf_min=0.5))
        with pytest.raises(IntegrityError):
            s.commit()


def test_data_sem_fuso_e_recusada(fabrica, camera_id):
    with fabrica() as s:
        s.add(ocorrencia(camera_id, data_hora=datetime(2026, 10, 14, 12, 0)))
        with pytest.raises(StatementError, match="sem fuso"):
            s.commit()


def test_datas_voltam_em_utc(fabrica, camera_id):
    brasilia = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc).astimezone()
    with fabrica() as s:
        s.add(ocorrencia(camera_id, data_hora=brasilia))
        s.commit()
    with fabrica() as s:
        lida = s.query(Ocorrencia).one()
        assert lida.data_hora == datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
        assert lida.data_hora.tzinfo is not None
        assert lida.validacao == "PENDENTE" and lida.origem == "ao_vivo"


def test_apagar_camera_apaga_os_epis_dela(fabrica, camera_id):
    with fabrica() as s:
        s.delete(s.get(Camera, camera_id))
        s.commit()
        assert s.query(ConfigEpiCamera).count() == 0


def test_camera_com_ocorrencias_nao_pode_ser_apagada(fabrica, camera_id):
    """O histórico de ocorrências não some junto com a câmera (desativar em vez de apagar)."""
    with fabrica() as s:
        s.add(ocorrencia(camera_id))
        s.commit()
    with fabrica() as s:
        s.delete(s.get(Camera, camera_id))
        with pytest.raises(IntegrityError):
            s.commit()


def test_ocorrencia_de_camera_inexistente_e_recusada(fabrica):
    with fabrica() as s:
        s.add(ocorrencia(999))
        with pytest.raises(IntegrityError):
            s.commit()
