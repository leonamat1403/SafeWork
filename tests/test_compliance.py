"""Regra da máscara de solda (RF07), cor da caixa (RF04) e rótulo – inclui os casos [FASE 1] do RNF06."""
from dataclasses import replace

from src.compliance import AvaliacaoEPI, avaliar_frame, cor_da_pessoa
from src.tipos import Estado, Pessoa
from tests.auxiliares import (CAIXA_PADRAO, MASCARA_ABAIXADA, MASCARA_LEVANTADA, MASCARA_NA_BANCADA, ORELHAS, ROSTO_DETECTADO,
                              OMBROS_COSTAS, QUADRIS, ROSTO_COBERTO, ROSTO_DESCOBERTO, criar_pessoa, deslocar,
                              deslocar_caixa, mascara)


def avaliar_uma(config, pontos, deteccoes, **kwargs):
    """Avalia uma única pessoa com os pontos e detecções dados e devolve a avaliação dela."""
    return avaliar_frame([criar_pessoa(pontos, **kwargs)], deteccoes, config)[0]


# --- Casos [FASE 1] do RNF06 -------------------------------------------------------------------------------------
def test_mascara_sobre_o_rosto_com_olhos_nao_visiveis_e_conforme(config):
    """Máscara sobre o rosto com olhos cobertos é conforme, verde e sem aviso de levantada."""
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
    """Pessoa de costas sem máscara fica indeterminada (amarelo), sem acusar falta."""
    aval = avaliar_uma(config, {**ORELHAS, **OMBROS_COSTAS}, [])
    assert aval.epis["mascara"].estado == Estado.INDETERMINADO
    assert aval.epis["mascara"].motivo == "de costas"
    assert aval.cor == "amarelo"
    assert aval.rotulo == "#1 ? MASCARA"


# --- Demais regras da máscara --------------------------------------------------------------------------------------
def test_rosto_visivel_sem_mascara_e_nao_conforme(config):
    """Rosto visível e nenhuma máscara detectada é não conforme (vermelho)."""
    aval = avaliar_uma(config, ROSTO_DESCOBERTO, [])
    assert aval.epis["mascara"].estado == Estado.NAO_CONFORME
    assert aval.cor == "vermelho"
    assert aval.rotulo == "#1 SEM MASCARA"


def test_mascara_longe_da_cabeca_nao_e_associada(config):
    """Máscara longe da cabeça (na bancada) não é associada à pessoa."""
    aval = avaliar_uma(config, ROSTO_DESCOBERTO, [mascara(MASCARA_NA_BANCADA)])
    assert aval.epis["mascara"].estado == Estado.NAO_CONFORME


def test_rosto_coberto_sem_mascara_detectada_e_indeterminado(config):
    """Máscara abaixada que o detector não encontrou: olhos cobertos -> não acusa (erra para o lado seguro)."""
    aval = avaliar_uma(config, ROSTO_COBERTO, [])
    assert aval.epis["mascara"].estado == Estado.INDETERMINADO


def test_cabeca_nao_visivel_e_indeterminado(config):
    """Sem cabeça visível (só quadris) o estado é indeterminado."""
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
    """Com duas pessoas afastadas, a máscara vale só para a que está perto dela."""
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
    """Devolve uma cópia da config com os parâmetros extras da máscara trocados pelos informados."""
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
    """Máscara na altura do rosto com rosto nítido fica indeterminada, sem acusar nem dar OK."""
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
    """Com a contradição de rosto visível desligada no config, a máscara abaixada conta como conforme."""
    cfg = com_extras_da_mascara(config, contradicao_rosto_visivel=False)
    aval = avaliar_uma(cfg, ROSTO_DESCOBERTO, [mascara(MASCARA_ABAIXADA)])
    assert aval.epis["mascara"].estado == Estado.CONFORME


def test_somente_epis_ativos_sao_avaliados(config):
    """Só os EPIs ativos no config aparecem na avaliação (aqui, só a máscara)."""
    aval = avaliar_uma(config, ROSTO_DESCOBERTO, [])
    assert list(aval.epis) == ["mascara"]


def test_rotulo_sem_track_id(config):
    """Pessoa sem identificador de rastreio recebe o rótulo com '#?'."""
    aval = avaliar_uma(config, ROSTO_DESCOBERTO, [], track_id=None)
    assert aval.rotulo == "#? SEM MASCARA"


