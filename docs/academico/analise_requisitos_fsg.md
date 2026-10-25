# Análise de requisitos x estado do projeto – Verificador de EPIs de Solda (FSG)

Data da análise: 24/10/2026 (sábado). Entrega e apresentação: 30/10/2026 (sexta). Restam 6 dias.
Legenda: **[V]** = fato verificado por mim hoje (arquivo, comando ou PDF original); **[I]** = inferência; **[?]** = não dá para saber pelos arquivos, confirmar.

Verificações feitas hoje: leitura das 5 extrações; conferência no PDF original da Aula 09 (slides 4 a 13, pdftotext) dos requisitos e da nota (0,4 / 0,8 / 0,8 / 1,5 / 1,0 / 0,5 = 5,0 [V]); leitura do README, `docs/` e `docs/academico/texto_base.md`; contagem automática de docstrings/comentários (script em scratchpad, nenhum arquivo do projeto alterado); `pytest` completo: **312 passed em 142,8 s [V]**; `git ls-files`, `.gitignore`, histórico e varredura de segredos; consulta anônima à API do GitHub.

---

## 1. Requisitos consolidados

| ID | Requisito | Fonte | Tipo | Peso | Prazo |
|---|---|---|---|---|---|
| R01 | Grupo de 3 a 5 integrantes ("trios, quartetos ou quintetos") | Aula 09 s5; Aulas 10 e 11 s4 | entrega/regulamentar | – | 09/10 |
| R02 | Grupo de 2 a 5 alunos, todos matriculados na mesma disciplina | Regulamento Art. 8, par. único, II | regulamentar | – | – |
| R03 | Tema: solução tecnológica com visão computacional para empresa, instituição ou sociedade | Aula 09 s5 | conteúdo | **0,4** (Tema e proposta) | 09/10 |
| R04 | Entrega do **Termo de Compromisso** no Portal | Aula 09 s11; Art. 8, I.1 | entrega/regulamentar | condição de aprovação | 09/10 |
| R05 | Entrega do **Plano de Trabalho** no Portal | Aula 09 s11; Art. 8, I.2 | entrega/regulamentar | condição de aprovação | 16/10 |
| R06 | Relatórios parciais (quantidade a critério do professor) | Art. 8, I.3 | regulamentar | condição | a definir pelo professor |
| R07 | Relatório Final (cumprimento integral da atividade) | Art. 8, I.4; Modelo do Relatório.docx | entrega/regulamentar | condição + parte da Documentação | 30/10 [I] |
| R08 | Front-end **web**, projetado para **usuários leigos** | Aula 09 s6 | técnico | **0,8** ("100% funcional") | 30/10 |
| R09 | Back-end recebe a entrada, processa e devolve ao front-end | Aula 09 s6 | técnico | **0,8** ("100% funcional") | 30/10 |
| R10 | Modelos pré-treinados permitidos; se prontos, **open source e referenciados** no projeto | Aula 09 s6 | técnico | – | 30/10 |
| R11 | Linguagens/frameworks/bibliotecas de livre escolha | Aula 09 s7 | técnico | – | – |
| R12 | Documentação: **tecnologias e versões** utilizadas | Aula 09 s7 | conteúdo (doc) | parte de **1,5** | 30/10 |
| R13 | Documentação: **instalação e configuração do ambiente passo a passo** | Aula 09 s7 | conteúdo (doc) | parte de 1,5 | 30/10 |
| R14 | Documentação: **funcionamento do back-end e do front-end** | Aula 09 s7 | conteúdo (doc) | parte de 1,5 | 30/10 |
| R15 | **Todos os códigos da solução comentados** | Aula 09 s7 | técnico/doc | parte de 1,5 | 30/10 |
| R16 | Códigos entregues no **GitHub** | Aula 09 s12 | entrega | **1,0** | 30/10 |
| R17 | Público-alvo: responder claramente às **4 perguntas** (quem é beneficiado; problema atual; como a visão computacional ajuda; uso no dia a dia) | Aula 09 s8 | conteúdo | [I] dentro de Tema/Documentação | 30/10 |
| R18 | Vincular a **ODS** da Agenda 2030 | Aula 09 s9; Art. 9, par. único; Modelo seção 2 | conteúdo/regulamentar | – | 30/10 (possivelmente já no Termo/Plano [?]) |
| R19 | Vincular a um **Núcleo Interdisciplinar** da FSG (com ODS compatíveis com o núcleo) | Aula 09 s10; Art. 9, par. único | regulamentar | – | idem |
| R20 | **Apresentação da solução** | Aula 09 s11 e s12 | apresentação | **0,5** | 30/10 |
| R21 | Entrega completa (solução + documentação) na pasta "Projeto Extensionista" do Portal, **por um único integrante** | Aula 09 s13; Aulas 10/11 s6 | entrega | – | 30/10 |
| R22 | Relatório no modelo FSG: capa (título em MAIÚSCULAS, negrito, até 3 linhas, centralizado; nomes; disciplina; "Caxias do Sul, dd de mês de 2026") + 7 seções na ordem: 1 Objetivos, 2 ODS, 3 Introdução Teórica, 4 Descrição da Atividade, 5 Resultados, 6 Conclusão, 7 Referências | Modelo do Relatório | conteúdo/formatação | parte de 1,5 [I] | 30/10 |
| R23 | Formatação: A4; margens sup./esq. 3 cm, dir./inf. 2 cm; corpo Times New Roman 12, justificado, entrelinha 1,5, recuo 1,25 cm; títulos TNR 12 negrito caixa alta numerados; logo FSG no cabeçalho; título da capa Arial 16 | Modelo (estilos) | formatação | – | 30/10 |
| R24 | Figuras numeradas: "Figura N: título" **acima**, "Fonte: ..." **abaixo**, com breve relato | Modelo seção 4 | formatação | – | 30/10 |
| R25 | Referências em ABNT | Modelo seção 7 | formatação | – | 30/10 |
| R26 | Objetivo geral e específicos | Modelo seção 1 | conteúdo | – | 30/10 |
| R27 | Introdução teórica que justifique a importância e a escolha do tema | Modelo seção 3 | conteúdo | – | 30/10 |
| R28 | Descrição de todos os passos executados | Modelo seção 4 | conteúdo | – | 30/10 |
| R29 | Resultados finais **com telas e endereços eletrônicos** | Modelo seção 5 | conteúdo | – | 30/10 |
| R30 | Conclusão sobre sucesso/insucesso frente aos objetivos + pontos de melhoria | Modelo seção 6 | conteúdo | – | 30/10 |
| R31 | Público-alvo constituído **em sua maioria por comunidade externa** | Regulamento Art. 4 | regulamentar | validação da ação | – |
| R32 | Ação **participativa e compartilhada**, com intervenção na comunidade; **relação dialógica** com grupos da sociedade | Art. 2, Art. 3-I, Art. 5 | regulamentar | validação da ação | – |
| R33 | Realizar **todas** as atividades extensionistas (I.1 a I.4); senão **reprovação automática e individual**, independentemente da nota | Art. 8 caput e par. único III | regulamentar | eliminatório | – |
| R34 | Carga horária extensionista integralizada (10% do PPC, somadas as modalidades) | Art. 1 §1; Art. 6 | regulamentar | – | depende do PPC/professor |
| R35 | Interdisciplinaridade como princípio norteador | Art. 3, par. único | regulamentar (fraco) | – | – |

