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
