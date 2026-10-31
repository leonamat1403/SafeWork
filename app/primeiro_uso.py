"""Primeira configuração do sistema web:  .venv\\Scripts\\python -m app --configurar

Cria o arquivo .env a partir do .env.example, gera a SECRET_KEY (a chave que assina o login) e pede a senha inicial
do administrador no terminal, sem mostrá-la. Nenhum valor aparece na tela nem sai do computador. Se o .env já
existir, só completa o que estiver vazio ou com o valor de exemplo; o resto do arquivo não muda.
"""
from __future__ import annotations

import re
import secrets
import sys
from collections.abc import Callable
from getpass import getpass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.auth import SENHA_PADRAO_ENV, gerar_hash, problema_na_senha
from app.config import RAIZ, Ajustes
from app.models import Usuario

# Valores que vêm no .env.example e que precisam ser trocados antes do uso real.
VALORES_DE_EXEMPLO = {"SECRET_KEY": "troque-esta-chave", "ADMIN_SENHA_INICIAL": SENHA_PADRAO_ENV}


def _valor(texto: str, chave: str) -> str | None:
    """Valor de `chave` no texto do .env, sem espaços nem aspas nas pontas; None se a chave não existir."""
    achado = re.search(rf"^{chave}=(.*)$", texto, re.MULTILINE)
    return achado.group(1).strip().strip("'\"") if achado else None


def _definir(texto: str, chave: str, valor: str) -> str:
    """Troca a linha `chave=...` pelo novo valor ou, se ela não existir, acrescenta ao fim do texto."""
    linha = f"{chave}={valor}"
    if re.search(rf"^{chave}=", texto, re.MULTILINE):
        # A troca é feita por uma função (lambda) para o re.sub não interpretar barras invertidas da senha.
        return re.sub(rf"^{chave}=.*$", lambda _: linha, texto, count=1, flags=re.MULTILINE)
    return texto.rstrip("\n") + f"\n{linha}\n"


def _entre_aspas(valor: str) -> str:
    """Valor protegido para o .env: espaços, # e aspas na senha não quebram a leitura."""
    if "'" not in valor:
        return f"'{valor}'"
    return '"' + valor.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _faltando(texto: str, chave: str) -> bool:
    """True se a chave está vazia ou ainda com o valor de exemplo do .env.example."""
    valor = _valor(texto, chave)
    return not valor or valor == VALORES_DE_EXEMPLO[chave]


def configurar_env(env: Path, exemplo: Path, pedir_senha: Callable[[str], str]) -> list[str]:
    """Cria ou completa o .env. Devolve o que foi feito (sem os valores)."""
    feitos = []
    if env.exists():
        texto = env.read_text(encoding="utf-8")
    else:
        texto = exemplo.read_text(encoding="utf-8")
        feitos.append("arquivo .env criado a partir do .env.example")
    if _faltando(texto, "SECRET_KEY"):
        texto = _definir(texto, "SECRET_KEY", secrets.token_hex(32))
        feitos.append("SECRET_KEY gerada (64 caracteres aleatórios)")
    if _faltando(texto, "ADMIN_SENHA_INICIAL"):
        login = _valor(texto, "ADMIN_LOGIN_INICIAL") or "admin"
        texto = _definir(texto, "ADMIN_SENHA_INICIAL", _entre_aspas(pedir_senha(login)))
        feitos.append(f"senha inicial do administrador '{login}' definida")
    if feitos:
        env.write_text(texto, encoding="utf-8")
    return feitos


def redefinir_senha_admin(fabrica: sessionmaker[Session], login: str, senha: str) -> bool:
    """Define uma nova senha para o administrador `login` (esquecimento da senha). Reativa o usuário, exige a troca da
    senha no próximo acesso e não mexe em mais nada do banco. Devolve False se o usuário não existe."""
    with fabrica() as sessao:
        usuario = sessao.scalars(select(Usuario).where(Usuario.login == login)).first()
        if usuario is None:
            return False
        usuario.senha_hash = gerar_hash(senha)
        usuario.ativo = True
        usuario.deve_trocar_senha = True
        sessao.commit()
    return True


def pedir_senha_no_terminal(login: str) -> str:
    """Pergunta a senha duas vezes; o que é digitado não aparece na tela."""
    while True:
        senha = getpass(f"Senha inicial do administrador '{login}' (mínimo 8 caracteres; ela será trocada no "
                        "primeiro acesso): ")
        if problema := problema_na_senha(senha, login):
            print(f"  {problema} Tente de novo.")
            continue
        if getpass("Repita a senha: ") != senha:
            print("  As duas senhas não são iguais. Tente de novo.")
            continue
        return senha


def problema_para_iniciar(ajustes: Ajustes, env: Path) -> str | None:
    """Explicação (em vez de um erro técnico) quando falta configurar algo antes de ligar o sistema."""
    comando = r".venv\Scripts\python -m app --configurar"
    if not env.exists():
        return f"O arquivo .env ainda não existe. Crie-o com o comando abaixo e depois ligue o sistema de novo:\n  {comando}"
    if (not ajustes.secret_key or ajustes.secret_key == VALORES_DE_EXEMPLO["SECRET_KEY"]) \
            and not ajustes.modo_desenvolvimento:
        return f"Falta a SECRET_KEY no .env. Para gerar uma, rode:\n  {comando}"
    banco = ajustes.caminho_sqlite
    sem_usuarios = banco is not None and not banco.exists()  # banco novo = ainda sem usuários
    # A senha inicial só é usada para criar o primeiro administrador, quando o banco ainda não existe.
    if sem_usuarios and (not ajustes.admin_senha_inicial or ajustes.admin_senha_inicial == SENHA_PADRAO_ENV):
        return f"Falta a senha inicial do administrador no .env (ADMIN_SENHA_INICIAL). Para defini-la, rode:\n  {comando}"
    return None


def aviso_do_python() -> str | None:
    """Avisa quando o sistema é aberto com um Python de fora do projeto (onde o YOLO pode não estar instalado)."""
    venv = RAIZ / ".venv"
    if venv.exists() and Path(sys.prefix).resolve() != venv.resolve():
        return (f"Atenção: este não é o Python do projeto ({sys.executable}).\n"
                r"  Use:  .venv\Scripts\python -m app")
    return None
