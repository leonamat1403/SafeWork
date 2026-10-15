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
from dataclasses import replace
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.calibracao import dados_calibracao, desenhar_calibracao
from app.config import RAIZ, Ajustes, config_da_camera
from app.models import Camera, MetricaSessao
from app.privacy import Borrador, ImagemBorrada
from app.registro import RegistradorOcorrencias
from app.tempo import agora_utc, para_local
from src.config import Config
from src.detector import Detector, ErroModelo
from src.occurrences import GerenciadorOcorrencias
from src.pipeline import Pipeline, ResultadoFrame, desenhar
from src.votacao import VotacaoTemporal
from src.zona import desenhar_zona
from src.tipos import Estado
from src.video import ErroFonte, FonteVideo, ocultar_senha

log = logging.getLogger("epi_solda.cameras")

LARGURA_STREAM = 1280          # o stream vai reduzido para o navegador (banda e CPU)
QUALIDADE_STREAM = 70
INTERVALO_METRICAS_S = 60      # metricas_sessao é atualizada a cada minuto
ESPERA_MAX_RECONEXAO_S = 30
QUADROS_POR_SEGUNDO_MJPEG = 10
PASSO_CORDAO_S = 10            # cordão do turno (T02): um trecho a cada 10 segundos
HORAS_CORDAO = 12              # guarda no máximo 12 h de trechos na memória
# Código de cada trecho do cordão: V = câmera ligada sem ninguém, C = conforme, I = indeterminado, N = não conforme.
# Cada quadro vale o pior estado entre as pessoas dele; o trecho mostra o estado que PREDOMINOU nos quadros (F2-D24):
# um quadro isolado errado não pinta 10 s de vermelho (as ocorrências exigem 4 s; o cordão não pode ser mais nervoso).
# Trecho ausente ("-") = câmera parada, pausada ou só quadros estourados pelo arco.
GRAVIDADE_CORDAO = {"V": 0, "C": 1, "I": 2, "N": 3}
CODIGO_ESTADO = {Estado.CONFORME: "C", Estado.INDETERMINADO: "I", Estado.NAO_CONFORME: "N"}
FRACAO_PESSOAS_CORDAO = 0.25   # com gente em menos de 1/4 dos quadros do trecho, ele conta como "ninguém no quadro"
CALIBRACAO_ATIVA_S = 5         # RD02: o quadro de calibração só é desenhado enquanto alguém olha a tela T07


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


def pior_estado(aval) -> Estado:
    """Estado da pessoa: NÃO CONFORME se algum EPI faltar; INDETERMINADO se algum não for visível; senão CONFORME."""
    estados = {e.estado for e in aval.epis.values()}
    if Estado.NAO_CONFORME in estados:
        return Estado.NAO_CONFORME
    if Estado.INDETERMINADO in estados or not estados:
        return Estado.INDETERMINADO
    return Estado.CONFORME


def codigo_do_trecho(quadros: list[int] | None) -> str:
    """Estado que predominou num trecho do cordão, a partir da contagem de quadros [V, C, I, N] (F2-D24)."""
    if quadros is None:
        return "-"
    vazios, conformes, indeterminados, nao_conformes = quadros
    com_pessoas = conformes + indeterminados + nao_conformes
    if com_pessoas == 0 or com_pessoas < FRACAO_PESSOAS_CORDAO * (com_pessoas + vazios):
        return "V"
    if 2 * nao_conformes >= com_pessoas:      # metade ou mais dos quadros com a falta
        return "N"
    if 2 * conformes > com_pessoas:
        return "C"
    return "I"                                 # mistura sem maioria: incerto


def status_das_pessoas(resultado: ResultadoFrame) -> list[dict]:
    """Status de cada pessoa para o painel ao vivo (T02): cor, rótulo e estado de cada EPI."""
    pessoas = []
    for aval in resultado.avaliacoes:
        pessoas.append({
            "track_id": aval.pessoa.track_id,
            "cor": aval.cor,
            "rotulo": aval.rotulo,
            "mascara_levantada": aval.mascara_levantada,
            "arco_ativo": aval.arco_ativo,
            "epis": {nome: {"estado": epi.estado.value, "motivo": epi.motivo,
                            "conf": round(epi.conf, 2) if epi.conf is not None else None}
                     for nome, epi in aval.epis.items()},
        })
    return pessoas


