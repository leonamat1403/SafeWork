"""Login, sessão, perfis e proteção CSRF (RF23, RF25, RNF05).

- Senha: bcrypt (custo 12), F2-D13. A senha nunca é guardada nem registrada no log.
- Sessão: cookie assinado com a SECRET_KEY (Starlette SessionMiddleware), HttpOnly e SameSite=Lax; expira após 8 h
  sem uso. O cookie guarda só o id do usuário, o token CSRF e a hora do último acesso.
- CSRF: toda rota que altera algo exige o token da sessão no cabeçalho X-CSRF-Token (ou no campo csrf_token de um
  formulário).
- Bloqueio: 5 senhas erradas seguidas para o mesmo login bloqueiam esse login por 5 minutos.
- 1º acesso: o ADMIN criado a partir do .env precisa trocar a senha antes de usar o sistema (F2-D9).
"""
from __future__ import annotations

import functools
import hmac
import logging
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Ajustes
from app.models import Auditoria, Usuario

log = logging.getLogger("epi_solda.acesso")

CUSTO_BCRYPT = 12
INATIVIDADE_MAX_S = 8 * 3600
TENTATIVAS_MAX = 5
BLOQUEIO_S = 5 * 60
SENHA_MIN = 8
SENHA_MAX_BYTES = 72          # limite do bcrypt
SENHA_PADRAO_ENV = "troque-no-primeiro-acesso"
METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}

# Aparece como "Authorize" na documentação /docs: cole ali o csrf_token devolvido pelo login
cabecalho_csrf = APIKeyHeader(name="X-CSRF-Token", auto_error=False, description="csrf_token devolvido pelo login")


