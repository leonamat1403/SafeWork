"""[FASE 2] Servidor web (Etapa 2.3): login, perfis, CSRF, câmera ao vivo, upload, ocorrências e /midia.

A câmera e o detector são SIMULADOS: uma "webcam" que devolve sempre o mesmo quadro e um detector que sempre vê uma
pessoa de frente, sem máscara, com o rosto descoberto. Nada toca a pasta data/ real.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.auth
from app.config import carregar_ajustes, config_da_camera
from app.main import criar_app
from app.models import Auditoria, Camera, ConfigEpiCamera, Ocorrencia, Usuario
from app.stream import origem_da_camera
from src.occurrences import Ocorrencia as OcorrenciaDetectada
from src.video import ErroFonte
from tests.auxiliares import REGIAO_CABECA_ESPERADA, ROSTO_DESCOBERTO, ROSTO_DETECTADO, criar_pessoa
from tests.conftest import detalhe

SENHA_INICIAL = "senha-inicial-123"
NOVA_SENHA = "Nova-senha-forte-1"
QUADRO = np.random.default_rng(0).integers(0, 256, (700, 500, 3), dtype=np.uint8)
UTC = timezone.utc


class DetectorFalso:
    """Sempre uma pessoa de frente, sem máscara, rosto descoberto (track_id 1)."""

    def detectar(self, frame):
        return [criar_pessoa(ROSTO_DESCOBERTO)], [], [ROSTO_DETECTADO]


class FonteFalsa:
    tipo, fps = "webcam", 20.0

    def __init__(self, origem: str) -> None:
        self.inicio = time.monotonic()

    def ler(self, parar=None):
        time.sleep(0.05)
        return QUADRO.copy(), time.monotonic() - self.inicio

    def fechar(self) -> None:
        pass


def fonte_offline(origem: str):
    raise ErroFonte("webcam 0 não encontrada")


@pytest.fixture(autouse=True)
def bcrypt_rapido(monkeypatch):
    monkeypatch.setattr(app.auth, "CUSTO_BCRYPT", 4)   # só nos testes: hash rápido


def ajustes_de_teste(tmp_path, **extra):
    ambiente = {"DATA_DIR": str(tmp_path / "data"), "SECRET_KEY": "x" * 64, "ADMIN_LOGIN_INICIAL": "admin",
                "ADMIN_SENHA_INICIAL": SENHA_INICIAL, "MODO_DESENVOLVIMENTO": "true", **extra}
    return carregar_ajustes(ambiente=ambiente)


TELEGRAM_ENVIADOS: list = []   # o que teria ido para o Telegram (os testes nunca usam a rede)


def telegram_falso(token, metodo, campos, foto=None):
    TELEGRAM_ENVIADOS.append((metodo, campos, foto))


def montar(tmp_path, fonte=FonteFalsa, **extra) -> TestClient:
    sistema = criar_app(ajustes_de_teste(tmp_path, **extra), criar_detector=lambda config: DetectorFalso(),
                        criar_fonte=fonte, iniciar_rotinas=False, enviar_telegram=telegram_falso)
    return TestClient(sistema)


@pytest.fixture
def cliente(tmp_path):
    with montar(tmp_path) as c:
        yield c


def ctx(c: TestClient):
    return c.app.state.ctx


def entrar(c: TestClient, login: str = "admin", senha: str = SENHA_INICIAL) -> str:
    resposta = c.post("/login", data={"login": login, "senha": senha})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["csrf_token"]


def admin_pronto(c: TestClient) -> str:
    """Login do admin inicial + troca obrigatória da senha. Devolve o token CSRF."""
    token = entrar(c)
    r = c.post("/api/trocar-senha", json={"senha_atual": SENHA_INICIAL, "nova_senha": NOVA_SENHA},
               headers={"X-CSRF-Token": token})
    assert r.status_code == 200, r.text
    return token


def criar_supervisor(c: TestClient, login: str = "sup", senha: str = "senha-supervisor-1") -> None:
    with ctx(c).fabrica() as s:
        s.add(Usuario(nome="Supervisor", login=login, senha_hash=app.auth.gerar_hash(senha), perfil="SUPERVISOR"))
        s.commit()


def registrar_ocorrencias(c: TestClient, quantidade: int, inicio: datetime, camera_id: int = 1) -> list[str]:
    """Ocorrências reais (imagem borrada no disco + linha no banco), uma por hora a partir de `inicio`."""
    registrador = ctx(c).registrador
    from src.compliance import avaliar_frame
    from src.pipeline import ResultadoFrame
    avaliacoes = avaliar_frame([criar_pessoa(ROSTO_DESCOBERTO)], [], ctx(c).config_base, rostos=[ROSTO_DETECTADO])
    resultado = ResultadoFrame(avaliacoes, [], False, 0.0, [ROSTO_DETECTADO])
    uuids = []
    for i in range(quantidade):
        oc = OcorrenciaDetectada(inicio + timedelta(hours=i), 1.0, 1, 1, ["mascara"],
                                 {"mascara": "rosto visível sem máscara"}, {"mascara": 1.0}, [], {}, False)
        uuids.append(registrador.registrar(oc, QUADRO, resultado, camera_id).uuid)
    return uuids


def esperar(condicao, limite_s: float = 5.0):
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        valor = condicao()
        if valor:
            return valor
        time.sleep(0.05)
    raise AssertionError("tempo esgotado")


# --------------------------------------------------------------------------------------------------- primeiro uso
def test_primeiro_uso_cria_admin_e_webcam(cliente):
    with ctx(cliente).fabrica() as s:
        admin = s.scalars(select(Usuario)).one()
        camera = s.scalars(select(Camera)).one()
        mascara = s.scalars(select(ConfigEpiCamera).where(ConfigEpiCamera.epi == "mascara")).one()
    assert admin.perfil == "ADMIN" and admin.deve_trocar_senha and admin.senha_hash != SENHA_INICIAL
    assert camera.nome_posto == "Webcam 0" and camera.tipo == "webcam"
    assert mascara.exigido and mascara.conf_min == 0.45 and mascara.persistencia_s == 4


# --------------------------------------------------------------------------------------------------- acesso
@pytest.mark.parametrize("rota", ["/api/me", "/api/status", "/api/cameras", "/api/ocorrencias",
                                  f"/midia/{uuid.uuid4()}", "/api/cameras/1/stream.mjpg",
                                  "/api/cameras/1/snapshot.jpg", "/api/uploads/abc"])
def test_sem_login_tudo_responde_401(cliente, rota):
    assert cliente.get(rota).status_code == 401


def test_senha_errada_e_bloqueio_apos_5_tentativas(cliente):
    for _ in range(5):
        assert cliente.post("/login", data={"login": "admin", "senha": "errada"}).status_code == 401
    assert cliente.post("/login", data={"login": "admin", "senha": SENHA_INICIAL}).status_code == 429
    assert cliente.post("/login", data={"login": "ninguem", "senha": "x"}).status_code == 401
    assert cliente.post("/login", data={"login": "minha-senha-secreta", "senha": "x"}).status_code == 401
    with ctx(cliente).fabrica() as s:
        falhas = [a.detalhes for a in s.query(Auditoria).filter_by(acao="login_falhou")]
    assert len(falhas) == 7 and falhas[0] == {"login": "admin"}
    assert falhas[-1] == {"login_desconhecido": True} and "minha-senha-secreta" not in str(falhas)


def test_primeiro_acesso_exige_troca_de_senha(cliente):
    token = entrar(cliente)
    assert cliente.get("/api/me").json()["deve_trocar_senha"] is True
    assert cliente.get("/api/status").status_code == 403
    corpo = {"senha_atual": SENHA_INICIAL, "nova_senha": "curta"}
    assert cliente.post("/api/trocar-senha", json=corpo).status_code == 403          # sem CSRF
    assert cliente.post("/api/trocar-senha", json=corpo, headers={"X-CSRF-Token": token}).status_code == 400
    corpo["nova_senha"] = NOVA_SENHA
    assert cliente.post("/api/trocar-senha", json=corpo, headers={"X-CSRF-Token": token}).status_code == 200
    assert cliente.get("/api/status").status_code == 200
    cliente.post("/logout", headers={"X-CSRF-Token": token})
    assert cliente.post("/login", data={"login": "admin", "senha": SENHA_INICIAL}).status_code == 401
    entrar(cliente, senha=NOVA_SENHA)


def test_logout_encerra_a_sessao(cliente):
    token = admin_pronto(cliente)
    assert cliente.post("/logout", headers={"X-CSRF-Token": token}).status_code == 200
    assert cliente.get("/api/me").status_code == 401
    with ctx(cliente).fabrica() as s:
        assert s.query(Auditoria).filter_by(acao="logout").count() == 1


def test_supervisor_nao_pausa_camera_e_admin_pausa(cliente):
    criar_supervisor(cliente)
    token = entrar(cliente, "sup", "senha-supervisor-1")
    assert cliente.post("/api/cameras/1/pausar", headers={"X-CSRF-Token": token}).status_code == 403
    token = admin_pronto(cliente)
    assert cliente.post("/api/cameras/1/pausar").status_code == 403                  # sem CSRF
    assert cliente.post("/api/cameras/1/pausar", headers={"X-CSRF-Token": token}).status_code == 200
    assert cliente.get("/api/status?camera_id=1").json()["pausada"] is True
    assert cliente.post("/api/cameras/1/retomar", headers={"X-CSRF-Token": token}).json()["pausada"] is False


def test_cabecalhos_de_seguranca_e_documentacao_no_modo_desenvolvimento(cliente):
    r = cliente.get("/docs")
    assert r.status_code == 200
    assert r.headers["X-Frame-Options"] == "DENY" and r.headers["X-Content-Type-Options"] == "nosniff"
    assert cliente.get("/api/me").headers["Cache-Control"] == "no-store, private"


def test_sem_modo_desenvolvimento_nao_ha_documentacao(tmp_path):
    with montar(tmp_path, MODO_DESENVOLVIMENTO="false") as c:
        assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404


def test_sem_secret_key_fora_do_modo_desenvolvimento_nao_inicia(tmp_path):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        criar_app(ajustes_de_teste(tmp_path, SECRET_KEY="", MODO_DESENVOLVIMENTO="false"))


# --------------------------------------------------------------------------------------------------- ao vivo
def test_status_ao_vivo_mostra_a_pessoa_sem_mascara(cliente):
    admin_pronto(cliente)
    status = esperar(lambda: (s := cliente.get("/api/status").json())["pessoas"] and s)
    assert status["online"] is True and status["camera_id"] == 1 and status["fps"] >= 0
    pessoa = status["pessoas"][0]
    assert pessoa["cor"] == "vermelho" and pessoa["epis"]["mascara"]["estado"] == "NAO_CONFORME"
    lista = cliente.get("/api/cameras").json()
    assert lista[0]["online"] is True and lista[0]["nome_posto"] == "Webcam 0"


def test_stream_mjpeg_envia_quadros_jpeg(cliente):
    admin_pronto(cliente)
    esperar(lambda: cliente.get("/api/status").json()["pessoas"])
    r = cliente.get("/api/cameras/1/stream.mjpg?max_quadros=1")
    assert r.status_code == 200 and r.headers["content-type"].startswith("multipart/x-mixed-replace")
    assert r.content.startswith(b"--quadro\r\nContent-Type: image/jpeg") and b"\xff\xd8" in r.content
    assert cliente.get("/api/cameras/99/stream.mjpg").status_code == 404


def test_snapshot_sai_borrado(cliente):
    admin_pronto(cliente)
    esperar(lambda: cliente.get("/api/status").json()["pessoas"])
    r = cliente.get("/api/cameras/1/snapshot.jpg")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    foto = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    assert detalhe(foto, REGIAO_CABECA_ESPERADA) < 0.10 * detalhe(QUADRO, REGIAO_CABECA_ESPERADA)


def test_camera_offline_aparece_no_status(tmp_path):
    with montar(tmp_path, fonte=fonte_offline) as c:
        admin_pronto(c)
        status = esperar(lambda: (s := c.get("/api/status").json())["erro"] and s)
        assert status["online"] is False and "não encontrada" in status["erro"]


# --------------------------------------------------------------------------------------------------- ocorrências
def test_lista_de_ocorrencias_paginada_e_filtrada(cliente):
    token = admin_pronto(cliente)
    registrar_ocorrencias(cliente, 25, datetime(2026, 10, 10, 12, 0, tzinfo=UTC))   # 10/10 09:00 em diante

    pagina1 = cliente.get("/api/ocorrencias").json()
    assert pagina1["total"] == 25 and pagina1["paginas"] == 2 and len(pagina1["itens"]) == 20
    datas = [i["data_hora"] for i in pagina1["itens"]]
    assert datas == sorted(datas, reverse=True)                                  # mais recente primeiro
    assert len(cliente.get("/api/ocorrencias?pagina=2").json()["itens"]) == 5
    item = pagina1["itens"][0]
    assert item["posto"] == "Webcam 0" and item["thumb_url"].startswith("/midia/") and item["validacao"] == "PENDENTE"

    # 10/10 em Brasília: das 09:00 às 23:00 = 15 ocorrências
    assert cliente.get("/api/ocorrencias?inicio=2026-10-10&fim=2026-10-10").json()["total"] == 15
    assert cliente.get("/api/ocorrencias?epi=mascara").json()["total"] == 25
    assert cliente.get("/api/ocorrencias?epi=luvas").json()["total"] == 0
    assert cliente.get("/api/ocorrencias?camera_id=2").json()["total"] == 0
    assert cliente.get("/api/ocorrencias?turno=3").json()["total"] > 0
    assert cliente.get("/api/ocorrencias?epi=sapato").status_code == 422

    alvo = item["uuid"]
    r = cliente.post(f"/api/ocorrencias/{alvo}/validacao", json={"validacao": "FALSO_POSITIVO"},
                     headers={"X-CSRF-Token": token})
    assert r.status_code == 200 and r.json()["validado_por"] == "Administrador"
    assert cliente.get("/api/ocorrencias?validacao=FALSO_POSITIVO").json()["total"] == 1
    assert cliente.get(f"/api/ocorrencias/{alvo}").json()["validacao"] == "FALSO_POSITIVO"
    with ctx(cliente).fabrica() as s:
        auditoria = s.query(Auditoria).filter_by(acao="validar").one()
    assert auditoria.detalhes == {"uuid": alvo, "de": "PENDENTE", "para": "FALSO_POSITIVO"}


def test_midia_so_com_login_e_sempre_borrada(cliente):
    alvo = registrar_ocorrencias(cliente, 1, datetime.now(UTC))[0]
    assert cliente.get(f"/midia/{alvo}").status_code == 401
    admin_pronto(cliente)
    r = cliente.get(f"/midia/{alvo}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.headers["Cache-Control"] == "no-store, private"
    imagem = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    assert detalhe(imagem, REGIAO_CABECA_ESPERADA) < 0.10 * detalhe(QUADRO, REGIAO_CABECA_ESPERADA)
    assert cliente.get(f"/midia/{alvo}?tipo=thumb").status_code == 200
    assert cliente.get(f"/midia/{uuid.uuid4()}").status_code == 404
    assert cliente.get("/midia/..%2F..%2Fdb%2Fepi.sqlite3").status_code == 404


def test_excluir_ocorrencia_so_admin(cliente):
    alvo = registrar_ocorrencias(cliente, 1, datetime.now(UTC))[0]
    with ctx(cliente).fabrica() as s:
        caminho = s.scalars(select(Ocorrencia.caminho_imagem)).one()
    criar_supervisor(cliente)
    token = entrar(cliente, "sup", "senha-supervisor-1")
    assert cliente.delete(f"/api/ocorrencias/{alvo}", headers={"X-CSRF-Token": token}).status_code == 403
    token = admin_pronto(cliente)
    assert cliente.delete(f"/api/ocorrencias/{alvo}", headers={"X-CSRF-Token": token}).status_code == 200
    assert not (ctx(cliente).ajustes.data_dir / caminho).exists()
    assert cliente.get(f"/api/ocorrencias/{alvo}").status_code == 404
    with ctx(cliente).fabrica() as s:
        assert s.query(Auditoria).filter_by(acao="excluir").count() == 1


# --------------------------------------------------------------------------------------------------- upload
def enviar(c: TestClient, token: str, nome: str, conteudo: bytes, tipo: str = "image/png"):
    return c.post("/api/uploads", files={"arquivo": (nome, conteudo, tipo)}, headers={"X-CSRF-Token": token})


def aguardar_upload(c: TestClient, trabalho_id: str) -> dict:
    return esperar(lambda: (r := c.get(f"/api/uploads/{trabalho_id}").json())["estado"] in ("concluido", "erro") and r)


def test_upload_de_foto_borrada_e_registro_como_ocorrencia(cliente):
    token = admin_pronto(cliente)
    r = enviar(cliente, token, "foto.png", cv2.imencode(".png", QUADRO)[1].tobytes())
    assert r.status_code == 202
    resultado = aguardar_upload(cliente, r.json()["id"])
    assert resultado["estado"] == "concluido", resultado["erro"]
    assert resultado["pessoas"][0]["epis"]["mascara"]["predominante"] == "NAO_CONFORME"
    assert len(resultado["ocorrencias_encontradas"]) == 1 and resultado["registradas"] is None

    arquivo = cliente.get(resultado["arquivo_url"])
    assert arquivo.status_code == 200 and arquivo.headers["content-type"] == "image/jpeg"
    foto = cv2.imdecode(np.frombuffer(arquivo.content, np.uint8), cv2.IMREAD_COLOR)
    assert detalhe(foto, REGIAO_CABECA_ESPERADA) < 0.10 * detalhe(QUADRO, REGIAO_CABECA_ESPERADA)
    assert not list((ctx(cliente).ajustes.data_dir / "uploads_temp").rglob("entrada*"))   # original apagado

    with ctx(cliente).fabrica() as s:
        assert s.query(Ocorrencia).count() == 0                                   # upload não vira ocorrência sozinho
    registro = cliente.post(f"/api/uploads/{resultado['id']}/registrar", headers={"X-CSRF-Token": token})
    assert registro.status_code == 200 and len(registro.json()["registradas"]) == 1
    assert cliente.post(f"/api/uploads/{resultado['id']}/registrar",
                        headers={"X-CSRF-Token": token}).status_code == 409
    with ctx(cliente).fabrica() as s:
        assert s.scalars(select(Ocorrencia.origem)).one() == "upload"


def test_upload_de_video(cliente, tmp_path):
    token = admin_pronto(cliente)
    caminho = tmp_path / "curto.mp4"
    gravador = cv2.VideoWriter(str(caminho), cv2.VideoWriter_fourcc(*"mp4v"), 10, (500, 700))
    for _ in range(15):
        gravador.write(QUADRO)
    gravador.release()
    r = enviar(cliente, token, "curto.mp4", caminho.read_bytes(), "video/mp4")
    resultado = aguardar_upload(cliente, r.json()["id"])
    assert resultado["estado"] == "concluido", resultado["erro"]
    assert resultado["tipo_arquivo"] in ("video/mp4", "video/webm") and resultado["pessoas"][0]["track_id"] == 1
    assert cliente.get(resultado["arquivo_url"]).status_code == 200


def test_upload_recusa_tipo_conteudo_e_tamanho(tmp_path):
    with montar(tmp_path) as c:
        token = admin_pronto(c)
        assert enviar(c, token, "notas.txt", b"texto", "text/plain").status_code == 415
        assert enviar(c, token, "falsa.jpg", b"isto nao e uma imagem").status_code == 415
        assert enviar(c, token, "vazia.png", b"").status_code == 400
        assert c.post("/api/uploads", files={"arquivo": ("f.png", b"x", "image/png")}).status_code == 403   # CSRF
        ctx(c).uploads.ajustes = ajustes_de_teste(tmp_path).__class__(
            **{**ctx(c).ajustes.__dict__, "upload_tamanho_max_mb": 1})
        assert enviar(c, token, "grande.png", b"0" * (1024 * 1024 + 10)).status_code == 413
        assert not [p for p in (ctx(c).ajustes.data_dir / "uploads_temp").rglob("*") if p.is_file()]


def test_upload_de_outro_usuario_nao_aparece(cliente):
    token = admin_pronto(cliente)
    trabalho = enviar(cliente, token, "foto.png", cv2.imencode(".png", QUADRO)[1].tobytes()).json()["id"]
    criar_supervisor(cliente)
    entrar(cliente, "sup", "senha-supervisor-1")
    assert cliente.get(f"/api/uploads/{trabalho}").status_code == 404


# --------------------------------------------------------------------------------------------------- unidades
def test_config_da_camera_usa_os_limiares_do_posto(config):
    linhas = [ConfigEpiCamera(epi="mascara", exigido=True, conf_min=0.6, persistencia_s=6, fracao_minima=0.8,
                              parametros_extra={"cobertura_min": 0.4}),
              ConfigEpiCamera(epi="luvas", exigido=True, conf_min=0.3, persistencia_s=2, fracao_minima=0.75,
                              parametros_extra={})]
    cfg = config_da_camera(config, linhas)
    assert (cfg.epis["mascara"].conf, cfg.epis["mascara"].persistencia_s, cfg.epis["mascara"].fracao_minima,
            cfg.epis["mascara"].cobertura_min) == (0.6, 6, 0.8, 0.4)
    assert cfg.epis["mascara"].extras["levantada_nao_conforme"] is True          # mantém os extras do config.yaml
    assert cfg.epis_ativos == ["mascara"]                                         # luvas: ainda não implementado


def test_rtsp_recebe_usuario_e_senha_do_env(tmp_path):
    ajustes = ajustes_de_teste(tmp_path, RTSP_USUARIO="operador", RTSP_SENHA="p@ss:1")
    assert origem_da_camera("rtsp", "rtsp://10.0.0.5:554/stream", ajustes) == \
        "rtsp://operador:p%40ss%3A1@10.0.0.5:554/stream"
    assert origem_da_camera("rtsp", "rtsp://outro:x@10.0.0.5/s", ajustes) == "rtsp://outro:x@10.0.0.5/s"
    assert origem_da_camera("webcam", "0", ajustes) == "0"
