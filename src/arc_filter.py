"""Arco elétrico: filtro de frames saturados (RF14) e "solda ativa" perto das mãos (RD03, Fase 2).

O brilho do arco "estoura" a câmera: boa parte da imagem fica branca e o detector perde a máscara, o que
geraria falsos "SEM MÁSCARA". Quando a fração de pixels muito claros passa do limite, o frame é ignorado:
os modelos não rodam, os estados não mudam e nada é contado para ocorrências.

Com um arco menor (que não estoura o quadro inteiro), o brilho fica concentrado perto da tocha, isto é, das mãos.
`fracao_perto_das_maos` mede os pixels estourados em volta de cada punho: acima de `fracao_min_maos`, a pessoa está
soldando (RD03).
"""
from __future__ import annotations

import cv2
import numpy as np

from src.config import ConfigArco
from src.tipos import Caixa, Pessoa

PULSO_ESQ, PULSO_DIR = 9, 10   # pontos COCO dos punhos

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


def regioes_das_maos(pessoa: Pessoa, conf_keypoint: float, raio: float) -> list[Caixa]:
    """Quadrados em volta de cada punho visível; o lado cresce com a altura da pessoa (perto/longe da câmera)."""
    _, y1, _, y2 = pessoa.caixa
    meio_lado = raio * max(1.0, y2 - y1)
    regioes = []
    for indice in (PULSO_ESQ, PULSO_DIR):
        if indice < len(pessoa.keypoints) and pessoa.keypoints[indice].conf >= conf_keypoint:
            ponto = pessoa.keypoints[indice]
            regioes.append((ponto.x - meio_lado, ponto.y - meio_lado, ponto.x + meio_lado, ponto.y + meio_lado))
    return regioes


def fracao_saturada_na_regiao(frame: np.ndarray, caixa: Caixa, limiar_brilho: int) -> float:
    """Fração dos pixels estourados dentro da caixa (a parte fora da imagem é ignorada)."""
    altura, largura = frame.shape[:2]
    x1, y1 = max(0, int(caixa[0])), max(0, int(caixa[1]))
    x2, y2 = min(largura, int(caixa[2])), min(altura, int(caixa[3]))
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return fracao_saturada(frame[y1:y2, x1:x2], limiar_brilho)


def fracao_perto_das_maos(frame: np.ndarray, pessoa: Pessoa, config: ConfigArco, conf_keypoint: float) -> float | None:
    """Maior fração de pixels estourados em volta dos punhos da pessoa; None se nenhum punho estiver visível."""
    regioes = regioes_das_maos(pessoa, conf_keypoint, config.raio_maos)
    if not regioes:
        return None
    return max(fracao_saturada_na_regiao(frame, caixa, config.limiar_brilho) for caixa in regioes)
