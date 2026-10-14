# Wireframes e mapa de navegação – Fase 2 (Etapa 2.4)

**Data:** 14/10/2026. **Para aprovar antes de programar as telas.** Nesta etapa serão implementadas T01, T02, T03,
T04 e T08. T05 (dashboard), T06 (configurações) e T07 (calibração) são requisitos desejáveis e entram na Etapa 2.5,
mas já estão desenhadas aqui para o mapa ficar completo.

Quem usa: o **supervisor** do setor de solda (muitas vezes num tablet ou celular, no chão de fábrica) e o
**administrador** (técnico de segurança / TI, no computador). O trabalho principal de cada tela:
- T02 Ao vivo: **ver, num relance, quem está sem a máscara agora**;
- T04 Ocorrências: **revisar e validar** o que o sistema registrou.

---

## 1. Direção visual

As cores de estado são as do prompt e não mudam. O resto da identidade vem do próprio ambiente: chapa de aço,
placas de segurança e o cordão de solda.

### Cores

| Nome | Hex | Uso |
|---|---|---|
| Aço | `#1E2933` | barra lateral, títulos, texto principal |
| Grafite | `#4A5661` | texto secundário, rótulos |
| Chapa | `#EEF1F4` | fundo das páginas |
| Linha | `#D5DBE1` | bordas e divisões |
| Branco | `#FFFFFF` | cartões e tabelas |
| **Conforme** | `#198754` | fixo (prompt) |
| **Não conforme** | `#DC3545` | fixo (prompt) |
| **Indeterminado** | `#FFC107` | fixo (prompt); texto preto por cima (contraste) |
| **Ações** | `#0D6EFD` | fixo (prompt): botões e links |

### Tipografia (arquivos locais em `static/vendor/fontes`, funcionam sem internet; todas com licença livre OFL)

| Papel | Fonte | Por quê |
|---|---|---|
| Títulos e rótulos | **Barlow Semi Condensed**, semibold, MAIÚSCULAS espaçadas | lembra as placas de sinalização de segurança da fábrica; cabe muita informação na largura de um tablet |
| Texto | **Atkinson Hyperlegible** | feita para máxima legibilidade (Braille Institute): letras que não se confundem (l/I/1, O/0) em tela de chão de fábrica |
| Números | **IBM Plex Mono** | horários, FPS, nº da pessoa, confiança: os dígitos ficam alinhados nas tabelas |

### Estados: cor + forma + texto (nunca só a cor)

```
  ● Conforme          círculo   (bi-check-circle-fill)      verde
  ⬣ Não conforme      octógono  (bi-x-octagon-fill)         vermelho   ← a forma da placa "PARE"
  ◆ Indeterminado     losango   (bi-question-diamond-fill)  amarelo    ← a forma da placa de "ATENÇÃO"
```
Mesmo quem não distingue vermelho de verde reconhece o estado pela forma, como nas placas de trânsito.

### Ícones dos EPIs

| EPI | Ícone |
|---|---|
| Máscara de solda | **desenho próprio** de capacete de solda (no estilo dos Bootstrap Icons): o Bootstrap Icons não tem uma máscara de solda, e a "bi-mask" é uma máscara de carnaval |
| Luvas · Proteção do corpo · Calçado · Capacete (desativados por enquanto) | `bi-hand-index-thumb` · `bi-person-badge` · `bi-boot`¹ · `bi-cone-striped` |

¹ Se não existir na versão do Bootstrap Icons baixada, uso um desenho próprio no mesmo estilo.

### Assinatura: o **cordão do turno**

Uma faixa horizontal embaixo do vídeo ao vivo, desenhada como um **cordão de solda**: cada trecho de 10 segundos do
turno tem a cor do pior estado daquele trecho (verde, amarelo ou vermelho), e um **pino** marca cada ocorrência
registrada. O supervisor vê de uma vez se o turno está "limpo" ou se as faltas se repetem num horário. É a mesma
informação do sistema (estados por quadro), só que no tempo.

```
CORDÃO DO TURNO 2 (14:00–22:00)                                                   agora 16:41
14:00 ███████████████▓▓▓██████████████████░░▒▒▒██████████████████▒▒██████████████│
                     ▲ 14:52                    ▲ 15:31                ▲ 16:05
█ conforme   ▒ sem máscara (não conforme)   ░ indeterminado   ▲ ocorrência registrada   (vazio = câmera parada)
```

