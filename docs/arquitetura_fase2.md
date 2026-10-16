# Arquitetura do sistema completo – Fase 2 (Etapa 2.1, atualizada até a 2.7)

**Data:** 14/10/2026. A Fase 1 foi validada para a **máscara de solda** (`docs/relatorio_validacao_fase1.md`).
Esta etapa define **como** o sistema completo vai funcionar: componentes, modelo de dados, rotas e a integração com o
código da Fase 1. O código está em `app/`; o andamento das etapas fica na seção 12.

## 0. Princípios

1. **A Fase 1 não é reescrita.** O sistema web *importa* `src/` (detector, regras, filtro do arco, ocorrências). Os
   100 testes da Fase 1 continuam rodando e protegem contra regressões (critério de aceite da Fase 2).
2. **Foco na máscara de solda**, como na Fase 1. O banco e as telas já são genéricos por EPI (luvas, proteção do
   corpo, calçado, capacete), para ativá-los no futuro sem mudar a estrutura.
3. **Tudo local (on-premises):** um único processo Python no computador do posto. Nenhum dado vai para a nuvem (o
   Telegram, RD09, é a única exceção documentada).
4. **Privacidade por construção:** nenhuma imagem sem blur chega ao disco. Isso é garantido pelo próprio código
   (seção 5), não só por cuidado de quem programa.
5. **Simples de explicar:** FastAPI + Jinja2 + Bootstrap + JavaScript puro, SQLite, threads (sem filas externas,
   sem Docker, sem React).

## 1. Visão geral

```
 Navegador (Bootstrap 5 + JS puro)
   │  páginas HTML (Jinja2)          ◄── cookie de sessão (HttpOnly, SameSite) + token CSRF
   │  <img src="/api/cameras/1/stream.mjpg">   (MJPEG, RF01)
   │  fetch /api/status a cada 1 s   (painel ao vivo, T02)
   ▼
 FastAPI / Uvicorn  (app/main.py, 1 processo)
   ├── auth.py ............ login, sessão, perfis ADMIN/SUPERVISOR, CSRF, hash de senha
   ├── rotas de páginas ... /login, /ao-vivo, /upload, /ocorrencias, /dashboard, /configuracoes, ...
   ├── rotas de API ....... /api/... (JSON) e /midia/{uuid} (imagens, sempre autenticado)
   │
   ├── stream.py: GerenciadorCameras
   │     └── TrabalhadorCamera (1 thread por câmera ativa)
   │           FonteVideo ─► Pipeline ─► desenhar ─► último JPEG + status (memória) ─► MJPEG / API
   │                         (src/)      (src/)
   │                            └─► GerenciadorOcorrencias (src/) ─► registro.py
   │                                                                   privacy.borrar ─► storage.salvar ─► banco
   ├── uploads.py: FilaUploads (1 thread) ─► o mesmo Pipeline, para fotos e vídeos enviados (T03)
   ├── scheduler.py (APScheduler) ─► retenção, backup do banco, limpeza de uploads, espaço em disco
   └── database.py / models.py (SQLAlchemy) ─► SQLite (migrações com Alembic)

 Disco: DATA_DIR (data/) ─► db/, ocorrencias/, thumbnails/, uploads_temp/, relatorios/, backups/, logs/
```

## 2. Integração com a Fase 1

| Módulo da Fase 1 | Uso na Fase 2 | Mudança |
|---|---|---|
| `src/tipos.py`, `src/body_regions.py`, `src/compliance.py`, `src/arc_filter.py` | importados como estão | nenhuma |
| `src/detector.py` (`Detector`, `DetectorRostos`) | 1 `Detector` por câmera e 1 para os uploads | nenhuma |
| `src/config.py` (`Config`, `ConfigEPI`...) | `app/config.py` monta um `Config` por câmera: `config.yaml` + banco | nenhuma; o adaptador fica em `app/` |
| `src/occurrences.py` (`GerenciadorOcorrencias`) | persistência de 4 s, cooldown e agrupamento, iguais aos da Fase 1 | nenhuma. O `RegistroCSV` não é usado; a exportação CSV da Fase 2 vem do banco |
| `src/run.py` (`Pipeline`, `ResultadoFrame`, `desenhar`, `FonteVideo`) | processamento e desenho de cada frame, leitura com reconexão | **refatoração sem mudar lógica:** essas classes saem do CLI para `src/pipeline.py` e `src/video.py`; o `run.py` passa a importá-las (F2-D2) |
| `ferramentas/`, `notebooks/`, `config.yaml` | continuam valendo | `config.yaml` ganha `turnos`, `retencao_dias` e limites de upload |

