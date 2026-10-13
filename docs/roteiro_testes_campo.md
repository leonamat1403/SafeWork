# Roteiro de testes de campo – Fase 1 (máscara de solda)

**Etapa 1.5.** Este roteiro diz **o que gravar**, **como avaliar** e **como medir** se a detecção atende às METAS DE
VALIDAÇÃO. Ferramentas:
- `ferramentas/capturar.py` – grava vídeos da webcam;
- `docs/planilha_testes_campo.xlsx` – modelo da planilha de testes e métricas;
- `ferramentas/avaliar_testes.py` – processa os vídeos listados na planilha e preenche os resultados.

## 1. O que queremos medir

| Métrica | Meta (prompt do projeto) | Onde aparece |
|---|---|---|
| **Recall da ausência**: nos testes em que a pessoa está sem máscara (ou com ela levantada) de frente/perfil, o sistema registrou a ocorrência? | **≥ 70%** | Planilha › Métricas |
| **Falsos positivos**: das ocorrências registradas, quantas eram erradas (pessoa com a máscara correta)? | **≤ 30%** | Planilha › Métricas (revisão manual na aba Ocorrências) |
| **FPS** em CPU, imgsz 640, processamento completo (pose + máscara + regras) | **≥ 5** | Planilha › Métricas e `python -m src.run --benchmark` |

Informativos (para o relatório): % do tempo reconhecido como "sem máscara", % de "OK" falso, % de INDETERMINADO, frames
ignorados pelo arco, e os mesmos números **por distância, ângulo e arco** (recortes na aba Métricas).

### Critérios de aceite da Fase 1 que este roteiro verifica (adaptados ao foco na máscara)

| Critério | Como verificar |
|---|---|
| Soldador a ~3 m, de frente, sem máscara, fica **vermelho** com o rótulo correto em até ~1 s | Cenários C01/C04: a caixa fica vermelha já nos primeiros frames (o **registro** da ocorrência vem após 4 s, por decisão D24) |
| Com a máscara abaixada fica **verde** mesmo sem os olhos visíveis | Cenários C10/C11: % CONFORME alto e nenhuma ocorrência |
| Máscara levantada é sinalizada | Cenário C14: rótulo "MASCARA LEVANTADA" e ocorrência após 4 s (decisão D25) |
| Frames saturados pelo arco são ignorados e não geram ocorrência | Cenários C16/C17: `ignorados_arco` > 0 e nenhuma ocorrência |
| Pessoa sem máscara gera 1 ocorrência; a mesma pessoa parada gera só 1 por janela de cooldown | Cenário C01 com vídeo de 60 s: exatamente 1 ocorrência |
| FPS ≥ 5 com imgsz 640 e FPS com 960 documentado | `python -m src.run --benchmark` + coluna `fps` |
| Testes pytest [FASE 1] passam | `python -m pytest` |

## 2. Segurança, ética e privacidade (leia antes de gravar)

- **Nunca peça para alguém soldar ou ficar perto de um arco aceso sem máscara** para gerar um teste. Cenários com arco
  aceso e pessoa sem máscara (C18) **só com vídeos já existentes** (internet).
- Testes com arco aceso: só com soldadores habilitados, com todos os EPIs, no laboratório ou na empresa, com autorização.
- Grave **apenas pessoas que autorizaram** (de preferência por escrito). Na Marcopolo, com autorização prévia da empresa
  e dos trabalhadores (exigência do projeto).
- Os vídeos ficam em `testes_campo/`, que está **fora do git**. No relatório, use números e, nas imagens, **rostos
  borrados**. O sistema não identifica ninguém: `pessoa #3` é só um número temporário do rastreamento.

## 3. Câmera e gravação

- **Câmera parada** (tripé, prateleira ou apoio), na altura de **1,6 a 2 m**, levemente inclinada para baixo, como uma
  câmera instalada no posto. Evite segurar o celular na mão.
- Enquadre o soldador **da cintura para cima ou inteiro**. Resolução de pelo menos 720p.
- Com arco aceso: câmera **fora da linha direta do arco** e, em ambiente real, protegida (vidro/policarbonato) de faíscas.
- **Um clipe por cenário**, de **20 a 60 s**, com **uma única situação** do começo ao fim (ex.: só sem máscara). Se um
  vídeo tiver várias situações, cadastre cada trecho como uma linha da planilha, usando `inicio_s` e `fim_s`.
- Nome sugerido: `cXX_descricao_distancia_data.mp4`, ex.: `c01_sem_mascara_frente_2m_20261013.mp4`.
- Webcam do computador:
  ```
  python ferramentas/capturar.py --saida testes_campo/c01_sem_mascara_frente_1m.mp4 --duracao-s 30
  ```
  Celular: grave normalmente e copie o arquivo para `testes_campo/`.

## 4. Cenários

Os mesmos cenários estão na aba **Cenários** da planilha (com o resultado esperado e a contagem de testes feitos).

### Fase A – só com webcam ou celular (dá para fazer agora)

