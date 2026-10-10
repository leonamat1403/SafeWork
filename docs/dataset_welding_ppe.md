# Dataset Welding-PPE – verificação e preparação (Etapa 1.2)

## 1. Ficha do dataset (conferida em 10/10/2026 na página pública)

| Item | Valor | Fonte |
|---|---|---|
| Nome | Welding-PPE | https://universe.roboflow.com/welding-ppe/welding-ppe |
| Autor / workspace | Welding PPE / `welding-ppe` | página do projeto |
| Licença | CC BY 4.0 (exige atribuição) | página do projeto |
| Imagens de origem | **801** | aba *Images* |
| Versões publicadas | 3 (v1, v2, v3) – a v3 é a mais recente, de 11/06/2023 | aba *Dataset* |
| Classes | 9: helmet, apron, Safety Shoes, Welding Apron, Welding Coverall, Welding Gloves, Welding Mask, welding-glove, welding-shose | página do projeto |
| Modelo de referência | `welding-ppe/3` (Roboflow 2.0 Object Detection, só via API em nuvem) | página do projeto |

### Versões publicadas

| Versão | Imagens | Split treino/val/teste | Pré-processamento | Augmentations |
|---|---|---|---|---|
| v1 | 153 | 105 / 27 / 21 | Auto-Orient, **Isolate Objects**, Stretch 640×640 | nenhuma |
| v2 | 3077 | 2778 / 170 / 129 | Auto-Orient, **Isolate Objects**, Stretch 640×640 | 3×: blur até 2,5 px, exposição ±25% na caixa |
| v3 | 2413 | 1782 / 244 / 387 | Auto-Orient, **Isolate Objects**, Stretch 640×640 | 3×: blur até 2,5 px, exposição ±25% na caixa |

### Campos para você preencher (após gerar a versão no seu fork)

| Item | Valor |
|---|---|
| Workspace do fork | `__________` (copiar do código de download, ver seção 6) |
| Projeto no fork | Welding-PPE (slug: `__________`) |
| Versão v1 (descartada) | 10/10/2026 14:27 – Auto-Orient; Exposure ±25% + Blur 2,5 px, 2×; split 561/160/80. **Descartada pela divisão desbalanceada (item 2b)** |
| Versão v2 (usada) | `v2` – Auto-Orient apenas, **sem augmentation**, com as imagens clonadas do "Welding Helmet" (item 2c) |
| Imagens clonadas do "Welding Helmet" | `____` |
| Divisão final (feita no notebook, seção 6b) | treino `____` / validação `____` / teste `____` imagens originais |
| Instâncias por classe | ver `balanceamento_classes.csv` gerado pelo notebook |

> Observação: grande parte das imagens são **fotos de produto** (um único EPI sobre fundo neutro). Isso faz parte do dataset original, não é efeito de recorte, e reforça a necessidade do fine-tuning com fotos reais (RF33).

### Instâncias por classe na v1 (só Welding-PPE, após o remapeamento)

As contagens do treino foram divididas por 2 para descontar as cópias da augmentation.

| Classe | Treino | Validação | Teste | Total (originais) | Área média da caixa |
|---|---|---|---|---|---|
| luvas | 435 | 37 | 46 | **518** | 25% da imagem |
| calcado | 171 | 98 | 63 | **332** | 29% |
| avental | 232 | 55 | 13 | **300** | 24% |
| mascara | 16 | 25 | 2 | **43** | 17% |
| macacao | 1 | 29 | 2 | **32** | 50% |

## 2. Problema encontrado: todas as versões públicas usam "Isolate Objects"

"Isolate Objects" transforma **cada caixa anotada em uma imagem separada** (um recorte só do objeto).
Por isso a v3 tem 2413 imagens geradas a partir das 801 originais. Para o nosso sistema isso inviabiliza as versões públicas:

1. **O domínio fica errado.** O modelo aprende uma luva ou uma máscara **ocupando a imagem inteira**. Na câmera do posto elas são objetos pequenos no meio da cena, junto com a pessoa, a bancada e a peça.
2. **As métricas ficam enganosas.** O conjunto de teste também é de recortes, então o mAP sairia alto, mas não representaria o uso real.
3. **O `imgsz` 960 não ajudaria.** Todas as versões foram esticadas para 640×640, e a comparação 640 x 960 (RF16/RF32) perderia o sentido.
4. **O modelo de referência do Roboflow (`welding-ppe/3`) foi treinado nesses recortes.** Por isso ele não serve como comparação justa, além de só rodar em nuvem. **Decisão:** não usaremos esse modelo como referência e registraremos isso como limitação.

**Solução:** fazer um *fork* (cópia gratuita para a sua conta) e gerar uma versão nova a partir das 801 imagens **originais**. O notebook verifica isso automaticamente e para com um erro se receber uma versão de recortes.

## 2b. Problema encontrado: a divisão do Roboflow ficou desbalanceada por classe

