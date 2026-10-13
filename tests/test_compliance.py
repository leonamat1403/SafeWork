"""Regra da máscara de solda (RF07), cor da caixa (RF04) e rótulo – inclui os casos [FASE 1] do RNF06."""
from dataclasses import replace

from src.compliance import AvaliacaoEPI, avaliar_frame, cor_da_pessoa
from src.tipos import Estado, Pessoa
from tests.auxiliares import (CAIXA_PADRAO, MASCARA_ABAIXADA, MASCARA_LEVANTADA, MASCARA_NA_BANCADA, ORELHAS,
                              OMBROS_COSTAS, QUADRIS, ROSTO_COBERTO, ROSTO_DESCOBERTO, criar_pessoa, deslocar,
                              deslocar_caixa, mascara)


def avaliar_uma(config, pontos, deteccoes, **kwargs):
    return avaliar_frame([criar_pessoa(pontos, **kwargs)], deteccoes, config)[0]


# --- Casos [FASE 1] do RNF06 -------------------------------------------------------------------------------------
def test_mascara_sobre_o_rosto_com_olhos_nao_visiveis_e_conforme(config):
    aval = avaliar_uma(config, ROSTO_COBERTO, [mascara(MASCARA_ABAIXADA)])
    assert aval.epis["mascara"].estado == Estado.CONFORME
    assert not aval.mascara_levantada
    assert aval.cor == "verde"
    assert aval.rotulo == "#1 OK"


def test_mascara_acima_dos_olhos_com_olhos_visiveis_e_mascara_levantada(config):
    """RNF06 original: máscara levantada é sinalizada e, sem a opção levantada_nao_conforme, conta como conforme."""
    cfg = com_extras_da_mascara(config, levantada_nao_conforme=False)
    aval = avaliar_uma(cfg, ROSTO_DESCOBERTO, [mascara(MASCARA_LEVANTADA)])
    assert aval.epis["mascara"].estado == Estado.CONFORME
    assert aval.mascara_levantada
    assert aval.cor == "verde"
    assert aval.rotulo == "#1 OK | MASCARA LEVANTADA"


def test_mascara_levantada_e_nao_conforme_no_config_do_projeto(config):
    """Decisão de 13/10/2026: máscara levantada conta como falta (gera ocorrência depois de 4 s)."""
    aval = avaliar_uma(config, ROSTO_DESCOBERTO, [mascara(MASCARA_LEVANTADA)])
    assert aval.epis["mascara"].estado == Estado.NAO_CONFORME
    assert aval.epis["mascara"].motivo == "máscara levantada"
    assert aval.mascara_levantada
    assert aval.cor == "vermelho"
    assert aval.rotulo == "#1 MASCARA LEVANTADA"


def test_pessoa_de_costas_sem_mascara_e_indeterminado(config):
    aval = avaliar_uma(config, {**ORELHAS, **OMBROS_COSTAS}, [])
    assert aval.epis["mascara"].estado == Estado.INDETERMINADO
    assert aval.epis["mascara"].motivo == "de costas"
    assert aval.cor == "amarelo"
    assert aval.rotulo == "#1 ? MASCARA"


# --- Demais regras da máscara --------------------------------------------------------------------------------------
def test_rosto_visivel_sem_mascara_e_nao_conforme(config):
    aval = avaliar_uma(config, ROSTO_DESCOBERTO, [])
    assert aval.epis["mascara"].estado == Estado.NAO_CONFORME
    assert aval.cor == "vermelho"
    assert aval.rotulo == "#1 SEM MASCARA"


def test_mascara_longe_da_cabeca_nao_e_associada(config):
    aval = avaliar_uma(config, ROSTO_DESCOBERTO, [mascara(MASCARA_NA_BANCADA)])
    assert aval.epis["mascara"].estado == Estado.NAO_CONFORME


def test_rosto_coberto_sem_mascara_detectada_e_indeterminado(config):
    """Máscara abaixada que o detector não encontrou: olhos cobertos -> não acusa (erra para o lado seguro)."""
    aval = avaliar_uma(config, ROSTO_COBERTO, [])
    assert aval.epis["mascara"].estado == Estado.INDETERMINADO


def test_cabeca_nao_visivel_e_indeterminado(config):
    aval = avaliar_uma(config, QUADRIS, [])
    assert aval.epis["mascara"].estado == Estado.INDETERMINADO
    assert aval.epis["mascara"].motivo == "cabeça não visível"


def test_fallback_sem_pose(config):
    """RF12: sem pose, máscara no quarto superior da caixa conta; sem máscara não dá para acusar."""
    com = avaliar_frame([Pessoa(caixa=CAIXA_PADRAO)], [mascara((170, 120, 230, 190))], config)[0]
    sem = avaliar_frame([Pessoa(caixa=CAIXA_PADRAO)], [], config)[0]
    assert com.epis["mascara"].estado == Estado.CONFORME
    assert sem.epis["mascara"].estado == Estado.INDETERMINADO
    assert com.regioes.fallback


