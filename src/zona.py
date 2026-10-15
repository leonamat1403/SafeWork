"""Zona de interesse (RD06, Fase 2): só avalia quem está dentro do posto/cabine de solda.

A zona é um polígono desenhado sobre a imagem da câmera (tela T06), guardado com coordenadas de 0 a 1 (fração da
largura e da altura), para continuar valendo se a resolução da câmera mudar. A pessoa está dentro quando o ponto
onde ela pisa (meio da base da caixa) cai dentro do polígono: quem passa no corredor ao fundo fica de fora.

Quem fica de fora não é avaliado nem gera ocorrência, mas continua BORRADO nas imagens (privacidade).
"""
from __future__ import annotations

import cv2
import numpy as np

from src.tipos import Pessoa

Ponto = tuple[float, float]


def ponto_da_pessoa(pessoa: Pessoa, largura: int, altura: int) -> Ponto:
    """Onde a pessoa pisa (meio da base da caixa), em fração da imagem."""
    x1, _, x2, y2 = pessoa.caixa
    return ((x1 + x2) / 2 / max(1, largura), y2 / max(1, altura))


def dentro_do_poligono(ponto: Ponto, poligono: list[Ponto]) -> bool:
    """Ponto dentro do polígono (regra do raio: conta quantas bordas uma linha horizontal cruza)."""
    x, y = ponto
    dentro = False
    for i in range(len(poligono)):
        (x1, y1), (x2, y2) = poligono[i], poligono[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            dentro = not dentro
    return dentro


def separar_por_zona(pessoas: list[Pessoa], poligono: list[Ponto] | None, largura: int,
                     altura: int) -> tuple[list[Pessoa], list[Pessoa]]:
    """(dentro, fora). Sem zona definida, todo mundo está dentro."""
    if not poligono or len(poligono) < 3:
        return pessoas, []
    dentro, fora = [], []
    for pessoa in pessoas:
        (dentro if dentro_do_poligono(ponto_da_pessoa(pessoa, largura, altura), poligono) else fora).append(pessoa)
    return dentro, fora


def desenhar_zona(img: np.ndarray, poligono: list[Ponto] | None) -> np.ndarray:
    """Contorno da zona por cima da imagem (linha branca fina com sombra, legível em fundo claro e escuro)."""
    if not poligono or len(poligono) < 3:
        return img
    altura, largura = img.shape[:2]
    pontos = np.array([[round(x * largura), round(y * altura)] for x, y in poligono], np.int32).reshape(-1, 1, 2)
    espessura = max(1, round(img.shape[1] / 1280))
    cv2.polylines(img, [pontos], True, (30, 30, 30), espessura + 2, cv2.LINE_AA)
    cv2.polylines(img, [pontos], True, (255, 255, 255), espessura, cv2.LINE_AA)
    return img