# --- Cor da caixa da pessoa (RF04) -----------------------------------------------------------------------------------
def test_cor_vermelha_quando_algum_epi_e_nao_conforme():
    """Qualquer EPI não conforme deixa a caixa da pessoa vermelha."""
    epis = {"mascara": AvaliacaoEPI(Estado.NAO_CONFORME), "luvas": AvaliacaoEPI(Estado.INDETERMINADO)}
    assert cor_da_pessoa(epis) == "vermelho"


def test_cor_amarela_quando_nenhum_nao_conforme_mas_algum_indeterminado():
    """Sem não conforme, mas com algum indeterminado, a caixa fica amarela."""
    epis = {"mascara": AvaliacaoEPI(Estado.CONFORME), "luvas": AvaliacaoEPI(Estado.INDETERMINADO)}
    assert cor_da_pessoa(epis) == "amarelo"


def test_cor_verde_quando_todos_conformes():
    """Todos os EPIs conformes deixam a caixa verde."""
    assert cor_da_pessoa({"mascara": AvaliacaoEPI(Estado.CONFORME)}) == "verde"


# --- Com o detector de rostos (testes de campo de 13/10/2026) -------------------------------------------------------
# A pose "enxerga" olhos e nariz até atrás da máscara de solda; o detector de rostos não. ROSTO_DESCOBERTO abaixo
# representa a pose "imaginando" o rosto; a lista `rostos` é o que o detector de rostos realmente encontrou.
def test_soldador_com_mascara_e_pose_imaginando_o_rosto_fica_conforme(config):
    """Caso real (T07): a pose vê "olhos", o detector de rostos não vê rosto, a máscara foi detectada."""
    for caixa in (MASCARA_ABAIXADA, MASCARA_LEVANTADA):
        aval = avaliar_frame([criar_pessoa(ROSTO_DESCOBERTO)], [mascara(caixa)], config, rostos=[])[0]
        assert aval.epis["mascara"].estado == Estado.CONFORME
        assert not aval.mascara_levantada


def test_sem_mascara_detectada_e_sem_rosto_detectado_fica_indeterminado(config):
    """Caso real (T03): máscara real não reconhecida pelo detector; sem rosto descoberto -> não acusa."""
    aval = avaliar_frame([criar_pessoa(ROSTO_DESCOBERTO)], [], config, rostos=[])[0]
    assert aval.epis["mascara"].estado == Estado.INDETERMINADO


def test_rosto_descoberto_detectado_sem_mascara_e_nao_conforme(config):
    """Rosto descoberto confirmado pelo detector de rostos e sem máscara é não conforme."""
    aval = avaliar_frame([criar_pessoa(ROSTO_DESCOBERTO)], [], config, rostos=[ROSTO_DETECTADO])[0]
    assert aval.epis["mascara"].estado == Estado.NAO_CONFORME
    assert aval.regioes.rosto_por_detector


def test_mascara_levantada_com_rosto_detectado(config):
    """Máscara levantada com rosto detectado é sinalizada como levantada."""
    aval = avaliar_frame([criar_pessoa(ROSTO_DESCOBERTO)], [mascara(MASCARA_LEVANTADA)], config,
                         rostos=[ROSTO_DETECTADO])[0]
    assert aval.mascara_levantada
    assert aval.epis["mascara"].motivo == "máscara levantada"


def test_contradicao_com_o_detector_de_rostos(config):
    """Máscara na altura do rosto com rosto detectado é contradição e fica indeterminada."""
    aval = avaliar_frame([criar_pessoa(ROSTO_DESCOBERTO)], [mascara(MASCARA_ABAIXADA)], config,
                         rostos=[ROSTO_DETECTADO])[0]
    assert aval.epis["mascara"].estado == Estado.INDETERMINADO
    assert aval.epis["mascara"].motivo == "máscara na altura do rosto, mas rosto visível"


def test_sem_pose_mas_com_rosto_detectado_pode_acusar(config):
    """Sem pose, mas com rosto detectado e sem máscara, já dá para acusar falta."""
    aval = avaliar_frame([Pessoa(caixa=CAIXA_PADRAO)], [], config, rostos=[ROSTO_DETECTADO])[0]
    assert aval.regioes.fallback
    assert aval.epis["mascara"].estado == Estado.NAO_CONFORME
