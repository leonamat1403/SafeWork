"""Leitura e validação do config.yaml, incluindo EPIs por posto (RF13)."""
import logging

import pytest
import yaml

from src.config import ErroConfig, carregar_config
from tests.conftest import RAIZ


def escrever(tmp_path, dados: dict):
    """Grava o dicionário como config.yaml temporário e devolve o caminho."""
    caminho = tmp_path / "config.yaml"
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding="utf-8")
    return caminho


BASICO = {"epis": {"mascara": {"ativo": True, "conf": 0.45, "persistencia_s": 4}}}


def test_config_do_projeto_carrega(config):
    """O config.yaml do projeto carrega com os valores esperados."""
    assert config.posto == "padrao"
    assert config.epis_ativos == ["mascara"]
    assert config.epis["mascara"].conf == 0.45
    assert config.deteccao.imgsz == 640
    assert config.modelos.epi == RAIZ / "models" / "epi_solda_best.pt"
    assert config.mapeamento_classes["welding-glove"] == "luvas"     # chaves em minúsculas


def test_posto_sobrescreve_so_o_que_muda():
    """O posto troca só o que define e herda o resto do padrão."""
    cfg = carregar_config(RAIZ / "config.yaml", posto="corte_01")
    assert cfg.epis["mascara"].conf == 0.55                           # sobrescrito pelo posto
    assert cfg.epis["mascara"].persistencia_s == 4                    # mantido do padrão
    assert cfg.epis["mascara"].fracao_minima == 0.75
    assert cfg.descricao.startswith("Área de corte")


def test_posto_inexistente(tmp_path):
    """Pedir um posto que não existe dá erro de configuração claro."""
    with pytest.raises(ErroConfig, match="Posto 'xyz' não existe"):
        carregar_config(RAIZ / "config.yaml", posto="xyz")


def test_confianca_fora_da_faixa(tmp_path):
    """Confiança fora da faixa permitida (1,5) dá erro de configuração."""
    dados = {"epis": {"mascara": {"ativo": True, "conf": 1.5}}}
    with pytest.raises(ErroConfig, match="epis.mascara.conf"):
        carregar_config(escrever(tmp_path, dados))


def test_epi_desconhecido(tmp_path):
    """EPI que o sistema não conhece dá erro de configuração."""
    dados = {"epis": {**BASICO["epis"], "oculos": {"ativo": True, "conf": 0.5}}}
    with pytest.raises(ErroConfig, match="EPI desconhecido"):
        carregar_config(escrever(tmp_path, dados))


def test_epi_ainda_nao_implementado_e_desativado_com_aviso(tmp_path, caplog):
    """EPI ainda não implementado é desativado e avisado no log, sem derrubar o carregamento."""
    dados = {"epis": {**BASICO["epis"], "luvas": {"ativo": True, "conf": 0.4}}}
    with caplog.at_level(logging.WARNING):
        cfg = carregar_config(escrever(tmp_path, dados))
    assert cfg.epis_ativos == ["mascara"]
    assert "ainda não foi implementado" in caplog.text


def test_nenhum_epi_ativo(tmp_path):
    """Config sem nenhum EPI ativo dá erro de configuração."""
    dados = {"epis": {"mascara": {"ativo": False, "conf": 0.45}}}
    with pytest.raises(ErroConfig, match="Nenhum EPI ativo"):
        carregar_config(escrever(tmp_path, dados))


def test_imgsz_deve_ser_multiplo_de_32(tmp_path):
    """Tamanho de imagem que não é múltiplo de 32 dá erro de configuração."""
    with pytest.raises(ErroConfig, match="múltiplo de 32"):
        carregar_config(escrever(tmp_path, {**BASICO, "deteccao": {"imgsz": 700}}))


def test_mapeamento_para_classe_inexistente(tmp_path):
    """Mapeamento de classe do detector para EPI inexistente dá erro de configuração."""
    with pytest.raises(ErroConfig, match="mapeamento_classes"):
        carregar_config(escrever(tmp_path, {**BASICO, "mapeamento_classes": {"Helmet": "chapeu"}}))


def test_arquivo_inexistente(tmp_path):
    """Arquivo de configuração que não existe dá erro de 'não encontrado'."""
    with pytest.raises(ErroConfig, match="não encontrado"):
        carregar_config(tmp_path / "nao_existe.yaml")


def test_chave_antiga_frames_persistencia_explica_a_mudanca(tmp_path):
    """A chave antiga frames_persistencia dá erro que explica que agora se usa persistencia_s."""
    dados = {"epis": {"mascara": {"ativo": True, "conf": 0.45, "frames_persistencia": 20}}}
    with pytest.raises(ErroConfig, match="persistencia_s"):
        carregar_config(escrever(tmp_path, dados))