O `run.py` (CLI) continua funcionando: os testes de campo e o benchmark seguem sendo feitos por ele.

## 3. Modelo de dados (SQLAlchemy + SQLite)

```
usuarios 1───N auditoria
usuarios 1───N ocorrencias (validado_por)
cameras  1───N config_epi_camera
cameras  1───N ocorrencias
cameras  1───N metricas_sessao
config_sistema (chave/valor, sem relação)
```

| Tabela | Colunas | Observações |
|---|---|---|
| **usuarios** | id, nome, login (único), senha_hash, perfil (ADMIN/SUPERVISOR), ativo, **deve_trocar_senha**, criado_em | o 1º ADMIN vem do `.env` e precisa trocar a senha no primeiro acesso (F2-D9) |
| **cameras** | id, nome_posto, processo_solda (MIG_MAG/TIG/ELETRODO/CORTE/OUTRO), tipo (webcam/rtsp/arquivo), origem (índice ou URL **sem** senha), ativa, roi_poligono (JSON, RD06), criado_em, atualizado_em | usuário e senha do RTSP vêm do `.env` (F2-D10) |
| **config_epi_camera** | id, camera_id (FK), epi, exigido, conf_min, **persistencia_s**, **fracao_minima**, parametros_extra (JSON) | único por (camera_id, epi). Persistência em **segundos**, como na Fase 1 (D24), e não em frames (F2-D7) |
| **ocorrencias** | id, uuid, camera_id (FK), data_hora (UTC), turno, track_id, epis_faltantes (JSON), epis_indeterminados (JSON), confianca_media (JSON), **situacao** (JSON: EPI → motivo), **fracao_nao_conforme** (JSON), mascara_levantada, arco_ativo (RD03), caminho_imagem, caminho_thumb, validacao (PENDENTE/CONFIRMADA/FALSO_POSITIVO), validado_por (FK), validado_em, origem (ao_vivo/upload) | índices em data_hora, camera_id e validacao. Só o **caminho relativo** da imagem, nunca a imagem |
| **metricas_sessao** | id, camera_id, inicio, fim, fps_medio, frames_ignorados_saturacao, total_pessoas_avaliadas, total_conformes, total_nao_conformes, total_indeterminados | uma sessão por período em que a câmera ficou ligada; atualizada a cada minuto, para não perder dados se o sistema cair |
| **auditoria** | id, usuario_id (FK, vazio para ações do sistema), acao, detalhes (JSON), data_hora | ações: login, login_falhou, logout, alterar_config, gerenciar_usuario, exportar, excluir, validar, retencao (F2-D11) |
| **config_sistema** | chave, valor (JSON), atualizado_em, atualizado_por | ajustes da aba Sistema (T06, RD05) por cima do `config.yaml` (F2-D8) |

Em relação ao prompt, mudam: `persistencia_s` e `fracao_minima` no lugar de `frames_persistencia` (D24 da Fase 1);
mais as colunas `situacao`, `fracao_nao_conforme`, `deve_trocar_senha` e a tabela `config_sistema`.
**Nunca são armazenados:** frames ou vídeo sem blur, vídeo contínuo, recortes de rosto, embeddings, nome ou matrícula
do trabalhador (RF26). O `track_id` é só um número temporário do rastreamento.

## 4. Como uma ocorrência é gerada (ao vivo)

```
 1. FonteVideo.ler()                    frame original (só em memória)
 2. Pipeline.processar(frame)           filtro do arco -> pose + máscara + rostos -> estados (Fase 1)
 3. desenhar(frame)                     frame anotado -> JPEG em memória -> MJPEG para o navegador (nunca vai ao disco)
 4. GerenciadorOcorrencias.atualizar()  4 s com >= 75% em falta, cooldown 60 s (Fase 1) -> [Ocorrencia]
 5. para cada ocorrência:
      privacy.borrar(frame, pessoas, rostos)  -> ImagemBorrada   (blur de TODAS as cabeças + rostos achados)
      desenhar caixas sobre a imagem borrada  -> contexto para quem valida
      storage.salvar(ImagemBorrada)           -> ocorrencias/AAAA/MM/DD/<uuid>.jpg + thumbnails/.../<uuid>_thumb.jpg
      INSERT em ocorrencias (turno, EPIs, confiança, máscara levantada, caminhos relativos)
      status em memória: "últimas 5 ocorrências" (T02)
```

Se o disco estiver cheio (abaixo do limite configurado), a ocorrência é gravada **sem** imagem, com um alerta no
status e no log (RNF03).