---

## 2. Matriz de atendimento

| ID | Situação | Evidência | Lacuna concreta |
|---|---|---|---|
| R01 / R02 | **Depende do aluno/professor** | Nenhum nome de integrante no repositório [V]; os 52 commits são de um único autor (`leonamat1403`) [V] | Confirmar quantos integrantes há. A regra da disciplina (3 a 5) é mais restritiva que a do regulamento (2 a 5): com 2 integrantes há risco perante a aula; com 1, descumpre ambos. Listar os nomes no README e na capa. |
| R03 | **Atendido** (conteúdo) | README.md linhas 1-14; `docs/plano_fase1.md` §0 | Falta formalizar no relatório (seções 1 e 3). O README e as telas citam "parceria com a Marcopolo" (README l.3; `app/templates/base.html` l.82; `base_simples.html` l.19), mas não houve contato/visita: ver Decisão D1. |
| R04 | **A confirmar** [?] | Nada no repositório | Confirmar se o Termo foi entregue em 09/10. Se não: entregar já e avisar o professor (é condição de aprovação, Art. 8). |
| R05 | **A confirmar** [?] | Nada no repositório | Idem para o Plano de Trabalho (16/10). Se o Plano citou empresa, ODS ou núcleo, o relatório deve ser coerente com ele. |
| R06 | **Depende do professor** | – | Perguntar se houve/há relatório parcial exigido. |
| R07 / R22 | **Não atendido** | `doc-fsg/Modelo do Relatório.docx` existe só como modelo; `docs/academico/texto_base.md` cobre Metodologia, Resultados e Limitações com campos [PREENCHER] (linhas 81-89, 147-162) [V] | Escrever o relatório no .docx da FSG, nas 7 seções. Seções 1, 2, 3 e 7 não têm texto pronto; 4, 5 e 6 têm base. |
| R08 | **Atendido** (técnico) / **Parcial** (evidência) | Telas Jinja2 + Bootstrap 5.3.8 + JS puro em `app/templates/` e `app/static/js/` (10 arquivos) [V]; pt-BR, estados cor+forma+texto (README §1 e §7; `docs/wireframes_fase2.md` §6); `tests/test_fase2_telas.py`; 312 testes passam [V] | Nenhuma captura de tela no repositório nem no relatório [V] (só gráficos de treino em `docs/resultados_treino/`). Não testei manualmente no navegador hoje. Para "leigo": o README é técnico (PowerShell, .venv); falta um "guia rápido do supervisor" de 1 página [I]. |
| R09 | **Atendido** | FastAPI em `app/main.py`, rotas `app/rotas/*.py`, API JSON e MJPEG (`docs/arquitetura_fase2.md` §1 e §7) [V]; testes passam [V] | Demonstração ao vivo depende de webcam e modelos baixados: preparar plano B (vídeo de demonstração em "Analisar arquivo"). |
| R10 | **Atendido, com ressalvas** | README §17 (l.382-390): Ultralytics YOLO **AGPL-3.0**, YuNet MIT, OpenCV Apache 2.0; README §16: datasets CC BY 4.0 com links; `models/LEIA-ME.md`; referências em `texto_base.md` l.200-210 [V] | (a) AGPL-3.0 é licença open source (aprovada pela OSI), então cumpre "opensource"; (b) **o repositório não tem arquivo LICENSE** [V] e usa biblioteca AGPL: se ficar público, convém declarar AGPL-3.0 (Decisão D5); (c) `models/LEIA-ME.md` diz que o modelo foi treinado com "Welding-PPE e Welding Helmet", mas a v5 também usou welder, safeweld e negativos COCO/Pexels (README §16; `texto_base.md` l.26-31) [V]: corrigir; (d) os pesos-base pré-treinados (yolov8n.pt e yolov8n-pose.pt, COCO) não têm referência própria explícita como "modelo pré-treinado usado"; (e) no relatório faltam as referências em ABNT. |
| R11 | **Atendido** | `requirements.txt` só com bibliotecas livres [V] | – |
| R12 | **Parcial** | Versões fixadas em `requirements.txt` (ultralytics 8.4.175, torch 2.14.1, fastapi 0.143.1 etc.) [V]; Python 3.12 (README l.66); Chart.js 4.4.7 (comentário no requirements e arquitetura F2-D33); Bootstrap só como "Bootstrap 5" na doc, versão 5.3.8 apenas no cabeçalho do CSS em vendor [V] | Não há uma **tabela "Tecnologias e versões"** no README (linguagem, framework, banco, front-end, modelos, versões). Bootstrap Icons e fontes sem versão. Esforço: 30 min. |
| R13 | **Atendido** | README §2 a §6 (requisitos, instalação em 3 passos, `--configurar`, primeiro acesso, rede, `.env`) [V] | Recomendo um teste de instalação limpa em outro computador (o README prevê download dos modelos de pose/rosto pela internet). |
| R14 | **Atendido na doc técnica / Parcial no README** | `docs/arquitetura_fase2.md` (330 linhas: visão geral, fluxo de ocorrência, threads, rotas, segurança) e `docs/wireframes_fase2.md` (444 linhas) [V]; README §1 e §7 | O README não tem seções explícitas "Back-end" e "Front-end": o avaliador pode não achar. Adicionar duas seções curtas com link para a arquitetura. Esforço: 1 h. |
| R15 | **Parcial** | Python (app/, src/, ferramentas/: 49 arquivos, 7.382 linhas): **49/49 módulos com docstring**; **266 de 465 funções/classes com docstring (57%)**; ~314 linhas de comentário; comentários em português [V]. JS próprio (10 arquivos, 1.959 linhas): cabeçalho por arquivo e comentários de seção, **~73 linhas de comentário (~4%)** [V]. Templates HTML: 0 comentários (exceto `_icones.html`) [V]. Arquivos com menor cobertura: `app/paginas.py` (7/15, 0 comentários), `app/relatorios.py` (4/8), `app/rotas/configuracoes.py` (8/23), `app/stream.py` (20/38), `app/uploads.py` (10/24), `src/run.py` (12/25), `ferramentas/criar_planilha_testes.py` (1/13) [V] | O slide pede "**todos** os códigos comentados". Faltam docstrings em ~199 funções/classes e comentários nas funções JS e nos templates. Claude pode fazer (só comentários, sem mudar lógica, rodando os 312 testes depois). Esforço: 4 a 6 h. |
| R16 | **Parcial** | Remoto `origin = https://github.com/leonamat1403/SafeWork.git`, local sincronizado com `origin/main` [V]; API anônima do GitHub responde **404** [V] → **[I] repositório privado** (ou o nome mudou) | O professor precisa conseguir abrir. Tornar público ou convidar o professor como colaborador (Decisão D4). Colocar o link no relatório (seção 5) e no Portal. |
| R17 | **Não atendido (formalmente)** | Há material espalhado: README l.3-5 (problema/uso), `docs/academico/roteiro_palestra.md` (público: soldadores, ajudantes e supervisores), `docs/revisao_lgpd.md` [V]. Nenhum texto responde às 4 perguntas [V] (busca por "público-alvo" sem resultado) | Escrever as 4 respostas (Claude redige; o aluno valida com a empresa/visita). Sem visita, as respostas são hipóteses e devem ser apresentadas como tal. |
| R18 | **Não atendido** | Busca por "ODS" no projeto: nada [V] | Escolher ODS e justificar (Decisão D2). |
| R19 | **Não atendido** | Nada no projeto [V] | Escolher o núcleo coerente com os ODS (Decisão D2). [?] Talvez já declarado no Termo/Plano. |
| R20 | **Não atendido** | `docs/academico/roteiro_palestra.md` é palestra para trabalhadores, não a apresentação da disciplina [V] | Slides da apresentação + demonstração + plano B. Formato e tempo desconhecidos (perguntar). |
| R21 | **Pendente** | – | Um único integrante envia no Portal em 30/10: relatório + link do GitHub (+ outros que o professor pedir). |
| R23 / R24 / R25 | **Não atendido** (o relatório não existe) | Estilos do modelo extraídos (`extracao_modelo_relatorio.md`) | Produzir o .docx a partir do próprio modelo da FSG, mantendo estilos, cabeçalho e logo. |
| R26 / R27 / R28 / R29 / R30 | **Parcial** | Base: `texto_base.md` (Metodologia → seção 4; Resultados → seção 5; Limitações/Trabalhos futuros → seção 6); `plano_fase1.md` §2 (conceitos didáticos) para a seção 3 [V] | Faltam: objetivos geral/específicos; introdução teórica com fontes; capturas de tela; endereço eletrônico; conclusão honesta (protótipo validado em laboratório, piloto não realizado). |
| R31 | **Risco alto** | Público pretendido (soldadores, supervisores e segurança do trabalho de uma empresa) é externo à FSG [I]; **nenhuma ação com esse público foi realizada** [informado pelo aluno] | Sem nenhum contato com público externo, a ação pode não ser validada como extensão. Ver Riscos 1 e 2. |
| R32 | **Não atendido** | Nenhuma visita, entrevista ou devolutiva [informado] | Pelo menos um encontro dialógico (demonstração + entrevista/escuta + devolutiva) com registro. |
| R33 | **Em risco** | Depende de R04 a R07 e R31/R32 | Ver Risco 1. |
| R34 | **Depende do professor** | – | Perguntar quantas horas a disciplina integraliza e como são comprovadas. |
| R35 | **Parcial** [I] | O projeto já cruza computação, segurança do trabalho (NR-6), direito (LGPD) e educação (palestra) | Explicitar no relatório (seção 3 ou 4). |

