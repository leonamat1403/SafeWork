"""Filtro de frames saturados pelo arco (RF14)."""
import numpy as np
import pytest

from src.arc_filter import fracao_saturada, frame_saturado
from src.config import ConfigArco


def frame_com_fracao_branca(fracao: float, largura: int = 640, altura: int = 480, brilho: int = 255) -> np.ndarray:
    """Frame escuro com as primeiras linhas (fracao da altura) no brilho informado."""
    img = np.full((altura, largura, 3), 40, np.uint8)
    img[: round(altura * fracao)] = brilho
    return img


def test_frame_escuro_nao_e_saturado():
    """Frame escuro não é saturado e tem fração zero."""
    assert frame_saturado(frame_com_fracao_branca(0.0), ConfigArco()) == (False, 0.0)


def test_frame_com_30_por_cento_estourado_e_ignorado():
    """Frame com 30% estourado passa do limite e é ignorado."""
    ignorar, fracao = frame_saturado(frame_com_fracao_branca(0.30), ConfigArco())
    assert ignorar
    assert fracao == pytest.approx(0.30, abs=0.01)


def test_frame_com_10_por_cento_estourado_nao_e_ignorado():
    """Frame com 10% estourado fica abaixo do limite e não é ignorado."""
    ignorar, fracao = frame_saturado(frame_com_fracao_branca(0.10), ConfigArco())
    assert not ignorar and fracao == pytest.approx(0.10, abs=0.01)


def test_limiares_configuraveis():
    """Brilho e fração máxima são configuráveis e mudam o resultado."""
    frame = frame_com_fracao_branca(0.20, brilho=240)                     # pixels claros, mas abaixo de 245
    assert fracao_saturada(frame, limiar_brilho=245) == 0.0
    assert fracao_saturada(frame, limiar_brilho=240) == pytest.approx(0.20, abs=0.01)
    assert frame_saturado(frame, ConfigArco(limiar_brilho=240, fracao_max_saturada=0.25))[0] is False


def test_frame_grande_e_reduzido_sem_alterar_a_fracao():
    """Frame grande é reduzido antes de medir, sem mudar a fração saturada."""
    frame = frame_com_fracao_branca(0.50, largura=1920, altura=1080)
    assert fracao_saturada(frame, 245) == pytest.approx(0.50, abs=0.01)


def test_aceita_imagem_em_tons_de_cinza():
    """Imagem em tons de cinza também é aceita."""
    cinza = frame_com_fracao_branca(0.40)[:, :, 0]
    assert fracao_saturada(cinza, 245) == pytest.approx(0.40, abs=0.01)
