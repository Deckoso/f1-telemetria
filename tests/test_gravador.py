"""Gravador + detecção automática de jogo e plataforma."""

import os
import time

from f1tele import gravador as mod
from f1tele.formato import Leitor
from f1tele.reprodutor import inventario
from f1tele.sintetico import gerar, montar_pacote, pacote_lixo

from .conftest import esperar

XBOX_IP = "192.168.0.50"


def alimentar(fila, ip, pacotes):
    n = 0
    for t, dados in pacotes:
        fila.put((int(t * 1e9), ip, dados))
        n += 1
    return n


def arquivos(pasta):
    return sorted(f for f in os.listdir(pasta) if ".f1rec" in f)


def test_xbox_na_rede_detectado_e_nomeado(gravacao):
    g, fila, pasta = gravacao()
    n = alimentar(fila, XBOX_IP, gerar(10, pista=11, tipo_sessao=18, plataforma=4))
    assert esperar(lambda: (g.estado().get("sessao") or {}).get("pacotes") == n)
    s = g.estado()["sessao"]
    assert s["rotulo"] == f"F1 25 v1.12 · UDP 2025 · Xbox · {XBOX_IP}"
    assert s["pista"] == "Monza" and s["tipo"] == "Time Trial"
    assert not s["divergencia_plataforma"] and s["tamanhos_inesperados"] == 0
    g.parar(); g.join(10)
    (nome,) = arquivos(pasta)
    assert nome.endswith("_monza_time-trial.f1rec")
    assert inventario(str(pasta / nome))["pacotes"] == n


def test_jogo_no_proprio_pc_steam(gravacao):
    g, fila, _ = gravacao()
    alimentar(fila, "127.0.0.1", gerar(6, plataforma=1))
    assert esperar(lambda: "PC (Steam)" in ((g.estado().get("sessao") or {}).get("rotulo") or ""))
    assert g.estado()["sessao"]["rotulo"].endswith("PC (Steam) · este computador")


def test_sem_participants_usa_a_origem(gravacao):
    g, fila, _ = gravacao()
    for q in range(30):
        fila.put((q, XBOX_IP, montar_pacote(6, 9, q / 60, q)))
    assert esperar(lambda: (g.estado().get("sessao") or {}).get("pacotes") == 30)
    assert g.estado()["sessao"]["plataforma"] == "console na rede"


def test_divergencia_registrada_sem_bloquear(gravacao):
    g, fila, _ = gravacao()
    alimentar(fila, "127.0.0.1", gerar(6, plataforma=4))
    assert esperar(lambda: (g.estado().get("sessao") or {}).get("divergencia_plataforma") is True)


def test_segunda_fonte_ignorada(gravacao):
    g, fila, pasta = gravacao()
    alimentar(fila, XBOX_IP, gerar(2))
    alimentar(fila, "192.168.0.77", gerar(1, sessao_uid=99))
    assert esperar(lambda: g.estado().get("outras_fontes", {}).get("192.168.0.77", 0) > 0)
    g.parar(); g.join(10)
    assert len(arquivos(pasta)) == 1


def test_lixo_e_formato_desconhecido(gravacao):
    g, fila, pasta = gravacao()
    fila.put((1, XBOX_IP, pacote_lixo()))
    for q in range(10):
        fila.put((q + 2, XBOX_IP, montar_pacote(6, 5, q, q, formato=2031)))
    assert esperar(lambda: g.estado().get("invalidos") == 1 and (g.estado().get("sessao") or {}).get("pacotes") == 10)
    assert g.estado()["sessao"]["formato_udp"] == 2031
    g.parar(); g.join(10)
    with Leitor(str(pasta / arquivos(pasta)[0])) as leitor:
        assert sum(1 for _ in leitor) == 10


def test_perda_de_pacote_contada(gravacao):
    g, fila, pasta = gravacao()
    alimentar(fila, XBOX_IP, gerar(20, perder_a_cada=10))  # 1200 quadros, 120 sem CarStatus
    g.parar(); g.join(10)
    inv = inventario(str(pasta / arquivos(pasta)[0]))
    assert inv["quadros"] == 1200 and inv["quadros_incompletos"] == 120
    import sqlite3
    linha = sqlite3.connect(pasta / "sessoes.sqlite").execute("SELECT quadros, quadros_incompletos, estado FROM sessoes").fetchone()
    assert linha[2] == "fechada" and linha[0] == 1198 and linha[1] == 120  # os 2 últimos quadros não contam


def test_sessoes_separadas_por_uid_e_fechamento_por_ociosidade(gravacao, monkeypatch):
    monkeypatch.setattr(mod, "SESSAO_OCIOSA_S", 0.5)
    g, fila, pasta = gravacao()
    alimentar(fila, XBOX_IP, gerar(2, sessao_uid=1, tipo_sessao=1))
    alimentar(fila, XBOX_IP, gerar(2, sessao_uid=2, tipo_sessao=15))
    assert esperar(lambda: len(g.estado().get("historico", [])) == 2, timeout=5)
    nomes = arquivos(pasta)
    assert len(nomes) == 2 and not any(n.endswith(".parcial") for n in nomes)
    assert any("treino-1" in n for n in nomes) and any("corrida" in n for n in nomes)


def test_disco_cheio_para_de_gravar(gravacao, monkeypatch):
    monkeypatch.setattr(mod, "DISCO_MINIMO", 1 << 62)
    monkeypatch.setattr(mod, "DISCO_RETOMA", 1 << 63)
    g, fila, _ = gravacao()
    fila.put((1, XBOX_IP, montar_pacote(6, 1, 0, 0)))
    assert esperar(lambda: g.estado().get("estado") == "pausado_disco")
    fila.put((2, XBOX_IP, montar_pacote(6, 1, 0, 1)))
    assert esperar(lambda: g.estado().get("descartados_disco", 0) >= 1)


def test_sessao_interrompida_recuperada_na_proxima_execucao(tmp_path):
    import queue as q
    from f1tele.formato import Escritor
    import shutil
    rascunho = tmp_path.parent / (tmp_path.name + "_rascunho.bin")
    esc = Escritor(str(rascunho), {})
    esc.escrever(1, 0, b"x" * 40)
    esc.sincronizar()
    # cópia sem o final do gzip: como se o PC tivesse desligado no meio da sessão
    shutil.copy(rascunho, tmp_path / "2026-09-25_120000_00000000000000aa.f1rec.parcial")
    esc.fechar()
    g = mod.Gravador(str(tmp_path), q.Queue(), {"127.0.0.1"}, 20777)
    g.start()
    try:
        assert esperar(lambda: (tmp_path / "2026-09-25_120000_00000000000000aa_interrompida.f1rec").exists())
        with Leitor(str(tmp_path / "2026-09-25_120000_00000000000000aa_interrompida.f1rec")) as leitor:
            assert len(list(leitor)) == 1
    finally:
        g.parar(); g.join(5)
