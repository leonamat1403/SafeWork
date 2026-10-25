"""Confere se alguma imagem de treino é (quase) um quadro dos vídeos de teste de campo.

Os vídeos de teste nunca podem entrar no treino, senão as métricas da Etapa 1.5 deixam de valer. Imagens de bancos
(Pexels, Shutterstock...) às vezes saem do mesmo vídeo ou da mesma sessão de fotos. O script compara cada imagem dos
datasets com quadros dos vídeos de teste (1 por segundo) de duas formas:
  - hash perceptual (pHash, 64 bits): acha a mesma imagem redimensionada ou recomprimida;
  - semelhança de características (embedding do YOLO, centralizado): acha recortes e quadros vizinhos da mesma cena.
    Sem centralizar, quase todas as imagens de solda dão semelhança ~0,98 entre si (a parte "genérica" do vetor
    domina); subtraindo o vetor médio, sobra o que distingue uma cena da outra.

Saídas (em testes_campo/vazamento/, fora do git porque mostram pessoas):
  - pares.csv: para cada imagem, o quadro de teste mais parecido (vídeo, segundo, distância do hash, semelhança);
  - folha_pares.jpg: os pares mais parecidos lado a lado, para a conferência visual;
  - suspeitas.txt: as imagens com hash próximo (distância <= --max-hamming), candidatas a sair do treino.
A decisão final é visual: confira a folha e liste as que forem da mesma cena em EXCLUIR_PARECIDAS_COM_TESTE
(célula 1 do notebook de treino).

Uso (na pasta do projeto, com o ambiente .venv ativo):
    python ferramentas/conferir_vazamento.py --datasets dados/roboflow_v4/welder dados/roboflow_v4/safeweld
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# Permite importar módulos do projeto mesmo rodando o script de dentro de ferramentas/.
sys.path.insert(0, str(RAIZ))
# Impede o ultralytics de tentar baixar arquivos da internet.
os.environ.setdefault("YOLO_OFFLINE", "true")

import cv2  # noqa: E402
import numpy as np  # noqa: E402

EXTENSOES_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MODELO_EMBEDDING = RAIZ / "models" / "yolov8n-pose.pt"


def phash(imagem: np.ndarray) -> int:
    """Hash perceptual de 64 bits: sinais das baixas frequências da DCT da imagem em 32x32 tons de cinza."""
    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY) if imagem.ndim == 3 else imagem
    pequena = cv2.resize(cinza, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    baixas = cv2.dct(pequena)[:8, :8].flatten()[1:]  # sem o componente contínuo (brilho médio)
    bits = baixas > np.median(baixas)
    return int("".join("1" if b else "0" for b in bits), 2)


def distancia_hamming(a: int, b: int) -> int:
    """Quantos bits diferem entre dois hashes (0 = idênticos; quanto menor, mais parecidas as imagens)."""
    return bin(a ^ b).count("1")


def quadros_de_teste(pasta: Path, intervalo_s: float = 1.0) -> list[tuple[str, float, np.ndarray]]:
    """Um quadro a cada `intervalo_s` de cada vídeo da pasta (e subpastas), reduzido para no máximo 640 px."""
    quadros = []
    for video in sorted(p for p in pasta.rglob("*") if p.suffix.lower() in EXTENSOES_VIDEO):
        if video.stem.startswith("saida_"):  # vídeos anotados gerados pelo próprio sistema
            continue
        cap = cv2.VideoCapture(str(video))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        duracao = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
        t = 0.0
        while t < duracao:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, quadro = cap.read()
            if not ok:
                break
            escala = 640 / max(quadro.shape[:2])
            if escala < 1:
                quadro = cv2.resize(quadro, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
            quadros.append((str(video.relative_to(RAIZ)) if video.is_relative_to(RAIZ) else str(video), t, quadro))
            t += intervalo_s
        cap.release()
    return quadros


def imagens_dos_datasets(pastas: list[Path]) -> list[Path]:
    """Lista, em ordem, as imagens (pela extensão) das pastas e subpastas dos datasets."""
    return sorted(p for pasta in pastas for p in pasta.rglob("*") if p.suffix.lower() in EXTENSOES_IMAGEM)


def embeddings(imagens: list[np.ndarray], lote: int = 32) -> np.ndarray:
    """Vetor de características de cada imagem, pelo backbone do YOLO."""
    from ultralytics import YOLO

    modelo = YOLO(str(MODELO_EMBEDDING))
    vetores = []
    for i in range(0, len(imagens), lote):
        vetores.extend(v.cpu().numpy().ravel() for v in modelo.embed(imagens[i:i + lote], imgsz=320, verbose=False))
    return np.stack(vetores)


def centralizar(*conjuntos: np.ndarray) -> list[np.ndarray]:
    """Subtrai o vetor médio de todos os conjuntos e normaliza cada vetor (para a semelhança de cosseno)."""
    media = np.concatenate(conjuntos).mean(axis=0)
    saida = []
    for c in conjuntos:
        c = c - media
        saida.append(c / (np.linalg.norm(c, axis=1, keepdims=True) + 1e-9))
    return saida


def ler(caminho: Path) -> np.ndarray | None:
    """Lê a imagem e reduz para no máximo 640 px de lado; None se o arquivo não for uma imagem legível."""
    imagem = cv2.imread(str(caminho))
    if imagem is not None:
        escala = 640 / max(imagem.shape[:2])
        if escala < 1:
            imagem = cv2.resize(imagem, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    return imagem


def folha_de_pares(pares: list[dict], saida: Path, lado: int = 260) -> None:
    """Imagem do dataset (esquerda) e quadro de teste mais parecido (direita), um par por linha de 3 pares."""
    celulas = []
    for par in pares:
        lado_a_lado = []
        for imagem in (par["img_dataset"], par["img_teste"]):
            escala = lado / max(imagem.shape[:2])
            reduzida = cv2.resize(imagem, (int(imagem.shape[1] * escala), int(imagem.shape[0] * escala)))
            fundo = np.full((lado, lado, 3), 255, np.uint8)
            fundo[:reduzida.shape[0], :reduzida.shape[1]] = reduzida
            lado_a_lado.append(fundo)
        celula = np.vstack([np.hstack(lado_a_lado), np.full((28, 2 * lado, 3), 255, np.uint8)])
        texto1 = f"sim {par['semelhanca']:.3f} | hash {par['hamming']} | {Path(par['imagem']).name[:34]}"
        texto2 = f"{Path(par['video']).name[:40]} @ {par['segundo']:.0f}s"
        cv2.putText(celula, texto1, (3, lado + 11), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 0, 0), 1)
        cv2.putText(celula, texto2, (3, lado + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 0, 0), 1)
        celulas.append(cv2.copyMakeBorder(celula, 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=(120, 120, 120)))
    while len(celulas) % 3:
        celulas.append(np.full_like(celulas[0], 255))
    linhas = [np.hstack(celulas[i:i + 3]) for i in range(0, len(celulas), 3)]
    cv2.imwrite(str(saida), np.vstack(linhas), [cv2.IMWRITE_JPEG_QUALITY, 85])


def main() -> None:
    """Compara as imagens dos datasets com os quadros dos vídeos de teste.

    Grava pares.csv, suspeitas.txt e folha_pares.jpg na pasta de saída.
    """
    parser = argparse.ArgumentParser(description="Confere se imagens de treino vieram dos vídeos de teste.")
    parser.add_argument("--datasets", nargs="+", type=Path, required=True, help="pastas dos datasets (YOLOv8)")
    parser.add_argument("--videos", type=Path, default=RAIZ / "testes_campo", help="pasta dos vídeos de teste")
    parser.add_argument("--saida", type=Path, default=RAIZ / "testes_campo" / "vazamento")
    parser.add_argument("--max-hamming", type=int, default=10, help="distância de hash considerada 'mesma imagem'")
    parser.add_argument("--pares", type=int, default=45, help="quantos pares mostrar na folha de conferência")
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)

    quadros = quadros_de_teste(args.videos)
    caminhos = imagens_dos_datasets(args.datasets)
    print(f"{len(quadros)} quadros de teste; {len(caminhos)} imagens nos datasets")

    hashes_teste = [phash(q) for _, _, q in quadros]
    imagens, validos = [], []
    for caminho in caminhos:
        imagem = ler(caminho)
        if imagem is not None:
            imagens.append(imagem)
            validos.append(caminho)
    hashes_dataset = [phash(im) for im in imagens]

    cache = args.saida / "cache_embeddings.npz"  # evita recalcular tudo a cada execução
    # A chave muda se mudarem os quadros ou a lista de imagens; nesse caso o cache é descartado.
    chave = np.array([f"{len(quadros)}"] + [str(c) for c in validos])
    if cache.exists() and np.array_equal(np.load(cache)["chave"], chave):
        dados = np.load(cache)
        vet_teste, vet_dataset = dados["teste"], dados["dataset"]
    else:
        vet_teste, vet_dataset = embeddings([q for _, _, q in quadros]), embeddings(imagens)
        np.savez_compressed(cache, chave=chave, teste=vet_teste, dataset=vet_dataset)
    vet_teste, vet_dataset = centralizar(vet_teste, vet_dataset)
    semelhanca = vet_dataset @ vet_teste.T  # cosseno, porque os vetores são normalizados

    pares = []
    for i, caminho in enumerate(validos):
        j = int(np.argmax(semelhanca[i]))
        # Menor distância de hash contra QUALQUER quadro de teste (não só o mais parecido pelo embedding).
        hamming = min(distancia_hamming(hashes_dataset[i], h) for h in hashes_teste)
        pares.append({"imagem": str(caminho), "video": quadros[j][0], "segundo": quadros[j][1],
                      "hamming": hamming, "semelhanca": float(semelhanca[i, j]), "i": i, "j": j})
    # Do par mais parecido para o menos parecido.
    pares.sort(key=lambda p: (-p["semelhanca"]))

    # utf-8-sig (com BOM) e separador ';' para o Excel em português abrir o arquivo direto.
    with open(args.saida / "pares.csv", "w", newline="", encoding="utf-8-sig") as arq:
        escritor = csv.writer(arq, delimiter=";")
        escritor.writerow(["imagem", "video_teste", "segundo", "distancia_hash", "semelhanca"])
        for p in pares:
            escritor.writerow([p["imagem"], p["video"], f"{p['segundo']:.0f}", p["hamming"],
                               f"{p['semelhanca']:.4f}".replace(".", ",")])

    suspeitas = [p for p in pares if p["hamming"] <= args.max_hamming]
    (args.saida / "suspeitas.txt").write_text("".join(f"{p['imagem']}\n" for p in suspeitas), encoding="utf-8")

    # A folha mostra todas as suspeitas e completa com os pares mais parecidos até o total de --pares.
    destaque = suspeitas + [p for p in pares if p not in suspeitas][:max(0, args.pares - len(suspeitas))]
    for p in destaque:
        p["img_dataset"], p["img_teste"] = imagens[p["i"]], quadros[p["j"]][2]
    folha_de_pares(destaque, args.saida / "folha_pares.jpg")

    valores = np.array([p["semelhanca"] for p in pares])
    print(f"Semelhança máxima por imagem: mediana {np.median(valores):.3f}, p99 {np.percentile(valores, 99):.3f}, "
          f"máx {valores.max():.3f}")
    print(f"Imagens com hash quase igual a um quadro de teste (distância <= {args.max_hamming}): {len(suspeitas)}")
    print(f"Confira visualmente: {args.saida / 'folha_pares.jpg'}")


if __name__ == "__main__":
    main()
