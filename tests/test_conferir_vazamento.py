"""Conferência de vazamento entre o treino e os vídeos de teste (rodada v4) – sem modelos nem vídeos."""
import cv2
import numpy as np

from ferramentas.conferir_vazamento import centralizar, distancia_hamming, phash, quadros_de_teste


def cena(semente: int) -> np.ndarray:
    """Imagem sintética com formas e cores aleatórias (uma "cena" diferente para cada semente)."""
    rnd = np.random.default_rng(semente)
    imagem = np.full((360, 640, 3), rnd.integers(0, 255, 3), np.uint8)
    for _ in range(12):
        x, y = rnd.integers(0, 600), rnd.integers(0, 330)
        cv2.rectangle(imagem, (int(x), int(y)), (int(x + rnd.integers(20, 200)), int(y + rnd.integers(20, 150))),
                      tuple(int(c) for c in rnd.integers(0, 255, 3)), -1)
    return imagem


def test_phash_reconhece_a_mesma_imagem_redimensionada_e_recomprimida():
    """O hash perceptual de uma imagem reduzida e recomprimida fica próximo do original."""
    original = cena(1)
    reduzida = cv2.resize(original, (320, 180))
    _, jpeg = cv2.imencode(".jpg", reduzida, [cv2.IMWRITE_JPEG_QUALITY, 60])
    recomprimida = cv2.imdecode(jpeg, cv2.IMREAD_COLOR)
    assert distancia_hamming(phash(original), phash(recomprimida)) <= 6


def test_phash_separa_cenas_diferentes():
    """Cenas diferentes têm hashes perceptuais bem distantes."""
    assert distancia_hamming(phash(cena(1)), phash(cena(2))) > 15


def test_centralizar_tira_a_parte_comum_dos_vetores():
    """Centralizar tira a parte comum dos vetores, e vetores sem relação passam a ter similaridade perto de zero."""
    comum = np.full(64, 10.0)
    rnd = np.random.default_rng(0)
    a, b = comum + rnd.normal(size=(5, 64)), comum + rnd.normal(size=(7, 64))
    bruto = (a / np.linalg.norm(a, axis=1, keepdims=True)) @ (b / np.linalg.norm(b, axis=1, keepdims=True)).T
    ca, cb = centralizar(a, b)
    assert bruto.min() > 0.9                  # sem centralizar, tudo parece igual
    assert abs((ca @ cb.T).mean()) < 0.2      # centralizado, vetores sem relação ficam perto de 0
    assert np.allclose(np.linalg.norm(ca, axis=1), 1)


def test_quadros_de_teste_um_por_segundo_e_ignora_saidas_do_sistema(tmp_path):
    """Extrai um quadro por segundo dos vídeos de teste e ignora os vídeos de saída do sistema."""
    for nome in ("teste.mp4", "saida_video_teste.mp4"):
        gravador = cv2.VideoWriter(str(tmp_path / nome), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
        for _ in range(30):  # 3 s a 10 FPS
            gravador.write(cena(3)[:48, :64])
        gravador.release()
    quadros = quadros_de_teste(tmp_path)
    assert [round(t) for _, t, _ in quadros] == [0, 1, 2]
    assert all("saida_" not in video for video, _, _ in quadros)
