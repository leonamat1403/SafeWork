"""Inicia o sistema web:  .venv\\Scripts\\python -m app   (Ctrl+C para encerrar).

Primeira vez:  .venv\\Scripts\\python -m app --configurar   (cria o .env com a SECRET_KEY e a senha do administrador).
"""
import argparse
import sys

from app.config import RAIZ, ErroAjustes, carregar_ajustes
from app.primeiro_uso import (aviso_do_python, configurar_env, pedir_senha_no_terminal, problema_para_iniciar,
                              redefinir_senha_admin)


def _redefinir_admin() -> int:
    """Pede uma senha nova no terminal e grava no banco para o administrador do .env (padrão: admin). Devolve o código de saída."""
    from app.database import aplicar_migracoes, criar_engine, criar_fabrica_sessoes   # só aqui: o modo normal não precisa
    try:
        ajustes = carregar_ajustes()
    except ErroAjustes as erro:
        print(f"Erro na configuração: {erro}", file=sys.stderr)
        return 1
    if ajustes.caminho_sqlite is not None and not ajustes.caminho_sqlite.exists():
        print("O banco ainda não existe: ligue o sistema uma vez (ele cria o admin com a senha do .env).", file=sys.stderr)
        return 1
    aplicar_migracoes(ajustes.database_url)
    login = ajustes.admin_login_inicial or "admin"
    senha = pedir_senha_no_terminal(login)
    if not redefinir_senha_admin(criar_fabrica_sessoes(criar_engine(ajustes.database_url)), login, senha):
        print(f"O usuário '{login}' não existe no banco. Crie-o em Usuários (com outro administrador).", file=sys.stderr)
        return 1
    print(f"Pronto: a senha de '{login}' foi redefinida. Ligue o sistema e entre; ele vai pedir uma senha nova.")
    return 0


def main() -> int:
    """Com --configurar, prepara o .env e sai; senão confere a configuração e sobe o servidor. Devolve o código de saída."""
    parser = argparse.ArgumentParser(prog="python -m app", description="Verificador de EPIs de Solda – sistema web")
    parser.add_argument("--configurar", action="store_true",
                        help="cria ou completa o .env (gera a SECRET_KEY e pede a senha do 1º administrador)")
    parser.add_argument("--redefinir-admin", action="store_true",
                        help="define uma nova senha para o usuário admin (se você a esqueceu); a troca é exigida no próximo acesso")
    args = parser.parse_args()
    if aviso := aviso_do_python():   # avisa (sem impedir) se não for o Python do .venv do projeto
        print(aviso, file=sys.stderr)
    env = RAIZ / ".env"
    if args.configurar:
        feitos = configurar_env(env, RAIZ / ".env.example", pedir_senha_no_terminal)
        for item in feitos or ["o .env já estava completo; nada mudou"]:
            print(f"- {item}")
        print(r"Pronto. Para ligar o sistema:  .venv\Scripts\python -m app")
        return 0
    if args.redefinir_admin:
        return _redefinir_admin()
    try:
        ajustes = carregar_ajustes()
    except ErroAjustes as erro:
        print(f"Erro na configuração: {erro}", file=sys.stderr)
        return 1
    if problema := problema_para_iniciar(ajustes, env):
        print(problema, file=sys.stderr)
        return 1
    import uvicorn   # importado só aqui: o modo --configurar não precisa do servidor
    print(f"Abra no navegador: http://{'127.0.0.1' if ajustes.host == '0.0.0.0' else ajustes.host}:{ajustes.porta}")
    # 1 processo só (sem workers): os modelos e as câmeras ficam na memória dele (docs/arquitetura_fase2.md, seção 6)
    uvicorn.run("app.main:criar_app", factory=True, host=ajustes.host, port=ajustes.porta, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
