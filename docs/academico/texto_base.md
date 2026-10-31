# Texto-base para o trabalho acadêmico (Etapa 2.7)

Texto de partida para as seções **Metodologia**, **Resultados** e **Limitações** do relatório ou artigo do projeto.
Adapte ao modelo da FSG (numeração, normas ABNT, tempo verbal). Os números vêm dos documentos do projeto, citados
entre parênteses. **O que depende do piloto na empresa está marcado como [PREENCHER]**: nada foi inventado.

---

## Metodologia

### Tipo de pesquisa e escopo

Trata-se de uma pesquisa aplicada, de caráter extensionista, com desenvolvimento de um protótipo e avaliação
experimental. O objetivo é verificar, por visão computacional, o uso do equipamento de proteção individual (EPI) no
posto de soldagem, conforme a NR-6. O escopo foi restringido a **um EPI, a máscara de solda**, por orientação
docente: é o EPI mais crítico do processo e o mais visível para a câmera, e o primeiro treino com cinco classes
mostrou poucos exemplos de máscara e métricas pouco confiáveis para luvas e calçado
(`docs/resultados_treino/README.md`, rodada v1). Luvas, proteção do corpo, calçado e capacete ficaram como trabalho
futuro.

O trabalho foi dividido em duas fases: **Fase 1**, validação da detecção por linha de comando; e **Fase 2**,
construção do sistema completo (servidor web, banco de dados, telas, privacidade) somente após a validação.

### Dados

Foram usados conjuntos públicos do Roboflow Universe com licença CC BY 4.0 (`docs/dataset_welding_ppe.md`):
Welding-PPE, Welding Helmet, welder e safeweld. As classes originais foram unificadas na classe interna `mascara`, e
as versões foram geradas sem as transformações automáticas dos conjuntos originais ("Isolate Objects", "Stretch" e
augmentations), que distorciam as imagens. Imagens sem máscara entraram como **exemplos negativos**: pessoas do COCO
2017 (rodada v3) e quadros de vídeos do Pexels de pessoas sem máscara em ambiente de solda (rodada v5), estes só no
conjunto de treino. A divisão em treino, validação e teste foi feita no notebook, de forma estratificada; os quadros
vindos de sequências de vídeo ficaram só no treino, para não haver quadros quase iguais entre treino e teste. Uma ferramenta própria
(`ferramentas/conferir_vazamento.py`) conferiu, por similaridade de imagem, que nenhum quadro de treino veio dos
vídeos usados nos testes de campo.

Foram feitas cinco rodadas de treino (`docs/dataset_welding_ppe.md`, seção 5). A versão final (v5) usou 4.678 imagens
de treino, 909 de validação e 455 de teste (imagens originais), além de 724 cópias escurecidas dos quadros negativos
no treino.

### Modelos e treinamento

O detector de máscara é um YOLOv8n (Ultralytics), treinado no Google Colab e no Kaggle a partir de pesos pré-treinados,
com imagens de 640 pixels e parada antecipada (87 épocas na v5). As métricas no conjunto de teste foram precisão,
recall, mAP@0.5 e mAP@0.5:0.95, além da taxa de falso positivo em pessoas sem máscara do COCO.

Para localizar as pessoas e as regiões do corpo usou-se o YOLOv8n-pose (17 pontos do corpo), com rastreamento
ByteTrack, que dá a cada pessoa um número temporário. Um detector de rostos (YuNet, OpenCV Zoo) indica se o rosto
está descoberto.

### Regras de decisão

A região da cabeça é estimada pelas orelhas e pelos ombros, sem exigir os olhos, que a máscara abaixada encobre. Cada
pessoa recebe um de três estados (`docs/plano_fase1.md`): **conforme** (máscara na região da cabeça),
**não conforme** (rosto descoberto sem máscara, ou máscara levantada) e **indeterminado** (cabeça não visível, pessoa
de costas, rosto coberto sem máscara detectada). O estado indeterminado nunca gera ocorrência: o sistema prefere não
acusar sem evidência.

Uma **ocorrência** só é registrada quando a falta aparece em pelo menos 75% dos quadros de uma janela de 4 segundos.
Depois disso, a mesma pessoa só gera outra após 60 segundos. Quadros com mais de 15% de pixels estourados pelo arco
elétrico são ignorados. Na Fase 2 foram acrescentadas a votação temporal da exibição, a detecção de solda ativa pelo
brilho perto das mãos e a zona de interesse do posto (`docs/arquitetura_fase2.md`, decisões F2-D29 a F2-D31).

### Testes de campo (Fase 1)

