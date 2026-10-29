"""[FASE 2] Configuração (.env + config.yaml), pastas de dados, log e turnos/fuso horário."""
import logging
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler

import pytest

from app.config import PASTAS_DADOS, RAIZ, ErroAjustes, carregar_ajustes, configurar_logging, preparar_pastas
from app.tempo import janela_do_turno, para_local, para_utc, turno_de, validar_turnos

UTC = timezone.utc
TURNOS = {"1": "06:00-14:00", "2": "14:00-22:00", "3": "22:00-06:00"}


@pytest.mark.parametrize("hora_utc, turno", [
    ((10, 0), "1"),     # 07:00 em Brasília
    ((17, 0), "2"),     # 14:00 (início do turno 2)
    ((1, 30), "3"),     # 22:30
    ((8, 59), "3"),     # 05:59: o turno 3 atravessa a meia-noite
    ((9, 0), "1"),      # 06:00
])
def test_turno_pelo_horario_de_brasilia(hora_utc, turno):
    """Horário em UTC cai no turno certo pelo horário de Brasília, inclusive o turno que passa da meia-noite."""
    assert turno_de(datetime(2026, 10, 14, *hora_utc, tzinfo=UTC), TURNOS) == turno


def test_horario_sem_turno():
    """Horário fora de qualquer turno devolve None."""
    assert turno_de(datetime(2026, 10, 14, 3, 0, tzinfo=UTC), {"1": "06:00-14:00"}) is None


@pytest.mark.parametrize("agora, turno, inicio, fim", [
    # 14:30 em Brasília: turno 2, das 14:00 às 22:00 (17:00 a 01:00 UTC)
    (datetime(2026, 10, 14, 17, 30, tzinfo=UTC), "2", datetime(2026, 10, 14, 17, 0, tzinfo=UTC),
     datetime(2026, 10, 15, 1, 0, tzinfo=UTC)),
    # 22:30 do dia 13 em Brasília: turno 3, que só termina às 06:00 do dia 14
    (datetime(2026, 10, 14, 1, 30, tzinfo=UTC), "3", datetime(2026, 10, 14, 1, 0, tzinfo=UTC),
     datetime(2026, 10, 14, 9, 0, tzinfo=UTC)),
    # 02:00 do dia 14 em Brasília: turno 3, que começou às 22:00 do dia 13
    (datetime(2026, 10, 14, 5, 0, tzinfo=UTC), "3", datetime(2026, 10, 14, 1, 0, tzinfo=UTC),
     datetime(2026, 10, 14, 9, 0, tzinfo=UTC)),
])
def test_janela_do_turno_para_o_cordao(agora, turno, inicio, fim):
    """A janela do turno devolve nome, início e fim em UTC, inclusive quando atravessa a meia-noite."""
    assert janela_do_turno(agora, TURNOS) == (turno, inicio, fim)


def test_janela_sem_turno_sao_as_ultimas_8_horas():
    """Sem turno, a janela são as últimas 8 horas."""
    agora = datetime(2026, 10, 14, 3, 0, tzinfo=UTC)
    assert janela_do_turno(agora, {"1": "06:00-14:00"}) == (None, agora - timedelta(hours=8), agora)


@pytest.mark.parametrize("ruim", [{"1": "6h-14h"}, {"1": "25:00-06:00"}, {"1": "06:00 - 14:00"}])
def test_turno_mal_escrito(ruim):
    """Turno escrito fora do formato HH:MM-HH:MM levanta ValueError."""
    with pytest.raises(ValueError):
        validar_turnos(ruim)


def test_conversoes_de_fuso():
    """Conversões entre UTC e horário local usam Brasília e assumem horário local quando falta o fuso."""
    meio_dia_utc = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
    assert para_local(meio_dia_utc).hour == 9                    # Brasília: UTC-3
    sem_fuso = datetime(2026, 10, 14, 12, 0)
    assert para_utc(sem_fuso).tzinfo == UTC                      # sem fuso = horário local do computador


def test_ajustes_do_env_e_do_config_yaml(tmp_path):
    """Ajustes são lidos do ambiente e do config.yaml, com caminhos relativos à pasta do projeto."""
    ajustes = carregar_ajustes(ambiente={"DATA_DIR": "./dados_teste", "SECRET_KEY": " segredo "})
    assert ajustes.data_dir == (RAIZ / "dados_teste").resolve()  # relativo à pasta do projeto
    assert ajustes.database_url == f"sqlite:///{(ajustes.data_dir / 'db' / 'epi.sqlite3').as_posix()}"
    assert ajustes.caminho_sqlite == ajustes.data_dir / "db" / "epi.sqlite3"
    assert ajustes.secret_key == "segredo" and ajustes.admin_login_inicial == "admin"
    assert ajustes.turnos == TURNOS and ajustes.retencao_dias == 30
    assert ajustes.espaco_minimo_mb == 500 and ajustes.backups_manter == 7 and ajustes.uploads_max_idade_s == 3600


def test_url_sqlite_relativa_e_outros_bancos():
    """URL SQLite relativa vira caminho absoluto e outros bancos ficam como estão."""
    relativo = carregar_ajustes(ambiente={"DATABASE_URL": "sqlite:///./data/db/x.sqlite3"})
    assert relativo.database_url == f"sqlite:///{(RAIZ / 'data' / 'db' / 'x.sqlite3').as_posix()}"
    postgres = carregar_ajustes(ambiente={"DATABASE_URL": "postgresql://u@servidor/epi"})
    assert postgres.database_url == "postgresql://u@servidor/epi" and postgres.caminho_sqlite is None


def test_turnos_invalidos_no_config_yaml(tmp_path):
    """Turnos inválidos no config.yaml levantam ErroAjustes."""
    arquivo = tmp_path / "config.yaml"
    arquivo.write_text('turnos: {"1": "seis às duas"}\n', encoding="utf-8")
    with pytest.raises(ErroAjustes, match="turnos"):
        carregar_ajustes(config_yaml=arquivo, ambiente={})


def test_preparar_pastas(tmp_path):
    """preparar_pastas cria todas as pastas de dados."""
    preparar_pastas(tmp_path / "data")
    assert {p.name for p in (tmp_path / "data").iterdir()} == set(PASTAS_DADOS)


def test_log_em_arquivo_com_rotacao_sem_duplicar(tmp_path):
    """O log vai para arquivo com rotação e chamar a configuração de novo não duplica as saídas."""
    raiz = logging.getLogger()
    antes = list(raiz.handlers)
    try:
        configurar_logging(tmp_path / "logs")
        configurar_logging(tmp_path / "logs")                    # chamar de novo não duplica as saídas
        arquivos = [h for h in raiz.handlers if isinstance(h, RotatingFileHandler)
                    and h.baseFilename == str((tmp_path / "logs" / "app.log").resolve())]
        assert len(arquivos) == 1 and arquivos[0].maxBytes == 5 * 1024 * 1024 and arquivos[0].backupCount == 5
        logging.getLogger("epi_solda.teste").info("mensagem de teste")
        arquivos[0].flush()
        assert "mensagem de teste" in (tmp_path / "logs" / "app.log").read_text(encoding="utf-8")
    finally:
        for handler in list(raiz.handlers):
            if handler not in antes:
                raiz.removeHandler(handler)
                handler.close()
