"""Tabelas do banco (docs/arquitetura_fase2.md, seção 3).

O banco guarda só o CAMINHO RELATIVO das imagens (dentro de DATA_DIR), nunca a imagem. Nenhuma tabela identifica o
trabalhador (RF26): o track_id é um número temporário do rastreamento.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, TypeDecorator
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.tempo import agora_utc
from src.config import EPIS_CONHECIDOS

PERFIS = ("ADMIN", "SUPERVISOR")
PROCESSOS_SOLDA = ("MIG_MAG", "TIG", "ELETRODO", "CORTE", "OUTRO")
TIPOS_CAMERA = ("webcam", "rtsp", "arquivo")
VALIDACOES = ("PENDENTE", "CONFIRMADA", "FALSO_POSITIVO")
ORIGENS = ("ao_vivo", "upload")
ACOES_AUDITORIA = ("login", "login_falhou", "logout", "alterar_config", "gerenciar_usuario", "exportar", "excluir",
                   "validar", "retencao")


class DataHoraUTC(TypeDecorator):
    """Data/hora sempre em UTC. Recusa valores sem fuso (evita misturar horário local e UTC no banco)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, valor: datetime | None, dialect) -> datetime | None:
        if valor is None:
            return None
        if valor.tzinfo is None:
            raise ValueError("Data/hora sem fuso: use app.tempo.agora_utc() ou para_utc()")
        return valor.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, valor: datetime | None, dialect) -> datetime | None:
        return None if valor is None else valor.replace(tzinfo=timezone.utc)


def _uma_das(coluna: str, valores: tuple[str, ...]) -> CheckConstraint:
    """Restrição "coluna IN (...)": o banco recusa valores fora da lista."""
    lista = ", ".join(f"'{v}'" for v in valores)
    return CheckConstraint(f"{coluna} IN ({lista})", name=coluna)


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (_uma_das("perfil", PERFIS),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    login: Mapped[str] = mapped_column(String(50), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(100))
    perfil: Mapped[str] = mapped_column(String(20))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    deve_trocar_senha: Mapped[bool] = mapped_column(Boolean, default=False)   # 1º acesso do admin do .env (F2-D9)
    criado_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora_utc)


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (_uma_das("processo_solda", PROCESSOS_SOLDA), _uma_das("tipo", TIPOS_CAMERA))

    id: Mapped[int] = mapped_column(primary_key=True)
    nome_posto: Mapped[str] = mapped_column(String(100))
    processo_solda: Mapped[str] = mapped_column(String(20), default="OUTRO")
    tipo: Mapped[str] = mapped_column(String(10))
    origem: Mapped[str] = mapped_column(String(500))             # índice da webcam ou URL SEM senha (F2-D10)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    roi_poligono: Mapped[list | None] = mapped_column(JSON)      # zona de interesse (RD06)
    criado_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora_utc, onupdate=agora_utc)

    epis: Mapped[list[ConfigEpiCamera]] = relationship(back_populates="camera", cascade="all, delete-orphan")


class ConfigEpiCamera(Base):
    """EPIs exigidos e limiares de cada posto (RF13). Persistência em segundos com maioria, como na Fase 1 (F2-D7)."""

    __tablename__ = "config_epi_camera"
    __table_args__ = (
        UniqueConstraint("camera_id", "epi"),
        _uma_das("epi", EPIS_CONHECIDOS),
        CheckConstraint("conf_min >= 0 AND conf_min <= 1", name="conf_min"),
        CheckConstraint("persistencia_s > 0", name="persistencia_s"),
        CheckConstraint("fracao_minima > 0 AND fracao_minima <= 1", name="fracao_minima"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"))
    epi: Mapped[str] = mapped_column(String(20))
    exigido: Mapped[bool] = mapped_column(Boolean, default=True)
    conf_min: Mapped[float] = mapped_column(Float)
    persistencia_s: Mapped[float] = mapped_column(Float, default=4.0)
    fracao_minima: Mapped[float] = mapped_column(Float, default=0.75)
    parametros_extra: Mapped[dict] = mapped_column(JSON, default=dict)   # ex.: levantada_nao_conforme, regra de luvas

    camera: Mapped[Camera] = relationship(back_populates="epis")


class Ocorrencia(Base):
    """Uma não conformidade registrada. A imagem (já borrada) fica em DATA_DIR; aqui só o caminho relativo."""

    __tablename__ = "ocorrencias"
    __table_args__ = (_uma_das("validacao", VALIDACOES), _uma_das("origem", ORIGENS))

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="RESTRICT"), index=True)
    data_hora: Mapped[datetime] = mapped_column(DataHoraUTC, index=True)
    turno: Mapped[str | None] = mapped_column(String(10))
    track_id: Mapped[int] = mapped_column(Integer)
    epis_faltantes: Mapped[list] = mapped_column(JSON)
    epis_indeterminados: Mapped[list] = mapped_column(JSON, default=list)
    confianca_media: Mapped[dict] = mapped_column(JSON, default=dict)
    situacao: Mapped[dict] = mapped_column(JSON, default=dict)              # EPI -> motivo (ex.: "máscara levantada")
    fracao_nao_conforme: Mapped[dict] = mapped_column(JSON, default=dict)   # EPI -> fração em falta na janela de 4 s
    mascara_levantada: Mapped[bool] = mapped_column(Boolean, default=False)
    arco_ativo: Mapped[bool] = mapped_column(Boolean, default=False)        # RD03
    caminho_imagem: Mapped[str | None] = mapped_column(String(200))         # None: disco cheio (RNF03)
    caminho_thumb: Mapped[str | None] = mapped_column(String(200))
    validacao: Mapped[str] = mapped_column(String(20), default="PENDENTE", index=True)
    validado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    validado_em: Mapped[datetime | None] = mapped_column(DataHoraUTC)
    origem: Mapped[str] = mapped_column(String(10), default="ao_vivo")


class MetricaSessao(Base):
    """Período em que uma câmera ficou ligada: taxa de conformidade sem guardar imagens."""

    __tablename__ = "metricas_sessao"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    inicio: Mapped[datetime] = mapped_column(DataHoraUTC)
    fim: Mapped[datetime | None] = mapped_column(DataHoraUTC)
    fps_medio: Mapped[float] = mapped_column(Float, default=0.0)
    frames_ignorados_saturacao: Mapped[int] = mapped_column(Integer, default=0)
    total_pessoas_avaliadas: Mapped[int] = mapped_column(Integer, default=0)
    total_conformes: Mapped[int] = mapped_column(Integer, default=0)
    total_nao_conformes: Mapped[int] = mapped_column(Integer, default=0)
    total_indeterminados: Mapped[int] = mapped_column(Integer, default=0)


class Auditoria(Base):
    """Quem fez o quê e quando (RF25). usuario_id vazio = ação do próprio sistema (ex.: retenção)."""

    __tablename__ = "auditoria"
    __table_args__ = (_uma_das("acao", ACOES_AUDITORIA),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    acao: Mapped[str] = mapped_column(String(30))
    detalhes: Mapped[dict] = mapped_column(JSON, default=dict)
    data_hora: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora_utc, index=True)


class ConfigSistema(Base):
    """Ajustes feitos pela tela de Configurações (RD05), por cima do config.yaml (F2-D8)."""

    __tablename__ = "config_sistema"

    chave: Mapped[str] = mapped_column(String(50), primary_key=True)
    valor: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    atualizado_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora_utc, onupdate=agora_utc)
    atualizado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
