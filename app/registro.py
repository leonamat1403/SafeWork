"""Registro de uma ocorrência: blur -> desenho das caixas -> Storage -> banco (docs/arquitetura_fase2.md, seção 4).

A DECISÃO de que existe uma ocorrência continua na Fase 1 (src/occurrences.py: 4 s com 75% em falta, cooldown de
60 s, vários EPIs numa ocorrência só). Este módulo só guarda o resultado. O nome é "registro" para não confundir com
src/occurrences.py (o prompt o chamava de app/occurrences.py).
"""
from __future__ import annotations

import logging
import uuid as uuid_mod
from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session, sessionmaker

from app.models import ORIGENS, Ocorrencia
from app.privacy import Borrador, ImagemBorrada
from app.storage import CaminhosImagem, ErroDiscoCheio, Storage
from app.tempo import para_utc, turno_de
from src.occurrences import Ocorrencia as OcorrenciaDetectada
from src.pipeline import ResultadoFrame, desenhar

log = logging.getLogger("epi_solda.registro")


class RegistradorOcorrencias:
    """Transforma uma ocorrência detectada pela Fase 1 numa linha do banco com a imagem borrada no disco."""

    def __init__(self, fabrica_sessoes: sessionmaker[Session], storage: Storage, borrador: Borrador,
                 turnos: dict[str, str]) -> None:
        """Recebe o banco, o armazenamento de imagens, o borrador e os horários dos turnos (usados para rotular)."""
        self.fabrica_sessoes = fabrica_sessoes
        self.storage = storage
        self.borrador = borrador
        self.turnos = turnos
        self.sem_espaco = False   # vira True quando o disco enche (o status ao vivo mostra o alerta)
        self.notificador = None   # RD09: alerta pelo Telegram (app/notificador.py), ligado pelo main

    def imagem_anotada(self, frame: np.ndarray, resultado: ResultadoFrame) -> ImagemBorrada:
        """Cópia BORRADA do frame com as caixas e os rótulos desenhados por cima (o que vai para o disco)."""
        pessoas = [a.pessoa for a in resultado.avaliacoes] + resultado.fora_da_zona   # fora da zona: borradas também
        rostos = [r.caixa for r in (resultado.rostos or [])]
        borrada = self.borrador.borrar(frame, pessoas, rostos)
        return borrada.com_desenho(lambda img: desenhar(img, resultado, []))

    def _salvar(self, imagem: ImagemBorrada, uuid: str, quando: datetime) -> CaminhosImagem | None:
        """Grava a imagem. None se o disco estiver cheio (RNF03): a ocorrência é registrada sem imagem."""
        try:
            caminhos = self.storage.salvar_ocorrencia(imagem, uuid, quando)
        except ErroDiscoCheio as erro:
            if not self.sem_espaco:
                log.error("Disco cheio: as ocorrências serão registradas SEM imagem até liberar espaço. %s", erro)
            self.sem_espaco = True
            return None
        self.sem_espaco = False
        return caminhos

    def registrar(self, detectada: OcorrenciaDetectada, frame: np.ndarray, resultado: ResultadoFrame,
                  camera_id: int, origem: str = "ao_vivo") -> Ocorrencia:
        """Grava a ocorrência e devolve a linha criada no banco.

        `frame` é o frame ORIGINAL em que a ocorrência foi confirmada; ele só é usado para gerar a cópia borrada.
        """
        return self.registrar_com_imagem(detectada, self.imagem_anotada(frame, resultado), camera_id, origem)

    def registrar_com_imagem(self, detectada: OcorrenciaDetectada, imagem: ImagemBorrada, camera_id: int,
                             origem: str = "ao_vivo") -> Ocorrencia:
        """Como registrar(), mas com a imagem já borrada e anotada (ex.: ocorrências de um upload, T03)."""
        if origem not in ORIGENS:
            raise ValueError(f"origem deve ser uma de {ORIGENS}")
        uuid = str(uuid_mod.uuid4())
        quando = para_utc(detectada.data_hora)   # a Fase 1 devolve horário local; o banco guarda sempre em UTC
        caminhos = self._salvar(imagem, uuid, quando)
        registro = Ocorrencia(
            uuid=uuid,
            camera_id=camera_id,
            data_hora=quando,
            turno=turno_de(quando, self.turnos),
            track_id=detectada.track_id,
            epis_faltantes=list(detectada.epis_faltantes),
            epis_indeterminados=list(detectada.epis_indeterminados),
            confianca_media={epi: round(v, 3) for epi, v in detectada.confianca_media.items()},
            situacao=dict(detectada.situacao),
            fracao_nao_conforme={epi: round(v, 3) for epi, v in detectada.fracao_nao_conforme.items()},
            mascara_levantada=detectada.mascara_levantada,
            arco_ativo=detectada.arco_ativo,
            caminho_imagem=caminhos.imagem if caminhos else None,
            caminho_thumb=caminhos.thumb if caminhos else None,
            origem=origem,
        )
        try:
            with self.fabrica_sessoes() as sessao:
                sessao.add(registro)
                sessao.commit()
        except Exception:
            if caminhos:   # sem a linha no banco, a imagem ficaria órfã no disco
                self.storage.apagar(caminhos.imagem)
                self.storage.apagar(caminhos.thumb)
            raise
        log.info("Ocorrência registrada: câmera %d, %s (%s)", camera_id, detectada.descricao(), uuid)
        if self.notificador is not None:
            self.notificador.avisar(registro)   # só entra na fila: o envio não atrasa a câmera
        return registro
