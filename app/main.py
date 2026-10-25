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
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app import VERSAO, paginas
from app.auth import ControleTentativas, criar_admin_inicial
from app.config import Ajustes, carregar_ajustes, configurar_logging, epis_padrao, preparar_pastas
from app.database import aplicar_migracoes, criar_engine, criar_fabrica_sessoes
from app.models import Camera, ConfigEpiCamera
from app.privacy import Borrador, DetectorRostosQuadro
from app.registro import RegistradorOcorrencias
from app.rotas import acesso, cameras, configuracoes, ocorrencias, painel, relatorios, uploads, usuarios
from app import sistema
from app.notificador import Enviar, Notificador, enviar_http
from app.scheduler import iniciar_agendador
from app.storage import StorageDisco
from app.stream import GerenciadorCameras
from app.uploads import FilaUploads
from src.config import Config, carregar_config
from src.detector import Detector
from src.video import FonteVideo

log = logging.getLogger("epi_solda")
CHAVE_PADRAO = "troque-esta-chave"
PASTA_ESTATICOS = Path(__file__).resolve().parent / "static"   # só css, js, ícones e fontes: NUNCA imagens de ocorrências
# Páginas: o navegador só carrega scripts, estilos, fontes e imagens do próprio sistema (sem nada de fora, sem
# scripts embutidos no HTML). A documentação /docs (modo desenvolvimento) fica de fora porque usa arquivos da internet.
POLITICA_CONTEUDO = ("default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; "
                     "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; "
                     "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


@dataclass
class Contexto:
    """Tudo o que as rotas usam (request.app.state.ctx)."""

    ajustes: Ajustes                 # em uso: .env + config.yaml + aba Sistema (config_sistema)
    config_base: Config              # em uso: config.yaml + aba Sistema
    engine: Engine                           # conexão com o banco
    fabrica: sessionmaker[Session]           # cria uma sessão do banco por operação
    storage: StorageDisco                    # grava e lê imagens/vídeos de ocorrências no disco
    borrador: Borrador                       # borra rostos (privacidade) nas imagens guardadas
    registrador: RegistradorOcorrencias      # transforma ocorrências detectadas em registros do banco
    cameras: GerenciadorCameras              # uma tarefa de análise por câmera ativa
    uploads: FilaUploads                     # fila de vídeos/fotos enviados pelo usuário
    tentativas: ControleTentativas           # limite de tentativas de login erradas
    notificador: Notificador | None = None   # RD09: alerta pelo Telegram
    config_yaml: Config | None = None     # como veio do config.yaml (base para reaplicar a aba Sistema)
    ajustes_yaml: Ajustes | None = None
    agendador: object | None = None       # rotinas automáticas (limpeza, backup); None nos testes


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
    """Chave que assina o cookie de sessão; sem chave no .env só é aceita a temporária, e só em desenvolvimento."""
    if ajustes.secret_key and ajustes.secret_key != CHAVE_PADRAO:
        return ajustes.secret_key
    if ajustes.modo_desenvolvimento:
        log.warning("SECRET_KEY não definida no .env: usando uma chave temporária (os logins caem ao reiniciar).")
        return secrets.token_hex(32)
    raise RuntimeError("Defina SECRET_KEY no .env (gere com: python -c \"import secrets; print(secrets.token_hex(32))\").")


def criar_app(ajustes: Ajustes | None = None, criar_detector: Callable[[Config], object] = Detector,
              criar_fonte: Callable[[str], object] = FonteVideo, iniciar_rotinas: bool = True,
              enviar_telegram: Enviar = enviar_http) -> FastAPI:
    """Monta o sistema. Os parâmetros permitem trocar o detector, a câmera e o envio ao Telegram por simulações nos
    testes (os testes nunca usam a rede)."""
    ajustes = ajustes or carregar_ajustes()
    chave = _chave_da_sessao(ajustes)

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        """Liga tudo ao iniciar (banco, câmeras, uploads, rotinas) e desliga na ordem inversa ao encerrar."""
        preparar_pastas(ajustes.data_dir)
        configurar_logging(ajustes.data_dir / "logs")
        aplicar_migracoes(ajustes.database_url)
        engine = criar_engine(ajustes.database_url)
        fabrica = criar_fabrica_sessoes(engine)
        config_yaml = carregar_config(ajustes.config_yaml)
        criar_admin_inicial(fabrica, ajustes)   # as migrações já criaram as tabelas; aqui entram os dados do 1º uso
        criar_camera_padrao(fabrica, config_yaml)
        # O que o ADMIN mudou na aba Sistema (RD05) vale por cima do config.yaml
        config_base, em_uso = sistema.aplicar(config_yaml, ajustes, sistema.ler_banco(fabrica))
        storage = StorageDisco(ajustes.data_dir, ajustes.espaco_minimo_mb)
        borrador = Borrador(DetectorRostosQuadro(config_base.modelos.rosto, config_base.deteccao.conf_rosto),
                            config_base.deteccao.conf_keypoint)
        registrador = RegistradorOcorrencias(fabrica, storage, borrador, em_uso.turnos)
        notificador = Notificador(em_uso, storage, fabrica, enviar_telegram)
        registrador.notificador = notificador
        # Ao vivo, só as cabeças da pose e os rostos já achados (sem rodar o detector de rostos de novo: CPU)
        borrador_ao_vivo = Borrador(None, config_base.deteccao.conf_keypoint) if ajustes.borrar_ao_vivo else None
        ctx = Contexto(
            ajustes=em_uso, config_base=config_base, engine=engine, fabrica=fabrica, storage=storage,
            borrador=borrador, registrador=registrador,
            cameras=GerenciadorCameras(em_uso, config_base, fabrica, registrador, borrador_ao_vivo, criar_detector,
                                       criar_fonte),
            uploads=FilaUploads(em_uso, config_base, fabrica, registrador, criar_detector),
            tentativas=ControleTentativas(), notificador=notificador, config_yaml=config_yaml, ajustes_yaml=ajustes)
        app.state.ctx = ctx
        notificador.iniciar()
        ctx.cameras.iniciar()
        ctx.uploads.iniciar()
        if iniciar_rotinas:
            ctx.agendador = iniciar_agendador(em_uso, fabrica, storage)
        log.info("Sistema iniciado (versão %s) em http://%s:%d", VERSAO, ajustes.host, ajustes.porta)
        try:
            yield
        finally:
            if ctx.agendador is not None:
                ctx.agendador.shutdown(wait=False)
            ctx.uploads.parar()
            ctx.cameras.parar()
            notificador.parar()
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
        """Acrescenta a toda resposta os cabeçalhos de segurança; API, mídia e páginas não ficam em cache (privacidade)."""
        resposta = await chamar_proximo(request)
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("X-Frame-Options", "DENY")
        resposta.headers.setdefault("Referrer-Policy", "same-origin")
        if request.url.path.startswith(("/api/", "/midia/")):
            resposta.headers.setdefault("Cache-Control", "no-store, private")
        if resposta.headers.get("content-type", "").startswith("text/html") and request.url.path != "/docs":
            resposta.headers.setdefault("Content-Security-Policy", POLITICA_CONTEUDO)
            resposta.headers.setdefault("Cache-Control", "no-store, private")
        return resposta

    if desenvolvimento:   # documentação interativa só para testes (MODO_DESENVOLVIMENTO=true no .env)
        @app.get("/docs", include_in_schema=False)
        def documentacao():
            """Página Swagger da API, usada só no modo de desenvolvimento."""
            return get_swagger_ui_html(openapi_url="/openapi.json", title="Verificador de EPIs – API",
                                       swagger_ui_parameters={"withCredentials": True, "persistAuthorization": True})

    for modulo in (acesso, cameras, configuracoes, uploads, ocorrencias, painel, relatorios, usuarios, paginas):
        app.include_router(modulo.rotas)
    app.mount("/static", StaticFiles(directory=PASTA_ESTATICOS), name="static")
    return app
