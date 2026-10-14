"""Inicia o sistema web:  python -m app   (Ctrl+C para encerrar)."""
import uvicorn

from app.config import carregar_ajustes

if __name__ == "__main__":
    ajustes = carregar_ajustes()
    # 1 processo só (sem workers): os modelos e as câmeras ficam na memória dele (docs/arquitetura_fase2.md, seção 6)
    uvicorn.run("app.main:criar_app", factory=True, host=ajustes.host, port=ajustes.porta, log_level="info")
