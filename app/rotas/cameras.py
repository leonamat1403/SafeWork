"""Câmeras ao vivo: lista, stream MJPEG (RF01), status para o painel (T02, RF05), pausar/retomar e snapshot."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.auth import UsuarioSessao, exigir_admin, exigir_csrf, usuario_liberado
from app.models import Camera, Ocorrencia
from app.stream import PASSO_CORDAO_S, TrabalhadorCamera, gerar_mjpeg, jpeg
from app.tempo import agora_utc, janela_do_turno, para_local

rotas = APIRouter(prefix="/api", tags=["câmeras"])
SEM_CACHE = {"Cache-Control": "no-store, private"}


def _trabalhador(request: Request, camera_id: int) -> TrabalhadorCamera:
    trabalhador = request.app.state.ctx.cameras.obter(camera_id)
    if trabalhador is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Câmera inexistente ou desativada.")
    return trabalhador


@rotas.get("/cameras")
def listar_cameras(request: Request, _: UsuarioSessao = Depends(usuario_liberado)) -> list[dict]:
    """Câmeras/postos cadastrados, com o status das que estão ligadas."""
    ctx = request.app.state.ctx
    with ctx.fabrica() as sessao:
        cameras = sessao.scalars(select(Camera).order_by(Camera.id)).all()
    resposta = []
    for camera in cameras:
        trabalhador = ctx.cameras.obter(camera.id)
        resposta.append({"id": camera.id, "nome_posto": camera.nome_posto, "processo_solda": camera.processo_solda,
                         "tipo": camera.tipo, "ativa": camera.ativa,
                         "online": trabalhador.online if trabalhador else False,
                         "pausada": trabalhador.pausada if trabalhador else False,
                         "fps": round(trabalhador.fps, 1) if trabalhador else 0.0})
    return resposta


@rotas.get("/cameras/{camera_id}/stream.mjpg")
def stream(camera_id: int, request: Request, max_quadros: int | None = Query(None, ge=1, include_in_schema=False),
           _: UsuarioSessao = Depends(usuario_liberado)) -> StreamingResponse:
    """Vídeo ao vivo anotado (e borrado, F2-D20). Abra este endereço numa aba do navegador ou numa <img>."""
    trabalhador = _trabalhador(request, camera_id)
    return StreamingResponse(gerar_mjpeg(trabalhador, request.is_disconnected, max_quadros=max_quadros),
                             media_type="multipart/x-mixed-replace; boundary=quadro", headers=SEM_CACHE)


@rotas.get("/cameras/{camera_id}/calibracao.mjpg")
def stream_calibracao(camera_id: int, request: Request,
                      max_quadros: int | None = Query(None, ge=1, include_in_schema=False),
                      _: UsuarioSessao = Depends(exigir_admin)) -> StreamingResponse:
    """Vídeo da calibração (RD02, T07): pontos do corpo, cabeça, linha dos olhos, rostos, cobertura da máscara e o
    brilho perto das mãos. Também borrado. Só ADMIN."""
    trabalhador = _trabalhador(request, camera_id)
    return StreamingResponse(gerar_mjpeg(trabalhador, request.is_disconnected, max_quadros=max_quadros,
                                         calibracao=True),
                             media_type="multipart/x-mixed-replace; boundary=quadro", headers=SEM_CACHE)


@rotas.get("/calibracao/{camera_id}")
def valores_calibracao(camera_id: int, request: Request, _: UsuarioSessao = Depends(exigir_admin)) -> dict:
    """Números de agora para a tela T07 (consultado a cada 1 s), com os limites do posto ao lado."""
    trabalhador = _trabalhador(request, camera_id)
    dados = trabalhador.dados_calibracao()
    return {"camera_id": camera_id, "nome": trabalhador.nome, "online": trabalhador.online,
            "pausada": trabalhador.pausada, "aguardando": dados is None, "pessoas": [], **(dados or {})}


@rotas.get("/status")
def status_ao_vivo(request: Request, camera_id: int | None = None,
                   _: UsuarioSessao = Depends(usuario_liberado)) -> dict:
    """Painel ao vivo (T02, consultado a cada 1 s): FPS, online, arco, pessoas com o estado de cada EPI, máscara
    levantada e as últimas 5 ocorrências. Sem camera_id, usa a primeira câmera ligada."""
    ctx = request.app.state.ctx
    if camera_id is None:
        ids = ctx.cameras.ids()
        if not ids:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nenhuma câmera ativa.")
        camera_id = ids[0]
    trabalhador = _trabalhador(request, camera_id)
    dados = trabalhador.status()
    agora = agora_utc()
    dados["agora_local"] = para_local(agora).strftime("%d/%m/%Y %H:%M:%S")
    dados["cordao"] = cordao_do_turno(request, trabalhador, agora)
    return dados


def cordao_do_turno(request: Request, trabalhador: TrabalhadorCamera, agora) -> dict:
    """Cordão do turno (T02): o pior estado de cada trecho de 10 s desde o início do turno, e um pino por ocorrência."""
    ctx = request.app.state.ctx
    turno, inicio, fim = janela_do_turno(agora, ctx.ajustes.turnos)
    with ctx.fabrica() as sessao:
        ocorrencias = sessao.execute(
            select(Ocorrencia.uuid, Ocorrencia.data_hora, Ocorrencia.epis_faltantes)
            .where(Ocorrencia.camera_id == trabalhador.camera_id, Ocorrencia.data_hora >= inicio,
                   Ocorrencia.origem == "ao_vivo")
            .order_by(Ocorrencia.data_hora)).all()
    return {
        "turno": turno, "passo_s": PASSO_CORDAO_S,
        "inicio": inicio.isoformat(), "fim": fim.isoformat(),
        "inicio_local": para_local(inicio).strftime("%H:%M"), "fim_local": para_local(fim).strftime("%H:%M"),
        "trechos": trabalhador.cordao(inicio.timestamp(), agora.timestamp()),
        "pinos": [{"uuid": u, "segundos": round((d - inicio).total_seconds()),
                   "hora_local": para_local(d).strftime("%H:%M"), "epis_faltantes": e} for u, d, e in ocorrencias],
    }


@rotas.post("/cameras/{camera_id}/pausar", dependencies=[Depends(exigir_csrf)])
def pausar(camera_id: int, request: Request, _: UsuarioSessao = Depends(exigir_admin)) -> dict:
    """Para o monitoramento desta câmera (sem ocorrências) até retomar. Só ADMIN (F2-D14)."""
    _trabalhador(request, camera_id).pausada = True
    return {"camera_id": camera_id, "pausada": True}


@rotas.post("/cameras/{camera_id}/retomar", dependencies=[Depends(exigir_csrf)])
def retomar(camera_id: int, request: Request, _: UsuarioSessao = Depends(exigir_admin)) -> dict:
    _trabalhador(request, camera_id).pausada = False
    return {"camera_id": camera_id, "pausada": False}


@rotas.get("/cameras/{camera_id}/snapshot.jpg")
def snapshot(camera_id: int, request: Request, _: UsuarioSessao = Depends(usuario_liberado)) -> Response:
    """Foto atual, SEMPRE borrada, para download. Não fica guardada no servidor (F2-D6)."""
    trabalhador = _trabalhador(request, camera_id)
    instantaneo = trabalhador.instantaneo()
    if instantaneo is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A câmera ainda não tem imagem.")
    frame, resultado = instantaneo
    imagem = request.app.state.ctx.registrador.imagem_anotada(frame, resultado)
    nome = f"snapshot_camera{camera_id}_{para_local(agora_utc()):%Y%m%d_%H%M%S}.jpg"
    return Response(jpeg(imagem.pixels, largura_max=1920, qualidade=85), media_type="image/jpeg",
                    headers={**SEM_CACHE, "Content-Disposition": f'attachment; filename="{nome}"'})
