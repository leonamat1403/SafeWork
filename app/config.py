"""Configuração do sistema web (Fase 2): segredos e caminhos do .env + seções da Fase 2 do config.yaml.

Ordem de precedência (docs/arquitetura_fase2.md, seção 8): .env -> config.yaml -> banco (config_sistema e câmeras).
As configurações de detecção (modelos, limiares, arco) continuam sendo lidas por src/config.py, da Fase 1.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml
from dotenv import dotenv_values

from app.tempo import validar_turnos
from src.config import EPIS_IMPLEMENTADOS, Config, ConfigEPI

RAIZ = Path(__file__).resolve().parent.parent
PASTAS_DADOS = ("db", "ocorrencias", "thumbnails", "uploads_temp", "relatorios", "backups", "logs")
TAMANHO_LOG_BYTES = 5 * 1024 * 1024   # RNF04: 5 arquivos de 5 MB
ARQUIVOS_LOG = 5


class ErroAjustes(ValueError):
    """Valor inválido no .env ou nas seções da Fase 2 do config.yaml."""


@dataclass(frozen=True)
class Ajustes:
    """Tudo o que o sistema web precisa saber antes de abrir o banco e as câmeras."""

    data_dir: Path
    database_url: str
    secret_key: str
    admin_login_inicial: str
    admin_senha_inicial: str
    rtsp_usuario: str
    rtsp_senha: str
    telegram_token: str
    telegram_chat_id: str
    config_yaml: Path
    turnos: dict[str, str]
    retencao_dias: int
    espaco_minimo_mb: float
    backups_manter: int
    uploads_max_idade_s: int
    upload_tamanho_max_mb: int = 200
    borrar_ao_vivo: bool = True          # F2-D20: o vídeo ao vivo também sai com as cabeças borradas
    telegram_ativo: bool = True          # RD09: alerta pelo Telegram ligado (só funciona com o token no .env)
    host: str = "127.0.0.1"              # 0.0.0.0 para outros computadores/celulares da rede acessarem
    porta: int = 8000
    modo_desenvolvimento: bool = False   # liga a documentação interativa /docs (só para testes)
    cookie_seguro: bool = False          # true quando o sistema estiver atrás de HTTPS

    @property
    def caminho_sqlite(self) -> Path | None:
        """Arquivo do banco, se for SQLite (usado pelo backup); None para outros bancos."""
        prefixo = "sqlite:///"
        return Path(self.database_url[len(prefixo):]) if self.database_url.startswith(prefixo) else None


def _caminho(texto: str) -> Path:
    """Caminho do .env: relativo à pasta do projeto, não à pasta de onde o programa foi aberto."""
    caminho = Path(texto)
    return caminho if caminho.is_absolute() else (RAIZ / caminho).resolve()


def _url_banco(texto: str | None, data_dir: Path) -> str:
    if not texto:
        return f"sqlite:///{(data_dir / 'db' / 'epi.sqlite3').as_posix()}"
    prefixo = "sqlite:///"
    if texto.startswith(prefixo) and not Path(texto[len(prefixo):]).is_absolute():
        return prefixo + _caminho(texto[len(prefixo):]).as_posix()
    return texto


def _inteiro(secao: dict, chave: str, onde: str, padrao: int, minimo: int) -> int:
    valor = secao.get(chave, padrao)
    if not isinstance(valor, (int, float)) or isinstance(valor, bool) or valor < minimo:
        raise ErroAjustes(f"{onde}.{chave} deve ser um número maior ou igual a {minimo} (valor atual: {valor!r})")
    return int(valor)


def carregar_ajustes(arquivo_env: Path | None = None, config_yaml: Path | None = None,
                     ambiente: Mapping[str, str] | None = None) -> Ajustes:
    """Lê o .env (as variáveis de ambiente do sistema têm prioridade) e as seções da Fase 2 do config.yaml.

    `ambiente` substitui o .env e as variáveis do sistema (usado nos testes).
    """
    if ambiente is None:
        ambiente = {**dotenv_values(arquivo_env or RAIZ / ".env"), **os.environ}
    valor = lambda chave, padrao="": (ambiente.get(chave) or padrao).strip()   # noqa: E731

    data_dir = _caminho(valor("DATA_DIR", "./data"))
    config_yaml = config_yaml or RAIZ / "config.yaml"
    try:
        dados = yaml.safe_load(Path(config_yaml).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as erro:
        raise ErroAjustes(f"Não foi possível ler {config_yaml}: {erro}") from erro

    turnos = {str(k): str(v) for k, v in (dados.get("turnos") or {}).items()}
    try:
        validar_turnos(turnos)
    except ValueError as erro:
        raise ErroAjustes(f"config.yaml, seção turnos: {erro}") from erro
    ocorrencias = dados.get("ocorrencias") or {}
    armazenamento = dados.get("armazenamento") or {}
    privacidade = dados.get("privacidade") or {}
    sim = lambda texto: texto.lower() in ("1", "true", "sim", "yes")   # noqa: E731
    try:
        porta = int(valor("PORTA", "8000"))
    except ValueError as erro:
        raise ErroAjustes(f"PORTA no .env deve ser um número (valor atual: {valor('PORTA')!r})") from erro
    return Ajustes(
        data_dir=data_dir,
        database_url=_url_banco(valor("DATABASE_URL"), data_dir),
        secret_key=valor("SECRET_KEY"),
        admin_login_inicial=valor("ADMIN_LOGIN_INICIAL", "admin"),
        admin_senha_inicial=valor("ADMIN_SENHA_INICIAL"),
        rtsp_usuario=valor("RTSP_USUARIO"),
        rtsp_senha=valor("RTSP_SENHA"),
        telegram_token=valor("TELEGRAM_TOKEN"),
        telegram_chat_id=valor("TELEGRAM_CHAT_ID"),
        config_yaml=Path(config_yaml),
        turnos=turnos,
        retencao_dias=_inteiro(ocorrencias, "retencao_dias", "ocorrencias", 30, 1),
        espaco_minimo_mb=float(_inteiro(armazenamento, "espaco_minimo_mb", "armazenamento", 500, 0)),
        backups_manter=_inteiro(armazenamento, "backups_manter", "armazenamento", 7, 1),
        uploads_max_idade_s=60 * _inteiro(armazenamento, "uploads_max_idade_min", "armazenamento", 60, 1),
        upload_tamanho_max_mb=_inteiro(armazenamento, "upload_tamanho_max_mb", "armazenamento", 200, 1),
        borrar_ao_vivo=bool(privacidade.get("borrar_ao_vivo", True)),
        host=valor("HOST", "127.0.0.1"),
        porta=porta,
        modo_desenvolvimento=sim(valor("MODO_DESENVOLVIMENTO", "false")),
        cookie_seguro=sim(valor("COOKIE_SEGURO", "false")),
    )


def config_da_camera(base: Config, linhas_epi: Iterable) -> Config:
    """Config da Fase 1 para uma câmera: padrões do config.yaml + EPIs e limiares do posto (tabela config_epi_camera).

    `linhas_epi` são objetos com epi, exigido, conf_min, persistencia_s, fracao_minima e parametros_extra.
    EPIs que ainda não foram implementados (só a máscara foi validada) ficam desligados, como na Fase 1.
    """
    epis = dict(base.epis)
    for linha in linhas_epi:
        padrao = base.epis.get(linha.epi) or ConfigEPI(nome=linha.epi, ativo=False, conf=linha.conf_min)
        extras = {**padrao.extras, **(linha.parametros_extra or {})}
        cobertura = float(extras.pop("cobertura_min", padrao.cobertura_min))
        epis[linha.epi] = replace(padrao, ativo=bool(linha.exigido) and linha.epi in EPIS_IMPLEMENTADOS,
                                  conf=float(linha.conf_min), persistencia_s=float(linha.persistencia_s),
                                  fracao_minima=float(linha.fracao_minima), cobertura_min=cobertura, extras=extras)
    return replace(base, epis=epis)


def epis_padrao(base: Config) -> list[dict]:
    """Linhas de config_epi_camera para uma câmera nova, copiadas do config.yaml."""
    return [{"epi": nome, "exigido": epi.ativo, "conf_min": epi.conf, "persistencia_s": epi.persistencia_s,
             "fracao_minima": epi.fracao_minima, "parametros_extra": {**epi.extras, "cobertura_min": epi.cobertura_min}}
            for nome, epi in base.epis.items()]


def preparar_pastas(data_dir: Path) -> None:
    """Cria a estrutura de DATA_DIR (db, ocorrencias, thumbnails, uploads_temp, relatorios, backups, logs)."""
    for nome in PASTAS_DADOS:
        (data_dir / nome).mkdir(parents=True, exist_ok=True)


def configurar_logging(pasta_logs: Path, nivel: int = logging.INFO) -> None:
    """Log no console e em data/logs/app.log, com rotação (RNF04). Pode ser chamada mais de uma vez."""
    raiz = logging.getLogger()
    raiz.setLevel(nivel)
    formato = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%d/%m/%Y %H:%M:%S")
    arquivo = (pasta_logs / "app.log").resolve()
    if not any(isinstance(h, RotatingFileHandler) and Path(h.baseFilename) == arquivo for h in raiz.handlers):
        pasta_logs.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(arquivo, maxBytes=TAMANHO_LOG_BYTES, backupCount=ARQUIVOS_LOG, encoding="utf-8")
        handler.setFormatter(formato)
        raiz.addHandler(handler)
    if not any(type(h) is logging.StreamHandler for h in raiz.handlers):
        console = logging.StreamHandler()
        console.setFormatter(formato)
        raiz.addHandler(console)
