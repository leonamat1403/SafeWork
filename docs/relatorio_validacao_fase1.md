# Relatório de validação da Fase 1 (Etapa 1.6)

**Projeto:** Verificador de EPIs de Solda com Visão Computacional (FSG + Marcopolo)
**Data:** 13/10/2026
**Escopo avaliado:** **máscara de solda** (= capacete de solda), por decisão do orientador em 11/10/2026
(`docs/plano_fase1.md`, seção 0)

Todos os números deste relatório vêm de execuções reais. A origem de cada um está indicada (arquivo ou comando),
para conferência.

## 1. Resumo

| Meta (prompt do projeto, "METAS DE VALIDAÇÃO") | Mínimo | Resultado | Situação |
|---|---|---|---|
| mAP@0.5 da máscara no conjunto de teste | 0,60 (meta boa 0,75) | **0,945** | ✅ meta boa |
| Recall da ausência de EPI nos testes de campo | ≥ 70% | **82%** (9 de 11) | ✅ |
| Falsos positivos (revisão manual das ocorrências) | ≤ 30% | **0%** (0 de 16) | ✅ |
| FPS em CPU com imgsz 640 | ≥ 5 | **12,5** | ✅ |

**Conclusão:** para o EPI em escopo (máscara de solda), os **mínimos da Fase 1 foram atingidos**, e o mAP atinge a
meta boa. Há limitações importantes (seção 6), principalmente: o verde ("conforme") aparece em só 19% do tempo para
quem está de máscara, e a amostra de testes de campo é pequena (11 situações de falta). Elas não impedem a
validação, porque os erros que restam são do tipo **"não confirmar"** (amarelo), e não do tipo "acusar errado".

**Recomendação:** considerar a detecção validada para a máscara de solda e seguir para a Fase 2. Em paralelo, fazer o
piloto no posto real da Marcopolo (seção 7). A decisão é sua: para iniciar a Fase 2, escreva
**"DETECÇÃO VALIDADA - INICIAR FASE 2"**.

## 2. O que foi avaliado

| Componente | Versão final | Onde |
|---|---|---|
| Detector de máscara | **v5**, YOLOv8n, imgsz 640, 1 classe (`mascara`) | `models/epi_solda_best.pt` (v3 e v4 guardados como `_v3`/`_v4`) |
| Pessoas e pontos do corpo | YOLOv8n-pose + ByteTrack | `models/yolov8n-pose.pt` |
| "Rosto visível" | detector de rostos YuNet (OpenCV Zoo, MIT) no recorte da cabeça (D27) | `models/face_detection_yunet_2023mar.onnx` |
| Regras | `src/compliance.py`, `src/body_regions.py` | estados CONFORME / NÃO CONFORME / INDETERMINADO |
| Ocorrências | ≥ 75% dos frames em falta nos últimos **4 s**; cooldown de **60 s**; máscara **levantada = falta** (D25); **óculos de maçarico = falta** (D28) | `config.yaml`, `src/occurrences.py` |
| Filtro do arco | frame ignorado se > 15% dos pixels ≥ 245 | `src/arc_filter.py` |

**Fora do escopo desta validação:** proteção do corpo (avental/macacão), luvas e calçado. O código e o notebook já
preveem essas classes (`CLASSES_MODELO`), mas elas não foram treinadas nem testadas. Ficam como trabalho futuro.

## 3. Métricas do modelo (conjunto de teste do notebook)

| Rodada | Dados | mAP@0.5 | Precisão | Recall | Falso positivo em pessoas (COCO) |
|---|---|---|---|---|---|
| v2 | Welding-PPE + Welding Helmet | 0,913 (`yolo26n_640`) | 0,959 | 0,877 | – |
| v3 | v2 + 1.500 pessoas do COCO (negativos) | 0,855 | 0,872 | 0,736 | 2,1% |
| v4 | v3 + *welder* + *safeweld* (soldadores reais) | 0,946 | 0,931 | 0,928 | 0,6% |
| **v5 (final)** | v4 + 362 quadros sem máscara (negativos difíceis) | **0,945** | **0,948** | **0,931** | **0%** |

