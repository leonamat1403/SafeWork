# Dados de treino – máscara de solda (Etapa 1.2)

> **Foco da Fase 1 (11/10/2026, com o orientador):** apenas a **máscara de solda** (= capacete de solda, o protetor
> facial com visor escuro). Ver `docs/plano_fase1.md`, seção 0.

## 1. Fontes de dados

### 1.1 Welding-PPE (conferido em 10/10/2026)

| Item | Valor |
|---|---|
| URL | https://universe.roboflow.com/welding-ppe/welding-ppe |
| Autor / licença | Welding PPE / **CC BY 4.0** (exige atribuição) |
| Imagens de origem | **801** |
| Classes | 9: helmet, apron, Safety Shoes, Welding Apron, Welding Coverall, Welding Gloves, Welding Mask, welding-glove, welding-shose |
| Caixas de máscara (`Welding Mask` + `helmet`) | **43** |
| Versões publicadas | v1 (153 imagens), v2 (3077), v3 (2413, a mais recente, de 11/06/2023). **Todas com "Isolate Objects"** (item 2.1) |
| Modelo de referência | `welding-ppe/3`, só via API em nuvem, treinado com recortes. **Não usado** (item 2.1) |
| Nosso fork | `leonardo-matte/welding-ppe-9n9br`, versão **v1** (Auto-Orient; Exposure ±25% + Blur 2,5 px, 2×) |

### 1.2 Welding Helmet (conferido em 10/10/2026)

| Item | Valor |
|---|---|
| URL | https://universe.roboflow.com/utp-jtbn5/welding-helmet |
| Autor / licença | UTP / **CC BY 4.0** |
| Imagens | **1098** |
| Classes | 1: `Helmet` (máscara/capacete de solda) |
| Conteúdo | maioria de fotos de produto (máscara sozinha sobre fundo neutro), com algumas fotos de uso real |
| Versão publicada | v1: Stretch 640×640 + rotações de 90° e outras augmentations. **Não usada**, porque máscara de lado ou de cabeça para baixo não acontece no posto |
| Nosso fork | `leonardo-matte/welding-helmet-nqk1c`, versão **v1** (Auto-Orient apenas) |

### 1.3 welder – soldadores reais (conferido em 13/10/2026, rodada v4)

