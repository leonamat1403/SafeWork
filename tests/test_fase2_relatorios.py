"""[FASE 2] Etapa 2.5, bloco F: alerta pelo Telegram (RD09, SEMPRE simulado: os testes nunca usam a rede) e
exportação CSV + relatório mensal em PDF (RD10). Câmera e detector SIMULADOS, como no test_fase2_web.py."""
from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timezone

import cv2
import numpy as np
from sqlalchemy import select

from app.models import Auditoria, Camera, Ocorrencia
from app.notificador import Notificador, _multipart, legenda
from app.privacy import Borrador
from app.registro import RegistradorOcorrencias
from app.relatorios import gerar_relatorio_mensal, guardar_relatorio_do_mes_passado, ultimo_dia
from src.compliance import avaliar_frame
from src.occurrences import Ocorrencia as OcorrenciaDetectada
from src.pipeline import ResultadoFrame
from tests.auxiliares import ROSTO_DESCOBERTO, ROSTO_DETECTADO, criar_pessoa
from tests.test_fase2_web import (TELEGRAM_ENVIADOS, admin_pronto, ajustes_de_teste, bcrypt_rapido, cliente,  # noqa: F401
                                  criar_supervisor, ctx, entrar, esperar, montar, registrar_ocorrencias)

UTC = timezone.utc
TELEGRAM = {"TELEGRAM_TOKEN": "123456789:AAH-token-de-teste-abcd", "TELEGRAM_CHAT_ID": "-1009876543"}


def preparar(c, token) -> list[str]:
    """3 ocorrências em 10/09/2026 (a 1ª de máscara levantada, com arco), uma confirmada."""
    uuids = registrar_ocorrencias(c, 3, datetime(2026, 9, 10, 12, 0, tzinfo=UTC))
    with ctx(c).fabrica() as s:
        primeira = s.query(Ocorrencia).filter_by(uuid=uuids[0]).one()
        primeira.mascara_levantada, primeira.arco_ativo = True, True
        s.commit()
    c.post(f"/api/ocorrencias/{uuids[1]}/validacao", json={"validacao": "CONFIRMADA"}, headers={"X-CSRF-Token": token})
    return uuids


def ler_csv(resposta) -> list[list[str]]:
    """Lê o CSV da resposta como lista de linhas, conferindo o BOM que o Excel exige."""
    texto = resposta.content.decode("utf-8")
    assert texto.startswith("﻿")                        # o Excel reconhece os acentos
    return list(csv.reader(io.StringIO(texto[1:]), delimiter=";"))


# --------------------------------------------------------------------------------------------------- CSV (RD10)
def test_exportar_csv_com_os_filtros_da_tela(cliente):
    """CSV exportado respeita os filtros da tela, traz as colunas certas e registra a exportação na auditoria."""
    token = admin_pronto(cliente)
    uuids = preparar(cliente, token)
    r = cliente.get("/api/ocorrencias/exportar.csv?inicio=2026-09-01&fim=2026-09-30")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"] and ".csv" in r.headers["content-disposition"]
    linhas = ler_csv(r)
    assert linhas[0][:5] == ["Data e hora", "Turno", "Posto", "Pessoa no vídeo", "Falta"] and len(linhas) == 4
    por_codigo = {linha[-1]: linha for linha in linhas[1:]}
    levantada = por_codigo[uuids[0]]
    assert levantada[0] == "10/09/2026 09:00:00" and levantada[1] == "1" and levantada[2] == "Webcam 0"
    assert levantada[4] == "Máscara levantada" and levantada[6] == "Sim"
    assert por_codigo[uuids[1]][10] == "Confirmada" and por_codigo[uuids[1]][11] == "Administrador"
    assert por_codigo[uuids[2]][4] == "Sem máscara" and por_codigo[uuids[2]][8] == "1,00"
    so_confirmadas = ler_csv(cliente.get("/api/ocorrencias/exportar.csv?inicio=2026-09-01&validacao=CONFIRMADA"))
    assert len(so_confirmadas) == 2
    with ctx(cliente).fabrica() as s:
        auditoria = [a.detalhes for a in s.scalars(select(Auditoria).where(Auditoria.acao == "exportar"))]
    assert auditoria[0] == {"formato": "csv", "linhas": 3, "inicio": "2026-09-01", "fim": "2026-09-30"}


def test_csv_nao_executa_formulas(cliente):
    """Um nome de posto que começa com "=" vira texto (o Excel não roda fórmulas vindas do arquivo)."""
    token = admin_pronto(cliente)
    preparar(cliente, token)
    with ctx(cliente).fabrica() as s:
        s.get(Camera, 1).nome_posto = '=HYPERLINK("http://exemplo")'
        s.commit()
    linhas = ler_csv(cliente.get("/api/ocorrencias/exportar.csv"))
    assert all(linha[2].startswith("'=") for linha in linhas[1:])


