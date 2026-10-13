"""Leitura e validação do config.yaml.

Os valores de `epis` são o padrão. Cada posto em `postos` sobrescreve só o que muda (RF13), e o posto é
escolhido na linha de comando com `--posto`. Qualquer erro no arquivo interrompe o programa com uma
mensagem clara, em vez de deixar o sistema rodar com um valor errado.
"""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

EPIS_CONHECIDOS = ("mascara", "luvas", "protecao_corpo", "calcado", "capacete")
EPIS_IMPLEMENTADOS = ("mascara",)   # Fase 1: foco na máscara de solda (decisão de 11/10/2026)

# Classe do modelo -> EPI do sistema (avental e macacão contam como "proteção do corpo")
EPI_DA_CLASSE = {
    "mascara": "mascara",
    "luvas": "luvas",
    "avental": "protecao_corpo",
    "macacao": "protecao_corpo",
    "calcado": "calcado",
    "capacete": "capacete",
}


class ErroConfig(ValueError):
    """Erro de conteúdo no config.yaml."""


@dataclass(frozen=True)
class ConfigEPI:
    nome: str
    ativo: bool
    conf: float                    # confiança mínima da detecção (RF15)
    persistencia_s: float = 4.0    # segundos de falta antes de registrar a ocorrência (RF18)
    fracao_minima: float = 0.75    # fração mínima de frames NÃO CONFORME nesse período (tolera frames errados)
    cobertura_min: float = 0.30    # fração mínima da caixa do EPI dentro da região do corpo
    extras: dict[str, Any] = field(default_factory=dict)   # parâmetros específicos (trabalho futuro)


@dataclass(frozen=True)
class ConfigDeteccao:
    imgsz: int = 640
    imgsz_pose: int = 640
    conf_pessoa: float = 0.40
    conf_keypoint: float = 0.5
    altura_min_pessoa_px: int = 200
    pular_frames: int = 1
    conf_rosto: float = 0.6        # confiança mínima do detector de rostos (YuNet)
    tamanho_recorte_rosto: int = 224   # o recorte da cabeça é ampliado/reduzido para este lado antes de procurar rostos


@dataclass(frozen=True)
class ConfigArco:
    limiar_brilho: int = 245
    fracao_max_saturada: float = 0.15
    exigir_mascara_somente_com_arco: bool = False


@dataclass(frozen=True)
class ConfigOcorrencias:
    cooldown_s: float = 60.0


@dataclass(frozen=True)
class ConfigModelos:
    epi: Path
    pose: Path
    rosto: Path | None = None      # detector de rostos (YuNet); sem ele, "rosto visível" vem da pose


@dataclass(frozen=True)
class Config:
    posto: str
    descricao: str
    epis: dict[str, ConfigEPI]
    deteccao: ConfigDeteccao
    arco: ConfigArco
    ocorrencias: ConfigOcorrencias
    modelos: ConfigModelos
    mapeamento_classes: dict[str, str]   # nome original (minúsculo) -> classe interna

    @property
    def epis_ativos(self) -> list[str]:
        """Nomes dos EPIs exigidos neste posto."""
        return [nome for nome, epi in self.epis.items() if epi.ativo]


def _mesclar(base: dict, extra: dict) -> dict:
    """Mescla dois dicionários em profundidade: `extra` sobrescreve só as chaves que define."""
    resultado = copy.deepcopy(base)
    for chave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(resultado.get(chave), dict):
            resultado[chave] = _mesclar(resultado[chave], valor)
        else:
            resultado[chave] = copy.deepcopy(valor)
    return resultado


def _numero(secao: dict, chave: str, onde: str, minimo: float, maximo: float, padrao: float | None = None) -> float:
    """Lê um número e confere se está na faixa [minimo, maximo]."""
    if chave not in secao:
        if padrao is None:
            raise ErroConfig(f"{onde}: falta o campo '{chave}'.")
        return padrao
    valor = secao[chave]
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErroConfig(f"{onde}.{chave} deve ser um número (recebido: {valor!r}).")
    if not minimo <= valor <= maximo:
        raise ErroConfig(f"{onde}.{chave} = {valor} está fora da faixa permitida ({minimo} a {maximo}).")
    return valor


def _ler_epis(secao: dict) -> dict[str, ConfigEPI]:
    if not isinstance(secao, dict) or not secao:
        raise ErroConfig("A seção 'epis' é obrigatória e não pode estar vazia.")
    epis = {}
    for nome, dados in secao.items():
        if nome not in EPIS_CONHECIDOS:
            raise ErroConfig(f"EPI desconhecido em 'epis': {nome!r}. Use um de: {', '.join(EPIS_CONHECIDOS)}.")
        if not isinstance(dados, dict):
            raise ErroConfig(f"epis.{nome} deve ser um bloco de campos (ex.: {{ativo: true, conf: 0.45}}).")
        onde = f"epis.{nome}"
        if "frames_persistencia" in dados:
            raise ErroConfig(f"{onde}.frames_persistencia foi substituído por persistencia_s (em segundos) e "
                             "fracao_minima (ex.: persistencia_s: 4, fracao_minima: 0.75).")
        ativo = bool(dados.get("ativo", False))
        if ativo and nome not in EPIS_IMPLEMENTADOS:
            log.warning("epis.%s está ativo, mas ainda não foi implementado na Fase 1 (foco: máscara). "
                        "Ele será ignorado.", nome)
            ativo = False
        conhecidos = {"ativo", "conf", "persistencia_s", "fracao_minima", "cobertura_min"}
        epis[nome] = ConfigEPI(
            nome=nome,
            ativo=ativo,
            conf=_numero(dados, "conf", onde, 0.0, 1.0),
            persistencia_s=_numero(dados, "persistencia_s", onde, 0.1, 600, padrao=4.0),
            fracao_minima=_numero(dados, "fracao_minima", onde, 0.01, 1.0, padrao=0.75),
            cobertura_min=_numero(dados, "cobertura_min", onde, 0.0, 1.0, padrao=0.30),
            extras={k: v for k, v in dados.items() if k not in conhecidos},
        )
    if not any(e.ativo for e in epis.values()):
        raise ErroConfig("Nenhum EPI ativo. Ative pelo menos a máscara (epis.mascara.ativo: true).")
    return epis


