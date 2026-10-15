"""[FASE 2] Configurações (Etapa 2.5, bloco D – RD05 e RD06, tela T06): postos, máscara por posto, zona de interesse
e ajustes do sistema, aplicados sem reiniciar. Câmera e detector SIMULADOS, como no test_fase2_web.py."""
from __future__ import annotations


import numpy as np
import pytest
from sqlalchemy import select

from app import sistema
from app.models import Auditoria, Camera, ConfigSistema
from app.privacy import Borrador
from app.registro import RegistradorOcorrencias
from src.pipeline import Pipeline
from src.zona import dentro_do_poligono, separar_por_zona
from tests.auxiliares import (REGIAO_CABECA_ESPERADA, ROSTO_DESCOBERTO, ROSTO_DETECTADO, criar_pessoa, deslocar,
                              deslocar_caixa)
from tests.conftest import detalhe
from tests.test_fase2_web import (QUADRO, admin_pronto, bcrypt_rapido, cliente, criar_supervisor, ctx, entrar,  # noqa: F401
                                  esperar, montar, registrar_ocorrencias)

QUADRADO = [(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)]       # metade esquerda da imagem


# --------------------------------------------------------------------------------------------------- zona (RD06)
def test_ponto_dentro_e_fora_do_poligono():
    assert dentro_do_poligono((0.25, 0.5), QUADRADO) and not dentro_do_poligono((0.75, 0.5), QUADRADO)
    triangulo = [(0.1, 0.9), (0.5, 0.1), (0.9, 0.9)]
    assert dentro_do_poligono((0.5, 0.6), triangulo) and not dentro_do_poligono((0.15, 0.2), triangulo)


def test_quem_pisa_fora_da_zona_nao_e_avaliado():
    dentro = criar_pessoa(ROSTO_DESCOBERTO)                                      # caixa x 100–300 numa imagem de 1000
    fora = criar_pessoa(ROSTO_DESCOBERTO, caixa=deslocar_caixa((100, 100, 300, 600), 600), track_id=2)
    assert separar_por_zona([dentro, fora], QUADRADO, 1000, 700) == ([dentro], [fora])
    assert separar_por_zona([dentro, fora], None, 1000, 700) == ([dentro, fora], [])


class DetectorDuasPessoas:
    """A pessoa padrão e outra igual 350 px à direita (pontos do corpo e caixa deslocados)."""

    def detectar(self, frame):
        fora = criar_pessoa(deslocar(ROSTO_DESCOBERTO, 350), caixa=deslocar_caixa((100, 100, 300, 600), 350), track_id=2)
        return [criar_pessoa(ROSTO_DESCOBERTO), fora], [], [ROSTO_DETECTADO]


def test_fora_da_zona_continua_borrado(config, fabrica, storage, camera_id):
    """Privacidade: a pessoa fora da zona não é avaliada, mas a imagem gravada sai com a cabeça dela borrada."""
    frame = np.random.default_rng(1).integers(0, 256, (700, 700, 3), dtype=np.uint8)
    resultado = Pipeline(config, DetectorDuasPessoas(), zona=QUADRADO).processar(frame)   # pés em x 0,29 e 0,79
    assert [a.pessoa.track_id for a in resultado.avaliacoes] == [1]
    assert [p.track_id for p in resultado.fora_da_zona] == [2]
    imagem = RegistradorOcorrencias(fabrica, storage, Borrador(None), {}).imagem_anotada(frame, resultado).pixels
    cabeca_de_fora = (510.0, 116.0, 590.0, 220.0)
    assert detalhe(imagem, cabeca_de_fora) < 0.15 * detalhe(frame, cabeca_de_fora)
    assert detalhe(imagem, REGIAO_CABECA_ESPERADA) < 0.15 * detalhe(frame, REGIAO_CABECA_ESPERADA)


# --------------------------------------------------------------------------------------------------- aba Sistema
def test_validacao_dos_ajustes_do_sistema(config, tmp_path):
    from tests.test_fase2_web import ajustes_de_teste
    atuais = sistema.valores_atuais(config, ajustes_de_teste(tmp_path))
    assert sistema.validar({"cooldown_s": 30, "imgsz": 960}, atuais) == {"cooldown_s": 30.0, "imgsz": 960}
    for errado, trecho in [({"imgsz": 700}, "múltiplo de 32"), ({"cooldown_s": -1}, "entre"),
                           ({"retencao_dias": 2.5}, "inteiro"), ({"turnos": {"1": "6h-14h"}}, "HH:MM"),
                           ({"turnos": {}}, "1 a 6"), ({"telegram_ativo": "sim"}, "verdadeiro"),
                           ({"chave_nova": 1}, "desconhecido"),
                           ({"detectar_solda_ativa": False, "exigir_mascara_somente_com_arco": True}, "solda ativa")]:
        with pytest.raises(sistema.ErroSistema, match=trecho):
            sistema.validar(errado, atuais)


