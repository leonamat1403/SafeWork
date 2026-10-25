"""Gera o aviso de monitoramento para imprimir (RF30): docs/modelos/aviso_monitoramento.pdf, A4, com os campos em
branco para preencher à mão. O texto é o de docs/modelos/aviso_monitoramento.md.

    .venv\\Scripts\\python ferramentas\\gerar_aviso.py [--retencao 30] [--saida caminho.pdf]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

RAIZ = Path(__file__).resolve().parent.parent
# Cores do aviso: aço (faixa e texto), amarelo de segurança e grafite (rodapé).
ACO, AMARELO, GRAFITE = colors.HexColor("#1E2933"), colors.HexColor("#FFC107"), colors.HexColor("#4A5661")
ALTURA_FAIXA = 6.4 * cm  # faixa do cabeçalho; também define a margem superior do texto


def _cabecalho(canvas, documento) -> None:
    """Faixa de aço com o título em amarelo, a fita listrada de segurança e uma câmera desenhada."""
    largura, altura = A4
    canvas.saveState()
    canvas.setFillColor(ACO)
    canvas.rect(0, altura - ALTURA_FAIXA, largura, ALTURA_FAIXA, stroke=0, fill=1)
    # fita listrada amarela e aço (sinalização de área)
    faixa_y, faixa_h, passo = altura - ALTURA_FAIXA - 0.7 * cm, 0.7 * cm, 0.9 * cm
    canvas.setFillColor(ACO)
    canvas.rect(0, faixa_y, largura, faixa_h, stroke=0, fill=1)
    canvas.setFillColor(AMARELO)
    x = -faixa_h
    while x < largura:
        caminho = canvas.beginPath()
        caminho.moveTo(x, faixa_y)
        caminho.lineTo(x + passo / 2, faixa_y)
        caminho.lineTo(x + passo / 2 + faixa_h, faixa_y + faixa_h)
        caminho.lineTo(x + faixa_h, faixa_y + faixa_h)
        caminho.close()
        canvas.drawPath(caminho, stroke=0, fill=1)
        x += passo
    # câmera
    cx, cy = largura - 5.2 * cm, altura - 3.6 * cm
    canvas.setFillColor(AMARELO)
    canvas.roundRect(cx, cy, 2.6 * cm, 1.6 * cm, 0.25 * cm, stroke=0, fill=1)
    caminho = canvas.beginPath()
    caminho.moveTo(cx + 2.6 * cm, cy + 0.55 * cm)
    caminho.lineTo(cx + 3.4 * cm, cy + 0.15 * cm)
    caminho.lineTo(cx + 3.4 * cm, cy + 1.45 * cm)
    caminho.lineTo(cx + 2.6 * cm, cy + 1.05 * cm)
    caminho.close()
    canvas.drawPath(caminho, stroke=0, fill=1)
    canvas.setFillColor(ACO)
    canvas.circle(cx + 1.3 * cm, cy + 0.8 * cm, 0.45 * cm, stroke=0, fill=1)
    # título
    canvas.setFillColor(AMARELO)
    canvas.setFont("Helvetica-Bold", 30)
    canvas.drawString(1.8 * cm, altura - 2.7 * cm, "ÁREA MONITORADA")
    canvas.drawString(1.8 * cm, altura - 3.9 * cm, "POR CÂMERA")
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 14)
    canvas.drawString(1.8 * cm, altura - 5.2 * cm, "Verificação do uso da máscara de solda (NR-6)")
    canvas.restoreState()


def gerar(saida: Path, retencao_dias: int = 30) -> Path:
    """Monta o PDF A4 do aviso (texto, campos em branco e rodapé) em `saida` e devolve o caminho."""
    titulo = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=ACO, spaceBefore=12,
                            spaceAfter=4)
    texto = ParagraphStyle("x", fontName="Helvetica", fontSize=13, leading=18, textColor=ACO)
    item = ParagraphStyle("i", parent=texto, leftIndent=0.6 * cm, bulletIndent=0.1 * cm)
    rodape = ParagraphStyle("r", parent=texto, fontSize=10, leading=13, textColor=GRAFITE)
    linha = "_" * 34  # campo em branco para preencher à mão
    historia = [
        Paragraph("Por quê?", titulo),
        Paragraph("Para prevenir acidentes. A máscara de solda protege os olhos e o rosto da radiação do arco, dos "
                  "respingos e das faíscas.", texto),
        Paragraph("O que o sistema faz", titulo),
        Paragraph("Verifica se a máscara de solda está sendo usada no posto. Quando ela falta por mais de alguns "
                  "segundos, guarda <b>uma foto com o rosto borrado</b> para o responsável pela segurança conferir.",
                  texto),
        Paragraph("O que o sistema NÃO faz", titulo),
        Paragraph("não reconhece rostos e não identifica pessoas (sem nome, sem matrícula);", item, bulletText="•"),
        Paragraph("não grava vídeo contínuo;", item, bulletText="•"),
        Paragraph("não guarda nenhuma imagem sem borrar.", item, bulletText="•"),
        Paragraph("Por quanto tempo", titulo),
        Paragraph(f"As fotos e os registros são apagados automaticamente depois de <b>{retencao_dias} dias</b>.", texto),
        Paragraph("Quem acessa", titulo),
        Paragraph("_" * 62, texto),
        Paragraph("Dúvidas e seus direitos (LGPD – Lei nº 13.709/2018)", titulo),
        Paragraph(f"Encarregado de dados: {linha}", texto),
        Paragraph(f"Contato (e-mail ou ramal): {linha}", texto),
        Spacer(1, 0.8 * cm),
        Paragraph("Empresa: ______________________________ · Projeto de extensão FSG – Verificador de EPIs de Solda",
                  rodape),
    ]
    saida.parent.mkdir(parents=True, exist_ok=True)
    # A margem superior deixa o texto começar abaixo da faixa que _cabecalho desenha em cada página.
    documento = SimpleDocTemplate(str(saida), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                                  topMargin=ALTURA_FAIXA + 1.3 * cm, bottomMargin=1.5 * cm,
                                  title="Aviso de monitoramento – setor de solda",
                                  author="Verificador de EPIs de Solda")
    documento.build(historia, onFirstPage=_cabecalho, onLaterPages=_cabecalho)
    return saida


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser(description="Gera o aviso de monitoramento (PDF A4) para imprimir.")
    argumentos.add_argument("--retencao", type=int, default=30, help="dias até as fotos serem apagadas (padrão 30)")
    argumentos.add_argument("--saida", type=Path, default=RAIZ / "docs" / "modelos" / "aviso_monitoramento.pdf")
    opcoes = argumentos.parse_args()
    print(f"Aviso gerado: {gerar(opcoes.saida, opcoes.retencao)}")
