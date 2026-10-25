"""Relatório mensal em PDF (RD10): o resumo de um mês, para imprimir ou mandar por e-mail.

Usa a mesma conta do Painel (app/estatisticas.py). Não tem nenhuma imagem de pessoa: só números, por dia, turno e
posto. Gerado na hora (Painel -> "Relatório do mês") e, no dia 1º de cada mês, o do mês anterior fica guardado em
data/relatorios/.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session, sessionmaker

from app import VERSAO
from app.estatisticas import SEM_TURNO, resumo_do_periodo
from app.tempo import agora_utc, hoje_local, para_local

log = logging.getLogger("epi_solda.relatorios")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
# Cores do relatório: aço (títulos e cabeçalhos), grafite (textos), linha das tabelas e azul das barras.
ACO, GRAFITE, LINHA, SERIE = (colors.HexColor(c) for c in ("#1E2933", "#4A5661", "#D5DBE1", "#2A78D6"))


def ultimo_dia(mes: date) -> date:
    """Último dia do mês de `mes`: vai ao dia 28, soma 4 dias (sempre cai no mês seguinte), vai ao dia 1º, volta 1."""
    proximo = (mes.replace(day=28) + timedelta(days=4)).replace(day=1)
    return proximo - timedelta(days=1)


def _pct(fracao: float | None) -> str:
    """Fração (0 a 1) como porcentagem inteira, no padrão brasileiro; '—' quando não há dados (None)."""
    return "—" if fracao is None else f"{fracao * 100:.0f}%".replace(".", ",")


def _numero(n: int) -> str:
    """Inteiro com ponto como separador de milhar (padrão brasileiro)."""
    return f"{n:,}".replace(",", ".")


def _tabela(linhas: list[list], larguras: list[float], numericas: int = 1) -> Table:
    """Tabela com cabeçalho em aço e as últimas `numericas` colunas alinhadas à direita."""
    tabela = Table(linhas, colWidths=larguras, repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACO), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (-numericas, 0), (-1, -1), "RIGHT"), ("LINEBELOW", (0, 1), (-1, -1), 0.5, LINHA),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabela


def _grafico_por_dia(por_dia: list[dict]) -> Drawing:
    """Barras de ocorrências por dia (uma série só, sem legenda)."""
    desenho = Drawing(17 * cm, 5.5 * cm)
    grafico = VerticalBarChart()
    grafico.x, grafico.y, grafico.width, grafico.height = 1.2 * cm, 1 * cm, 15.5 * cm, 4 * cm
    grafico.data = [[d["total"] for d in por_dia]]
    # O rótulo de cada barra é só o dia do mês (de AAAA-MM-DD fica DD).
    grafico.categoryAxis.categoryNames = [d["dia"][8:10] for d in por_dia]
    grafico.categoryAxis.labels.fontSize = 6
    grafico.categoryAxis.labels.fontName = "Helvetica"
    grafico.categoryAxis.strokeColor = LINHA
    grafico.valueAxis.valueMin = 0
    # O `+ [1]` evita máximo zero (e passo zero no eixo) quando o mês não teve ocorrências.
    maximo = max([d["total"] for d in por_dia] + [1])
    grafico.valueAxis.valueStep = max(1, round(maximo / 4))
    grafico.valueAxis.labels.fontSize = 7
    grafico.valueAxis.labels.fontName = "Helvetica"
    grafico.valueAxis.strokeColor = LINHA
    grafico.valueAxis.gridStrokeColor = LINHA
    grafico.valueAxis.visibleGrid = True
    grafico.bars[0].fillColor = SERIE
    grafico.bars[0].strokeColor = None
    grafico.barSpacing = 1
    desenho.add(grafico)
    desenho.add(String(1.2 * cm, 0.2 * cm, "dia do mês", fontName="Helvetica", fontSize=7, fillColor=GRAFITE))
    return desenho


def gerar_relatorio_mensal(fabrica: sessionmaker[Session], turnos: dict[str, str], mes: date,
                           camera_id: int | None = None, nome_posto: str | None = None) -> bytes:
    """PDF do mês de `mes` (qualquer dia dele), de todos os postos ou de um só."""
    inicio, fim = mes.replace(day=1), ultimo_dia(mes)
    dados = resumo_do_periodo(fabrica, turnos, inicio, fim, camera_id)
    c = dados["cartoes"]  # totais e taxas do mês
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=estilos["Title"], alignment=TA_LEFT, textColor=ACO, fontSize=18,
                            spaceAfter=2)
    subtitulo = ParagraphStyle("sub", parent=estilos["Normal"], textColor=GRAFITE, fontSize=10, spaceAfter=10)
    secao = ParagraphStyle("secao", parent=estilos["Heading2"], textColor=ACO, fontSize=12, spaceBefore=12,
                           spaceAfter=6)
    texto = ParagraphStyle("texto", parent=estilos["Normal"], fontSize=9, leading=12, textColor=ACO)
    nota = ParagraphStyle("nota", parent=texto, textColor=GRAFITE, fontSize=8, leading=10)

    validadas = c["validadas"]
    resumo = [["Indicador", "Valor"],
              ["Ocorrências registradas no mês", _numero(c["periodo"])],
              ["Com o arco aceso (solda em andamento)", _numero(c["com_arco"])],
              ["Validadas: confirmadas / falsos positivos", f"{_numero(c['confirmadas'])} / "
                                                            f"{_numero(validadas - c['confirmadas'])}"],
              ["Esperando validação", _numero(c["pendentes"])],
              ["Acerto do sistema nas validadas (confirmadas ÷ validadas)",
               _pct(c["confirmadas"] / validadas if validadas else None)],
              ["Conformidade da máscara (pessoas avaliadas, quadro a quadro)", _pct(c["conformidade"])],
              ["Avaliações indeterminadas (de costas, cabeça fora do quadro)", _pct(c["indeterminado"])]]
    turnos_linhas = [["Turno", "Sem máscara", "Máscara levantada", "Total"]] + [
        ["Sem turno" if t["turno"] == SEM_TURNO else f"Turno {t['turno']}", _numero(t["sem_mascara"]),
         _numero(t["levantada"]), _numero(t["sem_mascara"] + t["levantada"])] for t in dados["por_turno"]]
    postos_linhas = [["Posto", "Ocorrências"]] + [[p["posto"], _numero(p["total"])] for p in dados["por_posto"]]

    # Conteúdo do PDF, na ordem em que aparece na página (o Platypus empilha os itens).
    historia = [
        Paragraph("Relatório mensal: uso da máscara de solda", titulo),
        Paragraph(f"{MESES[inicio.month - 1].capitalize()} de {inicio.year} · {nome_posto or 'todos os postos'} · "
                  f"Verificador de EPIs de Solda – FSG / Marcopolo", subtitulo),
        _tabela(resumo, [12.5 * cm, 4.5 * cm]),
        Paragraph("Ocorrências por dia", secao), _grafico_por_dia(dados["por_dia"]),
        Paragraph("Por turno", secao), _tabela(turnos_linhas, [6.5 * cm, 3.5 * cm, 4 * cm, 3 * cm], numericas=3),
        Paragraph("Por posto", secao),
        _tabela(postos_linhas, [12.5 * cm, 4.5 * cm]) if dados["por_posto"]
        else Paragraph("Nenhuma ocorrência no mês.", texto),
        Spacer(1, 0.5 * cm),
        Paragraph("Como ler: uma ocorrência é registrada quando a falta da máscara dura pelo menos 4 segundos (75% dos "
                  "quadros), e a mesma pessoa só gera outra depois de 60 segundos. A conformidade vem do vídeo ao vivo, "
                  "quadro a quadro: conformes ÷ (conformes + não conformes); os indeterminados ficam de fora. O acerto "
                  "do sistema só considera as ocorrências que o supervisor validou.", nota),
        Spacer(1, 0.2 * cm),
        Paragraph("Privacidade (LGPD): este relatório não tem imagens. O sistema não identifica pessoas; o número da "
                  "pessoa no vídeo é temporário e as imagens guardadas são borradas.", nota),
    ]
    gerado = para_local(agora_utc()).strftime("%d/%m/%Y %H:%M")

    def rodape(canvas, documento) -> None:
        """Rodapé de cada página: data de geração, versão do sistema e número da página."""
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRAFITE)
        canvas.drawString(2 * cm, 1.2 * cm, f"Gerado em {gerado} · Verificador de EPIs de Solda v{VERSAO}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"página {documento.page}")
        canvas.restoreState()

    # O PDF é montado em memória e devolvido como bytes (quem chama envia ou grava).
    saida = BytesIO()
    documento = SimpleDocTemplate(saida, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                                  bottomMargin=2 * cm, title=f"Relatório mensal {inicio:%m/%Y}",
                                  author="Verificador de EPIs de Solda")
    documento.build(historia, onFirstPage=rodape, onLaterPages=rodape)
    return saida.getvalue()


def guardar_relatorio_do_mes_passado(fabrica: sessionmaker[Session], pasta: Path, turnos: dict[str, str]) -> Path:
    """Rotina do dia 1º: guarda em data/relatorios o PDF do mês que terminou (todos os postos)."""
    # Dia 1º deste mês menos um dia = último dia do mês anterior.
    mes = hoje_local().replace(day=1) - timedelta(days=1)
    caminho = pasta / f"relatorio_{mes:%Y-%m}.pdf"
    pasta.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(gerar_relatorio_mensal(fabrica, turnos, mes))
    log.info("Relatório mensal guardado: %s", caminho)
    return caminho
