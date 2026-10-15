"""Análise por upload (T03, RF02): foto (jpg/png) ou vídeo (mp4) enviados pelo navegador.

- O arquivo enviado fica em data/uploads_temp/<id>/ só durante o processamento e é apagado em seguida; o resultado
  (anotado e JÁ BORRADO) fica lá até 1 h para download (a rotina de limpeza apaga depois).
- Um trabalho por vez, numa thread separada, para não disputar CPU com as câmeras.
- Uploads NÃO viram ocorrências oficiais, a não ser que o usuário peça ("registrar como ocorrência").
"""
from __future__ import annotations

import logging
import queue
import shutil
import threading
import time
import uuid as uuid_mod
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi import UploadFile
from sqlalchemy.orm import Session, sessionmaker

from app.config import Ajustes, config_da_camera
from app.models import Camera
from app.privacy import ImagemBorrada
from app.registro import RegistradorOcorrencias
from src.config import Config
from src.detector import Detector
from src.occurrences import GerenciadorOcorrencias
from src.occurrences import Ocorrencia as OcorrenciaDetectada
from src.pipeline import Pipeline, ResultadoFrame
from src.tipos import Estado
from src.votacao import VotacaoTemporal

log = logging.getLogger("epi_solda.uploads")

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png"}
EXTENSOES_VIDEO = {".mp4"}
BLOCO = 1024 * 1024
LARGURA_MAX_SAIDA = 1280
# Codecs na ordem de preferência: H.264 (toca em todo navegador), VP8 (webm), mp4v (só para download)
CODECS = (("avc1", ".mp4", "video/mp4"), ("VP80", ".webm", "video/webm"), ("mp4v", ".mp4", "video/mp4"))


class ErroUpload(ValueError):
    """Arquivo recusado; `codigo` é o status HTTP a devolver."""

    def __init__(self, mensagem: str, codigo: int = 400) -> None:
        super().__init__(mensagem)
        self.codigo = codigo


@dataclass
class TrabalhoUpload:
    id: str
    usuario_id: int
    camera_id: int
    nome_original: str
    tipo: str                                   # "imagem" ou "video"
    pasta: Path
    entrada: Path
    criado_em: float = field(default_factory=time.time)
    estado: str = "na_fila"                     # na_fila, processando, concluido, erro
    progresso: float = 0.0
    erro: str | None = None
    saida: Path | None = None
    tipo_saida: str | None = None
    pessoas: list[dict] = field(default_factory=list)
    ocorrencias: list[tuple[OcorrenciaDetectada, ImagemBorrada]] = field(default_factory=list)
    registradas: list[str] | None = None

    def resumo(self) -> dict:
        return {
            "id": self.id, "nome_original": self.nome_original, "tipo": self.tipo, "camera_id": self.camera_id,
            "estado": self.estado, "progresso": round(self.progresso, 3), "erro": self.erro,
            "arquivo_url": f"/api/uploads/{self.id}/arquivo" if self.saida else None, "tipo_arquivo": self.tipo_saida,
            "pessoas": self.pessoas,
            "ocorrencias_encontradas": [{"track_id": oc.track_id, "epis_faltantes": oc.epis_faltantes,
                                         "situacao": oc.situacao} for oc, _ in self.ocorrencias],
            "registradas": self.registradas,
        }


def _reduzir(pixels: np.ndarray, largura_max: int = LARGURA_MAX_SAIDA) -> np.ndarray:
    altura, largura = pixels.shape[:2]
    if largura <= largura_max:
        return pixels
    return cv2.resize(pixels, (largura_max, round(altura * largura_max / largura)), interpolation=cv2.INTER_AREA)


