"""Painel (RD04, tela T05): números e séries dos gráficos. Os filtros (período e posto) valem para tudo.
A conta fica em app/estatisticas.py (o relatório mensal em PDF usa a mesma)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth import UsuarioSessao, usuario_liberado
from app.estatisticas import resumo_do_periodo
from app.tempo import hoje_local

rotas = APIRouter(prefix="/api", tags=["painel"])
MAX_DIAS = 366


@rotas.get("/dashboard")
def painel(request: Request, inicio: date | None = None, fim: date | None = None, camera_id: int | None = None,
           _: UsuarioSessao = Depends(usuario_liberado)) -> dict:
    """Painel do período (padrão: do dia 1º do mês até hoje) e do posto escolhido (padrão: todos)."""
    fim = fim or hoje_local()
    inicio = inicio or fim.replace(day=1)
    if inicio > fim:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A data inicial está depois da data final.")
    if (fim - inicio).days >= MAX_DIAS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Escolha um período de até {MAX_DIAS} dias.")
    ctx = request.app.state.ctx
    return resumo_do_periodo(ctx.fabrica, ctx.ajustes.turnos, inicio, fim, camera_id)