def carregar_config(caminho: str | Path = "config.yaml", posto: str = "padrao") -> Config:
    """Lê o config.yaml, aplica as configurações do posto escolhido e valida tudo.

    Levanta ErroConfig com uma mensagem explicativa se algo estiver errado.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        raise ErroConfig(f"Arquivo de configuração não encontrado: {caminho.resolve()}")
    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as erro:
        raise ErroConfig(f"O arquivo {caminho} não é um YAML válido: {erro}") from erro
    if not isinstance(dados, dict):
        raise ErroConfig(f"O arquivo {caminho} deve conter seções (epis, deteccao, ...).")

    # Posto: mescla as configurações específicas sobre o padrão
    postos = dados.get("postos") or {"padrao": {}}
    if posto not in postos:
        raise ErroConfig(f"Posto {posto!r} não existe em 'postos'. Disponíveis: {', '.join(postos)}.")
    dados_posto = postos[posto] or {}
    for nome in (dados_posto.get("epis") or {}):
        if nome not in EPIS_CONHECIDOS:
            raise ErroConfig(f"postos.{posto}.epis: EPI desconhecido {nome!r}.")
    epis = _ler_epis(_mesclar(dados.get("epis") or {}, dados_posto.get("epis") or {}))

    sec = dados.get("deteccao") or {}
    imgsz = int(_numero(sec, "imgsz", "deteccao", 32, 4096, padrao=640))
    imgsz_pose = int(_numero(sec, "imgsz_pose", "deteccao", 32, 4096, padrao=640))
    for nome, valor in (("imgsz", imgsz), ("imgsz_pose", imgsz_pose)):
        if valor % 32:
            raise ErroConfig(f"deteccao.{nome} = {valor} deve ser múltiplo de 32 (ex.: 640, 960).")
    deteccao = ConfigDeteccao(
        imgsz=imgsz,
        imgsz_pose=imgsz_pose,
        conf_pessoa=_numero(sec, "conf_pessoa", "deteccao", 0.0, 1.0, padrao=0.40),
        conf_keypoint=_numero(sec, "conf_keypoint", "deteccao", 0.0, 1.0, padrao=0.5),
        altura_min_pessoa_px=int(_numero(sec, "altura_min_pessoa_px", "deteccao", 0, 10_000, padrao=200)),
        pular_frames=int(_numero(sec, "pular_frames", "deteccao", 1, 100, padrao=1)),
        conf_rosto=_numero(sec, "conf_rosto", "deteccao", 0.0, 1.0, padrao=0.6),
        tamanho_recorte_rosto=int(_numero(sec, "tamanho_recorte_rosto", "deteccao", 64, 1024, padrao=224)),
    )

    sec = dados.get("arco") or {}
    arco = ConfigArco(
        limiar_brilho=int(_numero(sec, "limiar_brilho", "arco", 0, 255, padrao=245)),
        fracao_max_saturada=_numero(sec, "fracao_max_saturada", "arco", 0.0, 1.0, padrao=0.15),
        exigir_mascara_somente_com_arco=bool(sec.get("exigir_mascara_somente_com_arco", False)),
    )

    sec = dados.get("ocorrencias") or {}
    ocorrencias = ConfigOcorrencias(cooldown_s=_numero(sec, "cooldown_s", "ocorrencias", 0, 86_400, padrao=60))

    sec = dados.get("modelos") or {}
    base = caminho.resolve().parent
    modelos = ConfigModelos(
        epi=base / sec.get("epi", "models/epi_solda_best.pt"),
        pose=base / sec.get("pose", "models/yolov8n-pose.pt"),
        rosto=(base / sec["rosto"]) if sec.get("rosto") else None,
    )

    mapeamento = {}
    for original, interno in (dados.get("mapeamento_classes") or {}).items():
        if interno not in EPI_DA_CLASSE:
            raise ErroConfig(f"mapeamento_classes: {original!r} aponta para {interno!r}, que não é uma classe "
                             f"interna ({', '.join(EPI_DA_CLASSE)}).")
        mapeamento[str(original).strip().lower()] = interno

    return Config(
        posto=posto,
        descricao=str(dados_posto.get("descricao", posto)),
        epis=epis,
        deteccao=deteccao,
        arco=arco,
        ocorrencias=ocorrencias,
        modelos=modelos,
        mapeamento_classes=mapeamento,
    )
