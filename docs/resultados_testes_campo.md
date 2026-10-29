# Resultados dos testes de campo (13/10/2026)

> **Atualização:** as seções 1 a 5 avaliam o modelo **v3**. A comparação com o modelo **v4** (treinado com fotos de
> soldadores reais), nos mesmos 28 trechos, está na **seção 6**.

**Etapa 1.5.** Vídeos de banco de imagens (provável Pexels, a confirmar) e da webcam, avaliados com
`ferramentas/avaliar_testes.py`. A planilha completa fica em `testes_campo/planilha_testes_campo.xlsx` (fora do git,
porque contém vídeos de pessoas). Sistema avaliado:
- modelo de máscara **v3 (`yolov8n_640`)**;
- pose `yolov8n-pose`;
- **detector de rostos YuNet** (D27);
- regras do `config.yaml`: 4 s com pelo menos 75% dos frames em falta, cooldown de 60 s, máscara levantada como falta.

## 1. Base de testes: 21 vídeos, 28 trechos

Cada vídeo foi conferido quadro a quadro. Vários tinham mais de uma situação e foram divididos em trechos
(`inicio_s`/`fim_s`), e alguns foram reclassificados em relação à pasta em que foram entregues.

| Teste | Situação real | Ângulo | Dist. | Arco | Observação |
|---|---|---|---|---|---|
| T01 | sem máscara | varia | 1 m | apagado | webcam, cabeça em todas as direções |
| T02 | máscara (não visível) | costas | 2 m | apagado | esmerilhamento |
| T03 | máscara abaixada | perfil | 5 m | aceso | fumaça |
| T04 | **misto** | frente | 3 m | aceso | ajudantes de **respirador**, sem máscara de solda |
| T05 | máscara abaixada | costas | 2 m | aceso | levanta a máscara nos últimos ~2 s |
| T06 | máscara abaixada | frente | 1 m | aceso | outra pessoa passa ao fundo por ~2 s |
| T07 | máscara abaixada | frente | 2 m | apagado | esmerilhamento |
| T08 | máscara levantada | costas | 1,5 m | apagado | levantada vista de trás |
| T09 | sem máscara | frente | 2 m | aceso | soldando sem máscara |
| T10 | sem máscara | frente | 3 m | apagado | **cabeça baixa, ambiente escuro** |
| T11 | sem máscara | costas | 1,5 m | apagado | rosto escondido |
| T12 | **misto** | varia | 6 m | apagado | oficina com muitas pessoas |
| T13 | **misto** | perfil | 4 m | aceso | ajudante sem proteção nos olhos |
| T14 | **misto** | perfil | 3 m | aceso | observador com escudo de mão afastado do rosto |
| T15 | máscara abaixada | frente | 1,5 m | aceso | dois protegidos |
| T16 | **misto** | perfil | 2 m | apagado | aluno sem máscara parado perto |
| T17 | sem máscara | frente | 3 m | apagado | **óculos de maçarico** (D28) |
| T18 | sem máscara | varia | 3 m | apagado | 2 pessoas esmerilhando sem proteção |
| T19 | máscara levantada | **perfil** | 1,5 m | apagado | |
| T20 | máscara abaixada | frente | 3 m | aceso | |
| T21 | sem máscara | frente | 2 m | apagado | |
| T22 | sem máscara | varia | 4 m | apagado | **óculos de maçarico**; perto e longe |
| T23 | máscara levantada | perfil | 2 m | apagado | |
| T24 | sem máscara | frente | 3 m | apagado | |
| T25 | pausa curta (~3 s levantada) | frente | 3 m | apagado | não deve gerar ocorrência |
| T26 | máscara abaixada | perfil | 1,5 m | aceso | |
| T27 | máscara abaixada | frente | 2 m | aceso | |
| T28 | máscara levantada | frente | 3 m | apagado | |

## 2. Problema encontrado e corrigido: a pose "enxerga" um rosto atrás da máscara

Na primeira avaliação, os soldadores **com máscara** geraram ocorrências falsas. O diagnóstico frame a frame mostrou
duas causas:

1. **O modelo de pose "imagina" olhos e nariz através da máscara de solda**, com confiança ≥ 0,5 em 84% a 100% dos
   frames. As regras que dependiam de "rosto visível" concluíam "SEM MÁSCARA" ou "MÁSCARA LEVANTADA" para quem estava
   protegido.
2. **O detector de máscara reconhece mal máscaras reais em uso** (0% dos frames em T03, T06 e T15), porque aprendeu
   principalmente com fotos de produto.

**Correção (D27):** "rosto visível" passou a vir de um **detector de rostos** (YuNet, OpenCV Zoo, licença MIT),
executado no recorte da cabeça de cada pessoa. Um rosto coberto pela máscara não é detectado como rosto:

| Vídeo | Rosto "visto" pela pose | Rosto visto pelo YuNet |
|---|---|---|
| Soldadores com máscara (T03, T06, T07, T15) | 26% a 100% | **0% a 1%** |
| Sem máscara (T01 webcam, T09 soldando) | 96% a 98% | **86% a 98%** |