## 5. Privacidade (LGPD)

- **Garantia pelo tipo:** `storage.salvar()` só aceita um objeto `ImagemBorrada`, que só é criado por
  `privacy.borrar()`. Não existe caminho no código para gravar um frame original (F2-D4). Um teste verifica isso.
- **O que é borrado:** a região da **cabeça de todas as pessoas** (pelos pontos da pose, com folga) e os **rostos**
  achados pelo detector de rostos em todo o frame (pessoas que a pose não pegou). Isso cobre o "blur preventivo" do
  RF27: a cabeça é borrada mesmo quando a máscara esconde o rosto.
- **Detector de rostos:** YuNet (já usado na Fase 1, MIT), em vez do MediaPipe (F2-D5).
- **Como o blur é feito:** cada região, com 20% de folga, vira um mosaico de no máximo 6 × 6 blocos e depois é
  suavizada (F2-D19). As caixas e os rótulos são desenhados **por cima** da imagem já borrada.
- **Risco residual:** uma pessoa que nem a pose nem o detector de rostos encontram (muito pequena, desfocada, quase
  toda escondida) não é borrada. Na demonstração com o vídeo do T21, isso aconteceu com um trabalhador ao fundo,
  desfocado e de cabeça baixa, que não dá para reconhecer. Registrar na revisão LGPD (Etapa 2.6).
- **Uploads (T03):** o arquivo enviado fica em `uploads_temp/` só durante o processamento (máximo 1 h, depois é
  apagado); o resultado anotado para download também é **borrado**.
- **Snapshot (T02):** é entregue já borrado direto para download e não fica guardado no servidor (F2-D6).
- **Retenção:** rotina diária apaga as ocorrências com mais de N dias (primeiro as imagens, depois o registro) e
  grava a ação na auditoria (RF29).
- **Logs** sem dados pessoais; senhas e URLs RTSP mascaradas (já existe `ocultar_senha` na Fase 1).
- RF30: modelos de "Aviso de monitoramento" e de termo de autorização entram na Etapa 2.6.

## 6. Execução e threads

| Componente | Como roda | Por quê |
|---|---|---|
| Servidor | 1 processo Uvicorn (sem `--workers`) | os modelos e as câmeras ficam na memória; o SQLite tem um único escritor |
| Câmera | 1 thread por câmera ativa, com **seu próprio** `Detector` | o YOLO não é seguro para uso por várias threads ao mesmo tempo |
| Monitoramento | a câmera é processada **mesmo sem ninguém olhando** a tela | o registro de ocorrências não pode depender do navegador aberto |
| MJPEG | cada navegador recebe o último JPEG (até ~10 por segundo) | vários supervisores podem olhar sem custo extra de inferência |
| Uploads | 1 thread e 1 job por vez, com progresso consultado pela página | evita disputar CPU com as câmeras |
| Agendador | APScheduler no mesmo processo: backup às 02:00, retenção às 03:00, limpeza de uploads a cada 15 min, espaço em disco a cada 10 min | sem serviços externos |

**Capacidade neste computador** (Ryzen 5 5600, CPU): ~12 FPS no total com uma câmera Full HD. Medido na Etapa 2.3 com os modelos reais: um vídeo **4K** usado como câmera rodou a **7,7 FPS** (a decodificação e a redução do 4K custam caro). Duas câmeras Full HD ficam com ~6 FPS cada (ainda acima da meta de 5). Para mais câmeras, `pular_frames` ou uma GPU.

**Pausar/retomar** (T02) para o processamento e as ocorrências daquela câmera, e o stream mostra "PAUSADO".
**Alterações de configuração** valem sem reiniciar: a thread da câmera percebe a mudança e reconstrói o `Config`
(o modelo só é recarregado se o arquivo ou o `imgsz` mudarem).

## 7. Rotas

Todas exigem login (RF23). Rotas que alteram algo (POST/PUT/DELETE) exigem o token CSRF (RNF05).
Perfis: **A** = só ADMIN; **A/S** = ADMIN e SUPERVISOR.

### 7.1 Páginas (HTML, Jinja2)

| Rota | Tela | Perfil |
|---|---|---|
| `GET /` | redireciona para `/ao-vivo` | A/S |
| `GET /login` (página) · `POST /login` (JSON) · `POST /logout` | T01 Login; volta para a página pedida (`?proximo=`, só caminhos deste sistema) | público / A/S |
| `GET /trocar-senha` (página) · `POST /api/trocar-senha` | troca de senha (obrigatória no 1º acesso e depois de uma senha temporária) | A/S |
| `GET /ao-vivo` | T02 Monitoramento ao vivo | A/S |
| `GET /upload` | T03 Análise por upload | A/S |
| `GET /ocorrencias` | T04 Ocorrências | A/S |
| `GET /dashboard` | T05 Painel (RD04) | A/S |
| `GET /configuracoes` | T06 Configurações (RD05, RD06) | A |
| `GET /calibracao` | T07 Calibração (RD02) | A |
| `GET /usuarios` | T08 Usuários | A |

