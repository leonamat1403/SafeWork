# Plano da Fase 1 – Validação da Detecção

**Projeto:** Verificador de EPIs de Solda com Visão Computacional (FSG + Marcopolo)
**Etapa:** 1.1 – Plano enxuto da Fase 1
**Escopo:** detecção, pose, associação EPI → pessoa, filtro do arco, persistência de ocorrências (terminal/CSV) e testes.
**Fora do escopo desta fase:** banco de dados, API web, telas, login, blur e alertas (todos ficam para a Fase 2).

---

## 0. Decisão de escopo (11/10/2026) – foco na máscara de solda

Por orientação do orientador do projeto, a Fase 1 passa a validar **um único EPI: a máscara de solda**
(também chamada de capacete de solda: o protetor facial com visor escuro).

**Motivos:**
- é o EPI mais crítico da soldagem (protege olhos e rosto da radiação UV/IV do arco, de respingos e do calor);
- é o mais visível na câmera: um objeto grande na cabeça. Luvas e calçados são pequenos e ficam ocultos pela bancada;
- existem dados suficientes: Welding-PPE + "Welding Helmet" (UTP, CC BY 4.0, ~1100 imagens), contra apenas 43 caixas de máscara no Welding-PPE;
- o 1º treino (v1, 5 classes) mostrou métricas infladas para luvas/calçado (fotos de produto) e inconclusivas para a máscara (ver `docs/resultados_treino/README.md`).

**O que muda neste plano:**
- o modelo de EPI é treinado com **uma classe** (`mascara`). As imagens sem máscara entram como negativos;
- as regras dos itens 5.1 (máscara) e 5.6 (cor da caixa), o filtro do arco (6) e as ocorrências (7) continuam valendo;
- as regras de luvas (5.2), proteção do corpo (5.3), calçado (5.4) e capacete (5.5) ficam **documentadas como trabalho futuro**. A estrutura do código continua preparada para elas, mas na Fase 1 elas ficam desativadas no `config.yaml` e não serão implementadas nem testadas;
- as METAS DE VALIDAÇÃO da Fase 1 passam a ser só as da máscara (mAP@0.5 ≥ 0,60; meta boa 0,75) e as métricas práticas de campo.

---

## 1. Visão geral do fluxo

```
                 ┌───────────────────────────────┐
  fonte  ───────►│ leitura do frame (OpenCV)     │  webcam (índice) | arquivo | RTSP (com reconexão)
                 └──────────────┬────────────────┘
                                │ (pular_frames: processa 1 a cada N)
                                ▼
                 ┌───────────────────────────────┐
                 │ arc_filter                    │  fração de pixels com brilho >= 245
                 │ frame saturado?               │  passou de 15%?
                 └───────┬───────────────┬───────┘
                      sim│               │não
                         ▼               ▼
     frame IGNORADO: não roda     ┌──────────────────────────────┐
     os modelos; contadores       │ YOLOv8n-pose + ByteTrack     │ → pessoas, track_id, 17 keypoints
     pausados; tela mostra        │ YOLOv8 EPI (predict)         │ → caixas de EPI + confiança
     "ARCO - frame ignorado"      └──────────────┬───────────────┘
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │ body_regions                 │ cabeça, punhos, tronco+coxas,
                                  │ (ou fallback pela caixa)     │ tornozelos, orientação
                                  └──────────────┬───────────────┘
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │ compliance                   │ estado por EPI:
                                  │                              │ CONFORME / NÃO CONFORME /
                                  │                              │ INDETERMINADO (+ mascara_levantada)
                                  └──────────────┬───────────────┘
                                                 ▼
                ┌────────────────────────────────┴──────────────────────────┐
                ▼                                                           ▼
   desenho no frame (RF04/RF05)                            occurrences (RF18–RF20)
   caixa vermelha/amarela/verde,                           persistência por EPI → agrupamento
   rótulo "SEM MÁSCARA | SEM LUVA",                        → cooldown → linha no terminal + CSV
   FPS, status por EPI
```

