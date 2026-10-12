# Resultados dos treinos

Cada subpasta é uma rodada de treino do notebook de treinamento (`notebooks/colab/` ou `notebooks/kaggle/`).
Os pesos (`.pt`) não ficam aqui: o modelo escolhido vai para `models/`, que está fora do git.

| Pasta | Data | Classes | Dados | Situação |
|---|---|---|---|---|
| `v1/` | 10–11/10/2026 | 5 (mascara, luvas, avental, macacao, calcado) | Welding-PPE (fork v1), divisão do Roboflow | **Descartado** como resultado final; serve de comparação "antes" |
| `v2/` | (a preencher) | 1 (`mascara`) | Welding-PPE + Welding Helmet, divisão estratificada no notebook | Rodada atual |

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
