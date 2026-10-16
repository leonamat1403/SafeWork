"""[FASE 2] Documentação da Etapa 2.6: o README só cita arquivos que existem, e o aviso de monitoramento (RF30) é
gerado em PDF."""
from __future__ import annotations

import importlib.util
import re

from tests.conftest import RAIZ


def test_arquivos_citados_no_readme_existem():
    readme = (RAIZ / "README.md").read_text(encoding="utf-8-sig")
    citados = set(re.findall(r"`((?:docs|models|ferramentas|app|src|tests|notebooks)/[^`\s]*)`", readme))
    assert len(citados) > 15
    faltando = [c for c in citados if not (RAIZ / c.rstrip("/")).exists()]
    assert faltando == []


def test_modelos_de_documentos_do_rf30():
    for nome in ("aviso_monitoramento.md", "aviso_monitoramento.pdf", "termo_autorizacao.md"):
        assert (RAIZ / "docs" / "modelos" / nome).exists(), nome
    assert (RAIZ / "docs" / "revisao_lgpd.md").exists()


def test_material_academico_da_etapa_2_7():
    pasta = RAIZ / "docs" / "academico"
    for nome in ("texto_base.md", "planilha_antes_depois.xlsx", "roteiro_palestra.md"):
        assert (pasta / nome).exists(), nome
    texto = (pasta / "texto_base.md").read_text(encoding="utf-8")
    assert all(secao in texto for secao in ("## Metodologia", "## Resultados", "## Limitações"))


def test_gerar_aviso_para_imprimir(tmp_path):
    especificacao = importlib.util.spec_from_file_location("gerar_aviso", RAIZ / "ferramentas" / "gerar_aviso.py")
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    pdf = modulo.gerar(tmp_path / "aviso.pdf", retencao_dias=45)
    assert pdf.read_bytes().startswith(b"%PDF") and pdf.stat().st_size > 2000