**Ideia central:** o dataset Welding-PPE só tem classes de EPI **presentes**. Não há classe "pessoa" nem classes "sem_X".
Por isso a **ausência** é inferida: *se a região do corpo está visível e nenhum EPI foi associado a ela, o EPI está ausente.*
Se a região **não** está visível, não temos evidência de nada, e o estado é INDETERMINADO (nunca gera ocorrência).

---

## 2. Conceitos usados (resumo didático)

| Conceito | O que é | Para que usamos |
|---|---|---|
| **Detecção de objetos (YOLO)** | Rede que devolve caixas `(x1,y1,x2,y2)` + classe + confiança | Achar máscara, luvas, avental/macacão, calçado |
| **Estimativa de pose (YOLOv8n-pose)** | Devolve a caixa da pessoa + 17 pontos do corpo (keypoints COCO), cada um com confiança | Saber **onde** estão cabeça, punhos, tronco e pés |
| **Rastreamento (ByteTrack)** | Liga a mesma pessoa entre frames com um `track_id` | Contar persistência e cooldown por pessoa |
| **Fine-tuning** | Continuar o treino de um modelo pré-treinado com dados novos | Adaptar o detector ao posto real da Marcopolo |
| **imgsz** | Lado da imagem que entra na rede | Maior = vê objetos pequenos (luva, bota), porém mais lento |

Keypoints COCO usados (índice → ponto):

```
 0 nariz      1 olho esq.    2 olho dir.    3 orelha esq.   4 orelha dir.
 5 ombro esq. 6 ombro dir.   7 cotov. esq.  8 cotov. dir.
 9 punho esq. 10 punho dir. 11 quadril esq. 12 quadril dir.
13 joelho esq. 14 joelho dir. 15 tornoz. esq. 16 tornoz. dir.
```

Um keypoint é considerado **visível** quando sua confiança é `>= deteccao.conf_keypoint` (padrão 0.5).

> Atenção: no eixo Y da imagem, **para baixo é maior**. "Acima da linha dos olhos" significa `y < y_olhos`.

---

## 3. Regiões do corpo (body_regions)

```
          ┌──────────── caixa da pessoa ────────────┐
          │        ┌───────────┐                    │
          │        │  CABEÇA   │ ← orelhas/olhos/nariz + linha dos ombros
          │        │  (o o)    │   (fallback: 25% superior da caixa)
          │   ●────┴───────────┴────●   ombros (5,6)
          │   │                     │
          │   │   TRONCO + COXAS    │ ← ombros → quadris → joelhos
          │   │                     │   (fallback: 20%–75% da altura)
          │  ✋ punho          punho ✋  ← pontos 9 e 10 (fallback: laterais da metade central)
          │   ●──── quadris ────────●   (11,12)
          │   │                     │
          │   ●──── joelhos ────────●   (13,14)
          │        │         │
          │        👢        👢    ← tornozelos 15,16 (fallback: 10% inferior)
          └─────────────────────────────────────────┘
```

### 3.1 Cabeça
- **Centro horizontal:** média dos keypoints visíveis de cabeça (nariz, olhos, orelhas); se nenhum estiver visível, o ponto médio dos ombros.
- **Largura:** `max(distância entre orelhas, 0,5 × largura dos ombros) × 1,6`.
- **Base:** linha dos ombros. **Altura:** igual à largura (aprox. quadrada), estendida para cima para cobrir a máscara levantada.
- **Requisito mínimo:** pelo menos 1 orelha **ou** 1 ombro visível. Os olhos **não** são exigidos (máscara abaixada cobre os olhos).
- Sem esses pontos → cabeça "não visível".

### 3.2 Tronco + coxas
- Retângulo dos ombros até os joelhos, com largura entre os pontos mais externos de ombros/quadris (+ margem de 15%).
- Joelhos ocultos → base estimada em `quadril + 0,6 × (quadril − ombro)`.
- **Requisito mínimo:** pelo menos 1 ombro **e** 1 quadril visíveis.

### 3.3 Punhos e tornozelos
São usados como **pontos** (não regiões). Cada um é avaliado separadamente.

### 3.4 Orientação da pessoa
Necessária para não punir quem está **de costas**:

