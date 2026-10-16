"""Login, logout, troca de senha e dados do usuário logado (RF23, RF25)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.auth import (UsuarioSessao, auditar, conferir_senha, exigir_csrf, gerar_hash, hash_ficticio,
                      iniciar_sessao, problema_na_senha, usuario_atual)
from app.models import Usuario

rotas = APIRouter(tags=["acesso"])


@rotas.post("/login")
def login(request: Request, login: str = Form(...), senha: str = Form(...)) -> dict:
    """Entra no sistema. Devolve o perfil e o csrf_token (enviado depois no cabeçalho X-CSRF-Token)."""
    ctx = request.app.state.ctx
    login = login.strip()
    if ctx.tentativas.bloqueado(login):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Muitas tentativas erradas. Aguarde 5 minutos e tente de novo.")
    with ctx.fabrica() as sessao:
        usuario = sessao.scalars(select(Usuario).where(func.lower(Usuario.login) == login.lower())).first()
    # Confere a senha mesmo quando o login não existe: o tempo de resposta não revela quais logins existem
    senha_ok = conferir_senha(senha, usuario.senha_hash if usuario else hash_ficticio())
    if usuario is None or not usuario.ativo or not senha_ok:
        ctx.tentativas.registrar_falha(login)
        # O texto digitado só vai para a auditoria se for o login de um usuário que existe: quem digita a senha no
        # campo "Usuário" por engano não deixa a senha gravada no banco (revisão LGPD, docs/revisao_lgpd.md)
        auditar(ctx.fabrica, usuario.id if usuario else None, "login_falhou",
                {"login": usuario.login} if usuario else {"login_desconhecido": True})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login ou senha incorretos.")
    ctx.tentativas.zerar(login)
    token = iniciar_sessao(request, usuario)
    auditar(ctx.fabrica, usuario.id, "login")
    return {"nome": usuario.nome, "login": usuario.login, "perfil": usuario.perfil,
            "deve_trocar_senha": usuario.deve_trocar_senha, "csrf_token": token}


@rotas.post("/logout", dependencies=[Depends(exigir_csrf)])
def logout(request: Request, usuario: UsuarioSessao = Depends(usuario_atual)) -> dict:
    auditar(request.app.state.ctx.fabrica, usuario.id, "logout")
    request.session.clear()
    return {"ok": True}


@rotas.get("/api/me")
def eu(request: Request, usuario: UsuarioSessao = Depends(usuario_atual)) -> dict:
    """Quem está logado (as telas usam para montar o menu e pegar o csrf_token)."""
    return {"id": usuario.id, "nome": usuario.nome, "login": usuario.login, "perfil": usuario.perfil,
            "deve_trocar_senha": usuario.deve_trocar_senha, "csrf_token": request.session.get("csrf")}


class TrocaSenha(BaseModel):
    senha_atual: str
    nova_senha: str


@rotas.post("/api/trocar-senha", dependencies=[Depends(exigir_csrf)])
def trocar_senha(dados: TrocaSenha, request: Request, usuario: UsuarioSessao = Depends(usuario_atual)) -> dict:
    """Troca a própria senha (obrigatória no 1º acesso do administrador inicial)."""
    ctx = request.app.state.ctx
    with ctx.fabrica() as sessao:
        registro = sessao.get(Usuario, usuario.id)
        if not conferir_senha(dados.senha_atual, registro.senha_hash):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "A senha atual está incorreta.")
        if problema := problema_na_senha(dados.nova_senha, registro.login):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, problema)
        if conferir_senha(dados.nova_senha, registro.senha_hash):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "A nova senha precisa ser diferente da atual.")
        registro.senha_hash = gerar_hash(dados.nova_senha)
        registro.deve_trocar_senha = False
        sessao.commit()
    auditar(ctx.fabrica, usuario.id, "gerenciar_usuario", {"acao": "trocar_propria_senha"})
    return {"ok": True}
