# Revisão LGPD – Verificador de EPIs de Solda (Etapa 2.6)

**Data:** 15/10/2026. **Escopo:** o sistema da Fase 2 (pasta `app/`) com a detecção da Fase 1 (`src/`), na versão 2.5,
e o material dos testes de campo e do treinamento.

> **Importante:** esta é uma revisão **técnica**, feita pela equipe do projeto, sobre o que o software faz com os
> dados. **Não é parecer jurídico.** Antes de usar o sistema com trabalhadores de uma empresa, ela deve ser validada
> pelo encarregado de dados (DPO) e pelo jurídico da empresa, que decidem a base legal e a política de uso.

Lei Geral de Proteção de Dados: Lei nº 13.709/2018 ("LGPD"). Os artigos citados são os da lei.

---

## 1. Resumo

| Requisito do projeto | Situação | Onde está garantido |
|---|---|---|
| RF26 – sem reconhecimento facial nem biometria; não identifica pessoas | ✅ | os rostos são só **localizados** (YuNet) para serem borrados; nenhuma tabela tem nome, matrícula ou característica do rosto (`app/models.py`) |
| RF27 – blur depois da inferência e antes de gravar ou enviar; imagem original nunca salva; blur preventivo da cabeça | ✅ | `app/privacy.py` (`ImagemBorrada`) e `app/storage.py` (só aceita imagem borrada); testes em `tests/test_fase2_privacidade.py` e `tests/test_fase2_storage.py` |
| RF28 – sem vídeo contínuo; só os quadros das ocorrências | ✅ | o vídeo ao vivo só existe na memória; grava-se uma foto borrada por ocorrência (`app/registro.py`) |
| RF29 – retenção configurável com exclusão automática | ✅ | rotina das 03:00 (`app/scheduler.py`), prazo na tela Configurações; teste `test_retencao_apaga_imagens_e_registros_antigos_e_audita` |
| RF30 – aviso de monitoramento e termo de autorização | ✅ | `docs/modelos/aviso_monitoramento.md` (e `.pdf`) e `docs/modelos/termo_autorizacao.md` |
| RNF04 – logs com rotação e sem dados pessoais | ✅ | `app/config.py` (5 arquivos de 5 MB); os logs têm postos, códigos e erros, nunca dados de trabalhadores |
| RNF05 – cookies protegidos, CSRF, validação de upload, segredos no .env | ✅ | `app/auth.py`, `app/main.py` (cookie HttpOnly e SameSite, política de conteúdo das páginas), `app/uploads.py` |

**Conclusão técnica:** o sistema foi construído com **privacidade por padrão** (art. 46, § 2º): ele não identifica
ninguém, guarda o mínimo, borra antes de gravar, apaga sozinho e roda dentro da empresa. Ainda assim, as fotos e os
registros podem ser ligados a uma pessoa **pelo contexto** (posto, horário, turno, roupa). Por isso devem ser
tratados como **dados pessoais** (pseudonimizados, não anonimizados; art. 12), e a empresa precisa cumprir as
pendências da seção 9.

---

## 2. Que dados o sistema trata