| Orientação | Regra |
|---|---|
| **frente** | nariz ou algum olho visível |
| **costas** | nariz e olhos invisíveis **e** ombro esquerdo (5) aparece à **esquerda** do ombro direito (6) na imagem |
| **indefinida** | demais casos (perfil, máscara abaixada, etc.) |

> Por que a ordem dos ombros? Quando a pessoa está de frente para a câmera, o ombro **esquerdo dela** aparece no lado **direito** da imagem. De costas, a ordem se inverte. Isso diferencia "máscara abaixada" (rosto coberto, mas de frente) de "de costas".

### 3.5 Fallback sem pose (RF12)
Se o modelo de pose falhar ou estiver desativado, as regiões vêm de proporções fixas da caixa da pessoa (cabeça = 25% superior, mãos = laterais da metade central, corpo = 20%–75%, pés = 10% inferior). O log registra **"modo fallback ativo"** e cada linha do CSV marca `modo_fallback=1`.
Observação: sem pose também **não há caixa de pessoa** (o detector de EPI não detecta pessoas). Portanto o fallback só se aplica quando a pose devolve a caixa com keypoints de baixa confiança, ou se usarmos o modelo de pose apenas como detector de pessoas.

---

## 4. Como medimos "o EPI está na região"

Não usamos IoU (interseção ÷ união), porque a máscara e a região da cabeça têm tamanhos muito diferentes, e o IoU ficaria baixo mesmo com a máscara corretamente no rosto. Usamos:

```
cobertura = área(caixa_EPI ∩ região) / área(caixa_EPI)       → "quanto do EPI está dentro da região"
```

Para pontos (punho/tornozelo), usamos a **distância do ponto até a borda da caixa do EPI** (zero se o ponto estiver dentro), normalizada pela altura da pessoa:

```
dist_norm = distância(ponto, caixa_EPI) / altura_da_pessoa_em_px
```

> Por que até a borda e não até o centro? O keypoint do punho fica no pulso. Já o centro de uma luva de raspa fica na mão ou no antebraço, e a distância até o centro passaria facilmente do limiar de 0,08.

**Uma detecção de EPI pertence a no máximo uma pessoa.** Quando há várias pessoas, cada luva/bota/máscara vai para o melhor candidato (menor distância ou maior cobertura), em ordem gulosa: primeiro o par mais próximo de todos, depois o próximo, e assim por diante.

---

## 5. Regras por EPI

### 5.1 Máscara de solda (RF07)

```
   MÁSCARA ABAIXADA            MÁSCARA LEVANTADA             SEM MÁSCARA
   ┌───────────┐               ┌───────────┐ ← centro acima
   │▓▓▓▓▓▓▓▓▓▓▓│ olhos/nariz   │▓▓▓▓▓▓▓▓▓▓▓│   da linha dos olhos
   │▓▓▓▓▓▓▓▓▓▓▓│ invisíveis    └───────────┘
   │▓▓▓▓▓▓▓▓▓▓▓│                  o   o   ← olhos visíveis       o   o
   └───────────┘                    ▾                              ▾
 ●──── ombros ────●          ●──── ombros ────●           ●──── ombros ────●
   CONFORME                   CONFORME + "mascara_levantada"   NÃO CONFORME
```

Ordem de decisão:
1. Existe caixa `mascara` com `cobertura(cabeça) >= 0,30`?
   - **Sim** → CONFORME. Se o centro da máscara estiver acima da linha dos olhos **e** olhos ou nariz estiverem visíveis → marcar `mascara_levantada = true` (na Fase 1 continua CONFORME; vira NÃO CONFORME só com RD03, na Fase 2).
2. Não existe máscara associada:
   - cabeça não visível → INDETERMINADO;
   - orientação = **frente** (olhos/nariz visíveis) → **NÃO CONFORME**;
   - qualquer outro caso (costas, indefinida) → INDETERMINADO.

> Efeito colateral aceito: se a máscara estiver abaixada mas o detector **não** a encontrar, o resultado é INDETERMINADO (olhos cobertos), e não um falso positivo. Erramos para o lado seguro.

