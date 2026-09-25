import http.client
import json

import pytest

from f1tele.painel import Painel


@pytest.fixture
def painel(tmp_path):
    p = Painel(lambda: {"ok": 1}, str(tmp_path), porta=0)
    p.iniciar()
    yield p
    p.parar()


def pedir(p, metodo, caminho, host=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", p.porta, timeout=5)
    c.putrequest(metodo, caminho, skip_host=True)
    c.putheader("Host", host or f"127.0.0.1:{p.porta}")
    for k, v in (headers or {}).items():
        c.putheader(k, v)
    c.endheaders()
    r = c.getresponse()
    return r.status, r.read()


def test_pagina_e_estado(painel):
    status, corpo = pedir(painel, "GET", "/")
    assert status == 200 and b"Gravador de telemetria" in corpo
    status, corpo = pedir(painel, "GET", "/estado")
    assert status == 200 and json.loads(corpo) == {"ok": 1}


def test_so_ouve_localhost(painel):
    assert painel.servidor.server_address[0] == "127.0.0.1"


def test_host_estranho_bloqueado(painel):
    assert pedir(painel, "GET", "/estado", host="atacante.com")[0] == 403


def test_post_sem_cabecalho_proprio_bloqueado(painel):
    assert pedir(painel, "POST", "/abrir-pasta")[0] == 403
