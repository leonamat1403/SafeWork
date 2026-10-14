"""Leitura de webcam, arquivo de vídeo ou stream de rede (RTSP/HTTP), com reconexão automática (RNF03).

Usado pela linha de comando (src/run.py) e pelo sistema web da Fase 2 (app/). Saiu do run.py sem mudança de lógica
(decisão F2-D2).
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger("epi_solda")


class ErroFonte(RuntimeError):
    """Câmera, arquivo ou stream indisponível."""


def ocultar_senha(texto: str) -> str:
    """Esconde usuário/senha de URLs (rtsp://usuario:senha@ip -> rtsp://***@ip) antes de mostrar no terminal."""
    return re.sub(r"//[^/@]+@", "//***@", texto)


class FonteVideo:
    """Webcam (número), arquivo de vídeo ou stream de rede (RTSP/HTTP), com reconexão automática (RNF03)."""

    def __init__(self, fonte: str) -> None:
        self.fonte = fonte
        if fonte.isdigit():
            self.tipo = "webcam"
        elif fonte.lower().startswith(("rtsp://", "rtmp://", "http://", "https://")):
            self.tipo = "rede"
        else:
            if not Path(fonte).exists():
                raise ErroFonte(f"Arquivo não encontrado: {fonte}")
            self.tipo = "arquivo"
        self._inicio = time.monotonic()
        self.cap = self._abrir()
        if not self.cap.isOpened():
            raise ErroFonte(f"Não foi possível abrir a fonte {ocultar_senha(fonte)!r} ({self.tipo}). "
                            "Confira se a câmera está conectada e não está em uso por outro programa.")

    def _abrir(self) -> cv2.VideoCapture:
        if self.tipo == "webcam":
            api = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY   # DirectShow abre webcams mais rápido no Windows
            return cv2.VideoCapture(int(self.fonte), api)
        return cv2.VideoCapture(self.fonte)

    @property
    def fps(self) -> float:
        return self.cap.get(cv2.CAP_PROP_FPS) or 0.0

    def _tempo(self) -> float:
        """Tempo do frame em segundos: posição no vídeo (arquivo) ou tempo desde o início (ao vivo)."""
        if self.tipo == "arquivo":
            return self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        return time.monotonic() - self._inicio

    def ler(self, parar: threading.Event | None = None) -> tuple[np.ndarray | None, float]:
        """Lê o próximo frame. Retorna (None, 0) no fim do arquivo; ao vivo, tenta reconectar até conseguir.

        `parar` (usado pelo sistema web): se for acionado durante a reconexão, desiste e retorna (None, 0).
        """
        ok, frame = self.cap.read()
        if ok:
            return frame, self._tempo()
        if self.tipo == "arquivo":
            return None, 0.0
        espera = 1
        while True:
            log.warning("Sem imagem de %s. Nova tentativa em %d s...", ocultar_senha(self.fonte), espera)
            if parar is None:
                time.sleep(espera)
            elif parar.wait(espera):
                return None, 0.0
            self.cap.release()
            self.cap = self._abrir()
            ok, frame = self.cap.read()
            if ok:
                log.info("Fonte reconectada.")
                return frame, self._tempo()
            espera = min(espera * 2, 30)

    def fechar(self) -> None:
        self.cap.release()
