# Modelo de aviso de monitoramento (RF30)

Para afixar **na entrada do setor de solda e em cada posto com câmera**, em local visível, antes de ligar as câmeras.
Preencha os campos entre colchetes. Versão pronta para imprimir (A4, com os campos em branco):
`docs/modelos/aviso_monitoramento.pdf` (gerada por `ferramentas/gerar_aviso.py`).

> Modelo preparado pela equipe do projeto. Revise o texto com o encarregado de dados e o jurídico da empresa.

---

## ÁREA MONITORADA POR CÂMERA

### Verificação do uso da máscara de solda (NR-6)

**Por quê?** Para prevenir acidentes. A máscara de solda protege os olhos e o rosto da radiação do arco, dos
respingos e das faíscas.

**O que o sistema faz:** verifica se a máscara de solda está sendo usada no posto. Quando ela falta por mais de
alguns segundos, o sistema guarda **uma foto com o rosto borrado** para o responsável pela segurança conferir.

**O que o sistema NÃO faz:**

- não reconhece rostos e não identifica pessoas (sem nome, sem matrícula);
- não grava vídeo contínuo;
- não guarda nenhuma imagem sem borrar;
- não envia imagens para fora da empresa [ou: envia um alerta com a foto borrada pelo Telegram para os responsáveis].

**Por quanto tempo:** as fotos e os registros são apagados automaticamente depois de **[30] dias**.

**Quem acessa:** [setor de segurança do trabalho / supervisores autorizados].

**Dúvidas e seus direitos (LGPD – Lei nº 13.709/2018):** fale com [nome do encarregado de dados],
[e-mail / ramal].

[Nome da empresa] · Projeto de extensão [FSG / nome da instituição]
