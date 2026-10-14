"""Páginas HTML (Jinja2) da Etapa 2.4: login, troca de senha, Ao vivo (T02), Analisar arquivo (T03), Ocorrências (T04)
e Usuários (T08). Os dados vêm da API (JavaScript em static/js); as páginas só montam o esqueleto.

Sem login, qualquer página leva ao /login (e volta para onde estava depois de entrar). A API continua respondendo
401 (docs/wireframes_fase2.md, seção 5).
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app import VERSAO
from app.auth import UsuarioSessao, usuario_atual
from app.models import Camera, Ocorrencia

rotas = APIRouter(include_in_schema=False)
PASTA_APP = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(PASTA_APP / "templates"))


def versao_estaticos() -> str:
    """Muda quando algum CSS/JS do sistema muda: vai no endereço (?v=) para o navegador não usar o arquivo velho do cache."""
    arquivos = [*PASTA_APP.glob("static/css/*.css"), *PASTA_APP.glob("static/js/*.js")]
    return format(int(max((a.stat().st_mtime for a in arquivos), default=0)), "x")


templates.env.globals["v"] = versao_estaticos()


def destino_seguro(proximo: str | None) -> str:
    """Só aceita voltar para uma página deste sistema (evita redirecionar para outro site)."""
    if proximo and proximo.startswith("/") and not proximo.startswith(("//", "/\\")) and not proximo.startswith("/api"):
        return proximo
    return "/ao-vivo"


def _usuario_ou_redirecionar(request: Request, liberado: bool = True) -> UsuarioSessao | RedirectResponse:
    """O usuário logado, ou o redirecionamento para o login / para a troca obrigatória de senha."""
    try:
        usuario = usuario_atual(request)
    except HTTPException as erro:
        caminho = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        expirou = "&expirou=1" if "expirada" in str(erro.detail) else ""
        return RedirectResponse(f"/login?proximo={quote(caminho)}{expirou}", status_code=303)
    if liberado and usuario.deve_trocar_senha:
        return RedirectResponse("/trocar-senha", status_code=303)
    return usuario


def _pagina(request: Request, modelo: str, usuario: UsuarioSessao, ativa: str, **extra) -> HTMLResponse:
    ctx = request.app.state.ctx
    with ctx.fabrica() as sessao:
        cameras = [{"id": i, "nome": n} for i, n in sessao.execute(
            select(Camera.id, Camera.nome_posto).where(Camera.ativa.is_(True)).order_by(Camera.id)).all()]
        pendentes = sessao.scalar(select(func.count()).select_from(Ocorrencia)
                                  .where(Ocorrencia.validacao == "PENDENTE"))
    return templates.TemplateResponse(request, modelo, {
        "usuario": usuario, "csrf": request.session.get("csrf", ""), "versao": VERSAO, "ativa": ativa,
        "cameras": cameras, "pendentes": pendentes, **extra})


@rotas.get("/")
def inicio() -> RedirectResponse:
    return RedirectResponse("/ao-vivo", status_code=303)


@rotas.get("/login")
def pagina_login(request: Request, proximo: str | None = None, expirou: int = 0) -> Response:
    if request.session.get("usuario_id"):
        try:
            usuario_atual(request)
            return RedirectResponse(destino_seguro(proximo), status_code=303)
        except HTTPException:
            pass
    return templates.TemplateResponse(request, "login.html", {
        "versao": VERSAO, "proximo": destino_seguro(proximo), "expirou": bool(expirou)})


@rotas.get("/trocar-senha")
def pagina_trocar_senha(request: Request) -> Response:
    usuario = _usuario_ou_redirecionar(request, liberado=False)
    if isinstance(usuario, RedirectResponse):
        return usuario
    return templates.TemplateResponse(request, "trocar_senha.html", {
        "usuario": usuario, "csrf": request.session.get("csrf", ""), "versao": VERSAO})


@rotas.get("/ao-vivo")
def pagina_ao_vivo(request: Request, camera_id: int | None = None) -> Response:
    usuario = _usuario_ou_redirecionar(request)
    if isinstance(usuario, RedirectResponse):
        return usuario
    ids = request.app.state.ctx.cameras.ids()
    selecionada = camera_id if camera_id in ids else (ids[0] if ids else None)
    return _pagina(request, "ao_vivo.html", usuario, "ao-vivo", camera_id=selecionada)


@rotas.get("/upload")
def pagina_upload(request: Request) -> Response:
    usuario = _usuario_ou_redirecionar(request)
    if isinstance(usuario, RedirectResponse):
        return usuario
    return _pagina(request, "upload.html", usuario, "upload",
                   tamanho_max_mb=request.app.state.ctx.ajustes.upload_tamanho_max_mb)


@rotas.get("/ocorrencias")
def pagina_ocorrencias(request: Request) -> Response:
    usuario = _usuario_ou_redirecionar(request)
    if isinstance(usuario, RedirectResponse):
        return usuario
    return _pagina(request, "ocorrencias.html", usuario, "ocorrencias",
                   turnos=sorted(request.app.state.ctx.ajustes.turnos))


@rotas.get("/usuarios")
def pagina_usuarios(request: Request) -> Response:
    usuario = _usuario_ou_redirecionar(request)
    if isinstance(usuario, RedirectResponse):
        return usuario
    if not usuario.admin:
        resposta = _pagina(request, "erro.html", usuario, "", titulo="Página só para administradores",
                           mensagem="A gestão de usuários é feita pelo administrador do sistema.")
        resposta.status_code = 403
        return resposta
    return _pagina(request, "usuarios.html", usuario, "usuarios")
