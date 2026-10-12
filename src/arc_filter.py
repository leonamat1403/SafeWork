"""Filtro de frames saturados pelo arco elétrico (RF14).

O brilho do arco "estoura" a câmera: boa parte da imagem fica branca e o detector perde a máscara, o que
geraria falsos "SEM MÁSCARA". Quando a fração de pixels muito claros passa do limite, o frame é ignorado:
os modelos não rodam, os estados não mudam e nada é contado para ocorrências.
"""
from __future__ import annotations

import cv2
import numpy as np

from src.config import ConfigArco

LARGURA_ANALISE = 320   # a imagem é reduzida antes da contagem (mais rápido e o resultado praticamente não muda)


def fracao_saturada(frame: np.ndarray, limiar_brilho: int) -> float:
    """Fração (0 a 1) dos pixels com brilho maior ou igual a `limiar_brilho` (escala de cinza 0–255)."""
    cinza = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    altura, largura = cinza.shape[:2]
    if largura > LARGURA_ANALISE:
        nova_altura = max(1, round(altura * LARGURA_ANALISE / largura))
        # INTER_NEAREST amostra pixels sem fazer média, então um pixel estourado continua estourado
        cinza = cv2.resize(cinza, (LARGURA_ANALISE, nova_altura), interpolation=cv2.INTER_NEAREST)
    return float(np.count_nonzero(cinza >= limiar_brilho)) / cinza.size


def frame_saturado(frame: np.ndarray, config: ConfigArco) -> tuple[bool, float]:
    """Retorna (ignorar_frame, fração_saturada)."""
    fracao = fracao_saturada(frame, config.limiar_brilho)
    return fracao > config.fracao_max_saturada, fracao