### Uma faixa de alerta, um só uso

A faixa listrada **amarela e aço** (como a fita de isolamento de área) aparece **só** quando o vídeo não está sendo
avaliado: "ARCO DETECTADO – quadro ignorado" ou "CÂMERA OFFLINE". Em nenhum outro lugar.

---

## 2. Mapa de navegação

```
                          ┌─────────────┐
       (sem login, qualquer│  T01 LOGIN  │
        página leva aqui) ─►  /login     │
                          └──────┬──────┘
                                 │ login certo
                     ┌───────────▼────────────┐   1º acesso do ADMIN
                     │ precisa trocar a senha?├──────────────┐
                     └───────────┬────────────┘              ▼
                                 │ não               ┌───────────────┐
                                 │                   │ TROCAR SENHA  │
                                 ▼                   │ /trocar-senha │
  ┌──────────────────── BARRA LATERAL (todas as páginas) ──────────────────┘
  │
  │  OPERAÇÃO                         (ADMIN e SUPERVISOR)
  │   ├─ T02 Ao vivo ............ /ao-vivo        ← página inicial
  │   ├─ T04 Ocorrências [18] ... /ocorrencias    ← [nº de pendentes]
  │   ├─ T03 Analisar arquivo ... /upload
  │   └─ T05 Painel ............. /dashboard      (Etapa 2.5)
  │
  │  ADMINISTRAÇÃO                    (só ADMIN; o SUPERVISOR nem vê esta seção)
  │   ├─ T06 Configurações ...... /configuracoes  (Etapa 2.5)
  │   ├─ T07 Calibração ......... /calibracao     (Etapa 2.5)
  │   └─ T08 Usuários ........... /usuarios
  │
  │  RODAPÉ DA BARRA: nome e perfil · Trocar senha · Sair
  └────────────────────────────────────────────────────────────────────────

  Atalhos entre telas:
   T02 "últimas ocorrências" (clique) ──► T04 com o modal daquela ocorrência aberto
   T03 "Registrar como ocorrência" ─────► aviso com link "ver em Ocorrências" (T04)
   T05 clique numa barra do gráfico ────► T04 já filtrada (ex.: turno 2, máscara)
   T06 posto "Calibrar" ────────────────► T07 daquele posto
```

---

## 3. Layout base (todas as telas, menos T01)

```
┌──────────────────┬──────────────────────────────────────────────────────────────────────────────┐
│ [capacete]       │ VERIFICADOR DE EPIs DE SOLDA     Posto: [MIG 01 – Linha 3      ▾]   ● ONLINE  │
│ EPI · SOLDA      │                                                                     8,2 FPS   │
│                  ├──────────────────────────────────────────────────────────────────────────────┤
│ OPERAÇÃO         │                                                                              │
│ ▸ Ao vivo        │                                                                              │
│   Ocorrências 18 │                         ( conteúdo da tela )                                 │
│   Analisar arq.  │                                                                              │
│   Painel         │                                                                              │
│                  │                                                                              │
│ ADMINISTRAÇÃO    │                                                                              │
│   Configurações  │                                                                              │
│   Calibração     │                                                                              │
│   Usuários       │                                                                              │
│                  │                                                                              │
│ ──────────────── │                                                                              │
│ Leonardo · ADMIN │                                                                              │
│ Trocar senha     ├──────────────────────────────────────────────────────────────────────────────┤
│ Sair             │ Verificador de EPIs de Solda v2.4 · FSG / Marcopolo · nenhuma pessoa é identificada│
└──────────────────┴──────────────────────────────────────────────────────────────────────────────┘
```
- **Status da câmera** no topo: `● ONLINE 8,2 FPS` (verde) · `⬣ OFFLINE` (vermelho) · `‖ PAUSADA` (cinza). Sempre ícone
  + texto.
- **Tablet e celular** (abaixo de 992 px): a barra lateral vira um menu que abre pelo botão `☰` no topo; o seletor de
  posto e o status ficam numa segunda linha do topo.
- **Avisos (toasts)** no canto inferior direito, lidos pelos leitores de tela (`aria-live`): "Ocorrência validada como
  falso positivo.", "Usuário criado.", "Não foi possível conectar à câmera MIG 01. Tentando de novo…".
- O seletor de posto vale para T02 e T07; nas outras telas o filtro de posto fica na própria página.

