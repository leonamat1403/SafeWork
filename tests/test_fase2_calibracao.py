"""[FASE 2] Calibração (Etapa 2.5, bloco B – RD02, tela T07): números do quadro e de cada pessoa, desenho técnico
borrado e acesso só do ADMIN. Câmera e detector SIMULADOS (os mesmos do test_fase2_web.py)."""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.calibracao import dados_calibracao, desenhar_calibracao
from src.compliance import avaliar_frame
from src.pipeline import ResultadoFrame
from tests.auxiliares import (MASCARA_ABAIXADA, REGIAO_CABECA_ESPERADA, ROSTO_COBERTO, ROSTO_DESCOBERTO,
                              ROSTO_DETECTADO, criar_pessoa, mascara)
from tests.conftest import detalhe
from tests.test_fase2_web import (QUADRO, admin_pronto, bcrypt_rapido, cliente, criar_supervisor, entrar,  # noqa: F401
                                  esperar)

PULSOS = {9: (240, 380), 10: (160, 380)}


def quadro_com_arco() -> np.ndarray:
    """Imagem escura com um brilho de arco logo à frente de um punho."""
    img = np.full((700, 500, 3), 40, np.uint8)
    img[385:415, 230:260] = 255                     # brilho do arco logo à frente de um punho
    return img


def test_valores_de_quem_esta_de_mascara(config):
    """Pessoa de máscara tem os números da calibração (estado, altura, cobertura, confiança, mãos e brilho) corretos."""
    pessoa = criar_pessoa({**ROSTO_COBERTO, **PULSOS})
    avaliacoes = avaliar_frame([pessoa], [mascara(MASCARA_ABAIXADA, conf=0.81)], config, rostos=[])
    dados = dados_calibracao(quadro_com_arco(), ResultadoFrame(avaliacoes, [], False, 0.02, []), config)
    p = dados["pessoas"][0]
    assert p["estado"] == "CONFORME" and p["altura_px"] == 500 and p["cabeca_visivel"] and not p["sem_pose"]
    assert p["cobertura"] == 1.0 and p["conf_mascara"] == 0.81 and p["rosto_visivel"] is False
    assert p["maos_visiveis"] == 2 and p["brilho_maos"] == pytest.approx(900 / 14400, abs=0.001)
    assert dados["quadro_valido"] and dados["fracao_saturada"] == 0.02
    assert dados["limites"]["cobertura_min"] == 0.30 and dados["limites"]["fracao_max_saturada"] == 0.15


def test_valores_de_quem_esta_sem_mascara(config):
    """Pessoa sem máscara e com rosto visível aparece como não conforme, sem cobertura nem confiança de máscara."""
    avaliacoes = avaliar_frame([criar_pessoa(ROSTO_DESCOBERTO)], [], config, rostos=[ROSTO_DETECTADO])
    p = dados_calibracao(QUADRO, ResultadoFrame(avaliacoes, [], False, 0.0, [ROSTO_DETECTADO]), config)["pessoas"][0]
    assert p["estado"] == "NAO_CONFORME" and p["cobertura"] is None and p["conf_mascara"] is None
    assert p["rosto_visivel"] is True and p["conf_rosto"] == 0.9 and p["brilho_maos"] is None


def test_desenho_da_calibracao_fica_sobre_a_imagem(config):
    """O desenho de calibração é feito numa cópia da imagem e marca a região das mãos em vermelho."""
    avaliacoes = avaliar_frame([criar_pessoa({**ROSTO_COBERTO, **PULSOS})], [mascara(MASCARA_ABAIXADA)], config,
                               rostos=[])
    resultado = ResultadoFrame(avaliacoes, [mascara(MASCARA_ABAIXADA)], False, 0.0, [])
    base = np.zeros((700, 500, 3), np.uint8)
    desenho = desenhar_calibracao(base, quadro_com_arco(), resultado, config, "Posto 1")
    assert desenho.shape == base.shape and desenho.any() and not base.any()   # desenha numa cópia
    assert (desenho[:, :, 2] > 200).any()                                    # região das mãos em vermelho (arco)


# --------------------------------------------------------------------------------------------------- tela e API
def test_calibracao_so_para_admin(cliente):
    """Supervisor recebe 403 na tela, na API e no vídeo de calibração."""
    token = admin_pronto(cliente)
    criar_supervisor(cliente)
    cliente.post("/logout", headers={"X-CSRF-Token": token})
    entrar(cliente, "sup", "senha-supervisor-1")
    assert cliente.get("/calibracao").status_code == 403
    assert cliente.get("/api/calibracao/1").status_code == 403
    assert cliente.get("/api/cameras/1/calibracao.mjpg?max_quadros=1").status_code == 403


def test_tela_de_calibracao(cliente):
    """A tela de calibração mostra a câmera, o quadro de valores e o link no menu."""
    admin_pronto(cliente)
    html = cliente.get("/calibracao").text
    assert 'data-camera-id="1"' in html and "Valores agora" in html and 'href="/calibracao"' in html
    assert "/static/js/calibracao.js?v=" in html


def test_valores_e_video_de_calibracao(cliente):
    """A API devolve os valores da pessoa detectada e o vídeo de calibração mantém a cabeça borrada."""
    admin_pronto(cliente)
    dados = esperar(lambda: (d := cliente.get("/api/calibracao/1").json())["pessoas"] and d)
    assert dados["aguardando"] is False and dados["online"] is True and dados["quadro_valido"] is True
    assert dados["pessoas"][0]["estado"] == "NAO_CONFORME" and dados["pessoas"][0]["rosto_visivel"] is True
    r = cliente.get("/api/cameras/1/calibracao.mjpg?max_quadros=1")
    assert r.status_code == 200 and r.headers["content-type"].startswith("multipart/x-mixed-replace")
    inicio = r.content.index(b"\xff\xd8")
    foto = cv2.imdecode(np.frombuffer(r.content[inicio:r.content.rindex(b"\xff\xd9") + 2], np.uint8), cv2.IMREAD_COLOR)
    assert foto is not None
    escala = foto.shape[1] / QUADRO.shape[1]               # o stream pode vir reduzido
    x1, y1, x2, y2 = (round(v * escala) for v in REGIAO_CABECA_ESPERADA)
    # a cabeça continua borrada também na calibração (os traços do desenho cruzam a região, então o limite é folgado)
    assert detalhe(foto, (x1 + 4, y1 + 4, x2 - 4, y2 - 4)) < 0.5 * detalhe(QUADRO, REGIAO_CABECA_ESPERADA)
