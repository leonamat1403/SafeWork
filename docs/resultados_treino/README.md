# Resultados dos treinos

Cada subpasta é uma rodada de treino do notebook de treinamento (`notebooks/colab/` ou `notebooks/kaggle/`).
Os pesos (`.pt`) não ficam aqui: o modelo escolhido vai para `models/`, que está fora do git.

| Pasta | Data | Classes | Dados | Situação |
|---|---|---|---|---|
| `v1/` | 10–11/10/2026 | 5 (mascara, luvas, avental, macacao, calcado) | Welding-PPE (fork v1), divisão do Roboflow | **Descartado** como resultado final; serve de comparação "antes" |
| `v2/` | 11–12/10/2026 | 1 (`mascara`) | Welding-PPE + Welding Helmet, divisão estratificada no notebook | Modelo `yolo26n_640`. **Falso positivo** em rosto inclinado/de perfil no teste da webcam |
| `v3/` | 13/10/2026 | 1 (`mascara`) | v2 + 1.500 pessoas do COCO como negativos | modelo `yolov8n_640` (mAP@0.5 0,855; falso positivo em pessoas 2,1%). Guardado em `models/epi_solda_best_v3.pt` |
| `v4/` | 13/10/2026 | 1 (`mascara`) | v3 + *welder* + *safeweld* (soldadores reais, conferidos) | modelo `yolov8n_640` (mAP@0.5 0,946; falso positivo em pessoas 0,6%). Guardado em `models/epi_solda_best_v4.pt` |
| `v5/` | 13/10/2026 | 1 (`mascara`) | v4 + 362 quadros de vídeos do Pexels **sem** máscara (negativos difíceis) + cópias escuras, só no treino | **Atual**: modelo `yolov8n_640` (mAP@0.5 0,945; falso positivo em pessoas 0%) |

## v5 – resultado (13/10/2026, `yolov8n_640`, Kaggle em modo Commit, 2 h 8 min)

**Dados:** os mesmos da v4 mais 362 quadros sem máscara (e 724 cópias escuras), **só no treino**: treino 4.678 /
validação 909 / teste 455 imagens originais. A validação e o teste são **idênticos aos da v4**, então a comparação
abaixo é direta. 87 épocas (parada antecipada).

| Medida (mesmo conjunto de teste) | v4 | v5 |
|---|---|---|
| Precisão | 0,931 | **0,948** |
| Recall | 0,928 | 0,931 |
| mAP@0.5 | 0,946 | 0,945 |
| mAP@0.5:0.95 | 0,669 | 0,666 |
| Falso positivo em pessoas do COCO (155 imagens) | 0,6% | **0%** |

Por fonte (mAP@0.5): Welding Helmet 0,943, welder 0,940, safeweld 0,967. Os negativos novos não tiraram nada da
detecção da máscara e deixaram o modelo um pouco mais preciso. O efeito nos casos que motivaram a v5 (verde falso
em T10 e T22) é medido nos testes de campo.

## v4 – resultado (13/10/2026, `yolov8n_640`, Kaggle em modo Commit, ~2 h)

**Dados:** 5.680 imagens originais (treino 4.316 / validação 909 / teste 455): 3.096 caixas de máscara (36 do
Welding-PPE, 1.036 do Welding Helmet, **1.239 do welder e 785 do safeweld**) e 2.754 imagens negativas (1.500 do
COCO). A máscara média ocupa 16% da imagem (28% na v3): mais cenas reais, com a máscara menor. 97 épocas.

**Conjunto de teste:**

| Medida | v3 | v4 |
|---|---|---|
| Precisão | 0,872 | 0,931 |
| Recall | 0,736 | **0,928** |
| mAP@0.5 | 0,855 | **0,946** (meta boa ≥ 0,75 ✅) |
| mAP@0.5:0.95 | 0,587 | 0,669 |
| Falso positivo em pessoas do COCO | 2,1% (3 de 143) | **0,6%** (1 de 155) |

**Por fonte (v4):** mAP@0.5 de 0,933 no Welding Helmet, **0,970 no welder** e **0,959 no safeweld**. Falsos
positivos nos negativos: 0 de 41 no Welding-PPE, 2 de 44 no welder e 3 de 8 no Welding Helmet (amostra pequena).

**Cuidado na comparação:** os conjuntos de teste da v3 e da v4 são diferentes (o da v4 tem cenas reais e o dobro de
máscaras). A comparação justa entre os dois modelos são os testes de campo (`docs/resultados_testes_campo.md`).

## v3 – resultado (13/10/2026, `yolov8n_640`, Kaggle em modo Commit)

**Dados:** 2.948 imagens originais (treino 2.063 / validação 590 / teste 295): 1.072 caixas de máscara e 1.934 imagens
negativas (381 do Welding-PPE, 53 do Welding Helmet e **1.500 de pessoas do COCO**). 82 épocas (parada antecipada).

**Conjunto de teste:**

| Medida | v2 (`yolo26n_640`) | v3 (`yolov8n_640`) |
|---|---|---|
| Precisão | 0,959 | 0,872 |
| Recall | 0,877 | 0,736 |
| mAP@0.5 | 0,913 | **0,855** (meta boa ≥ 0,75 ✅) |
| mAP@0.5:0.95 | 0,673 | 0,587 |
| Falso positivo em pessoas do COCO (143 imagens) | – | **2,1%** (3 imagens) |
| Falso positivo nos negativos do Welding-PPE (46 imagens) | – | 4,3% |

O teste da v3 é mais difícil que o da v2: agora inclui 194 imagens sem máscara, quase todas de pessoas, onde a v2
erraria bastante. O recall menor (0,736) significa que o modelo ficou mais "cauteloso"; no sistema, máscara não
detectada com o rosto coberto vira INDETERMINADO, não "SEM MÁSCARA".

**Vídeo sem máscara (teste da webcam):** o falso "OK" caiu de 17% (v2) para 8% (v3), e para **2%** com a regra de
contradição (D23), sem perder nenhuma detecção correta de "SEM MÁSCARA" (89%). Os 8% restantes da v3 estavam
concentrados em dois trechos (40 e 20 frames) com a **cabeça de perfil e luz lateral forte**. Neles, a pose
enxergava olhos e nariz nitidamente, o que é impossível com uma máscara abaixada.

**A validar com uma máscara real:** se o modelo de pose "enxergar" olhos através de uma máscara verdadeira com
confiança ≥ 0,7, a regra de contradição marca INDETERMINADO (amarelo) em vez de OK. Isso não gera alarme falso, mas
precisa ser medido com vídeos de soldadores (bancos de vídeo gratuitos, laboratório, Marcopolo).

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
| v3 (`yolov8n_640`) | 110 (8%) | 1.285 (89%) | 45 (3%) |
| v3 + regra de contradição (D23) | **30 (2%)** | 1.285 (89%) | 125 (9%) |

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
