"""Alerta pelo Telegram (RD09): a cada ocorrência ao vivo, uma mensagem com a foto BORRADA e a falta da máscara.

É a ÚNICA informação que sai deste computador (exceção documentada; o resto do sistema é on-premises). Só funciona
com TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no .env e com o alerta ligado na tela de Configurações. A foto enviada é a
mesma imagem já borrada que foi gravada no disco, e o texto não identifica ninguém (o "#3" é um número temporário
do rastreamento).

O envio fica numa fila com uma thread própria: uma rede lenta ou fora do ar nunca atrasa a câmera nem o registro.
Ocorrências de arquivos enviados (upload) não geram alerta.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import urllib.error
import urllib.request
import uuid as uuid_mod
from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.config import Ajustes
from app.models import Camera, Ocorrencia
from app.storage import Storage
from app.tempo import para_local

log = logging.getLogger("epi_solda.telegram")
ENDERECO = "https://api.telegram.org/bot{token}/{metodo}"
TEMPO_LIMITE_S = 15
TAMANHO_FILA = 20                      # alertas esperando envio; além disso, os novos são descartados (com aviso no log)

Enviar = Callable[[str, str, dict, tuple[str, bytes, str] | None], None]


def legenda(ocorrencia: Ocorrencia, posto: str) -> str:
    """Texto do alerta. Com o arco aceso (RD03), a pessoa estava soldando: prioridade alta."""
    falta = "Máscara levantada" if ocorrencia.mascara_levantada else "Sem máscara"
    linhas = ["URGENTE: arco aceso, solda em andamento"] if ocorrencia.arco_ativo else []
    linhas += [f"Falta de EPI – {posto}", para_local(ocorrencia.data_hora).strftime("%d/%m/%Y %H:%M"),
               f"{falta} (pessoa #{ocorrencia.track_id} no vídeo)", "Valide em Ocorrências."]
    return "\n".join(linhas)


def _multipart(campos: dict[str, str], arquivo: tuple[str, bytes, str] | None) -> tuple[bytes, str]:
    """Corpo multipart/form-data (o Telegram recebe a foto assim), sem biblioteca extra."""
    fronteira = uuid_mod.uuid4().hex
    partes = []
    for nome, valor in campos.items():
        partes.append(f'--{fronteira}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n{valor}\r\n'.encode())
    if arquivo is not None:
        nome_arquivo, conteudo, tipo = arquivo
        partes.append(f'--{fronteira}\r\nContent-Disposition: form-data; name="photo"; filename="{nome_arquivo}"\r\n'
                      f"Content-Type: {tipo}\r\n\r\n".encode() + conteudo + b"\r\n")
    partes.append(f"--{fronteira}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={fronteira}"


def enviar_http(token: str, metodo: str, campos: dict, foto: tuple[str, bytes, str] | None = None) -> None:
    """Chama a API do Telegram (sendPhoto ou sendMessage). Levanta erro se ela recusar."""
    corpo, tipo = _multipart(campos, foto)
    pedido = urllib.request.Request(ENDERECO.format(token=token, metodo=metodo), data=corpo, method="POST",
                                    headers={"Content-Type": tipo})
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE_S) as resposta:
            dados = json.loads(resposta.read())
    except urllib.error.HTTPError as erro:
        raise RuntimeError(f"o Telegram recusou ({erro.code}); confira TELEGRAM_TOKEN e TELEGRAM_CHAT_ID") from None
    except urllib.error.URLError as erro:
        raise RuntimeError(f"sem conexão com o Telegram ({erro.reason})") from None
    if not dados.get("ok"):
        raise RuntimeError(f"o Telegram recusou: {dados.get('description', 'sem detalhes')}")


class Notificador:
    """Fila de alertas e a thread que envia."""

    def __init__(self, ajustes: Ajustes, storage: Storage, fabrica: sessionmaker[Session],
                 enviar: Enviar = enviar_http) -> None:
        self.ajustes, self.storage, self.fabrica, self._enviar = ajustes, storage, fabrica, enviar
        self._fila: queue.Queue[str] = queue.Queue(maxsize=TAMANHO_FILA)
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._executar, name="telegram", daemon=True)

    @property
    def configurado(self) -> bool:
        return bool(self.ajustes.telegram_token and self.ajustes.telegram_chat_id)

    @property
    def ativo(self) -> bool:
        return self.configurado and self.ajustes.telegram_ativo

    def iniciar(self) -> None:
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        if self._thread.is_alive():
            self._thread.join(5)

    def avisar(self, ocorrencia: Ocorrencia) -> bool:
        """Coloca o alerta na fila (não espera o envio). False se o alerta estiver desligado ou a fila cheia."""
        if not self.ativo or ocorrencia.origem != "ao_vivo":
            return False
        try:
            self._fila.put_nowait(ocorrencia.uuid)
            return True
        except queue.Full:
            log.warning("Fila de alertas do Telegram cheia: alerta da ocorrência %s descartado", ocorrencia.uuid)
            return False

    def testar(self) -> None:
        """Mensagem de teste pedida na tela de Configurações (espera o envio; levanta erro com a explicação)."""
        if not self.configurado:
            raise RuntimeError("coloque TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no arquivo .env e reinicie o sistema")
        self._enviar(self.ajustes.telegram_token, "sendMessage", {
            "chat_id": self.ajustes.telegram_chat_id,
            "text": "Teste do Verificador de EPIs de Solda: os alertas de falta de máscara chegarão aqui."}, None)

    def _executar(self) -> None:
        while not self._parar.is_set():
            try:
                uuid = self._fila.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._enviar_ocorrencia(uuid)
            except Exception as erro:   # um alerta perdido nunca derruba o sistema
                texto = str(erro).replace(self.ajustes.telegram_token, "****") if self.ajustes.telegram_token else erro
                log.warning("Alerta do Telegram não enviado (ocorrência %s): %s", uuid, texto)

    def _enviar_ocorrencia(self, uuid: str) -> None:
        with self.fabrica() as sessao:
            ocorrencia = sessao.query(Ocorrencia).filter_by(uuid=uuid).one_or_none()
            if ocorrencia is None:   # excluída antes do envio
                return
            camera = sessao.get(Camera, ocorrencia.camera_id)
            texto = legenda(ocorrencia, camera.nome_posto if camera else f"Posto {ocorrencia.camera_id}")
            caminho = ocorrencia.caminho_imagem
        campos = {"chat_id": self.ajustes.telegram_chat_id}
        foto = self.storage.ler(caminho) if caminho else None
        if foto:   # imagem gravada pelo Storage: sempre a cópia borrada (RF27)
            self._enviar(self.ajustes.telegram_token, "sendPhoto", {**campos, "caption": texto},
                         ("ocorrencia.jpg", foto, "image/jpeg"))
        else:      # disco cheio na hora: só o texto
            self._enviar(self.ajustes.telegram_token, "sendMessage", {**campos, "text": texto}, None)
        log.info("Alerta do Telegram enviado (ocorrência %s)", uuid)