Outras constatações [V]:
- `docs/academico/texto_base.md` l.145 diz "311 testes"; hoje são **312** e todos passam. Corrigir.
- README l.3 diz "Projeto extensionista de **Ciência da Computação**": confirmar o curso do grupo.
- Git/segurança: `.env`, `data/`, `dados/`, `testes_campo/`, `runs/`, `.venv/` estão no `.gitignore`; nenhum deles está versionado nem aparece no histórico como adicionado; nenhuma chave/token encontrado nos arquivos versionados (notebooks leem a chave do Roboflow de Secrets); `.env.example` só tem valores-modelo. Maior arquivo versionado: `models/epi_solda_best.pt` (~6,3 MB), aceitável. Nenhuma imagem de pessoa real versionada fora dos gráficos de treino.
- `doc-fsg/` está **não rastreada** (aparece em `git status`). [I] Não convém versionar material interno da FSG (slides, regulamento, modelo): adicionar ao `.gitignore` ou manter fora; o relatório final preenchido pode ir para `docs/academico/` se o grupo quiser.
- `models/` local tem `yolo26n-pose.pt` e versões antigas, ignorados pelo git e não usados pelo `config.yaml` (usa `yolov8n-pose.pt`, l.78).

---

## 3. Lacunas críticas e riscos (ordem de impacto)

