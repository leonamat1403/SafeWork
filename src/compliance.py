"""Associação EPI -> pessoa e estado de cada EPI (núcleo do projeto).

Fase 1: regra da MÁSCARA DE SOLDA (RF07), a cor da caixa (RF04) e o rótulo. As regras dos outros EPIs
(luvas, proteção do corpo, calçado, capacete) estão documentadas em docs/plano_fase1.md como trabalho futuro.

Regra da máscara, em ordem:
  1. máscara detectada com pelo menos `cobertura_min` da caixa dentro da região da cabeça -> CONFORME
     (e "máscara levantada" se o centro dela estiver acima da linha dos olhos com o rosto visível; com
     `levantada_nao_conforme: true` no config.yaml, a máscara levantada vira NÃO CONFORME – decisão de 13/10/2026);
     EXCETO se a "máscara" estiver na altura do rosto e o rosto estiver nitidamente visível (olhos/nariz com
     confiança alta): uma máscara abaixada cobre os olhos, então isso é contraditório -> INDETERMINADO.
     (Teste da webcam, 13/10/2026: rosto de perfil com luz lateral confundido com máscara.)
  2. sem máscara e cabeça não visível                     -> INDETERMINADO
  3. sem máscara e sem pose (fallback)                    -> INDETERMINADO (não dá para saber se o rosto aparece)
  4. sem máscara e rosto visível (de frente, descoberto)  -> NÃO CONFORME
     ("rosto visível" vem do detector de rostos quando ele existe; os pontos do rosto da pose enxergam olhos
      até atrás da máscara de solda – D27)
  5. sem máscara nos demais casos (costas, rosto coberto) -> INDETERMINADO
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.body_regions import RegioesCorpo, calcular_regioes, pontos_do_rosto_visiveis
from src.config import Config, ConfigEPI
from src.tipos import DeteccaoEPI, Estado, Pessoa, Rosto, centro, fracao_dentro

# Cores padronizadas do projeto, no formato BGR do OpenCV
CORES_BGR = {
    "verde": (84, 135, 25),       # #198754 – todos os EPIs exigidos conformes
    "amarelo": (7, 193, 255),     # #FFC107 – nenhum não conforme, mas algum indeterminado
    "vermelho": (69, 53, 220),    # #DC3545 – algum EPI exigido não conforme
}

# Nomes para a tela (sem acento: as fontes do OpenCV não desenham acentos)
NOMES_TELA = {"mascara": "MASCARA", "luvas": "LUVAS", "protecao_corpo": "PROTECAO CORPO",
              "calcado": "CALCADO", "capacete": "CAPACETE"}


@dataclass(frozen=True)
class AvaliacaoEPI:
    """Estado de um EPI para uma pessoa, com a confiança da detecção associada e o motivo."""

    estado: Estado
    conf: float | None = None
    motivo: str = ""
    caixa: tuple[float, float, float, float] | None = None   # caixa do EPI associado, se houver


@dataclass
class AvaliacaoPessoa:
    """Resultado completo de uma pessoa em um frame."""

    pessoa: Pessoa
    regioes: RegioesCorpo
    epis: dict[str, AvaliacaoEPI] = field(default_factory=dict)
    mascara_levantada: bool = False

    @property
    def cor(self) -> str:
        return cor_da_pessoa(self.epis)

    @property
    def rotulo(self) -> str:
        return rotulo_da_pessoa(self)


def cor_da_pessoa(epis: dict[str, AvaliacaoEPI]) -> str:
    """RF04: vermelho se algum EPI exigido for NÃO CONFORME; amarelo se algum for INDETERMINADO; senão verde."""
    estados = {a.estado for a in epis.values()}
    if Estado.NAO_CONFORME in estados:
        return "vermelho"
    if Estado.INDETERMINADO in estados:
        return "amarelo"
    return "verde"


def rotulo_da_pessoa(avaliacao: AvaliacaoPessoa) -> str:
    """Texto acima da caixa da pessoa, ex.: "#3 SEM MASCARA" ou "#3 OK | MASCARA LEVANTADA"."""
    ident = f"#{avaliacao.pessoa.track_id}" if avaliacao.pessoa.track_id is not None else "#?"
    faltando = [("MASCARA LEVANTADA" if n == "mascara" and avaliacao.mascara_levantada else f"SEM {NOMES_TELA[n]}")
                for n, a in avaliacao.epis.items() if a.estado == Estado.NAO_CONFORME]
    incertos = [f"? {NOMES_TELA[n]}" for n, a in avaliacao.epis.items() if a.estado == Estado.INDETERMINADO]
    partes = faltando or incertos or ["OK"]
    if avaliacao.mascara_levantada and "MASCARA LEVANTADA" not in partes:
        partes.append("MASCARA LEVANTADA")
    return f"{ident} " + " | ".join(partes)


def _associar(avaliacoes: list[AvaliacaoPessoa], deteccoes: list[DeteccaoEPI],
              cobertura_min: float) -> dict[int, DeteccaoEPI]:
    """Associa cada detecção a no máximo uma pessoa (e cada pessoa a no máximo uma detecção).

    Associação gulosa: primeiro o par (pessoa, detecção) com maior cobertura, depois o próximo, e assim por diante.
    Retorna {índice da pessoa: detecção}.
    """
    pares = []
    for i, aval in enumerate(avaliacoes):
        if aval.regioes.cabeca is None:
            continue
        for j, det in enumerate(deteccoes):
            cobertura = fracao_dentro(det.caixa, aval.regioes.cabeca)
            if cobertura >= cobertura_min:
                pares.append((cobertura, det.conf, i, j))
    pares.sort(reverse=True)

    associacao: dict[int, DeteccaoEPI] = {}
    usadas: set[int] = set()
    for _, _, i, j in pares:
        if i not in associacao and j not in usadas:
            associacao[i] = deteccoes[j]
            usadas.add(j)
    return associacao


def _avaliar_mascaras(avaliacoes: list[AvaliacaoPessoa], deteccoes: list[DeteccaoEPI], cfg: ConfigEPI) -> None:
    """Aplica a regra da máscara (RF07) a todas as pessoas do frame."""
    associacao = _associar(avaliacoes, [d for d in deteccoes if d.epi == "mascara"], cfg.cobertura_min)
    # Contradição "máscara sobre o rosto + rosto nítido" (configurável em epis.mascara do config.yaml)
    checar_contradicao = bool(cfg.extras.get("contradicao_rosto_visivel", True))
    conf_rosto = float(cfg.extras.get("conf_rosto_contradicao", 0.7))
    levantada_falta = bool(cfg.extras.get("levantada_nao_conforme", False))
    for i, aval in enumerate(avaliacoes):
        reg = aval.regioes
        det = associacao.get(i)
        if det is not None:
            _, cy = centro(det.caixa)
            acima_dos_olhos = reg.linha_olhos_y is not None and cy < reg.linha_olhos_y
            aval.mascara_levantada = bool(reg.rosto_visivel and acima_dos_olhos)
            # Rosto "nítido": pelo detector de rostos, se houver; senão, >= 2 pontos do rosto da pose com conf alta
            rosto_nitido = (reg.rosto_visivel if reg.rosto_por_detector
                            else pontos_do_rosto_visiveis(aval.pessoa, conf_rosto) >= 2)
            if checar_contradicao and not acima_dos_olhos and rosto_nitido:
                aval.mascara_levantada = False
                aval.epis["mascara"] = AvaliacaoEPI(Estado.INDETERMINADO, det.conf,
                                                    "máscara na altura do rosto, mas rosto visível", det.caixa)
                continue
            if aval.mascara_levantada and levantada_falta:
                aval.epis["mascara"] = AvaliacaoEPI(Estado.NAO_CONFORME, det.conf, "máscara levantada", det.caixa)
                continue
            aval.epis["mascara"] = AvaliacaoEPI(Estado.CONFORME, det.conf, "máscara na região da cabeça", det.caixa)
        elif reg.cabeca is None:
            aval.epis["mascara"] = AvaliacaoEPI(Estado.INDETERMINADO, motivo="cabeça não visível")
        elif reg.fallback and not reg.rosto_por_detector:
            aval.epis["mascara"] = AvaliacaoEPI(Estado.INDETERMINADO, motivo="sem pose: rosto não verificável")
        elif reg.rosto_visivel:
            aval.epis["mascara"] = AvaliacaoEPI(Estado.NAO_CONFORME, motivo="rosto visível sem máscara")
        else:
            motivo = "de costas" if reg.orientacao == "costas" else "rosto não visível"
            aval.epis["mascara"] = AvaliacaoEPI(Estado.INDETERMINADO, motivo=motivo)


# Regras implementadas por EPI. Os demais EPIs entram aqui quando forem implementados (trabalho futuro).
REGRAS = {"mascara": _avaliar_mascaras}


def avaliar_frame(pessoas: list[Pessoa], deteccoes: list[DeteccaoEPI], config: Config,
                  rostos: list[Rosto] | None = None) -> list[AvaliacaoPessoa]:
    """Avalia todos os EPIs ativos de todas as pessoas de um frame.

    `rostos`: saída do detector de rostos (None se ele não estiver disponível; aí vale a pose).
    """
    avaliacoes = [AvaliacaoPessoa(p, calcular_regioes(p, config.deteccao.conf_keypoint, rostos)) for p in pessoas]
    for nome in config.epis_ativos:
        regra = REGRAS.get(nome)
        if regra is not None:
            regra(avaliacoes, deteccoes, config.epis[nome])
    return avaliacoes
