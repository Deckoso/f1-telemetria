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


def test_rota_analise(tmp_path):
    from . import pista_sintetica as ps

    ps.gravar(str(tmp_path / "2026-09-25_2000_silverstone_treino-1_xbox.f1rec"), [{}, {}])
    p = Painel(lambda: {}, str(tmp_path), porta=0)
    p.iniciar()
    try:
        status, corpo = pedir(p, "GET", "/analise?arquivo=2026-09-25_2000_silverstone_treino-1_xbox.f1rec")
        assert status == 200 and b"Voltas" in corpo and b"f1tele-relatorio" in corpo
        assert (tmp_path / "analises" / "2026-09-25_2000_silverstone_treino-1_xbox.html").exists()
        for ruim in ("../segredo.f1rec", "..%2Fsegredo.f1rec", "/etc/passwd", "x.txt", ""):
            assert pedir(p, "GET", "/analise?arquivo=" + ruim)[0] == 400
        assert pedir(p, "GET", "/analise?arquivo=nao-existe.f1rec")[0] == 404
    finally:
        p.parar()