1. **Reprovação automática (Art. 8) por atividade extensionista incompleta.** O Art. 8 condiciona a aprovação a "todas as atividades" (Termo, Plano, relatórios parciais, Relatório Final) e à "realização" da ação; a reprovação é individual e independe da nota. Situação: Termo e Plano **a confirmar**; relatório final inexistente; ação com a comunidade não realizada. Impacto: eliminatório. Mitigação: confirmar Termo/Plano hoje; entregar o relatório final no modelo; realizar e registrar ao menos um encontro com o público externo até 28/10; perguntar ao professor o que conta como "realização" neste semestre.
2. **Público externo e interação dialógica (Art. 4, Art. 2, Art. 3-I, Art. 5) sem nenhuma visita.** O sistema foi desenvolvido e testado só com vídeos de banco de imagens e webcam da equipe. [I] Um software pronto sem contato com o público tende a ser lido como projeto de disciplina, não como extensão. Mitigação realista em 6 dias: uma visita/reunião de 1 a 2 h com um setor de solda real (Marcopolo, se houver contato; senão uma metalúrgica, serralheria ou oficina de Caxias do Sul, ou o laboratório de solda de uma escola técnica), com: demonstração do sistema sem arco aceso, entrevista curta com soldador/supervisor/técnico de segurança (as 4 perguntas na voz deles), versão curta da palestra (`roteiro_palestra.md`) e registro (lista de presença ou declaração assinada pela empresa, anotações, fotos só com autorização e sem identificar trabalhadores). Isso **não** é o piloto e não pode ser chamado de piloto.
3. **Relatório final inexistente** (Documentação 1,5 + condição do Art. 8). Muito do conteúdo existe; o trabalho é redigir as seções 1, 2, 3, 7 e adaptar 4, 5 e 6 ao modelo, com figuras e capturas.
4. **GitHub provavelmente privado** (Códigos no GitHub 1,0). [I] Pela resposta 404 anônima. Se o professor não conseguir abrir, perde-se o item inteiro.
5. **"Todos os códigos comentados" parcial** (parte de 1,5). 57% das funções/classes com docstring; JS e templates pouco comentados.
6. **Resultados sem piloto.** O texto-base tem campos [PREENCHER] para o piloto e a planilha antes x depois está vazia. Risco de escrever resultado que não existe. Mitigação: a seção 5 apresenta os resultados que existem (métricas do modelo, testes de campo com vídeos, desempenho, sistema completo, telas, link) e o relato qualitativo da visita, se houver; o piloto vai para a Conclusão como próximo passo. Não preencher a planilha antes x depois.
7. **Uso do nome "Marcopolo"** no README, no rodapé das telas e no PDF mensal, sem parceria confirmada [V + informado]. Risco de afirmar parceria inexistente e de uso de marca. Mitigação: confirmar; se não houver vínculo, trocar por "cenário de referência: indústria de carrocerias de ônibus da Serra Gaúcha" (Decisão D1).
8. **Tamanho do grupo**: 3 a 5 (aula) x 2 a 5 (regulamento) [V]. Se o grupo tem 2 pessoas, perguntar ao professor; se só 1 pessoa fez os commits, a participação dos demais deve aparecer no relatório (divisão de tarefas).
9. **ODS e núcleo não escolhidos** (seção 2 obrigatória do modelo; Art. 9). Fácil de resolver, mas precisa ser coerente com o Termo/Plano já entregues.
10. **Apresentação** (0,5): formato/tempo desconhecidos; demo ao vivo depende de webcam, modelos baixados e notebook. Preparar vídeo/gravação de tela como plano B.
11. **Licença AGPL-3.0** do Ultralytics: aceitável para uso acadêmico e open source; ausência de LICENSE no repositório e uso futuro por empresa exigem menção clara (já há em README §17 e `texto_base.md` limitação 9).
12. **Instalação pelo professor**: depende de Python 3.12, ~5 GB e download dos modelos de pose/rosto. Sem teste em máquina limpa recente [I]. Mitigação: teste de clone limpo no dia 29.

