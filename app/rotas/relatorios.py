"""Relatório mensal em PDF (RD10): download pelo Painel (ADMIN e SUPERVISOR). Fica na auditoria ("exportar")."""
from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.auth import UsuarioSessao, auditar, usuario_liberado
from app.models import Camera
from app.relatorios import gerar_relatorio_mensal
from app.tempo import hoje_local

rotas = APIRouter(prefix="/api/relatorios", tags=["relatórios"])
MES = re.compile(r"^(\d{4})-(\d{2})$")


@rotas.get("/mensal.pdf")
def relatorio_mensal(request: Request, mes: str | None = Query(None, description="AAAA-MM (padrão: o mês atual)"),
                     camera_id: int | None = None, usuario: UsuarioSessao = Depends(usuario_liberado)) -> Response:
    hoje = hoje_local()
    if mes is None:
        primeiro = hoje.replace(day=1)
    else:
        achado = MES.match(mes)
        if not achado or not 1 <= int(achado.group(2)) <= 12:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Informe o mês no formato AAAA-MM.")
        primeiro = date(int(achado.group(1)), int(achado.group(2)), 1)
        if primeiro > hoje:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Esse mês ainda não começou.")
    ctx = request.app.state.ctx
    nome_posto = None
    if camera_id is not None:
        with ctx.fabrica() as sessao:
            camera = sessao.get(Camera, camera_id)
            if camera is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Posto não encontrado.")
            nome_posto = camera.nome_posto
    pdf = gerar_relatorio_mensal(ctx.fabrica, ctx.ajustes.turnos, primeiro, camera_id, nome_posto)
    auditar(ctx.fabrica, usuario.id, "exportar", {"formato": "pdf", "mes": f"{primeiro:%Y-%m}",
                                                  "camera_id": camera_id})
    nome = f"relatorio_{primeiro:%Y-%m}" + (f"_posto{camera_id}" if camera_id is not None else "") + ".pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Cache-Control": "no-store, private", "Content-Disposition": f'attachment; filename="{nome}"'})
