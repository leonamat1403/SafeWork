"""Regiões do corpo a partir dos pontos simulados."""
import pytest

from src.body_regions import calcular_regioes
from src.tipos import Pessoa
from tests.auxiliares import (CAIXA_PADRAO, OMBROS_COSTAS, OMBROS_FRENTE, ORELHAS, QUADRIS, REGIAO_CABECA_ESPERADA,
                              ROSTO_COBERTO, ROSTO_DESCOBERTO, criar_pessoa)

CONF_KP = 0.5


def test_regiao_da_cabeca_pelos_pontos():
    """A região da cabeça sai dos pontos do corpo, com linha dos olhos e orientação de frente."""
    reg = calcular_regioes(criar_pessoa(ROSTO_DESCOBERTO), CONF_KP)
    assert reg.cabeca == pytest.approx(REGIAO_CABECA_ESPERADA)
    assert reg.linha_olhos_y == pytest.approx(150)
    assert reg.rosto_visivel and reg.orientacao == "frente" and not reg.fallback


def test_cabeca_localizada_mesmo_sem_olhos_visiveis():
    """Máscara abaixada cobre olhos e nariz: a cabeça ainda é encontrada pelas orelhas e ombros (RF07)."""
    reg = calcular_regioes(criar_pessoa(ROSTO_COBERTO), CONF_KP)
    assert reg.cabeca is not None
    assert reg.cabeca[3] == pytest.approx(220)          # base na linha dos ombros
    assert not reg.rosto_visivel
    assert reg.linha_olhos_y is None
    assert reg.orientacao == "indefinida"                # ombros na ordem "de frente", mas sem rosto


def test_orientacao_de_costas_pela_ordem_dos_ombros():
    """A ordem dos ombros sem rosto visível indica pessoa de costas."""
    reg = calcular_regioes(criar_pessoa({**ORELHAS, **OMBROS_COSTAS}), CONF_KP)
    assert reg.orientacao == "costas"


def test_so_ombros_visiveis_estima_a_cabeca_acima_deles():
    """Só com ombros visíveis, a cabeça é estimada acima deles e centrada entre eles."""
    reg = calcular_regioes(criar_pessoa(OMBROS_FRENTE), CONF_KP)
    x1, y1, x2, y2 = reg.cabeca
    assert y2 == pytest.approx(220) and y1 < 220
    assert (x1 + x2) / 2 == pytest.approx(200)           # centrada entre os ombros


def test_cabeca_nao_visivel():
    """Só com quadris não há como localizar a cabeça."""
    reg = calcular_regioes(criar_pessoa(QUADRIS), CONF_KP)
    assert reg.cabeca is None


def test_pontos_com_confianca_baixa_sao_ignorados():
    """Pontos com confiança abaixo do mínimo são ignorados: sem cabeça e sem rosto visível."""
    reg = calcular_regioes(criar_pessoa(ROSTO_DESCOBERTO, conf=0.3), CONF_KP)
    assert reg.cabeca is None and not reg.rosto_visivel


def test_fallback_sem_pose_usa_25_por_cento_superiores_da_caixa():
    """RF12: sem pontos do corpo, a cabeça é o quarto superior da caixa da pessoa."""
    reg = calcular_regioes(Pessoa(caixa=CAIXA_PADRAO), CONF_KP)
    assert reg.fallback
    assert reg.cabeca == pytest.approx((100, 100, 300, 225))


def test_com_detector_de_rostos_a_linha_dos_olhos_vem_do_rosto_detectado():
    """Com o detector de rostos, a linha dos olhos vem do rosto detectado."""
    from tests.auxiliares import ROSTO_DETECTADO
    reg = calcular_regioes(criar_pessoa(ROSTO_DESCOBERTO), CONF_KP, rostos=[ROSTO_DETECTADO])
    assert reg.rosto_visivel and reg.rosto_por_detector
    assert reg.linha_olhos_y == pytest.approx(150)
    assert reg.orientacao == "frente"


def test_rosto_detectado_fora_da_cabeca_nao_conta():
    """Rosto detectado longe da cabeça não conta como rosto visível."""
    from src.tipos import Rosto
    longe = Rosto(caixa=(500, 135, 550, 200), olhos_y=150.0, conf=0.9)
    reg = calcular_regioes(criar_pessoa(ROSTO_DESCOBERTO), CONF_KP, rostos=[longe])
    assert not reg.rosto_visivel
    assert reg.orientacao == "indefinida"      # a pose "viu" rosto, mas o detector não confirmou
