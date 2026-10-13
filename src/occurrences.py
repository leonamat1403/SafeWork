"""Ocorrências: persistência, cooldown e agrupamento (RF18–RF20). Saída no terminal e em CSV (Fase 1).

Regras (decisões de 13/10/2026, ver docs/plano_fase1.md):
- Persistência por TEMPO: uma ocorrência só é registrada se, nos últimos `persistencia_s` segundos (padrão 4 s),
  pelo menos `fracao_minima` (padrão 75%) dos frames válidos da pessoa forem NÃO CONFORME. Pausas curtas (o soldador
  levantando a máscara para conferir o cordão) e frames errados isolados não geram ocorrência.
- Cooldown (RF19): depois de uma ocorrência, a mesma pessoa (track_id) não gera outra do mesmo EPI antes de
  `cooldown_s` segundos (padrão 60 s), mesmo que tenha colocado a máscara no meio.
- Agrupamento (RF20): quando um EPI dispara, a ocorrência lista TODOS os EPIs não conformes da pessoa naquele momento,
  e todos entram em cooldown juntos.
- INDETERMINADO nunca conta como falta, e frames saturados pelo arco (RF14) não contam para nada.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.compliance import AvaliacaoPessoa
from src.config import Config
from src.tipos import Estado

INTERVALO_MAXIMO_S = 1.0   # ao somar tempos por estado, lacunas maiores que isso (pessoa sumiu) não são contadas
TOLERANCIA_JANELA_S = 0.2  # a janela de persistência pode ser até 0,2 s mais curta (frames chegam em intervalos)


@dataclass
class Ocorrencia:
    """Uma não conformidade confirmada de uma pessoa."""

    data_hora: datetime
    tempo_s: float                         # tempo no vídeo (arquivo) ou desde o início (ao vivo)
    frame: int
    track_id: int
    epis_faltantes: list[str]
    situacao: dict[str, str]               # EPI -> motivo (ex.: "máscara levantada")
    fracao_nao_conforme: dict[str, float]  # EPI -> fração de frames NÃO CONFORME na janela de persistência
    epis_indeterminados: list[str]
    confianca_media: dict[str, float]      # EPI -> confiança média das detecções associadas na janela
    mascara_levantada: bool

    def descricao(self) -> str:
        partes = [f"{epi}: {self.situacao.get(epi, 'não conforme')} ({self.fracao_nao_conforme.get(epi, 0):.0%})"
                  for epi in self.epis_faltantes]
        return f"pessoa #{self.track_id} | " + "; ".join(partes)


@dataclass
class _Amostra:
    t: float
    estado: Estado
    conf: float | None


@dataclass
class _HistoricoPessoa:
    janelas: dict[str, deque] = field(default_factory=lambda: defaultdict(deque))   # EPI -> amostras recentes
    ultima_ocorrencia: dict[str, float] = field(default_factory=dict)                # EPI -> tempo da última
    tempo_por_estado: dict[tuple[str, Estado], float] = field(default_factory=lambda: defaultdict(float))
    ocorrencias: int = 0
    ultimo_t: float | None = None
    ultimos_estados: dict[str, Estado] = field(default_factory=dict)                 # estado no frame anterior


class GerenciadorOcorrencias:
    """Recebe as avaliações de cada frame e devolve as ocorrências confirmadas."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._pessoas: dict[int, _HistoricoPessoa] = defaultdict(_HistoricoPessoa)

    def atualizar(self, avaliacoes: list[AvaliacaoPessoa], t: float, frame: int,
                  saturado: bool = False) -> list[Ocorrencia]:
        """Processa um frame (tempo `t` em segundos) e retorna as ocorrências novas."""
        if saturado:   # RF14: frame estourado pelo arco não conta para persistência nem gera ocorrência
            return []
        novas = []
        for aval in avaliacoes:
            if aval.pessoa.track_id is None:   # sem ID não há como acompanhar a pessoa ao longo do tempo
                continue
            hist = self._pessoas[aval.pessoa.track_id]
            self._somar_tempo(hist, aval, t)
            disparados = []
            for epi, avaliacao in aval.epis.items():
                cfg = self.config.epis[epi]
                janela = hist.janelas[epi]
                janela.append(_Amostra(t, avaliacao.estado, avaliacao.conf))
                while janela and t - janela[0].t > cfg.persistencia_s:
                    janela.popleft()
                if self._persistiu(janela, t, cfg.persistencia_s, cfg.fracao_minima) and \
                        t - hist.ultima_ocorrencia.get(epi, float("-inf")) >= self.config.ocorrencias.cooldown_s:
                    disparados.append(epi)
            if disparados:
                novas.append(self._criar(aval, hist, t, frame))
        return novas

    @staticmethod
    def _persistiu(janela: deque, t: float, persistencia_s: float, fracao_minima: float) -> bool:
        """A janela cobre (quase) todo o período e a fração de NÃO CONFORME atinge o mínimo."""
        if not janela or t - janela[0].t < persistencia_s - TOLERANCIA_JANELA_S:
            return False
        nao_conformes = sum(a.estado == Estado.NAO_CONFORME for a in janela)
        return nao_conformes / len(janela) >= fracao_minima

    def _criar(self, aval: AvaliacaoPessoa, hist: _HistoricoPessoa, t: float, frame: int) -> Ocorrencia:
        """RF20: uma ocorrência por pessoa com todos os EPIs não conformes no momento; todos entram em cooldown."""
        faltantes = [epi for epi, a in aval.epis.items() if a.estado == Estado.NAO_CONFORME]
        fracoes, confiancas = {}, {}
        for epi in aval.epis:
            janela = hist.janelas[epi]
            if janela:
                fracoes[epi] = round(sum(a.estado == Estado.NAO_CONFORME for a in janela) / len(janela), 3)
            confs = [a.conf for a in janela if a.conf is not None]
            if confs:
                confiancas[epi] = round(sum(confs) / len(confs), 3)
        for epi in faltantes:
            hist.ultima_ocorrencia[epi] = t
        hist.ocorrencias += 1
        return Ocorrencia(
            data_hora=datetime.now(),
            tempo_s=t,
            frame=frame,
            track_id=aval.pessoa.track_id,
            epis_faltantes=faltantes,
            situacao={epi: aval.epis[epi].motivo for epi in faltantes},
            fracao_nao_conforme={epi: fracoes.get(epi, 0.0) for epi in faltantes},
            epis_indeterminados=[epi for epi, a in aval.epis.items() if a.estado == Estado.INDETERMINADO],
            confianca_media=confiancas,
            mascara_levantada=aval.mascara_levantada,
        )

    @staticmethod
    def _somar_tempo(hist: _HistoricoPessoa, aval: AvaliacaoPessoa, t: float) -> None:
        """Acumula o tempo em cada estado (para o resumo por pessoa).

        O intervalo entre dois frames é somado ao estado do frame ANTERIOR, que é o estado que valeu nesse intervalo.
        """
        if hist.ultimo_t is not None and 0 < t - hist.ultimo_t <= INTERVALO_MAXIMO_S:
            for epi, estado in hist.ultimos_estados.items():
                hist.tempo_por_estado[(epi, estado)] += t - hist.ultimo_t
        hist.ultimo_t = t
        hist.ultimos_estados = {epi: a.estado for epi, a in aval.epis.items()}

    def resumo_por_pessoa(self) -> list[str]:
        """Linhas do resumo final: ocorrências e tempo em cada estado, por pessoa."""
        linhas = []
        for track_id, hist in sorted(self._pessoas.items()):
            epis = sorted({epi for epi, _ in hist.tempo_por_estado})
            tempos = "; ".join(
                f"{epi}: " + ", ".join(f"{estado.value} {hist.tempo_por_estado[(epi, estado)]:.1f}s" for estado in Estado)
                for epi in epis)
            linhas.append(f"pessoa #{track_id}: {hist.ocorrencias} ocorrência(s) | {tempos}")
        return linhas


