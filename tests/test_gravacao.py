"""Gravação de vídeo: FPS inválido informado pela webcam (ex.: -1) não pode gerar arquivo corrompido."""
import cv2
import numpy as np
import pytest

from ferramentas.capturar import GravadorMp4
from src.run import GravadorVideo, estimar_fps, fps_valido


def ler_video(caminho):
    """Lê o vídeo e devolve o número de frames e o FPS gravado."""
    cap = cv2.VideoCapture(str(caminho))
    frames = 0
    while cap.read()[0]:
        frames += 1
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return frames, fps


def frame(i: int) -> np.ndarray:
    """Imagem de teste com o número do quadro escrito."""
    img = np.full((120, 160, 3), 50, np.uint8)
    cv2.putText(img, str(i), (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
    return img


def test_fps_valido_rejeita_valores_impossiveis():
    """FPS negativo, zero ou absurdo vira None; FPS normal é aceito."""
    assert fps_valido(-1) is None and fps_valido(0) is None and fps_valido(1000) is None
    assert fps_valido(30) == 30


def test_estimar_fps_pelo_ritmo_real():
    """O FPS é estimado pelos instantes reais dos frames, com 15 como padrão se houver poucos."""
    assert estimar_fps([i / 12 for i in range(31)]) == pytest.approx(12)
    assert estimar_fps([0.0]) == 15.0


@pytest.mark.parametrize("classe", [GravadorVideo, GravadorMp4])
def test_ao_vivo_mede_o_fps_e_grava_todos_os_frames(tmp_path, classe):
    """Ao vivo com FPS inválido da webcam, o gravador mede o ritmo real e grava todos os frames."""
    caminho = tmp_path / "ao_vivo.mp4"
    gravador = classe(caminho, -1, True)                 # a webcam informou FPS -1
    for i in range(40):
        gravador.gravar(i / 12, frame(i))               # frames chegando a 12 por segundo
    gravador.fechar()
    frames, fps = ler_video(caminho)
    assert frames == 40
    assert fps == pytest.approx(12, abs=0.5)


@pytest.mark.parametrize("classe", [GravadorVideo, GravadorMp4])
def test_gravacao_curta_tambem_e_salva(tmp_path, classe):
    """Uma gravação curta (5 frames) também é salva por inteiro."""
    caminho = tmp_path / "curto.mp4"
    gravador = classe(caminho, -1, True)
    for i in range(5):
        gravador.gravar(i / 10, frame(i))
    gravador.fechar()
    assert ler_video(caminho)[0] == 5


def test_arquivo_com_fps_invalido_usa_o_padrao(tmp_path):
    """Vídeo de arquivo com FPS inválido é gravado com o FPS padrão de 15."""
    caminho = tmp_path / "arquivo.mp4"
    gravador = GravadorVideo(caminho, -1, False)
    for i in range(10):
        gravador.gravar(i, frame(i))
    gravador.fechar()
    frames, fps = ler_video(caminho)
    assert frames == 10 and fps == pytest.approx(15, abs=0.5)
