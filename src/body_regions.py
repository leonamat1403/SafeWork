"""Regiões do corpo a partir dos pontos do modelo de pose (padrão COCO).

Na Fase 1 só a região da CABEÇA é usada (máscara de solda). O cálculo não exige os olhos visíveis, porque a
máscara abaixada cobre olhos e nariz: a cabeça é localizada pelas orelhas e pelos ombros.

    ┌────────── cabeça ──────────┐  <- topo: estendido para cima, para caber a máscara levantada
    │          (o   o)           │  <- linha dos olhos
    │             ▾              │
    └────────────────────────────┘  <- base: linha dos ombros
  ●──────────── ombros ────────────●
"""
from __future__ import annotations

from dataclasses import dataclass

from src.tipos import Caixa, Keypoint, Pessoa, Rosto

# Índices dos pontos COCO
NARIZ, OLHO_ESQ, OLHO_DIR, ORELHA_ESQ, ORELHA_DIR = 0, 1, 2, 3, 4
OMBRO_ESQ, OMBRO_DIR = 5, 6
PONTOS_CABECA = (NARIZ, OLHO_ESQ, OLHO_DIR, ORELHA_ESQ, ORELHA_DIR)
PONTOS_ROSTO = (NARIZ, OLHO_ESQ, OLHO_DIR)

# Proporções da região da cabeça (ajustáveis após os testes de campo)
FATOR_LARGURA = 1.6        # largura da região = 1,6 × largura de referência da cabeça
FATOR_ALTURA = 1.3         # altura da região = 1,3 × largura (inclui folga acima da cabeça)
FRACAO_CABECA_FALLBACK = 0.25   # sem pose: cabeça = 25% superiores da caixa da pessoa (RF07/RF12)


@dataclass(frozen=True)
class RegioesCorpo:
    """Resultado das regiões de uma pessoa.

    - `cabeca`: caixa da região da cabeça, ou None se a cabeça não estiver visível;
    - `linha_olhos_y`: altura (y) da linha dos olhos, se olhos ou nariz estiverem visíveis;
    - `rosto_visivel`: rosto descoberto voltado para a câmera;
    - `orientacao`: "frente", "costas" ou "indefinida";
    - `fallback`: True quando a região veio só da caixa da pessoa (pose indisponível, RF12);
    - `rosto_por_detector`: True quando `rosto_visivel` e `linha_olhos_y` vieram do DETECTOR DE ROSTOS (confiável com
      máscara de solda); False quando vieram dos pontos do rosto da pose (que "enxergam" olhos atrás da máscara).
    """

    cabeca: Caixa | None
    linha_olhos_y: float | None
    rosto_visivel: bool
    orientacao: str
    fallback: bool
    rosto_por_detector: bool = False


def _visiveis(pessoa: Pessoa, indices: tuple[int, ...], conf_min: float) -> dict[int, Keypoint]:
    """Pontos da lista `indices` com confiança suficiente."""
    return {i: pessoa.keypoints[i] for i in indices
            if i < len(pessoa.keypoints) and pessoa.keypoints[i].conf >= conf_min}


def pontos_do_rosto_visiveis(pessoa: Pessoa, conf_min: float) -> int:
    """Quantos pontos do rosto (nariz e olhos) estão visíveis com confiança >= conf_min."""
    return len(_visiveis(pessoa, PONTOS_ROSTO, conf_min))


def orientacao_da_pessoa(pessoa: Pessoa, conf_min: float) -> str:
    """"frente", "costas" ou "indefinida".

    De frente para a câmera, o ombro ESQUERDO da pessoa aparece do lado DIREITO da imagem (x maior).
    De costas, a ordem se inverte. Isso diferencia "de costas" de "de frente com o rosto coberto pela máscara".
    """
    if _visiveis(pessoa, PONTOS_ROSTO, conf_min):
        return "frente"
    ombros = _visiveis(pessoa, (OMBRO_ESQ, OMBRO_DIR), conf_min)
    if len(ombros) == 2 and ombros[OMBRO_ESQ].x < ombros[OMBRO_DIR].x:
        return "costas"
    return "indefinida"