class RegistroCSV:
    """Grava as ocorrências em CSV, uma linha por ocorrência.

    Formato pensado para abrir direto no Excel em português: separador ";" , números com vírgula e UTF-8 com BOM.
    A coluna `revisao_manual` fica vazia para você preencher (VP = verdadeiro positivo, FP = falso positivo).
    """

    COLUNAS = ["data_hora", "tempo_video", "fonte", "posto", "frame", "pessoa", "epis_faltantes", "situacao",
               "fracao_nao_conforme", "epis_indeterminados", "confianca_media", "mascara_levantada", "revisao_manual"]

    def __init__(self, caminho: Path, fonte: str, posto: str) -> None:
        self.caminho = Path(caminho)
        self.fonte = fonte
        self.posto = posto
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        novo = not self.caminho.exists()
        self._arquivo = self.caminho.open("a", newline="", encoding="utf-8-sig")
        self._escritor = csv.writer(self._arquivo, delimiter=";")
        if novo:
            self._escritor.writerow(self.COLUNAS)
            self._arquivo.flush()

    @staticmethod
    def _numero(valor: float) -> str:
        return f"{valor:.3f}".replace(".", ",")

    def gravar(self, oc: Ocorrencia) -> None:
        self._escritor.writerow([
            oc.data_hora.strftime("%d/%m/%Y %H:%M:%S"),
            formatar_tempo(oc.tempo_s),
            self.fonte,
            self.posto,
            oc.frame,
            oc.track_id,
            ", ".join(oc.epis_faltantes),
            "; ".join(f"{epi}: {motivo}" for epi, motivo in oc.situacao.items()),
            ", ".join(f"{epi}={self._numero(f)}" for epi, f in oc.fracao_nao_conforme.items()),
            ", ".join(oc.epis_indeterminados),
            json.dumps(oc.confianca_media, ensure_ascii=False),
            int(oc.mascara_levantada),
            "",
        ])
        self._arquivo.flush()   # grava na hora: se o programa cair, as ocorrências já estão no arquivo

    def fechar(self) -> None:
        self._arquivo.close()


def formatar_tempo(segundos: float) -> str:
    """hh:mm:ss.s"""
    m, s = divmod(segundos, 60)
    h, m = divmod(int(m), 60)
    return f"{h:02d}:{m:02d}:{s:04.1f}"
