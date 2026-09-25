import socket

import pytest

from f1tele.receptor import Receptor
from f1tele.sintetico import enviar, gerar

from .conftest import esperar


def test_repasse_byte_a_byte_para_outro_programa():
    import threading
    destino = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    destino.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    destino.bind(("127.0.0.1", 0))
    destino.settimeout(5)
    rec = Receptor(0, host="127.0.0.1", repasses=[("127.0.0.1", destino.getsockname()[1])])
    rec.start()
    pacotes = [d for _, d in gerar(0.5)]
    recebidos = []

    def ler():  # lê em paralelo, como o F1 Laps faria
        try:
            while len(recebidos) < len(pacotes):
                recebidos.append(destino.recvfrom(2048)[0])
        except socket.timeout:
            pass

    leitor = threading.Thread(target=ler)
    leitor.start()
    try:
        enviar(((i / 600, d) for i, d in enumerate(pacotes)), porta=rec.porta, velocidade=1)
        leitor.join(10)
        assert recebidos == pacotes
        assert esperar(lambda: rec.repassados == len(pacotes))
        assert rec.fila.qsize() == len(pacotes)  # e também foi para a gravação
    finally:
        rec.parar(); destino.close()


def test_porta_ocupada_da_erro_claro():
    ocupante = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ocupante.bind(("127.0.0.1", 0))
    try:
        with pytest.raises(OSError):
            Receptor(ocupante.getsockname()[1], host="127.0.0.1")
    finally:
        ocupante.close()


def test_fila_cheia_descarta_e_conta_sem_crescer():
    import queue
    rec = Receptor(0, host="127.0.0.1", fila=queue.Queue(maxsize=50))
    rec.start()
    try:
        enviar(((0, d) for _, d in gerar(1)), porta=rec.porta, velocidade=0)
        assert esperar(lambda: rec.recebidos >= 300 and rec.descartes > 0, timeout=5)
        assert rec.fila.qsize() == 50
    finally:
        rec.parar()
