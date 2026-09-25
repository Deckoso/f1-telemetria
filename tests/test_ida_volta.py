"""CP-2: gravar -> reproduzir -> regravar = mesmos bytes, mesma ordem; ritmo fiel."""

import os
import queue
import statistics

from f1tele.formato import Leitor
from f1tele.gravador import Gravador
from f1tele.receptor import Receptor
from f1tele.reprodutor import reproduzir
from f1tele.sintetico import enviar, gerar

from .conftest import esperar


def gravar_via_udp(pasta, envio):
    rec = Receptor(0, host="127.0.0.1")
    g = Gravador(str(pasta), rec.fila, {"127.0.0.1"}, rec.porta, rec)
    rec.start(); g.start()
    n = envio(rec.porta)
    assert esperar(lambda: rec.recebidos == n, timeout=20)
    rec.parar(); rec.join(2)
    g.parar(); g.join(10)
    (nome,) = [f for f in os.listdir(pasta) if f.endswith(".f1rec")]
    return str(pasta / nome), rec


def corpos(caminho):
    with Leitor(caminho) as leitor:
        return [r.dados for r in leitor]


def test_ida_e_volta_byte_a_byte(tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir()
    original, rec1 = gravar_via_udp(tmp_path / "a", lambda porta: enviar(gerar(20), porta=porta, velocidade=5))
    copia, rec2 = gravar_via_udp(tmp_path / "b", lambda porta: reproduzir(original, porta=porta, velocidade=5))
    assert rec1.descartes == rec2.descartes == 0
    a, b = corpos(original), corpos(copia)
    assert len(a) > 7000 and a == b


def test_ritmo_da_reproducao(tmp_path):
    original, _ = gravar_via_udp(tmp_path, lambda porta: enviar(gerar(5), porta=porta, velocidade=1))
    atrasos = []
    reproduzir(original, porta=9, velocidade=1, atrasos=atrasos)  # porta 9 (discard): só mede o tempo
    atrasos.sort()
    p95 = atrasos[int(len(atrasos) * 0.95)]
    assert p95 <= 0.005, f"p95 {p95*1000:.2f} ms"