# --------------------------------------------------------------------------------------------------------------
# Senhas
# --------------------------------------------------------------------------------------------------------------
def gerar_hash(senha: str) -> str:
    """Transforma a senha em hash bcrypt (com sal aleatório) para guardar no banco."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(CUSTO_BCRYPT)).decode("ascii")


def conferir_senha(senha: str, senha_hash: str) -> bool:
    """Diz se a senha digitada corresponde ao hash guardado (False também se o hash for inválido)."""
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("ascii"))
    except ValueError:   # hash corrompido ou senha longa demais
        return False


@functools.cache
def hash_ficticio() -> str:
    """Hash de uma senha qualquer, conferido quando o login não existe (mesmo tempo de resposta)."""
    return gerar_hash(secrets.token_urlsafe(16))


def problema_na_senha(senha: str, login: str) -> str | None:
    """Motivo para recusar uma senha nova, ou None se ela serve."""
    if len(senha) < SENHA_MIN:
        return f"A senha precisa ter pelo menos {SENHA_MIN} caracteres."
    # o limite de 72 bytes é do bcrypt e conta bytes, não caracteres (acentos ocupam 2)
    if len(senha.encode("utf-8")) > SENHA_MAX_BYTES:
        return f"A senha pode ter no máximo {SENHA_MAX_BYTES} bytes."
    if senha.strip().lower() in (login.strip().lower(), SENHA_PADRAO_ENV):
        return "A senha não pode ser igual ao login nem à senha inicial do .env."
    return None


class ControleTentativas:
    """Conta as senhas erradas recentes de cada login (em memória; zera quando o sistema reinicia)."""

    def __init__(self, maximo: int = TENTATIVAS_MAX, janela_s: float = BLOQUEIO_S) -> None:
        """Guarda o limite de falhas e a janela de tempo; cada login tem a sua fila de horários de falha."""
        self.maximo, self.janela_s = maximo, janela_s
        self._falhas: dict[str, deque[float]] = defaultdict(deque)
        self._trava = threading.Lock()

    def _limpar(self, login: str, agora: float) -> deque[float]:
        """Descarta as falhas mais velhas que a janela e devolve as que restam (chamar com a trava já tomada)."""
        falhas = self._falhas[login]
        while falhas and agora - falhas[0] > self.janela_s:
            falhas.popleft()
        return falhas

    def bloqueado(self, login: str, agora: float | None = None) -> bool:
        """True se o login já errou a senha vezes demais dentro da janela (o relógio é injetável para os testes)."""
        agora = time.monotonic() if agora is None else agora
        with self._trava:
            return len(self._limpar(login.lower(), agora)) >= self.maximo

    def registrar_falha(self, login: str, agora: float | None = None) -> None:
        """Anota mais uma senha errada para o login (maiúsculas e minúsculas contam como o mesmo login)."""
        agora = time.monotonic() if agora is None else agora
        with self._trava:
            self._limpar(login.lower(), agora).append(agora)

    def zerar(self, login: str) -> None:
        """Esquece as falhas do login (chamado quando ele acerta a senha)."""
        with self._trava:
            self._falhas.pop(login.lower(), None)


# --------------------------------------------------------------------------------------------------------------
# Usuário da sessão
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class UsuarioSessao:
    """Dados do usuário logado que as rotas precisam; é imutável e não carrega o hash da senha."""
    id: int
    login: str
    nome: str
    perfil: str
    deve_trocar_senha: bool

    @property
    def admin(self) -> bool:
        """True se o perfil é ADMIN (o outro perfil existente é SUPERVISOR)."""
        return self.perfil == "ADMIN"


def auditar(fabrica: sessionmaker[Session], usuario_id: int | None, acao: str, detalhes: dict | None = None) -> None:
    """Grava uma linha de auditoria (RF25)."""
    with fabrica() as sessao:
        sessao.add(Auditoria(usuario_id=usuario_id, acao=acao, detalhes=detalhes or {}))
        sessao.commit()


def iniciar_sessao(request: Request, usuario: Usuario) -> str:
    """Começa uma sessão nova (descarta a anterior, contra fixação de sessão) e devolve o token CSRF."""
    request.session.clear()
    token = secrets.token_urlsafe(32)
    request.session.update({"usuario_id": usuario.id, "csrf": token, "ultimo_acesso": time.time()})
    return token


def usuario_atual(request: Request) -> UsuarioSessao:
    """Dependência: o usuário logado. Sem login (ou sessão expirada, ou usuário desativado) -> 401."""
    sessao = request.session
    usuario_id = sessao.get("usuario_id")
    if usuario_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar.")
    # expira por inatividade; cada requisição válida renova o ultimo_acesso (mais abaixo)
    if time.time() - float(sessao.get("ultimo_acesso", 0)) > INATIVIDADE_MAX_S:
        sessao.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Faça login de novo.")
    with request.app.state.ctx.fabrica() as s:
        usuario = s.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        sessao.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário desativado. Fale com o administrador.")
    sessao["ultimo_acesso"] = time.time()
    return UsuarioSessao(usuario.id, usuario.login, usuario.nome, usuario.perfil, usuario.deve_trocar_senha)


def usuario_liberado(usuario: UsuarioSessao = Depends(usuario_atual)) -> UsuarioSessao:
    """Dependência: usuário logado que já trocou a senha inicial."""
    if usuario.deve_trocar_senha:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Troque a senha antes de continuar (POST /api/trocar-senha).")
    return usuario


def exigir_admin(usuario: UsuarioSessao = Depends(usuario_liberado)) -> UsuarioSessao:
    """Dependência: só ADMIN (configurações, calibração, usuários, pausar câmeras, excluir)."""
    if not usuario.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Somente o administrador pode fazer isso.")
    return usuario


async def exigir_csrf(request: Request, token_cabecalho: str | None = Depends(cabecalho_csrf)) -> None:
    """Dependência das rotas que alteram algo: o token CSRF enviado tem de ser o da sessão (RNF05)."""
    # GET/HEAD/OPTIONS não alteram nada, então não precisam de token
    if request.method in METODOS_SEGUROS:
        return
    token = token_cabecalho
    if not token and request.headers.get("content-type", "").startswith(
            ("application/x-www-form-urlencoded", "multipart/form-data")):
        token = (await request.form()).get("csrf_token")
    esperado = request.session.get("csrf")
    # compare_digest compara em tempo constante, para o token não vazar por diferença de tempo
    if not token or not esperado or not hmac.compare_digest(str(token), str(esperado)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Token CSRF ausente ou inválido.")


# --------------------------------------------------------------------------------------------------------------
# Primeiro acesso
# --------------------------------------------------------------------------------------------------------------
class ErroPrimeiroAcesso(RuntimeError):
    """Não há usuários e o .env não define o administrador inicial."""


def criar_admin_inicial(fabrica: sessionmaker[Session], ajustes: Ajustes) -> bool:
    """Cria o ADMIN do .env se ainda não houver nenhum usuário. Devolve True se criou."""
    with fabrica() as sessao:
        if sessao.scalars(select(Usuario).limit(1)).first() is not None:
            return False
        if not ajustes.admin_senha_inicial:
            raise ErroPrimeiroAcesso("Nenhum usuário cadastrado: defina ADMIN_LOGIN_INICIAL e ADMIN_SENHA_INICIAL "
                                     "no .env para criar o primeiro administrador.")
        sessao.add(Usuario(nome="Administrador", login=ajustes.admin_login_inicial,
                           senha_hash=gerar_hash(ajustes.admin_senha_inicial), perfil="ADMIN", deve_trocar_senha=True))
        sessao.commit()
    log.warning("Administrador inicial %r criado a partir do .env; a troca de senha é obrigatória no 1º acesso.",
                ajustes.admin_login_inicial)
    return True
