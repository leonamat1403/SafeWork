"""Pessoas, pontos e máscaras SIMULADOS para os testes (sem câmera e sem modelos), RNF06.

Pessoa padrão: caixa (100, 100) – (300, 600), de frente para a câmera. Coordenadas em pixels; Y cresce para baixo.

        olhos (190,150) (210,150)       orelhas (180,160) (220,160)       nariz (200,162)
        ombro DIREITO (150,220)  ...  ombro ESQUERDO (250,220)   <- de frente: o esquerdo fica à direita na imagem

Região da cabeça esperada: x 160–240, y 116–220
  (centro x = 200; largura = 1,6 × max(40 entre orelhas, 0,5 × 100 entre ombros) = 80; altura = 1,3 × 80 = 104)
"""
from __future__ import annotations

from src.tipos import Caixa, DeteccaoEPI, Keypoint, Pessoa, Rosto

CAIXA_PADRAO: Caixa = (100, 100, 300, 600)
NARIZ = {0: (200, 162)}
OLHOS = {1: (210, 150), 2: (190, 150)}
ORELHAS = {3: (220, 160), 4: (180, 160)}
OMBROS_FRENTE = {5: (250, 220), 6: (150, 220)}
OMBROS_COSTAS = {5: (150, 220), 6: (250, 220)}   # de costas, a ordem dos ombros na imagem se inverte
QUADRIS = {11: (230, 380), 12: (170, 380)}

ROSTO_DESCOBERTO = {**NARIZ, **OLHOS, **ORELHAS, **OMBROS_FRENTE}
ROSTO_COBERTO = {**ORELHAS, **OMBROS_FRENTE}     # máscara abaixada: olhos e nariz somem
REGIAO_CABECA_ESPERADA = (160.0, 116.0, 240.0, 220.0)

MASCARA_ABAIXADA: Caixa = (165, 125, 235, 200)   # cobrindo o rosto
MASCARA_LEVANTADA: Caixa = (170, 95, 230, 140)   # sobre a testa/cabeça, centro (y=117,5) acima dos olhos (y=150)
MASCARA_NA_BANCADA: Caixa = (400, 450, 460, 500) # longe da cabeça

# Rosto DESCOBERTO encontrado pelo detector de rostos (YuNet), dentro da região da cabeça; olhos em y=150
ROSTO_DETECTADO = Rosto(caixa=(175, 135, 225, 200), olhos_y=150.0, conf=0.9)


def criar_pessoa(pontos: dict[int, tuple[float, float]], caixa: Caixa = CAIXA_PADRAO, track_id: int | None = 1,
                 conf: float = 0.9) -> Pessoa:
    """Pessoa com os pontos informados visíveis (conf alta) e os demais invisíveis (conf 0)."""
    kps = [Keypoint(0.0, 0.0, 0.0) for _ in range(17)]
    for indice, (x, y) in pontos.items():
        kps[indice] = Keypoint(float(x), float(y), conf)
    return Pessoa(caixa=caixa, keypoints=kps, track_id=track_id)


def deslocar(pontos: dict[int, tuple[float, float]], dx: float) -> dict[int, tuple[float, float]]:
    """Mesmos pontos, deslocados dx pixels na horizontal (para criar uma segunda pessoa)."""
    return {i: (x + dx, y) for i, (x, y) in pontos.items()}


def deslocar_caixa(caixa: Caixa, dx: float) -> Caixa:
    return (caixa[0] + dx, caixa[1], caixa[2] + dx, caixa[3])


def mascara(caixa: Caixa, conf: float = 0.8) -> DeteccaoEPI:
    return DeteccaoEPI(classe="mascara", epi="mascara", conf=conf, caixa=caixa)
