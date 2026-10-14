"""Câmeras ao vivo (RF01, RF05): uma thread por câmera ativa, que lê, detecta, registra ocorrências e guarda o
último quadro anotado (JPEG) para o stream MJPEG e o status para o painel (docs/arquitetura_fase2.md, seção 6).

A câmera é processada mesmo sem ninguém olhando a tela: o registro das ocorrências não depende do navegador.
Cada thread tem o seu próprio detector (o YOLO não pode ser usado por duas threads ao mesmo tempo).
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import RAIZ, Ajustes, config_da_camera
from app.models import Camera, MetricaSessao
from app.privacy import Borrador, ImagemBorrada
from app.registro import RegistradorOcorrencias
from app.tempo import agora_utc, para_local
from src.config import Config
from src.detector import Detector, ErroModelo
from src.occurrences import GerenciadorOcorrencias
from src.pipeline import Pipeline, ResultadoFrame, desenhar
from src.tipos import Estado
from src.video import ErroFonte, FonteVideo, ocultar_senha

log = logging.getLogger("epi_solda.cameras")

LARGURA_STREAM = 1280          # o stream vai reduzido para o navegador (banda e CPU)
QUALIDADE_STREAM = 70
INTERVALO_METRICAS_S = 60      # metricas_sessao é atualizada a cada minuto
ESPERA_MAX_RECONEXAO_S = 30
QUADROS_POR_SEGUNDO_MJPEG = 10


def jpeg(img: np.ndarray, largura_max: int = LARGURA_STREAM, qualidade: int = QUALIDADE_STREAM) -> bytes:
    """Codifica em JPEG, reduzindo para no máximo `largura_max` pixels de largura."""
    altura, largura = img.shape[:2]
    if largura > largura_max:   # interpolação linear: bem mais rápida que INTER_AREA em quadros 4K
        img = cv2.resize(img, (largura_max, round(altura * largura_max / largura)), interpolation=cv2.INTER_LINEAR)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, qualidade])[1].tobytes()


def quadro_aviso(texto: str, detalhe: str = "", largura: int = 960, altura: int = 540) -> bytes:
    """Quadro cinza com um aviso (CÂMERA OFFLINE, PAUSADO...), mostrado no lugar do vídeo."""
    img = np.full((altura, largura, 3), 45, np.uint8)
    for i, (linha, escala) in enumerate(((texto, 1.4), (detalhe, 0.7))):
        if not linha:
            continue
        (w, h), _ = cv2.getTextSize(linha, cv2.FONT_HERSHEY_SIMPLEX, escala, 2)
        cv2.putText(img, linha, ((largura - w) // 2, altura // 2 + i * 50), cv2.FONT_HERSHEY_SIMPLEX, escala,
                    (230, 230, 230), 2, cv2.LINE_AA)
    return jpeg(img)


def origem_da_camera(tipo: str, origem: str, ajustes: Ajustes) -> str:
    """O que passar para a FonteVideo: índice da webcam, caminho do arquivo ou URL RTSP com usuário e senha do .env
    (F2-D10: a senha não fica no banco)."""
    if tipo == "arquivo":
        caminho = Path(origem)
        return str(caminho if caminho.is_absolute() else (RAIZ / caminho).resolve())
    if tipo == "rtsp" and ajustes.rtsp_usuario:
        partes = urlsplit(origem)
        if "@" not in partes.netloc:
            credenciais = quote(ajustes.rtsp_usuario, safe="") + ":" + quote(ajustes.rtsp_senha, safe="")
            return urlunsplit(partes._replace(netloc=f"{credenciais}@{partes.netloc}"))
    return origem


def status_das_pessoas(resultado: ResultadoFrame) -> list[dict]:
    """Status de cada pessoa para o painel ao vivo (T02): cor, rótulo e estado de cada EPI."""
    pessoas = []
    for aval in resultado.avaliacoes:
        pessoas.append({
            "track_id": aval.pessoa.track_id,
            "cor": aval.cor,
            "rotulo": aval.rotulo,
            "mascara_levantada": aval.mascara_levantada,
            "epis": {nome: {"estado": epi.estado.value, "motivo": epi.motivo,
                            "conf": round(epi.conf, 2) if epi.conf is not None else None}
                     for nome, epi in aval.epis.items()},
        })
    return pessoas


class TrabalhadorCamera(threading.Thread):
    """Processa uma câmera: FonteVideo -> Pipeline -> desenho -> JPEG em memória; ocorrências -> RegistradorOcorrencias."""

    def __init__(self, camera_id: int, nome: str, origem: str, config: Config, registrador: RegistradorOcorrencias,
                 fabrica: sessionmaker[Session], borrador_ao_vivo: Borrador | None,
                 criar_detector: Callable[[Config], object], criar_fonte: Callable[[str], object]) -> None:
        super().__init__(name=f"camera-{camera_id}", daemon=True)
        self.camera_id, self.nome, self.origem, self.config = camera_id, nome, origem, config
        self.registrador, self.fabrica, self.borrador_ao_vivo = registrador, fabrica, borrador_ao_vivo
        self.criar_detector, self.criar_fonte = criar_detector, criar_fonte
        self.parar_evento = threading.Event()
        self.pausada = False
        self._trava = threading.Lock()
        self._jpeg = quadro_aviso("INICIANDO...", nome)
        self._quadro: np.ndarray | None = None              # último frame original (só em memória, para o snapshot)
        self._resultado: ResultadoFrame | None = None
        self.online = False
        self.erro: str | None = None
        self.fps = 0.0
        self.saturado = False
        self.fracao_saturada = 0.0
        self.pessoas: list[dict] = []
        self.ultimas: deque[dict] = deque(maxlen=5)
        self._metrica_id: int | None = None
        self._contagem = {"frames": 0, "ignorados": 0, "pessoas": 0, Estado.CONFORME: 0, Estado.NAO_CONFORME: 0,
                          Estado.INDETERMINADO: 0}

    # ---------------------------------------------------------------- leitura pelas rotas (outras threads)
    @property
    def ultimo_jpeg(self) -> bytes:
        with self._trava:
            return self._jpeg

    def instantaneo(self) -> tuple[np.ndarray, ResultadoFrame] | None:
        """Último frame original e o resultado dele (para o snapshot, que sai borrado)."""
        with self._trava:
            if self._quadro is None or self._resultado is None:
                return None
            return self._quadro.copy(), self._resultado

    def status(self) -> dict:
        with self._trava:
            return {
                "camera_id": self.camera_id, "nome": self.nome, "online": self.online, "pausada": self.pausada,
                "erro": self.erro, "fps": round(self.fps, 1), "saturado": self.saturado,
                "fracao_saturada": round(self.fracao_saturada, 3), "pessoas": list(self.pessoas),
                "ultimas_ocorrencias": list(self.ultimas), "sem_espaco": self.registrador.sem_espaco,
            }

    def parar(self) -> None:
        self.parar_evento.set()

    # ---------------------------------------------------------------- thread
    def _publicar(self, jpeg_bytes: bytes, **estado) -> None:
        with self._trava:
            self._jpeg = jpeg_bytes
            for chave, valor in estado.items():
                setattr(self, chave, valor)

    def _desenhar(self, frame: np.ndarray, resultado: ResultadoFrame) -> np.ndarray:
        """Quadro do stream: borrado (se configurado, F2-D20) e com caixas, rótulos e FPS."""
        if self.borrador_ao_vivo is not None:
            pessoas = [a.pessoa for a in resultado.avaliacoes]
            rostos = [r.caixa for r in (resultado.rostos or [])]
            base: np.ndarray | ImagemBorrada = self.borrador_ao_vivo.borrar(frame, pessoas, rostos)
            return base.com_desenho(lambda img: desenhar(img, resultado, [f"{self.nome} | {self.fps:.1f} FPS"])).pixels
        return desenhar(frame, resultado, [f"{self.nome} | {self.fps:.1f} FPS"])

    def _registrar(self, ocorrencias, frame: np.ndarray, resultado: ResultadoFrame) -> None:
        for oc in ocorrencias:
            try:
                registro = self.registrador.registrar(oc, frame, resultado, self.camera_id)
            except Exception:   # um erro no banco não pode parar a câmera
                log.exception("Câmera %s: falha ao registrar ocorrência", self.nome)
                continue
            with self._trava:
                self.ultimas.appendleft({
                    "uuid": registro.uuid, "data_hora": registro.data_hora.isoformat(),
                    "hora_local": para_local(registro.data_hora).strftime("%H:%M:%S"),
                    "epis_faltantes": registro.epis_faltantes, "mascara_levantada": registro.mascara_levantada,
                    "thumb_url": f"/midia/{registro.uuid}?tipo=thumb"})

    def _contar(self, resultado: ResultadoFrame) -> None:
        c = self._contagem
        c["frames"] += 1
        if resultado.saturado:
            c["ignorados"] += 1
            return
        for aval in resultado.avaliacoes:
            c["pessoas"] += 1
            estados = {e.estado for e in aval.epis.values()}
            pior = (Estado.NAO_CONFORME if Estado.NAO_CONFORME in estados else
                    Estado.INDETERMINADO if Estado.INDETERMINADO in estados or not estados else Estado.CONFORME)
            c[pior] += 1

    def _salvar_metricas(self, fim: bool = False) -> None:
        """Taxa de conformidade da sessão, sem imagens (tabela metricas_sessao)."""
        c = self._contagem
        try:
            with self.fabrica() as sessao:
                if self._metrica_id is None:
                    metrica = MetricaSessao(camera_id=self.camera_id, inicio=agora_utc())
                    sessao.add(metrica)
                else:
                    metrica = sessao.get(MetricaSessao, self._metrica_id)
                metrica.fps_medio = round(self.fps, 2)
                metrica.frames_ignorados_saturacao = c["ignorados"]
                metrica.total_pessoas_avaliadas = c["pessoas"]
                metrica.total_conformes = c[Estado.CONFORME]
                metrica.total_nao_conformes = c[Estado.NAO_CONFORME]
                metrica.total_indeterminados = c[Estado.INDETERMINADO]
                if fim:
                    metrica.fim = agora_utc()
                sessao.commit()
                self._metrica_id = metrica.id
        except Exception:
            log.exception("Câmera %s: falha ao salvar as métricas da sessão", self.nome)

    def _abrir_fonte(self, espera: float):
        """Abre a câmera; se falhar, mostra "CÂMERA OFFLINE" e espera (1, 2, 4... até 30 s) antes de tentar de novo."""
        try:
            fonte = self.criar_fonte(self.origem)
        except ErroFonte as erro:
            self._publicar(quadro_aviso("CAMERA OFFLINE", "nova tentativa em instantes"), online=False, erro=str(erro))
            log.warning("Câmera %s offline: %s", self.nome, ocultar_senha(str(erro)))
            self.parar_evento.wait(espera)
            return None
        self._publicar(self.ultimo_jpeg, online=True, erro=None)
        log.info("Câmera %s conectada (%s)", self.nome, ocultar_senha(self.origem))
        return fonte

    def run(self) -> None:
        try:
            detector = self.criar_detector(self.config)
        except ErroModelo as erro:
            self._publicar(quadro_aviso("MODELO NAO CARREGADO", "veja o aviso no painel"), erro=str(erro))
            log.error("Câmera %s: %s", self.nome, erro)
            return
        pipeline, gerenciador = Pipeline(self.config, detector), GerenciadorOcorrencias(self.config)
        pular = max(1, self.config.deteccao.pular_frames)
        fonte, espera, n = None, 1.0, 0
        inicio_fps, frames_fps, ultima_metrica = time.monotonic(), 0, time.monotonic()
        self._salvar_metricas()
        try:
            while not self.parar_evento.is_set():
                if fonte is None:
                    fonte = self._abrir_fonte(espera)
                    espera = 1.0 if fonte is not None else min(espera * 2, ESPERA_MAX_RECONEXAO_S)
                    continue
                if self.pausada:
                    self._publicar(quadro_aviso("PAUSADO", self.nome))
                    self.parar_evento.wait(0.3)
                    continue
                frame, t = fonte.ler(self.parar_evento)
                if frame is None:
                    if getattr(fonte, "tipo", "") == "arquivo":     # vídeo de teste: recomeça do início
                        fonte.fechar()
                        fonte = None
                    continue
                n += 1
                if n % pular:
                    continue
                inicio_quadro = time.monotonic()
                resultado = pipeline.processar(frame)
                self._registrar(gerenciador.atualizar(resultado.avaliacoes, t, n, resultado.saturado), frame,
                                resultado)
                self._contar(resultado)
                frames_fps += 1
                agora = time.monotonic()
                if agora - inicio_fps >= 2:
                    self.fps, inicio_fps, frames_fps = frames_fps / (agora - inicio_fps), agora, 0
                quadro = jpeg(self._desenhar(frame, resultado))
                with self._trava:
                    self._quadro, self._resultado = frame, resultado
                self._publicar(quadro, online=True, saturado=resultado.saturado,
                               fracao_saturada=resultado.fracao_saturada, pessoas=status_das_pessoas(resultado))
                if agora - ultima_metrica >= INTERVALO_METRICAS_S:
                    self._salvar_metricas()
                    ultima_metrica = agora
                if getattr(fonte, "tipo", "") == "arquivo" and fonte.fps:   # arquivo: no ritmo do vídeo
                    self.parar_evento.wait(max(0.0, pular / fonte.fps - (time.monotonic() - inicio_quadro)))
        except Exception as erro:
            log.exception("Câmera %s: erro inesperado; a thread foi encerrada", self.nome)
            self._publicar(quadro_aviso("ERRO NA CAMERA", "veja o log do sistema"), online=False, erro=str(erro))
        finally:
            if fonte is not None:
                fonte.fechar()
            self._salvar_metricas(fim=True)


class GerenciadorCameras:
    """Liga uma thread para cada câmera ativa e dá acesso a elas pelas rotas."""

    def __init__(self, ajustes: Ajustes, config_base: Config, fabrica: sessionmaker[Session],
                 registrador: RegistradorOcorrencias, borrador_ao_vivo: Borrador | None,
                 criar_detector: Callable[[Config], object] = Detector,
                 criar_fonte: Callable[[str], object] = FonteVideo) -> None:
        self.ajustes, self.config_base, self.fabrica = ajustes, config_base, fabrica
        self.registrador, self.borrador_ao_vivo = registrador, borrador_ao_vivo
        self.criar_detector, self.criar_fonte = criar_detector, criar_fonte
        self._trabalhadores: dict[int, TrabalhadorCamera] = {}

    def iniciar(self) -> None:
        with self.fabrica() as sessao:
            cameras = sessao.scalars(select(Camera).where(Camera.ativa.is_(True)).order_by(Camera.id)).all()
            dados = [(c.id, c.nome_posto, c.tipo, c.origem, list(c.epis)) for c in cameras]
        for camera_id, nome, tipo, origem, epis in dados:
            trabalhador = TrabalhadorCamera(
                camera_id, nome, origem_da_camera(tipo, origem, self.ajustes),
                config_da_camera(self.config_base, epis), self.registrador, self.fabrica, self.borrador_ao_vivo,
                self.criar_detector, self.criar_fonte)
            self._trabalhadores[camera_id] = trabalhador
            trabalhador.start()
        log.info("%d câmera(s) ativa(s) iniciada(s)", len(dados))

    def parar(self, espera_s: float = 10) -> None:
        for trabalhador in self._trabalhadores.values():
            trabalhador.parar()
        for trabalhador in self._trabalhadores.values():
            trabalhador.join(espera_s)
        self._trabalhadores.clear()

    def obter(self, camera_id: int) -> TrabalhadorCamera | None:
        return self._trabalhadores.get(camera_id)

    def ids(self) -> list[int]:
        return list(self._trabalhadores)


async def gerar_mjpeg(trabalhador: TrabalhadorCamera, desconectado: Callable[[], object],
                      quadros_por_segundo: float = QUADROS_POR_SEGUNDO_MJPEG,
                      max_quadros: int | None = None) -> AsyncIterator[bytes]:
    """Partes do stream MJPEG (multipart/x-mixed-replace): o navegador troca a imagem a cada parte recebida.

    Cada navegador recebe o último quadro pronto; vários supervisores olhando não aumentam o custo da detecção.
    """
    anterior, enviados = None, 0
    while not await desconectado():
        quadro = trabalhador.ultimo_jpeg
        if quadro is not anterior:
            yield (b"--quadro\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(quadro)).encode()
                   + b"\r\n\r\n" + quadro + b"\r\n")
            anterior, enviados = quadro, enviados + 1
            if max_quadros is not None and enviados >= max_quadros:
                return
        await asyncio.sleep(1 / quadros_por_segundo)