| ID | Cenário | Situação real | Esperado |
|---|---|---|---|
| C01 | Sem máscara, de frente | sem_mascara | ocorrência |
| C02 | Sem máscara, de perfil | sem_mascara | ocorrência |
| C03 | Sem máscara, de costas | sem_mascara (costas) | sem ocorrência (fica AMARELO) |
| C04 | Sem máscara, de frente, a ~4 m | sem_mascara | ocorrência |
| C05 | Sem máscara, de frente, a ~6 m | sem_mascara | ocorrência |
| C06 | Sem máscara, mexendo a cabeça (cima, baixo, lados, perfil) | sem_mascara (varia) | ocorrência |
| C07 | Sem máscara com luz forte de lado ou contraluz | sem_mascara | ocorrência |
| C08 | Sem máscara de solda, de boné ou capacete de segurança | sem_mascara | ocorrência |
| C09 | Pessoa passa sem máscara por menos de 4 s | pausa_curta | sem ocorrência |

### Fase B – com uma máscara de solda

| ID | Cenário | Situação real | Esperado |
|---|---|---|---|
| C10 | Máscara abaixada, de frente | mascara_abaixada | sem ocorrência |
| C11 | Máscara abaixada, de perfil | mascara_abaixada | sem ocorrência |
| C12 | Máscara abaixada, de costas | mascara_abaixada | sem ocorrência |
| C13 | Máscara abaixada a 4 m e a 6 m (um clipe para cada) | mascara_abaixada | sem ocorrência |
| C14 | Máscara levantada (sobre a cabeça) por mais de 4 s | mascara_levantada | ocorrência |
| C15 | Levanta a máscara por ~2 s para olhar o cordão e abaixa | pausa_curta | sem ocorrência |

### Fase C – com arco, fumos e várias pessoas (laboratório, Marcopolo ou vídeos da internet)

| ID | Cenário | Situação real | Esperado |
|---|---|---|---|
| C16 | Soldando com máscara abaixada e arco aceso | mascara_abaixada | sem ocorrência; `ignorados_arco` > 0 se a câmera estourar |
| C17 | Soldando com máscara abaixada, com fumos e faíscas | mascara_abaixada | sem ocorrência |
| C18 | Arco aceso e soldador sem máscara – **somente vídeos já existentes** | sem_mascara | ocorrência |
| C19 | Duas pessoas: uma com máscara, outra sem | misto | revisão manual |

**Mínimo recomendado para o relatório:** C01, C02, C03, C04, C06 e C09 (Fase A) e, se houver máscara ou vídeos,
C10, C14, C15 e C16. Repita os cenários principais com **2 ou 3 pessoas diferentes**, se possível.

### Vídeos da internet
Use bancos de vídeo com licença livre (**Pexels**, **Pixabay**), buscando `welding`, `welder`, `welding helmet`.
Escolha vídeos com câmera estável, pessoa da cintura para cima e situações claras. Evite closes do cordão de solda e
vídeos filmados de dentro da máscara. Cadastre cada vídeo na aba **Fontes** (link, licença, uso) e cada trecho
útil como uma linha na aba **Testes**, com `inicio_s`/`fim_s`. **Vídeos usados em teste não podem ir para o treino.**

## 5. Passo a passo da avaliação

1. **Criar a planilha** (só na primeira vez):
   ```
   python ferramentas/avaliar_testes.py
   ```
   Isso cria `testes_campo/planilha_testes_campo.xlsx` a partir do modelo em `docs/`.
2. **Preencher a aba Testes**, uma linha por vídeo ou trecho, nas colunas **amarelas**:
   - `ID` (T02, T03…) e `arquivo` (ex.: `testes_campo/c01_sem_mascara_frente_2m.mp4`);
   - `situacao_real`: **o que realmente acontece** no trecho. É a coluna mais importante;
   - `angulo`, `distancia_m`, `arco`, `fumos`, `pessoas`, `origem`, `cenario` (C01…);
   - `inicio_s`/`fim_s`, só se for usar um trecho do vídeo.
3. **Fechar a planilha no Excel** e rodar:
   ```
   python ferramentas/avaliar_testes.py
   ```
   As colunas **cinzas** e a aba **Ocorrências** são preenchidas. O terminal mostra o resumo de cada teste.
   Para ver os vídeos anotados (útil na revisão), use `--salvar-saida`. Para reavaliar tudo (ex.: depois de trocar o
   modelo ou o `config.yaml`), use `--todos`.
4. **Revisar as ocorrências:** na aba **Ocorrências**, a classificação automática diz VP (o teste esperava ocorrência)
   ou FP (não esperava). Confira no vídeo e, se estiver errada, escreva **VP** ou **FP** em `revisao_manual`.
5. **Ver o resultado:** aba **Métricas** (recall, falsos positivos, FPS e recortes por condição).
6. **Medir o FPS oficial:** `python -m src.run --benchmark --fonte testes_campo/<um vídeo>.mp4` e anotar a tabela.

## 6. O que levar para o relatório (Etapa 1.6)

- A aba **Métricas** (valores e situação de cada meta) e os **recortes** por distância, ângulo e arco.
- A tabela do **benchmark** de FPS (640 x 960) e o processador usado.
- A lista de cenários testados (aba Cenários, coluna `testes_feitos`) e as fontes dos vídeos (aba Fontes).
- Casos de erro marcantes (com rostos borrados) e as **limitações** observadas.

Com esses números, a Etapa 1.6 compara o resultado com as METAS DE VALIDAÇÃO e indica se a Fase 1 pode ser encerrada.
