# Treinamento no Kaggle

`treinamento_epi_solda_kaggle.ipynb` faz **o mesmo** que o notebook do Colab (`../colab/`): mesmos dados, mesma
divisão e mesmos experimentos. Muda só o ambiente:

| | Colab | Kaggle |
|---|---|---|
| Onde ficam os treinos | Google Drive (`Meu Drive/epi_solda/v2/treinos`) | `/kaggle/working/epi_solda/v2/treinos` → aba **Output** da versão |
| Chave do Roboflow | 🔑 Secrets do Colab | *Add-ons → Secrets* |
| Rodar com o navegador fechado | não | sim (*Save Version → Save & Run All*) |
| Cota de GPU | não divulgada | ~30 h por semana (visível no painel) |
| Continuar de onde parou | automático, pelo Drive | anexando a pasta `treinos` como *Input* (seção 2b do notebook) |

## Rodada v4 (soldadores reais): treino novo, do zero

A v4 não continua nenhum treino anterior. Use um notebook **novo** no Kaggle, sem nada anexado em *Input*.
Se reaproveitar o notebook da v3, a seção 2b ignora a saída da v3, mas é mais simples começar do zero.

1. Baixe `notebooks/kaggle/treinamento_epi_solda_kaggle.ipynb` do GitHub (versão da v4: a célula 1 mostra
   `RODADA = "v4"` e as fontes `welder-hqw5c` e `safeweld-cb24e-j7zky`).
2. https://www.kaggle.com/code → **+ New Notebook** → **File → Import Notebook** → escolha o arquivo.
3. **Session options:** **Accelerator: GPU T4 x2** e **Internet: On**.
4. **Add-ons → Secrets:** confira se `ROBOFLOW_API_KEY` está com a caixa **marcada** para este notebook. A chave é a
   mesma da v3; você não precisa digitá-la de novo, só anexar.
5. **Não** adicione nada em *Input*.
6. **Save Version → Save & Run All (Commit) → Save**. Pode fechar o navegador. O treino tem cerca de **o dobro de
   imagens da v3** (~4.300 originais, ~8.600 com augmentation), então deve levar cerca do dobro do tempo da v3.
7. Para acompanhar: **Your Work** → o notebook → a versão em execução → **Logs**. Na seção 6 devem aparecer as linhas
   `imagens excluídas: ...` do *welder* e do *safeweld*.
8. No fim, aba **Output** da versão → baixe **`resultado_treino_v4.zip`** e coloque o zip em
   `Z:\Documentos\SafeWork\testes_campo\` (eu descompacto e organizo, preservando o modelo da v3).

## Passo a passo: continuar no Kaggle o treino que parou no Colab

### A. Pegar o progresso no Google Drive
1. Abra o Google Drive **da conta onde o treino estava rodando**.
2. Entre em `Meu Drive/epi_solda/v2/`.
3. Clique com o botão direito na pasta **`treinos`** → **Fazer download**. O Drive gera um `.zip`. **Não precisa descompactar.**

### B. Conta no Kaggle (só na primeira vez)
1. Acesse https://www.kaggle.com e crie a conta (pode ser com a conta Google).
2. Clique na sua foto (canto superior direito) → **Settings** → **Phone Verification** e verifique o celular.
   Sem isso, as opções de **GPU** e **Internet** ficam bloqueadas.

### C. Subir o progresso como Dataset
1. Acesse https://www.kaggle.com/datasets → **+ New Dataset**.
2. Arraste o `.zip` da pasta `treinos`.
3. Título: `epi-solda-treinos-v2`. Visibilidade: **Private**.
4. Clique em **Create** e aguarde o processamento (alguns minutos).

### D. Criar o notebook
1. Baixe `notebooks/kaggle/treinamento_epi_solda_kaggle.ipynb` do GitHub.
2. Acesse https://www.kaggle.com/code → **+ New Notebook** → menu **File → Import Notebook** → escolha o arquivo.
3. No painel da direita (**Session options**):
   - **Accelerator:** **GPU T4 x2**. Não use a P100, que pode não ser compatível com a versão atual do PyTorch;
   - **Internet:** **On**. Se estiver cinza, falta a verificação do celular (passo B.2).
4. Menu **Add-ons → Secrets → Add Secret**:
   - Label: `ROBOFLOW_API_KEY`;
   - Value: a sua chave do Roboflow;
   - salve e confira se a caixa ao lado do secret está **marcada** (anexado ao notebook).
5. No painel da direita, **Input → + Add Input** → aba **Your Work** / **Datasets** → `epi-solda-treinos-v2` → clique no **+**.
6. Na célula **1. Configuração**, preencha a linha do **Welding Helmet** com o mesmo `projeto` e `versao` que você usou no Colab.

### E. Conferir antes de rodar tudo (2 minutos)
1. Rode só as primeiras células, uma a uma (▶), até a seção **2b**.
2. A saída da 2b deve listar os experimentos, por exemplo:
   ```
   Experimentos importados:
      yolov8n_640 (concluído)  <- /kaggle/input/...
      yolov8n_960 (concluído)  <- /kaggle/input/...
      yolov8s_640 (a retomar)  <- /kaggle/input/...
   ```
   Se aparecer `Nenhum progresso anterior encontrado`, o Dataset não foi anexado (passo D.5).
3. Pare a sessão (botão ■ / **Stop session**) para não gastar cota à toa.

> ⚠️ **Não treine na sessão interativa** (o "Draft Session" do topo, rodando célula por célula ou com *Run All*).
> Nela, os arquivos de `/kaggle/working` são temporários e **somem se a sessão reiniciar** (por inatividade ou por
> tempo): isso aconteceu na rodada v3, e o treino precisou ser refeito. Use a sessão interativa só para conferências
> rápidas (passo E) e treine sempre com **Save & Run All (Commit)**.

### F. Rodar com o navegador fechado
1. Canto superior direito: **Save Version** → **Save & Run All (Commit)** → **Save**.
2. Pode fechar o navegador. Para acompanhar: https://www.kaggle.com/code → **Your Work** → o notebook → a versão em execução → **Logs**.
3. Na saída do treino deve aparecer `já concluído, pulando.` para os experimentos prontos e `retomando do último checkpoint...` para o que parou no meio.

### G. Resultado
1. Na página da versão concluída, abra a aba **Output** e baixe **`resultado_treino_v2.zip`**.
2. Copie `epi_solda_best.pt` para `models/` e o resto para `docs/resultados_treino/v2/`.

### Se a execução no Kaggle também parar no meio
Crie uma nova versão com **Input → + Add Input → Notebook Output** da versão anterior. A seção 2b importa os
experimentos dessa saída do mesmo jeito.
