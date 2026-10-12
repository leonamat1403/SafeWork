"""Linha de comando da Fase 1: detecção da máscara de solda com janela do OpenCV.

Exemplos (na pasta do projeto, com o ambiente virtual ativo):
    python -m src.run --baixar-modelos                       # baixa os modelos de pose para models/ (uma vez)
    python -m src.run                                        # webcam 0
    python -m src.run --fonte testes_campo/video1.mp4 --posto mig_01
    python -m src.run --fonte testes_campo/foto1.jpg --salvar-saida
    python -m src.run --fonte "rtsp://usuario:senha@192.168.0.10/stream"
    python -m src.run --fonte testes_campo/video1.mp4 --benchmark

Teclas na janela: q ou ESC = sair, p = pausar/continuar.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

os.environ.setdefault("YOLO_OFFLINE", "true")   # sem consultas à internet durante o uso (rede com proxy)

import cv2
import numpy as np

from src.arc_filter import frame_saturado
from src.compliance import CORES_BGR, AvaliacaoPessoa, avaliar_frame
from src.config import Config, ErroConfig, carregar_config
from src.detector import Detector, ErroModelo
from src.tipos import DeteccaoEPI

log = logging.getLogger("epi_solda")

PASTA_SAIDA = Path("testes_campo")             # fora do git: pode conter pessoas reais
EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MODELOS_POSE = ("yolov8n-pose.pt", "yolo26n-pose.pt")
TITULO_JANELA = "Verificador de EPIs de Solda (q = sair, p = pausar)"
ESPACO_MINIMO_MB = 500                         # abaixo disso, para de gravar a saída (RNF03: disco cheio)


class ErroFonte(RuntimeError):
    """Câmera, arquivo ou stream indisponível."""


# ---------------------------------------------------------------------------------------------------------------
# Processamento de um frame
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class ResultadoFrame:
    avaliacoes: list[AvaliacaoPessoa]
    deteccoes: list[DeteccaoEPI]
    saturado: bool
    fracao_saturada: float


class Pipeline:
    """Filtro do arco -> modelos -> regras. Guarda o último resultado válido para os frames ignorados."""

    def __init__(self, config: Config, detector) -> None:
        self.config = config
        self.detector = detector
        self.ultimas_avaliacoes: list[AvaliacaoPessoa] = []
        self.ultimas_deteccoes: list[DeteccaoEPI] = []

    def processar(self, frame: np.ndarray) -> ResultadoFrame:
        saturado, fracao = frame_saturado(frame, self.config.arco)
        if saturado:
            # RF14: frame estourado pelo arco não muda nenhum estado; repete o último resultado válido
            return ResultadoFrame(self.ultimas_avaliacoes, self.ultimas_deteccoes, True, fracao)
        pessoas, deteccoes = self.detector.detectar(frame)
        self.ultimas_avaliacoes = avaliar_frame(pessoas, deteccoes, self.config)
        self.ultimas_deteccoes = deteccoes
        return ResultadoFrame(self.ultimas_avaliacoes, deteccoes, False, fracao)


# ---------------------------------------------------------------------------------------------------------------
# Desenho
# ---------------------------------------------------------------------------------------------------------------
def _texto_com_fundo(img: np.ndarray, texto: str, x: int, y: int, fundo: tuple[int, int, int],
                     escala: float = 0.55) -> None:
    """Escreve um texto com retângulo de fundo; (x, y) é o canto inferior esquerdo do fundo."""
    (larg, alt), base = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, 1)
    y = max(alt + base + 2, y)
    cor_texto = (0, 0, 0) if fundo == CORES_BGR["amarelo"] else (255, 255, 255)
    cv2.rectangle(img, (x, y - alt - base - 4), (x + larg + 6, y), fundo, -1)
    cv2.putText(img, texto, (x + 3, y - base - 2), cv2.FONT_HERSHEY_SIMPLEX, escala, cor_texto, 1, cv2.LINE_AA)


def desenhar(frame: np.ndarray, resultado: ResultadoFrame, linhas_hud: list[str], debug: bool = False) -> np.ndarray:
    """Desenha caixas das pessoas (cor RF04), rótulos, máscaras detectadas e o painel de informações (RF05)."""
    img = frame.copy()
    for det in resultado.deteccoes:
        x1, y1, x2, y2 = map(int, det.caixa)
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), 1)
        cv2.putText(img, f"{det.classe} {det.conf:.2f}", (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.4, (255, 255, 255), 1, cv2.LINE_AA)
    for aval in resultado.avaliacoes:
        cor = CORES_BGR[aval.cor]
        x1, y1, x2, y2 = map(int, aval.pessoa.caixa)
        cv2.rectangle(img, (x1, y1), (x2, y2), cor, 3)
        _texto_com_fundo(img, aval.rotulo, x1, y1, cor)
        if debug:
            if aval.regioes.cabeca is not None:
                cx1, cy1, cx2, cy2 = map(int, aval.regioes.cabeca)
                cv2.rectangle(img, (cx1, cy1), (cx2, cy2), (255, 255, 0), 1)
            if aval.regioes.linha_olhos_y is not None and aval.regioes.cabeca is not None:
                y = int(aval.regioes.linha_olhos_y)
                cv2.line(img, (int(aval.regioes.cabeca[0]), y), (int(aval.regioes.cabeca[2]), y), (255, 255, 0), 1)
            for kp in aval.pessoa.keypoints:
                if kp.conf >= 0.5:
                    cv2.circle(img, (int(kp.x), int(kp.y)), 3, (0, 255, 255), -1)

    y = 22
    for linha in linhas_hud:
        _texto_com_fundo(img, linha, 8, y, (40, 40, 40))
        y += 24
    if resultado.saturado:
        _texto_com_fundo(img, f"ARCO DETECTADO - frame ignorado ({resultado.fracao_saturada:.0%} saturado)",
                         8, y, CORES_BGR["vermelho"], escala=0.65)
    if any(a.regioes.fallback for a in resultado.avaliacoes):
        _texto_com_fundo(img, "MODO SEM POSE (fallback)", 8, y + 28, CORES_BGR["amarelo"])
    return img


# ---------------------------------------------------------------------------------------------------------------
# Fonte de vídeo e gravação
# ---------------------------------------------------------------------------------------------------------------
def ocultar_senha(texto: str) -> str:
    """Esconde usuário/senha de URLs (rtsp://usuario:senha@ip -> rtsp://***@ip) antes de mostrar no terminal."""
    return re.sub(r"//[^/@]+@", "//***@", texto)


class FonteVideo:
    """Webcam (número), arquivo de vídeo ou stream de rede (RTSP/HTTP), com reconexão automática (RNF03)."""

    def __init__(self, fonte: str) -> None:
        self.fonte = fonte
        if fonte.isdigit():
            self.tipo = "webcam"
        elif fonte.lower().startswith(("rtsp://", "rtmp://", "http://", "https://")):
            self.tipo = "rede"
        else:
            if not Path(fonte).exists():
                raise ErroFonte(f"Arquivo não encontrado: {fonte}")
            self.tipo = "arquivo"
        self._inicio = time.monotonic()
        self.cap = self._abrir()
        if not self.cap.isOpened():
            raise ErroFonte(f"Não foi possível abrir a fonte {ocultar_senha(fonte)!r} ({self.tipo}). "
                            "Confira se a câmera está conectada e não está em uso por outro programa.")

    def _abrir(self) -> cv2.VideoCapture:
        if self.tipo == "webcam":
            api = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY   # DirectShow abre webcams mais rápido no Windows
            return cv2.VideoCapture(int(self.fonte), api)
        return cv2.VideoCapture(self.fonte)

    @property
    def fps(self) -> float:
        return self.cap.get(cv2.CAP_PROP_FPS) or 0.0

    def _tempo(self) -> float:
        """Tempo do frame em segundos: posição no vídeo (arquivo) ou tempo desde o início (ao vivo)."""
        if self.tipo == "arquivo":
            return self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        return time.monotonic() - self._inicio

    def ler(self) -> tuple[np.ndarray | None, float]:
        """Lê o próximo frame. Retorna (None, 0) no fim do arquivo; ao vivo, tenta reconectar até conseguir."""
        ok, frame = self.cap.read()
        if ok:
            return frame, self._tempo()
        if self.tipo == "arquivo":
            return None, 0.0
        espera = 1
        while True:
            log.warning("Sem imagem de %s. Nova tentativa em %d s (Ctrl+C para sair)...", ocultar_senha(self.fonte), espera)
            time.sleep(espera)
            self.cap.release()
            self.cap = self._abrir()
            ok, frame = self.cap.read()
            if ok:
                log.info("Fonte reconectada.")
                return frame, self._tempo()
            espera = min(espera * 2, 30)

    def fechar(self) -> None:
        self.cap.release()


def nome_saida(fonte: str, extensao: str) -> Path:
    """Caminho do arquivo de saída em testes_campo/, com data e hora no nome."""
    base = "webcam" if fonte.isdigit() else ("stream" if "://" in fonte else Path(fonte).stem)
    return PASTA_SAIDA / f"saida_{base}_{datetime.now():%Y%m%d_%H%M%S}{extensao}"


def espaco_livre_mb(pasta: Path) -> float:
    return shutil.disk_usage(pasta).free / 1e6


class GravadorVideo:
    """Grava o vídeo anotado em testes_campo/ (opção --salvar-saida), parando se o disco estiver quase cheio."""

    def __init__(self, caminho: Path, fps: float, tamanho: tuple[int, int]) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho = caminho
        self.escritor = cv2.VideoWriter(str(caminho), cv2.VideoWriter_fourcc(*"mp4v"), fps or 15.0, tamanho)
        self.ativo = self.escritor.isOpened()
        self._frames = 0
        if not self.ativo:
            log.error("Não foi possível criar o vídeo de saída %s.", caminho)

    def gravar(self, frame: np.ndarray) -> None:
        if not self.ativo:
            return
        if self._frames % 100 == 0 and espaco_livre_mb(self.caminho.parent) < ESPACO_MINIMO_MB:
            log.error("Disco quase cheio (< %d MB livres): a gravação da saída foi interrompida.", ESPACO_MINIMO_MB)
            self.fechar()
            return
        self.escritor.write(frame)
        self._frames += 1

    def fechar(self) -> None:
        if self.ativo:
            self.escritor.release()
            self.ativo = False
            log.info("Vídeo anotado salvo em %s", self.caminho)


def ler_imagem(caminho: Path) -> np.ndarray | None:
    """cv2.imread não abre caminhos com acentos no Windows; imdecode abre."""
    dados = np.fromfile(str(caminho), dtype=np.uint8)
    return cv2.imdecode(dados, cv2.IMREAD_COLOR) if dados.size else None


def salvar_imagem(caminho: Path, img: np.ndarray) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if espaco_livre_mb(caminho.parent) < ESPACO_MINIMO_MB:
        log.error("Disco quase cheio (< %d MB livres): imagem não salva.", ESPACO_MINIMO_MB)
        return
    ok, buffer = cv2.imencode(caminho.suffix, img)
    if ok:
        buffer.tofile(str(caminho))
        log.info("Imagem anotada salva em %s", caminho)


# ---------------------------------------------------------------------------------------------------------------
# Modos de execução
# ---------------------------------------------------------------------------------------------------------------
def formatar_tempo(segundos: float) -> str:
    m, s = divmod(int(segundos), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def linha_status(tempo: float, fps: float, resultado: ResultadoFrame) -> str:
    """Resumo de uma linha para o terminal."""
    pessoas = ", ".join(a.rotulo for a in resultado.avaliacoes) or "nenhuma pessoa"
    arco = "ARCO (frame ignorado) | " if resultado.saturado else ""
    return f"[{formatar_tempo(tempo)}] FPS {fps:4.1f} | {arco}{pessoas}"


def processar_imagem(config: Config, pipeline: Pipeline, caminho: Path, args: argparse.Namespace) -> int:
    frame = ler_imagem(caminho)
    if frame is None:
        log.error("Não foi possível ler a imagem %s.", caminho)
        return 4
    resultado = pipeline.processar(frame)
    anotado = desenhar(frame, resultado, [f"posto: {config.posto}"], debug=args.debug)
    print(linha_status(0, 0, resultado))
    for aval in resultado.avaliacoes:
        for epi, a in aval.epis.items():
            conf = f" (conf {a.conf:.2f})" if a.conf is not None else ""
            print(f"   {aval.rotulo.split()[0]} {epi}: {a.estado.value}{conf} - {a.motivo}")
    if args.salvar_saida:
        salvar_imagem(nome_saida(str(caminho), ".jpg"), anotado)
    if not args.sem_janela:
        cv2.imshow(TITULO_JANELA, anotado)
        print("Pressione qualquer tecla na janela da imagem para fechar.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    return 0


def processar_video(config: Config, pipeline: Pipeline, fonte: FonteVideo, args: argparse.Namespace) -> int:
    pular = config.deteccao.pular_frames
    lidos = processados = ignorados = 0
    resultado: ResultadoFrame | None = None
    anotado = None
    gravador: GravadorVideo | None = None
    fps = 0.0
    ultimo_status = -1.0
    t_anterior = t_inicio = time.perf_counter()
    pausado = False
    try:
        while True:
            if not pausado:
                frame, tempo = fonte.ler()
                if frame is None:
                    break
                lidos += 1
                if resultado is None or (lidos - 1) % pular == 0:
                    resultado = pipeline.processar(frame)
                    processados += 1
                    ignorados += int(resultado.saturado)
                agora = time.perf_counter()
                instantaneo = 1.0 / max(agora - t_anterior, 1e-6)
                fps = instantaneo if fps == 0 else 0.9 * fps + 0.1 * instantaneo   # média móvel
                t_anterior = agora
                hud = [f"FPS {fps:.1f} | posto: {config.posto} | {formatar_tempo(tempo)}"]
                anotado = desenhar(frame, resultado, hud, debug=args.debug)
                if args.salvar_saida:
                    if gravador is None:
                        altura, largura = anotado.shape[:2]
                        gravador = GravadorVideo(nome_saida(fonte.fonte, ".mp4"), fonte.fps, (largura, altura))
                    gravador.gravar(anotado)
                if tempo - ultimo_status >= 1.0:
                    print(linha_status(tempo, fps, resultado))
                    ultimo_status = tempo
                if args.max_frames and lidos >= args.max_frames:
                    break
            if not args.sem_janela and anotado is not None:
                cv2.imshow(TITULO_JANELA, anotado)
                tecla = cv2.waitKey(1 if not pausado else 50) & 0xFF
                if tecla in (ord("q"), 27):
                    break
                if tecla == ord("p"):
                    pausado = not pausado
                    print("PAUSADO" if pausado else "CONTINUANDO")
                if cv2.getWindowProperty(TITULO_JANELA, cv2.WND_PROP_VISIBLE) < 1:   # janela fechada no X
                    break
    finally:
        fonte.fechar()
        if gravador is not None:
            gravador.fechar()
        cv2.destroyAllWindows()

    duracao = time.perf_counter() - t_inicio
    print("\n===== Resumo =====")
    print(f"Fonte: {ocultar_senha(fonte.fonte)} | posto: {config.posto}")
    print(f"Frames lidos: {lidos} | processados: {processados} | ignorados pelo arco: {ignorados}")
    print(f"Duração: {duracao:.1f} s | FPS médio: {lidos / duracao if duracao > 0 else 0:.1f}")
    return 0


def coletar_frames(fonte: str | None, quantidade: int) -> list[np.ndarray]:
    """Frames para o benchmark: de um vídeo/webcam, ou uma imagem repetida (padrão: imagem de exemplo do Ultralytics)."""
    if fonte is None:
        import ultralytics
        fonte = str(Path(ultralytics.__file__).parent / "assets" / "bus.jpg")
    if Path(fonte).suffix.lower() in EXTENSOES_IMAGEM:
        img = ler_imagem(Path(fonte))
        if img is None:
            raise ErroFonte(f"Não foi possível ler {fonte}")
        return [img] * quantidade
    video = FonteVideo(fonte)
    frames = []
    try:
        while len(frames) < quantidade:
            frame, _ = video.ler()
            if frame is None:
                break
            frames.append(frame)
    finally:
        video.fechar()
    if not frames:
        raise ErroFonte(f"Nenhum frame lido de {ocultar_senha(fonte)}")
    return frames


def benchmark(config: Config, fonte: str | None, quantidade: int = 60) -> int:
    """Mede o FPS do processamento completo (pose + máscara + regras + desenho), sem janela (RNF01, RF16)."""
    frames = coletar_frames(fonte, quantidade)
    altura, largura = frames[0].shape[:2]
    print(f"Benchmark: {len(frames)} frames de {largura}x{altura} | CPU: {cpu_nome()}")
    combinacoes = [(640, 640), (960, 640), (960, 960)]
    print(f"{'imgsz máscara':>14} {'imgsz pose':>11} {'ms/frame':>9} {'FPS':>6}")
    for imgsz, imgsz_pose in combinacoes:
        cfg = replace(config, deteccao=replace(config.deteccao, imgsz=imgsz, imgsz_pose=imgsz_pose))
        pipeline = Pipeline(cfg, Detector(cfg))
        for frame in frames[:3]:                    # aquecimento (a 1ª inferência é sempre mais lenta)
            pipeline.processar(frame)
        inicio = time.perf_counter()
        for frame in frames:
            desenhar(frame, pipeline.processar(frame), [])
        por_frame = (time.perf_counter() - inicio) / len(frames)
        print(f"{imgsz:>14} {imgsz_pose:>11} {por_frame * 1000:>9.0f} {1 / por_frame:>6.1f}")
    print("Meta (RNF01): >= 5 FPS com imgsz 640. Copie esta tabela para o relatório de validação.")
    return 0


def cpu_nome() -> str:
    """Nome comercial do processador (no Windows, lido do registro), para o relatório."""
    import platform
    if os.name == "nt":
        try:
            import winreg
            chave = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return str(winreg.QueryValueEx(chave, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    return platform.processor() or platform.machine()


def baixar_modelos(pasta: Path) -> int:
    """Baixa os modelos de pose pré-treinados (COCO) para uso offline (rede com proxy)."""
    from ultralytics.utils.downloads import attempt_download_asset

    pasta.mkdir(parents=True, exist_ok=True)
    for nome in MODELOS_POSE:
        destino = pasta / nome
        if destino.exists():
            print(f"{nome}: já existe em {destino}")
            continue
        try:
            attempt_download_asset(destino)
            print(f"{nome}: baixado em {destino}")
        except Exception as erro:   # sem internet, proxy etc.
            print(f"{nome}: falha no download ({erro}). Baixe em outra rede e copie para {pasta}/")
            return 5
    if not (pasta / "epi_solda_best.pt").exists():
        print("Atenção: falta models/epi_solda_best.pt (gerado pelo notebook de treinamento).")
    return 0


# ---------------------------------------------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------------------------------------------
def criar_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m src.run", description="Verificador de EPIs de Solda – Fase 1 "
                                "(validação da detecção da máscara de solda).")
    p.add_argument("--fonte", help="webcam (0, 1, ...), arquivo de imagem/vídeo ou URL RTSP. Padrão: webcam 0.")
    p.add_argument("--config", default="config.yaml", help="arquivo de configuração (padrão: config.yaml)")
    p.add_argument("--posto", default="padrao", help="posto de solda definido em 'postos' no config.yaml")
    p.add_argument("--salvar-saida", action="store_true", help="salva a imagem/vídeo anotado em testes_campo/")
    p.add_argument("--debug", action="store_true", help="desenha a região da cabeça, a linha dos olhos e os pontos")
    p.add_argument("--sem-janela", action="store_true", help="não abre janela (só terminal)")
    p.add_argument("--max-frames", type=int, default=0, help="para depois de N frames (0 = sem limite)")
    p.add_argument("--benchmark", action="store_true", help="mede o FPS com imgsz 640 e 960 e sai")
    p.add_argument("--baixar-modelos", action="store_true", help="baixa os modelos de pose para models/ e sai")
    return p


def main(argv: list[str] | None = None) -> int:
    args = criar_parser().parse_args(argv)
    # Saída padrão (stdout): no PowerShell, mensagens em stderr aparecem em vermelho como se fossem erros
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
                        stream=sys.stdout)

    if args.baixar_modelos:
        os.environ["YOLO_OFFLINE"] = "false"
        return baixar_modelos(Path(args.config).resolve().parent / "models")

    try:
        config = carregar_config(args.config, args.posto)
    except ErroConfig as erro:
        log.error("Configuração inválida: %s", erro)
        return 2
    log.info("Posto: %s (%s) | EPIs exigidos: %s | imgsz: %d", config.posto, config.descricao,
             ", ".join(config.epis_ativos), config.deteccao.imgsz)

    try:
        if args.benchmark:
            return benchmark(config, args.fonte)
        pipeline = Pipeline(config, Detector(config))
        fonte = args.fonte if args.fonte is not None else "0"
        if Path(fonte).suffix.lower() in EXTENSOES_IMAGEM:
            if not Path(fonte).exists():
                raise ErroFonte(f"Arquivo não encontrado: {fonte}")
            return processar_imagem(config, pipeline, Path(fonte), args)
        return processar_video(config, pipeline, FonteVideo(fonte), args)
    except ErroModelo as erro:
        log.error("%s", erro)
        return 3
    except ErroFonte as erro:
        log.error("%s", erro)
        return 4
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