class TrabalhadorCamera(threading.Thread):
    """Processa uma câmera: FonteVideo -> Pipeline -> desenho -> JPEG em memória; ocorrências -> RegistradorOcorrencias."""

    def __init__(self, camera_id: int, nome: str, origem: str, config: Config, registrador: RegistradorOcorrencias,
                 fabrica: sessionmaker[Session], borrador_ao_vivo: Borrador | None,
                 criar_detector: Callable[[Config], object], criar_fonte: Callable[[str], object],
                 zona: list | None = None) -> None:
        super().__init__(name=f"camera-{camera_id}", daemon=True)
        self.camera_id, self.nome, self.origem, self.config = camera_id, nome, origem, config
        self.zona = [tuple(p) for p in zona] if zona else None   # RD06: zona de interesse do posto
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
        self.fora_da_zona = 0                                # RD06: pessoas vistas fora da zona (não avaliadas)
        self.ultimas: deque[dict] = deque(maxlen=5)
        self._metrica_id: int | None = None
        self._cordao: dict[int, list[int]] = {}              # nº do trecho de 10 s -> quadros [V, C, I, N]
        self._contagem = {"frames": 0, "ignorados": 0, "pessoas": 0, Estado.CONFORME: 0, Estado.NAO_CONFORME: 0,
                          Estado.INDETERMINADO: 0}
        self._calibracao_ate = 0.0                           # RD02: até quando desenhar o quadro de calibração
        self._jpeg_calibracao: bytes | None = None
        self._dados_calibracao: dict | None = None

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

    # ---------------------------------------------------------------- calibração (RD02, tela T07)
    def pedir_calibracao(self) -> None:
        """Liga o desenho de calibração por alguns segundos (a tela T07 renova o pedido enquanto está aberta)."""
        self._calibracao_ate = time.monotonic() + CALIBRACAO_ATIVA_S

    @property
    def jpeg_calibracao(self) -> bytes:
        """Quadro com o desenho técnico; com a câmera pausada ou fora do ar, o mesmo aviso do ao vivo."""
        self.pedir_calibracao()
        with self._trava:
            if self._jpeg_calibracao is None or self.pausada or not self.online:
                return self._jpeg
            return self._jpeg_calibracao

    def dados_calibracao(self) -> dict | None:
        """Números do último quadro calibrado (None enquanto o primeiro não fica pronto)."""
        self.pedir_calibracao()
        with self._trava:
            return self._dados_calibracao

    def _calibrar(self, frame: np.ndarray, resultado: ResultadoFrame, base) -> None:
        def desenho(img: np.ndarray) -> np.ndarray:
            return desenhar_zona(desenhar_calibracao(img, frame, resultado, self.config, self.nome), self.zona)
        imagem = base.com_desenho(desenho).pixels if isinstance(base, ImagemBorrada) else desenho(base)
        dados = {**dados_calibracao(frame, resultado, self.config), "fps": round(self.fps, 1)}
        quadro = jpeg(imagem)
        with self._trava:
            self._jpeg_calibracao, self._dados_calibracao = quadro, dados

    def status(self) -> dict:
        with self._trava:
            return {
                "camera_id": self.camera_id, "nome": self.nome, "online": self.online, "pausada": self.pausada,
                "erro": self.erro, "fps": round(self.fps, 1), "saturado": self.saturado,
                "fracao_saturada": round(self.fracao_saturada, 3), "pessoas": list(self.pessoas),
                "fora_da_zona": self.fora_da_zona, "tem_zona": bool(self.zona),
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

    def _base(self, frame: np.ndarray, resultado: ResultadoFrame) -> np.ndarray | ImagemBorrada:
        """Imagem sobre a qual o stream é desenhado: borrada (se configurado, F2-D20) ou o próprio quadro."""
        if self.borrador_ao_vivo is None:
            return frame
        pessoas = [a.pessoa for a in resultado.avaliacoes] + resultado.fora_da_zona   # fora da zona: borradas também
        rostos = [r.caixa for r in (resultado.rostos or [])]
        return self.borrador_ao_vivo.borrar(frame, pessoas, rostos)

    def _desenhar(self, base: np.ndarray | ImagemBorrada, resultado: ResultadoFrame) -> np.ndarray:
        """Quadro do stream: caixas, rótulos e FPS por cima da base."""
        def desenho(img: np.ndarray) -> np.ndarray:
            return desenhar_zona(desenhar(img, resultado, [f"{self.nome} | {self.fps:.1f} FPS"]), self.zona)
        return base.com_desenho(desenho).pixels if isinstance(base, ImagemBorrada) else desenho(base)

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
                    "arco_ativo": registro.arco_ativo,
                    "thumb_url": f"/midia/{registro.uuid}?tipo=thumb"})

    def _contar(self, resultado: ResultadoFrame) -> None:
        c = self._contagem
        c["frames"] += 1
        if resultado.saturado:
            c["ignorados"] += 1
            return
        for aval in resultado.avaliacoes:
            c["pessoas"] += 1
            c[pior_estado(aval)] += 1

    def marcar_cordao(self, resultado: ResultadoFrame, instante: float | None = None) -> None:
        """Conta o quadro no trecho de 10 s atual (quadros estourados pelo arco não contam)."""
        if resultado.saturado:
            return
        codigo = max((CODIGO_ESTADO[pior_estado(a)] for a in resultado.avaliacoes), key=GRAVIDADE_CORDAO.get,
                     default="V")
        trecho = int((time.time() if instante is None else instante) // PASSO_CORDAO_S)
        with self._trava:
            self._cordao.setdefault(trecho, [0, 0, 0, 0])[GRAVIDADE_CORDAO[codigo]] += 1
            limite = trecho - HORAS_CORDAO * 3600 // PASSO_CORDAO_S
            if len(self._cordao) > HORAS_CORDAO * 3600 // PASSO_CORDAO_S + 60:
                for antigo in [k for k in self._cordao if k < limite]:
                    del self._cordao[antigo]

    def cordao(self, inicio: float, fim: float) -> str:
        """Códigos dos trechos de `inicio` a `fim` (timestamps), um caractere por trecho de 10 s."""
        primeiro, ultimo = int(inicio // PASSO_CORDAO_S), int(fim // PASSO_CORDAO_S)
        with self._trava:   # copia as contagens: a thread da câmera continua somando nelas
            contagens = [list(c) if (c := self._cordao.get(k)) else None for k in range(primeiro, ultimo + 1)]
        return "".join(codigo_do_trecho(c) for c in contagens)

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
        pipeline, gerenciador = Pipeline(self.config, detector, self.zona), GerenciadorOcorrencias(self.config)
        pular = max(1, self.config.deteccao.pular_frames)
        votacao, exibicao = VotacaoTemporal(self.config.deteccao.votacao_quadros), []
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
                resultado = pipeline.processar(frame)   # câmera ao vivo: o arco (RD03) usa o relógio do computador
                self._registrar(gerenciador.atualizar(resultado.avaliacoes, t, n, resultado.saturado), frame,
                                resultado)
                self._contar(resultado)
                self.marcar_cordao(resultado)
                # RD01: a tela mostra a maioria dos últimos quadros de cada pessoa (as ocorrências usam o quadro real)
                if not resultado.saturado:
                    exibicao = votacao.atualizar(resultado.avaliacoes)
                tela = replace(resultado, avaliacoes=exibicao)
                frames_fps += 1
                agora = time.monotonic()
                if agora - inicio_fps >= 2:
                    self.fps, inicio_fps, frames_fps = frames_fps / (agora - inicio_fps), agora, 0
                base = self._base(frame, resultado)
                quadro = jpeg(self._desenhar(base, tela))
                if time.monotonic() < self._calibracao_ate:   # RD02: alguém está com a tela de calibração aberta
                    self._calibrar(frame, resultado, base)
                with self._trava:
                    self._quadro, self._resultado = frame, tela
                self._publicar(quadro, online=True, saturado=resultado.saturado,
                               fracao_saturada=resultado.fracao_saturada, pessoas=status_das_pessoas(tela),
                               fora_da_zona=len(tela.fora_da_zona))
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
        self._trava = threading.Lock()   # duas mudanças de configuração ao mesmo tempo não se atropelam

    def _cameras_ativas(self, camera_id: int | None = None) -> list[tuple]:
        with self.fabrica() as sessao:
            consulta = select(Camera).where(Camera.ativa.is_(True)).order_by(Camera.id)
            if camera_id is not None:
                consulta = consulta.where(Camera.id == camera_id)
            return [(c.id, c.nome_posto, c.tipo, c.origem, list(c.epis), c.roi_poligono)
                    for c in sessao.scalars(consulta)]

    def _ligar(self, camera_id: int, nome: str, tipo: str, origem: str, epis: list, zona: list | None,
               anterior: TrabalhadorCamera | None = None) -> None:
        trabalhador = TrabalhadorCamera(
            camera_id, nome, origem_da_camera(tipo, origem, self.ajustes), config_da_camera(self.config_base, epis),
            self.registrador, self.fabrica, self.borrador_ao_vivo, self.criar_detector, self.criar_fonte, zona=zona)
        if anterior is not None:   # religada por uma mudança de configuração: o turno continua de onde estava
            trabalhador._cordao, trabalhador.ultimas = anterior._cordao, anterior.ultimas
            trabalhador.pausada = anterior.pausada
        self._trabalhadores[camera_id] = trabalhador
        trabalhador.start()

    def iniciar(self) -> None:
        with self._trava:
            dados = self._cameras_ativas()
            for camera in dados:
                self._ligar(*camera)
        log.info("%d câmera(s) ativa(s) iniciada(s)", len(dados))

    def reiniciar(self, camera_id: int | None = None) -> None:
        """Aplica mudanças de configuração sem reiniciar o sistema: para a câmera (ou todas, com None) e liga de novo
        com o que está no banco. Uma câmera desativada fica parada; uma ativada passa a rodar."""
        with self._trava:
            alvos = list(self._trabalhadores) if camera_id is None else [camera_id]
            antigos = {i: self._trabalhadores.pop(i) for i in alvos if i in self._trabalhadores}
            for trabalhador in antigos.values():
                trabalhador.parar()
            for trabalhador in antigos.values():
                trabalhador.join(10)
            for camera in self._cameras_ativas(camera_id):
                self._ligar(*camera, anterior=antigos.get(camera[0]))
        log.info("Câmera(s) religada(s) com a nova configuração: %s", "todas" if camera_id is None else camera_id)

    def parar(self, espera_s: float = 10) -> None:
        with self._trava:
            for trabalhador in self._trabalhadores.values():
                trabalhador.parar()
            for trabalhador in self._trabalhadores.values():
                trabalhador.join(espera_s)
            self._trabalhadores.clear()

    def obter(self, camera_id: int) -> TrabalhadorCamera | None:
        return self._trabalhadores.get(camera_id)

    def ids(self) -> list[int]:
        return sorted(self._trabalhadores)


async def gerar_mjpeg(trabalhador: TrabalhadorCamera, desconectado: Callable[[], object],
                      quadros_por_segundo: float = QUADROS_POR_SEGUNDO_MJPEG,
                      max_quadros: int | None = None, calibracao: bool = False) -> AsyncIterator[bytes]:
    """Partes do stream MJPEG (multipart/x-mixed-replace): o navegador troca a imagem a cada parte recebida.

    Cada navegador recebe o último quadro pronto; vários supervisores olhando não aumentam o custo da detecção.
    Com `calibracao`, envia o quadro com o desenho técnico da tela T07 (RD02).
    """
    anterior, enviados = None, 0
    while not await desconectado():
        quadro = trabalhador.jpeg_calibracao if calibracao else trabalhador.ultimo_jpeg
        if quadro is not anterior:
            yield (b"--quadro\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(quadro)).encode()
                   + b"\r\n\r\n" + quadro + b"\r\n")
            anterior, enviados = quadro, enviados + 1
            if max_quadros is not None and enviados >= max_quadros:
                return
        await asyncio.sleep(1 / quadros_por_segundo)