### 7.2 API (JSON) e mídia

| Método e rota | Para quê | Perfil |
|---|---|---|
| `GET /api/me` · `POST /api/trocar-senha` | quem está logado (e o token CSRF) · troca da própria senha | A/S |
| `GET /api/cameras` | lista de câmeras com status (online, pausada, FPS) | A/S |
| `GET /api/cameras/{id}/stream.mjpg` | stream ao vivo anotado (RF01) | A/S |
| `GET /api/status?camera_id=` | FPS, online, arco/frame ignorado, pessoas e estado de cada EPI, máscara levantada, últimas 5 ocorrências e o **cordão do turno** (trechos de 10 s + pinos das ocorrências) (T02, a cada 1 s) | A/S |
| `POST /api/cameras/{id}/pausar` · `/retomar` | pausar ou retomar o monitoramento | A |
| `GET /api/cameras/{id}/snapshot.jpg` | foto atual **borrada**, para download | A/S |
| `POST /api/uploads` | envia foto (jpg/png) ou vídeo (mp4); valida tipo e tamanho (RF02) | A/S |
| `GET /api/uploads/{job}` | progresso, estado e tabela de pessoas × EPIs | A/S |
| `GET /api/uploads/{job}/arquivo` | baixa o resultado anotado (borrado) | A/S |
| `POST /api/uploads/{job}/registrar` | "registrar como ocorrência" (T03) | A/S |
| `GET /api/ocorrencias` | lista com filtros (período, posto, EPI, turno, validação), 20 por página (RF22), e o resumo do período (total, pendentes, confirmadas, falsos positivos) | A/S |
| `GET /api/ocorrencias/resumo` | quantas esperam validação (número na barra lateral) | A/S |
| `GET /api/ocorrencias/{uuid}` | detalhes para o modal | A/S |
| `POST /api/ocorrencias/{uuid}/validacao` | Confirmada / Falso positivo (auditado) | A/S |
| `DELETE /api/ocorrencias/{uuid}` | exclusão manual (auditada) | A |
| `GET /api/ocorrencias/exportar.csv` | exportação CSV com os mesmos filtros da tela (RD10, auditada) | A/S |
| `GET /api/relatorios/mensal.pdf?mes=AAAA-MM&camera_id=` | relatório mensal em PDF, sem imagens (RD10, auditado) | A/S |
| `GET /midia/{uuid}?tipo=imagem\|thumb` | imagem ou miniatura da ocorrência, só com login (RF24) | A/S |
| `GET /api/dashboard?inicio&fim&camera_id` | números e séries dos gráficos (RD04) | A/S |
| `GET /api/config/cameras` · `POST /api/cameras` · `PUT, DELETE /api/cameras/{id}` | cadastro de postos/câmeras (RD05); remover só sem ocorrências | A |
| `GET, PUT /api/cameras/{id}/epis` | máscara do posto: exigir, confiança, persistência, cobertura, levantada = falta (RF13) | A |
| `PUT /api/cameras/{id}/roi` | zona de interesse (RD06) | A |
| `GET, PUT /api/config/sistema` · `POST /api/config/telegram/teste` | cooldown, retenção, imgsz, arco e solda ativa, turnos, Telegram (token mascarado), uso de disco (RD05); mensagem de teste (RD09) | A |
| `GET /api/cameras/{id}/calibracao.mjpg` · `GET /api/calibracao/{id}` | stream com pontos e regiões do corpo e valores numéricos (RD02) | A |
| `GET, POST /api/usuarios` · `POST /api/usuarios/{id}/desativar` · `/reativar` · `/senha` | gestão de usuários (T08): criar, desativar/reativar, senha temporária (mostrada uma vez); tudo auditado | A |

Sem login, as páginas redirecionam para `/login` e a API e o `/midia` respondem **401**. Um SUPERVISOR em rota de
ADMIN recebe **403**. As imagens **nunca** ficam em `static/`: o `/midia` busca o caminho no banco e lê pelo
`Storage`, que não aceita caminhos fora de `DATA_DIR`.

## 8. Configuração

Ordem de precedência (a de baixo vence):