def test_cada_mascara_vai_para_a_pessoa_certa(config):
    pessoas = [criar_pessoa(ROSTO_DESCOBERTO, track_id=1),
               criar_pessoa(deslocar(ROSTO_DESCOBERTO, 400), deslocar_caixa(CAIXA_PADRAO, 400), track_id=2)]
    cfg = com_extras_da_mascara(config, levantada_nao_conforme=False)   # aqui o foco é a associação
    avals = avaliar_frame(pessoas, [mascara(MASCARA_LEVANTADA)], cfg)
    assert avals[0].epis["mascara"].estado == Estado.CONFORME
    assert avals[1].epis["mascara"].estado == Estado.NAO_CONFORME


def test_uma_mascara_nao_conta_para_duas_pessoas(config):
    """Duas pessoas muito próximas e uma só máscara: só uma delas fica conforme."""
    pessoas = [criar_pessoa(ROSTO_DESCOBERTO, track_id=1),
               criar_pessoa(deslocar(ROSTO_DESCOBERTO, 20), deslocar_caixa(CAIXA_PADRAO, 20), track_id=2)]
    cfg = com_extras_da_mascara(config, levantada_nao_conforme=False)
    avals = avaliar_frame(pessoas, [mascara(MASCARA_LEVANTADA)], cfg)
    estados = sorted(a.epis["mascara"].estado.value for a in avals)
    assert estados == ["CONFORME", "NAO_CONFORME"]


def com_extras_da_mascara(config, **extras):
    mascara_cfg = config.epis["mascara"]
    return replace(config, epis={**config.epis, "mascara": replace(mascara_cfg, extras={**mascara_cfg.extras, **extras})})


def test_cobertura_minima_configuravel(config):
    """Máscara com só ~20% da caixa dentro da cabeça: não conta com o padrão (0,30), conta com 0,10."""
    meio_fora = mascara((225, 130, 300, 180))   # 15 de 75 px de largura dentro da cabeça (x <= 240)
    assert avaliar_uma(config, ROSTO_COBERTO, [meio_fora]).epis["mascara"].estado == Estado.INDETERMINADO
    permissiva = replace(config, epis={**config.epis, "mascara": replace(config.epis["mascara"], cobertura_min=0.10)})
    assert avaliar_uma(permissiva, ROSTO_COBERTO, [meio_fora]).epis["mascara"].estado == Estado.CONFORME


# --- Contradição: "máscara" sobre o rosto com o rosto nítido (falso positivo do teste da webcam) ---------------------
def test_mascara_na_altura_do_rosto_com_rosto_nitido_e_indeterminado(config):
    aval = avaliar_uma(config, ROSTO_DESCOBERTO, [mascara(MASCARA_ABAIXADA)])
    assert aval.epis["mascara"].estado == Estado.INDETERMINADO
    assert aval.epis["mascara"].motivo == "máscara na altura do rosto, mas rosto visível"
    assert not aval.mascara_levantada
    assert aval.cor == "amarelo"                      # não diz "OK" e também não acusa (não gera ocorrência)


def test_mascara_real_com_pontos_do_rosto_fracos_continua_conforme(config):
    """Pose "imaginando" olhos através da máscara com confiança baixa (0,6 < 0,7): a máscara continua valendo."""
    pessoa = criar_pessoa(ROSTO_DESCOBERTO)
    for indice in (0, 1, 2):                          # nariz e olhos com confiança 0,6
        k = pessoa.keypoints[indice]
        pessoa.keypoints[indice] = type(k)(k.x, k.y, 0.6)
    aval = avaliar_frame([pessoa], [mascara(MASCARA_ABAIXADA)], config)[0]
    assert aval.epis["mascara"].estado == Estado.CONFORME


def test_contradicao_pode_ser_desligada(config):
    cfg = com_extras_da_mascara(config, contradicao_rosto_visivel=False)
    aval = avaliar_uma(cfg, ROSTO_DESCOBERTO, [mascara(MASCARA_ABAIXADA)])
    assert aval.epis["mascara"].estado == Estado.CONFORME


def test_somente_epis_ativos_sao_avaliados(config):
    aval = avaliar_uma(config, ROSTO_DESCOBERTO, [])
    assert list(aval.epis) == ["mascara"]


def test_rotulo_sem_track_id(config):
    aval = avaliar_uma(config, ROSTO_DESCOBERTO, [], track_id=None)
    assert aval.rotulo == "#? SEM MASCARA"


# --- Cor da caixa da pessoa (RF04) -----------------------------------------------------------------------------------
def test_cor_vermelha_quando_algum_epi_e_nao_conforme():
    epis = {"mascara": AvaliacaoEPI(Estado.NAO_CONFORME), "luvas": AvaliacaoEPI(Estado.INDETERMINADO)}
    assert cor_da_pessoa(epis) == "vermelho"


def test_cor_amarela_quando_nenhum_nao_conforme_mas_algum_indeterminado():
    epis = {"mascara": AvaliacaoEPI(Estado.CONFORME), "luvas": AvaliacaoEPI(Estado.INDETERMINADO)}
    assert cor_da_pessoa(epis) == "amarelo"


def test_cor_verde_quando_todos_conformes():
    assert cor_da_pessoa({"mascara": AvaliacaoEPI(Estado.CONFORME)}) == "verde"
