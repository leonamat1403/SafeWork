# Verificador de EPIs de Solda com Visão Computacional

Projeto extensionista dos cursos de Análise e Desenvolvimento de Sistemas, Ciência da Computação e Engenharia de
Software da **FSG** (Caxias do Sul – RS). Público-alvo: empresas com **postos fixos de solda** ou setores de solda pequenos,
com a câmera a curta distância (2 a 6 m; testado até 4 m).

**Equipe:** Gabriel Gutierrez, Gabriel de Moura Jank, Gustavo Chimello e Leonardo Mattê.  
**Disciplina:** Processamento de Imagens (2026/2), professor Vinícius Colombo Sonda.

Uma câmera instalada no posto de solda verifica se o soldador está usando a **máscara de solda** e registra as
faltas (NR-6), com as imagens **sempre borradas** e sem identificar ninguém.

| Fase | Situação | Documento |
|---|---|---|
| Fase 1 – validação da detecção (linha de comando) | ✅ validada para a máscara de solda: mAP 0,945, recall de campo 82%, 0% de falsos positivos, 12,5 FPS em CPU | `docs/relatorio_validacao_fase1.md` |
| Fase 2 – sistema web completo | ✅ etapas 2.1 a 2.7 | `docs/arquitetura_fase2.md` |

O sistema verifica **só a máscara de solda** (decisão de escopo; luvas, avental, calçado e capacete ficaram como
trabalho futuro).

---

## Sumário

