from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Config, carregar_config

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def config() -> Config:
    """Configuração real do projeto (config.yaml), posto padrão."""
    return carregar_config(RAIZ / "config.yaml")