def regiao_cabeca(pessoa: Pessoa, conf_min: float) -> Caixa | None:
    """Região da cabeça pelos pontos do corpo; None se nem orelhas/olhos/nariz nem ombros estiverem visíveis."""
    cabeca = _visiveis(pessoa, PONTOS_CABECA, conf_min)
    ombros = _visiveis(pessoa, (OMBRO_ESQ, OMBRO_DIR), conf_min)
    if not cabeca and not ombros:
        return None

    # Centro horizontal: pontos da cabeça; se não houver, o meio dos ombros
    referencia = cabeca or ombros
    cx = sum(p.x for p in referencia.values()) / len(referencia)

    # Largura de referência: distância entre orelhas e/ou metade da largura dos ombros (o que for maior)
    candidatos = []
    if ORELHA_ESQ in cabeca and ORELHA_DIR in cabeca:
        candidatos.append(abs(cabeca[ORELHA_ESQ].x - cabeca[ORELHA_DIR].x))
    if len(ombros) == 2:
        candidatos.append(0.5 * abs(ombros[OMBRO_ESQ].x - ombros[OMBRO_DIR].x))
    x1, _, x2, _ = pessoa.caixa
    largura_ref = max(candidatos) if candidatos and max(candidatos) > 0 else 0.35 * (x2 - x1)
    largura = FATOR_LARGURA * largura_ref
    altura = FATOR_ALTURA * largura

    # Base: linha dos ombros; sem ombros, um pouco abaixo do ponto mais baixo da cabeça
    if ombros:
        base = sum(p.y for p in ombros.values()) / len(ombros)
    else:
        base = max(p.y for p in cabeca.values()) + 0.5 * largura_ref
    return (cx - largura / 2, max(0.0, base - altura), cx + largura / 2, base)


def linha_dos_olhos(pessoa: Pessoa, conf_min: float) -> float | None:
    """Altura (y) dos olhos; sem olhos visíveis, usa o nariz; sem nenhum dos dois, None."""
    olhos = _visiveis(pessoa, (OLHO_ESQ, OLHO_DIR), conf_min)
    if olhos:
        return sum(p.y for p in olhos.values()) / len(olhos)
    nariz = _visiveis(pessoa, (NARIZ,), conf_min)
    return nariz[NARIZ].y if nariz else None


def rosto_na_cabeca(cabeca: Caixa | None, rostos: list[Rosto]) -> Rosto | None:
    """O maior rosto detectado cujo centro está dentro da região da cabeça (ou None)."""
    if cabeca is None:
        return None
    dentro = [r for r in rostos
              if cabeca[0] <= (r.caixa[0] + r.caixa[2]) / 2 <= cabeca[2]
              and cabeca[1] <= (r.caixa[1] + r.caixa[3]) / 2 <= cabeca[3]]
    return max(dentro, key=lambda r: (r.caixa[2] - r.caixa[0]) * (r.caixa[3] - r.caixa[1]), default=None)


def calcular_regioes(pessoa: Pessoa, conf_keypoint: float, rostos: list[Rosto] | None = None) -> RegioesCorpo:
    """Calcula as regiões de uma pessoa; sem pontos do corpo, usa o fallback pela caixa (RF12).

    Com `rostos` (saída do detector de rostos), "rosto visível" e a linha dos olhos vêm dele. Com `rostos=None`
    (detector indisponível), vêm dos pontos do rosto da pose.
    """
    if not pessoa.keypoints:
        x1, y1, x2, y2 = pessoa.caixa
        cabeca = (x1, y1, x2, y1 + FRACAO_CABECA_FALLBACK * (y2 - y1))
        rosto = rosto_na_cabeca(cabeca, rostos) if rostos is not None else None
        return RegioesCorpo(cabeca=cabeca, linha_olhos_y=rosto.olhos_y if rosto else None,
                            rosto_visivel=rosto is not None, orientacao="frente" if rosto else "indefinida",
                            fallback=True, rosto_por_detector=rostos is not None)
    cabeca = regiao_cabeca(pessoa, conf_keypoint)
    if rostos is not None:
        rosto = rosto_na_cabeca(cabeca, rostos)
        orientacao = "frente" if rosto else orientacao_da_pessoa(pessoa, conf_keypoint)
        if orientacao == "frente" and rosto is None:   # a pose "viu" um rosto que o detector não viu
            orientacao = "indefinida"
        return RegioesCorpo(cabeca=cabeca, linha_olhos_y=rosto.olhos_y if rosto else None,
                            rosto_visivel=rosto is not None, orientacao=orientacao, fallback=False,
                            rosto_por_detector=True)
    return RegioesCorpo(
        cabeca=cabeca,
        linha_olhos_y=linha_dos_olhos(pessoa, conf_keypoint),
        rosto_visivel=bool(_visiveis(pessoa, PONTOS_ROSTO, conf_keypoint)),
        orientacao=orientacao_da_pessoa(pessoa, conf_keypoint),
        fallback=False,
    )