1. [Como funciona](#1-como-funciona)
2. [Requisitos](#2-requisitos)
3. [Instalação](#3-instalação-windows)
4. [Primeiro acesso](#4-primeiro-acesso)
5. [Execução e acesso pela rede](#5-execução-e-acesso-pela-rede)
6. [Configuração](#6-configuração)
7. [As telas](#7-as-telas)
8. [Posicionamento da câmera no setor de solda](#8-posicionamento-da-câmera-no-setor-de-solda)
9. [Backup e restauração](#9-backup-e-restauração)
10. [Privacidade e LGPD](#10-privacidade-e-lgpd)
11. [Limitações](#11-limitações)
12. [Testes automáticos](#12-testes-automáticos)
13. [Linha de comando da Fase 1 e testes de campo](#13-linha-de-comando-da-fase-1-e-testes-de-campo)
14. [Treinamento do modelo](#14-treinamento-do-modelo)
15. [Estrutura de pastas e documentação](#15-estrutura-de-pastas-e-documentação)
16. [Atribuição dos datasets](#16-atribuição-dos-datasets-cc-by-40)
17. [Licenças de software](#17-licenças-de-software)
18. [Tecnologias e versões](#18-tecnologias-e-versões)
19. [Funcionamento do back-end e do front-end](#19-funcionamento-do-back-end-e-do-front-end)

---

## 1. Como funciona

```
câmera ─► filtro do arco (quadro estourado pelo arco é ignorado)
       ─► YOLOv8n-pose + ByteTrack (pessoas, pontos do corpo e um número temporário para cada uma)
       ─► detector de máscara de solda (YOLOv8n treinado no projeto)
       ─► detector de rostos descobertos (YuNet)
       ─► regras: a máscara está na região da cabeça? o rosto está à mostra?
       ─► estado de cada pessoa ─► falta por 4 s (75% dos quadros) = ocorrência com a foto BORRADA
```

| Estado | Quando | Na tela |
|---|---|---|
| **Conforme** | máscara de solda na região da cabeça | verde, círculo ✔ |
| **Não conforme** | rosto descoberto e nenhuma máscara, ou máscara levantada | vermelho, octógono ✖ |
| **Indeterminado** | cabeça fora do quadro, pessoa de costas, rosto coberto sem máscara visível | amarelo, losango ? |

Indeterminado **nunca** gera ocorrência: o sistema não acusa sem evidência. Uma pessoa só gera outra ocorrência
depois de 60 s. Com o arco aceso perto das mãos, a ocorrência é marcada como **"Arco aceso"** (prioridade alta).

---

## 2. Requisitos

- **Computador:** Windows 10 ou 11, processador de 6 núcleos ou mais (testado em um AMD Ryzen 5 5600), 8 GB de RAM,
  cerca de 5 GB livres para a instalação e espaço para as imagens das ocorrências (cerca de 160 KB cada). Não precisa
  de placa de vídeo.
- **Python 3.12** (python.org). Outras versões não foram testadas; as bibliotecas estão fixadas para a 3.12.
- **Câmera:** webcam USB ou câmera IP com RTSP, de preferência 1080p (720p no mínimo).
- **Navegador:** Chrome, Edge ou Firefox atualizados (computador, tablet ou celular).
- **Internet:** só para instalar. Depois o sistema funciona sem internet (o único envio para fora é o alerta
  opcional pelo Telegram).

---

## 3. Instalação (Windows)

No PowerShell:

1. Baixe o projeto (ou use "Code → Download ZIP" no GitHub):
   ```powershell
   git clone https://github.com/leonamat1403/SafeWork.git
   cd SafeWork
   ```
2. Crie o ambiente do projeto e instale as bibliotecas (demora alguns minutos: o PyTorch é grande):
   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
3. Baixe os modelos de pose e de rosto (o modelo de máscara já vem no repositório, em `models/`):
   ```powershell
   .venv\Scripts\python -m src.run --baixar-modelos
   ```
   Em rede com proxy, rode este passo em outra rede e copie a pasta `models/`. Detalhes em `models/LEIA-ME.md`.

> Use sempre **`.venv\Scripts\python`**. O `python` do Windows pode ser outra versão, sem o YOLO e as outras
> bibliotecas; o sistema avisa quando é aberto assim.

---

## 4. Primeiro acesso

1. Crie a configuração (só na primeira vez):
   ```powershell
   .venv\Scripts\python -m app --configurar
   ```
   Ele cria o arquivo `.env` a partir do `.env.example`, gera a `SECRET_KEY` (a chave que protege o login) e pede a
   **senha inicial do administrador**. O que você digita não aparece na tela.
2. Ligue o sistema:
   ```powershell
   .venv\Scripts\python -m app
   ```
3. Abra **http://127.0.0.1:8000**, entre com o usuário `admin` e a senha do passo 1. O sistema pede uma senha nova
   (obrigatório no primeiro acesso).
4. Em **Configurações → Postos e câmeras**, ajuste o posto 1 (no primeiro uso ele é a "Webcam 0") ou cadastre a
   câmera do posto. Depois desenhe a **zona de interesse** e confira tudo na tela **Calibração**.
5. Em **Usuários**, crie os supervisores. Cada um troca a senha inicial no primeiro acesso.


### Usuário e senha

- **Usuário do administrador:** `admin` (vem de `ADMIN_LOGIN_INICIAL` no `.env`).
- **Senha:** a que você digitou no `--configurar`, guardada em `ADMIN_SENHA_INICIAL` no `.env`. Ela só vale até a primeira
  troca: depois do primeiro acesso, vale a senha nova que você escolheu (o `.env` não é atualizado).
- Não existe senha padrão fixa. Depois de 5 tentativas erradas o login é bloqueado por alguns minutos; reiniciar o
  sistema também libera.

### Esqueci a senha do admin

1. Feche o sistema (Ctrl+C no terminal em que ele está rodando).
2. Rode o comando abaixo, digite a senha nova duas vezes (ela não aparece na tela):
   ```powershell
   .venv\Scripts\python -m app --redefinir-admin
   ```
3. Ligue o sistema de novo (`.venv\Scripts\python -m app`) e entre com `admin` e a senha nova. O sistema pede outra
   senha no primeiro acesso. Nada mais é alterado: ocorrências, postos e usuários continuam como estavam.

Esqueceu a senha de um supervisor? Entre como administrador, abra **Usuários** e use **gerar senha temporária**.
Se o `admin` estiver desativado, o comando acima também o reativa.

### Como usar no dia a dia

1. **Ligue o sistema** e abra **http://127.0.0.1:8000** (ou o endereço da rede, seção 5). Entre com seu usuário.
2. **Ao vivo:** acompanhe o posto. Verde = máscara no rosto, vermelho = sem máscara ou levantada, amarelo = não dá para
   saber (de costas, fora do quadro). A foto de uma falta só é guardada quando ela dura cerca de 4 segundos.
3. **Ocorrências:** no fim do turno abra cada ocorrência, veja a foto (a cabeça sempre aparece borrada) e clique em
   **Confirmar falta** ou **Falso positivo**. Use os filtros por dia, posto e turno e **Exportar CSV** se precisar.
4. **Analisar arquivo:** para testar sem câmera, envie uma foto (.jpg/.png) ou um vídeo (.mp4, até 200 MB), escolha o
   posto e aguarde a barra de progresso (um vídeo de 30 s em 1080p leva alguns minutos). O resultado sai borrado e só
   vira ocorrência se você clicar em **Registrar como ocorrência**.
5. **Painel:** veja as faltas por dia, turno e posto e baixe o **relatório do mês em PDF** para a reunião de segurança.
6. **Administrador:** em **Configurações** ajuste postos, câmeras e a zona de interesse; em **Calibração** confira o que o
   sistema mede no posto; em **Usuários** crie supervisores.
7. **Para encerrar:** Ctrl+C no terminal. Os dados ficam na pasta `data/` (banco, imagens, backups e logs).

---

## 5. Execução e acesso pela rede

```powershell
.venv\Scripts\python -m app     # Ctrl+C para encerrar
```

Ao ligar, o sistema cria a pasta `data/` (banco, imagens, backups, logs), aplica as atualizações do banco e liga uma
câmera para cada posto ativo. As câmeras são processadas mesmo com ninguém olhando a tela.

**Tablet ou celular do supervisor:** por padrão o sistema só aceita conexões do próprio computador
(`HOST=127.0.0.1`). Para outros aparelhos da rede:

1. No `.env`, troque para `HOST=0.0.0.0` e reinicie o sistema.
2. Libere a porta 8000 no Firewall do Windows (precisa de administrador do computador).
3. No aparelho, abra `http://<IP do computador>:8000`.

O sistema não tem HTTPS próprio: use só em rede interna confiável. Para usar fora dela, coloque um proxy com HTTPS
na frente (ex.: IIS ou Caddy) e ligue `COOKIE_SEGURO=true` no `.env`.

---

## 6. Configuração

A configuração fica em três lugares; o de baixo vale por cima do de cima:

| Onde | O quê | Quem mexe |
|---|---|---|
| `config.yaml` | valores padrão: limites da máscara, filtro do arco, turnos, retenção, modelos | equipe técnica (editar e reiniciar) |
| `.env` | segredos e endereço: `SECRET_KEY`, administrador inicial, senha RTSP, Telegram, `HOST`, `PORTA`, `DATA_DIR` | equipe técnica (fora do git) |
| tela **Configurações** | postos e câmeras, máscara por posto, zona de interesse, sistema (intervalo entre ocorrências, retenção, arco, turnos, Telegram) | administrador; vale **na hora**, sem reiniciar, e fica na auditoria |

Variáveis do `.env` (modelo comentado em `.env.example`):

| Variável | Para quê |
|---|---|
| `DATA_DIR` | pasta dos dados (padrão `./data`) |
| `DATABASE_URL` | banco; padrão SQLite em `data/db/` |
| `HOST`, `PORTA` | endereço do sistema (`127.0.0.1` = só este computador; `0.0.0.0` = rede) |
| `SECRET_KEY` | assina o cookie de login (gerada pelo `--configurar`) |
| `ADMIN_LOGIN_INICIAL`, `ADMIN_SENHA_INICIAL` | primeiro administrador (usado só quando o banco está vazio) |
| `RTSP_USUARIO`, `RTSP_SENHA` | usuário e senha das câmeras IP (nunca vão para o banco) |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | alerta opcional pelo Telegram |
| `MODO_DESENVOLVIMENTO` | `true` só para testes: liga a documentação da API em `/docs` |
| `COOKIE_SEGURO` | `true` quando o sistema estiver atrás de HTTPS |

**Alerta pelo Telegram (opcional):** crie um bot com o @BotFather, coloque o token e o número da conversa no `.env`,
reinicie e use "Enviar mensagem de teste" em Configurações → Sistema. Cada ocorrência ao vivo manda a foto **já
borrada** e o tipo de falta. É a única informação que sai do computador (ver seção 10).

---

## 7. As telas

| Tela | Quem | Para quê |
|---|---|---|
| **Ao vivo** | todos | vídeo borrado com as caixas coloridas, "Pessoas agora", últimas ocorrências e o **cordão do turno** (o estado de cada 10 s do turno) |
| **Ocorrências** | todos | filtros, imagem borrada de cada falta, validação (**Confirmar falta / Falso positivo**), exportação **CSV** |
| **Analisar arquivo** | todos | envia uma foto ou um vídeo e recebe o resultado borrado; pode virar ocorrência |
| **Painel** | todos | ocorrências por dia, turno e posto, conformidade da máscara e o **relatório do mês em PDF** |
| **Configurações** | administrador | postos e câmeras, máscara por posto, zona de interesse e sistema |
| **Calibração** | administrador | desenho técnico e os números de cada pessoa ao lado dos limites |
| **Usuários** | administrador | criar supervisores, desativar e gerar senha temporária |

Todas funcionam no celular. Os estados aparecem sempre com cor **e** forma **e** texto.

---

## 8. Posicionamento da câmera no setor de solda

Recomendações tiradas dos testes de campo (`docs/resultados_testes_campo.md`):

- **De frente para o rosto do soldador** na posição de trabalho. De frente o sistema achou 83% das faltas; de perfil,
  só 50%.
- **Altura de 1,6 a 2 m**, levemente inclinada para baixo, a **2 a 4 m** do soldador. Acima de 4 m não foi testado.
- **A cabeça sempre dentro do quadro**, com enquadramento da cintura para cima ou de corpo inteiro. Resolução
  1080p (mínimo 720p).
- **Fora da linha direta do arco**, um pouco de lado, e protegida por **vidro ou policarbonato** contra respingos e
  faíscas. Limpe a proteção de tempos em tempos: os fumos embaçam a imagem.
- **Evite contraluz** (janela ou luminária atrás do soldador) e luz forte de um lado só. Cabeça baixa no escuro foi
  uma das falhas nos testes.
- Com **cortinas ou biombos de solda**, instale a câmera dentro da cabine ou com visão por cima da cortina.
- Desenhe a **zona de interesse** para deixar de fora corredores e outros postos.
- **Nunca filme** banheiros, vestiários, refeitório ou áreas fora do posto. A câmera serve só para o posto de solda.
- Depois de instalar, abra a tela **Calibração** com alguém no lugar do soldador (de frente, de lado, com a máscara
  abaixada e levantada; **ninguém solda sem máscara para o teste**) e confira: cabeça encontrada, rosto descoberto
  achado sem a máscara, cobertura acima do mínimo com a máscara, e o brilho das mãos com o arco aceso.
- Câmera IP: use cabo de rede e o fluxo de 1080p. Vídeos 4K deixam o sistema mais lento (cerca de 7,7 FPS, contra
  12,5 FPS em Full HD).

Aviso para afixar no setor: `docs/modelos/aviso_monitoramento.md` (versão para imprimir:
`docs/modelos/aviso_monitoramento.pdf`).

---

## 9. Backup e restauração

**O que é automático:**

| Rotina | Quando | O quê |
|---|---|---|
| Backup do banco | todo dia às 02:00 | cópia em `data/backups/epi_AAAAMMDD_HHMMSS.sqlite3`; guarda as 7 últimas |
| Retenção | todo dia às 03:00 | apaga as ocorrências com mais de 30 dias (configurável): primeiro as imagens, depois o registro, e anota na auditoria |
| Limpeza de uploads | a cada 15 min | apaga os arquivos enviados e os resultados com mais de 1 hora |
| Relatório mensal | dia 1º às 06:00 | guarda o PDF do mês anterior em `data/relatorios/` |

O backup automático copia **só o banco**. As imagens ficam em `data/ocorrencias/` e `data/thumbnails/`. Para guardar
tudo (por exemplo, toda semana, num disco externo ou servidor da empresa), **desligue o sistema** e copie a pasta
`data/` inteira, junto com o `.env`.

**Restaurar o banco a partir de um backup:**

1. Desligue o sistema (Ctrl+C).
2. Em `data/db/`, renomeie `epi.sqlite3` para `epi.sqlite3.antes` e tire dali os arquivos `epi.sqlite3-wal` e
   `epi.sqlite3-shm`, se existirem.
3. Copie o backup escolhido de `data/backups/` para `data/db/` com o nome `epi.sqlite3`.
4. Ligue o sistema. Ocorrências cujas imagens já tinham sido apagadas pela retenção aparecem "sem imagem".

**Levar o sistema para outro computador:** instale (seção 3), copie a pasta `data/` e o `.env` do computador antigo e
ligue. Faça um teste de restauração uma vez, antes de precisar.

---

## 10. Privacidade e LGPD

- O sistema **não identifica ninguém**: sem reconhecimento facial, sem biometria, sem nome nem matrícula. O "#3" na
  tela é um número temporário do rastreamento.
- **Nenhuma imagem sem blur vai para o disco** (garantido no código: o armazenamento só aceita imagens borradas). A
  cabeça é borrada mesmo quando o rosto não aparece.
- **Não grava vídeo contínuo**; guarda só uma foto borrada por ocorrência, apagada depois do prazo de retenção.
- O vídeo ao vivo, a foto baixada, a calibração e o resultado da análise de arquivos também saem borrados.
- Tudo fica **no computador da empresa**; a única exceção é o alerta opcional pelo Telegram (foto borrada).
- Acesso com login, perfis (administrador e supervisor), registro de auditoria e sessão que expira em 8 horas.

Revisão completa, com o que ainda cabe à empresa (encarregado de dados, relatório de impacto, política de uso):
**`docs/revisao_lgpd.md`**. Modelos: **aviso de monitoramento** para o setor e **termo de autorização** da empresa
parceira, em `docs/modelos/`.

---

## 11. Limitações

Da detecção (`docs/relatorio_validacao_fase1.md`, seção 6):

- **Só a máscara de solda** foi treinada e validada.
- A máscara bem colocada raramente fica verde (19% do tempo). No resto fica amarela, nunca vermelha: não gera
  alarme falso, mas também não confirma.
- De **perfil**, o sistema achou só 50% das faltas; **máscara levantada** de perfil não é reconhecida e, de frente,
  aparece como "sem máscara" (a consequência é a mesma: falta).
- Cabeça baixa no escuro, costas e respirador cobrindo o rosto ficam **indeterminados**.
- Amostra de teste pequena (11 situações de falta; intervalo de confiança do recall de 52% a 95%), com vídeos de
  banco de imagens, **sem teste no posto real** e **sem teste acima de 4 m**.
- O filtro do arco e a **solda ativa** (arco perto das mãos, limite inicial de 3%) não foram testados com arco real
  ao vivo: ajuste os limites na Calibração durante o piloto.
- A troca do número de rastreamento com os clarões do arco pode duplicar uma ocorrência.

Do sistema:

- Testado com até 2 câmeras ao mesmo tempo em um computador; vídeos 4K deixam cada câmera mais lenta.
- O cordão do turno e os resultados da análise de arquivos ficam na memória: se perdem quando o sistema reinicia.
- Sem HTTPS próprio (ver seção 5). O banco padrão é SQLite, em um computador só; o PostgreSQL é possível pela
  `DATABASE_URL`, mas não foi testado e precisa do driver.
- O alerta do Telegram foi testado só de forma simulada (sem um bot real).
- RD07 (mosaico para luvas e calçado) e RD08 (classificador de luvas) não foram feitos (só máscara).
- A revisão LGPD é técnica, feita pela equipe do projeto; **não é parecer jurídico**.
- Ideia para o futuro, fora do escopo: um **posto de validação** na entrada do setor de solda, que confere a
  máscara antes do início do trabalho (sem acompanhar o turno).

---

## 12. Testes automáticos

```powershell
.venv\Scripts\python -m pytest
```

São mais de 300 testes, com pessoas, máscaras e câmeras **simuladas**. Os testes da Fase 2 usam um banco e uma
pasta de dados temporários (nada toca a pasta `data/` real) e nunca usam a rede. O teste de integração com os
modelos reais é pulado se faltar algum modelo em `models/`.

---

## 13. Linha de comando da Fase 1 e testes de campo

A Fase 1 continua disponível, com janela do OpenCV:

```powershell
.venv\Scripts\python -m src.run                                         # webcam 0
.venv\Scripts\python -m src.run --fonte testes_campo\video1.mp4 --csv   # vídeo, ocorrências em CSV
.venv\Scripts\python -m src.run --fonte "rtsp://usuario:senha@192.168.0.10/stream"
.venv\Scripts\python -m src.run --fonte testes_campo\video1.mp4 --debug # região da cabeça, olhos e pontos
.venv\Scripts\python -m src.run --benchmark                             # FPS com imgsz 640 e 960
```

Teclas: **q** ou **ESC** sai, **p** pausa. Gravações de pessoas reais exigem **autorização prévia** da empresa e dos
trabalhadores filmados, e **ninguém deve soldar sem máscara** para uma gravação.

| Ferramenta | Para quê |
|---|---|
| `ferramentas/capturar.py` | grava vídeos ou fotos de teste |
| `ferramentas/avaliar_testes.py` | processa os vídeos da planilha de testes de campo e calcula as métricas |
| `ferramentas/demo_registro.py` | processa um vídeo e grava as ocorrências no banco, já borradas, sem o servidor |
| `ferramentas/conferir_vazamento.py` | confere que nenhuma imagem de treino veio dos vídeos de teste |

Roteiro: `docs/roteiro_testes_campo.md`. Resultados: `docs/resultados_testes_campo.md`.

---

## 14. Treinamento do modelo

Notebooks em `notebooks/colab/` e `notebooks/kaggle/`. Passo a passo e decisões sobre os dados:
`docs/dataset_welding_ppe.md`. Resultados das rodadas: `docs/resultados_treino/`. A chave do Roboflow fica nos
Secrets do Colab ou do Kaggle, nunca no código.

---

## 15. Estrutura de pastas e documentação

```
SafeWork/
├── app/            sistema web (Fase 2): servidor, telas, banco, privacidade, rotinas
├── src/            detecção (Fase 1): modelos, regiões do corpo, regras, arco, ocorrências, votação, zona
├── tests/          testes automáticos (pytest)
├── models/         modelos (só o de máscara vai no git; ver LEIA-ME.md)
├── alembic/        atualizações do banco
├── ferramentas/    testes de campo, demonstração, conferências, aviso para imprimir
├── notebooks/      treinamento (Colab e Kaggle)
├── docs/           planos, relatórios, arquitetura, telas, LGPD e modelos de documentos
├── config.yaml     padrões da detecção e do sistema
├── .env.example    modelo do .env
├── data/           (fora do git) banco, imagens borradas, backups, relatórios, logs
└── testes_campo/   (fora do git) vídeos e resultados dos testes de campo
```

| Documento | Conteúdo |
|---|---|
| `docs/plano_fase1.md` | regras de detecção e decisões da Fase 1 |
| `docs/relatorio_validacao_fase1.md` | métricas, testes de campo, limitações e recomendações |
| `docs/arquitetura_fase2.md` | componentes, banco, rotas e decisões da Fase 2 |
| `docs/wireframes_fase2.md` | desenho das telas e mapa de navegação |
| `docs/revisao_lgpd.md` | revisão de privacidade e pendências da empresa |
| `docs/modelos/` | aviso de monitoramento e termo de autorização |
| `docs/academico/texto_base.md` | texto-base de Metodologia, Resultados e Limitações |
| `docs/academico/planilha_antes_depois.xlsx` | planilha do piloto: antes x depois, semana a semana |
| `docs/academico/roteiro_palestra.md` | palestra de 15 minutos sobre riscos da soldagem e uso dos EPIs |

---

## 16. Atribuição dos datasets (CC BY 4.0)

- "Welding-PPE" – Welding PPE, Roboflow Universe, 2023. https://universe.roboflow.com/welding-ppe/welding-ppe
- "Welding Helmet" – UTP, Roboflow Universe, 2025. https://universe.roboflow.com/utp-jtbn5/welding-helmet
- "welder" – ESports, Roboflow Universe, 2025 (rodada v4). https://universe.roboflow.com/esports/welder
- "safeweld" – Josephs Workspace, Roboflow Universe, 2026 (rodada v4).
  https://universe.roboflow.com/josephs-workspace-gaago/safeweld-cb24e

As classes foram remapeadas para `mascara` e novas versões foram geradas sem "Isolate Objects", sem "Stretch" e sem
as augmentations originais. Na v4, parte das imagens foi excluída após conferência visual. Citações BibTeX em
`docs/dataset_welding_ppe.md`, seção 7.

Exemplos negativos (pessoas sem máscara, rodada v3): **COCO 2017** – Lin et al., "Microsoft COCO: Common Objects in
Context", ECCV 2014 (https://cocodataset.org); anotações CC BY 4.0, imagens com as licenças do Flickr indicadas no
COCO. Vídeos dos testes de campo: Pexels (links na aba Fontes da planilha de testes).

---

## 17. Licenças de software

- **Ultralytics YOLO** (detecção e pose): **AGPL-3.0**. Adequado a este projeto acadêmico; um uso interno contínuo
  pela empresa deve considerar essa licença. O modelo de máscara (`models/epi_solda_best.pt`) foi treinado a partir
  dele.
- **Este repositório** é distribuído sob a **AGPL-3.0** (arquivo `LICENSE`), a mesma licença do Ultralytics.
- **YuNet** (OpenCV Zoo): MIT. **OpenCV**: Apache 2.0. **FastAPI**, **SQLAlchemy**, **APScheduler**: MIT.
  **ReportLab** (PDF): BSD.
- Telas: **Bootstrap**, **Bootstrap Icons** e **Chart.js** (MIT) e as fontes **Barlow Semi Condensed**, **Atkinson
  Hyperlegible** e **IBM Plex Mono** (SIL Open Font License 1.1), guardadas em `app/static/vendor/` com as licenças.

---

## 18. Tecnologias e versões

Linguagem: **Python 3.12**. As versões abaixo estão fixadas em `requirements.txt` (RNF07); as do navegador ficam
guardadas no próprio projeto, em `app/static/vendor/`, e funcionam sem internet.

| Camada | Tecnologia | Versão | Para quê |
|---|---|---|---|
| Visão computacional | Ultralytics (YOLOv8n e YOLOv8n-pose) | 8.4.175 | detector de máscara (treinado no projeto) e pontos do corpo |
| | PyTorch / torchvision | 2.14.1 / 0.29.1 | execução dos modelos em CPU |
| | OpenCV | 5.0.0.93 | leitura da câmera, blur, desenho; detector de rostos YuNet |
| | NumPy, lap | 2.5.3, 0.5.13 | cálculo e rastreamento (ByteTrack) |
| Servidor | FastAPI, Starlette, Uvicorn | 0.143.1, 1.8.0, 0.54.0 | rotas, API e servidor web |
| | Jinja2 | 3.1.6 | páginas HTML no servidor |
| | python-multipart, itsdangerous, bcrypt | 0.0.32, 2.2.0, 5.0.0 | upload, cookie de login assinado, senhas |
| Dados | SQLAlchemy, Alembic | 2.1.4, 1.20.0 | banco (SQLite) e atualizações do banco |
| | APScheduler | 3.11.3 | backup, retenção e relatório mensal |
| | python-dotenv, PyYAML, tzdata | 1.2.4, 6.0.3, 2026.5 | configuração (`.env`, `config.yaml`) e fuso de Brasília |
| Relatórios | ReportLab, openpyxl | 4.2.5, 3.1.5 | PDF mensal e planilhas de teste |
| Telas | Bootstrap, Bootstrap Icons | 5.3.8, 1.13.2 | layout responsivo e ícones |
| | Chart.js | 4.4.7 | gráficos do Painel |
| | JavaScript puro (fetch) | – | comportamento das telas, sem framework |
| | Fontes Barlow Semi Condensed, Atkinson Hyperlegible, IBM Plex Mono | – | tipografia |
| Testes | pytest, httpx2 | 9.1.1, 2.13.1 | testes automáticos |
| Modelos pré-treinados | YOLOv8n-pose (COCO) e YuNet (OpenCV Zoo) | – | pontos do corpo e rostos (open source; referências na seção 17) |

---

## 19. Funcionamento do back-end e do front-end

### Back-end (`app/` e `src/`)

O back-end recebe a imagem, processa e devolve o resultado para as telas (`docs/arquitetura_fase2.md`).

1. **Entrada:** uma thread por câmera ativa lê o vídeo (webcam, RTSP ou arquivo) em `app/stream.py`.
2. **Processamento:** cada quadro passa por `src/pipeline.py`: filtro do arco, detecção de pessoas, de máscara e de
   rostos, e as regras de `src/compliance.py` (conforme, não conforme, indeterminado).
3. **Decisão:** `src/occurrences.py` só gera a ocorrência quando a falta dura 4 s (75% dos quadros).
4. **Privacidade e gravação:** `app/privacy.py` borra cabeças e rostos; `app/storage.py` só grava imagens já borradas;
   `app/registro.py` grava a ocorrência no banco (`app/models.py`).
5. **Saída:** rotas em `app/rotas/` entregam o vídeo ao vivo (MJPEG), o estado das pessoas (a cada 1 s), as
   ocorrências, o painel, as configurações e os relatórios; `app/auth.py` exige login e CSRF em todas.
6. **Rotinas:** `app/scheduler.py` faz backup (02:00), retenção (03:00) e relatório mensal (dia 1º).

### Front-end (`app/templates/` e `app/static/`)

Interface web em português, pensada para usuários leigos (supervisor e técnico de segurança), sem instalar nada no
aparelho.

- As páginas são montadas no servidor (Jinja2) e o JavaScript puro (`app/static/js/`) busca os dados na API e
  atualiza a tela, por exemplo o painel "Pessoas agora" a cada segundo.
- **Responsivo:** Bootstrap; no celular o menu vira botão e as telas ficam empilhadas (testado em 375 px).
- **Acessível:** o estado nunca depende só da cor (cor + forma + texto), foco visível, navegação por teclado.
- **Seguro:** nenhum script ou estilo dentro do HTML; os dados da API entram como texto, nunca como HTML.
- Desenho e decisões das telas: `docs/wireframes_fase2.md`.
