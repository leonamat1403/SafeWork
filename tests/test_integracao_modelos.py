"""Teste de integração com os modelos reais (pulado se models/*.pt não existirem)."""
from pathlib import Path

import pytest

from src.tipos import Estado

pytestmark = pytest.mark.modelos


@pytest.fixture
def pipeline(config):
    """Monta o pipeline com os modelos reais, ou pula o teste se os modelos não existirem."""
    if not (config.modelos.epi.exists() and config.modelos.pose.exists()):
        pytest.skip("modelos ausentes em models/ (rode: python -m src.run --baixar-modelos)")
    from src.detector import Detector
    from src.run import Pipeline
    return Pipeline(config, Detector(config))


def test_pessoas_sem_mascara_na_imagem_de_exemplo(pipeline):
    """bus.jpg (exemplo do Ultralytics): pessoas de frente, sem máscara de solda."""
    import ultralytics
    from src.run import ler_imagem

    img = ler_imagem(Path(ultralytics.__file__).parent / "assets" / "bus.jpg")
    resultado = pipeline.processar(img)
    assert len(resultado.avaliacoes) >= 3
    assert all(a.pessoa.track_id is not None for a in resultado.avaliacoes)
    estados = [a.epis["mascara"].estado for a in resultado.avaliacoes]
    assert Estado.CONFORME not in estados
    assert Estado.NAO_CONFORME in estados