| Dado | Exemplo | Onde fica | Por quanto tempo | Quem acessa | É dado pessoal? |
|---|---|---|---|---|---|
| Vídeo ao vivo | imagem da câmera do posto | só na memória (nunca gravado); na tela, com as cabeças borradas | enquanto é exibido | ADMIN e SUPERVISOR logados | sim, enquanto exibido |
| Foto da ocorrência e miniatura | quadro **borrado** com as caixas desenhadas | `data/ocorrencias/` e `data/thumbnails/` | retenção (padrão 30 dias) | ADMIN e SUPERVISOR, pela rota com login `/midia` | sim, pelo contexto |
| Registro da ocorrência | data e hora, posto, turno, número temporário (#3), falta, confiança, arco aceso, validação | banco (`data/db/`) | retenção (30 dias) + até 7 dias nos backups | ADMIN e SUPERVISOR | sim, pelo contexto |
| Métricas de sessão | quantos quadros conformes, não conformes e indeterminados | banco | sem prazo | ADMIN e SUPERVISOR (Painel) | não (só contagens) |
| Usuários do sistema | nome, login, perfil, senha em hash bcrypt | banco | enquanto existirem (não há exclusão, só desativação) | ADMIN | sim (dos supervisores) |
| Auditoria | quem entrou, validou, excluiu, exportou, mudou configuração; logins errados | banco | **sem prazo hoje** (pendência 9.6) | banco (sem tela) | sim (dos usuários) |
| Logs | erros, câmeras ligadas, ocorrências registradas (código) | `data/logs/` | rotação de 25 MB | quem acessa o computador | não |
| Arquivo enviado na tela "Analisar arquivo" | foto ou vídeo trazido pelo usuário | `data/uploads_temp/` | **apagado logo após a análise**; o resultado borrado, em até 1 h | quem enviou (e o ADMIN) | sim |
| Exportações | CSV das ocorrências, PDF mensal (sem imagens) | onde o usuário salvar | fora do controle do sistema | quem baixou | o CSV, sim, pelo contexto |
| Alerta do Telegram (opcional) | foto **borrada** + texto da falta | servidores do Telegram (fora do Brasil) | regras do Telegram | membros da conversa | sim, pelo contexto |
| Material de testes e treino | vídeos de banco de imagens (Pexels), vídeo da webcam da equipe, datasets públicos | `testes_campo/`, `dados/` (fora do git, no computador da equipe) | até o fim do projeto | equipe do projeto | sim, nos vídeos de pessoas |

**O que nunca é guardado:** imagem ou vídeo sem blur, vídeo contínuo, recorte de rosto, características do rosto
(embeddings), nome ou matrícula de quem foi filmado.

---

## 3. Princípios da LGPD (art. 6º) no sistema

| Princípio | Como o sistema atende |
|---|---|
| Finalidade e adequação | serve só para verificar o uso da máscara de solda (segurança do trabalho, NR-6) e medir a conformidade do setor |
| Necessidade (minimização) | uma foto borrada por ocorrência, só quando a falta dura 4 s; contagens agregadas no lugar de imagens; sem identificação; zona de interesse para não avaliar quem passa fora do posto |
| Livre acesso e transparência | aviso de monitoramento no setor (RF30) e na tela de login; este documento |
| Qualidade dos dados | cada ocorrência pode ser validada (Confirmada / Falso positivo); o sistema não acusa sem evidência (indeterminado não gera ocorrência) |
| Segurança e prevenção | login, perfis, CSRF, senhas em hash, blur garantido no código, dados dentro da empresa (seção 6) |
| Não discriminação | não há identificação nem perfil de pessoas; a política de uso deve impedir punição baseada só no sistema (seção 8) |
| Responsabilização | auditoria de login, validação, exclusão, exportação e mudança de configuração (RF25) |

---

## 4. Base legal (sugestão para o jurídico)

- **Cumprimento de obrigação legal ou regulatória** (art. 7º, II): a empresa deve cumprir e fazer cumprir as normas
  de segurança do trabalho (CLT, art. 157) e exigir o uso do EPI (NR-6). Verificar o uso da máscara é uma forma de
  cumprir essa obrigação.
- **Legítimo interesse** (art. 7º, IX, e art. 10) para as estatísticas de conformidade e a melhoria do sistema, com a
  avaliação de impacto da seção 9.
- O **consentimento** não é recomendado como base principal: na relação de trabalho ele não é livre o bastante.
- **Dados sensíveis** (art. 11): o sistema **não** trata biometria. O detector de rostos só encontra onde há um rosto
  para borrá-lo; não compara, não reconhece e não guarda nada do rosto (RF26).

---

## 5. Direitos dos titulares (art. 18)

O sistema não sabe quem é cada pessoa, então não dá para buscar "as ocorrências do João". Para atender um pedido:

| Direito | Como atender |
|---|---|
| Confirmação e acesso | localizar pelo posto, dia e horário em **Ocorrências** e mostrar a imagem borrada |
| Correção | marcar como **Falso positivo** (fica registrado quem validou e quando) |
| Eliminação | o ADMIN **exclui** a ocorrência (imagem e registro; a exclusão fica na auditoria); a retenção apaga tudo depois do prazo |
| Informação | aviso de monitoramento, este documento e a política de uso da empresa |

---

## 6. Segurança (art. 46)

**Já implementado:**

- Login obrigatório em todas as telas, rotas e imagens (RF23, RF24); perfis ADMIN e SUPERVISOR; sessão de 8 horas.
- Senhas com bcrypt; bloqueio depois de 5 senhas erradas; troca obrigatória da senha inicial.
- Proteção contra CSRF nas ações; cookie HttpOnly e SameSite; páginas sem scripts de fora (política de conteúdo).
- Imagens só pela rota com login, nunca por arquivo público; nomes aleatórios (UUID).
- Blur garantido pelo tipo `ImagemBorrada`: o armazenamento recusa qualquer imagem que não passou pelo blur.
- Upload: tipo e tamanho conferidos; o arquivo original é apagado logo após a análise.
- Segredos (chave do login, senha das câmeras, token do Telegram) só no `.env`, fora do git; o token nunca aparece
  inteiro na tela nem no log.
- Exportação CSV protegida contra fórmulas maliciosas; o relatório PDF não tem imagens.
- Auditoria das ações (RF25).

**Recomendado à empresa** (fora do software):

- Criptografar o disco do computador do sistema (BitLocker) e restringir o acesso físico a ele.
- Usar o sistema só na rede interna; para acesso de fora, HTTPS com um proxy e `COOKIE_SEGURO=true`.
- Liberar a porta só para a rede dos supervisores (Firewall do Windows) e manter o Windows atualizado.
- Guardar as cópias da pasta `data/` em local também protegido.
- Desativar na hora o usuário de quem sair da função.

---

## 7. Transferência internacional: alerta pelo Telegram (art. 33)

O alerta pelo Telegram é **opcional e desligado** enquanto não houver token no `.env`. Quando ligado, a foto
**borrada** e o texto da falta vão para os servidores do Telegram, fora do Brasil. Antes de ligar:

- avaliar com o encarregado se a transferência é aceitável (art. 33) e registrá-la na avaliação de impacto;
- usar uma conversa ou grupo só com as pessoas autorizadas;
- lembrar que o que chega ao Telegram sai do controle da retenção do sistema.

Alternativa sem transferência: não usar o Telegram e acompanhar o número de pendentes na barra lateral do sistema.

---

## 8. Riscos que continuam e como reduzir

| Risco | Redução |
|---|---|
| **Reidentificação pelo contexto**: posto + horário + turno + roupa podem indicar quem estava ali | acesso só para supervisores autorizados; retenção curta; tratar como dado pessoal |
| **Uso disciplinar** de uma ocorrência sem conferência | política de uso: o sistema **orienta**, não pune sozinho; toda ocorrência é validada por uma pessoa (o modelo erra: ver as limitações do README) |
| **Falso positivo** atribuído a alguém | validação manual; "Falso positivo" fica registrado; o sistema prefere não acusar (indeterminado) |
| **Vídeo ao vivo sem blur** se alguém desligar `privacidade.borrar_ao_vivo` | manter `true` (padrão); a mudança só é possível no `config.yaml` |
| **Exportações** (CSV) circulando fora do sistema | exportação registrada na auditoria; orientar os supervisores |
| **Câmera filmando além do posto** | zona de interesse; posicionamento (README, seção 8); nunca filmar áreas privadas |
| **Material dos testes de campo** com pessoas reais | fora do git, só no computador da equipe; apagar ao fim do projeto; usar em trabalhos só com rostos borrados |

---

## 9. O que a empresa precisa fazer antes de usar

1. **Encarregado (art. 41):** indicar quem responde pelos dados do sistema e colocar o contato no aviso.
2. **Relatório de impacto (RIPD, art. 38):** registrar a finalidade, a base legal, os riscos da seção 8 e as medidas.
   As seções 2 a 8 deste documento servem de ponto de partida.
3. **Transparência:** afixar o aviso de monitoramento no setor (`docs/modelos/aviso_monitoramento.pdf`), informar os
   trabalhadores antes de ligar as câmeras e envolver a CIPA e, se for o caso, a representação dos trabalhadores.
4. **Política de uso:** quem pode acessar, para que serve (prevenção e estatística), que nenhuma medida disciplinar é
   tomada só com base no sistema e como os trabalhadores podem pedir informações.
5. **Retenção:** confirmar os 30 dias (ou outro prazo) na tela Configurações → Sistema.
6. **Auditoria e usuários:** definir por quanto tempo guardar a auditoria (hoje não há prazo) e revisar os usuários
   ativos de tempos em tempos.
7. **Registro das operações (art. 37)** e **procedimento de incidente (art. 48):** incluir o sistema nos controles da
   empresa (quem avisar se o computador for perdido ou invadido).
8. **Termo de autorização** do projeto acadêmico assinado (`docs/modelos/termo_autorizacao.md`) antes do piloto.

---

## 10. Pesquisa acadêmica e testes de campo

- Gravações para testes e treino (RF33) só com o termo assinado pela empresa e a ciência prévia dos trabalhadores.
- **Ninguém deve soldar sem máscara para uma gravação.** Situações de falta são simuladas sem arco aceso, ou com
  vídeos de banco de imagens.
- Os vídeos originais ficam só no computador da equipe (`testes_campo/`, fora do git) e são apagados ao fim do
  projeto. Em relatórios, artigos e apresentações, só imagens borradas.
- Os datasets públicos usados no treino têm licença CC BY 4.0 e estão atribuídos no README.

---

## 11. Melhorias futuras sugeridas

- Prazo configurável para a auditoria e para os registros de usuários desativados.
- Opção de alerta do Telegram só com texto (sem a foto).
- Tela de auditoria para o ADMIN (hoje a auditoria fica só no banco).
- Criptografia das imagens guardadas, para os casos em que o disco não puder ser criptografado.
