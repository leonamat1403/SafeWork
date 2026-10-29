"""[FASE 2] Desejáveis da detecção (Etapa 2.5, bloco A): votação temporal na tela (RD01) e solda ativa (RD03).

Pessoas, máscaras e quadros SIMULADOS (sem câmera e sem modelos).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import numpy as np
import pytest
import yaml

from app.models import Ocorrencia
from app.privacy import Borrador
from app.registro import RegistradorOcorrencias
from src.arc_filter import fracao_perto_das_maos, regioes_das_maos
from src.body_regions import RegioesCorpo
from src.compliance import AvaliacaoEPI, AvaliacaoPessoa, avaliar_frame
from src.config import ErroConfig, carregar_config
from src.occurrences import GerenciadorOcorrencias
from src.pipeline import Pipeline, ResultadoFrame
from src.tipos import Estado
from src.votacao import VotacaoTemporal
from tests.auxiliares import MASCARA_LEVANTADA, ROSTO_DESCOBERTO, ROSTO_DETECTADO, criar_pessoa, mascara
from tests.conftest import RAIZ

PULSOS = {9: (240, 380), 10: (160, 380)}             # punhos da pessoa padrão (caixa 100,100 – 300,600)
PESSOA_SOLDANDO = {**ROSTO_DESCOBERTO, **PULSOS}
REGIOES = RegioesCorpo(cabeca=None, linha_olhos_y=None, rosto_visivel=False, orientacao="indefinida", fallback=False)


# --------------------------------------------------------------------------------------------------- RD01
def avaliacao(estado: Estado, track_id: int | None = 1, levantada: bool = False, motivo: str = "") -> AvaliacaoPessoa:
    """Monta a avaliação de uma pessoa com o estado da máscara informado."""
    pessoa = criar_pessoa({}, track_id=track_id)
    return AvaliacaoPessoa(pessoa, REGIOES, {"mascara": AvaliacaoEPI(estado, motivo=motivo or estado.value)},
                           mascara_levantada=levantada)


def mostrado(votacao: VotacaoTemporal, *estados: Estado, track_id: int = 1) -> Estado:
    """Passa os estados de uma pessoa, um por quadro, e devolve o que a tela mostra no último."""
    for estado in estados:
        tela = votacao.atualizar([avaliacao(estado, track_id)])
    return tela[0].epis["mascara"].estado


N, C, I = Estado.NAO_CONFORME, Estado.CONFORME, Estado.INDETERMINADO


def test_um_quadro_errado_nao_muda_o_que_a_tela_mostra():
    """Um quadro isolado errado não muda o estado mostrado, só a maioria muda."""
    votacao = VotacaoTemporal(5)
    assert mostrado(votacao, C, C, C, N) == C        # 1 quadro "sem máscara" no meio de conformes
    assert mostrado(votacao, N, N) == N               # [C, C, N, N, N]: agora a maioria é não conforme


def test_empate_fica_com_o_estado_mais_recente():
    """Em caso de empate na votação vale o estado mais recente."""
    assert mostrado(VotacaoTemporal(4), N, C) == C
    assert mostrado(VotacaoTemporal(4), C, I, I, C) == C


def test_votacao_desligada_devolve_o_quadro_atual():
    """Com janela de 1 quadro a votação devolve o próprio quadro atual."""
    votacao = VotacaoTemporal(1)
    quadro = [avaliacao(N)]
    assert votacao.atualizar(quadro) is quadro


def test_pessoa_sem_id_nao_e_votada():
    """Pessoa sem track_id não entra na votação e mostra o estado do quadro atual."""
    votacao = VotacaoTemporal(5)
    for _ in range(3):
        votacao.atualizar([avaliacao(C, track_id=None)])
    assert votacao.atualizar([avaliacao(N, track_id=None)])[0].epis["mascara"].estado == N


def test_pessoa_que_sumiu_comeca_do_zero():
    """Pessoa que some por vários quadros começa a votação do zero ao voltar."""
    votacao = VotacaoTemporal(3)
    mostrado(votacao, N, N, N)
    for _ in range(4):                                  # 4 quadros só com outra pessoa
        votacao.atualizar([avaliacao(C, track_id=2)])
    assert mostrado(votacao, C) == C


def test_rotulo_coerente_com_o_estado_votado():
    """O motivo e o aviso de "máscara levantada" vêm do último quadro com o estado vencedor."""
    votacao = VotacaoTemporal(5)
    for _ in range(3):
        votacao.atualizar([avaliacao(C, motivo="máscara na região da cabeça")])
    tela = votacao.atualizar([avaliacao(N, levantada=True, motivo="máscara levantada")])[0]
    assert tela.epis["mascara"].estado == C and tela.epis["mascara"].motivo == "máscara na região da cabeça"
    assert tela.mascara_levantada is False and tela.cor == "verde"


def test_votacao_nao_altera_as_avaliacoes_originais():
    """A votação não modifica as avaliações originais recebidas."""
    votacao = VotacaoTemporal(5)
    votacao.atualizar([avaliacao(C)])
    original = avaliacao(N)
    votacao.atualizar([original])
    assert original.epis["mascara"].estado == N


# --------------------------------------------------------------------------------------------------- RD03
def quadro(com_arco: bool = False, altura: int = 700, largura: int = 500) -> np.ndarray:
    """Quadro escuro; com arco, um ponto estourado de 30 x 30 px logo à frente do punho direito da imagem (240, 380)."""
    img = np.full((altura, largura, 3), 40, np.uint8)
    if com_arco:
        img[385:415, 230:260] = 255
    return img


def test_brilho_perto_das_maos(config):
    """Brilho estourado perto dos punhos é medido; sem brilho ou sem punhos o resultado é zero ou nulo."""
    pessoa = criar_pessoa(PESSOA_SOLDANDO)
    assert len(regioes_das_maos(pessoa, 0.5, 0.12)) == 2          # 12% de 500 px de altura = 60 px para cada lado
    assert fracao_perto_das_maos(quadro(), pessoa, config.arco, 0.5) == 0.0
    assert fracao_perto_das_maos(quadro(com_arco=True), pessoa, config.arco, 0.5) == pytest.approx(900 / 14400)
    assert fracao_perto_das_maos(quadro(com_arco=True), criar_pessoa(ROSTO_DESCOBERTO), config.arco, 0.5) is None


def test_brilho_longe_das_maos_nao_conta(config):
    """Luz estourada longe dos punhos não conta como arco."""
    img = quadro()
    img[100:160, 400:460] = 255                                    # luz estourada no canto, longe dos punhos
    assert fracao_perto_das_maos(img, criar_pessoa(PESSOA_SOLDANDO), config.arco, 0.5) == 0.0


class DetectorSoldador:
    """Uma pessoa de frente, sem máscara, com os punhos visíveis."""

    def detectar(self, frame):
        """Devolve uma pessoa soldando, sem máscara, e um rosto detectado."""
        return [criar_pessoa(PESSOA_SOLDANDO)], [], [ROSTO_DETECTADO]


def test_arco_continua_aceso_por_alguns_segundos(config):
    """O arco pisca: depois de visto, a pessoa conta como "soldando" por manter_aceso_s (2 s)."""
    pipeline = Pipeline(config, DetectorSoldador())
    assert pipeline.processar(quadro(), t=0.0).avaliacoes[0].arco_ativo is False
    sinal = pipeline.processar(quadro(com_arco=True), t=1.0).avaliacoes[0]
    assert sinal.arco_ativo is True and sinal.arco_maos == pytest.approx(900 / 14400)
    assert pipeline.processar(quadro(), t=2.9).avaliacoes[0].arco_ativo is True
    assert pipeline.processar(quadro(), t=3.1).avaliacoes[0].arco_ativo is False


def test_deteccao_de_solda_ativa_desligada(config):
    """Com a detecção de solda ativa desligada, o arco nunca é marcado."""
    cfg = replace(config, arco=replace(config.arco, detectar_solda_ativa=False))
    aval = Pipeline(cfg, DetectorSoldador()).processar(quadro(com_arco=True), t=0.0).avaliacoes[0]
    assert aval.arco_ativo is False and aval.arco_maos is None


def sem_levantada_como_falta(config):
    """Regra original do prompt: máscara levantada só é falta com o arco aceso (RD03)."""
    mascara_cfg = config.epis["mascara"]
    extras = {**mascara_cfg.extras, "levantada_nao_conforme": False}
    return replace(config, epis={**config.epis, "mascara": replace(mascara_cfg, extras=extras)})


def test_mascara_levantada_com_arco_aceso_e_nao_conforme(config):
    """[FASE 2] do RNF06: máscara levantada + RD03 ativo + arco detectado -> NÃO CONFORME."""
    cfg = sem_levantada_como_falta(config)
    pessoa, deteccoes = criar_pessoa(ROSTO_DESCOBERTO), [mascara(MASCARA_LEVANTADA)]
    sem_arco = avaliar_frame([pessoa], deteccoes, cfg, arco_ativo=[False])[0]
    assert sem_arco.mascara_levantada and sem_arco.epis["mascara"].estado == Estado.CONFORME
    com_arco = avaliar_frame([pessoa], deteccoes, cfg, arco_ativo=[True])[0]
    assert com_arco.epis["mascara"].estado == Estado.NAO_CONFORME
    assert com_arco.epis["mascara"].motivo == "máscara levantada com o arco aceso"


def test_exigir_mascara_somente_com_arco(config):
    """Com a opção ligada, rosto sem máscara só é não conforme quando há arco aceso."""
    cfg = replace(config, arco=replace(config.arco, exigir_mascara_somente_com_arco=True))
    pessoa = criar_pessoa(ROSTO_DESCOBERTO)
    parado = avaliar_frame([pessoa], [], cfg, [ROSTO_DETECTADO], arco_ativo=[False])[0]
    assert parado.epis["mascara"].estado == Estado.CONFORME
    assert "sem arco aceso" in parado.epis["mascara"].motivo
    soldando = avaliar_frame([pessoa], [], cfg, [ROSTO_DETECTADO], arco_ativo=[True])[0]
    assert soldando.epis["mascara"].estado == Estado.NAO_CONFORME
    assert soldando.epis["mascara"].motivo == "rosto visível sem máscara, arco aceso"


def test_padrao_do_projeto_nao_muda_sem_arco(config):
    """Com exigir_mascara_somente_com_arco: false (padrão), a regra validada na Fase 1 continua igual."""
    assert config.arco.exigir_mascara_somente_com_arco is False and config.arco.detectar_solda_ativa is True
    aval = avaliar_frame([criar_pessoa(ROSTO_DESCOBERTO)], [], config, [ROSTO_DETECTADO], arco_ativo=[False])[0]
    assert aval.epis["mascara"].estado == Estado.NAO_CONFORME
    assert aval.epis["mascara"].motivo == "rosto visível sem máscara"


def test_exigir_arco_sem_detectar_arco_e_recusado(tmp_path):
    """Configuração que exige arco mas desliga a detecção de solda ativa é recusada."""
    dados = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8-sig"))
    dados["arco"].update(exigir_mascara_somente_com_arco=True, detectar_solda_ativa=False)
    for nome in ("epi", "pose", "rosto"):
        dados["modelos"][nome] = str(RAIZ / dados["modelos"][nome])
    arquivo = tmp_path / "config.yaml"
    arquivo.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ErroConfig, match="detectar_solda_ativa"):
        carregar_config(arquivo)


def test_ocorrencia_guarda_o_arco_aceso(config, fabrica, storage, camera_id):
    """A ocorrência confirmada com o arco aceso vai para o banco com arco_ativo = True (prioridade alta)."""
    gerenciador, novas = GerenciadorOcorrencias(config), []
    for i in range(45):                                            # 4,5 s a 10 quadros por segundo, sem máscara
        aval = avaliar_frame([criar_pessoa(PESSOA_SOLDANDO)], [], config, [ROSTO_DETECTADO], arco_ativo=[True])
        novas += gerenciador.atualizar(aval, i / 10, i)
    assert len(novas) == 1 and novas[0].arco_ativo is True
    registrador = RegistradorOcorrencias(fabrica, storage, Borrador(None), {"1": "00:00-23:59"})
    resultado = ResultadoFrame(aval, [], False, 0.0, [ROSTO_DETECTADO])
    oc = replace(novas[0], data_hora=datetime(2026, 10, 15, 12, tzinfo=timezone.utc))
    registrador.registrar(oc, quadro(), resultado, camera_id)
    with fabrica() as sessao:
        assert sessao.query(Ocorrencia).one().arco_ativo is True