def test_csv_para_supervisor_e_com_login(cliente):
    """Exportar CSV exige login, vale para supervisor e recusa validação desconhecida."""
    assert cliente.get("/api/ocorrencias/exportar.csv").status_code == 401
    token = admin_pronto(cliente)
    criar_supervisor(cliente)
    cliente.post("/logout", headers={"X-CSRF-Token": token})
    entrar(cliente, "sup", "senha-supervisor-1")
    assert cliente.get("/api/ocorrencias/exportar.csv").status_code == 200
    assert cliente.get("/api/ocorrencias/exportar.csv?validacao=OUTRA").status_code == 422


# --------------------------------------------------------------------------------------------------- PDF (RD10)
def test_relatorio_mensal_em_pdf(cliente):
    """Relatório mensal em PDF é gerado, valida mês e posto e registra a exportação na auditoria."""
    token = admin_pronto(cliente)
    preparar(cliente, token)
    r = cliente.get("/api/relatorios/mensal.pdf?mes=2026-09")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and len(r.content) > 2000
    assert 'filename="relatorio_2026-09.pdf"' in r.headers["content-disposition"]
    assert cliente.get("/api/relatorios/mensal.pdf?mes=2026-09&camera_id=1").status_code == 200
    assert cliente.get("/api/relatorios/mensal.pdf?mes=setembro").status_code == 422
    assert cliente.get("/api/relatorios/mensal.pdf?mes=2099-01").status_code == 422
    assert cliente.get("/api/relatorios/mensal.pdf?mes=2026-09&camera_id=99").status_code == 404
    with ctx(cliente).fabrica() as s:
        formatos = [a.detalhes["formato"] for a in s.scalars(select(Auditoria).where(Auditoria.acao == "exportar"))]
    assert formatos == ["pdf", "pdf"]


def test_pdf_de_mes_vazio_e_rotina_do_dia_primeiro(fabrica, tmp_path):
    """Mês sem ocorrências gera PDF, e a rotina do dia 1 guarda o relatório do mês passado."""
    assert ultimo_dia(date(2026, 2, 10)) == date(2026, 2, 28) and ultimo_dia(date(2026, 12, 1)) == date(2026, 12, 31)
    assert gerar_relatorio_mensal(fabrica, {"1": "06:00-14:00"}, date(2026, 2, 1)).startswith(b"%PDF")
    caminho = guardar_relatorio_do_mes_passado(fabrica, tmp_path / "relatorios", {"1": "06:00-14:00"})
    assert caminho.exists() and caminho.name.startswith("relatorio_") and caminho.read_bytes().startswith(b"%PDF")


# --------------------------------------------------------------------------------------------------- Telegram (RD09)
def test_texto_do_alerta():
    """Legenda do alerta e corpo multipart da foto saem no formato esperado."""
    oc = Ocorrencia(uuid="x", camera_id=1, data_hora=datetime(2026, 10, 15, 13, 5, tzinfo=UTC), track_id=3,
                    mascara_levantada=True, arco_ativo=True, origem="ao_vivo")
    texto = legenda(oc, "MIG 01")
    assert texto.splitlines() == ["URGENTE: arco aceso, solda em andamento", "Falta de EPI – MIG 01",
                                  "15/10/2026 10:05", "Máscara levantada (pessoa #3 no vídeo)", "Valide em Ocorrências."]
    corpo, tipo = _multipart({"chat_id": "-100"}, ("o.jpg", b"\xff\xd8JPEG", "image/jpeg"))
    fronteira = tipo.split("boundary=")[1]
    assert corpo.count(fronteira.encode()) == 3 and b'name="photo"; filename="o.jpg"' in corpo and b"\xff\xd8JPEG" in corpo


def alertas(trecho: str) -> list:
    """Lista os envios simulados do Telegram cujo texto contém o trecho dado."""
    return [(m, campos, foto) for m, campos, foto in TELEGRAM_ENVIADOS if trecho in campos.get("caption", campos.get("text", ""))]