Fonte: `docs/resultados_treino/` (uma pasta por rodada) e `docs/resultados_treino/README.md`.

- O teste da v4 e da v5 é **o mesmo** (455 imagens, 218 máscaras: 102 do Welding Helmet, 39 do *welder*, 77 do
  *safeweld*), então essas duas linhas são diretamente comparáveis. Os testes da v2 e da v3 são outros, menores e com
  mais fotos de produto.
- mAP por fonte na v5: Welding Helmet 0,943, *welder* 0,940, *safeweld* 0,967 (todas acima da meta boa).
- **Cuidado:** um mAP alto mostra que o modelo acerta em imagens **parecidas com as do treino**. O desempenho no posto
  de solda é medido nos testes de campo (seção 4).

## 4. Testes de campo

**Base:** 28 trechos de 21 vídeos de banco de imagens (Pexels) e 1 vídeo da webcam, conferidos quadro a quadro e
classificados (`docs/resultados_testes_campo.md`, seção 1). Avaliação automática com `ferramentas/avaliar_testes.py`;
ocorrências dos testes com várias pessoas ("mistos") revisadas manualmente. Planilha: `testes_campo/planilha_testes_campo.xlsx`
(fora do git, porque mostra pessoas).

### 4.1 Métricas práticas (modelo v5)

| Métrica | Meta | Resultado | Intervalo de confiança de 95% (Wilson) |
|---|---|---|---|
| Recall da ausência (testes em que deveria haver ocorrência) | ≥ 70% | **82%** (9/11) | 52% a 95% |
| Recall contando os testes mistos (por pessoa) | – | 81% (13/16) | – |
| Falsos positivos (ocorrências erradas ÷ ocorrências) | ≤ 30% | **0%** (0/16) | 0% a 19% |
| Testes "sem ocorrência" com alarme falso | – | **0 de 12** | – |

O intervalo do recall é largo porque só há 11 situações de falta. O resultado atinge a meta, mas **não prova** que o
recall real fica acima de 70%. Mais testes (de preferência no posto real) reduzem essa incerteza. Já o limite
superior dos falsos positivos (19%) fica abaixo da meta de 30%.

**Recall por condição** (`docs/resultados_testes_campo.md`, seção 3; os acertos e as falhas são os mesmos na v3, v4 e v5):

| Condição | Testes | Recall |
|---|---|---|
| Até 2 m / 2 a 4 m | 15 / 11 | 80% / 83% |
| Acima de 4 m | 2 | sem teste de falta (limitação) |
| De frente / de perfil | 13 / 7 | 83% / **50%** |
| Arco apagado / aceso | 17 / 11 | 80% / 100% |

**As 3 falhas de recall** (o sistema ficou amarelo, sem acusar): T10, sem máscara de cabeça baixa no escuro; T19,
máscara levantada vista de perfil; T04, ajudantes com respirador cobrindo nariz e boca.

### 4.2 Evolução do modelo nos testes de campo

| Métrica (28 trechos) | v3 | v4 | **v5** |
|---|---|---|---|
| Recall / alarmes falsos | 9/11 / 0 de 12 | 9/11 / 0 de 12 | 9/11 / 0 de 12 |
| Verde na máscara abaixada (média) | 14% | 26% | 19% |
| **Verde falso** em quem está sem máscara (média) | 0,9% | 7,3% | **1,3%** |

A v4 (soldadores reais) passou a confirmar mais vezes a máscara, inclusive de costas, mas criou "verde falso" (cabeça
baixa no escuro, gorro com óculos de maçarico). A v5 (exemplos negativos difíceis) eliminou o pior caso (T10: 45% → 0%)
e manteve parte do ganho. **Escolha da v5:** num sistema de segurança, "conforme" para quem está sem proteção é o erro
mais grave (detalhes em `docs/resultados_testes_campo.md`, seções 6 e 7).

### 4.3 Desempenho em CPU (RNF01)