def test_ajustes_do_banco_por_cima_do_config_yaml(config, tmp_path):
    from tests.test_fase2_web import ajustes_de_teste
    ajustes = ajustes_de_teste(tmp_path)
    novo_config, novos_ajustes = sistema.aplicar(config, ajustes, {"cooldown_s": 15, "fracao_max_saturada": 0.2,
                                                                   "turnos": {"A": "07:00-19:00"}, "retencao_dias": 90})
    assert novo_config.ocorrencias.cooldown_s == 15 and novo_config.arco.fracao_max_saturada == 0.2
    assert novos_ajustes.turnos == {"A": "07:00-19:00"} and novos_ajustes.retencao_dias == 90
    assert config.ocorrencias.cooldown_s == 60                                # o config.yaml não muda
    # valor inválido gravado à mão no banco: ignorado (o sistema continua iniciando)
    assert sistema.aplicar(config, ajustes, {"imgsz": 333}) == (config, ajustes)


# --------------------------------------------------------------------------------------------------- acesso
def test_configuracoes_so_para_admin(cliente):
    token = admin_pronto(cliente)
    assert cliente.get("/configuracoes").status_code == 200
    criar_supervisor(cliente)
    cliente.post("/logout", headers={"X-CSRF-Token": token})
    token_sup = entrar(cliente, "sup", "senha-supervisor-1")
    cab = {"X-CSRF-Token": token_sup}
    assert cliente.get("/configuracoes").status_code == 403
    assert cliente.get("/api/config/cameras").status_code == 403
    assert cliente.get("/api/config/sistema").status_code == 403
    assert cliente.put("/api/config/sistema", json={"cooldown_s": 1}, headers=cab).status_code == 403
    assert cliente.put("/api/cameras/1/roi", json={"pontos": None}, headers=cab).status_code == 403
    assert cliente.post("/api/cameras", json={}, headers=cab).status_code in (403, 422)


# --------------------------------------------------------------------------------------------------- postos
def novo_posto(c, token, **dados):
    corpo = {"nome_posto": "TIG 02", "processo_solda": "TIG", "tipo": "webcam", "origem": "1", "ativa": True, **dados}
    return c.post("/api/cameras", json=corpo, headers={"X-CSRF-Token": token})


def test_criar_editar_e_desativar_posto(cliente):
    token = admin_pronto(cliente)
    r = novo_posto(cliente, token)
    assert r.status_code == 201, r.text
    posto = r.json()
    assert posto["mascara"]["exigido"] is True and posto["mascara"]["conf_min"] == 0.45
    esperar(lambda: posto["id"] in ctx(cliente).cameras.ids())               # a câmera nova já está ligada
    assert novo_posto(cliente, token, nome_posto="tig 02").status_code == 409
    editado = cliente.put(f"/api/cameras/{posto['id']}", headers={"X-CSRF-Token": token},
                          json={**{k: posto[k] for k in ("nome_posto", "processo_solda", "tipo", "origem")},
                                "ativa": False}).json()
    assert editado["ativa"] is False and posto["id"] not in ctx(cliente).cameras.ids()
    assert cliente.get(f"/api/status?camera_id={posto['id']}").status_code == 404
    with ctx(cliente).fabrica() as s:
        acoes = [a.detalhes.get("acao") for a in s.scalars(select(Auditoria).where(Auditoria.acao == "alterar_config"))]
    assert acoes == ["criar", "editar"]


@pytest.mark.parametrize("dados, trecho", [
    ({"tipo": "rtsp", "origem": "rtsp://admin:1234@10.0.0.5/stream"}, ".env"),
    ({"tipo": "rtsp", "origem": "http://10.0.0.5"}, "RTSP"),
    ({"tipo": "webcam", "origem": "câmera"}, "número"),
    ({"tipo": "arquivo", "origem": "nao_existe.mp4"}, "não encontrado"),
    ({"nome_posto": "X"}, "2 a 100"),
])
def test_posto_com_dados_ruins(cliente, dados, trecho):
    token = admin_pronto(cliente)
    r = novo_posto(cliente, token, **dados)
    assert r.status_code == 400 and trecho in r.json()["detail"]


def test_posto_com_ocorrencias_nao_e_removido(cliente):
    token = admin_pronto(cliente)
    from datetime import datetime, timezone
    registrar_ocorrencias(cliente, 1, datetime(2026, 9, 1, tzinfo=timezone.utc))
    r = cliente.delete("/api/cameras/1", headers={"X-CSRF-Token": token})
    assert r.status_code == 409 and "desative" in r.json()["detail"]
    vazio = novo_posto(cliente, token, ativa=False).json()
    assert cliente.delete(f"/api/cameras/{vazio['id']}", headers={"X-CSRF-Token": token}).status_code == 200
    with ctx(cliente).fabrica() as s:
        assert s.get(Camera, vazio["id"]) is None