---

## 4. Plano de ação até 30/10

Esforços são estimativas. "Claude" = pode ser feito por mim sozinho, com revisão do aluno no fim. Itens marcados ★ são críticos.

### Sábado 24/10
| # | Tarefa | Dono | Esforço | Verificação |
|---|---|---|---|---|
| 1 ★ | Enviar e-mail ao professor com as perguntas da seção 6 | Aluno | 15 min | e-mail enviado |
| 2 ★ | Conferir no Portal se Termo de Compromisso e Plano de Trabalho foram entregues; baixar cópias e me passar o texto (ODS, núcleo, empresa, objetivos que constam neles) | Aluno | 20 min | arquivos em `doc-fsg/` |
| 3 ★ | Listar nomes completos dos integrantes e a divisão de tarefas | Aluno | 10 min | lista no chat |
| 4 ★ | Começar contato com um setor de solda real para visita entre 27 e 28/10 (ver D1) | Aluno | 1 h | data marcada |
| 5 | Tabela "Tecnologias e versões" no README; seções "Como funciona o back-end" e "Como funciona o front-end"; corrigir 311→312 e `models/LEIA-ME.md` (datasets da v5); referenciar explicitamente os pesos pré-treinados (yolov8n.pt, yolov8n-pose.pt, YuNet) | Claude | 1,5 h | diff revisado; README com as 3 seções |

