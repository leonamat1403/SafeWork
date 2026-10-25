"""Linha de comando da Fase 1: detecção da máscara de solda com janela do OpenCV.

Exemplos (na pasta do projeto, com o ambiente virtual ativo):
    python -m src.run --baixar-modelos                       # baixa os modelos de pose para models/ (uma vez)
    python -m src.run                                        # webcam 0
    python -m src.run --fonte testes_campo/video1.mp4 --posto mig_01 --csv
    python -m src.run --fonte testes_campo/foto1.jpg --salvar-saida
    python -m src.run --fonte "rtsp://usuario:senha@192.168.0.10/stream"
    python -m src.run --fonte testes_campo/video1.mp4 --benchmark

Teclas na janela: q ou ESC = sair, p = pausar/continuar.
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import time
from collections import Counter
from dataclasses import replace
from datetime import datetime
from pathlib import Path

os.environ.setdefault("YOLO_OFFLINE", "true")   # sem consultas à internet durante o uso (rede com proxy)

import cv2
import numpy as np

from src.config import Config, ErroConfig, carregar_config
from src.detector import Detector, ErroModelo
from src.occurrences import GerenciadorOcorrencias, Ocorrencia, RegistroCSV
from src.pipeline import Pipeline, ResultadoFrame, desenhar  # noqa: F401 (reexportados para quem importa de src.run)
from src.tipos import Estado
from src.video import ErroFonte, FonteVideo, ocultar_senha  # noqa: F401

log = logging.getLogger("epi_solda")

PASTA_SAIDA = Path("testes_campo")             # fora do git: pode conter pessoas reais
EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MODELOS_POSE = ("yolov8n-pose.pt", "yolo26n-pose.pt")
# Detector de rostos YuNet (OpenCV Zoo, licença MIT)
MODELO_ROSTOS = "face_detection_yunet_2023mar.onnx"
URL_MODELO_ROSTOS = ("https://github.com/opencv/opencv_zoo/raw/refs/heads/main/models/face_detection_yunet/"
                     + MODELO_ROSTOS)
TITULO_JANELA = "Verificador de EPIs de Solda (q = sair, p = pausar)"
ESPACO_MINIMO_MB = 500                         # abaixo disso, para de gravar a saída (RNF03: disco cheio)


# ---------------------------------------------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------------------------------------------
def nome_saida(fonte: str, extensao: str, prefixo: str = "saida") -> Path:
    """Caminho do arquivo de saída em testes_campo/, com data e hora no nome."""
    base = "webcam" if fonte.isdigit() else ("stream" if "://" in fonte else Path(fonte).stem)
    return PASTA_SAIDA / f"{prefixo}_{base}_{datetime.now():%Y%m%d_%H%M%S}{extensao}"


def espaco_livre_mb(pasta: Path) -> float:
    """Espaço livre em disco, em megabytes, no disco onde está `pasta`."""
    return shutil.disk_usage(pasta).free / 1e6


FRAMES_PARA_MEDIR_FPS = 30
FPS_PADRAO = 15.0


def fps_valido(valor: float) -> float | None:
    """O FPS informado pela fonte só é aceito se for plausível (1 a 120); webcams às vezes informam -1."""
    return float(valor) if 1 <= valor <= 120 else None


def estimar_fps(tempos: list[float]) -> float:
    """FPS real a partir dos instantes (em segundos) dos frames, limitado a 1–60."""
    if len(tempos) < 2 or tempos[-1] <= tempos[0]:
        return FPS_PADRAO
    return min(60.0, max(1.0, (len(tempos) - 1) / (tempos[-1] - tempos[0])))


class GravadorVideo:
    """Grava o vídeo anotado em testes_campo/ (opção --salvar-saida), parando se o disco estiver quase cheio.

    Ao vivo, o FPS informado pela câmera não é confiável e o processamento é mais lento que a câmera. Por isso os
    primeiros frames ficam guardados até medir o ritmo real, e só então o arquivo é criado (senão o vídeo sai
    acelerado ou corrompido).
    """

    def __init__(self, caminho: Path, fps_informado: float, ao_vivo: bool) -> None:
        """Prepara a gravação. Ao vivo (`fps` = None) o FPS será medido; em arquivo, usa o informado ou o padrão."""
        self.caminho = caminho
        self.fps = None if ao_vivo else (fps_valido(fps_informado) or FPS_PADRAO)
        self.escritor: cv2.VideoWriter | None = None
        self.ativo = True
        self._pendentes: list[tuple[float, np.ndarray]] = []
        self._frames = 0

    def _criar(self, frame: np.ndarray) -> None:
        """Cria o arquivo MP4 com o tamanho do frame dado; se não conseguir, desativa a gravação."""
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        altura, largura = frame.shape[:2]
        self.escritor = cv2.VideoWriter(str(self.caminho), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (largura, altura))
        if not self.escritor.isOpened():
            log.error("Não foi possível criar o vídeo de saída %s.", self.caminho)
            self.ativo = False

    def _descarregar(self) -> None:
        """Cria o arquivo (já com o FPS medido) e grava de uma vez os frames que estavam guardados."""
        if not self._pendentes:
            return
        if self.fps is None:
            self.fps = estimar_fps([t for t, _ in self._pendentes])
        self._criar(self._pendentes[0][1])
        pendentes, self._pendentes = self._pendentes, []
        for _, frame in pendentes:
            self._escrever(frame)

    def _escrever(self, frame: np.ndarray) -> None:
        """Grava um frame no arquivo; a cada 100 frames confere o disco e interrompe se estiver quase cheio (RNF03)."""
        if not self.ativo:
            return
        if self._frames % 100 == 0 and espaco_livre_mb(self.caminho.parent) < ESPACO_MINIMO_MB:
            log.error("Disco quase cheio (< %d MB livres): a gravação da saída foi interrompida.", ESPACO_MINIMO_MB)
            self.fechar()
            return
        self.escritor.write(frame)
        self._frames += 1

    def gravar(self, t: float, frame: np.ndarray) -> None:
        """Recebe um frame anotado e o instante `t` (s). Enquanto o FPS não é conhecido, só guarda o frame na espera."""
        if not self.ativo:
            return
        if self.escritor is None:
            self._pendentes.append((t, frame))
            if self.fps is None and len(self._pendentes) < FRAMES_PARA_MEDIR_FPS:
                return
            self._descarregar()
            return
        self._escrever(frame)

    def fechar(self) -> None:
        """Termina a gravação: descarrega os frames pendentes e fecha o arquivo de vídeo."""
        if self.escritor is None:
            self._descarregar()          # gravação curta: menos frames do que o necessário para medir o FPS
        if self.escritor is not None and self.ativo:
            self.escritor.release()
            self.ativo = False
            log.info("Vídeo anotado salvo em %s (%d frames, %.1f FPS)", self.caminho, self._frames, self.fps or 0)


def ler_imagem(caminho: Path) -> np.ndarray | None:
    """cv2.imread não abre caminhos com acentos no Windows; imdecode abre."""
    dados = np.fromfile(str(caminho), dtype=np.uint8)
    return cv2.imdecode(dados, cv2.IMREAD_COLOR) if dados.size else None


def salvar_imagem(caminho: Path, img: np.ndarray) -> None:
    """Salva a imagem anotada (cv2.imencode + tofile, que aceita acentos no caminho do Windows), se houver espaço."""
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
    """Tempo no formato hh:mm:ss (segundos inteiros), para o terminal e a tela."""
    m, s = divmod(int(segundos), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def linha_status(tempo: float, fps: float, resultado: ResultadoFrame) -> str:
    """Resumo de uma linha para o terminal."""
    pessoas = ", ".join(a.rotulo for a in resultado.avaliacoes) or "nenhuma pessoa"
    arco = "ARCO (frame ignorado) | " if resultado.saturado else ""
    return f"[{formatar_tempo(tempo)}] FPS {fps:4.1f} | {arco}{pessoas}"


def contar_estados(contagem: Counter, resultado: ResultadoFrame) -> None:
    """Soma o estado de cada EPI de cada pessoa (só frames realmente processados, sem arco)."""
    if resultado.saturado:
        return
    for aval in resultado.avaliacoes:
        for epi, avaliacao in aval.epis.items():
            contagem[(epi, avaliacao.estado)] += 1


def resumo_estados(contagem: Counter) -> list[str]:
    """Linhas do resumo, ex.: "mascara: CONFORME 120 (40%) | NAO_CONFORME 150 (50%) | INDETERMINADO 30 (10%)".

    Em um vídeo de teste SEM máscara, o percentual de CONFORME é a taxa de falso positivo do sistema.
    """
    linhas = []
    for epi in sorted({e for e, _ in contagem}):
        total = sum(n for (e, _), n in contagem.items() if e == epi)
        partes = [f"{estado.value} {contagem[(epi, estado)]} ({contagem[(epi, estado)] / total:.0%})" for estado in Estado]
        linhas.append(f"{epi} (pessoa x frame, total {total}): " + " | ".join(partes))
    return linhas


def processar_imagem(config: Config, pipeline: Pipeline, caminho: Path, args: argparse.Namespace) -> int:
    """Modo foto: avalia uma imagem, mostra o resultado no terminal (e na janela) e devolve o código de saída."""
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
    print("(Ocorrências precisam de vídeo ou câmera: uma foto não tem duração.)")
    if args.salvar_saida:
        salvar_imagem(nome_saida(str(caminho), ".jpg"), anotado)
    if not args.sem_janela:
        cv2.imshow(TITULO_JANELA, anotado)
        print("Pressione qualquer tecla na janela da imagem para fechar.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    return 0


def processar_video(config: Config, pipeline: Pipeline, fonte: FonteVideo, args: argparse.Namespace) -> int:
    """Modo vídeo/câmera: lê frames, avalia, registra ocorrências, mostra a janela e imprime o resumo no fim."""
    pular = config.deteccao.pular_frames   # processa 1 a cada `pular` frames; nos demais repete o último resultado
    lidos = processados = ignorados = 0
    contagem: Counter = Counter()
    resultado: ResultadoFrame | None = None
    anotado = None
    gravador: GravadorVideo | None = None
    gerenciador = GerenciadorOcorrencias(config)
    registro = None
    if args.csv is not None:
        caminho_csv = nome_saida(fonte.fonte, ".csv", "ocorrencias") if args.csv == "auto" else Path(args.csv)
        registro = RegistroCSV(caminho_csv, ocultar_senha(fonte.fonte), config.posto)
    total_ocorrencias = 0
    ultima: tuple[float, Ocorrencia] | None = None
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
                    contar_estados(contagem, resultado)
                    # Ocorrências só são avaliadas nos frames realmente processados (e nunca nos saturados pelo arco)
                    for oc in gerenciador.atualizar(resultado.avaliacoes, tempo, lidos, resultado.saturado):
                        total_ocorrencias += 1
                        ultima = (tempo, oc)
                        print(f"*** OCORRÊNCIA [{formatar_tempo(tempo)}] posto {config.posto} | {oc.descricao()}")
                        if registro is not None:
                            registro.gravar(oc)
                agora = time.perf_counter()
                instantaneo = 1.0 / max(agora - t_anterior, 1e-6)
                fps = instantaneo if fps == 0 else 0.9 * fps + 0.1 * instantaneo   # média móvel
                t_anterior = agora
                hud = [f"FPS {fps:.1f} | posto: {config.posto} | {formatar_tempo(tempo)} | ocorrencias: {total_ocorrencias}"]
                alerta = None
                if ultima is not None and tempo - ultima[0] < 3.0:   # aviso na tela por 3 s
                    alerta = f"OCORRENCIA REGISTRADA: pessoa #{ultima[1].track_id}"
                anotado = desenhar(frame, resultado, hud, debug=args.debug, alerta=alerta)
                if args.salvar_saida:
                    if gravador is None:
                        gravador = GravadorVideo(nome_saida(fonte.fonte, ".mp4"), fonte.fps, fonte.tipo != "arquivo")
                    gravador.gravar(tempo, anotado)
                if tempo - ultimo_status >= 1.0:
                    print(linha_status(tempo, fps, resultado))
                    ultimo_status = tempo
                if args.max_frames and lidos >= args.max_frames:
                    break
            if not args.sem_janela and anotado is not None:
                cv2.imshow(TITULO_JANELA, anotado)
                # waitKey também atualiza a janela; em pausa espera mais (50 ms) para não gastar CPU à toa
                tecla = cv2.waitKey(1 if not pausado else 50) & 0xFF
                if tecla in (ord("q"), 27):
                    break
                if tecla == ord("p"):
                    pausado = not pausado
                    print("PAUSADO" if pausado else "CONTINUANDO")
                if cv2.getWindowProperty(TITULO_JANELA, cv2.WND_PROP_VISIBLE) < 1:   # janela fechada no X
                    break
    finally:   # roda mesmo com erro ou Ctrl+C: libera câmera, arquivos e janelas
        fonte.fechar()
        if gravador is not None:
            gravador.fechar()
        if registro is not None:
            registro.fechar()
        cv2.destroyAllWindows()

    duracao = time.perf_counter() - t_inicio
    print("\n===== Resumo =====")
    print(f"Fonte: {ocultar_senha(fonte.fonte)} | posto: {config.posto}")
    print(f"Frames lidos: {lidos} | processados: {processados} | ignorados pelo arco: {ignorados}")
    print(f"Duração: {duracao:.1f} s | FPS médio: {lidos / duracao if duracao > 0 else 0:.1f}")
    for linha in resumo_estados(contagem):
        print(linha)
    print(f"Ocorrências registradas: {total_ocorrencias}" + (f" | CSV: {registro.caminho}" if registro else ""))
    for linha in gerenciador.resumo_por_pessoa():
        print("  " + linha)
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
    destino = pasta / MODELO_ROSTOS
    if destino.exists():
        print(f"{MODELO_ROSTOS}: já existe em {destino}")
    else:
        try:
            import urllib.request
            urllib.request.urlretrieve(URL_MODELO_ROSTOS, destino)
            if destino.stat().st_size < 100_000:   # o GitHub devolveu um ponteiro, não o modelo
                destino.unlink()
                raise RuntimeError("arquivo baixado incompleto")
            print(f"{MODELO_ROSTOS}: baixado em {destino}")
        except Exception as erro:   # sem internet, proxy etc.
            print(f"{MODELO_ROSTOS}: falha no download ({erro}). Baixe {URL_MODELO_ROSTOS} em outra rede e "
                  f"copie para {pasta}/")
            return 5
    if not (pasta / "epi_solda_best.pt").exists():
        print("Atenção: falta models/epi_solda_best.pt (gerado pelo notebook de treinamento).")
    return 0


# ---------------------------------------------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------------------------------------------
def criar_parser() -> argparse.ArgumentParser:
    """Define as opções da linha de comando (fonte, config, posto, saída, depuração, benchmark e download)."""
    p = argparse.ArgumentParser(prog="python -m src.run", description="Verificador de EPIs de Solda – Fase 1 "
                                "(validação da detecção da máscara de solda).")
    p.add_argument("--fonte", help="webcam (0, 1, ...), arquivo de imagem/vídeo ou URL RTSP. Padrão: webcam 0.")
    p.add_argument("--config", default="config.yaml", help="arquivo de configuração (padrão: config.yaml)")
    p.add_argument("--posto", default="padrao", help="posto de solda definido em 'postos' no config.yaml")
    p.add_argument("--salvar-saida", action="store_true", help="salva a imagem/vídeo anotado em testes_campo/")
    p.add_argument("--debug", action="store_true", help="desenha a região da cabeça, a linha dos olhos e os pontos")
    p.add_argument("--sem-janela", action="store_true", help="não abre janela (só terminal)")
    p.add_argument("--max-frames", type=int, default=0, help="para depois de N frames (0 = sem limite)")
    p.add_argument("--csv", nargs="?", const="auto", help="grava as ocorrências em CSV (sem caminho: "
                   "testes_campo/ocorrencias_<fonte>_<data>.csv)")
    p.add_argument("--benchmark", action="store_true", help="mede o FPS com imgsz 640 e 960 e sai")
    p.add_argument("--baixar-modelos", action="store_true", help="baixa os modelos de pose para models/ e sai")
    return p


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada. Códigos de saída: 0 ok, 2 config inválida, 3 modelo ausente, 4 fonte inválida, 5 download."""
    args = criar_parser().parse_args(argv)
    # Saída padrão (stdout): no PowerShell, mensagens em stderr aparecem em vermelho como se fossem erros
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
                        stream=sys.stdout)

    if args.baixar_modelos:
        os.environ["YOLO_OFFLINE"] = "false"   # só aqui a internet é liberada, para baixar os modelos
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
