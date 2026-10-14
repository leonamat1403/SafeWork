"""Sistema web (FastAPI): inicialização, rotas e encerramento.

Para rodar:  python -m app      (endereço e porta no .env: HOST, PORTA; padrão http://127.0.0.1:8000)

Ao iniciar: lê o .env e o config.yaml, aplica as migrações do banco, cria o administrador inicial e a câmera padrão
(1º uso), liga as câmeras ativas, a fila de uploads e as rotinas automáticas. Ao encerrar, desliga tudo.
"""
from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.auth import ControleTentativas, criar_admin_inicial
from app.config import Ajustes, carregar_ajustes, configurar_logging, epis_padrao, preparar_pastas
from app.database import aplicar_migracoes, criar_engine, criar_fabrica_sessoes
from app.models import Camera, ConfigEpiCamera
from app.privacy import Borrador, DetectorRostosQuadro
from app.registro import RegistradorOcorrencias
from app.rotas import acesso, cameras, ocorrencias, uploads
from app.scheduler import iniciar_agendador
from app.storage import StorageDisco
from app.stream import GerenciadorCameras
from app.uploads import FilaUploads
from src.config import Config, carregar_config
from src.detector import Detector
from src.video import FonteVideo

log = logging.getLogger("epi_solda")
VERSAO = "2.3"
CHAVE_PADRAO = "troque-esta-chave"


@dataclass
class Contexto:
    """Tudo o que as rotas usam (request.app.state.ctx)."""

    ajustes: Ajustes
    config_base: Config
    engine: Engine
    fabrica: sessionmaker[Session]
    storage: StorageDisco
    borrador: Borrador
    registrador: RegistradorOcorrencias
    cameras: GerenciadorCameras
    uploads: FilaUploads
    tentativas: ControleTentativas
    agendador: object | None = None


def criar_camera_padrao(fabrica: sessionmaker[Session], config: Config) -> bool:
    """1º uso: sem nenhuma câmera, cadastra a "Webcam 0" com os EPIs padrão do config.yaml."""
    with fabrica() as sessao:
        if sessao.scalars(select(Camera.id).limit(1)).first() is not None:
            return False
        sessao.add(Camera(nome_posto="Webcam 0", processo_solda="OUTRO", tipo="webcam", origem="0", ativa=True,
                          epis=[ConfigEpiCamera(**linha) for linha in epis_padrao(config)]))
        sessao.commit()
    log.info("Câmera padrão \"Webcam 0\" cadastrada (troque em Configurações).")
    return True


def _chave_da_sessao(ajustes: Ajustes) -> str:
    if ajustes.secret_key and ajustes.secret_key != CHAVE_PADRAO:
        return ajustes.secret_key
    if ajustes.modo_desenvolvimento:
        log.warning("SECRET_KEY não definida no .env: usando uma chave temporária (os logins caem ao reiniciar).")
        return secrets.token_hex(32)
    raise RuntimeError("Defina SECRET_KEY no .env (gere com: python -c \"import secrets; print(secrets.token_hex(32))\").")


def criar_app(ajustes: Ajustes | None = None, criar_detector: Callable[[Config], object] = Detector,
              criar_fonte: Callable[[str], object] = FonteVideo, iniciar_rotinas: bool = True) -> FastAPI:
    """Monta o sistema. Os parâmetros permitem trocar o detector e a câmera por simulações nos testes."""
    ajustes = ajustes or carregar_ajustes()
    chave = _chave_da_sessao(ajustes)

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        preparar_pastas(ajustes.data_dir)
        configurar_logging(ajustes.data_dir / "logs")
        aplicar_migracoes(ajustes.database_url)
        engine = criar_engine(ajustes.database_url)
        fabrica = criar_fabrica_sessoes(engine)
        config_base = carregar_config(ajustes.config_yaml)
        criar_admin_inicial(fabrica, ajustes)
        criar_camera_padrao(fabrica, config_base)
        storage = StorageDisco(ajustes.data_dir, ajustes.espaco_minimo_mb)
        borrador = Borrador(DetectorRostosQuadro(config_base.modelos.rosto, config_base.deteccao.conf_rosto),
                            config_base.deteccao.conf_keypoint)
        registrador = RegistradorOcorrencias(fabrica, storage, borrador, ajustes.turnos)
        # Ao vivo, só as cabeças da pose e os rostos já achados (sem rodar o detector de rostos de novo: CPU)
        borrador_ao_vivo = Borrador(None, config_base.deteccao.conf_keypoint) if ajustes.borrar_ao_vivo else None
        ctx = Contexto(
            ajustes=ajustes, config_base=config_base, engine=engine, fabrica=fabrica, storage=storage,
            borrador=borrador, registrador=registrador,
            cameras=GerenciadorCameras(ajustes, config_base, fabrica, registrador, borrador_ao_vivo, criar_detector,
                                       criar_fonte),
            uploads=FilaUploads(ajustes, config_base, fabrica, registrador, criar_detector),
            tentativas=ControleTentativas())
        app.state.ctx = ctx
        ctx.cameras.iniciar()
        ctx.uploads.iniciar()
        if iniciar_rotinas:
            ctx.agendador = iniciar_agendador(ajustes, fabrica, storage)
        log.info("Sistema iniciado (versão %s) em http://%s:%d", VERSAO, ajustes.host, ajustes.porta)
        try:
            yield
        finally:
            if ctx.agendador is not None:
                ctx.agendador.shutdown(wait=False)
            ctx.uploads.parar()
            ctx.cameras.parar()
            engine.dispose()
            log.info("Sistema encerrado.")

    desenvolvimento = ajustes.modo_desenvolvimento
    # Telemetria do FastAPI (OpenTelemetry) desligada: nada sai do computador e não gasta CPU (F2-D21)
    sem_telemetria = {"auto_configure": False, "tracing": False, "metrics": False, "logs": False,
                      "operation_spans": False}
    app = FastAPI(title="Verificador de EPIs de Solda", version=VERSAO, lifespan=ciclo_de_vida,
                  telemetry=sem_telemetria,
                  docs_url=None, redoc_url=None, openapi_url="/openapi.json" if desenvolvimento else None,
                  description="API do sistema (Fase 2). Faça POST /login, copie o csrf_token e cole em **Authorize**.")
    app.add_middleware(SessionMiddleware, secret_key=chave, session_cookie="epi_sessao", max_age=8 * 3600,
                       same_site="lax", https_only=ajustes.cookie_seguro)

    @app.middleware("http")
    async def cabecalhos_de_seguranca(request: Request, chamar_proximo):
        resposta = await chamar_proximo(request)
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("X-Frame-Options", "DENY")
        resposta.headers.setdefault("Referrer-Policy", "same-origin")
        if request.url.path.startswith(("/api/", "/midia/")):
            resposta.headers.setdefault("Cache-Control", "no-store, private")
        return resposta

    if desenvolvimento:   # documentação interativa só para testes (MODO_DESENVOLVIMENTO=true no .env)
        @app.get("/docs", include_in_schema=False)
        def documentacao():
            return get_swagger_ui_html(openapi_url="/openapi.json", title="Verificador de EPIs – API",
                                       swagger_ui_parameters={"withCredentials": True, "persistAuthorization": True})

    for modulo in (acesso, cameras, uploads, ocorrencias):
        app.include_router(modulo.rotas)
    return app
