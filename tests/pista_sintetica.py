"""Pista sintética com física simples para testar a análise (formato 2026, 20 Hz).

Pista de 2000 m com duas curvas (ápices em 600 m e 1400 m). O carro acelera
a 12 m/s², freia a 30 m/s² e faz as curvas a 90 e 130 km/h. `freio_antes`
antecipa a frenagem de uma curva numa volta específica.
"""

import struct

from f1tele import decodificador as dec
from f1tele import spec
from f1tele.formato import Escritor

COMPRIMENTO = 2000
CURVAS = [(600, 90 / 3.6), (1400, 130 / 3.6)]
VMAX = 300 / 3.6
ACEL, FREIO = 12.0, 30.0
HZ = 20
L = dec.layout(2026)
CARRO = 0


def perfil(freio_antes: dict) -> list:
    """Velocidade-alvo (m/s) por metro, com frenagem antecipada opcional (índice da curva -> m)."""
    v = [VMAX] * (COMPRIMENTO + 1)
    for k, (apex, vc) in enumerate(CURVAS):
        extra = freio_antes.get(k, 0)
        for d in range(COMPRIMENTO + 1):
            dist = apex - d
            if dist >= 0:  # antes do ápice: limite de frenagem (com antecipação)
                lim = (vc ** 2 + 2 * FREIO * max(0, dist - extra)) ** 0.5 if dist > extra else vc
            else:  # depois: limite de aceleração
                lim = (vc ** 2 + 2 * ACEL * (-dist)) ** 0.5
            v[d] = min(v[d], lim)
    return v


def _cab(pid, uid, t, quadro):
    return spec.HEADER.pack(2026, 25, 1, 26, 1, pid, uid, t, quadro, quadro, CARRO, 255)


def gravar(caminho: str, voltas_freio: list, uid: int = 0x51) -> list:
    """Grava uma sessão com len(voltas_freio) voltas + 50 m da seguinte. Devolve os tempos (ms)."""
    esc = Escritor(caminho, {"jogo": "F1 25 v1.26 · UDP 2026 (Season Pack)", "inicio": "2026-09-25T20:00:00-03:00", "origem": "rede"})
    t_sessao, quadro, tempos = 0.0, 0, []
    voltas_hist = []

    def pacote(pid, corpo_fn):
        dados = bytearray(spec.TAMANHOS_2026[pid])
        dados[:29] = _cab(pid, uid, t_sessao, quadro)
        corpo_fn(dados)
        esc.escrever(int(t_sessao * 1e9), 1, bytes(dados))

    def sessao(d):
        d[29 + 4:29 + 6] = struct.pack("<H", COMPRIMENTO)
        d[spec.SESSION_TIPO] = 1
        d[spec.SESSION_PISTA] = 7

    pacote(1, sessao)
    for n, freio_antes in enumerate(voltas_freio + [{}], start=1):
        v = perfil(freio_antes)
        d, t_volta = 0.0, 0.0
        fim = COMPRIMENTO if n <= len(voltas_freio) else 50
        while d < fim:
            vel = v[min(int(d), COMPRIMENTO)]
            prox = v[min(int(d) + 1, COMPRIMENTO)]
            freando = prox < vel - 0.05

            def lap(p, d=d, t_volta=t_volta, n=n):
                o = 29 + CARRO * L.lap
                struct.pack_into("<II", p, o, tempos[-1] if tempos else 0, int(t_volta * 1000))
                struct.pack_into("<ff", p, o + 20, d, d + (n - 1) * COMPRIMENTO)
                p[o + 33] = n

            def tel(p, vel=vel, freando=freando):
                o = 29 + CARRO * L.tel
                struct.pack_into("<Hfff", p, o, int(vel * 3.6), 0.0 if freando else 1.0, 0.0, 1.0 if freando else 0.0)
                p[o + 15] = max(1, min(8, int(vel * 3.6 / 40)))

            def mot(p, d=d):
                struct.pack_into("<ff", p, 29 + CARRO * L.motion, d, 0.0)
                struct.pack_into("<f", p, 29 + CARRO * L.motion + 8, (d / 300.0) ** 2)

            pacote(0, mot)
            pacote(2, lap)
            pacote(6, tel)
            dt = 1 / HZ
            d += vel * dt
            t_volta += dt
            t_sessao += dt
            quadro += 1
        if n <= len(voltas_freio):
            tempos.append(int(t_volta * 1000))
            voltas_hist.append(tempos[-1])

    def hist(p):
        p[29] = CARRO
        p[30] = len(voltas_hist) + 1
        for i, ms in enumerate(voltas_hist):
            o = 29 + 7 + i * 14
            s = ms // 3
            struct.pack_into("<IHBHBHBB", p, o, ms, s % 60000, s // 60000, s % 60000, s // 60000, (ms - 2 * s) % 60000, (ms - 2 * s) // 60000, 0x0F)

    pacote(11, hist)
    esc.fechar()
    return tempos