### Domingo 25/10
| # | Tarefa | Dono | Esforço | Verificação |
|---|---|---|---|---|
| 6 ★ | Comentar o código: docstrings em pt-BR nas ~199 funções/classes sem docstring (prioridade: `app/paginas.py`, `app/rotas/configuracoes.py`, `app/stream.py`, `app/uploads.py`, `src/run.py`, `ferramentas/`), comentários por função nos 10 JS e comentário de cabeçalho nos 13 templates. Só comentários, sem mudar lógica | Claude | 4–6 h | script de contagem ≥ 95%; 312 testes passando; diff só com comentários |
| 7 ★ | Redigir as 4 perguntas do público-alvo, objetivos (geral e específicos) e seção de ODS/núcleo (com a recomendação D2), marcando o que depende da visita | Claude | 1,5 h | texto revisado pelo aluno |
| 8 ★ | Kit da visita: roteiro de entrevista (10 perguntas, 15 min), formulário de opinião de 1 página, declaração de participação/visita para a empresa assinar, palestra curta (5–7 min, a partir de `roteiro_palestra.md`) | Claude | 1,5 h | 4 arquivos prontos para imprimir |

### Segunda 26/10
| # | Tarefa | Dono | Esforço | Verificação |
|---|---|---|---|---|
| 9 ★ | Rascunho completo do relatório no .docx da FSG (capa + 7 seções), com o estilo do modelo (A4, margens 3/3/2/2, TNR 12, 1,5, recuo 1,25, títulos numerados, figuras com legenda acima e fonte abaixo, ABNT) e [PENDENTE] onde depende da visita | Claude | 4–5 h | .docx abre no Word, estilos do modelo preservados |
| 10 | Capturas das telas (Login, Ao vivo, Analisar arquivo, Ocorrências, Painel, Configurações, Calibração, Usuários) com dados de demonstração, sem pessoas reais identificáveis; diagrama de arquitetura como figura | Claude (o aluno roda o sistema se precisar de webcam) | 1,5 h | 8–10 PNG numeradas |
| 11 ★ | Decidir visibilidade do GitHub e dar acesso ao professor (D4); adicionar LICENSE se público (D5) | Aluno (Claude prepara o LICENSE) | 20 min | link abre em aba anônima, ou convite aceito |

### Terça 27/10 e quarta 28/10
| # | Tarefa | Dono | Esforço | Verificação |
|---|---|---|---|---|
| 12 ★ | Visita/encontro: demonstração, entrevista, palestra curta, declaração assinada, anotações (sem fotografar trabalhadores sem autorização) | Aluno + grupo | 2–3 h + deslocamento | declaração assinada; anotações |
| 13 ★ | Incorporar o relato da visita no relatório (seções 4, 5 e 6) e ajustar as 4 respostas com a fala do público, sem inventar números | Claude (com as anotações do aluno) | 1,5 h | nenhum [PENDENTE] restante |
| 14 | Slides da apresentação (8–10 slides: problema e público, ODS, solução, arquitetura, demonstração, resultados, limitações, extensão realizada, próximos passos) + roteiro de fala + vídeo curto de plano B | Claude (vídeo: aluno grava a tela) | 2–3 h | .pptx pronto; vídeo de 1–2 min |

### Quinta 29/10
| # | Tarefa | Dono | Esforço | Verificação |
|---|---|---|---|---|
| 15 ★ | Revisão final do relatório pelo grupo (nomes, data, título ≤ 3 linhas, referências) | Aluno | 1 h | versão final .docx e .pdf |
| 16 | Teste de instalação limpa (git clone + README passo a passo) em outro computador | Aluno | 1 h | sistema abre no navegador |
| 17 | Commit/push final (documentação e comentários), conferir que `doc-fsg/` não vai para o git | Claude prepara; aluno autoriza o push | 15 min | GitHub com o último commit |
| 18 | Ensaio da apresentação com cronômetro | Grupo | 1 h | tempo dentro do limite |

### Sexta 30/10
| # | Tarefa | Dono | Esforço | Verificação |
|---|---|---|---|---|
| 19 ★ | Entrega no Portal por **um** integrante: relatório (.docx/.pdf), link do GitHub e o que mais o professor pedir | Aluno | 15 min | comprovante do Portal |
| 20 ★ | Apresentação | Grupo | – | – |

