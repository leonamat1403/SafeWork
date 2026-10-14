"""[FASE 2] Blur de privacidade (RF27): cabeças e rostos borrados antes de qualquer gravação."""
import numpy as np
import pytest

from app.privacy import Borrador, DetectorRostosQuadro, ImagemBorrada
from tests.auxiliares import CAIXA_PADRAO, REGIAO_CABECA_ESPERADA, ROSTO_COBERTO, ROSTO_DESCOBERTO, criar_pessoa
from tests.conftest import RAIZ, detalhe

LONGE_DA_CABECA = (330, 400, 480, 650)   # região sem pessoa nenhuma


def test_imagem_borrada_so_pode_ser_criada_pelo_borrador():
    with pytest.raises(TypeError, match="RF27"):
        ImagemBorrada(np.zeros((10, 10, 3), np.uint8))


def test_cabeca_de_quem_esta_sem_mascara_e_borrada_e_o_resto_nao(frame_texturizado):
    original = frame_texturizado.copy()
    borrada = Borrador(None).borrar(frame_texturizado, [criar_pessoa(ROSTO_DESCOBERTO)])

    assert detalhe(borrada.pixels, REGIAO_CABECA_ESPERADA) < 0.05 * detalhe(original, REGIAO_CABECA_ESPERADA)
    x1, y1, x2, y2 = LONGE_DA_CABECA
    assert np.array_equal(borrada.pixels[y1:y2, x1:x2], original[y1:y2, x1:x2])
    assert np.array_equal(frame_texturizado, original)          # o frame original não é alterado


def test_cabeca_e_borrada_mesmo_com_a_mascara_cobrindo_o_rosto(frame_texturizado):
    """Blur preventivo (RF27): olhos e nariz escondidos pela máscara, cabeça borrada pelas orelhas e ombros."""
    borrada = Borrador(None).borrar(frame_texturizado, [criar_pessoa(ROSTO_COBERTO)])
    assert detalhe(borrada.pixels, REGIAO_CABECA_ESPERADA) < 0.05 * detalhe(frame_texturizado, REGIAO_CABECA_ESPERADA)


def test_sem_pontos_do_corpo_borra_os_25_porcento_superiores_da_pessoa(frame_texturizado):
    borrada = Borrador(None).borrar(frame_texturizado, [criar_pessoa({})])
    x1, y1, x2, y2 = CAIXA_PADRAO
    topo = (x1, y1, x2, y1 + 0.25 * (y2 - y1))
    assert detalhe(borrada.pixels, topo) < 0.05 * detalhe(frame_texturizado, topo)


class DetectorFalso:
    def detectar(self, frame):
        return [LONGE_DA_CABECA]


def test_rostos_do_detector_e_da_fase_1_tambem_sao_borrados(frame_texturizado):
    rosto_fase1 = (20, 20, 80, 80)
    borrada = Borrador(DetectorFalso()).borrar(frame_texturizado, [], rostos=[rosto_fase1])
    for regiao in (LONGE_DA_CABECA, rosto_fase1):
        assert detalhe(borrada.pixels, regiao) < 0.05 * detalhe(frame_texturizado, regiao)


def test_imagem_borrada_e_somente_leitura(frame_texturizado):
    borrada = Borrador(None).borrar(frame_texturizado, [])
    with pytest.raises(ValueError):
        borrada.pixels[0, 0, 0] = 1


def test_desenhar_por_cima_continua_sendo_imagem_borrada(frame_texturizado):
    borrada = Borrador(None).borrar(frame_texturizado, [criar_pessoa(ROSTO_DESCOBERTO)])

    def caixa_preta(img):
        img[0:10, 0:10] = 0
        return img

    desenhada = borrada.com_desenho(caixa_preta)
    assert isinstance(desenhada, ImagemBorrada)
    assert desenhada.pixels[5, 5].tolist() == [0, 0, 0]
    assert not np.array_equal(borrada.pixels[0:10, 0:10], desenhada.pixels[0:10, 0:10])   # a original não muda


def test_detector_de_rostos_sem_modelo_nao_quebra(frame_texturizado):
    assert DetectorRostosQuadro(None).detectar(frame_texturizado) == []


def test_detector_de_rostos_com_o_modelo_do_projeto_roda_no_frame_inteiro(frame_texturizado):
    modelo = RAIZ / "models" / "face_detection_yunet_2023mar.onnx"
    if not modelo.exists():
        pytest.skip("modelo de rostos não baixado (python -m src.run --baixar-modelos)")
    assert DetectorRostosQuadro(modelo).detectar(frame_texturizado) == []   # ruído não tem rosto
