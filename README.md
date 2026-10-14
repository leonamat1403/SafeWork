# Verificador de EPIs de Solda com Visão Computacional

Projeto extensionista de Ciência da Computação da **FSG** (Caxias do Sul – RS), em parceria com a **Marcopolo**.
Uma câmera instalada no posto de solda verifica se o soldador está usando a **máscara de solda** e sinaliza
as não conformidades (NR-6).

> **Fase 1 – validação da detecção:** concluída e validada para a **máscara de solda**
> (`docs/relatorio_validacao_fase1.md`). Execução por linha de comando, com janela do OpenCV.
> **Fase 2 – sistema completo:** em andamento (`docs/arquitetura_fase2.md`). Etapas 2.2 (banco, imagens borradas,
> rotinas), 2.3 (servidor web) e 2.4 (telas: login, ao vivo, analisar arquivo, ocorrências e usuários) prontas
> (seção "Fase 2" abaixo).

## Como funciona (resumo)

```
frame ─► filtro do arco (frame estourado é ignorado)
      ─► YOLOv8n-pose + ByteTrack (pessoas, pontos do corpo, ID de cada pessoa)
      ─► detector de máscara de solda (YOLO treinado no projeto)
      ─► detector de rostos descobertos (YuNet)
      ─► regras: a máscara está na região da cabeça?  ─► caixa VERDE / AMARELA / VERMELHA
```

| Estado | Quando | Cor |
|---|---|---|
| CONFORME | máscara detectada na região da cabeça | verde |
| NÃO CONFORME | rosto descoberto visível (detector de rostos) e nenhuma máscara, ou máscara levantada | vermelho |
| INDETERMINADO | cabeça não visível, pessoa de costas, rosto coberto sem máscara detectada | amarelo |

"MASCARA LEVANTADA" é indicada quando a máscara está acima da linha dos olhos com o rosto visível.

## Instalação (Windows, Python 3.12)

