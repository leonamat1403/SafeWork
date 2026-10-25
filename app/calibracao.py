"""Calibração (RD02, tela T07): os números que as regras usam, para ajustar os limites no próprio posto.

Para cada pessoa: altura, região da cabeça, cobertura da máscara, confiança da máscara e do rosto, orientação e o
brilho perto das mãos (arco, RD03). Para o quadro: a fração de pixels estourados (filtro do arco, RF14).
O desenho é feito sobre a cópia BORRADA (como no ao vivo); os números vêm do quadro original, que fica só na memória.
"""
from __future__ import annotations

import cv2
import numpy as np

from src.arc_filter import fracao_saturada_na_regiao, regioes_das_maos
from src.body_regions import rosto_na_cabeca
from src.config import Config
from src.pipeline import ResultadoFrame, desenhar, fator_desenho
from src.tipos import fracao_dentro

LARANJA = (0, 140, 255)       # regiões das mãos (BGR)
CIANO = (255, 255, 0)         # região da cabeça (BGR, igual ao modo --debug da Fase 1)


def _arredondar(valor: float | None, casas: int = 2) -> float | None:
    """Arredonda para `casas` decimais, preservando None (valor ausente)."""
    return None if valor is None else round(float(valor), casas)


def dados_calibracao(frame: np.ndarray, resultado: ResultadoFrame, config: Config) -> dict:
    """Valores de agora (quadro e pessoas) com os limites do config ao lado, para a tela comparar."""
    arco, mascara = config.arco, config.epis["mascara"]
    pessoas = []
    for aval in resultado.avaliacoes:
        x1, y1, x2, y2 = aval.pessoa.caixa
        reg = aval.regioes
        epi = aval.epis.get("mascara")
        # Cobertura = fração da caixa da máscara que está dentro da região da cabeça.
        cobertura = (fracao_dentro(epi.caixa, reg.cabeca) if epi is not None and epi.caixa is not None
                     and reg.cabeca is not None else None)
        # Só procura o rosto detectado quando a região do rosto veio do detector de rosto (e não da pose).
        rosto = rosto_na_cabeca(reg.cabeca, resultado.rostos or []) if reg.rosto_por_detector else None
        # Brilho (fração de pixels estourados) em volta de cada mão, medido no quadro ORIGINAL; indica arco aceso.
        maos = [fracao_saturada_na_regiao(frame, caixa, arco.limiar_brilho)
                for caixa in regioes_das_maos(aval.pessoa, config.deteccao.conf_keypoint, arco.raio_maos)]
        pessoas.append({
            "track_id": aval.pessoa.track_id,
            "altura_px": round(y2 - y1),
            "cabeca_visivel": reg.cabeca is not None,
            "sem_pose": reg.fallback,
            "orientacao": reg.orientacao,
            "cobertura": _arredondar(cobertura),
            "conf_mascara": _arredondar(epi.conf if epi is not None else None),
            "rosto_visivel": reg.rosto_visivel,
            "conf_rosto": _arredondar(rosto.conf if rosto is not None else None),
            "mascara_levantada": aval.mascara_levantada,
            "maos_visiveis": len(maos),
            "brilho_maos": _arredondar(max(maos) if maos else None, 3),
            "arco_ativo": aval.arco_ativo,
            "estado": epi.estado.value if epi is not None else None,
            "motivo": epi.motivo if epi is not None else "",
        })
    return {
        "quadro_valido": not resultado.saturado,
        "fracao_saturada": round(resultado.fracao_saturada, 3),
        "pessoas": pessoas,
        "limites": {
            "fracao_max_saturada": arco.fracao_max_saturada, "limiar_brilho": arco.limiar_brilho,
            "fracao_min_maos": arco.fracao_min_maos, "detectar_solda_ativa": arco.detectar_solda_ativa,
            "exigir_mascara_somente_com_arco": arco.exigir_mascara_somente_com_arco,
            "cobertura_min": mascara.cobertura_min, "conf_mascara": mascara.conf,
            "conf_rosto": config.deteccao.conf_rosto, "conf_keypoint": config.deteccao.conf_keypoint,
        },
    }


def _texto(img: np.ndarray, texto: str, x: float, y: float, cor: tuple[int, int, int], f: float) -> None:
    """Escreve `texto` sobre um fundo cinza escuro (para ler em qualquer cena); `f` é o fator de escala do desenho."""
    escala, espessura = 0.5 * f, max(1, round(f))
    (largura, altura), base = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, espessura)
    # Mantém o rótulo dentro da imagem (não sai pela esquerda nem pelo topo).
    x, y = int(max(0, x)), int(max(altura + base, y))
    cv2.rectangle(img, (x, y - altura - base - 2), (x + largura + 4, y + 2), (30, 30, 30), -1)
    cv2.putText(img, texto, (x + 2, y - base), cv2.FONT_HERSHEY_SIMPLEX, escala, cor, espessura, cv2.LINE_AA)


def desenhar_calibracao(img: np.ndarray, frame: np.ndarray, resultado: ResultadoFrame, config: Config,
                        nome: str) -> np.ndarray:
    """Desenho técnico sobre `img` (cópia já borrada): pontos do corpo, cabeça, linha dos olhos, rostos (magenta),
    máscaras com a cobertura, regiões das mãos com o brilho (arco) e a fração estourada do quadro."""
    arco = config.arco
    hud = [f"CALIBRACAO | {nome}",
           f"estourado {resultado.fracao_saturada:.1%} (limite {arco.fracao_max_saturada:.0%})".replace(".", ",")]
    img = desenhar(img, resultado, hud, debug=True)
    f = fator_desenho(img)
    linha = max(1, round(2 * f))
    for aval in resultado.avaliacoes:
        epi = aval.epis.get("mascara")
        if epi is not None and epi.caixa is not None and aval.regioes.cabeca is not None:
            cx1, cy1, _, cy2 = aval.regioes.cabeca
            cobertura = f"{fracao_dentro(epi.caixa, aval.regioes.cabeca):.2f}".replace(".", ",")
            _texto(img, f"cobertura {cobertura}", cx1, cy2 + 18 * f, CIANO, f)
        for caixa in regioes_das_maos(aval.pessoa, config.deteccao.conf_keypoint, arco.raio_maos):
            x1, y1, x2, y2 = map(int, caixa)
            fracao = fracao_saturada_na_regiao(frame, caixa, arco.limiar_brilho)
            # Vermelho quando o brilho já passa do mínimo que indica arco aceso; laranja caso contrário.
            cor = (0, 0, 255) if fracao >= arco.fracao_min_maos else LARANJA
            cv2.rectangle(img, (x1, y1), (x2, y2), cor, linha)
            _texto(img, f"maos {fracao:.1%}".replace(".", ","), x1, y2 + 18 * f, cor, f)
    return img
