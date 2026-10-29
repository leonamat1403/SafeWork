"""Ocorrências: persistência por tempo, cooldown, agrupamento e CSV – casos [FASE 1] do RNF06 (RF18–RF20)."""
import csv

import pytest

from src.body_regions import RegioesCorpo
from src.compliance import AvaliacaoEPI, AvaliacaoPessoa
from src.occurrences import GerenciadorOcorrencias, RegistroCSV
from src.tipos import Estado, Pessoa

FPS = 15
C, NC, IND = Estado.CONFORME, Estado.NAO_CONFORME, Estado.INDETERMINADO
REGIOES = RegioesCorpo(cabeca=(0, 0, 10, 10), linha_olhos_y=None, rosto_visivel=True, orientacao="frente",
                       fallback=False)
MOTIVOS = {C: "máscara na região da cabeça", NC: "rosto visível sem máscara", IND: "rosto não visível"}


def avaliacao(estados: dict, track_id=1, levantada=False) -> AvaliacaoPessoa:
    """Avaliação pronta de uma pessoa, ex.: avaliacao({"mascara": NC})."""
    epis = {epi: AvaliacaoEPI(est, 0.8 if est == C else None, MOTIVOS[est]) for epi, est in estados.items()}
    return AvaliacaoPessoa(Pessoa(caixa=(0, 0, 100, 300), track_id=track_id), REGIOES, epis, levantada)


def simular(config, linha_do_tempo, duracao_s: float, saturado=lambda t: False):
    """Roda o gerenciador a 15 FPS. `linha_do_tempo(t)` devolve a lista de avaliações do frame no instante t."""
    gerenciador = GerenciadorOcorrencias(config)
    ocorrencias = []
    for frame in range(int(duracao_s * FPS) + 1):
        t = frame / FPS
        ocorrencias += gerenciador.atualizar(linha_do_tempo(t), t, frame, saturado(t))
    return ocorrencias, gerenciador


# --- Persistência (4 s com pelo menos 75% dos frames em falta) -------------------------------------------------------
def test_sem_mascara_por_4_segundos_gera_uma_ocorrencia(config):
    """Quatro segundos sem máscara geram uma única ocorrência com o EPI e a situação certos."""
    ocorrencias, _ = simular(config, lambda t: [avaliacao({"mascara": NC})], 10)
    assert len(ocorrencias) == 1
    assert 3.7 <= ocorrencias[0].tempo_s <= 4.1
    assert ocorrencias[0].epis_faltantes == ["mascara"]
    assert ocorrencias[0].situacao == {"mascara": "rosto visível sem máscara"}


def test_levantar_a_mascara_por_2_segundos_nao_gera_ocorrencia(config):
    """O soldador levanta a máscara para olhar o cordão e abaixa de novo."""
    ocorrencias, _ = simular(config, lambda t: [avaliacao({"mascara": NC if 2 <= t < 4 else C})], 15)
    assert ocorrencias == []


def test_frames_errados_isolados_nao_zeram_a_contagem(config):
    """90% dos frames sem máscara (1 frame "OK" falso a cada 10): a ocorrência sai mesmo assim."""
    ocorrencias, _ = simular(config, lambda t: [avaliacao({"mascara": C if round(t * FPS) % 10 == 0 else NC})], 10)
    assert len(ocorrencias) == 1


def test_metade_dos_frames_sem_mascara_nao_basta(config):
    """Só metade dos frames sem máscara fica abaixo dos 75% e não gera ocorrência."""
    ocorrencias, _ = simular(config, lambda t: [avaliacao({"mascara": NC if round(t * FPS) % 2 else C})], 20)
    assert ocorrencias == []


def test_indeterminado_nunca_gera_ocorrencia(config):
    """Estado indeterminado, por mais tempo que dure, nunca gera ocorrência."""
    ocorrencias, _ = simular(config, lambda t: [avaliacao({"mascara": IND})], 30)
    assert ocorrencias == []


def test_mascara_levantada_gera_ocorrencia_com_a_situacao_certa(config):
    """Máscara levantada por tempo suficiente gera ocorrência com a situação 'máscara levantada'."""
    def linha(t):
        """Linha do tempo simulada: sempre uma pessoa com máscara levantada, contada como falta."""
        aval = avaliacao({"mascara": NC}, levantada=True)
        aval.epis["mascara"] = AvaliacaoEPI(NC, 0.7, "máscara levantada")
        return [aval]
    ocorrencias, _ = simular(config, linha, 6)
    assert len(ocorrencias) == 1
    assert ocorrencias[0].situacao == {"mascara": "máscara levantada"}
    assert ocorrencias[0].mascara_levantada


