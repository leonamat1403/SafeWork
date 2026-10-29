"""Mapeamento de classes duplicadas e limiar de confiança por EPI (RF03, RF15) – sem carregar modelos."""
from src.config import carregar_config
from src.detector import classe_interna, mapear_deteccoes
from tests.conftest import RAIZ

CAIXA = (0.0, 0.0, 10.0, 10.0)


def test_classes_duplicadas_viram_a_mesma_classe_interna(config):
    """Nomes diferentes da mesma classe (luvas, calçado, avental) viram a mesma classe interna."""
    m = config.mapeamento_classes
    assert classe_interna("Welding Gloves", m) == classe_interna("welding-glove", m) == "luvas"
    assert classe_interna("Safety Shoes", m) == classe_interna("welding-shose", m) == "calcado"
    assert classe_interna("Welding Apron", m) == classe_interna("apron", m) == "avental"


def test_mascara_e_capacete_de_solda_viram_mascara(config):
    """Máscara de solda e capacete viram a classe mascara."""
    m = config.mapeamento_classes
    for nome in ("Welding Mask", "helmet", "Helmet", "mascara"):
        assert classe_interna(nome, m) == "mascara"


def test_limiar_de_confianca_por_epi(config):
    """Detecções abaixo do limiar de confiança do EPI são descartadas."""
    brutas = [("mascara", 0.50, CAIXA), ("mascara", 0.40, CAIXA)]       # limiar da máscara: 0,45
    assert [d.conf for d in mapear_deteccoes(brutas, config)] == [0.50]


def test_epis_inativos_e_classes_desconhecidas_sao_descartados(config):
    """EPIs inativos e classes desconhecidas são descartados; só a máscara fica."""
    brutas = [("Welding Gloves", 0.9, CAIXA), ("bone", 0.9, CAIXA), ("Helmet", 0.9, CAIXA)]
    deteccoes = mapear_deteccoes(brutas, config)
    assert [(d.classe, d.epi) for d in deteccoes] == [("mascara", "mascara")]


def test_limiar_do_posto_e_respeitado():
    """O limiar de confiança definido para o posto é respeitado."""
    cfg = carregar_config(RAIZ / "config.yaml", posto="corte_01")        # máscara exige 0,55 neste posto
    assert mapear_deteccoes([("mascara", 0.50, CAIXA)], cfg) == []