Na v1, o *Rebalance* acertou o total de imagens (70/20/10), mas não por classe:
- **macacão:** 29 das 32 caixas ficaram na validação e **só 1 no treino**, então o modelo não teria como aprender a classe;
- **máscara:** só 16 caixas no treino e **2 no teste**. Um mAP calculado com 2 exemplos não tem valor estatístico.

**Solução:** a divisão passou a ser feita **no notebook** (seção 6b), por *estratificação iterativa*. As imagens com as classes mais raras são distribuídas primeiro, para que **cada classe** fique perto de 70/20/10, sempre com a mesma semente. Por isso a versão do Roboflow agora é gerada **sem augmentation**: se ela viesse com cópias aumentadas, uma cópia poderia cair no treino e outra no teste (vazamento). O blur e a exposição passaram a ser aplicados no notebook, só no treino.

## 2c. Problema encontrado: poucas máscaras de solda

Mesmo com a divisão corrigida, **43 caixas de máscara** é muito pouco para a classe mais importante do sistema, que tem mínimo de 0,60 de mAP@0.5. **Solução:** clonar imagens do dataset **"Welding Helmet"** (*UTP*, CC BY 4.0, 1098 imagens, classe única `Helmet` = máscara de solda) para dentro do fork. O notebook já mapeia `Helmet` para `mascara`.

| Item | Valor |
|---|---|
| URL | https://universe.roboflow.com/utp-jtbn5/welding-helmet |
| Licença | CC BY 4.0 |
| Imagens | 1098 (a versão publicada tem rotações de 90°, por isso clonamos as imagens originais e não baixamos a versão) |
| Conteúdo | maioria de fotos de produto (máscara sozinha), com algumas fotos de uso real |

Clonamos **~300 imagens** e não as 1098, para a máscara não dominar o dataset com fotos de produto. Uma consequência a registrar no relatório: o mAP de `mascara` no teste vai refletir em boa parte fotos de produto, que são mais fáceis que a cena real. O teste de campo (Etapa 1.5) é que mede o desempenho de verdade.

**Macacão continua pequeno (32 caixas).** No sistema, ele conta junto com o avental como "proteção do corpo", e a meta é avaliada para a combinação dos dois. A opção `aceitar_macacao=false` fica funcional, mas com baixa confiabilidade até o fine-tuning (RF33). Isso fica registrado como **limitação**.

## 3. Verificação da classe `helmet`

Conferi as amostras com o filtro `class = helmet` (imagens `img136.jpg` a `img144.jpg` e vizinhas). Em todas aparece uma pessoa usando um **capacete/máscara de solda metálico com visor escuro** cobrindo o rosto. Não são capacetes de segurança (de obra).

**Decisão:** `helmet` → `mascara`.

Consequências:
- a classe interna `capacete` (capacete de segurança) **não existe** neste dataset. O EPI opcional "capacete" fica indisponível até um fine-tuning com fotos anotadas (RF33). Se ele for ativado no `config.yaml`, o sistema vai avisar que o modelo não tem essa classe;
- `Welding Mask` reúne principalmente fotos da internet (cenas de soldagem com faíscas), e `helmet` reúne uma série de fotos em estúdio com fundo neutro. Juntas, elas dão mais variedade à classe `mascara`.

**Observação de domínio:** parte das imagens são fotos de produto e de estúdio (fundo cinza/branco, pessoa posando). Isso é bem diferente de um posto de solda real, o que reforça a necessidade do fine-tuning com fotos da Marcopolo (RF33).

## 4. Mapeamento de classes (9 → 5)

| Classe original | Classe interna | Motivo |
|---|---|---|
| Welding Mask | `mascara` | – |
| helmet | `mascara` | verificado visualmente (item 3) |
| Welding Gloves, welding-glove | `luvas` | duplicadas |
| Welding Apron, apron | `avental` | duplicadas |
| Welding Coverall | `macacao` | separado do avental para permitir `aceitar_macacao=false` (plano, item 5.3) |
| Safety Shoes, welding-shose | `calcado` | duplicadas ("shose" é erro de digitação) |

Ordem dos ids no modelo treinado: `0 mascara, 1 luvas, 2 avental, 3 macacao, 4 calcado`.
O remapeamento é feito **no notebook**, o que deixa o processo documentado e repetível. Remapear também no Roboflow é opcional, e o notebook aceita as duas formas.

## 5. Passo a passo: fork e geração da versão (VOCÊ)

1. Crie uma conta gratuita em https://app.roboflow.com (pode entrar com a conta Google).
2. Abra https://universe.roboflow.com/welding-ppe/welding-ppe e clique em **Fork Dataset**. Escolha o seu workspace e aguarde a cópia das 801 imagens.
3. **Clone ~300 imagens de máscaras de solda** (item 2c), já logado no Roboflow:
   - abra https://universe.roboflow.com/utp-jtbn5/welding-helmet → aba **Images**;
   - marque a caixa **"Select all"** (seleciona a página inteira) e repita nas próximas páginas até ~300 imagens;
   - clique em **Clone Images** → escolha o seu workspace e o projeto **Welding-PPE** → confirme. As anotações vêm junto, com a classe `Helmet`.