Efeito na 1ª rodada (16 trechos): os falsos positivos caíram de **60% para 0%**, e os testes com máscara que
geraram alarme falso caíram de **5 de 8 para 0 de 8**.

## 3. Métricas consolidadas (28 trechos; os "mistos" ficam fora do cálculo automático)

| Métrica | Meta | Resultado |
|---|---|---|
| **Recall da ausência** (testes "ocorrência" em que houve ocorrência) | ≥ 70% | **82%** (9/11) ✅ |
| **Falsos positivos** (ocorrências erradas ÷ ocorrências) | ≤ 30% | **0%** (0 de 16 ocorrências) ✅ |
| Testes "sem ocorrência" com alarme falso | – | **0 de 12** |
| **FPS** em CPU, imgsz 640 (benchmark oficial, computador livre) | ≥ 5 | **13,7** ✅ |
| FPS com imgsz 960 (máscara 960 / pose 640; tudo em 960) | documentar | 9,8 / 7,0 |
| FPS ao vivo na webcam (média) | – | 14,3 |
| % do tempo com a máscara **confirmada** (testes com máscara abaixada) | – | 14% |

Benchmark: `python -m src.run --benchmark` em um AMD Ryzen 5 5600, imagem de 810×1080 com 4 pessoas. O FPS mais baixo
da tabela de testes (7,7) foi medido com um jogo aberto no computador.

**Recortes (recall):**

| Condição | Testes | Recall | Alarmes falsos |
|---|---|---|---|
| distância até 2 m | 15 | 80% | 0 |
| distância de 2 a 4 m | 11 | 83% | 0 |
| distância acima de 4 m | 2 | sem teste "ocorrência" | 0 |
| de frente | 13 | 83% | 0 |
| de perfil | 7 | **50%** | 0 |
| arco apagado / aceso | 17 / 11 | 80% / 100% | 0 / 0 |

**Testes mistos** (revisão manual, ocorrência por pessoa): T12 (3 VP), T13 (1 VP), T14 (1 VP) e T16 (1 VP) acusaram
corretamente a pessoa sem máscara, e no T16 o soldador mascarado ficou **verde**. O T04 não acusou os ajudantes de
respirador. Contando os mistos: **recall 81% (13/16 situações)** e **0 falsos positivos**.

**Falhas de recall (3):**
- **T10:** cabeça baixa e ambiente escuro, o rosto não aparece;
- **T19:** máscara levantada vista de perfil, o rosto de lado não foi detectado;
- **T04:** respirador cobrindo nariz e boca.

Nos três casos o sistema ficou **amarelo (INDETERMINADO)**: deixou de acusar, mas não acusou errado.

## 4. Limitações observadas

1. **Rosto pouco visível** (perfil acentuado, cabeça baixa, escuro, costas, respirador): o sistema fica
   INDETERMINADO e não acusa. É uma escolha de projeto (não acusar sem evidência), mas reduz o recall de perfil (50%).
2. **A máscara correta raramente fica verde** (14% do tempo): o detector de máscara ainda reconhece mal máscaras reais
   em uso e máscaras levantadas. O sistema não gera alarme falso por isso (fica amarelo), mas também não "confirma" a
   conformidade.
3. **A máscara levantada é acusada como "sem máscara"**: nos testes T23 e T28 a ocorrência saiu corretamente, mas com o
   motivo "rosto visível sem máscara", porque a máscara sobre a cabeça não foi detectada. Para a conformidade, o
   resultado é o mesmo (as duas situações são falta, D25).
