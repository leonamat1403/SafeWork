"""Captura imagens da webcam (ou de um vídeo) para treino e testes.

Dois modos, escolhidos pela extensão de --saida:
  - PASTA  -> salva 1 frame a cada --intervalo-s segundos (ex.: fotos de pessoas SEM máscara, para usar como
              exemplos negativos no treino; essas fotos não precisam ser anotadas);
  - .mp4   -> grava um vídeo (ex.: vídeo de teste para medir falsos positivos com o run.py).

Exemplos (na pasta do projeto):
    python ferramentas/capturar.py --saida testes_campo/negativos_webcam/sessao1
    python ferramentas/capturar.py --saida testes_campo/teste_sem_mascara.mp4 --duracao-s 60
    python ferramentas/capturar.py --fonte testes_campo/video1.mp4 --saida testes_campo/frames_video1

Tudo fica em testes_campo/ (fora do git). Só capture pessoas que autorizaram.
Durante a captura: mexa a cabeça devagar (frente, inclinada para cima/baixo/lados, perfil, de costas),
mude de distância e, se possível, de iluminação. Tecla q (ou ESC) termina antes do tempo.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

FRAMES_PARA_MEDIR_FPS = 30   # a webcam informa um FPS pouco confiável (às vezes -1); medimos o real
FPS_PADRAO = 15.0  # usado quando não dá para saber o FPS real


def abrir(fonte: str) -> cv2.VideoCapture:
    """Abre a webcam (se `fonte` for só dígitos) ou um arquivo de vídeo; no Windows a webcam abre pelo DirectShow."""
    if fonte.isdigit():
        api = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        return cv2.VideoCapture(int(fonte), api)
    return cv2.VideoCapture(fonte)


def fps_valido(valor: float) -> float | None:
    """O FPS informado só é aceito se for plausível (1 a 120); senão, None."""
    return float(valor) if 1 <= valor <= 120 else None


def estimar_fps(tempos: list[float]) -> float:
    """FPS real a partir dos instantes (em segundos) em que os frames chegaram, limitado a 1–60."""
    if len(tempos) < 2 or tempos[-1] <= tempos[0]:
        return FPS_PADRAO
    return min(60.0, max(1.0, (len(tempos) - 1) / (tempos[-1] - tempos[0])))


class GravadorMp4:
    """Grava .mp4; ao vivo, guarda os primeiros frames até medir o FPS real e só então cria o arquivo."""

    def __init__(self, caminho: Path, fps_informado: float, ao_vivo: bool) -> None:
        """Na webcam o FPS fica None até ser medido; em arquivo usa o informado (ou o padrão, se for implausível)."""
        self.caminho = caminho
        self.fps = None if ao_vivo else (fps_valido(fps_informado) or FPS_PADRAO)
        self._pendentes: list[tuple[float, np.ndarray]] = []
        self._escritor = None
        self.frames = 0

    def _criar(self, fps: float, frame: np.ndarray) -> None:
        """Cria a pasta e o arquivo .mp4, com o tamanho do primeiro frame e o FPS definido."""
        altura, largura = frame.shape[:2]
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._escritor = cv2.VideoWriter(str(self.caminho), cv2.VideoWriter_fourcc(*"mp4v"), fps, (largura, altura))
        self.fps = fps

    def gravar(self, t: float, frame: np.ndarray) -> None:
        """Grava um frame; enquanto o FPS não foi medido, guarda os frames na memória (`_pendentes`)."""
        if self._escritor is None:
            self._pendentes.append((t, frame))
            if self.fps is None and len(self._pendentes) < FRAMES_PARA_MEDIR_FPS:
                return
            self._descarregar()
            return
        self._escritor.write(frame)
        self.frames += 1

    def _descarregar(self) -> None:
        """Define o FPS (medindo, se preciso), cria o arquivo e grava os frames que estavam esperando."""
        if not self._pendentes:
            return
        fps = self.fps or estimar_fps([t for t, _ in self._pendentes])
        self._criar(fps, self._pendentes[0][1])
        for _, frame in self._pendentes:
            self._escritor.write(frame)
            self.frames += 1
        self._pendentes.clear()

    def fechar(self) -> None:
        """Termina a gravação (gravando antes o que ainda estava pendente) e libera o arquivo."""
        if self._escritor is None:
            self._descarregar()          # gravação curta: menos frames do que o necessário para medir o FPS
        if self._escritor is not None:
            self._escritor.release()


def main(argv: list[str] | None = None) -> int:
    """Captura da fonte até o vídeo acabar, a duração passar ou o usuário apertar q/ESC.

    Devolve 0, ou 1 se a fonte não abriu.
    """
    p = argparse.ArgumentParser(description="Captura frames ou vídeo da webcam/vídeo para o projeto.")
    p.add_argument("--fonte", default="0", help="webcam (0, 1, ...) ou arquivo de vídeo (padrão: webcam 0)")
    p.add_argument("--saida", required=True, help="pasta (modo frames) ou arquivo .mp4 (modo vídeo)")
    p.add_argument("--intervalo-s", type=float, default=0.5, help="modo frames: segundos entre fotos (padrão 0,5)")
    p.add_argument("--duracao-s", type=float, default=60, help="tempo máximo de captura da webcam (padrão 60 s)")
    args = p.parse_args(argv)

    saida = Path(args.saida)
    modo_video = saida.suffix.lower() == ".mp4"
    ao_vivo = args.fonte.isdigit()
    cap = abrir(args.fonte)
    if not cap.isOpened():
        print(f"Não foi possível abrir a fonte {args.fonte!r}.")
        return 1
    if not modo_video:
        saida.mkdir(parents=True, exist_ok=True)
    gravador = GravadorMp4(saida, cap.get(cv2.CAP_PROP_FPS), ao_vivo) if modo_video else None

    inicio = time.monotonic()
    ultimo_frame_salvo = -1e9  # força salvar já o primeiro frame
    salvos = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            # Tempo do frame: relógio (webcam) ou posição no vídeo (arquivo)
            t = time.monotonic() - inicio if ao_vivo else cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if ao_vivo and t > args.duracao_s:
                break
            if gravador is not None:
                gravador.gravar(t, frame)
            elif t - ultimo_frame_salvo >= args.intervalo_s:
                ok_img, buffer = cv2.imencode(".jpg", frame)
                if ok_img:
                    # tofile em vez de imwrite: funciona também com caminhos com acentos no Windows.
                    buffer.tofile(str(saida / f"{saida.name}_{salvos:04d}.jpg"))
                    salvos += 1
                    ultimo_frame_salvo = t
            if ao_vivo:
                # O texto é desenhado numa cópia: o frame salvo ou gravado fica sem desenho.
                previa = frame.copy()
                restante = max(0, args.duracao_s - t)
                texto = f"GRAVANDO {restante:4.0f}s" if modo_video else f"fotos: {salvos} | restam {restante:4.0f}s"
                cv2.putText(previa, texto + " (q = parar)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.imshow("Captura", previa)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
    finally:
        cap.release()
        if gravador is not None:
            gravador.fechar()
        cv2.destroyAllWindows()

    if gravador is not None:
        print(f"Vídeo salvo em {saida} ({gravador.frames} frames, {gravador.fps or 0:.1f} FPS).")
    else:
        print(f"{salvos} fotos salvas em {saida}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