def test_alerta_com_a_foto_borrada(tmp_path):
    """Ocorrência nova dispara alerta no Telegram com a mesma foto borrada gravada no disco."""
    TELEGRAM_ENVIADOS.clear()
    with montar(tmp_path, **TELEGRAM) as c:
        admin_pronto(c)
        registrar_ocorrencias(c, 1, datetime(2026, 9, 10, 12, 0, tzinfo=UTC))
        metodo, campos, foto = esperar(lambda: alertas("10/09/2026 09:00"))[0]
        assert metodo == "sendPhoto" and campos["chat_id"] == "-1009876543"
        assert "Falta de EPI – Webcam 0" in campos["caption"] and "Sem máscara" in campos["caption"]
        nome, conteudo, tipo = foto
        assert tipo == "image/jpeg" and cv2.imdecode(np.frombuffer(conteudo, np.uint8), cv2.IMREAD_COLOR) is not None
        with ctx(c).fabrica() as s:   # a foto enviada é exatamente a imagem borrada gravada no disco
            caminho = s.scalars(select(Ocorrencia.caminho_imagem).order_by(Ocorrencia.data_hora)).first()
        assert conteudo == ctx(c).storage.ler(caminho)


def test_alerta_desligado_ou_sem_token(tmp_path):
    """Sem token ou com o alerta desligado na tela, nada é enviado ao Telegram."""
    TELEGRAM_ENVIADOS.clear()
    with montar(tmp_path) as c:                                     # sem token no .env
        admin_pronto(c)
        assert ctx(c).notificador.ativo is False
        registrar_ocorrencias(c, 1, datetime(2026, 9, 10, 12, 0, tzinfo=UTC))
    with montar(tmp_path / "b", **TELEGRAM) as c:                   # com token, mas desligado na tela
        token = admin_pronto(c)
        c.put("/api/config/sistema", json={"telegram_ativo": False}, headers={"X-CSRF-Token": token})
        assert ctx(c).notificador.ativo is False
        registrar_ocorrencias(c, 1, datetime(2026, 9, 11, 12, 0, tzinfo=UTC))
    assert TELEGRAM_ENVIADOS == []


def test_upload_registrado_nao_gera_alerta(fabrica, storage, camera_id, tmp_path):
    """Ocorrência vinda de upload não gera alerta."""
    notificador = Notificador(ajustes_de_teste(tmp_path, **TELEGRAM), storage, fabrica, lambda *a: None)
    assert notificador.ativo is True
    assert notificador.avisar(Ocorrencia(uuid="u", camera_id=camera_id, origem="upload")) is False


def test_falha_no_envio_nao_derruba_e_nao_mostra_o_token(config, fabrica, storage, camera_id, caplog, tmp_path):
    """Falha no envio é registrada sem mostrar o token e a thread do notificador continua viva."""
    def falha(token, metodo, campos, foto=None):
        """Simula um envio que falha com erro cuja mensagem contém o token."""
        raise RuntimeError(f"erro na URL https://api.telegram.org/bot{token}/sendMessage")
    notificador = Notificador(ajustes_de_teste(tmp_path, **TELEGRAM), storage, fabrica, falha)
    registrador = RegistradorOcorrencias(fabrica, storage, Borrador(None), {})
    registrador.notificador = notificador
    notificador.iniciar()
    try:
        with caplog.at_level(logging.WARNING, logger="epi_solda.telegram"):
            avaliacoes = avaliar_frame([criar_pessoa(ROSTO_DESCOBERTO)], [], config, rostos=[ROSTO_DETECTADO])
            detectada = OcorrenciaDetectada(datetime(2026, 9, 1, tzinfo=UTC), 1.0, 1, 1, ["mascara"], {}, {}, [], {},
                                            False)
            registrador.registrar(detectada, np.zeros((700, 500, 3), np.uint8),
                                  ResultadoFrame(avaliacoes, [], False, 0.0, []), camera_id)
            esperar(lambda: "não enviado" in caplog.text)
        assert "token-de-teste" not in caplog.text and "****" in caplog.text
        assert notificador._thread.is_alive()                     # a thread continua para o próximo alerta
    finally:
        notificador.parar()


def test_mensagem_de_teste_pela_tela(tmp_path):
    """Mensagem de teste do Telegram é enviada com token e dá erro 502 sem ele."""
    TELEGRAM_ENVIADOS.clear()
    with montar(tmp_path, **TELEGRAM) as c:
        token = admin_pronto(c)
        assert c.post("/api/config/telegram/teste", headers={"X-CSRF-Token": token}).json() == {"enviado": True}
        assert TELEGRAM_ENVIADOS[-1][0] == "sendMessage" and "Teste" in TELEGRAM_ENVIADOS[-1][1]["text"]
    with montar(tmp_path / "b") as c:
        token = admin_pronto(c)
        r = c.post("/api/config/telegram/teste", headers={"X-CSRF-Token": token})
        assert r.status_code == 502 and ".env" in r.json()["detail"]
