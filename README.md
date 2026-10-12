# Verificador de EPIs de Solda com Visão Computacional

Projeto extensionista de Ciência da Computação da **FSG** (Caxias do Sul – RS), em parceria com a **Marcopolo**.
Uma câmera instalada no posto de solda verifica se o soldador está usando a **máscara de solda** e sinaliza
as não conformidades (NR-6).

> **Fase 1 – validação da detecção.** Execução por linha de comando, com janela do OpenCV.
> Foco atual: **máscara de solda** (decisão de 11/10/2026, com o orientador). Ver `docs/plano_fase1.md`.

## Como funciona (resumo)

```
frame ─► filtro do arco (frame estourado é ignorado)
      ─► YOLOv8n-pose + ByteTrack (pessoas, pontos do corpo, ID de cada pessoa)
      ─► detector de máscara de solda (YOLO treinado no projeto)
      ─► regras: a máscara está na região da cabeça?  ─► caixa VERDE / AMARELA / VERMELHA
```

| Estado | Quando | Cor |
|---|---|---|
| CONFORME | máscara detectada na região da cabeça | verde |
| NÃO CONFORME | rosto visível (olhos/nariz) e nenhuma máscara | vermelho |
| INDETERMINADO | cabeça não visível, pessoa de costas, rosto coberto sem máscara detectada | amarelo |

"MASCARA LEVANTADA" é indicada quando a máscara está acima da linha dos olhos com o rosto visível.

## Instalação (Windows, Python 3.12)

```powershell
cd Z:\Documentos\SafeWork
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Modelos (pasta `models/`, fora do git):
- `epi_solda_best.pt`: gerado pelo notebook de treinamento (`notebooks/colab` ou `notebooks/kaggle`);
- modelos de pose: `python -m src.run --baixar-modelos`. Em rede com proxy, rode em outra rede e copie a pasta `models/`.

## Uso

```powershell
python -m src.run                                         # webcam 0
python -m src.run --fonte 1                               # outra webcam
python -m src.run --fonte testes_campo\video1.mp4 --posto mig_01
python -m src.run --fonte testes_campo\foto1.jpg --salvar-saida
python -m src.run --fonte "rtsp://usuario:senha@192.168.0.10/stream"
python -m src.run --fonte testes_campo\video1.mp4 --debug  # mostra região da cabeça, linha dos olhos e pontos
python -m src.run --benchmark                              # FPS com imgsz 640 e 960
```

Teclas na janela: **q** ou **ESC** sai, **p** pausa.
`--salvar-saida` grava o resultado anotado em `testes_campo/` (fora do git). **Gravações de pessoas reais exigem
autorização prévia da empresa e dos trabalhadores filmados.**

Configuração: `config.yaml` (EPIs, limiares, postos de solda, filtro do arco, modelos).

## Testes

```powershell
python -m pytest
```

Os testes usam pessoas e máscaras **simuladas** (sem câmera). O teste de integração usa os modelos reais e é pulado
se eles não estiverem em `models/`.

## Treinamento

Notebooks em `notebooks/colab/` (Google Colab) e `notebooks/kaggle/` (Kaggle). Passo a passo e decisões sobre os
dados: `docs/dataset_welding_ppe.md`. Resultados: `docs/resultados_treino/`.

## Atribuição dos datasets (CC BY 4.0)

- "Welding-PPE" – Welding PPE, Roboflow Universe, 2023. https://universe.roboflow.com/welding-ppe/welding-ppe
- "Welding Helmet" – UTP, Roboflow Universe, 2025. https://universe.roboflow.com/utp-jtbn5/welding-helmet

As classes foram remapeadas para `mascara` e novas versões foram geradas sem "Isolate Objects", sem "Stretch" e sem
as augmentations originais. Citações BibTeX em `docs/dataset_welding_ppe.md`, seção 7.

Exemplos negativos (pessoas sem máscara, rodada v3): **COCO 2017** – Lin et al., "Microsoft COCO: Common Objects in
Context", ECCV 2014 (https://cocodataset.org); anotações CC BY 4.0, imagens com as licenças do Flickr indicadas no COCO.

## Ferramentas

`ferramentas/capturar.py` grava um vídeo de teste ou salva fotos da webcam a cada 0,5 s (exemplos negativos para o
treino). Ex.: `python ferramentas/capturar.py --saida testes_campo/teste_sem_mascara.mp4 --duracao-s 60`.

## Licenças de software

O Ultralytics YOLO é distribuído sob **AGPL-3.0**: adequado a este projeto acadêmico; um uso interno contínuo pela
empresa deve considerar essa licença.