```powershell
cd Z:\Documentos\SafeWork
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Modelos (pasta `models/`, fora do git):
- `epi_solda_best.pt`: gerado pelo notebook de treinamento (`notebooks/colab` ou `notebooks/kaggle`);
- modelos de pose e o detector de rostos (YuNet): `python -m src.run --baixar-modelos`. Em rede com proxy, rode em outra rede e copie a pasta `models/`.

## Uso

```powershell
python -m src.run                                         # webcam 0
python -m src.run --fonte 1                               # outra webcam
python -m src.run --fonte testes_campo\video1.mp4 --posto mig_01 --csv   # grava as ocorrências em CSV
python -m src.run --fonte testes_campo\foto1.jpg --salvar-saida
python -m src.run --fonte "rtsp://usuario:senha@192.168.0.10/stream"
python -m src.run --fonte testes_campo\video1.mp4 --debug  # mostra região da cabeça, linha dos olhos e pontos
python -m src.run --benchmark                              # FPS com imgsz 640 e 960
```

Teclas na janela: **q** ou **ESC** sai, **p** pausa.
`--salvar-saida` grava o resultado anotado em `testes_campo/` (fora do git). **Gravações de pessoas reais exigem
autorização prévia da empresa e dos trabalhadores filmados.**

**Ocorrências:** uma ocorrência é registrada quando a pessoa fica **sem máscara ou com a máscara levantada** em pelo
menos 75% dos frames de **4 segundos**; a mesma pessoa só gera outra depois de **60 segundos**. Elas aparecem no
terminal e na tela e, com `--csv`, vão para `testes_campo/ocorrencias_<fonte>_<data>.csv` (abre no Excel; a coluna
`revisao_manual` é para marcar VP/FP). No fim, o terminal mostra um resumo por pessoa.

Configuração: `config.yaml` (EPIs, limiares, tempos de persistência e cooldown, postos de solda, filtro do arco, modelos).

## Testes

```powershell
python -m pytest
```

Os testes usam pessoas e máscaras **simuladas** (sem câmera). O teste de integração usa os modelos reais e é pulado
se eles não estiverem em `models/`. Os arquivos `tests/test_fase2_*.py` testam a Fase 2 com um banco e uma pasta
de dados temporários (nada toca a pasta `data/` real).

## Fase 2 – sistema completo (em andamento)

Arquitetura: `docs/arquitetura_fase2.md`. O código novo fica em `app/` e **importa** a detecção da Fase 1 (`src/`).

**Primeira vez:** copie `.env.example` para `.env` e ajuste (a pasta de dados padrão é `./data`, fora do git).

| Etapa 2.2 – o que já existe | Arquivo |
|---|---|
| Configuração (.env + config.yaml), pastas de dados, log com rotação | `app/config.py` |
| Banco SQLite (SQLAlchemy), 7 tabelas, datas em UTC | `app/database.py`, `app/models.py` |
| Migrações do banco | `alembic/` (`alembic upgrade head`; o sistema também aplica ao iniciar) |
| Blur de cabeças e rostos antes de gravar (só `ImagemBorrada` pode ir para o disco) | `app/privacy.py` |
| Imagens das ocorrências em `data/ocorrencias/AAAA/MM/DD/` e miniaturas | `app/storage.py` |
| Ocorrência da Fase 1 → blur → imagem → banco | `app/registro.py` |
| Retenção (03:00), backup do banco (02:00), limpeza de uploads (15 min) | `app/scheduler.py` |
| Fuso de Brasília e turnos | `app/tempo.py` |

| Etapa 2.3 – servidor web | Arquivo |
|---|---|
| Inicialização, cabeçalhos de segurança, documentação /docs (modo desenvolvimento) | `app/main.py` (`python -m app`) |
| Login, sessão (8 h), perfis ADMIN/SUPERVISOR, CSRF, bloqueio após 5 erros, troca de senha | `app/auth.py`, `app/rotas/acesso.py` |
| Câmeras ao vivo: uma thread por câmera, stream MJPEG, status, pausar, snapshot borrado | `app/stream.py`, `app/rotas/cameras.py` |
| Upload de foto/vídeo, resultado borrado, "registrar como ocorrência" | `app/uploads.py`, `app/rotas/uploads.py` |
| Ocorrências (filtros, 20 por página, validação, exclusão) e imagens em `/midia/{uuid}` | `app/rotas/ocorrencias.py` |

| Etapa 2.4 – telas (`docs/wireframes_fase2.md`) | Arquivo |
|---|---|
| Páginas: login, troca de senha, Ao vivo (T02), Analisar arquivo (T03), Ocorrências (T04), Usuários (T08) | `app/paginas.py`, `app/templates/` |
| Comportamento das telas (JavaScript puro, sem script dentro do HTML) | `app/static/js/` |
| Visual: Bootstrap 5.3.8, Bootstrap Icons 1.13.2 e fontes **locais** (funciona sem internet) | `app/static/css/app.css`, `app/static/vendor/` |
| "Cordão do turno" (estado de cada 10 s do turno) e gestão de usuários | `app/stream.py`, `app/rotas/cameras.py`, `app/rotas/usuarios.py` |

**Rodar o sistema web:**

```powershell
copy .env.example .env          # depois edite: SECRET_KEY e ADMIN_SENHA_INICIAL
python -m app                   # Ctrl+C para encerrar
```

1. Abra http://127.0.0.1:8000 → entre com `admin` e a senha do `.env` → defina uma senha nova (obrigatório).
2. **Ao vivo:** vídeo da câmera (cabeças borradas), "Pessoas agora", últimas ocorrências e o cordão do turno.
   No 1º uso a câmera 1 é a "Webcam 0" (o sistema liga a webcam ao iniciar).
3. **Ocorrências:** filtros (padrão: últimos 7 dias), clique numa linha para ver a imagem e validar
   (Confirmar falta / Marcar falso positivo; ← → passam de uma para outra).
4. **Analisar arquivo:** arraste uma foto ou um vídeo; o resultado sai borrado e pode virar ocorrência.
5. **Usuários** (só administrador): criar supervisor, desativar/reativar, gerar senha temporária.

Com `MODO_DESENVOLVIMENTO=true`, a documentação da API fica em http://127.0.0.1:8000/docs (a API continua exigindo
login).

**Demonstração sem servidor:** processa um vídeo e grava as ocorrências no banco, com as imagens já borradas:

```powershell
python ferramentas\demo_registro.py --fonte testes_campo\videos\nao_conformes\7006656-uhd_4096_2160_25fps.mp4
python ferramentas\demo_registro.py --listar
```

## Treinamento

Notebooks em `notebooks/colab/` (Google Colab) e `notebooks/kaggle/` (Kaggle). Passo a passo e decisões sobre os
dados: `docs/dataset_welding_ppe.md`. Resultados: `docs/resultados_treino/`.

## Atribuição dos datasets (CC BY 4.0)

- "Welding-PPE" – Welding PPE, Roboflow Universe, 2023. https://universe.roboflow.com/welding-ppe/welding-ppe
- "Welding Helmet" – UTP, Roboflow Universe, 2025. https://universe.roboflow.com/utp-jtbn5/welding-helmet
- "welder" – ESports, Roboflow Universe, 2025 (rodada v4). https://universe.roboflow.com/esports/welder
- "safeweld" – Josephs Workspace, Roboflow Universe, 2026 (rodada v4).
  https://universe.roboflow.com/josephs-workspace-gaago/safeweld-cb24e

As classes foram remapeadas para `mascara` e novas versões foram geradas sem "Isolate Objects", sem "Stretch" e sem
as augmentations originais. Na v4, parte das imagens foi excluída após conferência visual. Citações BibTeX em
`docs/dataset_welding_ppe.md`, seção 7.

Conferência de que nenhuma imagem de treino veio dos vídeos de teste de campo:
`python ferramentas/conferir_vazamento.py --datasets <pastas dos datasets>` (saída em `testes_campo/vazamento/`).

Exemplos negativos (pessoas sem máscara, rodada v3): **COCO 2017** – Lin et al., "Microsoft COCO: Common Objects in
Context", ECCV 2014 (https://cocodataset.org); anotações CC BY 4.0, imagens com as licenças do Flickr indicadas no COCO.

## Testes de campo (Etapa 1.5)

Roteiro completo: `docs/roteiro_testes_campo.md` (cenários, gravação, segurança e métricas).

| Ferramenta | Para que serve |
|---|---|
| `python ferramentas/capturar.py --saida testes_campo/c01.mp4 --duracao-s 30` | grava um vídeo de teste (ou, com uma pasta em `--saida`, fotos a cada 0,5 s) |
| `docs/planilha_testes_campo.xlsx` | modelo da planilha: cenários, testes, ocorrências (VP/FP), fontes dos vídeos e métricas x metas |
| `python ferramentas/avaliar_testes.py` | processa os vídeos listados na planilha (`testes_campo/planilha_testes_campo.xlsx`) e preenche resultados e métricas |
| `python ferramentas/criar_planilha_testes.py` | recria o modelo da planilha |

Resultados dos testes de campo (v3, v4 e v5): `docs/resultados_testes_campo.md`.
**Relatório de validação da Fase 1 (Etapa 1.6):** `docs/relatorio_validacao_fase1.md`.

## Licenças de software

As telas usam **Bootstrap** e **Bootstrap Icons** (licença MIT) e as fontes **Barlow Semi Condensed**, **Atkinson
Hyperlegible** e **IBM Plex Mono** (SIL Open Font License 1.1), todas guardadas em `app/static/vendor/` com as
licenças junto.

O Ultralytics YOLO é distribuído sob **AGPL-3.0**: adequado a este projeto acadêmico; um uso interno contínuo pela
empresa deve considerar essa licença.