4. No projeto copiado, abra **Versions → Create New Version** e configure:
   - **Train/Test Split:** pode deixar como estiver, porque o notebook refaz a divisão;
   - **Preprocessing:** mantenha só **Auto-Orient**. **Remova "Resize"** e **não** adicione "Isolate Objects";
   - **Augmentations:** **nenhuma**. Se aparecer alguma, remova; o notebook aplica blur e exposição só no treino;
   - clique em **Create** / **Generate**.
5. Anote o **nome do workspace** e o do **projeto** (aparecem no código de download, ver seção 6) e o **número da versão** (v2).
6. Copie a chave da API em **Settings → API Keys → Private API Key**. Não envie a chave para mim nem a coloque em arquivos do projeto.

> Se o plano gratuito pedir para o projeto ser público, tudo bem: é um fork de um dataset que já é público (CC BY 4.0).

## 6. Passo a passo: rodar o notebook no Colab (VOCÊ)

1. Acesse https://colab.research.google.com → **Arquivo → Fazer upload de notebook** → escolha `notebooks/treinamento_epi_solda.ipynb`.
2. Menu **Ambiente de execução → Alterar o tipo de ambiente de execução → T4 GPU**.
3. Na barra lateral, clique no ícone 🔑 **Secrets** → *Adicionar novo secret*:
   - Nome: `ROBOFLOW_API_KEY`
   - Valor: a sua chave
   - Ative a chave "Acesso ao notebook".
4. Na célula **1. Configuração**, preencha `WORKSPACE` e `VERSAO`.
5. **Ambiente de execução → Executar tudo**. Na montagem do Google Drive, autorize o acesso.
6. Tempo estimado (não medido): de 1 a 3 horas para os 4 experimentos na T4. Se o Colab desconectar, rode **Executar tudo** de novo: os treinos continuam de onde pararam (ficam salvos em `Meu Drive/epi_solda/`).
7. No fim, o navegador baixa `resultado_treino.zip`. Copie `epi_solda_best.pt` para `models/` e o restante para `docs/resultados_treino/`. Depois me avise para eu analisar.

## 7. Atribuição (para o README e o relatório)

> Este projeto utiliza o dataset "Welding-PPE" (Welding PPE, Roboflow Universe, 2023), disponível em
> https://universe.roboflow.com/welding-ppe/welding-ppe sob licença CC BY 4.0. As classes foram
> remapeadas (9 → 5) e uma nova versão foi gerada sem o pré-processamento "Isolate Objects".
> Foram acrescentadas imagens do dataset "Welding Helmet" (UTP, Roboflow Universe, 2025), disponível em
> https://universe.roboflow.com/utp-jtbn5/welding-helmet sob licença CC BY 4.0, com a classe `Helmet`
> mapeada para `mascara`.

```bibtex
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
```

## 8. Fine-tuning com fotos do posto da Marcopolo (RF33) – planejamento

Fazer **depois** do primeiro treino, se as métricas ou os testes de campo indicarem necessidade (e só com autorização da empresa e dos trabalhadores fotografados).

1. **Coleta (150 a 300 imagens no mínimo)**, com a câmera na posição definitiva, cobrindo:
   - máscara abaixada, máscara levantada e sem máscara;
   - luvas de raspa, luvas comuns e mãos sem luva;
   - avental, macacão e roupa comum;
   - arco aceso, fumos e faíscas;
   - frente, perfil e costas, a 2, 4 e 6 m;
   - **negativos:** boné, óculos de sol, jaqueta comum, luva comum. Esses objetos ficam **sem caixa**, para o modelo aprender que não são EPI.
   - Dica: extraia 1 quadro a cada 2–3 s de vídeos curtos. Quadros seguidos são quase iguais e não acrescentam informação.
2. **Anotação no Roboflow:** suba as imagens **no mesmo projeto do fork**, use **exatamente** os nomes internos (`mascara, luvas, avental, macacao, calcado` e, se o posto exigir, `capacete`) e anote com *Annotate* (o *Label Assist* do modelo do fork pode pré-anotar). Revise caixa por caixa.
3. **Merge:** gere uma nova versão com as mesmas configurações do item 5. As fotos novas se juntam às 801 do Welding-PPE, e o rebalanceamento garante fotos da Marcopolo também no conjunto de **teste**.
4. **Retreino:** no notebook, mude `VERSAO` e, em `EXPERIMENTOS`, use como modelo base o `epi_solda_best.pt` anterior (continua o aprendizado) ou de novo o `yolov8n.pt`. Compare os dois.
5. **Comparação:** avalie o modelo antigo e o novo **no mesmo conjunto de teste com fotos da Marcopolo** e registre o antes x depois para o relatório.