**Só o aluno pode:** confirmar Termo/Plano; falar com o professor; escolher e contatar a empresa; fazer a visita e colher assinaturas; definir nomes do grupo e curso; mudar a visibilidade do repositório ou convidar o professor; enviar no Portal; apresentar.
**Claude pode produzir sozinho:** comentários no código; seções de documentação no README; relatório no modelo da FSG em .docx; respostas às 4 perguntas e texto dos ODS (como proposta); kit da visita; capturas de tela com dados de demonstração; slides; LICENSE; revisão de coerência entre documentos.

---

## 5. Decisões que o aluno precisa tomar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D1 | Empresa/cenário | (a) Marcopolo, se já existe contato real; (b) outra empresa ou oficina de solda de Caxias do Sul acessível nesta semana; (c) só cenário de referência, sem visita | **(a) se der para marcar até 28/10; senão (b).** A (c) deixa o Art. 4/5 descoberto. Se não houver vínculo formal com a Marcopolo, trocar "parceria com a Marcopolo" por "cenário de referência" no README, no rodapé das telas e no PDF, e no relatório citar a empresa visitada só com autorização dela. |
| D2 | ODS e núcleo | Núcleo "Direitos Humanos, Justiça, Trabalho, Empregabilidade e Desenvolvimento Regional" (ODS 1, 2, 4, 5, 8, 9, 10, 11, 13, 16, 17) ou "Saúde e Bem-Estar" (ODS 1, 2, 3, 6, 11, 12, 13, 14, 15, 17) | **Núcleo Trabalho/Empregabilidade/Desenvolvimento Regional, com ODS 8 (meta 8.8, ambientes de trabalho seguros) como principal e ODS 9 (inovação na indústria) como secundário.** O ODS 3 só aparece no núcleo Saúde; citá-lo como relação indireta ou perguntar ao professor. Se o Termo/Plano já declarou algo, manter o que foi declarado. |
| D3 | Ausência de piloto | (a) apresentar o piloto como próximo passo e relatar só o que foi feito; (b) preencher "resultados esperados" | **(a).** Resultados = métricas do modelo, testes com 28 trechos de vídeo, desempenho em CPU, sistema completo, telas, link e relato da visita (se houver). Conclusão: "protótipo validado em laboratório; piloto não realizado no prazo". Não preencher a planilha antes x depois nem estimar efeitos. |
| D4 | Repositório público x privado | (a) público; (b) privado com o professor como colaborador | **(a) público**, depois de conferir (já conferi: sem `.env`, sem dados de pessoas, sem chaves). Facilita a avaliação e combina com a AGPL. Se o grupo preferir (b), mandar o convite já e confirmar que o professor aceitou. |
| D5 | Licença | (a) LICENSE AGPL-3.0; (b) sem licença | **(a)**, por coerência com o Ultralytics (AGPL-3.0) e com o requisito open source; manter a observação de que uso contínuo por empresa exige avaliar a licença. |
| D6 | Comentar todo o código agora | (a) sim, só comentários, com testes; (b) não mexer | **(a)**: o slide diz "todos os códigos comentados" e o risco é baixo se o diff tiver só comentários e os 312 testes passarem. |

---

## 6. Perguntas ao professor (prontas para e-mail)

Assunto: Projeto Extensionista – dúvidas para a entrega de 30/10 (Verificador de EPIs de Solda)

1. A "Documentação do projeto" (1,5) é o relatório no modelo da FSG, a documentação técnica do GitHub (README), ou as duas?
2. O que devemos enviar no Portal em 30/10: relatório em .docx, em PDF, link do GitHub? Mais algum arquivo?
3. O repositório pode ser público, ou prefere ser convidado como colaborador? Qual seu usuário do GitHub?
4. Qual o tempo e o formato da apresentação? Demonstração ao vivo é esperada?
5. Para validar a ação extensionista (Art. 4 e 5 do Regulamento), basta uma visita com demonstração e conversa com soldadores e supervisores, com uma declaração da empresa? Que comprovante o senhor aceita?
6. O piloto na empresa pode ficar como próximo passo, ou precisa ter acontecido até 30/10?
7. Há relatório parcial exigido além do relatório final?
8. Nosso grupo tem [N] integrantes. Está de acordo com a regra da disciplina (3 a 5)?
9. Podemos vincular o projeto ao núcleo "Direitos Humanos, Justiça, Trabalho, Empregabilidade e Desenvolvimento Regional" com os ODS 8 e 9? Podemos citar também o ODS 3?
10. Quantas horas extensionistas a disciplina integraliza e como elas são registradas?

---

## 7. Sumário detalhado sugerido do relatório (modelo FSG)

**Capa.** Título sugerido (≤ 3 linhas, maiúsculas): "VERIFICADOR DE USO DA MÁSCARA DE SOLDA COM VISÃO COMPUTACIONAL". Nomes [aluno]; Disciplina de Processamento de Imagens; "Caxias do Sul, 30 de outubro de 2026".

