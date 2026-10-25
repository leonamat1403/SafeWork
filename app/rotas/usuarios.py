"""Usuários (T08, só ADMIN): listar, criar, desativar/reativar e redefinir senha. Tudo auditado (RF25).

Não existe "excluir usuário": desativar mantém o histórico de validações e da auditoria. O administrador não pode
desativar a si mesmo, e o sistema nunca fica sem nenhum administrador ativo.
"""
from __future__ import annotations

import re
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.auth import UsuarioSessao, auditar, exigir_admin, exigir_csrf, gerar_hash, problema_na_senha
from app.models import Usuario
from app.tempo import para_local

rotas = APIRouter(prefix="/api/usuarios", tags=["usuários"])
LOGIN_VALIDO = re.compile(r"^[A-Za-z0-9._-]{3,50}$")
# Senha temporária sem letras que se confundem (l, I, 1, O, 0), mostrada uma única vez na tela
ALFABETO_TEMPORARIA = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def usuario_json(u: Usuario, eu: int) -> dict:
    """Dados do usuário para as telas (nunca inclui o hash); 'voce' marca o próprio usuário logado."""
    return {"id": u.id, "nome": u.nome, "login": u.login, "perfil": u.perfil, "ativo": u.ativo,
            "deve_trocar_senha": u.deve_trocar_senha, "criado_em": para_local(u.criado_em).strftime("%d/%m/%Y"),
            "voce": u.id == eu}


@rotas.get("")
def listar(request: Request, admin: UsuarioSessao = Depends(exigir_admin)) -> list[dict]:
    """Lista todos os usuários (ativos primeiro, depois por nome). Só ADMIN."""
    with request.app.state.ctx.fabrica() as sessao:
        usuarios = sessao.scalars(select(Usuario).order_by(Usuario.ativo.desc(), Usuario.nome)).all()
    return [usuario_json(u, admin.id) for u in usuarios]


class NovoUsuario(BaseModel):
    """Corpo do pedido de criação de usuário."""
    nome: str
    login: str
    perfil: Literal["ADMIN", "SUPERVISOR"]
    senha_inicial: str


@rotas.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(exigir_csrf)])
def criar(dados: NovoUsuario, request: Request, admin: UsuarioSessao = Depends(exigir_admin)) -> dict:
    """Cria o usuário; ele precisa trocar a senha inicial no primeiro acesso."""
    ctx = request.app.state.ctx
    nome, login = dados.nome.strip(), dados.login.strip()
    if not 2 <= len(nome) <= 100:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Informe o nome (de 2 a 100 caracteres).")
    if not LOGIN_VALIDO.match(login):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "O login deve ter de 3 a 50 caracteres: letras sem acento, números, ponto, hífen ou _.")
    if problema := problema_na_senha(dados.senha_inicial, login):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problema)
    with ctx.fabrica() as sessao:
        if sessao.scalar(select(Usuario.id).where(func.lower(Usuario.login) == login.lower())) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Já existe um usuário com o login {login}.")
        usuario = Usuario(nome=nome, login=login, perfil=dados.perfil, senha_hash=gerar_hash(dados.senha_inicial),
                          deve_trocar_senha=True)
        sessao.add(usuario)
        sessao.commit()
    auditar(ctx.fabrica, admin.id, "gerenciar_usuario", {"acao": "criar", "login": login, "perfil": dados.perfil})
    return usuario_json(usuario, admin.id)


def _alvo(sessao, usuario_id: int) -> Usuario:
    """Busca o usuário que sofrerá a ação ou responde 404."""
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    return usuario


@rotas.post("/{usuario_id}/desativar", dependencies=[Depends(exigir_csrf)])
def desativar(usuario_id: int, request: Request, admin: UsuarioSessao = Depends(exigir_admin)) -> dict:
    """Desativa: a pessoa não entra mais (e uma sessão aberta cai na próxima ação)."""
    ctx = request.app.state.ctx
    if usuario_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Você não pode desativar o seu próprio usuário.")
    with ctx.fabrica() as sessao:
        usuario = _alvo(sessao, usuario_id)
        if usuario.perfil == "ADMIN" and usuario.ativo:
            admins_ativos = sessao.scalar(select(func.count()).select_from(Usuario)
                                          .where(Usuario.perfil == "ADMIN", Usuario.ativo.is_(True)))
            # trava para o sistema nunca ficar sem quem o administre
            if admins_ativos <= 1:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "O sistema precisa de pelo menos um administrador ativo.")
        usuario.ativo = False
        sessao.commit()
    auditar(ctx.fabrica, admin.id, "gerenciar_usuario", {"acao": "desativar", "login": usuario.login})
    return usuario_json(usuario, admin.id)


@rotas.post("/{usuario_id}/reativar", dependencies=[Depends(exigir_csrf)])
def reativar(usuario_id: int, request: Request, admin: UsuarioSessao = Depends(exigir_admin)) -> dict:
    """Reativa um usuário desativado, com a mesma senha de antes. Só ADMIN."""
    ctx = request.app.state.ctx
    with ctx.fabrica() as sessao:
        usuario = _alvo(sessao, usuario_id)
        usuario.ativo = True
        sessao.commit()
    auditar(ctx.fabrica, admin.id, "gerenciar_usuario", {"acao": "reativar", "login": usuario.login})
    return usuario_json(usuario, admin.id)


@rotas.post("/{usuario_id}/senha", dependencies=[Depends(exigir_csrf)])
def redefinir_senha(usuario_id: int, request: Request, admin: UsuarioSessao = Depends(exigir_admin)) -> dict:
    """Gera uma senha temporária (mostrada uma única vez); a pessoa troca no próximo acesso."""
    ctx = request.app.state.ctx
    # secrets (e não random): a senha temporária precisa ser imprevisível
    temporaria = "".join(secrets.choice(ALFABETO_TEMPORARIA) for _ in range(10))
    with ctx.fabrica() as sessao:
        usuario = _alvo(sessao, usuario_id)
        usuario.senha_hash = gerar_hash(temporaria)
        usuario.deve_trocar_senha = True
        sessao.commit()
    auditar(ctx.fabrica, admin.id, "gerenciar_usuario", {"acao": "redefinir_senha", "login": usuario.login})
    return {**usuario_json(usuario, admin.id), "senha_temporaria": temporaria}
