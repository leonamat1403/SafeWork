from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.config import Config, carregar_config

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def config() -> Config:
    """Configuração real do projeto (config.yaml), posto padrão."""
    return carregar_config(RAIZ / "config.yaml")


# --------------------------------------------------------------------------------------------------------------
# Fase 2: banco e armazenamento em pastas temporárias (nada toca a pasta data/ real)
# --------------------------------------------------------------------------------------------------------------
@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    from app.config import preparar_pastas

    pasta = tmp_path / "data"
    preparar_pastas(pasta)
    return pasta


@pytest.fixture
def url_banco(data_dir: Path) -> str:
    return f"sqlite:///{(data_dir / 'db' / 'epi.sqlite3').as_posix()}"


@pytest.fixture
def banco(url_banco: str):
    """(engine, fabrica_sessoes) de um SQLite novo, criado pelas migrações do Alembic (como no sistema real)."""
    from app.database import aplicar_migracoes, criar_engine, criar_fabrica_sessoes

    aplicar_migracoes(url_banco)
    engine = criar_engine(url_banco)
    yield engine, criar_fabrica_sessoes(engine)
    engine.dispose()


@pytest.fixture
def fabrica(banco):
    return banco[1]


@pytest.fixture
def storage(data_dir: Path):
    from app.storage import StorageDisco

    return StorageDisco(data_dir, espaco_minimo_mb=0)


@pytest.fixture
def camera_id(fabrica) -> int:
    from app.models import Camera, ConfigEpiCamera

    with fabrica() as sessao:
        camera = Camera(nome_posto="Posto de teste", tipo="webcam", origem="0",
                        epis=[ConfigEpiCamera(epi="mascara", conf_min=0.45)])
        sessao.add(camera)
        sessao.commit()
        return camera.id


@pytest.fixture
def frame_texturizado() -> np.ndarray:
    """Imagem 700 x 500 de ruído: qualquer blur aparece como queda forte de detalhe (variância do Laplaciano)."""
    return np.random.default_rng(0).integers(0, 256, (700, 500, 3), dtype=np.uint8)


def detalhe(img: np.ndarray, caixa: tuple[float, float, float, float]) -> float:
    """Quantidade de detalhe (bordas) de uma região: cai muito quando a região é borrada."""
    import cv2

    x1, y1, x2, y2 = map(int, caixa)
    cinza = cv2.cvtColor(np.ascontiguousarray(img[y1:y2, x1:x2]), cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(cinza, cv2.CV_64F).var())
