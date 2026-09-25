"""Reprodutor e inventário de gravações .f1rec."""

import collections
import socket
import time

from . import spec
from .cabecalho import PacoteInvalido, ler_cabecalho, ler_plataforma, ler_sessao, rotulo_jogo
from .formato import Leitor


def reproduzir(
    caminho: str,
    host: str = "127.0.0.1",
    porta: int = 20777,
    velocidade: float = 1.0,
    desde_s: float = 0.0,
    loop: bool = False,
    parar=None,
    atrasos: list | None = None,
) -> int:
    """Reenvia os pacotes com o ritmo original. velocidade<=0 = o mais rápido possível.

    `atrasos` (lista opcional) recebe o atraso real de cada envio em segundos (medição).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    enviados = 0
    try:
        while True:
            with Leitor(caminho) as leitor:
                t0 = None
                inicio = time.perf_counter()
                for reg in leitor:
                    if parar is not None and parar.is_set():
                        return enviados
                    if t0 is None:
                        t0 = reg.t_ns + int(desde_s * 1e9)
                    rel = (reg.t_ns - t0) / 1e9
                    if rel < 0:
                        continue
                    if velocidade > 0:
                        alvo = inicio + rel / velocidade
                        espera = alvo - time.perf_counter()
                        if espera > 0.002:
                            time.sleep(espera - 0.0015)
                        while time.perf_counter() < alvo:
                            pass
                        if atrasos is not None:
                            atrasos.append(time.perf_counter() - alvo)
                    s.sendto(reg.dados, (host, porta))
                    enviados += 1
            if not loop:
                return enviados
    finally:
        s.close()


def inventario(caminho: str) -> dict:
    """Resumo de uma gravação sem decodificar o corpo (além de Session e Participants)."""
    contagem = collections.Counter()
    tamanhos = collections.defaultdict(collections.Counter)
    invalidos = 0
    primeiro = ultimo = None
    info_sessao = None
    plataforma = None
    jogo = None
    formatos = collections.Counter()
    quadros = collections.OrderedDict()  # janela limitada: memória não cresce com a duração
    n_quadros = incompletos = 0
    completo = (1 << len(spec.PACOTES_POR_QUADRO)) - 1
    bits = {pid: 1 << i for i, pid in enumerate(spec.PACOTES_POR_QUADRO)}
    with Leitor(caminho) as leitor:
        meta = leitor.meta
        for reg in leitor:
            primeiro = primeiro if primeiro is not None else reg.t_ns
            ultimo = reg.t_ns
            try:
                cab = ler_cabecalho(reg.dados)
            except PacoteInvalido:
                invalidos += 1
                continue
            contagem[cab.id_pacote] += 1
            tamanhos[cab.id_pacote][len(reg.dados)] += 1
            formatos[cab.formato] += 1
            jogo = jogo or rotulo_jogo(cab)
            if cab.id_pacote == 1:
                info_sessao = ler_sessao(reg.dados) or info_sessao
            elif cab.id_pacote == 4 and cab.carro_jogador < spec.PARTICIPANTS_CARROS:
                codigo = ler_plataforma(reg.dados, cab.carro_jogador)
                if codigo not in (None, 255):
                    plataforma = codigo
            if cab.id_pacote in bits:
                quadros[cab.quadro] = quadros.get(cab.quadro, 0) | bits[cab.id_pacote]
                while len(quadros) > 240:
                    n_quadros += 1
                    incompletos += quadros.popitem(last=False)[1] != completo
        truncado = leitor.truncado
    duracao = (ultimo - primeiro) / 1e9 if primeiro is not None else 0.0
    n_quadros += len(quadros)
    incompletos += sum(1 for m in quadros.values() if m != completo)
    return {
        "arquivo": caminho,
        "meta": meta,
        "jogo": jogo,
        "formatos_udp": dict(formatos),
        "plataforma": spec.PLATAFORMAS.get(plataforma) if plataforma is not None else None,
        "sessao": info_sessao,
        "duracao_s": round(duracao, 1),
        "pacotes": sum(contagem.values()),
        "invalidos": invalidos,
        "truncado": truncado,
        "quadros": n_quadros,
        "quadros_incompletos": incompletos,
        "por_tipo": {
            spec.NOMES_PACOTE.get(pid, str(pid)): {
                "id": pid,
                "pacotes": n,
                "hz": round(n / duracao, 2) if duracao else None,
                "tamanhos": dict(tamanhos[pid]),
                "tamanho_spec_2025": spec.TAMANHOS_2025.get(pid),
            }
            for pid, n in sorted(contagem.items())
        },
    }
