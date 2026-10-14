"""[FASE 2] Rotinas automáticas: retenção (RF29), backup diário do banco e limpeza de uploads temporários."""
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone

from app.config import carregar_ajustes
from app.models import Auditoria, Ocorrencia
from app.privacy import Borrador
from app.registro import RegistradorOcorrencias
from app.scheduler import apagar_ocorrencias_antigas, fazer_backup, iniciar_agendador, limpar_uploads
from src.compliance import avaliar_frame
from src.pipeline import ResultadoFrame
from tests.auxiliares import ROSTO_DESCOBERTO, criar_pessoa
from tests.test_fase2_registro import TURNOS, detectada

UTC = timezone.utc
AGORA = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)


def registrar(fabrica, storage, config, frame, camera_id, quando):
    avaliacoes = avaliar_frame([criar_pessoa(ROSTO_DESCOBERTO)], [], config)
    resultado = ResultadoFrame(avaliacoes, [], False, 0.0)
    return RegistradorOcorrencias(fabrica, storage, Borrador(None), TURNOS).registrar(
        detectada(quando), frame, resultado, camera_id)


def test_retencao_apaga_imagens_e_registros_antigos_e_audita(fabrica, storage, config, frame_texturizado, camera_id,
                                                              data_dir):
    antiga = registrar(fabrica, storage, config, frame_texturizado, camera_id, AGORA - timedelta(days=40))
    recente = registrar(fabrica, storage, config, frame_texturizado, camera_id, AGORA - timedelta(days=1))

    assert apagar_ocorrencias_antigas(fabrica, storage, dias=30, agora=AGORA) == 1

    assert not (data_dir / antiga.caminho_imagem).exists() and not (data_dir / antiga.caminho_thumb).exists()
    assert (data_dir / recente.caminho_imagem).exists()
    with fabrica() as s:
        assert [o.uuid for o in s.query(Ocorrencia)] == [recente.uuid]
        auditoria = s.query(Auditoria).one()
    assert auditoria.acao == "retencao" and auditoria.usuario_id is None
    assert auditoria.detalhes["apagadas"] == 1 and auditoria.detalhes["dias"] == 30


def test_retencao_sem_nada_para_apagar_nao_audita(fabrica, storage):
    assert apagar_ocorrencias_antigas(fabrica, storage, dias=30, agora=AGORA) == 0
    with fabrica() as s:
        assert s.query(Auditoria).count() == 0


def test_retencao_continua_se_uma_imagem_ja_sumiu(fabrica, storage, config, frame_texturizado, camera_id, data_dir):
    antiga = registrar(fabrica, storage, config, frame_texturizado, camera_id, AGORA - timedelta(days=40))
    (data_dir / antiga.caminho_imagem).unlink()
    assert apagar_ocorrencias_antigas(fabrica, storage, dias=30, agora=AGORA) == 1


def test_backup_mantem_as_7_copias_mais_recentes(banco, data_dir, camera_id):
    pasta = data_dir / "backups"
    banco_sqlite = data_dir / "db" / "epi.sqlite3"
    for dia in range(1, 10):
        ultima = fazer_backup(banco_sqlite, pasta, manter=7, agora=AGORA + timedelta(days=dia))
    copias = sorted(p.name for p in pasta.glob("epi_*.sqlite3"))
    assert len(copias) == 7 and copias[-1] == ultima.name
    with closing(sqlite3.connect(ultima)) as conexao:
        assert conexao.execute("SELECT count(*) FROM cameras").fetchone()[0] == 1   # a cópia tem os dados


def test_limpeza_de_uploads_apaga_so_os_antigos(tmp_path):
    antigo, novo, pasta_antiga = tmp_path / "antigo.mp4", tmp_path / "novo.mp4", tmp_path / "job_antigo"
    antigo.write_bytes(b"x")
    novo.write_bytes(b"x")
    pasta_antiga.mkdir()
    (pasta_antiga / "resultado.jpg").write_bytes(b"x")
    duas_horas_atras = time.time() - 7200
    for item in (antigo, pasta_antiga):
        os.utime(item, (duas_horas_atras, duas_horas_atras))

    assert limpar_uploads(tmp_path, idade_max_s=3600) == 2
    assert [p.name for p in tmp_path.iterdir()] == ["novo.mp4"]


def test_agendador_registra_as_tres_rotinas(fabrica, storage, data_dir, url_banco):
    ajustes = carregar_ajustes(ambiente={"DATA_DIR": str(data_dir), "DATABASE_URL": url_banco})
    agendador = iniciar_agendador(ajustes, fabrica, storage)
    try:
        assert {j.id for j in agendador.get_jobs()} == {"backup", "retencao", "uploads"}
        assert str(agendador.get_job("retencao").trigger.timezone) == "America/Sao_Paulo"
    finally:
        agendador.shutdown(wait=False)