---

## 4. Telas

### T01 – Login (`/login`) · Etapa 2.4

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                          │
│                         [capacete de solda, ícone grande]                                │
│                         VERIFICADOR DE EPIs DE SOLDA                                     │
│                         Postos de solda · FSG / Marcopolo                                │
│                                                                                          │
│                   ┌──────────────────────────────────────────────┐                       │
│                   │  Usuário                                     │                       │
│                   │  [______________________________________]    │                       │
│                   │  Senha                                       │                       │
│                   │  [_________________________________] [👁]    │  ← mostrar/ocultar    │
│                   │                                              │                       │
│                   │  [            ENTRAR            ]  (azul)    │                       │
│                   │                                              │                       │
│                   │  ⬣ Usuário ou senha incorretos.              │  ← só quando errar    │
│                   └──────────────────────────────────────────────┘                       │
│                                                                                          │
│          Área monitorada por câmera para verificar o uso de EPIs (NR-6).                 │
│          O sistema não identifica pessoas e as imagens guardadas são borradas.           │
│                                                                                    v2.4  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```
- Após 5 erros: `◆ Muitas tentativas. Tente de novo em 5 minutos.`
- Sessão expirada: `◆ Sua sessão expirou depois de 8 horas sem uso. Entre de novo.`

**Trocar senha (`/trocar-senha`)** – mesmo cartão, obrigatório no 1º acesso do administrador:

```
                   ┌──────────────────────────────────────────────┐
                   │  DEFINA UMA SENHA NOVA                       │
                   │  É o seu primeiro acesso: a senha inicial    │
                   │  do arquivo .env precisa ser trocada.        │
                   │  Senha atual       [____________________]    │
                   │  Nova senha        [____________________]    │
                   │  Repita a nova     [____________________]    │
                   │  · pelo menos 8 caracteres                   │  ← vira ✓ verde ao cumprir
                   │  · diferente do login e da senha atual       │
                   │  [        SALVAR NOVA SENHA        ]         │
                   └──────────────────────────────────────────────┘