### 5.2 Luvas de solda (RF08)
1. Pessoa com altura < `altura_min_pessoa_px` (200) → INDETERMINADO.
2. Para cada punho **visível**, procurar uma luva com `dist_norm <= dist_max_punho` (0,08).
3. Regra `"ambas"` (padrão):
   - algum punho visível **sem** luva → NÃO CONFORME;
   - senão, algum punho invisível → INDETERMINADO;
   - senão → CONFORME.
4. Regra `"pelo_menos_uma"`:
   - alguma luva associada → CONFORME;
   - senão, algum punho visível → NÃO CONFORME;
   - senão → INDETERMINADO.

```
   luva perto do punho            luva sobre a bancada
      ✋▓▓ ← dist ≈ 0               ✋                  ▓▓ (longe)
      CONFORME                     não associada → mão "sem luva"
```

> Interpretação do teste "um punho oculto + regra ambas → INDETERMINADO": vale quando o punho **visível** está com luva. Se o punho visível estiver **sem** luva, já há evidência de não conformidade → NÃO CONFORME.

### 5.3 Proteção do corpo (RF09)
1. Tronco não visível → INDETERMINADO.
2. Existe avental (se `aceitar_avental`) ou macacão (se `aceitar_macacao`) com `cobertura(tronco+coxas) >= 0,30`? → CONFORME.
3. Senão:
   - orientação = **costas** → INDETERMINADO (o avental fica na frente do corpo e não aparece de costas);
   - caso contrário → NÃO CONFORME.

**Detalhe importante do remapeamento:** no modelo treinado, avental e macacão viram uma única classe `protecao_corpo`. Com isso, `aceitar_macacao=false` **não teria como funcionar**, porque o modelo não saberia distinguir os dois.
**Decisão:** o notebook mantém **duas classes** no modelo (`avental` e `macacao`), e a lógica as junta em "proteção do corpo" respeitando `aceitar_avental`/`aceitar_macacao`. Assim o modelo fica com 5 classes: `mascara, luvas, avental, macacao, calcado`. A Etapa 1.2 confirmou que `helmet` é máscara de solda, então não há classe `capacete` (ver `docs/dataset_welding_ppe.md`). Isso atende ao RF09 e ao teste do RNF06 ("aceitar_macacao=false + só macacão → NÃO CONFORME").

### 5.4 Calçado de segurança (RF10)
Mesma lógica das luvas (regra "ambas"), usando tornozelos e `dist_max_tornozelo`:
- pessoa pequena demais → INDETERMINADO;
- nenhum tornozelo visível → INDETERMINADO;
- tornozelo visível sem calçado associado → NÃO CONFORME.
Desativado por padrão (`ativo: false`), porque a bancada costuma esconder os pés.

### 5.5 Capacete (RF11, opcional)
- Cabeça não visível → INDETERMINADO.
- Caixa `capacete` com centro **acima** da linha de olhos/orelhas e dentro da largura da cabeça → CONFORME; senão → NÃO CONFORME (só se orientação = frente; senão INDETERMINADO).
- Desativado por padrão.

### 5.6 Cor e rótulo da caixa da pessoa (RF04)
Só os EPIs **ativos** no posto entram na conta:

| Situação | Cor | Exemplo de rótulo |
|---|---|---|
| algum NÃO CONFORME | vermelho | `#3 SEM MÁSCARA \| SEM LUVA` |
| nenhum NC, algum INDETERMINADO | amarelo | `#3 ? LUVAS` |
| todos CONFORMES | verde | `#3 OK` |

`mascara_levantada` aparece como texto extra (`MÁSCARA LEVANTADA`) sem mudar a cor na Fase 1.
Na Fase 1 a cor é calculada **frame a frame** e por isso pode oscilar. A estabilização (votação temporal, RD01) é da Fase 2.

---

## 6. Filtro do arco elétrico (RF14)

```
  frame → escala de cinza → reduzido para 320 px de largura (mais rápido)
        → fração = (pixels com brilho >= limiar_brilho) / total
        → fração > fracao_max_saturada ?  →  frame IGNORADO
```

