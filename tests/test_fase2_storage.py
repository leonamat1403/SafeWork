"""[FASE 2] Armazenamento das imagens: só imagens borradas, só dentro de DATA_DIR, pastas pelo dia de Brasília."""
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np
import pytest

from app.privacy import Borrador
from app.storage import ErroArmazenamento, ErroDiscoCheio, StorageDisco

UTC = timezone.utc


@pytest.fixture
def imagem(frame_texturizado):
    """Imagem de ruído já borrada, no tipo aceito pelo armazenamento."""
    return Borrador(None).borrar(frame_texturizado, [])


def test_recusa_imagem_sem_blur(storage, frame_texturizado):
    """O armazenamento recusa imagem que não passou pelo borrador."""
    with pytest.raises(TypeError, match="ImagemBorrada"):
        storage.salvar_ocorrencia(frame_texturizado, str(uuid.uuid4()), datetime.now(UTC))


def test_salva_imagem_e_miniatura_na_pasta_do_dia_de_brasilia(storage, data_dir, imagem):
    """Salva imagem e miniatura em JPEG na pasta do dia de Brasília, sem deixar arquivos temporários."""
    uid = str(uuid.uuid4())
    quando = datetime(2026, 10, 15, 2, 0, tzinfo=UTC)          # em Brasília ainda é 14/10, 23:00
    caminhos = storage.salvar_ocorrencia(imagem, uid, quando)

    assert caminhos.imagem == f"ocorrencias/2026/10/14/{uid}.jpg"
    assert caminhos.thumb == f"thumbnails/2026/10/14/{uid}_thumb.jpg"
    assert (data_dir / caminhos.imagem).exists() and (data_dir / caminhos.thumb).exists()
    assert storage.ler(caminhos.imagem)[:2] == b"\xff\xd8"     # JPEG
    miniatura = cv2.imdecode(np.frombuffer(storage.ler(caminhos.thumb), np.uint8), cv2.IMREAD_COLOR)
    assert miniatura.shape[1] == 320
    assert storage.uso_mb() > 0
    assert not list(data_dir.rglob("*.tmp"))                    # gravação atômica não deixa restos


def test_nome_precisa_ser_um_uuid(storage, imagem):
    """Nome de arquivo que não é UUID (como um caminho com ..) é recusado."""
    with pytest.raises(ValueError):
        storage.salvar_ocorrencia(imagem, "../../outra_pasta/arquivo", datetime.now(UTC))


@pytest.mark.parametrize("caminho", ["../fora.jpg", "db/epi.sqlite3", "backups/x.sqlite3", "/etc/passwd"])
def test_nao_le_nem_apaga_fora_das_pastas_de_imagens(storage, caminho):
    """Ler ou apagar fora das pastas de imagens levanta ErroArmazenamento."""
    with pytest.raises(ErroArmazenamento):
        storage.ler(caminho)
    with pytest.raises(ErroArmazenamento):
        storage.apagar(caminho)


def test_apagar(storage, imagem):
    """Apagar remove o arquivo e devolve True; a segunda vez devolve False e a leitura falha."""
    caminhos = storage.salvar_ocorrencia(imagem, str(uuid.uuid4()), datetime.now(UTC))
    assert storage.apagar(caminhos.imagem) is True
    assert storage.apagar(caminhos.imagem) is False             # já não existia
    with pytest.raises(ErroArmazenamento):
        storage.ler(caminhos.imagem)


def test_imagem_4k_e_reduzida_para_full_hd(storage, data_dir):
    """Imagem 4K é reduzida para 1920 px de largura mantendo a proporção."""
    imagem_4k = Borrador(None).borrar(np.zeros((2160, 4096, 3), np.uint8), [])
    caminhos = storage.salvar_ocorrencia(imagem_4k, str(uuid.uuid4()), datetime.now(UTC))
    salva = cv2.imread(str(data_dir / caminhos.imagem))
    assert salva.shape[1] == 1920 and abs(salva.shape[0] - 2160 * 1920 / 4096) <= 1   # proporção mantida


def test_disco_cheio(data_dir, imagem):
    """Sem espaço mínimo livre no disco, salvar levanta ErroDiscoCheio."""
    cheio = StorageDisco(data_dir, espaco_minimo_mb=10**12)
    with pytest.raises(ErroDiscoCheio):
        cheio.salvar_ocorrencia(imagem, str(uuid.uuid4()), datetime.now(UTC))
