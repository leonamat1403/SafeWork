"""Análise por upload (T03, RF02): enviar, acompanhar o progresso, baixar o resultado e registrar ocorrências."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.auth import UsuarioSessao, exigir_csrf, usuario_liberado
from app.models import Camera
from app.uploads import ErroUpload, TrabalhoUpload

rotas = APIRouter(prefix="/api/uploads", tags=["upload"])


def _trabalho(request: Request, trabalho_id: str, usuario: UsuarioSessao) -> TrabalhoUpload:
    trabalho = request.app.state.ctx.uploads.obter(trabalho_id, usuario.id, usuario.admin)
    if trabalho is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload não encontrado (ou já expirou, após 1 h).")
    return trabalho


@rotas.post("", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(exigir_csrf)])
async def enviar(request: Request, arquivo: UploadFile = File(..., description="foto .jpg/.png ou vídeo .mp4"),
                 camera_id: int | None = Form(None, description="posto usado nas regras (padrão: o primeiro)"),
                 usuario: UsuarioSessao = Depends(usuario_liberado)) -> dict:
    """Envia o arquivo; o processamento roda em segundo plano (acompanhe em GET /api/uploads/{id})."""
    ctx = request.app.state.ctx
    if camera_id is None:
        with ctx.fabrica() as sessao:
            camera_id = sessao.scalars(select(Camera.id).order_by(Camera.id).limit(1)).first()
        if camera_id is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cadastre um posto antes de enviar arquivos.")
    try:
        trabalho = await ctx.uploads.receber(arquivo, usuario.id, camera_id)
    except ErroUpload as erro:
        raise HTTPException(erro.codigo, str(erro)) from erro
    return trabalho.resumo()


@rotas.get("/{trabalho_id}")
def consultar(trabalho_id: str, request: Request, usuario: UsuarioSessao = Depends(usuario_liberado)) -> dict:
    """Estado, progresso (0 a 1) e, no fim, a tabela de pessoas × EPIs e as ocorrências encontradas."""
    return _trabalho(request, trabalho_id, usuario).resumo()


@rotas.get("/{trabalho_id}/arquivo")
def baixar(trabalho_id: str, request: Request, usuario: UsuarioSessao = Depends(usuario_liberado)) -> FileResponse:
    """Resultado anotado e borrado (foto .jpg ou vídeo .mp4/.webm)."""
    trabalho = _trabalho(request, trabalho_id, usuario)
    if trabalho.estado != "concluido" or trabalho.saida is None or not trabalho.saida.exists():
        raise HTTPException(status.HTTP_409_CONFLICT, "O resultado ainda não está pronto.")
    nome = f"resultado_{trabalho.id[:8]}{trabalho.saida.suffix}"
    return FileResponse(trabalho.saida, media_type=trabalho.tipo_saida, filename=nome,
                        headers={"Cache-Control": "no-store, private"})


@rotas.post("/{trabalho_id}/registrar", dependencies=[Depends(exigir_csrf)])
def registrar(trabalho_id: str, request: Request, usuario: UsuarioSessao = Depends(usuario_liberado)) -> dict:
    """"Registrar como ocorrência" (T03): grava no banco as ocorrências encontradas neste arquivo."""
    trabalho = _trabalho(request, trabalho_id, usuario)
    try:
        uuids = request.app.state.ctx.uploads.registrar(trabalho)
    except ErroUpload as erro:
        raise HTTPException(erro.codigo, str(erro)) from erro
    return {"registradas": uuids}
