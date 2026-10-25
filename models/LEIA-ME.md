# Modelos

| Arquivo | O que é | Como chega aqui |
|---|---|---|
| `epi_solda_best.pt` | Detector da **máscara de solda** (YOLOv8n, 1 classe, versão **v5**, validada na Fase 1: `docs/relatorio_validacao_fase1.md`) | vem **no repositório** |
| `yolov8n-pose.pt` | Pontos do corpo (Ultralytics, COCO) | `.venv\Scripts\python -m src.run --baixar-modelos` |
| `face_detection_yunet_2023mar.onnx` | Detector de rostos descobertos (YuNet, OpenCV Zoo, licença MIT) | o mesmo comando acima |

Sem o `epi_solda_best.pt`, o sistema liga, mas a tela Ao vivo avisa "Modelo de EPI não encontrado".

O `epi_solda_best.pt` foi treinado a partir do YOLOv8n da Ultralytics (licença AGPL-3.0) com os datasets
Welding-PPE, Welding Helmet, welder e safeweld (CC BY 4.0, atribuição no README) e exemplos negativos
(pessoas do COCO 2017 e quadros de vídeos do Pexels sem máscara). Versões antigas (v2, v3, v4) e
outros pesos ficam só no computador de quem treinou (não vão para o git).