# --------------------------------------------------------------------------------------------------- máscara e zona
def test_mascara_do_posto_vale_na_hora_e_mantem_o_cordao(cliente):
    token = admin_pronto(cliente)
    esperar(lambda: ctx(cliente).cameras.obter(1).online)
    antigo = ctx(cliente).cameras.obter(1)
    corpo = {"exigido": True, "conf_min": 0.6, "persistencia_s": 6, "fracao_minima": 0.8, "cobertura_min": 0.4,
             "levantada_nao_conforme": False}
    r = cliente.put("/api/cameras/1/epis", json=corpo, headers={"X-CSRF-Token": token})
    assert r.status_code == 200 and r.json()["mascara"] == corpo
    novo = ctx(cliente).cameras.obter(1)
    mascara = novo.config.epis["mascara"]
    assert novo is not antigo and mascara.conf == 0.6 and mascara.persistencia_s == 6
    assert mascara.cobertura_min == 0.4 and mascara.extras["levantada_nao_conforme"] is False
    assert novo._cordao is antigo._cordao                                       # o cordão do turno continua
    assert cliente.get("/api/cameras/1/epis").json()["mascara"] == corpo
    ruim = {**corpo, "conf_min": 0.99}
    assert cliente.put("/api/cameras/1/epis", json=ruim, headers={"X-CSRF-Token": token}).status_code == 400


def test_zona_de_interesse_do_posto(cliente):
    token = admin_pronto(cliente)
    cab = {"X-CSRF-Token": token}
    r = cliente.put("/api/cameras/1/roi", json={"pontos": [[0, 0], [0.5, 0], [0.5, 1]]}, headers=cab)
    assert r.status_code == 200 and r.json()["zona"] == [[0, 0], [0.5, 0], [0.5, 1]]
    assert ctx(cliente).cameras.obter(1).zona == [(0, 0), (0.5, 0), (0.5, 1)]
    assert cliente.get("/api/config/cameras").json()[0]["zona"] == [[0, 0], [0.5, 0], [0.5, 1]]
    assert cliente.put("/api/cameras/1/roi", json={"pontos": [[0, 0], [1, 1]]}, headers=cab).status_code == 400
    assert cliente.put("/api/cameras/1/roi", json={"pontos": [[0, 0], [2, 0], [0, 1]]}, headers=cab).status_code == 400
    assert cliente.put("/api/cameras/1/roi", json={"pontos": None}, headers=cab).json()["zona"] is None
    assert ctx(cliente).cameras.obter(1).zona is None


# --------------------------------------------------------------------------------------------------- sistema (API)
def test_sistema_vale_na_hora_e_depois_de_reiniciar(tmp_path):
    with montar(tmp_path) as c:
        token = admin_pronto(c)
        d = c.get("/api/config/sistema").json()
        assert d["valores"]["cooldown_s"] == 60 and d["padrao"]["cooldown_s"] == 60
        assert d["telegram"]["configurado"] is False and d["disco"]["total_bytes"] > 0
        r = c.put("/api/config/sistema", json={"cooldown_s": 30, "turnos": {"A": "07:00-19:00", "B": "19:00-07:00"}},
                  headers={"X-CSRF-Token": token})
        assert r.status_code == 200 and r.json()["alterados"] == ["cooldown_s", "turnos"]
        assert ctx(c).config_base.ocorrencias.cooldown_s == 30
        assert esperar(lambda: ctx(c).cameras.obter(1)).config.ocorrencias.cooldown_s == 30
        assert ctx(c).registrador.turnos == {"A": "07:00-19:00", "B": "19:00-07:00"}
        assert '<option value="B">' in c.get("/ocorrencias").text
        mesma = c.put("/api/config/sistema", json={"cooldown_s": 30}, headers={"X-CSRF-Token": token})
        assert mesma.json()["alterados"] == []
        ruim = c.put("/api/config/sistema", json={"imgsz": 700}, headers={"X-CSRF-Token": token})
        assert ruim.status_code == 400 and "32" in ruim.json()["detail"]
        with ctx(c).fabrica() as s:
            assert s.get(ConfigSistema, "cooldown_s").valor == 30
    with montar(tmp_path) as c:                                                 # o sistema reiniciou: continua valendo
        assert ctx(c).config_base.ocorrencias.cooldown_s == 30 and ctx(c).ajustes.turnos["A"] == "07:00-19:00"


def test_token_do_telegram_nunca_aparece_inteiro(tmp_path):
    with montar(tmp_path, TELEGRAM_TOKEN="123456789:AAH-segredo-do-bot-xyz9", TELEGRAM_CHAT_ID="-1001234567") as c:
        admin_pronto(c)
        resposta = c.get("/api/config/sistema")
        t = resposta.json()["telegram"]
        assert t["configurado"] is True and t["token"] == "••••xyz9" and t["chat_id"] == "••••4567"
        assert "segredo" not in resposta.text and "1001234567" not in resposta.text
