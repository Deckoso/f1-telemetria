import queue
import time

import pytest

from f1tele import gravador as mod_gravador
from f1tele.gravador import Gravador


@pytest.fixture
def gravacao(tmp_path):
    """Gravador alimentado direto pela fila (sem socket). Devolve (gravador, fila, pasta)."""
    criados = []

    def fabricar(locais=frozenset({"127.0.0.1"})):
        fila = queue.Queue()
        g = Gravador(str(tmp_path), fila, set(locais), 20777)
        g.start()
        criados.append(g)
        return g, fila, tmp_path

    yield fabricar
    for g in criados:
        g.parar()
        g.join(10)


def esperar(cond, timeout=5.0):
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if cond():
            return True
        time.sleep(0.02)
    return False
