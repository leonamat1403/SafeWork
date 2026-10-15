"""Processamento de um frame (filtro do arco -> modelos -> regras) e desenho do resultado.

Usado pela linha de comando (src/run.py) e pelo sistema web da Fase 2 (app/). Saiu do run.py sem mudança de lógica
(decisão F2-D2).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from src.arc_filter import fracao_perto_das_maos, frame_saturado
from src.compliance import CORES_BGR, AvaliacaoPessoa, avaliar_frame
from src.config import Config
from src.tipos import DeteccaoEPI, Rosto


@dataclass
class ResultadoFrame:
    avaliacoes: list[AvaliacaoPessoa]
    deteccoes: list[DeteccaoEPI]
    saturado: bool
    fracao_saturada: float
    rostos: list[Rosto] | None = None


class Pipeline:
    """Filtro do arco -> modelos -> regras. Guarda o último resultado válido para os frames ignorados."""

    def __init__(self, config: Config, detector) -> None:
        self.config = config
        self.detector = detector
        self.ultimas_avaliacoes: list[AvaliacaoPessoa] = []
        self.ultimas_deteccoes: list[DeteccaoEPI] = []
        self.ultimos_rostos: list[Rosto] | None = None
        self._arco_ate: dict[int, float] = {}   # RD03: track_id -> até quando a pessoa conta como "soldando"

    def processar(self, frame: np.ndarray, t: float | None = None) -> ResultadoFrame:
        """Processa um frame. `t` (segundos) é o tempo do vídeo ou da câmera; sem ele, usa o relógio do computador."""
        saturado, fracao = frame_saturado(frame, self.config.arco)
        if saturado:
            # RF14: frame estourado pelo arco não muda nenhum estado; repete o último resultado válido
            return ResultadoFrame(self.ultimas_avaliacoes, self.ultimas_deteccoes, True, fracao, self.ultimos_rostos)
        pessoas, deteccoes, rostos = self.detector.detectar(frame)
        arco_ativo, arco_maos = self._solda_ativa(frame, pessoas, time.monotonic() if t is None else t)
        self.ultimas_avaliacoes = avaliar_frame(pessoas, deteccoes, self.config, rostos, arco_ativo, arco_maos)
        self.ultimas_deteccoes = deteccoes
        self.ultimos_rostos = rostos
        return ResultadoFrame(self.ultimas_avaliacoes, deteccoes, False, fracao, rostos)

    def _solda_ativa(self, frame: np.ndarray, pessoas: list, t: float) -> tuple[list[bool] | None, list | None]:
        """RD03: arco aceso perto das mãos de cada pessoa. O arco pisca; por isso a pessoa continua "soldando" por
        `manter_aceso_s` depois da última vez em que o brilho foi visto."""
        cfg = self.config.arco
        if not cfg.detectar_solda_ativa:
            return None, None
        ativos, fracoes = [], []
        for pessoa in pessoas:
            fracao = fracao_perto_das_maos(frame, pessoa, cfg, self.config.deteccao.conf_keypoint)
            visto = fracao is not None and fracao >= cfg.fracao_min_maos
            if pessoa.track_id is None:
                ativos.append(visto)
            else:
                if visto:
                    self._arco_ate[pessoa.track_id] = t + cfg.manter_aceso_s
                ativos.append(t <= self._arco_ate.get(pessoa.track_id, float("-inf")))
            fracoes.append(fracao)
        for track_id in [k for k, ate in self._arco_ate.items() if ate < t - 60]:   # esquece quem sumiu
            del self._arco_ate[track_id]
        return ativos, fracoes


LARGURA_REFERENCIA = 1280   # até esta largura, texto e linhas têm o tamanho original; acima, crescem junto


def fator_desenho(img: np.ndarray) -> float:
    """Quanto aumentar textos e linhas para continuarem legíveis em imagens grandes (ex.: 4K -> 3,2x)."""
    return max(1.0, img.shape[1] / LARGURA_REFERENCIA)


def _texto_com_fundo(img: np.ndarray, texto: str, x: int, y: int, fundo: tuple[int, int, int],
                     escala: float = 0.55, fator: float = 1.0) -> None:
    """Escreve um texto com retângulo de fundo; (x, y) é o canto inferior esquerdo do fundo."""
    escala, espessura = escala * fator, max(1, round(fator))
    (larg, alt), base = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, espessura)
    y = max(alt + base + 2, y)
    cor_texto = (0, 0, 0) if fundo == CORES_BGR["amarelo"] else (255, 255, 255)
    folga = round(3 * fator)
    cv2.rectangle(img, (x, y - alt - base - 2 * folga), (x + larg + 2 * folga, y), fundo, -1)
    cv2.putText(img, texto, (x + folga, y - base - folga), cv2.FONT_HERSHEY_SIMPLEX, escala, cor_texto, espessura,
                cv2.LINE_AA)


def desenhar(frame: np.ndarray, resultado: ResultadoFrame, linhas_hud: list[str], debug: bool = False,
             alerta: str | None = None) -> np.ndarray:
    """Desenha caixas das pessoas (cor RF04), rótulos, máscaras detectadas e o painel de informações (RF05)."""
    img = frame.copy()
    f = fator_desenho(img)
    fina, grossa = max(1, round(f)), max(3, round(3 * f))
    for det in resultado.deteccoes:
        x1, y1, x2, y2 = map(int, det.caixa)
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), fina)
        cv2.putText(img, f"{det.classe} {det.conf:.2f}", (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.4 * f, (255, 255, 255), fina, cv2.LINE_AA)
    for aval in resultado.avaliacoes:
        cor = CORES_BGR[aval.cor]
        x1, y1, x2, y2 = map(int, aval.pessoa.caixa)
        cv2.rectangle(img, (x1, y1), (x2, y2), cor, grossa)
        _texto_com_fundo(img, aval.rotulo, x1, y1, cor, fator=f)
        if debug:   # traços crescem com a imagem (num 4K reduzido para a tela, 1 px some)
            if aval.regioes.cabeca is not None:
                cx1, cy1, cx2, cy2 = map(int, aval.regioes.cabeca)
                cv2.rectangle(img, (cx1, cy1), (cx2, cy2), (255, 255, 0), fina)
            if aval.regioes.linha_olhos_y is not None and aval.regioes.cabeca is not None:
                y = int(aval.regioes.linha_olhos_y)
                cv2.line(img, (int(aval.regioes.cabeca[0]), y), (int(aval.regioes.cabeca[2]), y), (255, 255, 0), fina)
            for kp in aval.pessoa.keypoints:
                if kp.conf >= 0.5:
                    cv2.circle(img, (int(kp.x), int(kp.y)), max(3, round(3 * f)), (0, 255, 255), -1)
    if debug and resultado.rostos:
        for rosto in resultado.rostos:   # rostos descobertos encontrados pelo YuNet (magenta)
            x1, y1, x2, y2 = map(int, rosto.caixa)
            cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 255), max(2, round(2 * f)))
            cv2.putText(img, f"rosto {rosto.conf:.2f}", (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4 * f,
                        (255, 0, 255), fina, cv2.LINE_AA)

    y = round(22 * f)
    for linha in linhas_hud:
        _texto_com_fundo(img, linha, 8, y, (40, 40, 40), fator=f)
        y += round(24 * f)
    if resultado.saturado:
        _texto_com_fundo(img, f"ARCO DETECTADO - frame ignorado ({resultado.fracao_saturada:.0%} saturado)",
                         8, y, CORES_BGR["vermelho"], escala=0.65, fator=f)
    if any(a.regioes.fallback for a in resultado.avaliacoes):
        _texto_com_fundo(img, "MODO SEM POSE (fallback)", 8, y + round(28 * f), CORES_BGR["amarelo"], fator=f)
    if alerta:
        _texto_com_fundo(img, alerta, 8, img.shape[0] - 10, CORES_BGR["vermelho"], escala=0.7, fator=f)
    return img
