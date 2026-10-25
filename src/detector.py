"""Modelos YOLO: pose (pessoas + pontos do corpo + rastreamento ByteTrack) e detector de EPI de solda.

Este é o ÚNICO módulo que conhece o Ultralytics. Ele converte os resultados dos modelos para as estruturas
simples de src/tipos.py, que o resto do sistema usa.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

import cv2
import numpy as np

from src.body_regions import regiao_cabeca
from src.config import EPI_DA_CLASSE, Config
from src.tipos import Caixa, DeteccaoEPI, Keypoint, Pessoa, Rosto

log = logging.getLogger(__name__)


class ErroModelo(RuntimeError):
    """Modelo ausente ou incompatível."""


def classe_interna(nome_modelo: str, mapeamento: dict[str, str]) -> str:
    """Converte o nome de classe do modelo para o nome interno (ex.: "welding-glove" -> "luvas").

    Modelos treinados no notebook já saem com os nomes internos e passam direto.
    """
    nome = nome_modelo.strip().lower()
    return mapeamento.get(nome, nome)


def mapear_deteccoes(brutas: Iterable[tuple[str, float, Caixa]], config: Config) -> list[DeteccaoEPI]:
    """Aplica o mapeamento de classes e o limiar de confiança POR EPI (RF15).

    Descarta classes desconhecidas e EPIs desativados no posto.
    """
    saida = []
    for nome_modelo, conf, caixa in brutas:
        classe = classe_interna(nome_modelo, config.mapeamento_classes)
        epi = EPI_DA_CLASSE.get(classe)
        if epi is None or epi not in config.epis_ativos:
            continue
        if conf < config.epis[epi].conf:
            continue
        saida.append(DeteccaoEPI(classe=classe, epi=epi, conf=conf, caixa=caixa))
    return saida


def converter_pessoas(resultado) -> list[Pessoa]:
    """Converte o resultado do modelo de pose (Ultralytics) em uma lista de Pessoa."""
    caixas = resultado.boxes
    if caixas is None or len(caixas) == 0:
        return []
    xyxy = caixas.xyxy.cpu().numpy()
    confs = caixas.conf.cpu().numpy()
    ids = caixas.id.int().cpu().numpy() if caixas.id is not None else [None] * len(xyxy)
    pontos = resultado.keypoints.data.cpu().numpy() if resultado.keypoints is not None else None

    pessoas = []
    for k in range(len(xyxy)):
        kps = []
        if pontos is not None and len(pontos) > k:
            kps = [Keypoint(float(x), float(y), float(c)) for x, y, c in pontos[k]]
        pessoas.append(Pessoa(
            caixa=tuple(float(v) for v in xyxy[k]),
            keypoints=kps,
            track_id=int(ids[k]) if ids[k] is not None else None,
            conf=float(confs[k]),
        ))
    return pessoas


class DetectorRostos:
    """Detector de rostos descobertos YuNet (OpenCV). Um rosto coberto pela máscara de solda NÃO é encontrado.

    Roda só no recorte da cabeça de cada pessoa (e não na imagem inteira): é bem mais rápido e, como o recorte é
    ampliado para `tamanho_recorte` px, também encontra rostos de pessoas mais distantes.
    """

    def __init__(self, caminho: Path, conf: float, tamanho_recorte: int) -> None:
        """Carrega o modelo YuNet de `caminho` com a confiança mínima `conf` e o tamanho (px) do recorte da cabeça."""
        # Parâmetros 0.3 e 50 do YuNet: limiar do NMS (supressão de caixas repetidas) e máximo de rostos por recorte
        self.modelo = cv2.FaceDetectorYN.create(str(caminho), "", (tamanho_recorte, tamanho_recorte), conf, 0.3, 50)
        self.tamanho = tamanho_recorte

    def detectar(self, frame: np.ndarray, pessoas: list[Pessoa], conf_keypoint: float) -> list[Rosto]:
        """Procura rostos descobertos na cabeça de cada pessoa e devolve as caixas em coordenadas da imagem inteira."""
        altura_img, largura_img = frame.shape[:2]
        rostos = []
        for pessoa in pessoas:
            cabeca = regiao_cabeca(pessoa, conf_keypoint) if pessoa.keypoints else None
            if cabeca is None:   # sem pontos da cabeça: quarto superior da caixa da pessoa
                x1, y1, x2, y2 = pessoa.caixa
                cabeca = (x1, y1, x2, y1 + 0.25 * (y2 - y1))
            cx, cy = (cabeca[0] + cabeca[2]) / 2, (cabeca[1] + cabeca[3]) / 2
            lado = 1.3 * max(cabeca[2] - cabeca[0], cabeca[3] - cabeca[1])   # recorte quadrado com folga de 30%
            x1, y1 = max(0, int(cx - lado / 2)), max(0, int(cy - lado / 2))
            x2, y2 = min(largura_img, int(cx + lado / 2)), min(altura_img, int(cy + lado / 2))
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue
            # O recorte é ampliado até `self.tamanho` px; depois as coordenadas voltam à escala original (÷ escala)
            escala = self.tamanho / max(x2 - x1, y2 - y1)
            recorte = cv2.resize(frame[y1:y2, x1:x2], (max(1, round((x2 - x1) * escala)), max(1, round((y2 - y1) * escala))))
            self.modelo.setInputSize((recorte.shape[1], recorte.shape[0]))
            _, faces = self.modelo.detect(recorte)
            for f in faces if faces is not None else []:
                fx, fy, fw, fh = (float(v) / escala for v in f[:4])
                olhos_y = y1 + (float(f[5]) + float(f[7])) / 2 / escala   # landmarks: olho direito e esquerdo (y)
                rostos.append(Rosto(caixa=(x1 + fx, y1 + fy, x1 + fx + fw, y1 + fy + fh), olhos_y=olhos_y,
                                    conf=float(f[14])))
        return rostos


class Detector:
    """Carrega os modelos e roda todos em cada frame (RF06): pose, EPI e (se disponível) rostos."""

    def __init__(self, config: Config) -> None:
        """Confere se os arquivos dos modelos existem, carrega pose e EPI e, se houver, o detector de rostos."""
        self.config = config
        for papel, caminho in (("EPI", config.modelos.epi), ("pose", config.modelos.pose)):
            if not Path(caminho).exists():
                dica = ("baixe com:  python -m src.run --baixar-modelos" if papel == "pose"
                        else "copie o epi_solda_best.pt gerado pelo notebook de treinamento para a pasta models/")
                raise ErroModelo(f"Modelo de {papel} não encontrado: {caminho}\n  -> {dica}")

        from ultralytics import YOLO   # importado aqui para os testes de regras não precisarem do Ultralytics

        self.modelo_epi = YOLO(str(config.modelos.epi))
        self.modelo_pose = YOLO(str(config.modelos.pose))
        if self.modelo_pose.task != "pose":
            raise ErroModelo(f"{config.modelos.pose} não é um modelo de pose (tarefa: {self.modelo_pose.task}).")

        nomes_modelo = {classe_interna(n, config.mapeamento_classes) for n in self.modelo_epi.names.values()}
        for epi in config.epis_ativos:
            if not any(EPI_DA_CLASSE.get(c) == epi for c in nomes_modelo):
                log.warning("O EPI %r está ativo, mas o modelo %s não tem essa classe (classes: %s).",
                            epi, Path(config.modelos.epi).name, sorted(nomes_modelo))
        self.rostos: DetectorRostos | None = None
        if config.modelos.rosto is not None and Path(config.modelos.rosto).exists():
            self.rostos = DetectorRostos(config.modelos.rosto, config.deteccao.conf_rosto,
                                         config.deteccao.tamanho_recorte_rosto)
        else:
            log.warning("Detector de rostos não encontrado (%s): o 'rosto visível' virá dos pontos da pose, que "
                        "erram com máscara de solda. Baixe com: python -m src.run --baixar-modelos",
                        config.modelos.rosto)
        self._conf_minima = min(config.epis[e].conf for e in config.epis_ativos)
        log.info("Modelos carregados: EPI=%s %s | pose=%s", Path(config.modelos.epi).name,
                 sorted(nomes_modelo), Path(config.modelos.pose).name)

    def detectar(self, frame: np.ndarray) -> tuple[list[Pessoa], list[DeteccaoEPI], list[Rosto] | None]:
        """Roda pose + rastreamento, o detector de EPI e o de rostos no mesmo frame.

        O terceiro item é None quando o detector de rostos não está disponível.
        """
        det = self.config.deteccao
        r_pose = self.modelo_pose.track(frame, persist=True, tracker="bytetrack.yaml", imgsz=det.imgsz_pose,
                                        conf=det.conf_pessoa, verbose=False)[0]
        # O modelo de EPI roda com o menor limiar entre os EPIs; o limiar de cada EPI é aplicado depois (RF15)
        r_epi = self.modelo_epi.predict(frame, imgsz=det.imgsz, conf=self._conf_minima, verbose=False)[0]
        brutas = []
        if r_epi.boxes is not None:
            for classe, conf, xyxy in zip(r_epi.boxes.cls.cpu().numpy(), r_epi.boxes.conf.cpu().numpy(),
                                          r_epi.boxes.xyxy.cpu().numpy()):
                brutas.append((r_epi.names[int(classe)], float(conf), tuple(float(v) for v in xyxy)))
        pessoas = converter_pessoas(r_pose)
        rostos = self.rostos.detectar(frame, pessoas, det.conf_keypoint) if self.rostos is not None else None
        return pessoas, mapear_deteccoes(brutas, self.config), rostos
