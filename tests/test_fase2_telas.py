"""[FASE 2] Telas da Etapa 2.4 (login, troca de senha, Ao vivo, Analisar arquivo, Ocorrências, Usuários) e as APIs
novas: gestão de usuários, resumo das ocorrências e o "cordão do turno" no status ao vivo.

Mesma câmera e mesmo detector SIMULADOS do test_fase2_web.py. Nada toca a pasta data/ real.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import VERSAO
from app.models import Auditoria, Usuario
from app.paginas import destino_seguro
from app.rotas.usuarios import ALFABETO_TEMPORARIA
from app.stream import PASSO_CORDAO_S, TrabalhadorCamera, codigo_do_trecho
from src.compliance import avaliar_frame
from src.pipeline import ResultadoFrame
from tests.auxiliares import ROSTO_DESCOBERTO, ROSTO_DETECTADO, criar_pessoa
from tests.test_fase2_web import (admin_pronto, bcrypt_rapido, cliente, criar_supervisor, ctx, entrar,  # noqa: F401
                                  esperar, registrar_ocorrencias)

UTC = timezone.utc
PAGINAS = ["/ao-vivo", "/upload", "/ocorrencias", "/usuarios", "/calibracao", "/dashboard", "/configuracoes"]


class Referencias(HTMLParser):
    """Coleta os scripts, estilos e imagens que a página carrega, os scripts sem arquivo e os atributos style."""

    def __init__(self) -> None:
        """Zera os contadores e a lista de arquivos carregados."""
        super().__init__()
        self.arquivos: list[str] = []
        self.scripts_inline = 0
        self.atributos_style = 0
        self.handlers_inline = 0

    def handle_starttag(self, tag, attrs):
        """Registra arquivos carregados, scripts sem arquivo, atributos style e manipuladores on*."""
        atributos = dict(attrs)
        if tag == "script":
            if atributos.get("src"):
                self.arquivos.append(atributos["src"])
            else:
                self.scripts_inline += 1
        if tag == "link" and atributos.get("href", "").startswith("/static/"):
            self.arquivos.append(atributos["href"])
        if "style" in atributos:
            self.atributos_style += 1
        self.handlers_inline += sum(1 for nome in atributos if nome.startswith("on"))


def analisar(html: str) -> Referencias:
    """Lê o HTML e devolve o que a página carrega e usa dentro dele."""
    leitor = Referencias()
    leitor.feed(html)
    return leitor


# --------------------------------------------------------------------------------------------------- redirecionamentos
@pytest.mark.parametrize("proximo, esperado", [
    ("/ocorrencias?validacao=PENDENTE", "/ocorrencias?validacao=PENDENTE"),
    ("/upload", "/upload"),
    ("//outro-site.com", "/ao-vivo"),
    ("/\\outro-site.com", "/ao-vivo"),
    ("https://outro-site.com", "/ao-vivo"),
    ("/api/me", "/ao-vivo"),
    ("", "/ao-vivo"),
    (None, "/ao-vivo"),
])
def test_destino_depois_do_login_so_dentro_do_sistema(proximo, esperado):
    """Depois do login só se aceita destino dentro do sistema; o resto vai para Ao vivo."""
    assert destino_seguro(proximo) == esperado


@pytest.mark.parametrize("pagina", PAGINAS + ["/trocar-senha"])
def test_paginas_sem_login_levam_ao_login(cliente, pagina):
    """Página aberta sem login redireciona para o login."""
    r = cliente.get(pagina, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login?proximo=")


def test_volta_para_a_pagina_pedida_depois_do_login(cliente):
    """O login lembra a página pedida e leva de volta a ela."""
    r = cliente.get("/ocorrencias?validacao=PENDENTE", follow_redirects=False)
    assert r.headers["location"] == "/login?proximo=/ocorrencias%3Fvalidacao%3DPENDENTE"
    pagina = cliente.get(r.headers["location"])
    assert pagina.status_code == 200 and 'data-proximo="/ocorrencias?validacao=PENDENTE"' in pagina.text
    assert cliente.get("/", follow_redirects=False).headers["location"] == "/ao-vivo"


def test_login_com_destino_externo_vai_para_ao_vivo(cliente):
    """Login com destino em outro site ignora o destino e vai para Ao vivo."""
    pagina = cliente.get("/login?proximo=//outro-site.com")
    assert 'data-proximo="/ao-vivo"' in pagina.text and "outro-site" not in pagina.text


def test_troca_de_senha_obrigatoria_antes_das_telas(cliente):
    """Com senha ainda inicial, todas as telas levam à troca de senha."""
    entrar(cliente)   # admin inicial, ainda com a senha do .env
    for pagina in PAGINAS:
        r = cliente.get(pagina, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/trocar-senha"
    troca = cliente.get("/trocar-senha")
    assert troca.status_code == 200 and "Defina uma senha nova" in troca.text and "Voltar sem trocar" not in troca.text


def test_quem_ja_entrou_e_abre_o_login_vai_direto(cliente):
    """Quem já está logado e abre o login é levado direto ao destino."""
    admin_pronto(cliente)
    r = cliente.get("/login?proximo=/upload", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/upload"
    assert "Voltar sem trocar" in cliente.get("/trocar-senha").text


# --------------------------------------------------------------------------------------------------- conteúdo das telas
def test_ao_vivo_mostra_o_posto_e_o_token_csrf(cliente):
    """A tela Ao vivo mostra o posto, o token CSRF e os botões do administrador."""
    token = admin_pronto(cliente)
    html = cliente.get("/ao-vivo").text
    assert f'<meta name="csrf-token" content="{token}">' in html
    assert 'data-camera-id="1"' in html and "Webcam 0" in html and 'id="cordao"' in html
    assert 'id="botao-pausar"' in html                          # só o ADMIN vê "Pausar posto"
    assert 'href="/usuarios"' in html and f"v{VERSAO}" in html
    assert cliente.get("/ao-vivo?camera_id=99").status_code == 200   # posto inexistente: mostra o primeiro


def test_supervisor_nao_ve_administracao(cliente):
    """O supervisor não vê o botão de pausar nem a área de usuários."""
    token = admin_pronto(cliente)
    criar_supervisor(cliente)
    cliente.post("/logout", headers={"X-CSRF-Token": token})
    entrar(cliente, "sup", "senha-supervisor-1")
    html = cliente.get("/ao-vivo").text
    assert 'id="botao-pausar"' not in html and 'href="/usuarios"' not in html and "Administração" not in html
    r = cliente.get("/usuarios")
    assert r.status_code == 403 and "só para administradores" in r.text


def test_telas_de_upload_e_ocorrencias(cliente):
    """As telas de upload, ocorrências e usuários trazem os elementos esperados."""
    admin_pronto(cliente)
    upload = cliente.get("/upload").text
    assert 'data-tamanho-max-mb="200"' in upload and 'accept=".jpg,.jpeg,.png,.mp4' in upload
    ocorrencias = cliente.get("/ocorrencias").text
    assert re.search(r'<a[^>]*id="exportar"[^>]*href="/api/ocorrencias/exportar.csv"', ocorrencias)   # RD10
    for turno in ("1", "2", "3"):
        assert f'<option value="{turno}">' in ocorrencias
    assert 'id="botao-excluir"' in ocorrencias                                    # ADMIN exclui
    assert "Novo usuário" in cliente.get("/usuarios").text


@pytest.mark.parametrize("pagina", ["/login"] + PAGINAS + ["/trocar-senha"])
def test_paginas_seguem_a_politica_de_conteudo(cliente, pagina):
    """Sem scripts dentro do HTML, sem atributos style/on*: a CSP bloqueia tudo o que não vem de /static."""
    if pagina != "/login":
        admin_pronto(cliente)
    r = cliente.get(pagina)
    assert r.status_code == 200
    csp = r.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe-inline" not in csp
    leitor = analisar(r.text)
    assert leitor.scripts_inline == 0 and leitor.atributos_style == 0 and leitor.handlers_inline == 0
    for arquivo in leitor.arquivos:                       # tudo o que a página carrega existe e é local
        assert arquivo.startswith("/static/"), arquivo
        assert cliente.get(arquivo).status_code == 200, arquivo


def test_api_nao_recebe_csp_de_pagina(cliente):
    """As respostas da API não levam a política de conteúdo de páginas."""
    admin_pronto(cliente)
    assert "Content-Security-Policy" not in cliente.get("/api/me").headers


def test_arquivos_estaticos_sem_login_e_sem_internet(cliente):
    """Bootstrap, ícones e fontes vêm do próprio servidor: as telas funcionam sem internet."""
    for arquivo in ("/static/js/app.js", "/static/css/app.css", "/static/vendor/bootstrap/bootstrap.min.css",
                    "/static/vendor/bootstrap/bootstrap.bundle.min.js", "/static/img/icone.svg",
                    "/static/vendor/bootstrap-icons/bootstrap-icons.min.css",
                    "/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2",
                    "/static/vendor/fontes/atkinson-hyperlegible-400.woff2"):
        assert cliente.get(arquivo).status_code == 200, arquivo
    css = cliente.get("/static/css/app.css").text + cliente.get("/static/vendor/bootstrap-icons/bootstrap-icons.min.css").text
    assert not re.search(r"url\(\s*['\"]?(https?:)?//", css) and "@import" not in css


# --------------------------------------------------------------------------------------------------- usuários (T08)
def criar_usuario(c, token, **dados):
    """Cria um usuário pela API com dados padrão que podem ser trocados."""
    corpo = {"nome": "Maria Souza", "login": "maria", "perfil": "SUPERVISOR", "senha_inicial": "inicial-maria-1", **dados}
    return c.post("/api/usuarios", json=corpo, headers={"X-CSRF-Token": token})


def test_admin_cria_usuario_que_troca_a_senha_no_primeiro_acesso(cliente):
    """O administrador cria usuário, que precisa trocar a senha no primeiro acesso."""
    token = admin_pronto(cliente)
    r = criar_usuario(cliente, token)
    assert r.status_code == 201, r.text
    novo = r.json()
    assert novo["perfil"] == "SUPERVISOR" and novo["ativo"] and novo["deve_trocar_senha"] and not novo["voce"]
    lista = cliente.get("/api/usuarios").json()
    assert [u["login"] for u in lista] == ["admin", "maria"] and lista[0]["voce"]
    cliente.post("/logout", headers={"X-CSRF-Token": token})
    entrar(cliente, "MARIA", "inicial-maria-1")        # login sem diferença de maiúsculas
    assert cliente.get("/ao-vivo", follow_redirects=False).headers["location"] == "/trocar-senha"


@pytest.mark.parametrize("dados, codigo, trecho", [
    ({"login": "Maria"}, 409, "Já existe"),
    ({"login": "ma ria"}, 400, "login"),
    ({"login": "jo"}, 400, "login"),
    ({"nome": " "}, 400, "nome"),
    ({"senha_inicial": "curta"}, 400, "8 caracteres"),
    ({"login": "joana.silva", "senha_inicial": "joana.silva"}, 400, "igual ao login"),
    ({"perfil": "DONO"}, 422, ""),
])
def test_criar_usuario_recusa_dados_ruins(cliente, dados, codigo, trecho):
    """Criar usuário recusa login repetido ou inválido, nome vazio, senha fraca e perfil desconhecido."""
    token = admin_pronto(cliente)
    assert criar_usuario(cliente, token).status_code == 201
    r = criar_usuario(cliente, token, **dados)
    assert r.status_code == codigo and trecho in str(r.json()["detail"])


def test_gestao_de_usuarios_so_admin_e_com_csrf(cliente):
    """Gerir usuários exige ser administrador e ter o token CSRF certo."""
    token = admin_pronto(cliente)
    assert criar_usuario(cliente, "token-errado").status_code == 403
    criar_supervisor(cliente)
    cliente.post("/logout", headers={"X-CSRF-Token": token})
    token_sup = entrar(cliente, "sup", "senha-supervisor-1")
    assert cliente.get("/api/usuarios").status_code == 403
    assert criar_usuario(cliente, token_sup).status_code == 403
    assert cliente.post("/api/usuarios/1/senha", headers={"X-CSRF-Token": token_sup}).status_code == 403


def test_desativar_e_reativar(cliente):
    """O administrador desativa e reativa usuários, mas não a si mesmo."""
    token = admin_pronto(cliente)
    maria = criar_usuario(cliente, token).json()
    eu = cliente.get("/api/me").json()["id"]
    r = cliente.post(f"/api/usuarios/{eu}/desativar", headers={"X-CSRF-Token": token})
    assert r.status_code == 400 and "próprio" in r.json()["detail"]
    assert cliente.post("/api/usuarios/999/desativar", headers={"X-CSRF-Token": token}).status_code == 404

    assert cliente.post(f"/api/usuarios/{maria['id']}/desativar", headers={"X-CSRF-Token": token}).json()["ativo"] is False
    assert cliente.post("/login", data={"login": "maria", "senha": "inicial-maria-1"}).status_code == 401
    assert cliente.get("/api/me").status_code == 200                   # o admin continua dentro
    assert cliente.post(f"/api/usuarios/{maria['id']}/reativar", headers={"X-CSRF-Token": token}).json()["ativo"] is True
    cliente.post("/logout", headers={"X-CSRF-Token": token})
    entrar(cliente, "maria", "inicial-maria-1")


def test_sessao_aberta_cai_quando_o_usuario_e_desativado(cliente):
    """A sessão aberta de um usuário cai quando ele é desativado."""
    token = admin_pronto(cliente)
    criar_usuario(cliente, token)
    maria = TestClient(cliente.app)            # mesma aplicação, outro navegador (outro cookie)
    entrar(maria, "maria", "inicial-maria-1")
    assert maria.get("/api/me").status_code == 200
    with ctx(cliente).fabrica() as s:
        id_maria = s.scalar(select(Usuario.id).where(Usuario.login == "maria"))
    cliente.post(f"/api/usuarios/{id_maria}/desativar", headers={"X-CSRF-Token": token})
    assert maria.get("/api/me").status_code == 401
    assert maria.get("/ao-vivo", follow_redirects=False).headers["location"].startswith("/login")


def test_sempre_sobra_um_administrador_ativo(cliente):
    """Nunca se desativa o último administrador ativo."""
    token = admin_pronto(cliente)
    outro = criar_usuario(cliente, token, login="chefe", perfil="ADMIN").json()
    assert cliente.post(f"/api/usuarios/{outro['id']}/desativar", headers={"X-CSRF-Token": token}).status_code == 200
    with ctx(cliente).fabrica() as s:
        assert s.scalar(select(func.count()).select_from(Usuario)
                        .where(Usuario.perfil == "ADMIN", Usuario.ativo.is_(True))) == 1
    eu = cliente.get("/api/me").json()["id"]
    assert cliente.post(f"/api/usuarios/{eu}/desativar", headers={"X-CSRF-Token": token}).status_code == 400


def test_redefinir_senha_gera_temporaria_mostrada_uma_vez(cliente):
    """Redefinir a senha gera uma temporária mostrada uma só vez e sem guardá-la na auditoria."""
    token = admin_pronto(cliente)
    maria = criar_usuario(cliente, token).json()
    r = cliente.post(f"/api/usuarios/{maria['id']}/senha", headers={"X-CSRF-Token": token})
    temporaria = r.json()["senha_temporaria"]
    assert len(temporaria) == 10 and set(temporaria) <= set(ALFABETO_TEMPORARIA)
    assert "senha_temporaria" not in str(cliente.get("/api/usuarios").json())
    cliente.post("/logout", headers={"X-CSRF-Token": token})
    assert cliente.post("/login", data={"login": "maria", "senha": "inicial-maria-1"}).status_code == 401
    assert cliente.post("/login", data={"login": "maria", "senha": temporaria}).json()["deve_trocar_senha"] is True
    with ctx(cliente).fabrica() as s:
        acoes = [a.detalhes["acao"] for a in s.scalars(select(Auditoria).where(Auditoria.acao == "gerenciar_usuario"))]
    assert acoes.count("criar") == 1 and acoes.count("redefinir_senha") == 1
    assert temporaria not in str(acoes)


# --------------------------------------------------------------------------------------------------- ocorrências (T04)
def test_resumo_do_periodo_ignora_o_filtro_de_validacao(cliente):
    """O resumo do período conta tudo, sem aplicar o filtro de validação, e o contador de pendentes confere."""
    token = admin_pronto(cliente)
    uuids = registrar_ocorrencias(cliente, 4, datetime(2026, 10, 10, 12, 0, tzinfo=UTC))
    cabecalho = {"X-CSRF-Token": token}
    cliente.post(f"/api/ocorrencias/{uuids[0]}/validacao", json={"validacao": "CONFIRMADA"}, headers=cabecalho)
    cliente.post(f"/api/ocorrencias/{uuids[1]}/validacao", json={"validacao": "FALSO_POSITIVO"}, headers=cabecalho)
    dados = cliente.get("/api/ocorrencias?inicio=2026-10-10&fim=2026-10-10&validacao=PENDENTE").json()
    assert dados["total"] == 2 and len(dados["itens"]) == 2
    assert dados["resumo"] == {"total": 4, "pendentes": 2, "confirmadas": 1, "falsos_positivos": 1}
    assert cliente.get("/api/ocorrencias?inicio=2026-10-11").json()["resumo"]["total"] == 0
    assert cliente.get("/api/ocorrencias/resumo").json() == {"pendentes": 2}
    assert re.search(r'id="contador-pendentes"[^>]*>2<', cliente.get("/ocorrencias").text)


def test_resumo_de_pendentes_exige_login(cliente):
    """O resumo de pendentes responde 401 sem login."""
    assert cliente.get("/api/ocorrencias/resumo").status_code == 401


# --------------------------------------------------------------------------------------------------- cordão do turno (T02)
def resultado(com_pessoa: bool, saturado: bool = False, config=None):
    """Monta um resultado de quadro com ou sem a pessoa sem máscara, e com ou sem arco saturado."""
    avaliacoes = avaliar_frame([criar_pessoa(ROSTO_DESCOBERTO)], [], config, rostos=[ROSTO_DETECTADO]) if com_pessoa else []
    return ResultadoFrame(avaliacoes, [], saturado, 0.4 if saturado else 0.0, [ROSTO_DETECTADO] if com_pessoa else [])


@pytest.mark.parametrize("quadros, codigo", [
    (None, "-"),            # câmera parada / pausada / só arco
    ([5, 0, 0, 0], "V"),    # ninguém
    ([0, 0, 0, 3], "N"),
    ([0, 7, 0, 1], "C"),    # um quadro errado no meio de 7 conformes NÃO pinta o trecho de vermelho
    ([0, 5, 0, 5], "N"),    # metade dos quadros com a falta: vermelho
    ([0, 4, 3, 3], "I"),    # mistura sem maioria: incerto
    ([10, 0, 0, 2], "V"),   # gente em menos de 1/4 dos quadros: conta como vazio
    ([3, 0, 0, 1], "N"),    # 1/4 exato já conta
])
def test_codigo_do_trecho_e_o_estado_predominante(quadros, codigo):
    """O código do trecho do cordão reflete o estado predominante dos quadros."""
    assert codigo_do_trecho(quadros) == codigo


def test_cordao_conta_os_quadros_de_cada_trecho(config):
    """O cordão conta os quadros de cada trecho e ignora os de arco de solda."""
    trabalhador = TrabalhadorCamera(9, "Teste", "0", config, None, None, None, None, None)
    t0 = 1_000_000.0                                        # início de um trecho de 10 s
    trabalhador.marcar_cordao(resultado(False), t0)          # ninguém
    trabalhador.marcar_cordao(resultado(True, config=config), t0 + 3)   # sem máscara
    trabalhador.marcar_cordao(resultado(False), t0 + 6)
    trabalhador.marcar_cordao(resultado(False), t0 + PASSO_CORDAO_S)
    trabalhador.marcar_cordao(resultado(True, saturado=True, config=config), t0 + 2 * PASSO_CORDAO_S)  # arco: ignorado
    trabalhador.marcar_cordao(resultado(False), t0 + 3 * PASSO_CORDAO_S + 1)
    assert trabalhador.cordao(t0, t0 + 3 * PASSO_CORDAO_S + 5) == "NV-V"
    assert trabalhador.cordao(t0 - 2 * PASSO_CORDAO_S, t0 - 1) == "--"   # antes de ligar: câmera parada


def test_status_ao_vivo_traz_o_cordao_do_turno_e_os_pinos(cliente):
    """O status ao vivo traz o cordão do turno e os pinos das ocorrências do turno atual."""
    admin_pronto(cliente)
    cordao = esperar(lambda: "N" in (c := cliente.get("/api/status").json()["cordao"])["trechos"] and c)
    inicio, fim = datetime.fromisoformat(cordao["inicio"]), datetime.fromisoformat(cordao["fim"])
    assert cordao["passo_s"] == PASSO_CORDAO_S and cordao["turno"] in ("1", "2", "3")
    assert fim - inicio == timedelta(hours=8) and re.fullmatch(r"\d\d:\d\d", cordao["inicio_local"])
    agora = datetime.now(UTC)
    assert abs(len(cordao["trechos"]) - ((agora - inicio).total_seconds() // PASSO_CORDAO_S + 1)) <= 1
    assert set(cordao["trechos"]) <= set("CINV-")

    meio = inicio + (agora - inicio) / 2
    uuid = registrar_ocorrencias(cliente, 1, meio)[0]
    antes = registrar_ocorrencias(cliente, 1, inicio - timedelta(minutes=1))[0]   # turno anterior: fora
    pinos = cliente.get("/api/status").json()["cordao"]["pinos"]
    pino = next(p for p in pinos if p["uuid"] == uuid)
    assert abs(pino["segundos"] - (meio - inicio).total_seconds()) <= 1 and pino["epis_faltantes"] == ["mascara"]
    assert antes not in [p["uuid"] for p in pinos]