1. **`.env`**: segredos e caminhos (`DATA_DIR`, `DATABASE_URL`, `SECRET_KEY`, admin inicial, RTSP, Telegram).
2. **`config.yaml`**: padrões (modelos, detecção, arco, cooldown, retenção, turnos, limites de upload).
3. **`config_sistema`** (banco): o que o ADMIN mudou na aba Sistema (RD05).
4. **`cameras` + `config_epi_camera`** (banco): EPIs exigidos e limiares de cada posto (RF13).

No primeiro uso, se não houver câmeras, o sistema cria a "Webcam 0" com os EPIs padrão do `config.yaml`. Os `postos`
do `config.yaml` continuam servindo só ao CLI da Fase 1.

## 9. Segurança e erros

- **Sessão:** cookie assinado (`SECRET_KEY`), HttpOnly, SameSite=Lax, Secure quando houver HTTPS; expira após 8 h
  sem uso.
- **Senhas:** bcrypt (custo 12). Após 5 erros seguidos, o login fica bloqueado por 5 min, e a falha é auditada.
- **CSRF:** um token por sessão, em campo oculto nos formulários e no cabeçalho `X-CSRF-Token` nas chamadas `fetch`.
- **Uploads:** extensão e conteúdo conferidos (o arquivo precisa abrir como imagem ou vídeo), tamanho máximo
  configurável, nome aleatório no disco.
- **RNF03:** câmera fora do ar → reconexão automática (já existe na Fase 1), status "Offline" e um quadro "CÂMERA
  OFFLINE" no stream. Modelo ausente → o sistema abre e mostra um aviso, sem cair. Disco cheio → seção 4. O SQLite
  roda em modo WAL, com transações curtas.
- **RNF04:** log em arquivo e console, com rotação de 5 arquivos de 5 MB.

## 10. Estrutura de pastas

```
SafeWork/
├── src/                      # Fase 1 (núcleo da detecção) – reaproveitado
│   ├── pipeline.py, video.py # (F2-D2) saem do run.py, sem mudar a lógica
│   └── ... (config, detector, body_regions, compliance, arc_filter, occurrences, tipos, run)
├── app/                      # Fase 2
│   ├── main.py               # FastAPI, rotas, inicialização e encerramento
│   ├── config.py             # .env + config.yaml + banco -> Config de cada câmera
│   ├── auth.py               # login, sessão, perfis, CSRF, bcrypt
│   ├── database.py, models.py
│   ├── storage.py            # interface Storage + disco local (DATA_DIR)
│   ├── privacy.py            # blur (ImagemBorrada)
│   ├── registro.py           # ocorrência -> blur -> Storage -> banco (o "registro" do prompt)
│   ├── stream.py             # GerenciadorCameras, TrabalhadorCamera, MJPEG
│   ├── uploads.py            # FilaUploads (T03)
│   ├── scheduler.py          # retenção, backup, limpeza, disco
│   ├── tempo.py              # UTC <-> horário de Brasília, turnos
│   ├── notifier.py (RD09), reports.py (RD10)   # só nas etapas dos desejáveis
│   ├── templates/            # base, login, ao_vivo, upload, ocorrencias, dashboard, configuracoes, calibracao, usuarios
│   └── static/               # css, js, vendor (Bootstrap, Bootstrap Icons, Chart.js locais) – NUNCA imagens de ocorrências
├── alembic/                  # migrações
├── data/                     # fora do git (DATA_DIR)
├── models/, notebooks/, ferramentas/, docs/, tests/
├── config.yaml, .env.example, requirements.txt, README.md
```

O prompt chama o registro de `app/occurrences.py`. Aqui ele se chama `app/registro.py`, para não confundir com
`src/occurrences.py` (a lógica de persistência e cooldown, que continua na Fase 1).

**Dependências novas** (versões fixadas na Etapa 2.2): fastapi, uvicorn, jinja2, python-multipart, sqlalchemy,
alembic, bcrypt, itsdangerous, apscheduler, tzdata (fuso America/Sao_Paulo no Windows) e httpx (testes).

## 11. Testes da Fase 2

Com `TestClient` do FastAPI, um `DATA_DIR` temporário e um detector **simulado** (sem câmera nem modelo):

- os testes [FASE 1] continuam passando;
- **blur antes de gravar:** `storage.salvar()` recusa imagem que não é `ImagemBorrada`; a região da cabeça na imagem
  salva fica de fato borrada;
- sem login: páginas redirecionam e `/api/*` e `/midia/*` respondem 401; SUPERVISOR em rota de ADMIN → 403;
  POST sem CSRF → 403;