def gravar_imagem_borrada(imagem: ImagemBorrada, caminho: Path) -> None:
    """Grava o resultado de uma foto. Só aceita ImagemBorrada (RF27)."""
    if not isinstance(imagem, ImagemBorrada):
        raise TypeError("Só imagens borradas podem ser gravadas (RF27).")
    cv2.imencode(".jpg", _reduzir(imagem.pixels), [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(str(caminho))


class GravadorBorrado:
    """Grava o vídeo de resultado quadro a quadro. Só aceita ImagemBorrada (RF27)."""

    def __init__(self, base: Path, fps: float) -> None:
        self.base, self.fps = base, fps if 1 <= fps <= 120 else 25.0
        self.caminho: Path | None = None
        self.tipo: str | None = None
        self._escritor: cv2.VideoWriter | None = None

    def gravar(self, imagem: ImagemBorrada) -> None:
        if not isinstance(imagem, ImagemBorrada):
            raise TypeError("Só imagens borradas podem ser gravadas (RF27).")
        pixels = _reduzir(imagem.pixels)
        if self._escritor is None:
            altura, largura = pixels.shape[:2]
            for fourcc, extensao, tipo in CODECS:
                caminho = self.base.with_suffix(extensao)
                escritor = cv2.VideoWriter(str(caminho), cv2.VideoWriter_fourcc(*fourcc), self.fps, (largura, altura))
                if escritor.isOpened():
                    self._escritor, self.caminho, self.tipo = escritor, caminho, tipo
                    break
                escritor.release()
            else:
                raise RuntimeError("Nenhum codec de vídeo disponível no OpenCV para gravar o resultado.")
        self._escritor.write(pixels)

    def fechar(self) -> None:
        if self._escritor is not None:
            self._escritor.release()


def _resumo_por_pessoa(contagem: dict[int, dict[str, Counter]], levantada: Counter) -> list[dict]:
    """Tabela do resultado (T03): para cada pessoa, a % de cada estado por EPI e o estado que predominou."""
    pessoas = []
    for track_id in sorted(contagem):
        epis = {}
        for epi, estados in contagem[track_id].items():
            total = sum(estados.values())
            epis[epi] = {"predominante": estados.most_common(1)[0][0],
                         "percentuais": {e: round(n / total, 3) for e, n in estados.items()}}
        pessoas.append({"track_id": track_id, "epis": epis, "mascara_levantada_frames": levantada[track_id]})
    return pessoas


def ocorrencias_da_foto(resultado: ResultadoFrame) -> list[OcorrenciaDetectada]:
    """Numa foto não há "4 segundos": cada pessoa com algum EPI NÃO CONFORME vira uma ocorrência candidata."""
    ocorrencias = []
    for i, aval in enumerate(resultado.avaliacoes, start=1):
        faltando = [epi for epi, a in aval.epis.items() if a.estado == Estado.NAO_CONFORME]
        if not faltando:
            continue
        ocorrencias.append(OcorrenciaDetectada(
            data_hora=datetime.now(), tempo_s=0.0, frame=0, track_id=aval.pessoa.track_id or i,
            epis_faltantes=faltando, situacao={epi: aval.epis[epi].motivo for epi in faltando},
            fracao_nao_conforme={epi: 1.0 for epi in faltando},
            epis_indeterminados=[epi for epi, a in aval.epis.items() if a.estado == Estado.INDETERMINADO],
            confianca_media={epi: a.conf for epi, a in aval.epis.items() if a.conf is not None},
            mascara_levantada=aval.mascara_levantada))
    return ocorrencias


class FilaUploads:
    """Recebe os arquivos, processa um por vez e guarda os resultados por até 1 h (em memória e em uploads_temp)."""

    def __init__(self, ajustes: Ajustes, config_base: Config, fabrica: sessionmaker[Session],
                 registrador: RegistradorOcorrencias, criar_detector: Callable[[Config], object] = Detector) -> None:
        self.ajustes, self.config_base, self.fabrica = ajustes, config_base, fabrica
        self.registrador, self.criar_detector = registrador, criar_detector
        self.pasta = ajustes.data_dir / "uploads_temp"
        self._trabalhos: dict[str, TrabalhoUpload] = {}
        self._fila: queue.Queue[str] = queue.Queue()
        self._trava = threading.Lock()
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._executar, name="uploads", daemon=True)

    # ---------------------------------------------------------------- ciclo de vida
    def iniciar(self) -> None:
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        if self._thread.is_alive():
            self._thread.join(10)

    # ---------------------------------------------------------------- pelas rotas
    async def receber(self, arquivo: UploadFile, usuario_id: int, camera_id: int) -> TrabalhoUpload:
        """Valida o tipo e o tamanho, grava em uploads_temp e coloca na fila."""
        nome = Path(arquivo.filename or "").name
        extensao = Path(nome).suffix.lower()
        if extensao in EXTENSOES_IMAGEM:
            tipo = "imagem"
        elif extensao in EXTENSOES_VIDEO:
            tipo = "video"
        else:
            raise ErroUpload("Tipo não aceito: envie uma foto .jpg/.png ou um vídeo .mp4.", 415)
        with self.fabrica() as sessao:
            if sessao.get(Camera, camera_id) is None:
                raise ErroUpload(f"Posto {camera_id} não existe.", 404)
        trabalho_id = uuid_mod.uuid4().hex
        pasta = self.pasta / trabalho_id
        pasta.mkdir(parents=True)
        entrada = pasta / f"entrada{extensao}"          # nome aleatório: o nome enviado nunca vira caminho
        limite = self.ajustes.upload_tamanho_max_mb * BLOCO
        tamanho = 0
        try:
            with entrada.open("wb") as destino:
                while bloco := await arquivo.read(BLOCO):
                    tamanho += len(bloco)
                    if tamanho > limite:
                        raise ErroUpload(f"Arquivo maior que {self.ajustes.upload_tamanho_max_mb} MB.", 413)
                    destino.write(bloco)
            if tamanho == 0:
                raise ErroUpload("Arquivo vazio.")
            self._conferir_conteudo(entrada, tipo)
        except ErroUpload:
            shutil.rmtree(pasta, ignore_errors=True)
            raise
        trabalho = TrabalhoUpload(trabalho_id, usuario_id, camera_id, nome, tipo, pasta, entrada)
        with self._trava:
            self._trabalhos[trabalho_id] = trabalho
        self._fila.put(trabalho_id)
        log.info("Upload recebido: %s (%s, %.1f MB)", trabalho_id, tipo, tamanho / BLOCO)
        return trabalho

    @staticmethod
    def _conferir_conteudo(entrada: Path, tipo: str) -> None:
        """A extensão pode mentir: o arquivo tem de abrir como imagem ou vídeo de verdade."""
        if tipo == "imagem":
            if cv2.imdecode(np.fromfile(str(entrada), np.uint8), cv2.IMREAD_COLOR) is None:
                raise ErroUpload("O arquivo não é uma imagem válida.", 415)
            return
        captura = cv2.VideoCapture(str(entrada))
        ok, _ = captura.read()
        captura.release()
        if not ok:
            raise ErroUpload("O arquivo não é um vídeo válido.", 415)

    def obter(self, trabalho_id: str, usuario_id: int, admin: bool) -> TrabalhoUpload | None:
        """O trabalho, se existir e for do usuário (o ADMIN vê todos)."""
        with self._trava:
            trabalho = self._trabalhos.get(trabalho_id)
        if trabalho is None or (trabalho.usuario_id != usuario_id and not admin):
            return None
        return trabalho

    def registrar(self, trabalho: TrabalhoUpload) -> list[str]:
        """Grava como ocorrências oficiais (origem "upload") as ocorrências encontradas no arquivo."""
        if trabalho.estado != "concluido":
            raise ErroUpload("O processamento ainda não terminou.", 409)
        with self._trava:
            if trabalho.registradas is not None:
                raise ErroUpload("As ocorrências deste upload já foram registradas.", 409)
            trabalho.registradas = []
        for detectada, imagem in trabalho.ocorrencias:
            registro = self.registrador.registrar_com_imagem(detectada, imagem, trabalho.camera_id, origem="upload")
            trabalho.registradas.append(registro.uuid)
        return trabalho.registradas

    # ---------------------------------------------------------------- thread
    def _executar(self) -> None:
        while not self._parar.is_set():
            self._esquecer_antigos()
            try:
                trabalho_id = self._fila.get(timeout=0.5)
            except queue.Empty:
                continue
            trabalho = self._trabalhos.get(trabalho_id)
            if trabalho is None:
                continue
            trabalho.estado = "processando"
            try:
                self._processar(trabalho)
                trabalho.estado, trabalho.progresso = "concluido", 1.0
            except Exception as erro:
                log.exception("Upload %s: falha no processamento", trabalho.id)
                trabalho.estado, trabalho.erro = "erro", str(erro)
            finally:
                trabalho.entrada.unlink(missing_ok=True)   # o arquivo original é apagado logo após o processamento

    def _esquecer_antigos(self) -> None:
        limite = time.time() - self.ajustes.uploads_max_idade_s
        with self._trava:
            for trabalho_id in [t.id for t in self._trabalhos.values() if t.criado_em < limite]:
                trabalho = self._trabalhos.pop(trabalho_id)
                shutil.rmtree(trabalho.pasta, ignore_errors=True)

    def _config(self, camera_id: int) -> Config:
        with self.fabrica() as sessao:
            camera = sessao.get(Camera, camera_id)
            return config_da_camera(self.config_base, list(camera.epis) if camera else [])

    def _processar(self, trabalho: TrabalhoUpload) -> None:
        config = self._config(trabalho.camera_id)
        pipeline = Pipeline(config, self.criar_detector(config))
        if trabalho.tipo == "imagem":
            frame = cv2.imdecode(np.fromfile(str(trabalho.entrada), np.uint8), cv2.IMREAD_COLOR)
            resultado = pipeline.processar(frame)
            anotada = self.registrador.imagem_anotada(frame, resultado)
            trabalho.saida, trabalho.tipo_saida = trabalho.pasta / "resultado.jpg", "image/jpeg"
            gravar_imagem_borrada(anotada, trabalho.saida)
            contagem: dict[int, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
            for i, aval in enumerate(resultado.avaliacoes, start=1):
                for epi, a in aval.epis.items():
                    contagem[aval.pessoa.track_id or i][epi][a.estado.value] += 1
            levantada = Counter({(a.pessoa.track_id or i): int(a.mascara_levantada)
                                 for i, a in enumerate(resultado.avaliacoes, start=1)})
            trabalho.pessoas = _resumo_por_pessoa(contagem, levantada)
            trabalho.ocorrencias = [(oc, anotada) for oc in ocorrencias_da_foto(resultado)]
            return

        captura = cv2.VideoCapture(str(trabalho.entrada))
        total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        gravador = GravadorBorrado(trabalho.pasta / "resultado", captura.get(cv2.CAP_PROP_FPS) or 25.0)
        gerenciador = GerenciadorOcorrencias(config)
        votacao, exibicao = VotacaoTemporal(config.deteccao.votacao_quadros), []   # RD01: só o vídeo de resultado
        contagem = defaultdict(lambda: defaultdict(Counter))
        levantada: Counter = Counter()
        n = 0
        try:
            while not self._parar.is_set():
                ok, frame = captura.read()
                if not ok:
                    break
                t = captura.get(cv2.CAP_PROP_POS_MSEC) / 1000
                resultado = pipeline.processar(frame, t)
                if not resultado.saturado:
                    exibicao = votacao.atualizar(resultado.avaliacoes)
                gravador.gravar(self.registrador.imagem_anotada(frame, replace(resultado, avaliacoes=exibicao)))
                novas = gerenciador.atualizar(resultado.avaliacoes, t, n, resultado.saturado)
                if novas:   # a imagem da ocorrência mostra o quadro real (sem votação), como no ao vivo
                    anotada = self.registrador.imagem_anotada(frame, resultado)
                    trabalho.ocorrencias.extend((oc, anotada) for oc in novas)
                if not resultado.saturado:
                    for aval in resultado.avaliacoes:
                        if aval.pessoa.track_id is None:
                            continue
                        for epi, a in aval.epis.items():
                            contagem[aval.pessoa.track_id][epi][a.estado.value] += 1
                        levantada[aval.pessoa.track_id] += int(aval.mascara_levantada)
                n += 1
                trabalho.progresso = min(0.99, n / total)
        finally:
            captura.release()
            gravador.fechar()
        trabalho.saida, trabalho.tipo_saida = gravador.caminho, gravador.tipo
        trabalho.pessoas = _resumo_por_pessoa(contagem, levantada)
