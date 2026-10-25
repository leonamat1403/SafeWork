"""Onde as imagens das ocorrências ficam guardadas (interface Storage + implementação em disco local).

O resto do sistema só fala com a interface: para trocar o disco local por um servidor de arquivos (NAS), basta uma
nova implementação, sem mexer no resto do código. O banco guarda só o caminho RELATIVO devolvido aqui.

Estrutura em DATA_DIR (pastas pelo dia em horário de Brasília):
    ocorrencias/AAAA/MM/DD/<uuid>.jpg          imagem já borrada
    thumbnails/AAAA/MM/DD/<uuid>_thumb.jpg     miniatura com 320 px de largura
"""
from __future__ import annotations

import os
import shutil
import uuid as uuid_mod
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from app.privacy import ImagemBorrada
from app.tempo import para_local

LARGURA_THUMB = 320
LARGURA_MAX_IMAGEM = 1920   # câmeras 4K: a imagem da ocorrência é reduzida (Full HD basta para validar)
QUALIDADE_JPEG = 85
PASTAS_DE_IMAGENS = ("ocorrencias", "thumbnails")   # o Storage só lê e apaga dentro destas pastas


class ErroArmazenamento(RuntimeError):
    """Falha ao gravar, ler ou apagar uma imagem."""


class ErroDiscoCheio(ErroArmazenamento):
    """Espaço livre abaixo do mínimo configurado (armazenamento.espaco_minimo_mb no config.yaml)."""


@dataclass(frozen=True)
class CaminhosImagem:
    """Caminhos relativos da imagem da ocorrência e da sua miniatura, como são guardados no banco."""

    imagem: str   # relativo a DATA_DIR, com "/" (ex.: "ocorrencias/2026/10/14/<uuid>.jpg")
    thumb: str


class Storage(ABC):
    """O que o sistema precisa de um armazenamento de imagens."""

    @abstractmethod
    def salvar_ocorrencia(self, imagem: ImagemBorrada, uuid: str, quando: datetime) -> CaminhosImagem:
        """Grava a imagem (já borrada) e a miniatura; devolve os caminhos relativos."""

    @abstractmethod
    def ler(self, caminho: str) -> bytes:
        """Conteúdo do arquivo (JPEG) de um caminho relativo devolvido por salvar_ocorrencia."""

    @abstractmethod
    def apagar(self, caminho: str) -> bool:
        """Apaga o arquivo; False se ele já não existia."""

    @abstractmethod
    def espaco_livre_mb(self) -> float:
        """Espaço livre no disco onde as imagens ficam."""

    @abstractmethod
    def uso_mb(self) -> float:
        """Quanto a pasta de dados ocupa (aba Sistema das Configurações)."""


def _jpeg(img: np.ndarray) -> bytes:
    """Codifica a imagem em JPEG com a qualidade padrão do armazenamento."""
    ok, dados = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, QUALIDADE_JPEG])
    if not ok:
        raise ErroArmazenamento("Não foi possível codificar a imagem em JPEG")
    return dados.tobytes()


def _reduzir(img: np.ndarray, largura_max: int) -> np.ndarray:
    """Reduz para no máximo `largura_max` pixels de largura, mantendo a proporção (não amplia)."""
    altura, largura = img.shape[:2]
    if largura <= largura_max:
        return img
    return cv2.resize(img, (largura_max, max(1, round(altura * largura_max / largura))), interpolation=cv2.INTER_AREA)


class StorageDisco(Storage):
    """Imagens em pastas dentro de DATA_DIR, no disco do próprio computador (on-premises)."""

    def __init__(self, data_dir: Path, espaco_minimo_mb: float = 500) -> None:
        """`data_dir` é a raiz dos dados; abaixo de `espaco_minimo_mb` livres, novas imagens são recusadas."""
        self.base = Path(data_dir).resolve()
        self.espaco_minimo_mb = espaco_minimo_mb

    def _resolver(self, caminho: str) -> Path:
        """Caminho absoluto de um caminho relativo, recusando qualquer coisa fora das pastas de imagens."""
        destino = (self.base / caminho).resolve()
        permitidas = [self.base / pasta for pasta in PASTAS_DE_IMAGENS]
        if not any(destino.is_relative_to(p) for p in permitidas):
            raise ErroArmazenamento(f"Caminho fora das pastas de imagens: {caminho!r}")
        return destino

    def _gravar(self, caminho: str, dados: bytes) -> None:
        """Grava os bytes num arquivo temporário e o renomeia, para nunca deixar uma imagem pela metade."""
        destino = self._resolver(caminho)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_suffix(".tmp")
        temporario.write_bytes(dados)
        os.replace(temporario, destino)   # o arquivo aparece completo ou não aparece

    def salvar_ocorrencia(self, imagem: ImagemBorrada, uuid: str, quando: datetime) -> CaminhosImagem:
        """Grava a imagem (até 1920 px) e a miniatura (320 px) na pasta do dia local; recusa imagem sem blur e disco cheio."""
        if not isinstance(imagem, ImagemBorrada):
            raise TypeError("O Storage só grava ImagemBorrada (RF27): passe a imagem por privacy.Borrador.borrar().")
        uuid = str(uuid_mod.UUID(uuid))   # recusa nomes que não sejam um UUID válido
        livre = self.espaco_livre_mb()
        if livre < self.espaco_minimo_mb:
            raise ErroDiscoCheio(f"Só {livre:.0f} MB livres em {self.base} (mínimo {self.espaco_minimo_mb:.0f} MB)")
        dia = para_local(quando).strftime("%Y/%m/%d")   # a pasta é o dia em Brasília, embora `quando` venha em UTC
        caminhos = CaminhosImagem(f"ocorrencias/{dia}/{uuid}.jpg", f"thumbnails/{dia}/{uuid}_thumb.jpg")
        self._gravar(caminhos.imagem, _jpeg(_reduzir(imagem.pixels, LARGURA_MAX_IMAGEM)))
        self._gravar(caminhos.thumb, _jpeg(_reduzir(imagem.pixels, LARGURA_THUMB)))
        return caminhos

    def ler(self, caminho: str) -> bytes:
        """Lê o JPEG do disco; converte "arquivo não encontrado" em ErroArmazenamento."""
        try:
            return self._resolver(caminho).read_bytes()
        except FileNotFoundError as erro:
            raise ErroArmazenamento(f"Imagem não encontrada: {caminho}") from erro

    def apagar(self, caminho: str) -> bool:
        """Apaga o arquivo; devolve False se ele já não existia."""
        destino = self._resolver(caminho)
        try:
            destino.unlink()
        except FileNotFoundError:
            return False
        return True

    def espaco_livre_mb(self) -> float:
        """Espaço livre, em MB, no disco da pasta de dados (cria a pasta se ainda não existir)."""
        self.base.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(self.base).free / (1024 * 1024)

    def uso_mb(self) -> float:
        """Soma o tamanho de todos os arquivos da pasta de dados, em MB."""
        total = sum(p.stat().st_size for p in self.base.rglob("*") if p.is_file())
        return total / (1024 * 1024)