`python -m src.run --benchmark` (AMD Ryzen 5 5600, 60 frames de 810×1080 com 4 pessoas, modelo v5):

| imgsz máscara | imgsz pose | ms/frame | FPS |
|---|---|---|---|
| **640** | 640 | 80 | **12,5** |
| 960 | 640 | 109 | 9,2 |
| 960 | 960 | 140 | 7,1 |

Média nos testes de campo (vídeos de até 4K, decodificação incluída): 12,9 FPS.

## 5. Critérios de aceite da Fase 1

| Critério (prompt do projeto) | Situação | Evidência |
|---|---|---|
| mAP@0.5 máscara ≥ 0,60 | ✅ | 0,945 (seção 3) |
| mAP proteção do corpo ≥ 0,60, luvas ≥ 0,50, calçado ≥ 0,40 | fora do escopo | foco só na máscara (decisão de 11/10/2026) |
| Testes de campo: recall ≥ 70% e falsos positivos ≤ 30% | ✅ | 82% e 0% (seção 4.1), com a ressalva da amostra pequena |
| Soldador a ~3 m, de frente, sem máscara → vermelho com o rótulo certo em ~1 s | ✅ | T24 (3 m, frente): vermelho em 100% dos frames, rótulo "SEM MASCARA"; T21 (2 m): 79%. O estado muda já no 1º frame; a ocorrência vem após 4 s (D24) |
| Com a máscara abaixada → verde, mesmo sem olhos visíveis | ⚠️ parcial | verde em 19% do tempo, em média (T05 de costas: 83%; T07: 50%; T27: 39%). No resto fica **amarelo**, nunca vermelho (0 alarmes falsos) |
| Máscara levantada sinalizada no frame | ⚠️ parcial | T23 e T28: vermelho e ocorrência, mas com o rótulo "SEM MÁSCARA", porque o detector reconhece mal a máscara sobre a cabeça. T19 (perfil) e T08 (costas): amarelo. Obs.: o prompt previa levantada = CONFORME; a decisão D25 a tornou falta |
| Luvas: ausência a ~2 m; mãos ocultas → INDETERMINADO | fora do escopo | – |
| Proteção do corpo: avental ou macacão aceitos conforme a configuração | fora do escopo | – |
| Frames saturados pelo arco ignorados, sem ocorrência | ✅ código / ⚠️ campo | `tests/test_arc_filter.py` e `test_frames_saturados_pelo_arco_nao_contam`; nos vídeos de campo nenhum frame passou de 15% de pixels estourados, então o filtro não foi exercitado |
| Sem máscara e sem luvas → 1 ocorrência com os 2 EPIs | ✅ lógica | `test_varios_epis_faltando_geram_uma_unica_ocorrencia`; em campo só a máscara está ativa |
| Mesma pessoa parada → 1 ocorrência por janela de cooldown | ✅ | testes de cooldown em `tests/test_occurrences.py`; T17 (60 s sem máscara): 1 ocorrência. Ressalva: troca de ID no rastreamento pode duplicar (T09) |
| FPS ≥ 5 com imgsz 640, e FPS com 960 documentado | ✅ | 12,5 / 9,2 / 7,1 FPS (seção 4.3) |
| Testes pytest [FASE 1] passam | ✅ | `python -m pytest`: **100 testes passando** |
| Classe "helmet" verificada e mapeada | ✅ | `docs/dataset_welding_ppe.md`, seção 3: máscara de solda → `mascara` |

## 6. Limitações (para o relatório acadêmico)

1. **Só a máscara de solda foi validada.** Proteção do corpo, luvas e calçado ficam para trabalho futuro.
2. **A máscara correta raramente fica verde** (19% do tempo). De perfil, com o arco aceso (T03, T20, T26) e em
   algumas cenas de costas (T02), o sistema fica amarelo. Não gera alarme falso, mas também não confirma a
   conformidade.