Quando o frame é ignorado:
- os modelos **não rodam** (economiza CPU). O ByteTrack tolera essa lacuna e mantém os IDs por até ~30 frames;
- os contadores de persistência ficam **pausados** (não avançam e não zeram);
- a tela mostra o último estado válido de cada pessoa e o aviso **"ARCO DETECTADO - frame ignorado"**;
- o contador de `frames_ignorados_saturacao` aparece no resumo final.

**Risco a medir em campo:** na solda MIG o arco fica aceso por vários segundos seguidos. Se a câmera estourar com frequência, o sistema fica "cego" justamente durante a soldagem. A mitigação é o posicionamento da câmera (fora da linha direta do arco, exposição manual/fixa), e o % de frames ignorados entra no roteiro de testes de campo (Etapa 1.5).

---

## 7. Ocorrências: persistência, cooldown e agrupamento (RF18–RF20)

Estado mantido por `(track_id, epi)`:

```
 frame válido, EPI = NÃO CONFORME  → contador += 1
 frame válido, EPI = CONFORME      → contador = 0
 frame válido, EPI = INDETERMINADO → contador = 0   ("consecutivos" é levado ao pé da letra; evita falsos positivos)
 frame saturado                    → contador inalterado (pausa)
```

Disparo:
1. Quando o contador de algum EPI atinge `frames_persistencia` daquele EPI **e** esse EPI **não está em cooldown** para o `track_id`, é gerada uma ocorrência.
2. **Agrupamento (RF20):** a ocorrência lista **todos** os EPIs que estão NÃO CONFORMES naquele frame (mesmo que ainda não tenham atingido o próprio N). Todos os EPIs listados entram em cooldown juntos.
   *Exemplo:* máscara (N=20) e luvas (N=30) ausentes desde o início → no frame 20 sai **1** ocorrência com `mascara;luvas`. No frame 30 as luvas já estão em cooldown, então não sai uma segunda ocorrência.
3. **Cooldown (RF19):** `cooldown_s` (60 s) por `(track_id, epi)`, medido pelo **tempo do vídeo** (posição do frame) e não pelo relógio do computador. Assim o teste com arquivo de vídeo é reproduzível.

**Limitação conhecida:** se o ByteTrack trocar o ID da pessoa (oclusão longa, cruzamento), a mesma pessoa pode gerar uma nova ocorrência. Isso será medido na revisão manual.

### Saída
- **Terminal:** uma linha por ocorrência, ex.: `[00:01:23] posto=mig_01 pessoa#3 FALTANDO: mascara, luvas | indeterminado: calcado`.
- **CSV** (`--csv caminho.csv`), uma linha por ocorrência:

| coluna | exemplo |
|---|---|
| `timestamp_video` | `00:01:23.400` |
| `data_hora` | `2026-10-10 14:32:05` |
| `fonte` | `video_posto1.mp4` |
| `posto` | `mig_01` |
| `frame` | `2085` |
| `track_id` | `3` |
| `epis_faltantes` | `mascara;luvas` |
| `epis_indeterminados` | `calcado` |
| `confianca_media` | `{"protecao_corpo":0.71}` (média das detecções associadas na janela; EPIs faltantes não têm confiança) |
| `mascara_levantada` | `0` |
| `modo_fallback` | `0` |
| `revisao_manual` | *(vazio – você preenche: VP / FP)* |

- **Resumo ao final:** frames lidos, processados, ignorados por arco, FPS médio, nº de ocorrências.
- A coluna `revisao_manual` é o que permite medir a taxa de falsos positivos na Fase 1.

---

## 8. Configuração (config.yaml) – EPIs por posto (RF13)

Os valores em `epis:` são o **padrão**. Cada posto em `postos:` **sobrescreve só o que muda** (mescla profunda). O posto é escolhido na linha de comando com `--posto`.

