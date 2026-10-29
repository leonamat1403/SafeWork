"""[FASE 2] Registro de ocorrências: Fase 1 decide, Fase 2 borra, grava a imagem e grava no banco."""
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Ocorrencia
from app.privacy import Borrador
from app.registro import RegistradorOcorrencias
from app.storage import StorageDisco
from src.compliance import avaliar_frame
from src.occurrences import GerenciadorOcorrencias
from src.occurrences import Ocorrencia as OcorrenciaDetectada
from src.pipeline import ResultadoFrame
from tests.auxiliares import REGIAO_CABECA_ESPERADA, ROSTO_DESCOBERTO, ROSTO_DETECTADO, criar_pessoa
from tests.conftest import detalhe

UTC = timezone.utc
TURNOS = {"1": "06:00-14:00", "2": "14:00-22:00", "3": "22:00-06:00"}


@pytest.fixture
def registrador(fabrica, storage):
    """Registrador de ocorrências ligado ao banco e ao armazenamento de teste."""
    return RegistradorOcorrencias(fabrica, storage, Borrador(None), TURNOS)


@pytest.fixture
def resultado(config):
    """Uma pessoa de frente, SEM máscara, rosto descoberto (o detector de rostos achou o rosto)."""
    avaliacoes = avaliar_frame([criar_pessoa(ROSTO_DESCOBERTO)], [], config, rostos=[ROSTO_DETECTADO])
    return ResultadoFrame(avaliacoes, [], False, 0.0, [ROSTO_DETECTADO])


def detectada(quando: datetime) -> OcorrenciaDetectada:
    """Ocorrência detectada pela Fase 1 (sem máscara, rosto visível) na data e hora informadas."""
    return OcorrenciaDetectada(data_hora=quando, tempo_s=10.0, frame=100, track_id=1, epis_faltantes=["mascara"],
                               situacao={"mascara": "rosto visível sem máscara"}, fracao_nao_conforme={"mascara": 0.9},
                               epis_indeterminados=[], confianca_media={}, mascara_levantada=False)


def test_registra_no_banco_com_a_imagem_borrada(registrador, resultado, frame_texturizado, camera_id, data_dir,
                                               fabrica):
    """Registrar grava a ocorrência no banco com turno e pasta do dia de Brasília, e a imagem salva sai com a cabeça borrada."""
    quando = datetime(2026, 10, 15, 1, 30, tzinfo=UTC)          # 22:30 em Brasília -> turno 3
    registro = registrador.registrar(detectada(quando), frame_texturizado, resultado, camera_id)

    with fabrica() as s:
        lido = s.query(Ocorrencia).one()
    assert lido.uuid == registro.uuid and lido.camera_id == camera_id
    assert lido.turno == "3" and lido.data_hora == quando
    assert lido.epis_faltantes == ["mascara"] and lido.situacao == {"mascara": "rosto visível sem máscara"}
    assert lido.fracao_nao_conforme == {"mascara": 0.9} and lido.validacao == "PENDENTE"
    assert lido.caminho_imagem.startswith("ocorrencias/2026/10/14/")

    salva = cv2.imread(str(data_dir / lido.caminho_imagem))
    assert detalhe(salva, REGIAO_CABECA_ESPERADA) < 0.10 * detalhe(frame_texturizado, REGIAO_CABECA_ESPERADA)
    assert (data_dir / lido.caminho_thumb).exists()


def test_disco_cheio_registra_sem_imagem(fabrica, data_dir, resultado, frame_texturizado, camera_id):
    """Com o disco cheio, a ocorrência é registrada sem imagem e o registrador marca falta de espaço."""
    cheio = RegistradorOcorrencias(fabrica, StorageDisco(data_dir, espaco_minimo_mb=10**12), Borrador(None), TURNOS)
    registro = cheio.registrar(detectada(datetime.now(UTC)), frame_texturizado, resultado, camera_id)
    assert registro.caminho_imagem is None and registro.caminho_thumb is None
    assert cheio.sem_espaco is True


def test_falha_no_banco_nao_deixa_imagem_orfa(registrador, resultado, frame_texturizado, data_dir):
    """Se o banco recusa o registro, nenhuma imagem fica salva no disco."""
    with pytest.raises(IntegrityError):
        registrador.registrar(detectada(datetime.now(UTC)), frame_texturizado, resultado, camera_id=999)
    assert not [p for p in (data_dir / "ocorrencias").rglob("*") if p.is_file()]


def test_origem_invalida(registrador, resultado, frame_texturizado, camera_id):
    """Origem de registro desconhecida levanta ValueError."""
    with pytest.raises(ValueError):
        registrador.registrar(detectada(datetime.now(UTC)), frame_texturizado, resultado, camera_id, origem="email")


def test_da_fase_1_ao_banco(config, registrador, frame_texturizado, camera_id, fabrica):
    """Integração: 6 s de uma pessoa sem máscara a 10 FPS -> a regra da Fase 1 confirma 1 ocorrência (4 s, 75%),
    o cooldown impede repetição, e ela vai para o banco."""
    gerenciador = GerenciadorOcorrencias(config)
    pessoa = criar_pessoa(ROSTO_DESCOBERTO)
    inicio = datetime.now(UTC)
    for i in range(60):
        t = i / 10
        avaliacoes = avaliar_frame([pessoa], [], config, rostos=[ROSTO_DETECTADO])
        resultado = ResultadoFrame(avaliacoes, [], False, 0.0, [ROSTO_DETECTADO])
        for oc in gerenciador.atualizar(avaliacoes, t, i):
            oc.data_hora = inicio + timedelta(seconds=t)
            registrador.registrar(oc, frame_texturizado, resultado, camera_id)
    with fabrica() as s:
        registros = s.query(Ocorrencia).all()
    assert len(registros) == 1
    assert registros[0].epis_faltantes == ["mascara"]
    assert registros[0].fracao_nao_conforme["mascara"] >= 0.75
