# Verificador de EPIs de Solda com Visão Computacional

Projeto extensionista de Ciência da Computação da **FSG** (Caxias do Sul – RS), em parceria com a **Marcopolo**.
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
- **YuNet** (OpenCV Zoo): MIT. **OpenCV**: Apache 2.0. **FastAPI**, **SQLAlchemy**, **APScheduler**: MIT.
  **ReportLab** (PDF): BSD.
- Telas: **Bootstrap**, **Bootstrap Icons** e **Chart.js** (MIT) e as fontes **Barlow Semi Condensed**, **Atkinson
  Hyperlegible** e **IBM Plex Mono** (SIL Open Font License 1.1), guardadas em `app/static/vendor/` com as licenças.
