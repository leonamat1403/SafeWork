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


def abrir(fonte: str) -> cv2.VideoCapture:
    if fonte.isdigit():
        api = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        return cv2.VideoCapture(int(fonte), api)
    return cv2.VideoCapture(fonte)


def main(argv: list[str] | None = None) -> int:
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

    escritor = None
    if modo_video:
        saida.parent.mkdir(parents=True, exist_ok=True)
    else:
        saida.mkdir(parents=True, exist_ok=True)
    fps_fonte = cap.get(cv2.CAP_PROP_FPS) or 15.0

    inicio = time.monotonic()
    ultimo_frame_salvo = -1e9
    salvos = lidos = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            lidos += 1
            # Tempo do frame: relógio (webcam) ou posição no vídeo (arquivo)
            t = time.monotonic() - inicio if ao_vivo else cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if ao_vivo and t > args.duracao_s:
                break
            if modo_video:
                if escritor is None:
                    altura, largura = frame.shape[:2]
                    escritor = cv2.VideoWriter(str(saida), cv2.VideoWriter_fourcc(*"mp4v"), fps_fonte, (largura, altura))
                escritor.write(frame)
            elif t - ultimo_frame_salvo >= args.intervalo_s:
                ok_img, buffer = cv2.imencode(".jpg", frame)
                if ok_img:
                    buffer.tofile(str(saida / f"{saida.name}_{salvos:04d}.jpg"))
                    salvos += 1
                    ultimo_frame_salvo = t
            if ao_vivo:
                previa = frame.copy()
                restante = max(0, args.duracao_s - t)
                texto = f"GRAVANDO {restante:4.0f}s" if modo_video else f"fotos: {salvos} | restam {restante:4.0f}s"
                cv2.putText(previa, texto + " (q = parar)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.imshow("Captura", previa)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
    finally:
        cap.release()
        if escritor is not None:
            escritor.release()
        cv2.destroyAllWindows()

    if modo_video:
        print(f"Vídeo salvo em {saida} ({lidos} frames).")
    else:
        print(f"{salvos} fotos salvas em {saida}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
