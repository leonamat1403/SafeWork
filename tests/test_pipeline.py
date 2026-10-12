"""Pipeline do run.py com um detector falso: filtro do arco antes dos modelos (RF14) e desenho."""
import numpy as np

from src.run import Pipeline, desenhar, ocultar_senha
from src.tipos import Estado
from tests.auxiliares import ROSTO_DESCOBERTO, criar_pessoa


class DetectorFalso:
    """Simula o Detector: sempre devolve uma pessoa de rosto descoberto e sem máscara."""

    def __init__(self):
        self.chamadas = 0

    def detectar(self, frame):
        self.chamadas += 1
        return [criar_pessoa(ROSTO_DESCOBERTO)], []


def frame(brilho: int) -> np.ndarray:
    return np.full((480, 640, 3), brilho, np.uint8)


def test_frame_saturado_nao_roda_os_modelos_nem_altera_estados(config):
    detector = DetectorFalso()
    pipeline = Pipeline(config, detector)
    normal = pipeline.processar(frame(60))
    assert detector.chamadas == 1 and not normal.saturado
    assert normal.avaliacoes[0].epis["mascara"].estado == Estado.NAO_CONFORME

    estourado = pipeline.processar(frame(255))
    assert estourado.saturado and estourado.fracao_saturada == 1.0
    assert detector.chamadas == 1                                  # os modelos não rodaram
    assert estourado.avaliacoes is normal.avaliacoes                # o último estado válido foi mantido


def test_desenhar_nao_altera_o_frame_original(config):
    original = frame(60)
    copia = original.copy()
    resultado = Pipeline(config, DetectorFalso()).processar(original)
    anotado = desenhar(original, resultado, ["FPS 10"], debug=True)
    assert anotado.shape == original.shape
    assert np.array_equal(original, copia)
    assert not np.array_equal(anotado, original)


def test_senha_do_rtsp_nao_aparece_no_terminal():
    assert ocultar_senha("rtsp://admin:segredo@192.168.0.10/stream") == "rtsp://***@192.168.0.10/stream"
    assert ocultar_senha("video.mp4") == "video.mp4"
