"""Modelos YOLO: pose (pessoas + pontos do corpo + rastreamento ByteTrack) e detector de EPI de solda.

Este é o ÚNICO módulo que conhece o Ultralytics. Ele converte os resultados dos modelos para as estruturas
simples de src/tipos.py, que o resto do sistema usa.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

import numpy as np

from src.config import EPI_DA_CLASSE, Config
from src.tipos import Caixa, DeteccaoEPI, Keypoint, Pessoa

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


class Detector:
    """Carrega os dois modelos e roda ambos em cada frame (RF06)."""

    def __init__(self, config: Config) -> None:
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
        self._conf_minima = min(config.epis[e].conf for e in config.epis_ativos)
        log.info("Modelos carregados: EPI=%s %s | pose=%s", Path(config.modelos.epi).name,
                 sorted(nomes_modelo), Path(config.modelos.pose).name)

    def detectar(self, frame: np.ndarray) -> tuple[list[Pessoa], list[DeteccaoEPI]]:
        """Roda pose + rastreamento e o detector de EPI no mesmo frame."""
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
        return converter_pessoas(r_pose), mapear_deteccoes(brutas, self.config)
