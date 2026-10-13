# Resultados dos treinos

Cada subpasta é uma rodada de treino do notebook de treinamento (`notebooks/colab/` ou `notebooks/kaggle/`).
Os pesos (`.pt`) não ficam aqui: o modelo escolhido vai para `models/`, que está fora do git.

| Pasta | Data | Classes | Dados | Situação |
|---|---|---|---|---|
| `v1/` | 10–11/10/2026 | 5 (mascara, luvas, avental, macacao, calcado) | Welding-PPE (fork v1), divisão do Roboflow | **Descartado** como resultado final; serve de comparação "antes" |
| `v2/` | 11–12/10/2026 | 1 (`mascara`) | Welding-PPE + Welding Helmet, divisão estratificada no notebook | Modelo `yolo26n_640`. **Falso positivo** em rosto inclinado/de perfil no teste da webcam |
| `v3/` | (em andamento) | 1 (`mascara`) | v2 + pessoas do COCO como negativos (+ fotos próprias, opcional) | Corrige o falso positivo da v2; modelo `yolov8n_640` |

## v3 – 1ª execução (13/10/2026, sessão interativa do Kaggle: arquivos perdidos)

Os dois candidatos para CPU foram treinados com os negativos do COCO. A sessão interativa reiniciou e os arquivos se
perderam; ficaram só os números do resumo exibidos na tela:

| Experimento | mAP@0.5 (teste) | Taxa média de falso positivo (imagens de teste sem máscara) |
|---|---|---|
| yolo26n_640 | 0,900 | 27,9% |
| **yolov8n_640** | 0,837 | **7,9%** |

**Decisão:** a rodada v3 passa a usar o **yolov8n_640**. Ele detecta um pouco menos as máscaras (0,837, ainda acima
da meta boa de 0,75), mas aponta máscara em pessoa sem máscara ~3,5× menos, e esse era o problema a corrigir.
O treino foi refeito só com ele, no modo *Save & Run All (Commit)*.

## v2 – resultado (máscara de solda)

**Dados:** 1.448 imagens originais (treino 1.013 / validação 290 / teste 145); 1.072 caixas de máscara
(36 do Welding-PPE e 1.036 do Welding Helmet) e 434 imagens negativas. A caixa da máscara ocupa, em média, 28% da imagem.
Treino feito no Colab (YOLOv8n/s) e concluído no Kaggle (YOLOv8s_960 retomado + YOLO26n).

**Conjunto de teste (107 máscaras):**

| Experimento | Precisão | Recall | mAP@0.5 | mAP@0.5:0.95 | Épocas |
|---|---|---|---|---|---|
| yolov8n_640 | 0,955 | 0,841 | 0,910 | 0,643 | 100 |
| yolov8n_960 | 0,930 | 0,832 | 0,908 | 0,586 | 100 |
| yolov8s_640 | 0,953 | 0,832 | **0,936** | 0,670 | 100 |
| yolov8s_960 | 0,903 | 0,860 | 0,910 | 0,605 | 47 (parada antecipada) |
| **yolo26n_640** (escolhido) | **0,959** | **0,877** | 0,913 | **0,673** | 100 |
| yolo26n_960 | 0,926 | 0,825 | 0,913 | 0,595 | 59 (parada antecipada) |

**Meta da Fase 1 (mAP@0.5 ≥ 0,60; meta boa ≥ 0,75):** todos os experimentos atingem a **meta boa**.

**Por que o `yolo26n_640`:** é um dos dois modelos mais leves (próprios para CPU), com o maior recall e o maior
mAP@0.5:0.95 de todos. O `yolov8s_640` tem mAP@0.5 um pouco maior (0,936), mas custa ~3× mais processamento.
Velocidade medida em CPU (AMD Ryzen 5 5600, só o modelo de máscara, imagem 1280×720): **~37 FPS em 640** e **~22 FPS em 960**.
O FPS do sistema completo (máscara + pose) será medido na Etapa 1.3.

**Imgsz 960 não ajudou:** as máscaras são objetos grandes nestas imagens (28% da imagem), e 640 já basta. Em câmera
distante (máscara pequena) isso pode mudar; ver testes de campo.

**Teste na webcam (12/10/2026) – falso positivo encontrado:** com a cabeça inclinada para cima ou de perfil, o
**rosto descoberto** foi detectado como máscara (confiança 0,67 e 0,88).

Medida em vídeo (`testes_campo/teste_sem_mascara.mp4`: 96 s, 1.440 frames, uma pessoa **sem máscara** mexendo a
cabeça em todas as direções; gravado com `ferramentas/capturar.py` e avaliado com `python -m src.run --fonte ... --sem-janela`):

| Modelo | CONFORME (falso positivo) | NÃO CONFORME | INDETERMINADO |
|---|---|---|---|
| v2 (`yolo26n_640`) | **239 (17%)** | 1.163 (81%) | 38 (3%) |
| v3 | (a medir no mesmo vídeo) | | |

Este vídeo é o **conjunto de teste** do problema: não deve ser usado no treino.

**Limitações (para o relatório):**
- **O teste é quase todo do Welding Helmet** (104 de 107 máscaras), que é formado principalmente por fotos de produto.
  O Welding-PPE (cenas reais) tem só **3 máscaras no teste**, e o "0,995" dessa fonte não tem valor estatístico.
- Portanto, **mAP 0,91 é o desempenho em fotos parecidas com as do treino**, não no posto de solda. A validação de
  verdade são os testes de campo (Etapa 1.5), de preferência com um conjunto próprio de fotos/vídeos (máscara abaixada,
  levantada e sem máscara).
- Recall de 0,88: cerca de 1 em cada 8 máscaras do teste não foi detectada. No sistema, isso é amortecido pela
  persistência (N frames seguidos antes de gerar ocorrência) e pela regra "rosto não visível → INDETERMINADO".

## v1 – por que foi descartado

- A divisão do Roboflow deixou **2 máscaras e 2 macacões no teste** (e 1 macacão no treino). Um mAP com 2 exemplos não tem valor estatístico.
- O dataset tinha só **43 caixas de máscara**, o EPI mais importante.
- Luvas (mAP@0.5 = 0,975) e calçado (0,995) parecem ótimos, mas o teste é formado principalmente por **fotos de produto** (objeto ocupando ~25–29% da imagem). Isso não representa a câmera no posto de solda.

Resultado do modelo escolhido na v1 (`yolov8n_960`, conjunto de teste):

| Classe | Instâncias | mAP@0.5 |
|---|---|---|
| mascara | 2 | 0,495 |
| luvas | 46 | 0,975 |
| avental | 13 | 0,941 |
| macacao | 2 | 0,495 |
| calcado | 63 | 0,995 |

**Decisão (11/10/2026, com o orientador):** a Fase 1 passa a focar só na **máscara de solda**. Ver `docs/plano_fase1.md`, seção 0.