- retenção apaga as imagens e depois os registros, e audita; backup cria o arquivo e mantém só os 7 últimos;
- uploads: tipo e tamanho inválidos são recusados; o temporário some após o processamento;
- turno (inclusive o que atravessa a meia-noite, 22:00–06:00) e conversão UTC → America/Sao_Paulo;
- ocorrência de ponta a ponta: frames simulados → `GerenciadorOcorrencias` → registro (arquivo borrado + linha no
  banco);
- filtros, paginação e CSV com os mesmos filtros;
- telas (Etapa 2.4, `tests/test_fase2_telas.py`): redirecionamento para o login e de volta, troca obrigatória de
  senha, menu de administração só para o ADMIN, nenhuma página com script/estilo dentro do HTML (CSP), todos os
  arquivos carregados existem e são locais, gestão de usuários, resumo das ocorrências e o cordão do turno;
- desejáveis (Etapa 2.5): votação temporal e solda ativa (`test_fase2_deteccao.py`), calibração
  (`test_fase2_calibracao.py`), painel (`test_fase2_painel.py`), configurações e zona de interesse – inclusive que
  quem está fora da zona continua borrado (`test_fase2_configuracoes.py`), Telegram simulado, CSV e PDF
  (`test_fase2_relatorios.py`). Os testes nunca usam a rede.

## 12. Próximas etapas (como no prompt)

| Etapa | Entrega |
|---|---|
| 2.2 ✅ | `database.py`/`models.py` + Alembic + `storage.py` + `privacy.py` + `scheduler.py` + registro de ocorrências no banco + testes (e a refatoração F2-D2). Demonstração: `ferramentas/demo_registro.py` |
| 2.3 ✅ | Backend FastAPI: autenticação, streaming ao vivo, upload, `/midia/{uuid}`, API de status e de ocorrências. Teste pela documentação interativa `/docs` (modo desenvolvimento) |
| 2.4 ✅ | Wireframes T01–T08 + mapa de navegação (`docs/wireframes_fase2.md`, aprovados) → telas T01, T02, T03, T04 e T08 |
| 2.5 ✅ | Desejáveis: RD01, RD02 (T07), RD03, RD04 (T05), RD05 + RD06 (T06), RD09, RD10. RD07 e RD08 não foram feitos (F2-D28) |
| 2.6 ✅ | README completo, revisão LGPD (`docs/revisao_lgpd.md`), aviso de monitoramento e termo de autorização (RF30, `docs/modelos/`), comando de primeira configuração |
| 2.7 ✅ | Material acadêmico em `docs/academico/`: texto-base (Metodologia, Resultados, Limitações), planilha antes x depois e roteiro da palestra de 15 minutos |

## 13. Decisões da Fase 2

