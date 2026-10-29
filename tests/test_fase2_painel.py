"""[FASE 2] Painel (Etapa 2.5, bloco C – RD04, tela T05): números e séries com os filtros de período e posto.

Os dados ficam em setembro de 2026, longe de "hoje", para a câmera simulada (que também grava métricas) não
interferir. Câmera e detector SIMULADOS, como no test_fase2_web.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import MetricaSessao, Ocorrencia
from app.tempo import hoje_local
from tests.test_fase2_web import (admin_pronto, bcrypt_rapido, cliente, criar_supervisor, ctx, entrar,  # noqa: F401
                                  registrar_ocorrencias)

UTC = timezone.utc
SETEMBRO = "/api/dashboard?inicio=2026-09-01&fim=2026-09-30"


def preparar_setembro(c, token):
    """3 ocorrências em 10/09 (09:00, 10:00 e 11:00 em Brasília, turno 1), uma delas de máscara levantada e com arco;
    uma confirmada e uma falso positivo; e uma sessão de câmera com 80 conformes, 20 não conformes e 25 indeterminados."""
    uuids = registrar_ocorrencias(c, 3, datetime(2026, 9, 10, 12, 0, tzinfo=UTC))
    with ctx(c).fabrica() as s:
        primeira = s.query(Ocorrencia).filter_by(uuid=uuids[0]).one()
        primeira.mascara_levantada, primeira.arco_ativo = True, True
        s.add(MetricaSessao(camera_id=1, inicio=datetime(2026, 9, 10, 11, tzinfo=UTC),
                            fim=datetime(2026, 9, 10, 20, tzinfo=UTC), total_conformes=80, total_nao_conformes=20,
                            total_indeterminados=25))
        s.commit()
    cabecalho = {"X-CSRF-Token": token}
    c.post(f"/api/ocorrencias/{uuids[1]}/validacao", json={"validacao": "CONFIRMADA"}, headers=cabecalho)
    c.post(f"/api/ocorrencias/{uuids[2]}/validacao", json={"validacao": "FALSO_POSITIVO"}, headers=cabecalho)


def test_painel_do_periodo(cliente):
    """O painel soma por dia, turno e posto, e calcula os cartões de conformidade, falsos positivos e pendentes do período."""
    token = admin_pronto(cliente)
    preparar_setembro(cliente, token)
    d = cliente.get(SETEMBRO).json()
    assert d["periodo"] == {"inicio": "2026-09-01", "fim": "2026-09-30", "camera_id": None}
    assert len(d["por_dia"]) == 30 and d["por_dia"][9] == {"dia": "2026-09-10", "total": 3}
    assert sum(x["total"] for x in d["por_dia"]) == 3
    assert d["por_turno"][0] == {"turno": "1", "sem_mascara": 2, "levantada": 1}
    assert [x["turno"] for x in d["por_turno"]] == ["1", "2", "3"]
    assert d["por_posto"] == [{"camera_id": 1, "posto": "Webcam 0", "total": 3}]
    assert d["estados"] == {"conforme": 80, "nao_conforme": 20, "indeterminado": 25}
    c = d["cartoes"]
    assert c["periodo"] == 3 and c["conformidade"] == 0.8 and c["indeterminado"] == 0.2
    assert c["falsos_positivos"] == 0.5 and c["validadas"] == 2 and c["pendentes"] == 1 and c["com_arco"] == 1


def test_filtro_de_posto_vale_para_tudo(cliente):
    """Filtrar por um posto sem dados zera todos os números do painel."""
    token = admin_pronto(cliente)
    preparar_setembro(cliente, token)
    d = cliente.get(SETEMBRO + "&camera_id=99").json()
    assert d["cartoes"]["periodo"] == 0 and d["por_posto"] == [] and d["cartoes"]["conformidade"] is None
    assert d["estados"] == {"conforme": 0, "nao_conforme": 0, "indeterminado": 0}
    assert d["cartoes"]["falsos_positivos"] is None


def test_periodo_padrao_e_cartoes_de_hoje(cliente):
    """Sem filtro, o período vai do dia 1 do mês até hoje e os cartões de hoje e do mês contam a ocorrência nova."""
    admin_pronto(cliente)
    registrar_ocorrencias(cliente, 1, datetime.now(UTC))
    d = cliente.get("/api/dashboard").json()
    hoje = hoje_local()
    assert d["periodo"]["inicio"] == hoje.replace(day=1).isoformat() and d["periodo"]["fim"] == hoje.isoformat()
    assert d["cartoes"]["hoje"] >= 1 and d["cartoes"]["mes"] >= d["cartoes"]["hoje"]


def test_periodo_invalido(cliente):
    """Período invertido ou longo demais é recusado com erro 422."""
    admin_pronto(cliente)
    assert cliente.get("/api/dashboard?inicio=2026-10-10&fim=2026-10-01").status_code == 422
    assert cliente.get("/api/dashboard?inicio=2025-01-01&fim=2026-10-01").status_code == 422


def test_painel_para_supervisor_e_com_login(cliente):
    """O painel exige login, e o supervisor consegue ver a API e a tela."""
    assert cliente.get("/api/dashboard").status_code == 401
    token = admin_pronto(cliente)
    criar_supervisor(cliente)
    cliente.post("/logout", headers={"X-CSRF-Token": token})
    entrar(cliente, "sup", "senha-supervisor-1")
    assert cliente.get("/api/dashboard").status_code == 200
    html = cliente.get("/dashboard").text
    assert 'href="/dashboard"' in html and "/static/vendor/chartjs/chart.umd.js" in html and 'id="g-turno"' in html
