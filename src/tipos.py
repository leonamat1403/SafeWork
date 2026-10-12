"""Estruturas de dados simples compartilhadas entre os módulos.

Os módulos de regras (body_regions, compliance) trabalham só com estas estruturas, sem depender do
Ultralytics. Isso permite testá-los com caixas e pontos simulados (RNF06) e reaproveitá-los na Fase 2.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# Caixa no formato (x1, y1, x2, y2), em pixels da imagem. O eixo Y cresce PARA BAIXO.
Caixa = tuple[float, float, float, float]


class Estado(str, Enum):
    """Os três estados possíveis de um EPI para uma pessoa."""

    CONFORME = "CONFORME"
    NAO_CONFORME = "NAO_CONFORME"
    INDETERMINADO = "INDETERMINADO"   # região do corpo não visível: NUNCA gera ocorrência


@dataclass(frozen=True)
class Keypoint:
    """Um ponto do corpo (modelo de pose, padrão COCO) e a confiança de que ele está visível."""

    x: float
    y: float
    conf: float


@dataclass
class Pessoa:
    """Uma pessoa detectada pelo modelo de pose.

    `keypoints` tem 17 pontos no padrão COCO, ou fica vazia quando a pose não está disponível (modo fallback, RF12).
    """

    caixa: Caixa
    keypoints: list[Keypoint] = field(default_factory=list)
    track_id: int | None = None
    conf: float = 1.0

    @property
    def altura(self) -> float:
        return self.caixa[3] - self.caixa[1]


@dataclass(frozen=True)
class DeteccaoEPI:
    """Uma detecção do modelo de EPI, já com o nome interno da classe.

    `classe` é a classe do modelo (ex.: "avental") e `epi` é o EPI do sistema a que ela pertence
    (ex.: "protecao_corpo"). Para a máscara, as duas são "mascara".
    """

    classe: str
    epi: str
    conf: float
    caixa: Caixa


def area(caixa: Caixa) -> float:
    """Área de uma caixa (zero se ela for degenerada)."""
    return max(0.0, caixa[2] - caixa[0]) * max(0.0, caixa[3] - caixa[1])


def intersecao(a: Caixa, b: Caixa) -> float:
    """Área da interseção entre duas caixas."""
    largura = min(a[2], b[2]) - max(a[0], b[0])
    altura = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, largura) * max(0.0, altura)


def fracao_dentro(caixa_epi: Caixa, regiao: Caixa) -> float:
    """Quanto (0 a 1) da caixa do EPI está dentro da região do corpo.

    Usamos esta medida em vez do IoU porque a máscara e a região da cabeça têm tamanhos diferentes:
    uma máscara inteira dentro da cabeça daria IoU baixo, mas fração 1,0.
    """
    a = area(caixa_epi)
    return intersecao(caixa_epi, regiao) / a if a > 0 else 0.0


def centro(caixa: Caixa) -> tuple[float, float]:
    """Centro (x, y) de uma caixa."""
    return (caixa[0] + caixa[2]) / 2, (caixa[1] + caixa[3]) / 2