| Item | Valor |
|---|---|
| URL | https://universe.roboflow.com/esports/welder |
| Autor / licença | ESports / **CC BY 4.0** |
| Imagens | **3.001** (Indonésia; nomes das classes em indonésio) |
| Classes | 7: Apron, Gloves, **Helm** (capacete/máscara de solda), Orang (pessoa), Tanpa_Apron, Tanpa_Gloves, Tanpa_Helm ("sem ...") |
| Conteúdo | sessão de fotos de um aluno com e sem máscara (`pribadi-…`, 958), quadros de vídeo de obra (`H-2206…`, `test…_mp4`), fotos da web (algumas com marca d'água de bancos de imagem), **705 fotos do COCO** e 28 imagens geradas por IA |
| Caixas `Helm` | 1.340 em 1.262 imagens; mediana de 4,9% da área da imagem |
| Nosso fork | `leonardo-matte/welder-hqw5c`, versão **v1** (Auto-Orient apenas) |

### 1.4 safeweld – soldadores reais (conferido em 13/10/2026, rodada v4)

| Item | Valor |
|---|---|
| URL | https://universe.roboflow.com/josephs-workspace-gaago/safeweld-cb24e |
| Autor / licença | Josephs Workspace / **CC BY 4.0** |
| Imagens | **1.942** |
| Classes | 10: face_shield, non_welder, protective_suit, safety_glasses, welder, welding_apron, welding_boots, welding_gloves, **welding_helmet**, welding_jacket |
| Conteúdo | fotos da web de soldadores em ação (máscara abaixada e **levantada**), arco aceso, faíscas; algumas fotos de produto |
| Caixas `welding_helmet` | 785 em 727 imagens; mediana de 8,8% da área da imagem |
| Nosso fork | `leonardo-matte/safeweld-cb24e-j7zky`, versão **v1** (Auto-Orient apenas) |

## 2. Problemas encontrados e soluções

### 2.1 As versões públicas do Welding-PPE usam "Isolate Objects"
Esse pré-processamento transforma **cada caixa anotada em uma imagem separada** (um recorte só do objeto):
- o modelo aprenderia o EPI **ocupando a imagem inteira**, mas na câmera do posto ele é um objeto menor no meio da cena;
- o teste também seria de recortes, então as métricas sairiam otimistas;
- tudo foi esticado para 640×640, e a comparação entre `imgsz` 640 e 960 perderia o sentido.

**Solução:** *fork* (cópia gratuita) e geração de versões próprias só com *Auto-Orient*.

### 2.2 A divisão treino/validação/teste do Roboflow ficou desbalanceada
Na 1ª rodada (v1), o *Rebalance* acertou o total de imagens (70/20/10), mas deixou **2 máscaras no teste** e só 16 no treino.

**Solução:** a divisão é feita **no notebook** (seção 6b), por *estratificação iterativa* e com semente fixa. Se a versão do Roboflow tiver cópias aumentadas (caso do fork do Welding-PPE v1), o notebook mantém **uma única cópia** de cada foto original. Assim a mesma foto não aparece no treino e no teste. O blur e a exposição são aplicados no notebook, só no treino.

### 2.3 Poucas máscaras no Welding-PPE
43 caixas é muito pouco. **Solução:** acrescentar o **Welding Helmet** (1098 imagens), com a classe `Helmet` mapeada para `mascara`.

**Consequência a registrar no relatório:** a maioria das máscaras vem de **fotos de produto**, que são mais fáceis que a cena real. Por isso o notebook mostra as métricas **por fonte**, e o desempenho de verdade é medido nos testes de campo (Etapa 1.5).

### 2.4 Negativos
As imagens do Welding-PPE **sem máscara** (luvas, botas, aventais) entram como **exemplos negativos**: ensinam o modelo a não chamar uma luva ou um avental de máscara. Elas são limitadas a 30% do total (`FRACAO_MAX_NEGATIVOS`), para não dominarem o treino.

**Limitação:** se alguma dessas imagens tiver uma máscara **não anotada** na fonte original, ela vira um negativo errado. O notebook mostra amostras de negativos para conferência visual.

### 2.5 Rosto sem máscara detectado como máscara (encontrado no teste da webcam, 12/10/2026)
Com o modelo da rodada v2, o **rosto descoberto** foi detectado como máscara quando a cabeça estava **inclinada para
cima** (confiança 0,67) ou **de perfil** (0,88). Como a confiança é alta, subir o limiar não resolve.

**Causa:** os únicos negativos do treino eram fotos de luvas, botas e aventais. O modelo nunca viu uma cabeça de
pessoa **sem** máscara.

**Solução (rodada v3):** acrescentar **fotos de pessoas comuns sem máscara** como negativos (imagens sem caixa, que
não precisam de anotação):
- **COCO 2017** (validação): fotos do dia a dia com pessoas de frente, de perfil, inclinadas, de costas, de boné e de
  capacete de moto. O notebook baixa automaticamente e usa até 1.500 fotos em que a pessoa ocupa ≥ 5% da imagem
  (há 1.866 assim);
- **fotos próprias** (opcional): frames da webcam capturados com `ferramentas/capturar.py`.

E medir o efeito com uma métrica nova: a **taxa de falso positivo** nas imagens de teste sem máscara (por fonte).

| Item | Valor |
|---|---|
| Dataset | COCO 2017 – conjunto de validação (val2017), só imagens com pessoa |
| URLs | http://images.cocodataset.org/zips/val2017.zip (778 MB) e rótulos YOLO do Ultralytics (46 MB) |
| Licença | anotações CC BY 4.0; imagens com as licenças do Flickr indicadas pelo COCO |
| Citação | Lin, T.-Y. et al. *Microsoft COCO: Common Objects in Context.* ECCV 2014 |

### 2.6 Máscara vista de costas
Uma pessoa reconhece a máscara de solda também de costas (carcaça e cinta na cabeça). O modelo foi treinado quase só
com máscaras de frente, então ainda **não sabemos** se ele as reconhece de costas. Por isso a regra continua:
**de costas sem máscara detectada → INDETERMINADO** (RNF06). Se os testes com uma máscara real mostrarem que o modelo
detecta bem de costas, a regra pode virar uma opção no `config.yaml` (ex.: `acusar_de_costas: true`). Para melhorar
essa detecção, a próxima coleta de fotos (RF33) deve incluir **máscaras vistas de costas**, anotadas.

### 2.7 A máscara real em uso quase não fica verde (testes de campo, 13/10/2026)
Nos testes de campo (`docs/resultados_testes_campo.md`), a máscara abaixada só foi **confirmada** em 14% do tempo, e a
máscara levantada quase nunca foi detectada. **Causa:** a maioria das máscaras do treino vinha de fotos de produto.

**Solução (rodada v4):** acrescentar o *welder* e o *safeweld* (itens 1.3 e 1.4), com soldadores reais. Antes do
treino, os dois foram conferidos por amostragem visual (folhas de contato com as caixas desenhadas), e isto foi
encontrado:

| Problema | Exemplo | Decisão (célula 1 do notebook) |
|---|---|---|
| Fotos do COCO no *welder* com capacetes de esqui, de moto, de obra e máscaras de beisebol marcados como `Helm` (43 imagens) | `000000036539` (esquiador) | excluir **todas** as 705 fotos do COCO do *welder*; o COCO já entra como negativo (2.5) |
| Imagens geradas por IA | `DALL-E-2022-…` (28) | excluir |
| Rótulos errados isolados | respirador marcado como `Helm` (`images-147`); soldador de costas, de máscara, sem anotação (`pribadi-583`) | excluir |
| No *safeweld*, as fotos **sem** `welding_helmet` têm soldadores de máscara sem anotação, ou com a máscara marcada como `face_shield` | `1192805d-welding_302` | usar do *safeweld* **só as fotos com máscara anotada** (`so_positivas`) |
| Fotos em sequência no *welder* (mesma pessoa e mesmo fundo; quadros seguidos de vídeo) | `pribadi-…`, `H-220829_D31_…` | só no **treino** (`so_treino`); quase-cópias na validação ou no teste inflariam o mAP |
| Fotos de produto de avental (`00000053-2-…`), sem máscara | – | mantidas como negativos comuns |

Verificado em seguida (`Helm` fora do COCO): são máscaras de solda, incluindo os modelos de fibra laranja usados na
Indonésia, vistas de frente, de perfil, de costas e levantadas. `face_shield` (protetor facial de esmerilhamento) e
`safety_glasses` **não** viram máscara (D28).

### 2.8 Nenhuma imagem de treino pode vir dos vídeos de teste
Os vídeos de teste de campo são de bancos de imagem (Pexels). As fotos dos datasets também vêm da web, e um fotógrafo
pode publicar fotos e vídeos da mesma sessão. `ferramentas/conferir_vazamento.py` compara cada imagem dos datasets com
1 quadro por segundo de cada vídeo de teste, por **hash perceptual** (mesma imagem redimensionada ou recomprimida) e
por **semelhança de características** do YOLO (mesma cena, recortes). Os pares mais parecidos são conferidos a olho, e
as imagens da mesma cena entram em `EXCLUIR_PARECIDAS_COM_TESTE` (célula 1 do notebook).

**Resultado da conferência da v4 (13/10/2026):** 4.943 imagens (*welder* e *safeweld*, antes das exclusões) contra 550
quadros dos 21 vídeos de teste e do vídeo da webcam. Nenhum dos 45 pares mais parecidos é da mesma cena, e o único
par com hash próximo (distância 10) também é de cenas diferentes. **Nenhuma imagem precisou sair**, e
`EXCLUIR_PARECIDAS_COM_TESTE` ficou vazia.
Observação de método: sem centralizar os vetores, a semelhança ficou em ~0,98 para quase todos os pares (inútil para
ordenar); centralizados, a mediana é 0,57 e o máximo 0,93. Os datasets antigos (Welding-PPE, Welding Helmet) não
foram conferidos assim, porque não estão no computador; eles são anteriores aos vídeos de teste e têm outra origem.

### 2.9 Verde falso com a v4: negativos difíceis (rodada v5)
Nos testes de campo, a v4 confirmou mais vezes a máscara verdadeira, mas mostrou **verde falso** em quem estava sem
máscara: cabeça baixa no escuro (T10, 45% do tempo) e boné/gorro com óculos de maçarico (T22, 16%). Subir o limiar
de confiança não separa os casos (`docs/resultados_testes_campo.md`, seção 6). O modelo precisa ver essas situações
**sem** máscara.

**Solução:** 25 vídeos do Pexels (licença livre) de pessoas **sem máscara de solda** em oficinas, obras e
estaleiros, baixados pelo usuário e conferidos quadro a quadro:
- **1 quadro por segundo** (`ferramentas/capturar.py --intervalo-s 1`): 362 quadros, reduzidos para 1.280 px no
  pacote do Kaggle (`dados/epi_solda_negativos_v5.zip`, fora do git; lista dos vídeos no `FONTES.txt` do pacote);
- conferência de cada vídeo com folhas de contato e com as detecções da v4 desenhadas. A v4 confundia com máscara um
  **protetor facial transparente**, um **capacete de obra de costas**, um **lenço na cabeça**, um rosto de perfil
  numa oficina escura e **boné + óculos escuros com maçarico**: são os exemplos mais úteis;
- **6 vídeos recusados**: 3 eram cópias exatas de vídeos de teste (T10, T17, T18) e 3 eram da mesma série/sessão de
  vídeos de teste (mesma pessoa e lugar do T10; série 4941… dos testes T08, T19, T20, T25 e T26);
- `ferramentas/conferir_vazamento.py`: nenhum dos 362 quadros é da mesma cena de um vídeo de teste;
- no notebook, os quadros vão **só para o treino** (são sequências) e cada um ganha **2 cópias bem escuras** (20–45%
  do brilho, com ruído), para o caso "oficina escura". Validação e teste ficam iguais aos da v4, então as métricas
  das duas rodadas são comparáveis. É a única mudança em relação à v4.

Vídeos usados (https://www.pexels.com/video/ID/): 2865276, 3976811, 3977979, 6263171, 6263483, 6964237, 7165971,
7519299, 8064125, 9480718, 12724977, 12748637, 12938242, 13398903, 13530494, 13752039, 14514794, 14649305,
15342548, 15342588, 15477233, 15694207, 16313183, 17014398 e um vídeo do Pexels salvo sem o número
(`uhd_30fps.mp4`, operário com vergalhão e capacete amarelo).

## 3. Verificação da classe `helmet` do Welding-PPE

Conferi as amostras com o filtro `class = helmet` (imagens `img136.jpg` a `img144.jpg` e vizinhas). Em todas aparece uma pessoa usando uma **máscara/capacete de solda metálico com visor escuro** cobrindo o rosto. Não são capacetes de segurança (de obra). **Decisão:** `helmet` → `mascara`.

## 4. Mapeamento de classes

| Classe original | Classe interna | Na Fase 1 |
|---|---|---|
| Welding Mask (Welding-PPE) | `mascara` | **usada** |
| helmet (Welding-PPE) | `mascara` | **usada** |
| Helmet (Welding Helmet) | `mascara` | **usada** |
| Helm (welder) | `mascara` | **usada** (fora das fotos do COCO, excluídas) |
| welding_helmet (safeweld) | `mascara` | **usada** |
| Orang, welder, non_welder, Tanpa_\*, face_shield, safety_glasses | – | removidas (não são máscara de solda) |
| Welding Gloves, welding-glove | `luvas` | removida (trabalho futuro) |
| Welding Apron, apron | `avental` | removida (trabalho futuro) |
| Welding Coverall | `macacao` | removida (trabalho futuro) |
| Safety Shoes, welding-shose | `calcado` | removida (trabalho futuro) |

Para treinar outros EPIs no futuro, basta acrescentar o nome em `CLASSES_MODELO` (célula 1 do notebook).

## 5. Rodadas de treino

| Rodada | Classes | Dados | Divisão (treino / val / teste) | Resultado |
|---|---|---|---|---|
| v1 | 5 | Welding-PPE (fork v1) | 561 / 160 / 80 (Roboflow) | descartada, ver `docs/resultados_treino/README.md` |
| v2 | 1 (`mascara`) | Welding-PPE (fork v1) + Welding Helmet (fork v1) | 1.013 / 290 / 145 (notebook) | `docs/resultados_treino/v2/` – mAP@0.5 = 0,913 (`yolo26n_640`) |
| v3 | 1 (`mascara`) | v2 + **COCO pessoas** (negativos) | 2.063 / 590 / 295 (notebook) | `docs/resultados_treino/v3/` – mAP@0.5 = 0,855 (`yolov8n_640`); falso positivo em pessoas 2,1% |
| v4 | 1 (`mascara`) | v3 + **welder** + **safeweld** (soldadores reais, conferidos: seção 2.7) | 4.316 / 909 / 455 (notebook; sequências só no treino) | `docs/resultados_treino/v4/` – mAP@0.5 = 0,946; falso positivo em pessoas 0,6% |
| v5 | 1 (`mascara`) | v4 + **362 quadros sem máscara** de vídeos do Pexels (+2 cópias escuras de cada), só no treino (seção 2.9) | treino +362; validação e teste iguais aos da v4 | em andamento |

## 6. Passo a passo para a rodada v2 (VOCÊ)

### 6.1 Fork do Welding Helmet (Roboflow)
1. Abra https://universe.roboflow.com/utp-jtbn5/welding-helmet (logado na sua conta) e clique em **Fork Dataset**. Escolha o seu workspace e aguarde a cópia das 1098 imagens.
2. No projeto copiado, abra **Versions → Create New Version**:
   - **Source Images:** confira 1.098 imagens e 1 classe (2 imagens sem anotação viram negativos) → **Continue**;
   - **Train/Test Split:** deixe como estiver (80/10/10), sem *Rebalance*, porque o notebook refaz a divisão → **Continue**;
   - **Preprocessing:** clique em **Edit**, mantenha só **Auto-Orient** e remova **Resize** (lixeira/✕) → **Continue**;
   - **Augmentation:** **nenhuma**. Se houver alguma, remova → **Continue**;
   - **Create:** clique em **Create**.
3. Clique em **Download Dataset → YOLOv8 → Show download code** e anote o texto de `project("...")` e o número de `version(...)`. **Não copie a `api_key`.**

### 6.2 Colab
1. Baixe o notebook atualizado (`notebooks/colab/treinamento_epi_solda.ipynb`, no GitHub) e envie para o Colab (**File → Upload notebook**).
2. **Runtime → Change runtime type → T4 GPU → Save**.
3. 🔑 **Secrets:** confira se `ROBOFLOW_API_KEY` está lá, com **acesso ao notebook** ativado.
4. Na célula **1. Configuração**, na linha do **Welding Helmet**, troque `PREENCHER` pelo nome do projeto e ajuste `versao`. A linha do Welding-PPE já está preenchida.
5. **Runtime → Run all** e autorize o Google Drive (só o item "See, edit, create, and delete all of your Google Drive files").
6. Os treinos ficam em `Meu Drive/epi_solda/v2/treinos/`. Se o Colab desconectar, rode **Run all** de novo e ele continua de onde parou.
7. No fim, o navegador baixa `resultado_treino_v2.zip`. Copie `epi_solda_best.pt` para `models/` (substituindo o anterior) e o resto para `docs/resultados_treino/v2/`.

### 6.3 Rodada v3 (negativos de pessoas sem máscara)
O notebook já vem configurado para a v3 (`RODADA = "v3"`, COCO ativado, os dois forks preenchidos, só o `yolov8n_640`, que teve menos falsos positivos).
Nada muda no Roboflow. Opcionalmente, antes de rodar:
1. **Medir o "antes"** com um vídeo de teste sem máscara:
   `python ferramentas/capturar.py --saida testes_campo/teste_sem_mascara.mp4 --duracao-s 60` e depois
   `python -m src.run --fonte testes_campo/teste_sem_mascara.mp4 --sem-janela`. Anote a linha `mascara (...)` do
   resumo: o % de CONFORME é a taxa de falso positivo.
2. **Fotos próprias como negativos** (em outra sessão, diferente do vídeo de teste):
   `python ferramentas/capturar.py --saida testes_campo/negativos_webcam/sessao1`, suba a pasta como Dataset no
   Kaggle (ou no Google Drive, no Colab) e coloque o caminho em `PASTAS_NEGATIVOS` na célula 1.

### 6.4 Alternativa: Kaggle
Se a cota de GPU do Colab acabar, o mesmo treino pode continuar no Kaggle a partir do progresso salvo no Drive:
`notebooks/kaggle/treinamento_epi_solda_kaggle.ipynb`, com o passo a passo em `notebooks/kaggle/LEIA-ME.md`.

### 6.5 Rodada v4 (soldadores reais)
1. **Roboflow (feito em 13/10/2026):** fork do *welder* e do *safeweld*, versão v1 de cada um só com *Auto-Orient*,
   sem augmentation, como em 6.1. Os nomes dos projetos já estão na célula 1 do notebook.
2. **Conferência local (feita):** os zips da versão (formato YOLOv8) ficam em `dados/roboflow_v4/` (fora do git) para
   as folhas de contato e para `python ferramentas/conferir_vazamento.py --datasets dados/roboflow_v4/welder
   dados/roboflow_v4/safeweld`.
3. **Treino:** no Kaggle, num notebook novo e sem *Input*: passo a passo em `notebooks/kaggle/LEIA-ME.md`, seção
   "Rodada v4".
4. **Depois do treino:** guardar o modelo da v3 como `models/epi_solda_best_v3.pt`, instalar o da v4 e repetir os
   28 trechos de teste de campo com `ferramentas/avaliar_testes.py --todos`, comparando v3 com v4.

## 7. Atribuição (para o README e o relatório)

> Este projeto utiliza os datasets "Welding-PPE" (Welding PPE, Roboflow Universe, 2023,
> https://universe.roboflow.com/welding-ppe/welding-ppe) e "Welding Helmet" (UTP, Roboflow Universe, 2025,
> https://universe.roboflow.com/utp-jtbn5/welding-helmet), ambos sob licença CC BY 4.0. As classes foram
> remapeadas para `mascara` e novas versões foram geradas sem os pré-processamentos "Isolate Objects" e
> "Stretch", e sem as augmentations originais.
>
> A partir da rodada v4, também utiliza os datasets "welder" (ESports, Roboflow Universe, 2025,
> https://universe.roboflow.com/esports/welder) e "safeweld" (Josephs Workspace, Roboflow Universe, 2026,
> https://universe.roboflow.com/josephs-workspace-gaago/safeweld-cb24e), ambos sob licença CC BY 4.0. As classes
> `Helm` e `welding_helmet` foram remapeadas para `mascara`, as demais foram removidas, e parte das imagens foi
> excluída após conferência visual (fotos do COCO com rótulos errados, imagens geradas por IA e, no safeweld,
> imagens sem a máscara anotada).

```bibtex
@misc{ welding-ppe_dataset,
  title = { Welding-PPE Dataset },
  type = { Open Source Dataset },
  author = { Welding PPE },
  howpublished = { \url{ https://universe.roboflow.com/welding-ppe/welding-ppe } },
  url = { https://universe.roboflow.com/welding-ppe/welding-ppe },
  journal = { Roboflow Universe },
  publisher = { Roboflow },
  year = { 2023 },
  month = { jun },
  note = { visited on 2026-10-10 },
}

@misc{ welding-helmet_dataset,
  title = { Welding Helmet Dataset },
  type = { Open Source Dataset },
  author = { UTP },
  howpublished = { \url{ https://universe.roboflow.com/utp-jtbn5/welding-helmet } },
  url = { https://universe.roboflow.com/utp-jtbn5/welding-helmet },
  journal = { Roboflow Universe },
  publisher = { Roboflow },
  year = { 2025 },
  month = { apr },
  note = { visited on 2026-10-10 },
}

@misc{ welder_dataset,
  title = { welder Dataset },
  type = { Open Source Dataset },
  author = { ESports },
  howpublished = { \url{ https://universe.roboflow.com/esports/welder } },
  url = { https://universe.roboflow.com/esports/welder },
  journal = { Roboflow Universe },
  publisher = { Roboflow },
  year = { 2025 },
  month = { jul },
  note = { visited on 2026-10-13 },
}

@misc{ safeweld-cb24e_dataset,
  title = { safeweld Dataset },
  type = { Open Source Dataset },
  author = { Josephs Workspace },
  howpublished = { \url{ https://universe.roboflow.com/josephs-workspace-gaago/safeweld-cb24e } },
  url = { https://universe.roboflow.com/josephs-workspace-gaago/safeweld-cb24e },
  journal = { Roboflow Universe },
  publisher = { Roboflow },
  year = { 2026 },
  month = { jul },
  note = { visited on 2026-10-13 },
}
```

## 8. Fine-tuning com fotos do posto real (RF33) – planejamento

Fazer **depois** da rodada v2, se as métricas ou os testes de campo indicarem necessidade, e só com autorização da empresa e dos trabalhadores fotografados.

1. **Coleta (150 a 300 imagens no mínimo)**, com a câmera na posição definitiva:
   - máscara **abaixada**, máscara **levantada** (sobre a cabeça) e **sem máscara**;
   - arco aceso, fumos e faíscas;
   - frente, perfil e costas, a 2, 4 e 6 m;
   - **negativos:** boné, óculos de sol, protetor auricular, capacete de segurança. Esses objetos ficam **sem caixa**, para o modelo aprender que não são máscara de solda;
   - dica: extraia 1 quadro a cada 2–3 s de vídeos curtos. Quadros seguidos são quase iguais.
2. **Anotação no Roboflow:** crie um projeto (ou use um dos forks) e anote com o nome **`mascara`**. Revise caixa por caixa.
3. **Merge:** acrescente o projeto novo como mais uma fonte em `FONTES` (célula 1 do notebook). A divisão estratificada garante fotos do posto real também no **teste**. Use `so_treino` para os quadros de um mesmo vídeo que forem muito parecidos.
4. **Retreino:** nova rodada (ex.: `RODADA = "v5"`), usando como modelo base o `epi_solda_best.pt` anterior (continua o aprendizado) ou de novo o `yolov8n.pt`. Compare os dois.
5. **Comparação:** avalie o modelo antigo e o novo **no mesmo conjunto de teste com fotos do posto real** e registre o antes x depois para o relatório.