```yaml
epis:
  mascara:        {ativo: true,  conf: 0.45, frames_persistencia: 20, cobertura_min: 0.30}
  luvas:          {ativo: true,  conf: 0.40, frames_persistencia: 30, dist_max_punho: 0.08, regra: "ambas"}
  protecao_corpo: {ativo: true,  conf: 0.50, frames_persistencia: 15, cobertura_min: 0.30,
                   aceitar_avental: true, aceitar_macacao: true}
  calcado:        {ativo: false, conf: 0.35, frames_persistencia: 30, dist_max_tornozelo: 0.08}
  capacete:       {ativo: false, conf: 0.50, frames_persistencia: 15}

postos:
  padrao: {}                                   # usa "epis" como está
  mig_01:
    descricao: "Posto de solda MIG/MAG 01"
    epis: {}                                   # máscara + luvas + proteção do corpo
  corte_01:
    descricao: "Área de corte"
    epis:
      mascara:        {ativo: false}
      protecao_corpo: {ativo: false}
      calcado:        {ativo: true}

deteccao: {imgsz: 960, imgsz_pose: 640, altura_min_pessoa_px: 200, pular_frames: 1, conf_keypoint: 0.5}
arco:     {limiar_brilho: 245, fracao_max_saturada: 0.15, exigir_mascara_somente_com_arco: false}
ocorrencias: {cooldown_s: 60, retencao_dias: 30}    # retencao_dias é ignorado na Fase 1
turnos: {"1": "06:00-14:00", "2": "14:00-22:00", "3": "22:00-06:00"}   # ignorado na Fase 1
modelos: {epi: "models/epi_solda_best.pt", pose: "models/yolov8n-pose.pt"}

mapeamento_classes:            # camada de segurança para modelos com nomes originais
  "Welding Mask": mascara
  "Welding Gloves": luvas
  "welding-glove": luvas
  "Welding Apron": avental
  "apron": avental
  "Welding Coverall": macacao
  "Safety Shoes": calcado
  "welding-shose": calcado
  "helmet": mascara            # verificado na Etapa 1.2: são máscaras/capacetes de SOLDA
```

Diferenças em relação ao exemplo do prompt (todas justificadas acima):
- `postos:` (RF13), `cobertura_min`, `imgsz_pose` e `modelos:` foram **adicionados**;
- `apron`/`Welding Apron` → `avental` e `Welding Coverall` → `macacao` (em vez de `protecao_corpo` direto), por causa do item 5.3;
- `config.py` valida o arquivo ao iniciar (chaves obrigatórias, faixas 0–1, regra de luvas válida) e aborta com uma mensagem clara se houver erro.

---

## 9. Decisões técnicas

| # | Decisão | Motivo |
|---|---|---|
| D1 | **Dois modelos no mesmo frame:** pose com `model.track(persist=True, tracker="bytetrack.yaml")`; EPI com `model.predict()` | O tracking só faz sentido para pessoas. O EPI é associado à pessoa pela geometria a cada frame |
| D2 | `imgsz_pose` separado do `imgsz` do EPI (pose fixa em 640) | Pessoas são objetos grandes; o custo de CPU fica no detector de EPI, que precisa de resolução para luvas e botas (RF16) |
| D3 | EPI roda com `conf` = **menor** limiar entre as classes, e o filtro por classe é aplicado depois (RF15) | O Ultralytics só aceita um `conf` global |
| D4 | `body_regions`, `compliance` e `occurrences` recebem **estruturas simples** (dataclasses `Pessoa`, `DeteccaoEPI`, `Keypoint`), sem depender do Ultralytics | Permite testar com caixas e keypoints simulados no pytest (RNF06) e reaproveitar na Fase 2 sem mudanças |
| D5 | `detector.py` é o **único** módulo que conhece o Ultralytics: converte os resultados para essas dataclasses e aplica o `mapeamento_classes` | Isola a biblioteca; trocar o modelo não afeta a lógica |
| D6 | Modelo de EPI com classes separadas `avental` e `macacao` | Viabiliza `aceitar_avental`/`aceitar_macacao` (item 5.3) |
| D7 | Associação gulosa (1 EPI → no máximo 1 pessoa / 1 punho) | Simples de explicar; com poucas pessoas por posto, o resultado é o mesmo do algoritmo ótimo (húngaro) |
| D8 | Tempo de cooldown pelo **tempo do vídeo** | Testes reproduzíveis com arquivo |
| D9 | RTSP: ao falhar a leitura, tenta reconectar com espera crescente (1, 2, 4… até 30 s), sem derrubar o programa (RNF03) | Câmeras IP caem com frequência em rede industrial |
| D10 | Modelos `.pt` carregados de `models/` local; se o arquivo não existir, o programa para com uma mensagem dizendo onde obtê-lo (sem download automático) | Rede corporativa com proxy, uso offline |
| D11 | Versões **fixadas** no `requirements.txt` (RNF07): ultralytics, opencv-python, PyYAML, pytest. As versões exatas serão conferidas no PyPI na Etapa 1.3 | Reprodutibilidade |
| D12 | O `run.py` mede o FPS (média móvel) e imprime um resumo; a opção `--benchmark` roda um vídeo sem janela e reporta o FPS a 640 e a 960 | RNF01 / RF16: medir em vez de estimar |
| D13 | `--salvar-saida` grava só em `testes_campo/` (fora do git) | Privacidade das gravações de campo |