Foram avaliados 28 trechos de 21 vídeos de banco de imagens (Pexels) e de um vídeo gravado com a webcam da equipe,
classificados quadro a quadro quanto à situação da máscara, à distância, ao ângulo e ao arco
(`docs/resultados_testes_campo.md`). As métricas práticas foram o **recall da ausência** (proporção de situações de
falta em que o sistema registrou a ocorrência) e a **proporção de falsos positivos** entre as ocorrências, conferidas
por revisão manual. Para o recall foi calculado o intervalo de confiança de 95% de Wilson. O desempenho foi medido em
quadros por segundo (FPS) em um processador AMD Ryzen 5 5600, sem placa de vídeo.

### Sistema completo (Fase 2)

O sistema foi desenvolvido em Python, com FastAPI no servidor, SQLite (SQLAlchemy e Alembic) para os dados, telas em
HTML com Bootstrap e Chart.js guardados localmente e rotinas automáticas (APScheduler) para retenção, backup e
relatório mensal. A privacidade foi tratada desde o projeto: o código só permite gravar imagens que passaram pelo blur
das cabeças e rostos; não há reconhecimento facial nem vídeo contínuo; os dados ficam no computador da empresa
(`docs/revisao_lgpd.md`). O sistema foi verificado com testes automáticos (pytest) que simulam pessoas, máscaras e
câmeras.

### Piloto e comparação antes x depois

[PREENCHER: período do piloto, postos, quantidade de câmeras, turnos acompanhados.]

O piloto prevê dois períodos: **antes**, com as câmeras ligadas em observação (sem alertas e sem cobrança), e
**depois**, com o sistema em uso e após a palestra de conscientização. Os indicadores (ocorrências por 100 horas de
câmera, conformidade da máscara, proporção de indeterminados, acerto do sistema nas ocorrências validadas e, como
conferência, observação manual em horários sorteados) são registrados semanalmente na planilha
`docs/academico/planilha_antes_depois.xlsx`.

### Aspectos éticos

O projeto seguiu a LGPD (Lei nº 13.709/2018): o sistema não identifica pessoas, as imagens guardadas são borradas e
apagadas após o prazo de retenção, e os trabalhadores são informados por aviso no setor. As gravações dependem do
termo de autorização da empresa (`docs/modelos/termo_autorizacao.md`). Nenhuma pessoa soldou sem máscara para as
gravações: as situações de falta vieram de vídeos de banco de imagens ou foram simuladas com o arco apagado.

---

## Resultados

### Treinamento do detector de máscara

| Rodada | Dados (treino / validação / teste) | Precisão | Recall | mAP@0.5 | Falso positivo em pessoas (COCO) |
|---|---|---|---|---|---|
| v3 | 2.063 / 590 / 295 | 0,872 | 0,736 | 0,855 | 2,1% |
| v4 | 4.316 / 909 / 455 | 0,931 | 0,928 | 0,946 | 0,6% |
| **v5** | 4.678 / 909 / 455 | **0,948** | 0,931 | **0,945** | **0%** |

Fonte: `docs/resultados_treino/README.md`. A v4 e a v5 usam o mesmo conjunto de teste, o que permite comparação
direta. Por fonte, o mAP@0.5 da v5 foi de 0,943 no Welding Helmet, 0,940 no welder e 0,967 no safeweld. O mAP@0.5
de 0,945 supera a meta boa do projeto (0,75).

### Testes de campo

| Métrica | Meta | Resultado (v5) |
|---|---|---|
| Recall da ausência | ≥ 70% | **82%** (9 de 11; IC 95% de 52% a 95%) |
| Falsos positivos entre as ocorrências | ≤ 30% | **0%** (0 de 16; limite superior de 19%) |
| Testes sem falta com alarme falso | – | 0 de 12 |

| Condição | Recall |
|---|---|
| Até 2 m / de 2 a 4 m | 80% / 83% |
| De frente / de perfil | 83% / **50%** |
| Arco apagado / aceso | 80% / 100% |

Fonte: `docs/relatorio_validacao_fase1.md`, seção 4. As três falhas foram: cabeça baixa no escuro, máscara levantada
vista de perfil e ajudantes com respirador cobrindo o rosto; em todas o sistema ficou **indeterminado**, sem acusar
errado. A máscara corretamente abaixada foi confirmada como conforme em 19% do tempo, em média; no restante ficou
indeterminada, nunca não conforme. Entre as versões, a v5 reduziu o "verde falso" (conforme para quem está sem
máscara) de 7,3% (v4) para 1,3% do tempo.

### Desempenho

Em CPU, com imagens de 640 pixels, o processamento atingiu **12,5 FPS** (80 ms por quadro), acima do mínimo de 5 FPS.
Com 960 pixels no detector de máscara, 9,2 FPS (`docs/relatorio_validacao_fase1.md`, seção 4.3). No sistema
completo, um vídeo 4K com o blur ao vivo foi processado a cerca de 7,7 FPS.

### Sistema completo

O sistema entregue tem monitoramento ao vivo com as cabeças borradas, registro de ocorrências com foto borrada,
validação pelos supervisores, painel com gráficos, configuração por posto (inclusive a zona de interesse),
calibração no local, análise de arquivos, exportação CSV, relatório mensal em PDF e alerta opcional pelo Telegram.
Foram escritos 313 testes automáticos, todos aprovados na versão final (`README.md`, seção 12).