4. **Falso "rosto" na nuca** (T12, pessoa #69, conf. 0,56): pode ser ajustado subindo `conf_rosto`, o que precisa ser
   testado.
5. **Troca de ID** do rastreamento com os clarões do arco pode duplicar uma ocorrência (T09).
6. **O filtro do arco não foi acionado** em nenhum vídeo: nenhum frame passou de 15% de pixels estourados. O teste
   com câmera real no posto ainda é necessário.
7. **Sem testes de "sem máscara" a mais de 4 m.**

## 5. Recomendações

1. **Fine-tuning do detector de máscara com imagens reais de soldadores** (RF33), de vídeos **diferentes** dos usados
   em teste. Isso ataca as limitações 2 e 3, que são as que impedem o verde e o rótulo "MASCARA LEVANTADA" de aparecer.
2. Gravar ou obter vídeos **sem máscara a 4–6 m** e **de perfil**.
3. Testar `conf_rosto` 0,7 (limitação 4).
4. Teste no posto real, com autorização: câmera fixa, arco aceso, fumos.

## 6. Modelo v4 (soldadores reais) x v3, nos mesmos 28 trechos

O modelo v4 (`docs/resultados_treino/README.md`) foi avaliado com as mesmas regras, vídeos e trechos. A planilha da v3
foi guardada em `testes_campo/planilha_testes_campo_v3.xlsx`, e o modelo da v3 em `models/epi_solda_best_v3.pt`.

| Métrica | v3 | v4 |
|---|---|---|
| Recall da ausência (testes "ocorrência") | 82% (9/11) | 82% (9/11) |
| Falsos positivos (ocorrências erradas) | 0% | 0% |
| Testes "sem ocorrência" com alarme falso | 0 de 12 | 0 de 12 |
| Mistos (revisão manual) | 6 VP, 0 FP | as mesmas 6 ocorrências (VP) |
| **Máscara abaixada confirmada (verde)**, média dos testes | 14% | **26%** |
| Máscara levantada com o motivo certo ("MÁSCARA LEVANTADA") | nenhum teste | **T28** |
| **Verde falso** em testes **sem máscara**, média | 0,8% | **7,2%** |
| FPS médio nos testes | 11,0 | 11,3 |

**O que melhorou:**
- verde na máscara abaixada: T05 (de costas) de 0% para **83%**, T06 de 0% para 18%, T15 de 0% para 21% e T27 de 49% para 60%;
- o soldador com **máscara laranja de fibra** do T04 passou a ficar verde (22% do tempo; antes, 2%);
- no T28 a ocorrência saiu com o motivo **"máscara levantada"** (antes, "rosto visível sem máscara").

**O que piorou: verde falso em dois testes sem máscara.** Isso não gerou alarme falso nem mudou as ocorrências, mas
o sistema mostra "conforme" para quem está sem proteção:
- **T10** (sem máscara, **cabeça baixa no escuro**, esmerilhando): 45% verde. O topo da cabeça escura, visto de cima,
  foi confundido com uma máscara (confiança 0,52–0,77). Na v3 esse teste ficava amarelo; nos dois modelos ele já era
  uma falha de recall;
- **T22** (gorro escuro com **óculos de maçarico**): 16% verde (6% na v3). O conjunto gorro + óculos foi confundido
  com uma máscara (confiança 0,57–0,87). A ocorrência saiu mesmo assim.

**Subir o limiar de confiança não resolve:** com 0,70, sobram 53% dos verdes verdadeiros e 51% dos falsos (medido
nos quadros verdes de T05, T06, T07, T15 e T27 x T10 e T22). Corrigir isso exige **exemplos negativos** de cabeça
baixa, gorro e óculos sem máscara, de preferência gravados no posto real (RF33).

**Máscara abaixada que continua amarela:** T03, T20 e T26 (perfil ou arco aceso) e T02 (de costas, que caiu de 32%
para 0%). Nesses casos o sistema não confirma, mas também não acusa.

## 7. Modelo v5 (negativos difíceis) x v4 x v3, nos mesmos 28 trechos

A v5 é a v4 com 362 quadros de vídeos do Pexels de pessoas **sem** máscara (cabeça baixa, oficina escura, capacete
de obra, boné, óculos com maçarico), só no treino (D30). Planilhas: `planilha_testes_campo_v3.xlsx`,
`planilha_testes_campo_v4.xlsx` e `planilha_testes_campo.xlsx` (v5). Modelos: `models/epi_solda_best_v3.pt`,
`epi_solda_best_v4.pt` e `epi_solda_best.pt` (v5).

| Métrica | v3 | v4 | v5 |
|---|---|---|---|
| Recall da ausência | 82% (9/11) | 82% (9/11) | 82% (9/11) |
| Testes "sem ocorrência" com alarme falso | 0 de 12 | 0 de 12 | 0 de 12 |
| Mistos (revisão manual) | 6 VP | 6 VP | 6 VP (as mesmas ocorrências) |
| **Verde falso** em testes sem máscara (média) | 0,9% | 7,3% | **1,3%** |
| Verde na máscara abaixada (média) | 14,3% | **25,8%** | 19,3% |
| Máscara levantada com o motivo certo | – | T28 | – |
| FPS médio nos testes | 11,0 | 11,3 | 12,9 |

**O que a v5 corrigiu:** o verde falso do **T10** (cabeça baixa no escuro) caiu de 45% para **0%**, e o do **T22**
(gorro + óculos de maçarico) de 16% para 10% (6% na v3). Na média dos testes sem máscara, o verde falso voltou
praticamente ao nível da v3 (1,3%).

**O que a v5 perdeu em relação à v4:** ficou mais "desconfiada". Continua confirmando a máscara de costas no T05
(83%) e a do T07 (50%), mas deixou de confirmar a do T06 (18% → 0%), a do T15 (21% → 1%) e a máscara laranja de
fibra do T04 (22% → 4%); T27 caiu de 60% para 39%. O T28 voltou a sair como "rosto visível sem máscara" (a v4
reconhecia a máscara levantada). Nada disso mudou as ocorrências: nos três modelos, as mesmas.

**Leitura:** o verde da v5 é mais **confiável** (quase nunca aparece para quem está sem máscara), ao custo de
aparecer menos para quem está de máscara (19% contra 26%). Para um sistema de segurança, um "conforme" falso é pior
que um "indeterminado", por isso a v5 é o modelo recomendado. Melhorar os dois ao mesmo tempo exige imagens do posto
real (RF33), com máscaras abaixadas e pessoas sem máscara no mesmo ambiente.