### CLI prevista (`src/run.py`)
```
python -m src.run --fonte 0                         # webcam
python -m src.run --fonte testes_campo/video1.mp4 --posto mig_01 --csv testes_campo/res1.csv
python -m src.run --fonte rtsp://camera/stream --salvar-saida
python -m src.run --fonte testes_campo/video1.mp4 --benchmark
```
Teclas na janela: `q` sai, `p` pausa/retoma.

### Responsabilidade de cada módulo
| Módulo | Faz | Não faz |
|---|---|---|
| `config.py` | lê/valida o YAML, mescla posto + padrão | – |
| `detector.py` | carrega modelos, roda pose+track e EPI, converte para dataclasses, aplica o mapeamento | regras de negócio |
| `body_regions.py` | regiões, visibilidade, orientação, fallback | decidir conformidade |
| `compliance.py` | associação EPI→pessoa, 3 estados, máscara levantada, cor/rótulo | desenhar, contar frames |
| `arc_filter.py` | fração saturada e decisão de ignorar o frame | – |
| `occurrences.py` | persistência, agrupamento, cooldown, escrita no CSV | detecção |
| `run.py` | laço de vídeo, desenho, janela, CLI, reconexão, resumo | regras |

---

## 10. Riscos e limitações já previstas

| Risco | Efeito | Mitigação / como medir |
|---|---|---|
| Dataset pequeno (~800 imagens) e de outro ambiente | Recall baixo no posto real | Augmentations + fine-tuning com fotos do parceiro (RF33) |
| Luvas e calçado são objetos pequenos e costumam ficar ocultos | Muitos INDETERMINADOS | imgsz 960, `altura_min_pessoa_px`, INDETERMINADO nunca gera ocorrência |
| Arco estoura a câmera por longos períodos | Sistema "cego" durante a solda | Posicionamento/exposição; medir o % de frames ignorados |
| Troca de ID no ByteTrack | Ocorrência duplicada | Revisão manual no CSV |
| Copy-paste do Ultralytics exige máscaras de segmentação | Essa augmentation não tem efeito num dataset só com caixas | Documentar no notebook (Etapa 1.2) |
| Orientação "costas" depende da ordem dos ombros | Pose pode errar o lado | Na dúvida a orientação fica "indefinida", que leva a INDETERMINADO |
| CPU sem GPU | FPS abaixo de 5 a 960 | `pular_frames`, imgsz 640, benchmark documentado |
| Licença do Ultralytics é AGPL-3.0 | Ok para uso acadêmico; uso interno contínuo pela empresa exige atenção | Citar no relatório |

---

## 11. Próxima etapa (1.2)
- Verificação do dataset Welding-PPE (versão atual, nº de imagens, splits, classe `helmet`). Campos marcados para você confirmar na página.
- Notebook do Colab: download via API, remapeamento para as classes internas (com `avental`/`macacao` separados), contagem de instâncias por classe, treino de YOLOv8n/s a 640/960, métricas por classe, matriz de confusão e exportação do `best.pt`.

**Requisitos tratados neste plano:** desenho de RF03–RF20, RF31–RF33 (planejamento), RNF01–RNF03, RNF06 [FASE 1], RNF07.
