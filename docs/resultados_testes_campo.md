# Resultados dos testes de campo – rodada 1 (13/10/2026)

**Etapa 1.5.** Testes com 13 vídeos de banco de imagens (provável Pexels, a confirmar) e o vídeo da webcam (T01),
avaliados com `ferramentas/avaliar_testes.py`. A planilha completa fica em `testes_campo/planilha_testes_campo.xlsx`
(fora do git, porque contém vídeos de pessoas). Modelo de máscara: **v3 (`yolov8n_640`)**.

## 1. Base de testes

16 testes (trechos de vídeo). Cada vídeo foi conferido quadro a quadro, e vários precisaram ser reclassificados em
relação às pastas em que foram entregues:

| Teste | Vídeo | Situação real (revisada) | Ângulo | Arco | Observação |
|---|---|---|---|---|---|
| T01 | webcam (próprio) | sem máscara | varia | apagado | cabeça em todas as direções |
| T02 | 10294767 | máscara (não visível) | costas | apagado | esmerilhamento |
| T03 | 13550763 | máscara abaixada | perfil, ~5 m | aceso | fumaça |
| T04 | 13751344 | **misto** | frente | aceso | ajudantes com **respirador**, sem máscara de solda |
| T05 | 14314690 | máscara abaixada | costas | aceso | levanta a máscara nos últimos ~2 s |
| T06 | 14314814 | máscara abaixada | frente, ~1 m | aceso | outra pessoa passa ao fundo por ~2 s |
| T07 | 15809710 (0–6,5 s) | máscara abaixada | frente | apagado | esmerilhamento |
| T08 | 4941454 | **máscara levantada** | costas | apagado | estava em "conformes" |
| T09 | 13258042 | sem máscara | frente | aceso | soldando sem máscara (vídeo existente) |
| T10 | 5846600 | sem máscara | frente | apagado | **cabeça baixa, ambiente escuro** |
| T11 | 6046352 | sem máscara | costas | apagado | rosto escondido |
| T12 | 14742079 | **misto** | varia, ~6 m | apagado | oficina com muitas pessoas |
| T13 | 17039559 | **misto** | perfil | aceso | ajudante sem proteção nos olhos |
| T14 | 6046354 (0–14,5 s) | **misto** | perfil | aceso | observador com escudo de mão afastado do rosto |
| T15 | 6046354 (15 s–fim) | máscara abaixada | frente | aceso | os dois protegidos |
| T16 | 15809710 (6,5 s–fim) | **misto** | perfil | apagado | aluno sem máscara parado perto |

## 2. Problema encontrado: a pose "enxerga" um rosto atrás da máscara de solda

Na primeira avaliação, os soldadores **com máscara** geraram ocorrências falsas. O diagnóstico frame a frame mostrou
duas causas:

1. **O modelo de pose (YOLOv8n-pose, treinado com pessoas comuns) "imagina" olhos e nariz através da máscara**, com
   confiança ≥ 0,5 em 84% a 100% dos frames. As regras que dependiam de "rosto visível" concluíam "SEM MÁSCARA" ou
   "MÁSCARA LEVANTADA" para quem estava protegido.
2. **O detector de máscara não reconhece bem máscaras reais em uso** em vários vídeos (0% dos frames em T03, T06 e T15),
   porque aprendeu principalmente com fotos de produto (dataset Welding Helmet).

**Correção (D27):** "rosto visível" passou a vir de um **detector de rostos de verdade** (YuNet, do OpenCV Zoo,
licença MIT), executado no recorte da cabeça de cada pessoa. Um rosto coberto pela máscara não é detectado como rosto:

| Vídeo | Rosto "visto" pela pose | Rosto visto pelo YuNet |
|---|---|---|
| Soldadores com máscara (T03, T06, T07, T15) | 26% a 100% | **0% a 1%** |
| Sem máscara (T01 webcam, T09 soldando) | 96% a 98% | **86% a 98%** |
| Sem máscara, cabeça baixa e escuro (T10) | 100% | 0% |

## 3. Métricas (testes que não são "misto")

