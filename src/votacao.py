"""Votação temporal (RD01, Fase 2): deixa estável o que aparece na tela ao vivo.

O estado da máscara mostrado para cada pessoa (track_id) é o que mais apareceu nos últimos K quadros válidos dela
(quadros estourados pelo arco não entram). Um quadro errado no meio de vários certos não faz a caixa piscar de cor.
Empate: vale o estado mais recente entre os empatados. O motivo, a confiança e o aviso de "máscara levantada" vêm do
último quadro que teve o estado vencedor, para o rótulo não contradizer o estado.

Só a EXIBIÇÃO usa a votação (caixas, rótulos e o painel "Pessoas agora"). As ocorrências continuam com a regra de
4 s / 75% (src/occurrences.py), que já é uma votação no tempo e foi a validada na Fase 1.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field

from src.compliance import AvaliacaoEPI, AvaliacaoPessoa
from src.tipos import Estado


@dataclass
class _Historico:
    """Memória de uma pessoa (track_id): estados recentes de cada EPI e a última avaliação de cada estado."""

    estados: dict[str, deque] = field(default_factory=dict)        # EPI -> últimos estados
    # (EPI, estado) -> última avaliação com esse estado e se a máscara estava levantada naquele quadro
    ultima: dict[tuple[str, Estado], tuple[AvaliacaoEPI, bool]] = field(default_factory=dict)
    ultimo_quadro: int = 0   # número do último quadro em que a pessoa apareceu (para esquecer quem sumiu)


def mais_votado(valores: deque) -> Estado:
    """O valor que mais aparece; no empate, o que apareceu por último."""
    contagem = Counter(valores)
    maximo = max(contagem.values())
    return next(valor for valor in reversed(valores) if contagem[valor] == maximo)


class VotacaoTemporal:
    """Guarda os últimos `quadros` estados de cada pessoa e devolve as avaliações "votadas" para a tela."""

    def __init__(self, quadros: int = 5) -> None:
        """`quadros` é o tamanho da janela de votação (K); com 1 a votação fica desligada."""
        self.quadros = max(1, int(quadros))
        self._pessoas: dict[int, _Historico] = {}
        self._quadro = 0

    def atualizar(self, avaliacoes: list[AvaliacaoPessoa]) -> list[AvaliacaoPessoa]:
        """Recebe as avaliações de um quadro VÁLIDO e devolve cópias com o estado da maioria (as originais não mudam)."""
        if self.quadros == 1:
            return avaliacoes
        self._quadro += 1
        votadas = []
        for aval in avaliacoes:
            if aval.pessoa.track_id is None:   # sem ID não há histórico: mostra o quadro atual
                votadas.append(aval)
                continue
            hist = self._pessoas.setdefault(aval.pessoa.track_id, _Historico())
            hist.ultimo_quadro = self._quadro
            epis, levantada = {}, False
            for epi, avaliacao in aval.epis.items():
                estados = hist.estados.setdefault(epi, deque(maxlen=self.quadros))
                estados.append(avaliacao.estado)
                hist.ultima[(epi, avaliacao.estado)] = (avaliacao, aval.mascara_levantada)
                epis[epi], levantada_do_quadro = hist.ultima[(epi, mais_votado(estados))]
                if epi == "mascara":
                    levantada = levantada_do_quadro
            votadas.append(AvaliacaoPessoa(aval.pessoa, aval.regioes, epis, levantada, aval.arco_ativo,
                                           aval.arco_maos))
        # Esquece quem sumiu há mais de K quadros (o track_id pode voltar como outra pessoa)
        for track_id in [t for t, h in self._pessoas.items() if self._quadro - h.ultimo_quadro > self.quadros]:
            del self._pessoas[track_id]
        return votadas