| Seção | Conteúdo proposto | Material existente | O que falta escrever |
|---|---|---|---|
| **1 Objetivos** | Geral: desenvolver e validar um protótipo web que verifica, por visão computacional, o uso da máscara de solda em postos de soldagem, sem identificar pessoas. Específicos: treinar o detector; definir regras com 3 estados; validar com vídeos (metas de recall ≥ 70% e FP ≤ 30%); construir back-end, front-end e banco; aplicar privacidade (LGPD); apresentar a solução ao público do setor de solda | README l.1-14; `plano_fase1.md` §0-1; metas em `relatorio_validacao_fase1.md` §5 | Todo o texto (Claude, 0,5 h) |
| **2 ODS** | ODS 8 (meta 8.8) e 9; núcleo; relação com a atividade | `extracao_regulamento.md` (lista de núcleos x ODS) | Todo o texto, conforme D2 e Termo/Plano |
| **3 Introdução teórica** | Riscos da soldagem e NR-6; problema atual e público-alvo (4 perguntas); visão computacional, detecção de objetos (YOLO), estimativa de pose, rastreamento (ByteTrack), detecção de rostos (YuNet), métricas (precisão, recall, mAP); privacidade (LGPD); justificativa | `plano_fase1.md` §2 (conceitos didáticos); `roteiro_palestra.md` (riscos); `revisao_lgpd.md`; referências em `texto_base.md` l.200-210 | Texto de 2–3 páginas com citações; números sobre acidentes só com fonte oficial (não há nenhum no projeto) |
| **4 Descrição da atividade** | 4.1 Definição do escopo (só máscara); 4.2 Dados e treino (5 rodadas); 4.3 Regras de decisão; 4.4 Testes de campo; 4.5 Sistema completo (back-end e front-end, arquitetura); 4.6 Privacidade; 4.7 Ação com o público externo (visita, se houver) | `texto_base.md` Metodologia (l.9-98); `dataset_welding_ppe.md`; `arquitetura_fase2.md` §1 (figura); `wireframes_fase2.md` | Adaptar o texto-base; figuras (arquitetura, fluxo de detecção); relato da visita. O modelo não tem subseções: usar parágrafos com título em negrito ou perguntar |
| **5 Resultados** | Métricas do modelo (tabela v3/v4/v5); testes de campo (recall 82%, IC 52–95%; FP 0/16); desempenho (12,5 FPS em CPU); sistema entregue com **capturas das telas**; **endereço do GitHub**; 312 testes automáticos; retorno do público na visita | `texto_base.md` Resultados (l.100-145); `relatorio_validacao_fase1.md` §3-4; `docs/resultados_treino/` (matrizes de confusão, gráfico de mAP) | Capturas de tela; link; relato qualitativo da visita; **remover** a subseção "Piloto: antes x depois" ou trocá-la por uma frase dizendo que o piloto não foi realizado |
| **6 Conclusão** | Objetivos atingidos (protótipo e validação em laboratório) e não atingidos (piloto no posto real); limitações principais; melhorias e próximos passos | `texto_base.md` Limitações (l.164-189) e Trabalhos futuros (l.191-197); README §11 | Juízo de sucesso/insucesso frente a cada objetivo específico |
| **7 Referências** | ABNT: NR-6, LGPD, Ultralytics YOLOv8, ByteTrack, YuNet, COCO, Wilson (1927), datasets Roboflow (CC BY 4.0), documentação do FastAPI/OpenCV, fontes da introdução | `texto_base.md` l.200-210; README §16-17; `dataset_welding_ppe.md` §7 | Formatar em ABNT (NBR 6023 por analogia para sites e datasets) e conferir cada referência |

Figuras candidatas (legenda acima, fonte abaixo): arquitetura (`arquitetura_fase2.md` §1, redesenhada); fluxo de detecção (README §1); matriz de confusão da v5 e comparação de mAP (`docs/resultados_treino/`); telas Ao vivo, Ocorrências, Painel, Configurações; estados conforme/não conforme/indeterminado.

---

### Arquivos relevantes
- `Z:\Documentos\SafeWork\README.md`
- `Z:\Documentos\SafeWork\docs\academico\texto_base.md`
- `Z:\Documentos\SafeWork\docs\arquitetura_fase2.md`
- `Z:\Documentos\SafeWork\models\LEIA-ME.md`
- `Z:\Documentos\SafeWork\doc-fsg\Modelo do Relatório.docx`
- Script de contagem de comentários (fora do projeto): `C:\Users\Leonardo\AppData\Local\Temp\claude\Z--Documentos-SafeWork\24180fc5-f653-4bc0-b4a5-eb3a4d5ccf24\scratchpad\analise\coment.py`