```

### T02 – Ao vivo (`/ao-vivo`) · Etapa 2.4 · página inicial

```
┌ (barra lateral) ┬─────────────────────────────────────────────────────────────────────────────────┐
│                 │ AO VIVO · MIG 01 – Linha 3                               14/10/2026 16:41:07   │
│                 │ ┌──────────────────────────────────────────────────────┐ ┌───────────────────┐ │
│                 │ │                                                      │ │ PESSOAS AGORA  2  │ │
│                 │ │                                                      │ │                   │ │
│                 │ │          vídeo ao vivo (MJPEG), com as cabeças       │ │ ┌───────────────┐ │ │
│                 │ │          borradas, caixas coloridas e rótulos        │ │ │#1 ⬣ NÃO CONF. │ │ │
│                 │ │          "#1 SEM MASCARA", "#2 ? MASCARA"            │ │ │[capacete] Más-│ │ │
│                 │ │                                                      │ │ │cara: sem más- │ │ │
│                 │ │                                                      │ │ │cara (rosto    │ │ │
│                 │ │                                                      │ │ │visível)       │ │ │
│                 │ │                                                      │ │ └───────────────┘ │ │
│                 │ │▨▨▨▨▨ ARCO DETECTADO – quadro ignorado (18% estourado) ▨▨│ │ ┌───────────────┐ │ │
│                 │ └──────────────────────────────────────────────────────┘ │ │#2 ◆ INDETERM. │ │ │
│                 │  [‖ Pausar posto]  [⇩ Baixar foto (borrada)]              │ │ │Máscara: rosto │ │ │
│                 │                                                          │ │ │não visível    │ │ │
│                 │ CORDÃO DO TURNO 2 (14:00–22:00)                  agora   │ │ └───────────────┘ │ │
│                 │ 14:00 ███████▓▓▓██████████░░▒▒▒████████▒▒██████████│     │ │                   │ │
│                 │              ▲14:52         ▲15:31     ▲16:05            │ │ ÚLTIMAS           │ │
│                 │ █ conforme ▒ não conforme ░ indeterminado ▲ ocorrência   │ │ OCORRÊNCIAS       │ │
│                 │                                                          │ │ [mini] 16:05:12   │ │
│                 │                                                          │ │  ⬣ Sem máscara #1 │ │
│                 │                                                          │ │ [mini] 15:31:40   │ │
│                 │                                                          │ │  ⬣ Máscara levan- │ │
│                 │                                                          │ │    tada #3        │ │
│                 │                                                          │ │ Ver todas →       │ │
│                 │                                                          │ └───────────────────┘ │
└─────────────────┴─────────────────────────────────────────────────────────────────────────────────┘
```
- O painel da direita é atualizado **a cada 1 segundo** (`/api/status`); o vídeo, pelo stream MJPEG.
- "Pausar posto" só aparece para o ADMIN. O botão vira `▶ Retomar posto` e o vídeo mostra "PAUSADO".
- Sem pessoas: `Ninguém no quadro agora.` Câmera fora do ar: o vídeo vira a faixa `▨ CÂMERA OFFLINE ▨` com
  `Tentando reconectar…`. Modelo ausente: `⬣ Modelo de detecção não encontrado em models/. Fale com o administrador.`
- Disco cheio: `◆ Disco quase cheio: as ocorrências estão sendo registradas sem imagem.`
- Clique numa ocorrência da lista → abre a T04 com o modal dela.
- **Celular:** vídeo na largura toda → "Pessoas agora" → cordão do turno → últimas ocorrências, um embaixo do outro.

### T03 – Analisar arquivo (`/upload`) · Etapa 2.4

```
┌ (barra lateral) ┬─────────────────────────────────────────────────────────────────────────────────┐
│                 │ ANALISAR FOTO OU VÍDEO                                                          │
│                 │ Regras do posto: [MIG 01 – Linha 3 ▾]                                          │
│                 │ ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐  │
│                 │                                                                                │
│                 │ │          Arraste uma foto (.jpg, .png) ou um vídeo (.mp4) para cá            │  │
│                 │            ou  [ Escolher arquivo ]          · até 200 MB                      │
│                 │ └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘  │
│                 │ O arquivo é apagado logo após a análise; o resultado fica disponível por 1 hora. │
│                 │                                                                                 │
│                 │ soldagem_linha3.mp4 · analisando ▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░ 68%                       │
│                 │                                                                                 │
│                 │ RESULTADO                                                    [⇩ Baixar resultado] │
│                 │ ┌──────────────────────────────────────────┐                                    │
│                 │ │  vídeo ou foto anotada, BORRADA          │                                    │
│                 │ │  (player de vídeo do navegador)          │                                    │
│                 │ └──────────────────────────────────────────┘                                    │
│                 │ ┌────────┬──────────────────────────────────────────┬──────────────────────┐    │
│                 │ │ PESSOA │ MÁSCARA                                  │ MÁSCARA LEVANTADA    │    │
│                 │ ├────────┼──────────────────────────────────────────┼──────────────────────┤    │
│                 │ │ #1     │ ⬣ Não conforme · 76% do tempo            │ –                    │    │
│                 │ │ #2     │ ● Conforme · 61% · ◆ 39%                 │ 12 quadros           │    │
│                 │ └────────┴──────────────────────────────────────────┴──────────────────────┘    │
│                 │ OCORRÊNCIAS ENCONTRADAS: 1 (#1 sem máscara)                                      │
│                 │ Arquivos enviados não viram ocorrências oficiais sozinhos.                     │
│                 │ [ Registrar como ocorrência ]                                                    │
└─────────────────┴─────────────────────────────────────────────────────────────────────────────────┘
```
- Erros na própria área de envio: `⬣ Este tipo de arquivo não é aceito. Envie .jpg, .png ou .mp4.` ·
  `⬣ O arquivo tem 340 MB; o limite é 200 MB.` · `⬣ O arquivo não abriu como vídeo. Ele pode estar corrompido.`
- Depois de registrar: o botão vira `✓ 1 ocorrência registrada · ver em Ocorrências`.
- Nenhuma falta encontrada: `● Nenhuma ocorrência encontrada neste arquivo.` (sem o botão de registrar).

### T04 – Ocorrências (`/ocorrencias`) · Etapa 2.4

```
┌ (barra lateral) ┬─────────────────────────────────────────────────────────────────────────────────┐
│                 │ OCORRÊNCIAS                                              [⇩ Exportar CSV]²      │
│                 │ Período [01/10/2026]–[14/10/2026]  Posto [Todos ▾]  EPI [Todos ▾]               │
│                 │ Turno [Todos ▾]  Validação [Pendentes ▾]          [ Filtrar ]  Limpar filtros   │
│                 │                                                                                 │
│                 │ 25 ocorrências no período · 18 pendentes · 5 confirmadas · 2 falsos positivos   │
│                 │ ┌──────┬──────────────┬───────────┬──────────────────┬────────┬──────┬──────┬─────────────┐│
│                 │ │      │ DATA E HORA  │ POSTO     │ EPI FALTANTE     │ INDET. │ LEV. │ CONF.│ VALIDAÇÃO   ││
│                 │ ├──────┼──────────────┼───────────┼──────────────────┼────────┼──────┼──────┼─────────────┤│
│                 │ │[mini]│ 14/10 16:05  │ MIG 01    │ ⬣ Máscara        │ –      │ –    │ 0,91 │ ◆ Pendente  ││
│                 │ │[mini]│ 14/10 15:31  │ MIG 01    │ ⬣ Máscara        │ –      │ sim  │ 0,74 │ ● Confirmada││
│                 │ │[mini]│ 14/10 14:52  │ Corte 01  │ ⬣ Máscara        │ –      │ –    │ –    │ ✕ Falso pos.││
│                 │ │ …    │              │           │                  │        │      │      │             ││
│                 │ └──────┴──────────────┴───────────┴──────────────────┴────────┴──────┴──────┴─────────────┘│
│                 │                         ‹ Anterior   página 1 de 2   Próxima ›                  │
└─────────────────┴─────────────────────────────────────────────────────────────────────────────────┘
```
² A exportação CSV é o RD10 (Etapa 2.5); o botão aparece já na 2.4 desativado, ou só na 2.5 (sua escolha).

**Modal ao clicar numa linha** (teclado: Enter abre, Esc fecha, ← → passa para a anterior/próxima):

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ OCORRÊNCIA · 14/10/2026 16:05:12 · MIG 01 – Linha 3 · Turno 2               [✕] │
│ ┌──────────────────────────────────────────────┐  Pessoa       #1               │
│ │                                              │  Faltou       ⬣ Máscara        │
│ │   imagem da ocorrência, ampliada,            │  Motivo       rosto visível    │
│ │   SEMPRE BORRADA, com a caixa vermelha       │               sem máscara      │
│ │                                              │  Em falta     91% dos 4 s      │
│ │                                              │  Indeterm.    –                │
│ └──────────────────────────────────────────────┘  Origem       ao vivo          │
│                                                    Validação    ◆ Pendente       │
│  [ ✓ Confirmar falta ]  [ ✕ Marcar falso positivo ]  [ ↺ Voltar para pendente ] │
│                                                   [🗑 Excluir] ← só ADMIN, pede confirmação │
└──────────────────────────────────────────────────────────────────────────────────┘
```
- Validada: `● Confirmada por Leonardo em 14/10/2026 16:20`.
- Sem imagem (disco cheio na hora): `◆ Esta ocorrência foi registrada sem imagem (disco cheio).`
- Nada encontrado com os filtros: `Nenhuma ocorrência neste período. Ajuste os filtros ou limpe-os.`
- **Celular:** a tabela vira uma lista de cartões (miniatura à esquerda, data, EPI faltante e validação à direita).

### T05 – Painel (`/dashboard`) · RD04 · Etapa 2.5

```
┌ (barra lateral) ┬─────────────────────────────────────────────────────────────────────────────────┐
│                 │ PAINEL       Período [01/10/2026]–[14/10/2026]   Posto [Todos ▾]   [ Aplicar ]  │
│                 │ ┌────────────────┐ ┌────────────────┐ ┌──────────────────┐ ┌─────────────────┐  │
│                 │ │ HOJE           │ │ NO MÊS         │ │ CONFORMIDADE     │ │ FALSOS POSITIVOS│  │
│                 │ │ 3 ocorrências  │ │ 25 ocorrências │ │ 92% do tempo     │ │ 8% das validadas│  │
│                 │ └────────────────┘ └────────────────┘ └──────────────────┘ └─────────────────┘  │
│                 │ ┌───────────────────────────────────────┐ ┌──────────────────────────────────┐  │
│                 │ │ OCORRÊNCIAS POR DIA (linha)           │ │ CONFORME × NÃO CONF. × INDET.    │  │
│                 │ │      ╱╲    ╱╲                          │ │          (rosca)                 │  │
│                 │ │ ____╱  ╲__╱  ╲___                      │ │                                  │  │
│                 │ └───────────────────────────────────────┘ └──────────────────────────────────┘  │
│                 │ ┌───────────────────────┐ ┌──────────────────────┐ ┌─────────────────────────┐  │
│                 │ │ POR TURNO (empilhadas)│ │ POR POSTO (barras)   │ │ POR EPI: conformidade e │  │
│                 │ │                       │ │                      │ │ % indeterminado         │  │
│                 │ └───────────────────────┘ └──────────────────────┘ └─────────────────────────┘  │
└─────────────────┴─────────────────────────────────────────────────────────────────────────────────┘
```
- "Conformidade" vem de `metricas_sessao` (tempo avaliado), não das ocorrências.
- Todo gráfico tem a tabela de dados abaixo, num "Ver dados" (acessibilidade). Clique numa barra → T04 filtrada.

### T06 – Configurações (`/configuracoes`) · só ADMIN · RD05/RD06 · Etapa 2.5

```
┌ (barra lateral) ┬─────────────────────────────────────────────────────────────────────────────────┐
│                 │ CONFIGURAÇÕES                                                                   │
│                 │ [ Postos e câmeras ] [ EPIs por posto ] [ Sistema ] [ Zona de interesse ]      │
│                 │ ─────────────────────────────────────────────────────────────────────────────  │
│                 │ POSTOS E CÂMERAS                                         [ + Novo posto ]       │
│                 │ ┌──────────────────────┬──────────┬──────────┬──────────────────┬────────────┐ │
│                 │ │ POSTO                │ PROCESSO │ ORIGEM   │ ENDEREÇO         │ ATIVO      │ │
│                 │ ├──────────────────────┼──────────┼──────────┼──────────────────┼────────────┤ │
│                 │ │ MIG 01 – Linha 3     │ MIG/MAG  │ RTSP     │ rtsp://10.0.3.21 │ [■] Editar │ │
│                 │ │ Webcam 0             │ Outro    │ Webcam   │ 0                │ [ ] Editar │ │
│                 │ └──────────────────────┴──────────┴──────────┴──────────────────┴────────────┘ │
│                 │ A senha das câmeras fica no arquivo .env, nunca aqui.                          │
│                 │                                                                                 │
│  aba EPIs por posto:   [✓] Máscara de solda   Confiança mínima  ──●──── 0,45                    │
│                        Tempo em falta para registrar ──●── 4 s    Fração mínima ──●── 75%        │
│                        [ ] Luvas  [ ] Proteção do corpo  [ ] Calçado  [ ] Capacete  (em breve)   │
│  aba Sistema:          Intervalo entre ocorrências (cooldown) 60 s · Guardar imagens por 30 dias │
│                        Tamanho da imagem 640 · Limite do arco 245 / 15% · Turnos · Telegram ****  │
│                        Espaço usado em data/: 1,2 GB de 50 GB  [▓▓░░░░░░░░]                     │
│  aba Zona de interesse: foto atual do posto (borrada) + desenhar o polígono com cliques          │
│                        [ Desfazer ponto ] [ Limpar ] [ Salvar zona ]                             │
└─────────────────┴─────────────────────────────────────────────────────────────────────────────────┘
```
- Toda alteração vale **sem reiniciar** e fica na auditoria. Botão `Salvar alterações` por aba; ao salvar, toast
  `Configurações do posto MIG 01 salvas.`

### T07 – Calibração (`/calibracao`) · só ADMIN · RD02 · Etapa 2.5

```
┌ (barra lateral) ┬─────────────────────────────────────────────────────────────────────────────────┐
│                 │ CALIBRAÇÃO · MIG 01 – Linha 3                                                   │
│                 │ ┌──────────────────────────────────────────────────────┐ ┌───────────────────┐ │
│                 │ │ vídeo com: pontos do corpo, região da cabeça,        │ │ VALORES AGORA     │ │
│                 │ │ linha dos olhos, rosto encontrado (magenta),         │ │ Pessoa #1         │ │
│                 │ │ caixa da máscara e a cobertura (%)                   │ │  altura 412 px    │ │
│                 │ │ (cabeças borradas, como no ao vivo)                  │ │  cobertura 0,62   │ │
│                 │ │                                                      │ │  conf. máscara .81│ │
│                 │ └──────────────────────────────────────────────────────┘ │  rosto: não       │ │
│                 │ Pixels estourados (arco): ▓▓▓░░░░░░░ 9% (limite 15%)      │ Quadro: válido    │ │
│                 │ [ Ajustar limites em Configurações → ]                    └───────────────────┘ │
└─────────────────┴─────────────────────────────────────────────────────────────────────────────────┘
```

### T08 – Usuários (`/usuarios`) · só ADMIN · Etapa 2.4

```
┌ (barra lateral) ┬─────────────────────────────────────────────────────────────────────────────────┐
│                 │ USUÁRIOS                                                    [ + Novo usuário ]  │
│                 │ ┌──────────────────┬────────────┬─────────────┬──────────────┬────────────────┐ │
│                 │ │ NOME             │ LOGIN      │ PERFIL      │ SITUAÇÃO     │                │ │
│                 │ ├──────────────────┼────────────┼─────────────┼──────────────┼────────────────┤ │
│                 │ │ Leonardo         │ admin      │ Administrador│ ● Ativo     │ (você)         │ │
│                 │ │ Ana Souza        │ ana.souza  │ Supervisor  │ ● Ativo      │ Redefinir senha│ │
│                 │ │                  │            │             │              │ Desativar      │ │
│                 │ │ Carlos Lima      │ carlos     │ Supervisor  │ ‖ Desativado │ Reativar       │ │
│                 │ └──────────────────┴────────────┴─────────────┴──────────────┴────────────────┘ │
└─────────────────┴─────────────────────────────────────────────────────────────────────────────────┘
```
**Novo usuário (modal):**
```
  NOVO USUÁRIO
  Nome           [_________________________]
  Login          [_________________________]   letras, números, ponto e hífen
  Perfil         (•) Supervisor – vê e valida   ( ) Administrador – configura tudo
  Senha inicial  [_________________________]   a pessoa troca no primeiro acesso
  [ Cancelar ]                                   [ Criar usuário ]
```
- "Redefinir senha" gera uma senha temporária mostrada **uma vez** na tela, e a pessoa precisa trocá-la no próximo acesso.
- O administrador não pode desativar a si mesmo nem rebaixar o último ADMIN (o sistema ficaria sem administrador).
- Não há "excluir usuário": desativar mantém o histórico de validações e da auditoria.
- Toasts: `Usuário ana.souza criado.` · `Usuário carlos desativado.` · `Senha de ana.souza redefinida.`

---

## 5. O que muda no backend para essas telas (implementado junto com as telas)

| Tela | Necessidade | Rota |
|---|---|---|
| todas | páginas HTML (Jinja2), arquivos locais de Bootstrap, ícones, Chart.js e fontes | `GET /`, `/login`, `/trocar-senha`, `/ao-vivo`, `/upload`, `/ocorrencias`, `/usuarios`; `static/vendor/` |
| todas | sem login, página redireciona para `/login` (a API continua respondendo 401) | — |
| barra lateral | nº de ocorrências pendentes | `GET /api/ocorrencias/resumo` |
| T02 | cordão do turno (estado a cada 10 s, desde o início do turno) e pinos das ocorrências | campo novo em `GET /api/status` |
| T04 | contagens do período (total, pendentes, confirmadas, falsos positivos) | campo novo em `GET /api/ocorrencias` |
| T08 | listar, criar, desativar/reativar, redefinir senha | `GET, POST /api/usuarios` · `POST /api/usuarios/{id}/desativar` · `/reativar` · `/senha` |

---

## 6. Acessibilidade e responsividade (valem para todas as telas)

- Estado sempre com **ícone + forma + texto**; contraste mínimo AA (texto preto sobre o amarelo).
- Navegação completa pelo teclado, com foco visível (contorno azul de 3 px); modal com foco preso e `Esc` para fechar.
- Imagens com texto alternativo (ex.: "Ocorrência de 14/10/2026 16:05, posto MIG 01, imagem com rostos borrados").
- Datas `dd/mm/aaaa HH:mm`, horário de Brasília; números no formato brasileiro (0,91 · 1,2 GB).
- Quem prefere menos movimento (`prefers-reduced-motion`): sem animações na faixa de alerta e nas trocas de estado.
- Telas testadas em 1366 px (notebook), 1024 px (tablet deitado), 768 px (tablet em pé) e 375 px (celular).