| Métrica | Meta | Antes (pose) | **Depois (YuNet)** |
|---|---|---|---|
| Recall da ausência (testes "ocorrência" com ocorrência) | ≥ 70% | 100% (3/3) | **67% (2/3)** ❌ |
| Falsos positivos (ocorrências erradas ÷ ocorrências) | ≤ 30% | 60% ❌ | **0%** ✅ |
| Testes "sem ocorrência" com alarme falso | – | 62,5% (5/8) | **0% (0/8)** |
| FPS mínimo (processamento completo, imgsz 640) | ≥ 5 | 11,3 | **7,7** ✅ |
| % do tempo com a máscara reconhecida (testes com máscara abaixada) | – | 5% | 13% |

O FPS da rodada "depois" foi medido **com um jogo aberto no computador** (CPU a ~58%). Com o computador livre, o
pipeline completo rodava a 15 FPS sem o YuNet. O YuNet custa ~7 ms por pessoa.

**Leitura:**
- A correção eliminou os alarmes falsos, e o FP passou de 60% para 0%. O "recall de 100%" anterior era enganoso:
  o sistema dizia "SEM MÁSCARA" para quase todo mundo, inclusive para quem estava de máscara.
- O único teste "ocorrência" que falhou foi o **T10** (sem máscara, **cabeça baixa e ambiente escuro**). O rosto não
  aparece, o sistema fica amarelo e não acusa. Isso é uma limitação conhecida.
- Com só **3 testes** de "ocorrência", o recall ainda **não tem valor estatístico**: cada teste vale 33 pontos
  percentuais. São necessários mais vídeos de pessoas sem máscara.

### Testes mistos (revisão manual das ocorrências)

| Teste | Ocorrências | Quem foi acusado | Revisão |
|---|---|---|---|
| T04 | 0 | ninguém (os 2 ajudantes de respirador não foram acusados) | **falha**: respirador cobre nariz/boca, o rosto não é detectado |
| T12 | 3 | pessoas #33 e #61 (de frente, sem máscara) e #69 (de costas) | 3 VP; o #69 foi acusado por um "rosto" detectado na nuca (conf. 0,56) |
| T13 | 1 | ajudante de capacete azul, sem proteção | VP |
| T14 | 1 | observador com o escudo de mão afastado do rosto | VP |
| T16 | 1 | aluno sem máscara (o soldador mascarado ficou **verde**) | VP |

Contando os mistos: **recall 75% (6/8 situações)** e **0 falsos positivos em 9 ocorrências**.

Observação: no T09, o mesmo soldador gerou 2 ocorrências a 6 s de distância porque o rastreamento trocou o ID dele
durante os clarões do arco (limitação conhecida do ByteTrack).

## 4. Limitações observadas

1. **Rosto escondido** (cabeça baixa, escuro, de costas, respirador): o sistema fica INDETERMINADO e não acusa.
2. **A máscara correta raramente fica verde** (13% do tempo): o detector de máscara ainda não reconhece bem máscaras
   reais em uso. O sistema não gera alarme falso nesses casos, mas também não "confirma" a conformidade. Fine-tuning
   com imagens reais é necessário (RF33).
3. **Falso "rosto" na nuca** (T12 #69): o YuNet pode confundir a parte de trás da cabeça com um rosto. Pode ser
   ajustado subindo `conf_rosto` (0,6 → 0,7), o que precisa ser testado.
4. **Máscara levantada vista de costas** (T08) não é reconhecida como levantada.
5. **Troca de ID** do rastreamento com clarões do arco pode duplicar ocorrências.

## 5. Próximos passos

1. **Mais vídeos de pessoas SEM máscara de frente** (2 a 6 m), para o recall ter base estatística (meta: ≥ 10 testes).
2. **Vídeos com máscara levantada de frente** (C14) e com a máscara sendo levantada por poucos segundos (C15): ainda
   não há nenhum.
3. **Fine-tuning do detector de máscara** com imagens de soldadores reais (outros vídeos, nunca os de teste).
4. Repetir o benchmark de FPS com o computador livre.
