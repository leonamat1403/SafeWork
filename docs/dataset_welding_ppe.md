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

## 3. Verificação da classe `helmet` do Welding-PPE

Conferi as amostras com o filtro `class = helmet` (imagens `img136.jpg` a `img144.jpg` e vizinhas). Em todas aparece uma pessoa usando uma **máscara/capacete de solda metálico com visor escuro** cobrindo o rosto. Não são capacetes de segurança (de obra). **Decisão:** `helmet` → `mascara`.

## 4. Mapeamento de classes

| Classe original | Classe interna | Na Fase 1 |
|---|---|---|
| Welding Mask (Welding-PPE) | `mascara` | **usada** |
| helmet (Welding-PPE) | `mascara` | **usada** |
| Helmet (Welding Helmet) | `mascara` | **usada** |
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

## 7. Atribuição (para o README e o relatório)

> Este projeto utiliza os datasets "Welding-PPE" (Welding PPE, Roboflow Universe, 2023,
> https://universe.roboflow.com/welding-ppe/welding-ppe) e "Welding Helmet" (UTP, Roboflow Universe, 2025,
> https://universe.roboflow.com/utp-jtbn5/welding-helmet), ambos sob licença CC BY 4.0. As classes foram
> remapeadas para `mascara` e novas versões foram geradas sem os pré-processamentos "Isolate Objects" e
> "Stretch", e sem as augmentations originais.

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
```

## 8. Fine-tuning com fotos do posto da Marcopolo (RF33) – planejamento

Fazer **depois** da rodada v2, se as métricas ou os testes de campo indicarem necessidade, e só com autorização da empresa e dos trabalhadores fotografados.

1. **Coleta (150 a 300 imagens no mínimo)**, com a câmera na posição definitiva:
   - máscara **abaixada**, máscara **levantada** (sobre a cabeça) e **sem máscara**;
   - arco aceso, fumos e faíscas;
   - frente, perfil e costas, a 2, 4 e 6 m;
   - **negativos:** boné, óculos de sol, protetor auricular, capacete de segurança. Esses objetos ficam **sem caixa**, para o modelo aprender que não são máscara de solda;
   - dica: extraia 1 quadro a cada 2–3 s de vídeos curtos. Quadros seguidos são quase iguais.
2. **Anotação no Roboflow:** crie um projeto (ou use um dos forks) e anote com o nome **`mascara`**. Revise caixa por caixa.
3. **Merge:** acrescente o projeto novo como uma terceira fonte em `FONTES` (célula 1 do notebook). A divisão estratificada garante fotos da Marcopolo também no **teste**.
4. **Retreino:** nova rodada (`RODADA = "v3"`), usando como modelo base o `epi_solda_best.pt` anterior (continua o aprendizado) ou de novo o `yolov8n.pt`. Compare os dois.
5. **Comparação:** avalie o modelo antigo e o novo **no mesmo conjunto de teste com fotos da Marcopolo** e registre o antes x depois para o relatório.