| # | Decisão | Motivo |
|---|---|---|
| F2-D1 | `app/` **importa** `src/` (a pasta `src/` não é renomeada) | reaproveita a Fase 1 sem duplicar código; os testes da Fase 1 continuam valendo |
| F2-D2 | `Pipeline`, `ResultadoFrame`, `desenhar` e `FonteVideo` saem de `src/run.py` para `src/pipeline.py` e `src/video.py`, **sem mudar a lógica** | o servidor não deve depender do arquivo do CLI |
| F2-D3 | Só a **máscara** vem ativa; o banco e as telas suportam os outros EPIs | a validação da Fase 1 cobriu só a máscara |
| F2-D4 | `storage.salvar()` só aceita `ImagemBorrada` | garante pelo código que nenhuma imagem sem blur chega ao disco (RF27) |
| F2-D5 | Blur com **YuNet** (OpenCV Zoo) em vez do MediaPipe | já está no projeto e foi validado na Fase 1 (achou rosto em 86–98% dos frames sem máscara); evita uma dependência a mais |
| F2-D6 | Snapshot é baixado já borrado e não fica no servidor | menos dados guardados; não há tabela para snapshots |
| F2-D7 | Persistência por EPI em **segundos com maioria** (4 s, 75%), e não em frames | decisão D24 da Fase 1; independe do FPS |
| F2-D8 | Tabela `config_sistema` para os ajustes feitos na tela (RD05), por cima do `config.yaml` | o `config.yaml` não é reescrito pelo sistema; as mudanças valem sem reiniciar e ficam auditadas |
| F2-D9 | ADMIN inicial criado do `.env` com troca de senha obrigatória no 1º acesso | a senha do `.env` é conhecida por quem instalou |
| F2-D10 | Usuário e senha do RTSP só no `.env` (um par para todas as câmeras); o banco guarda a URL sem senha | segredos fora do banco (RNF05) |
| F2-D11 | A auditoria inclui também `login_falhou`, `logout`, `gerenciar_usuario` e `retencao` | rastrear tentativas de acesso e a gestão de usuários; a retenção precisa ser auditada (prompt) |
| F2-D12 | Painel ao vivo por **polling** de 1 s em `/api/status` (não WebSocket) | mais simples, com o mesmo resultado para 1 atualização por segundo |
| F2-D13 | Senhas com a biblioteca **bcrypt** diretamente (sem passlib) | o passlib não é mais mantido e dá avisos com o bcrypt atual |
| F2-D14 | SUPERVISOR pode ver, validar, exportar CSV, fazer upload e baixar snapshot; **não** pode pausar câmeras nem mexer em configurações, calibração ou usuários | "só visualiza e valida" (RF23); pausar a câmera interrompe o monitoramento |
| F2-D15 | Máscara **levantada = NÃO CONFORME** continua (D25); o RD03 (arco) poderá tornar isso dependente do arco aceso | coerência com a Fase 1 validada |
| F2-D16 | Imagem da ocorrência gravada com no máximo **1.920 px** de largura (JPEG 85); textos e linhas do desenho crescem com o tamanho da imagem | numa câmera 4K, o print ocupava vários MB e o rótulo ficava ilegível; Full HD basta para validar (~160 KB) |
| F2-D17 | Pastas de imagens pelo **dia de Brasília** (`AAAA/MM/DD`), banco em UTC | quem procura um arquivo pensa no dia local; o banco não sofre com horário de verão |
| F2-D18 | Câmera **com ocorrências não pode ser apagada** (só desativada); ao apagar uma câmera sem ocorrências, os EPIs dela vão junto | o histórico de ocorrências não pode sumir |
| F2-D19 | Blur: a região (com 20% de folga) é reduzida a no máximo **6 × 6 cores médias** e ampliada de volta com interpolação linear (fica suave) | não sobra detalhe para reconhecer o rosto; custa o mesmo em qualquer resolução (o desfoque Gaussiano levava ~900 ms por quadro numa cabeça de vídeo 4K; assim, ~30 ms) |
| F2-D20 | **Vídeo ao vivo também borrado** por padrão (`privacidade.borrar_ao_vivo` no config.yaml), usando as cabeças da pose e os rostos já encontrados pela Fase 1 | minimização de dados (LGPD): o supervisor vê o estado dos EPIs pelas cores e rótulos; sem rodar de novo o detector de rostos, o custo é pequeno |
| F2-D21 | Telemetria do FastAPI (OpenTelemetry) **desligada** no código | ela só exportaria dados se alguém configurasse um destino, mas o projeto é on-premises: desligada, não há risco e não gasta CPU |
| F2-D22 | Documentação interativa `/docs` só com `MODO_DESENVOLVIMENTO=true`; a página é aberta, mas todas as rotas da API continuam exigindo login | permite testar o backend antes das telas (2.4) sem abrir nenhum dado |
| F2-D23 | Resultado de vídeo do upload em H.264 (`.mp4`), com VP8 (`.webm`) e mp4v de reserva; cada upload só aparece para quem enviou (o ADMIN vê todos) | H.264 e VP8 tocam direto no navegador (T03); o mp4v só serve para download |
| F2-D24 | O **cordão do turno** mostra o estado que **predominou** em cada trecho de 10 s (vermelho com metade ou mais dos quadros não conformes; verde com maioria conforme; amarelo na mistura; "ninguém" se houve gente em menos de 1/4 dos quadros), e não o pior quadro | no teste com um vídeo conforme, o "pior quadro" pintou 43% do cordão de vermelho sem nenhuma ocorrência: um quadro isolado errado não pode valer 10 s. As ocorrências continuam com a regra de 4 s / 75% |
| F2-D25 | Telas sem nenhum script ou estilo dentro do HTML (CSP `script-src 'self'`, sem `unsafe-inline`); dados da API entram sempre como texto (`textContent`); CSS e JS com `?v=` que muda quando os arquivos mudam | um dado vindo do banco nunca vira código na página (XSS); o navegador não usa um arquivo velho do cache depois de uma atualização |
| F2-D26 | Não existe "excluir usuário" (só desativar); ninguém desativa a si mesmo e sempre sobra um ADMIN ativo; a senha temporária gerada pelo ADMIN aparece **uma única vez** e obriga a troca no próximo acesso | o histórico de validações e a auditoria apontam para o usuário; o sistema não pode ficar sem administrador; o ADMIN não fica sabendo a senha definitiva de ninguém |
| F2-D27 | Bootstrap, ícones e fontes ficam no próprio sistema (`app/static/vendor/`), sem CDN | a rede da fábrica pode não ter internet, e nada sai do computador |
| F2-D28 | **Só a máscara de solda** no sistema todo (15/10/2026): as telas não mostram outros EPIs; RD07 (mosaico para luvas e calçado) e RD08 (classificador de luvas) **não foram implementados** e ficam como trabalho futuro | os dois só servem para luvas e calçado, que saíram do escopo; o RD08 ainda exigiria treinar um classificador com fotos de luvas que o projeto não tem |
| F2-D29 | RD01: a votação (maioria dos últimos 5 quadros válidos da pessoa; empate = o mais recente) vale **só para a exibição** (caixas, rótulos, painel e vídeo do upload). As ocorrências continuam com 4 s / 75% | a regra das ocorrências já é uma votação no tempo e foi a validada na Fase 1; mudar a tela não pode mudar os números |
| F2-D30 | RD03: arco aceso = pelo menos 3% de pixels estourados num quadrado em volta de um punho (lado = 24% da altura da pessoa); a pessoa continua "soldando" por 2 s. Máscara levantada com arco aceso é sempre falta; `exigir_mascara_somente_com_arco` (padrão **false**) faz a falta só contar com o arco aceso. A ocorrência guarda `arco_ativo` | o brilho do arco fica concentrado na tocha (nas mãos); o arco pisca, então sem a memória de 2 s o estado ficaria trocando; o padrão mantém a regra validada |
| F2-D31 | RD06: a pessoa está na zona quando o ponto onde pisa (meio da base da caixa) cai no polígono; o polígono é guardado em frações da imagem. Quem fica fora não é avaliado, mas **continua borrado**. Trocar a câmera do posto apaga a zona | o chão define o posto melhor que a cabeça (quem passa ao fundo fica de fora); frações continuam valendo se a resolução mudar; privacidade não depende da zona |
| F2-D32 | RD05: cada mudança religa só a câmera afetada (a aba Sistema religa todas), mantendo o cordão do turno, as últimas ocorrências e a pausa. Ajustes do sistema ficam em `config_sistema` por cima do config.yaml; um valor inválido no banco é ignorado com aviso no log | "vale sem reiniciar" (prompt) sem perder o turno; o sistema nunca deixa de iniciar por causa de um ajuste |
| F2-D33 | Painel: conformidade = conformes ÷ (conformes + não conformes) de `metricas_sessao`, com os indeterminados à parte; "por tipo de EPI" virou sem máscara × máscara levantada; Chart.js 4.4.7 local, com a tabela "Ver dados" em cada gráfico e cores das séries validadas para daltonismo | indeterminado não é falta nem acerto; a mesma conta (app/estatisticas.py) vale para o painel e o PDF |
| F2-D34 | RD09: o alerta do Telegram leva a **mesma imagem borrada** gravada no disco e um texto sem identificação; fila com thread própria; só com token no .env e ligado na tela; uploads não alertam. É a única saída de dados do sistema | exceção documentada ao "nada vai para a nuvem"; rede lenta não pode atrasar a câmera |
| F2-D35 | RD10: CSV com `;`, vírgula decimal e BOM (Excel em português), células que começam com = + - @ viram texto; PDF mensal com ReportLab, sem imagens, também guardado em data/relatorios no dia 1º | abre direto no Excel; evita fórmulas maliciosas num nome de posto; o relatório pode circular por e-mail sem expor ninguém |
| F2-D36 | RD02: o quadro de calibração só é desenhado enquanto a tela T07 está aberta (5 s depois do último pedido) | o desenho técnico custa CPU; ninguém olhando, nada é feito |
| F2-D37 | Login errado: a auditoria guarda o login só quando ele é de um usuário que existe; senão, só "login desconhecido" | quem digita a senha no campo "Usuário" por engano não deixa a senha gravada no banco (revisão LGPD) |
| F2-D38 | O modelo de máscara validado (`models/epi_solda_best.pt`, v5, 6,5 MB) vai no repositório; os outros pesos continuam fora e os de pose e rosto são baixados com `--baixar-modelos` | instalar e testar em outro computador sem copiar arquivos à mão (pedido de 15/10/2026) |
| F2-D39 | Primeira configuração por comando (`python -m app --configurar`): cria o `.env`, gera a SECRET_KEY e pede a senha do administrador sem mostrá-la; sem `.env`, o sistema explica o que falta em vez de mostrar o erro técnico | o primeiro uso real travou na falta do `.env` |