### Piloto: antes x depois

[PREENCHER com a aba "Antes x Depois" da planilha.]

| Indicador | Antes | Depois | Variação |
|---|---|---|---|
| Ocorrências por 100 h de câmera | [ ] | [ ] | [ ] |
| Conformidade da máscara | [ ] | [ ] | [ ] |
| Indeterminado | [ ] | [ ] | [ ] |
| Acerto do sistema nas validadas | [ ] | [ ] | [ ] |
| Sem máscara na observação manual | [ ] | [ ] | [ ] |

[PREENCHER: interpretação. Cuidado: com poucas semanas, mudanças de turno, de pessoas ou de produção também alteram
os números; o efeito do sistema e o da palestra não podem ser separados neste desenho.]

---

## Limitações

1. **Um único EPI.** Só a máscara de solda foi treinada e validada; luvas, proteção do corpo, calçado e capacete não
   são verificados.
2. **Confirmação parcial da conformidade.** A máscara corretamente usada é confirmada em apenas 19% do tempo; no
   restante o estado é indeterminado. O sistema não acusa errado, mas também não confirma.
3. **Ângulo e visibilidade.** De perfil, o recall foi de 50%; cabeça baixa no escuro, costas e respirador levam ao
   estado indeterminado, o que reduz o recall por escolha de projeto.
4. **Máscara levantada.** Não é reconhecida de perfil e, de frente, aparece como "sem máscara" (a consequência, uma
   ocorrência, é a mesma).
5. **Amostra de validação pequena e não representativa do posto real.** Onze situações de falta (intervalo de
   confiança do recall de 52% a 95%), vídeos de banco de imagens, sem testes acima de 4 m e sem o ambiente real
   (câmera, iluminação e fumos da empresa). [PREENCHER se o piloto ampliar a amostra.]
6. **Arco elétrico.** O filtro de quadros estourados e a detecção de solda ativa não foram exercitados com arco real
   ao vivo; os limites precisam ser calibrados no posto.
7. **Rastreamento.** A troca do número temporário de uma pessoa com os clarões do arco pode duplicar ocorrências.
8. **Dados de treino.** Muitas fotos de produto e da web, conferidas por amostragem.
9. **Infraestrutura.** Testado com até duas câmeras em um computador sem placa de vídeo, sem HTTPS próprio e com
   banco SQLite; o uso contínuo em produção exigiria avaliação de carga, segurança de rede e licenciamento
   (o Ultralytics YOLO é AGPL-3.0).
10. **Desenho do piloto.** A comparação antes x depois não tem grupo de controle; o efeito do sistema e o da palestra
    aparecem juntos. [PREENCHER/ajustar conforme o piloto realizado.]
11. **Aspecto legal.** A revisão de privacidade é técnica, feita pela equipe; não substitui a análise jurídica da
    empresa.

---

## Trabalhos futuros

- Ajuste fino com imagens do próprio posto (máscaras abaixadas e levantadas de vários ângulos; pessoas sem máscara
  no mesmo ambiente), conforme o planejamento em `docs/dataset_welding_ppe.md`, seção 8.
- Inclusão dos demais EPIs, com dados próprios, e dos requisitos RD07 e RD08.
- Avaliação com mais câmeras, arco real e por mais tempo; estudo com grupo de controle.
- Posto de validação na entrada do setor de solda (sugestão do professor da disciplina): a câmera confere se a pessoa
  tem a máscara antes de começar o trabalho, em vez de acompanhar o turno inteiro. Exige aceitar a máscara levantada
  como conforme e dar a resposta na hora; não substitui o monitoramento no posto, que é o foco deste trabalho.

---

## Referências sugeridas (conferir e formatar em ABNT)

- BRASIL. Lei nº 13.709, de 14 de agosto de 2018. Lei Geral de Proteção de Dados Pessoais (LGPD).
- BRASIL. Ministério do Trabalho e Emprego. Norma Regulamentadora nº 6 (NR-6) – Equipamento de Proteção Individual.
- JOCHER, G.; CHAURASIA, A.; QIU, J. Ultralytics YOLOv8. 2023. Disponível em: https://github.com/ultralytics/ultralytics.
- ZHANG, Y. et al. ByteTrack: multi-object tracking by associating every detection box. ECCV, 2022.
- WU, W.; PENG, H.; YU, S. YuNet: a tiny millisecond-level face detector. Machine Intelligence Research, 2023.
- LIN, T.-Y. et al. Microsoft COCO: common objects in context. ECCV, 2014.
- WILSON, E. B. Probable inference, the law of succession, and statistical inference. Journal of the American
  Statistical Association, 1927.
- Conjuntos de dados do Roboflow Universe: ver `README.md`, seção 16.
