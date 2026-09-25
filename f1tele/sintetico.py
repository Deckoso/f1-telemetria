"""Gerador de pacotes sintéticos no formato 2025.

Cabeçalho e tamanhos seguem a spec; o corpo é plausível só onde o gravador
lê algo (Session: pista/tipo; Participants: plataforma). Serve para testar
o encanamento. Não serve para validar análise: isso exige gravação real.
"""

import random
import socket
import struct
import time
from typing import Iterator

from . import spec

_MODELOS: dict[int, bytes] = {}

# Frequências por tipo de pacote (por segundo). None = taxa do menu.
FREQUENCIAS = {
    0: None, 2: None, 6: None, 7: None, 13: None,
    1: 2, 5: 2, 10: 10, 11: 20, 12: 20, 14: 1, 15: 1,
    4: 0.2,  # a cada 5 s
}


def montar_pacote(
    pid: int,
    sessao_uid: int,
    tempo: float,
    quadro: int,
    *,
    formato: int = 2025,
    carro_jogador: int = 0,
    pista: int = 11,
    tipo_sessao: int = 18,
    plataforma: int = 4,
    tamanho: int | None = None,
    corpo_rng: random.Random | None = None,
) -> bytes:
    tamanho = tamanho or spec.TAMANHOS_2025[pid]
    cab = spec.HEADER.pack(formato, 25, 1, 12, 1, pid, sessao_uid, tempo, quadro, quadro, carro_jogador, 255)
    corpo = bytearray(tamanho - spec.HEADER_SIZE)
    if corpo_rng is not None and pid not in (1, 4):
        # corpo fixo por tipo + alguns floats que variam por quadro (comprime parecido com dado real)
        modelo = _MODELOS.get(pid)
        if modelo is None or len(modelo) != len(corpo):
            modelo = _MODELOS[pid] = bytes(corpo_rng.getrandbits(8) & 0x3F for _ in range(len(corpo)))
        corpo[:] = modelo
        for i in range(0, min(len(corpo) - 4, 96), 12):
            struct.pack_into("<f", corpo, i, quadro * 0.01 + i)
    pacote = bytearray(cab) + corpo
    if pid == 1:
        pacote[spec.SESSION_TIPO] = tipo_sessao
        pacote[spec.SESSION_PISTA] = pista & 0xFF
    elif pid == 4:
        pacote[spec.HEADER_SIZE] = 20  # m_numActiveCars
        registro = (tamanho - spec.PARTICIPANTS_BASE) // spec.PARTICIPANTS_CARROS
        offset = spec.PLATAFORMA_OFFSET_POR_REGISTRO[registro]
        for carro in range(20):
            pacote[spec.PARTICIPANTS_BASE + carro * registro + offset] = plataforma if carro == carro_jogador else 255
    return bytes(pacote)


def gerar(
    duracao_s: float,
    hz: int = 60,
    sessao_uid: int = 0x1234ABCD5678EF01,
    *,
    pista: int = 11,
    tipo_sessao: int = 18,
    plataforma: int = 4,
    formato: int = 2025,
    perder_a_cada: int = 0,
    semente: int = 7,
) -> Iterator[tuple[float, bytes]]:
    """Gera (segundos desde o início, pacote) em ordem de tempo.

    perder_a_cada=N remove o CarStatus de 1 a cada N quadros (simula perda).
    """
    rng = random.Random(semente)
    passo = 1.0 / hz
    proximo = {pid: 0.0 for pid in FREQUENCIAS}
    quadro = 0
    t = 0.0
    while t < duracao_s:
        for pid, freq in FREQUENCIAS.items():
            intervalo = passo if freq is None else 1.0 / freq
            if t + 1e-9 >= proximo[pid]:
                proximo[pid] += intervalo
                if perder_a_cada and pid == 7 and quadro % perder_a_cada == 0:
                    continue
                yield t, montar_pacote(
                    pid, sessao_uid, t, quadro, formato=formato, pista=pista,
                    tipo_sessao=tipo_sessao, plataforma=plataforma, corpo_rng=rng,
                )
        if quadro % (hz * 30) == 0:
            yield t, montar_pacote(3, sessao_uid, t, quadro, formato=formato)
        quadro += 1
        t = quadro * passo


def enviar(pacotes, host: str = "127.0.0.1", porta: int = 20777, velocidade: float = 1.0) -> int:
    """Envia pacotes (t, bytes) respeitando o tempo / velocidade. velocidade<=0 = máximo."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    inicio = time.perf_counter()
    n = 0
    try:
        for t, dados in pacotes:
            if velocidade > 0:
                espera = t / velocidade - (time.perf_counter() - inicio)
                if espera > 0.002:
                    time.sleep(espera - 0.001)
            s.sendto(dados, (host, porta))
            n += 1
    finally:
        s.close()
    return n


def pacote_lixo() -> bytes:
    return struct.pack("<I", 0xDEADBEEF) * 3