# --- Cooldown (60 s por pessoa e EPI) ---------------------------------------------------------------------------------
def test_mesma_pessoa_sem_mascara_gera_de_novo_so_depois_de_60_segundos(config):
    """Mesma pessoa sem máscara só gera nova ocorrência 60 s depois da anterior."""
    ocorrencias, _ = simular(config, lambda t: [avaliacao({"mascara": NC})], 70)
    assert len(ocorrencias) == 2
    assert ocorrencias[1].tempo_s - ocorrencias[0].tempo_s == pytest.approx(60, abs=0.1)


def test_cooldown_vale_mesmo_se_a_pessoa_colocou_a_mascara_no_meio(config):
    """O cooldown de 60 s continua valendo mesmo que a pessoa tenha colocado a máscara no meio."""
    def estado(t):   # sem máscara 0–6 s, com máscara 6–20 s, sem máscara 20–30 s e de novo a partir de 70 s
        """Estado simulado no instante t: em falta nos trechos iniciais, de 20 a 30 s e depois de 70 s."""
        return NC if t < 6 or 20 <= t < 30 or t >= 70 else C
    ocorrencias, _ = simular(config, lambda t: [avaliacao({"mascara": estado(t)})], 80)
    tempos = [round(o.tempo_s) for o in ocorrencias]
    assert len(ocorrencias) == 2                     # ~4 s e ~74 s; o trecho de 20–30 s está dentro do cooldown
    assert tempos[0] == 4 and 73 <= tempos[1] <= 74


def test_cada_pessoa_tem_seu_proprio_cooldown(config):
    """Duas pessoas em falta ao mesmo tempo geram uma ocorrência cada, com cooldowns separados."""
    ocorrencias, _ = simular(config, lambda t: [avaliacao({"mascara": NC}, track_id=1),
                                                avaliacao({"mascara": NC}, track_id=2)], 10)
    assert sorted(o.track_id for o in ocorrencias) == [1, 2]


# --- Agrupamento (RF20) e arco (RF14) --------------------------------------------------------------------------------
def test_varios_epis_faltando_geram_uma_unica_ocorrencia(config):
    """Luvas (persistência 2 s no config) e máscara (4 s) em falta: 1 ocorrência com os dois EPIs."""
    ocorrencias, _ = simular(config, lambda t: [avaliacao({"mascara": NC, "luvas": NC})], 30)
    assert len(ocorrencias) == 1
    assert ocorrencias[0].epis_faltantes == ["mascara", "luvas"]


def test_frames_saturados_pelo_arco_nao_contam(config):
    """Arco aceso de 0 a 10 s: nada conta. Depois, são precisos mais 4 s de falta para registrar."""
    ocorrencias, _ = simular(config, lambda t: [avaliacao({"mascara": NC})], 20, saturado=lambda t: t < 10)
    assert len(ocorrencias) == 1
    assert 13.7 <= ocorrencias[0].tempo_s <= 14.1


def test_pessoa_sem_track_id_e_ignorada(config):
    """Pessoa sem identificador de rastreio é ignorada e não gera ocorrência."""
    ocorrencias, _ = simular(config, lambda t: [avaliacao({"mascara": NC}, track_id=None)], 10)
    assert ocorrencias == []


# --- Saídas: resumo por pessoa e CSV ----------------------------------------------------------------------------------
def test_resumo_por_pessoa(config):
    """O resumo por pessoa traz o número de ocorrências e o tempo em cada estado."""
    _, gerenciador = simular(config, lambda t: [avaliacao({"mascara": NC if t < 5 else C})], 10)
    linha = gerenciador.resumo_por_pessoa()[0]
    assert linha.startswith("pessoa #1: 1 ocorrência(s)")
    assert "NAO_CONFORME 5.0s" in linha and "CONFORME 5.0s" in linha


def test_csv_abre_no_excel_em_portugues(config, tmp_path):
    """O CSV é gravado em UTF-8 com BOM, separado por ponto e vírgula e com vírgula decimal, para abrir no Excel."""
    ocorrencias, _ = simular(config, lambda t: [avaliacao({"mascara": NC}, track_id=7)], 6)
    caminho = tmp_path / "ocorrencias.csv"
    registro = RegistroCSV(caminho, "video_teste.mp4", "mig_01")
    registro.gravar(ocorrencias[0])
    registro.fechar()

    texto = caminho.read_bytes()
    assert texto.startswith(b"\xef\xbb\xbf")                       # UTF-8 com BOM (acentos corretos no Excel)
    with caminho.open(encoding="utf-8-sig", newline="") as arq:
        linhas = list(csv.reader(arq, delimiter=";"))
    assert linhas[0] == RegistroCSV.COLUNAS
    registro_lido = dict(zip(linhas[0], linhas[1]))
    assert registro_lido["pessoa"] == "7"
    assert registro_lido["posto"] == "mig_01"
    assert registro_lido["epis_faltantes"] == "mascara"
    assert registro_lido["situacao"] == "mascara: rosto visível sem máscara"
    assert registro_lido["fracao_nao_conforme"] == "mascara=1,000"   # vírgula decimal
    assert registro_lido["revisao_manual"] == ""
