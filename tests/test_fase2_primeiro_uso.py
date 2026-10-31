"""[FASE 2] Primeira configuração (python -m app --configurar) e as mensagens claras quando falta algo no .env.
Tudo em pastas temporárias: o .env de verdade nunca é tocado."""
from __future__ import annotations

import re

import pytest
from dotenv import dotenv_values

from app.config import carregar_ajustes
from app.primeiro_uso import configurar_env, problema_para_iniciar
from tests.conftest import RAIZ

EXEMPLO = RAIZ / ".env.example"


@pytest.mark.parametrize("senha", ["senha-forte-1", "com espaço # e 'aspas'", 'dupla"aspa\\barra'])
def test_cria_o_env_com_chave_e_senha(tmp_path, senha):
    """Cria o .env com chave aleatória e senha do administrador, sem mostrar valores."""
    env = tmp_path / ".env"
    feitos = configurar_env(env, EXEMPLO, lambda login: senha)
    assert feitos == ["arquivo .env criado a partir do .env.example", "SECRET_KEY gerada (64 caracteres aleatórios)",
                      "senha inicial do administrador 'admin' definida"]
    valores = dotenv_values(env)
    assert re.fullmatch(r"[0-9a-f]{64}", valores["SECRET_KEY"]) and valores["ADMIN_SENHA_INICIAL"] == senha
    assert valores["DATA_DIR"] == "./data" and valores["PORTA"] == "8000"          # o resto veio do exemplo
    assert all(senha not in item for item in feitos)                                 # nada de valor na tela


def test_env_completo_nao_muda(tmp_path):
    """Um .env já completo não é alterado nem pede a senha de novo."""
    env = tmp_path / ".env"
    configurar_env(env, EXEMPLO, lambda login: "senha-forte-1")
    antes = env.read_text(encoding="utf-8")
    assert configurar_env(env, EXEMPLO, lambda login: pytest.fail("não devia pedir a senha")) == []
    assert env.read_text(encoding="utf-8") == antes


def test_completa_so_o_que_falta(tmp_path):
    """Completa só o que falta no .env e preserva o que já estava."""
    env = tmp_path / ".env"
    env.write_text("DATA_DIR=./outra\nSECRET_KEY=troque-esta-chave\nADMIN_LOGIN_INICIAL=chefe\n", encoding="utf-8")
    feitos = configurar_env(env, EXEMPLO, lambda login: f"senha-do-{login}")
    assert feitos == ["SECRET_KEY gerada (64 caracteres aleatórios)", "senha inicial do administrador 'chefe' definida"]
    valores = dotenv_values(env)
    assert valores["DATA_DIR"] == "./outra" and valores["ADMIN_SENHA_INICIAL"] == "senha-do-chefe"
    assert valores["SECRET_KEY"] != "troque-esta-chave"


def test_mensagens_claras_antes_de_ligar(tmp_path):
    """Antes de ligar, o sistema aponta com clareza o que falta no .env."""
    ajustes = lambda **extra: carregar_ajustes(ambiente={"DATA_DIR": str(tmp_path / "data"), **extra})   # noqa: E731
    env = tmp_path / ".env"
    assert "--configurar" in problema_para_iniciar(ajustes(), env) and "não existe" in problema_para_iniciar(ajustes(), env)
    env.write_text("", encoding="utf-8")
    assert "SECRET_KEY" in problema_para_iniciar(ajustes(SECRET_KEY="troque-esta-chave"), env)
    assert "ADMIN_SENHA_INICIAL" in problema_para_iniciar(ajustes(SECRET_KEY="x" * 64), env)
    assert problema_para_iniciar(ajustes(SECRET_KEY="x" * 64, ADMIN_SENHA_INICIAL="senha-forte-1"), env) is None


def test_redefinir_senha_do_admin(tmp_path):
    """--redefinir-admin troca a senha, reativa o usuário e exige nova troca; usuário inexistente devolve False."""
    from app.auth import conferir_senha, gerar_hash
    from app.database import criar_engine, criar_fabrica_sessoes
    from app.models import Base, Usuario
    from app.primeiro_uso import redefinir_senha_admin

    engine = criar_engine(f"sqlite:///{tmp_path / 'teste.sqlite3'}")
    Base.metadata.create_all(engine)
    fabrica = criar_fabrica_sessoes(engine)
    with fabrica() as s:
        s.add(Usuario(nome="Administrador", login="admin", senha_hash=gerar_hash("senha-antiga-1"), perfil="ADMIN",
                      ativo=False, deve_trocar_senha=False))
        s.commit()
    assert redefinir_senha_admin(fabrica, "admin", "senha-nova-123") is True
    with fabrica() as s:
        u = s.query(Usuario).filter_by(login="admin").one()
        assert conferir_senha("senha-nova-123", u.senha_hash) and not conferir_senha("senha-antiga-1", u.senha_hash)
        assert u.ativo and u.deve_trocar_senha
    assert redefinir_senha_admin(fabrica, "outro", "senha-nova-123") is False
