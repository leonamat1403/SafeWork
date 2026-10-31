"""Blur de rostos e cabeças (RF27, LGPD) antes de qualquer imagem ir para o disco.

Garantia pelo código (F2-D4): o Storage só aceita um objeto ImagemBorrada, e só a função Borrador.borrar() cria esse
objeto. Não existe caminho no sistema para gravar um frame original.

O que é borrado:
  - a região da CABEÇA de todas as pessoas encontradas pela pose (a mesma região da regra da máscara, com folga),
    mesmo quando a máscara cobre o rosto ("blur preventivo" do RF27); sem pontos do corpo, os 25% superiores da caixa;
  - os ROSTOS encontrados pelo detector de rostos (YuNet, F2-D5) no frame inteiro, para pegar quem a pose não achou;
  - os rostos que a Fase 1 já encontrou no recorte da cabeça (ResultadoFrame.rostos).
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable
from pathlib import Path

import cv2
import numpy as np

from src.body_regions import FRACAO_CABECA_FALLBACK, regiao_cabeca
from src.tipos import Caixa, Pessoa

log = logging.getLogger("epi_solda.privacidade")

FOLGA = 0.20              # aumenta cada região em 20% de cada lado (cabelo, orelhas, queixo)
BLOCOS = 6                # a região vira um mosaico de no máximo 6 x 6 blocos: não dá para reconhecer ninguém
LADO_MAX_ROSTOS = 1280    # o detector de rostos roda numa cópia reduzida do frame (velocidade)
_CHAVE = object()         # só este módulo cria ImagemBorrada


class ImagemBorrada:
    """Imagem que JÁ passou pelo blur. Só privacy.Borrador.borrar() cria objetos desta classe."""

    __slots__ = ("_pixels",)

    def __init__(self, pixels: np.ndarray, _chave: object = None) -> None:
        """Só aceita criação com a chave secreta do módulo; guarda uma cópia imutável dos pixels."""
        if _chave is not _CHAVE:
            raise TypeError("ImagemBorrada só pode ser criada por privacy.Borrador.borrar() (RF27): "
                            "nenhuma imagem sem blur pode ser gravada.")
        copia = np.ascontiguousarray(pixels).copy()
        copia.setflags(write=False)   # ninguém altera os pixels depois do blur
        self._pixels = copia

    @property
    def pixels(self) -> np.ndarray:
        """Pixels (BGR), somente leitura."""
        return self._pixels

    @property
    def forma(self) -> tuple[int, ...]:
        """Dimensões da imagem (altura, largura, canais)."""
        return self._pixels.shape

    def com_desenho(self, desenhar: Callable[[np.ndarray], np.ndarray]) -> ImagemBorrada:
        """Nova ImagemBorrada com caixas e textos desenhados por cima (ex.: src.pipeline.desenhar).

        Desenhar só acrescenta traços sobre a imagem já borrada; não traz de volta nenhum pixel original.
        """
        return ImagemBorrada(desenhar(self._pixels.copy()), _CHAVE)


def _ampliar(caixa: Caixa, folga: float, largura: int, altura: int) -> tuple[int, int, int, int]:
    """Aumenta a caixa pela `folga` em cada lado e a limita às bordas da imagem, em pixels inteiros."""
    x1, y1, x2, y2 = caixa
    dx, dy = (x2 - x1) * folga, (y2 - y1) * folga
    return (max(0, int(x1 - dx)), max(0, int(y1 - dy)), min(largura, int(x2 + dx + 1)), min(altura, int(y2 + dy + 1)))


def regioes_das_cabecas(pessoas: Iterable[Pessoa], conf_keypoint: float) -> list[Caixa]:
    """Região da cabeça de cada pessoa (pelos pontos do corpo) ou, sem pontos, os 25% superiores da caixa."""
    regioes = []
    for pessoa in pessoas:
        cabeca = regiao_cabeca(pessoa, conf_keypoint)
        if cabeca is None:
            x1, y1, x2, y2 = pessoa.caixa
            cabeca = (x1, y1, x2, y1 + (y2 - y1) * FRACAO_CABECA_FALLBACK)
        regioes.append(cabeca)
    return regioes


def pixelizar(img: np.ndarray, caixa: Caixa, folga: float = FOLGA) -> None:
    """Reduz a região a no máximo 6 x 6 cores médias e a amplia de volta suavizada, alterando `img` no lugar.

    Só sobram 36 cores médias da região: não dá para reconhecer ninguém. A suavização vem da própria ampliação
    (interpolação linear), que custa o mesmo em qualquer resolução (um desfoque Gaussiano numa cabeça de vídeo 4K
    levava quase 1 s por quadro).
    """
    altura, largura = img.shape[:2]
    x1, y1, x2, y2 = _ampliar(caixa, folga, largura, altura)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return
    regiao = img[y1:y2, x1:x2]
    pequena = cv2.resize(regiao, (min(BLOCOS, x2 - x1), min(BLOCOS, y2 - y1)), interpolation=cv2.INTER_AREA)
    img[y1:y2, x1:x2] = cv2.resize(pequena, (x2 - x1, y2 - y1), interpolation=cv2.INTER_LINEAR)


class DetectorRostosQuadro:
    """Rostos no frame inteiro com o YuNet (o mesmo modelo da Fase 1). Sem o arquivo do modelo, não acha nada e
    avisa no log: as cabeças encontradas pela pose continuam sendo borradas."""

    def __init__(self, caminho_modelo: Path | None, conf: float = 0.6) -> None:
        """Carrega o YuNet de `caminho_modelo`; `conf` é a confiança mínima para aceitar um rosto."""
        self._caminho, self._conf = caminho_modelo, conf
        self._detectores: dict[tuple[int, int], cv2.FaceDetectorYN] = {}   # um YuNet para cada tamanho de imagem
        self._trava = threading.Lock()   # o mesmo detector é usado pela câmera e pelo upload ao mesmo tempo
        self._disponivel = caminho_modelo is not None and Path(caminho_modelo).exists()
        if not self._disponivel:
            log.warning("Modelo de rostos não encontrado (%s): o blur usa só a cabeça das pessoas (pose).",
                        caminho_modelo)

    def _para_tamanho(self, largura: int, altura: int) -> cv2.FaceDetectorYN:
        """O YuNet do OpenCV 5 falha se o tamanho da entrada muda entre chamadas (câmera 640x480 e upload 1920x1080,
        por exemplo): por isso há um detector para cada tamanho, criado na primeira vez que ele aparece."""
        chave = (largura, altura)
        if chave not in self._detectores:
            if len(self._detectores) >= 8:   # poucos tamanhos na prática; evita crescer sem limite
                self._detectores.clear()
            # Parâmetros: confiança mínima, limiar do NMS (supressão de caixas repetidas) e máximo de rostos
            self._detectores[chave] = cv2.FaceDetectorYN.create(str(self._caminho), "", chave, self._conf, 0.3, 5000)
        return self._detectores[chave]

    def detectar(self, frame: np.ndarray) -> list[Caixa]:
        """Caixas (x1, y1, x2, y2) dos rostos, nas coordenadas do frame original (a detecção usa cópia reduzida)."""
        if not self._disponivel:
            return []
        altura, largura = frame.shape[:2]
        escala = min(1.0, LADO_MAX_ROSTOS / max(altura, largura))
        imagem = cv2.resize(frame, None, fx=escala, fy=escala) if escala < 1 else frame
        with self._trava:
            _, faces = self._para_tamanho(imagem.shape[1], imagem.shape[0]).detect(imagem)
        if faces is None:
            return []
        return [(f[0] / escala, f[1] / escala, (f[0] + f[2]) / escala, (f[1] + f[3]) / escala) for f in faces]


class Borrador:
    """Aplica o blur de privacidade e devolve a ImagemBorrada (a única coisa que o Storage aceita)."""

    def __init__(self, detector_rostos: DetectorRostosQuadro | None, conf_keypoint: float = 0.5) -> None:
        """`conf_keypoint` é a confiança mínima dos pontos do corpo usados para achar a cabeça."""
        self.detector_rostos = detector_rostos
        self.conf_keypoint = conf_keypoint

    def borrar(self, frame: np.ndarray, pessoas: Iterable[Pessoa], rostos: Iterable[Caixa] = ()) -> ImagemBorrada:
        """Borra cabeças e rostos numa CÓPIA do frame (o original não é alterado nem guardado)."""
        img = frame.copy()
        regioes = regioes_das_cabecas(pessoas, self.conf_keypoint) + list(rostos)
        if self.detector_rostos is not None:
            regioes += self.detector_rostos.detectar(frame)
        for caixa in regioes:
            pixelizar(img, caixa)
        return ImagemBorrada(img, _CHAVE)
