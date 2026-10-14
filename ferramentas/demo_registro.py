"""Demonstração da Etapa 2.2 (antes de existir a tela): processa um vídeo e grava as ocorrências no BANCO, com as
imagens JÁ BORRADAS em data/ocorrencias e data/thumbnails.

Uso (na pasta do projeto, com o ambiente .venv ativo):
    python ferramentas/demo_registro.py --fonte testes_campo/videos/nao_conformes/7006656-uhd_4096_2160_25fps.mp4
    python ferramentas/demo_registro.py --listar            # mostra as ocorrências que já estão no banco

Usa a pasta de dados do .env (DATA_DIR, padrão ./data, fora do git). Cria o banco na primeira vez (migrações).
Abra as imagens listadas no fim para conferir o blur das cabeças e dos rostos.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("YOLO_OFFLINE", "true")

from sqlalchemy import select  # noqa: E402

from app.config import carregar_ajustes, configurar_logging, preparar_pastas  # noqa: E402
from app.database import aplicar_migracoes, criar_engine, criar_fabrica_sessoes  # noqa: E402
from app.models import Camera, ConfigEpiCamera, Ocorrencia  # noqa: E402
from app.privacy import Borrador, DetectorRostosQuadro  # noqa: E402
from app.registro import RegistradorOcorrencias  # noqa: E402
from app.storage import StorageDisco  # noqa: E402
from app.tempo import para_local  # noqa: E402

NOME_CAMERA = "Demonstração (arquivo de vídeo)"


def camera_de_demonstracao(fabrica, fonte: str, conf_mascara: float) -> int:
    """A câmera "de mentira" usada pela demonstração (criada na primeira vez)."""
    with fabrica() as sessao:
        camera = sessao.scalars(select(Camera).where(Camera.nome_posto == NOME_CAMERA)).first()
        if camera is None:
            camera = Camera(nome_posto=NOME_CAMERA, tipo="arquivo", origem=fonte, ativa=False,
                            epis=[ConfigEpiCamera(epi="mascara", conf_min=conf_mascara)])
            sessao.add(camera)
        camera.origem = fonte
        sessao.commit()
        return camera.id


def listar(fabrica, data_dir: Path, limite: int = 20) -> None:
    with fabrica() as sessao:
        ocorrencias = sessao.scalars(select(Ocorrencia).order_by(Ocorrencia.data_hora.desc()).limit(limite)).all()
    if not ocorrencias:
        print("Nenhuma ocorrência no banco.")
        return
    print(f"Últimas {len(ocorrencias)} ocorrência(s) no banco ({data_dir}):")
    for oc in ocorrencias:
        imagem = data_dir / oc.caminho_imagem if oc.caminho_imagem else "(sem imagem: disco cheio)"
        print(f"  {para_local(oc.data_hora):%d/%m/%Y %H:%M:%S} | turno {oc.turno} | pessoa #{oc.track_id} | "
              f"{', '.join(f'{e}: {oc.situacao.get(e, '')}' for e in oc.epis_faltantes)} | {oc.validacao}")
        print(f"      {imagem}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Grava no banco as ocorrências de um vídeo (demonstração da 2.2).")
    parser.add_argument("--fonte", help="arquivo de vídeo")
    parser.add_argument("--max-frames", type=int, default=0, help="para depois de N frames (0 = vídeo inteiro)")
    parser.add_argument("--listar", action="store_true", help="só lista as ocorrências do banco")
    args = parser.parse_args(argv)

    ajustes = carregar_ajustes()
    preparar_pastas(ajustes.data_dir)
    configurar_logging(ajustes.data_dir / "logs")
    aplicar_migracoes(ajustes.database_url)
    engine = criar_engine(ajustes.database_url)
    fabrica = criar_fabrica_sessoes(engine)
    try:
        if args.listar or not args.fonte:
            listar(fabrica, ajustes.data_dir)
            return 0

        from src.config import carregar_config
        from src.detector import Detector
        from src.occurrences import GerenciadorOcorrencias
        from src.pipeline import Pipeline
        from src.video import FonteVideo

        config = carregar_config(ajustes.config_yaml)
        camera_id = camera_de_demonstracao(fabrica, args.fonte, config.epis["mascara"].conf)
        registrador = RegistradorOcorrencias(
            fabrica, StorageDisco(ajustes.data_dir, ajustes.espaco_minimo_mb),
            Borrador(DetectorRostosQuadro(config.modelos.rosto, config.deteccao.conf_rosto),
                     config.deteccao.conf_keypoint),
            ajustes.turnos)
        pipeline = Pipeline(config, Detector(config))
        gerenciador = GerenciadorOcorrencias(config)
        fonte = FonteVideo(args.fonte)
        n = registradas = 0
        try:
            while True:
                frame, t = fonte.ler()
                if frame is None or (args.max_frames and n >= args.max_frames):
                    break
                resultado = pipeline.processar(frame)
                for oc in gerenciador.atualizar(resultado.avaliacoes, t, n, resultado.saturado):
                    registrador.registrar(oc, frame, resultado, camera_id)
                    registradas += 1
                n += 1
        finally:
            fonte.fechar()
        print(f"\n{n} frames processados, {registradas} ocorrência(s) gravada(s) no banco.\n")
        listar(fabrica, ajustes.data_dir, limite=max(registradas, 1))
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