3. **Máscara levantada** sai como "sem máscara" (mesma consequência: falta) e não é reconhecida de perfil (T19).
4. **Rosto pouco visível → INDETERMINADO:** cabeça baixa no escuro (T10), perfil acentuado (recall de perfil 50%),
   costas e respirador (T04). É uma escolha de projeto (não acusar sem evidência), que reduz o recall.
5. **Verde falso residual:** gorro escuro com óculos de maçarico ainda aparece como "conforme" em 10% do tempo (T22).
   A ocorrência é gerada mesmo assim.
6. **Amostra pequena** nos testes de campo (11 situações de falta; intervalo de confiança do recall de 52% a 95%) e
   **sem testes de falta a mais de 4 m**.
7. **Os vídeos de teste são de banco de imagens**, não do posto real. Câmera, iluminação, fumos e distância na
   Marcopolo ainda não foram testados. O **filtro do arco** não foi exercitado em campo.
8. **Troca de ID** do rastreamento com os clarões do arco pode duplicar uma ocorrência (T09).
9. **Dados de treino:** muitas fotos de produto (Welding Helmet) e fotos da web (algumas com marca d'água); conferência
   por amostragem, não imagem a imagem. Os datasets usados têm licença CC BY 4.0 (seção 9).
10. **Fontes dos vídeos de teste:** os links do Pexels foram deduzidos do nome dos arquivos e estão marcados
    "confirmar" na aba Fontes da planilha.

## 7. Recomendações

1. **Validar a Fase 1 para a máscara de solda** e iniciar a Fase 2, mantendo os testes [FASE 1] como proteção contra
   regressões.
2. **Piloto no posto real da Marcopolo** (com autorização da empresa e dos trabalhadores): câmera fixa na posição
   definitiva, arco aceso, fumos, distâncias de 2, 4 e 6 m. Isso mede o recall real, exercita o filtro do arco e
   gera material para o RF33.
3. **Fine-tuning com imagens do posto (RF33):** máscaras abaixadas e levantadas (inclusive de perfil e de costas) e
   pessoas sem máscara no mesmo ambiente (boné, gorro, óculos). É o caminho para melhorar ao mesmo tempo o verde
   verdadeiro (limitação 2) e o verde falso (limitação 5). Ninguém deve soldar sem máscara para a gravação.
4. **Ajustes finos a testar:** `conf_rosto` 0,7 (falso "rosto" na nuca, T12) e parâmetros do rastreamento (troca de
   ID com o arco).
5. **Outros EPIs:** reativar as classes no notebook (`CLASSES_MODELO`), com dados próprios para luvas e avental.
6. Confirmar os links e as licenças dos vídeos de teste na aba Fontes antes de publicar o trabalho.

## 8. Como reproduzir

```bash
python -m pytest                                    # 100 testes
python -m src.run --benchmark                       # tabela da seção 4.3
python ferramentas/avaliar_testes.py --todos        # testes de campo (planilha em testes_campo/)
python ferramentas/conferir_vazamento.py --datasets dados/roboflow_v4/welder dados/roboflow_v4/safeweld
```

Treino: `notebooks/kaggle/treinamento_epi_solda_kaggle.ipynb` (passo a passo em `notebooks/kaggle/LEIA-ME.md`).
Decisões técnicas: `docs/plano_fase1.md` (D1 a D30). Dados de treino: `docs/dataset_welding_ppe.md`.

## 9. Atribuição

- **Welding-PPE** (Welding PPE, Roboflow Universe, 2023), **Welding Helmet** (UTP, 2025), **welder** (ESports, 2025) e
  **safeweld** (Josephs Workspace, 2026), todos sob licença CC BY 4.0. Citações BibTeX em `docs/dataset_welding_ppe.md`, seção 7.
- **COCO 2017**: Lin et al., "Microsoft COCO: Common Objects in Context", ECCV 2014 (anotações CC BY 4.0).
- **YuNet** (OpenCV Zoo, licença MIT) para a detecção de rostos.
- Vídeos de teste e de exemplos negativos: **Pexels** (licença Pexels, uso livre); lista em
  `docs/dataset_welding_ppe.md`, 2.9, e na aba Fontes da planilha de testes.
