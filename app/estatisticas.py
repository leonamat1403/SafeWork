"""Números de um período (Painel T05 e relatório mensal em PDF, RD04 e RD10): as duas saídas usam a mesma conta.

O sistema verifica só a máscara de solda (decisão de 15/10/2026). Por isso, no lugar de "ocorrências por tipo de EPI"
o painel mostra os tipos de falta da máscara (sem máscara × máscara levantada), e a conformidade é a da máscara.

- Ocorrências: tabela `ocorrencias` (cada uma é uma falta confirmada pela regra de 4 s / 75%).
- Conformidade: tabela `metricas_sessao` (pessoas avaliadas quadro a quadro, sem imagens). Conformidade =
  conformes ÷ (conformes + não conformes); os indeterminados ficam de fora, porque não dá para saber (de costas,
  cabeça fora do quadro) e aparecem em separado.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Camera, MetricaSessao, Ocorrencia
from app.tempo import hoje_local, inicio_do_dia_utc, para_local

SEM_TURNO = "sem turno"


def _fracao(parte: int, todo: int) -> float | None:
    return round(parte / todo, 4) if todo else None


def resumo_do_periodo(fabrica: sessionmaker[Session], turnos: dict[str, str], inicio: date, fim: date,
                      camera_id: int | None = None) -> dict:
    """Cartões, ocorrências por dia/turno/posto e estados das pessoas avaliadas, de `inicio` a `fim` (inclusive)."""
    hoje = hoje_local()
    de, ate = inicio_do_dia_utc(inicio), inicio_do_dia_utc(fim + timedelta(days=1))
    do_posto = [Ocorrencia.camera_id == camera_id] if camera_id is not None else []

    def contar(sessao, desde: date, antes_de: date) -> int:
        return sessao.scalar(select(func.count()).select_from(Ocorrencia).where(
            Ocorrencia.data_hora >= inicio_do_dia_utc(desde), Ocorrencia.data_hora < inicio_do_dia_utc(antes_de),
            *do_posto))

    with fabrica() as sessao:
        linhas = sessao.execute(
            select(Ocorrencia.data_hora, Ocorrencia.turno, Ocorrencia.camera_id, Ocorrencia.mascara_levantada,
                   Ocorrencia.validacao, Ocorrencia.arco_ativo)
            .where(Ocorrencia.data_hora >= de, Ocorrencia.data_hora < ate, *do_posto)).all()
        hoje_total = contar(sessao, hoje, hoje + timedelta(days=1))
        mes_total = contar(sessao, hoje.replace(day=1), hoje + timedelta(days=1))
        postos = dict(sessao.execute(select(Camera.id, Camera.nome_posto)).all())
        # Sessões de câmera que tocam o período (os totais de cada sessão não são separados por dia)
        conformes, nao_conformes, indeterminados = sessao.execute(
            select(func.coalesce(func.sum(MetricaSessao.total_conformes), 0),
                   func.coalesce(func.sum(MetricaSessao.total_nao_conformes), 0),
                   func.coalesce(func.sum(MetricaSessao.total_indeterminados), 0))
            .where(MetricaSessao.inicio < ate, or_(MetricaSessao.fim.is_(None), MetricaSessao.fim >= de),
                   *([MetricaSessao.camera_id == camera_id] if camera_id is not None else []))).one()

    por_dia: Counter = Counter()
    por_turno: dict[str, Counter] = defaultdict(Counter)
    por_posto: Counter = Counter()
    validacoes: Counter = Counter()
    com_arco = 0
    for data_hora, turno, posto, levantada, validacao, arco in linhas:
        por_dia[para_local(data_hora).date()] += 1
        por_turno[turno or SEM_TURNO]["levantada" if levantada else "sem_mascara"] += 1
        por_posto[posto] += 1
        validacoes[validacao] += 1
        com_arco += bool(arco)

    lista_turnos = sorted(turnos) + ([SEM_TURNO] if SEM_TURNO in por_turno else [])
    validadas = validacoes["CONFIRMADA"] + validacoes["FALSO_POSITIVO"]
    avaliados = conformes + nao_conformes
    return {
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "camera_id": camera_id},
        "cartoes": {
            "hoje": hoje_total, "mes": mes_total, "periodo": len(linhas),
            "conformidade": _fracao(conformes, avaliados),
            "indeterminado": _fracao(indeterminados, avaliados + indeterminados),
            "falsos_positivos": _fracao(validacoes["FALSO_POSITIVO"], validadas), "validadas": validadas,
            "pendentes": validacoes["PENDENTE"], "confirmadas": validacoes["CONFIRMADA"], "com_arco": com_arco,
        },
        "por_dia": [{"dia": (inicio + timedelta(days=i)).isoformat(),
                     "total": por_dia[inicio + timedelta(days=i)]} for i in range((fim - inicio).days + 1)],
        "por_turno": [{"turno": t, "sem_mascara": por_turno[t]["sem_mascara"], "levantada": por_turno[t]["levantada"]}
                      for t in lista_turnos],
        "por_posto": [{"camera_id": c, "posto": postos.get(c, f"Posto {c}"), "total": n}
                      for c, n in por_posto.most_common()],
        "estados": {"conforme": conformes, "nao_conforme": nao_conformes, "indeterminado": indeterminados},
    }
