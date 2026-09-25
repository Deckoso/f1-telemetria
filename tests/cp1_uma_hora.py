"""CP-1 (fora do pytest, demora alguns minutos).

A) 1 h sintética a 60 Hz (16 tipos) enviada por UDP real em velocidade acelerada
   para o gravador rodando como processo separado: descartes, RAM de pico, CPU
   por hora simulada, tamanho em disco.
B) kill -9 no meio de uma sessão: o .parcial precisa ser legível até <= 1 s antes.

Uso: python tests/cp1_uma_hora.py [--velocidade 20]
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from f1tele.formato import Leitor  # noqa: E402
from f1tele.reprodutor import inventario  # noqa: E402
from f1tele.sintetico import enviar, gerar  # noqa: E402

PORTA = 20899


def iniciar(pasta):
    return subprocess.Popen(
        [sys.executable, "-m", "f1tele", "gravar", "--porta", str(PORTA), "--pasta", pasta,
         "--painel-porta", "0", "--sem-navegador"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )


def monitorar(pid, amostras, parar):
    while not parar.is_set():
        saida = subprocess.run(["ps", "-o", "rss=,time=", "-p", str(pid)], capture_output=True, text=True).stdout.split()
        if saida:
            amostras.append((int(saida[0]) * 1024, saida[1]))
        parar.wait(0.5)


def cpu_segundos(texto):
    partes = [float(p) for p in texto.replace("-", ":").split(":")]
    s = 0.0
    for p in partes:
        s = s * 60 + p
    return s


def parte_a(velocidade):
    pasta = tempfile.mkdtemp(prefix="cp1a_")
    proc = iniciar(pasta)
    time.sleep(1.5)
    amostras, parar = [], threading.Event()
    th = threading.Thread(target=monitorar, args=(proc.pid, amostras, parar), daemon=True)
    th.start()
    t0 = time.monotonic()
    enviados = enviar(gerar(3600, 60), "127.0.0.1", PORTA, velocidade)
    duracao = time.monotonic() - t0
    time.sleep(3)
    parar.set(); th.join()
    proc.send_signal(signal.SIGINT)
    proc.wait(30)
    (nome,) = [f for f in os.listdir(pasta) if f.endswith(".f1rec")]
    inv = inventario(os.path.join(pasta, nome))
    pico = max(a[0] for a in amostras)
    cpu = cpu_segundos(amostras[-1][1])
    tamanho = os.path.getsize(os.path.join(pasta, nome))
    return {
        "pacotes_enviados": enviados,
        "pacotes_gravados": inv["pacotes"],
        "perdidos": enviados - inv["pacotes"],
        "tempo_real_s": round(duracao, 1),
        "velocidade": velocidade,
        "ram_pico_mb": round(pico / 1048576, 1),
        "cpu_s_por_hora_simulada": round(cpu, 1),
        "cpu_pct_de_1_nucleo_em_tempo_real": round(cpu / 3600 * 100, 2),
        "disco_mb_por_hora": round(tamanho / 1048576, 1),
        "bruto_mb_por_hora": round(sum(len(r.dados) for r in Leitor(os.path.join(pasta, nome))) / 1048576, 1),
        "arquivo": nome,
    }


def parte_b():
    pasta = tempfile.mkdtemp(prefix="cp1b_")
    proc = iniciar(pasta)
    time.sleep(1.5)
    # 20 s de sessão em tempo real, depois kill -9 com o jogo ainda "mandando"
    parar = threading.Event()
    ultimo_envio = [0]

    def envio():
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        inicio = time.perf_counter()
        for t, dados in gerar(600, 60):
            if parar.is_set():
                break
            espera = t - (time.perf_counter() - inicio)
            if espera > 0:
                time.sleep(espera)
            s.sendto(dados, ("127.0.0.1", PORTA))
            ultimo_envio[0] = time.time_ns()

    th = threading.Thread(target=envio, daemon=True)
    th.start()
    time.sleep(20)
    morte = time.time_ns()
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait()
    parar.set(); th.join()
    (nome,) = [f for f in os.listdir(pasta) if ".f1rec" in f]
    with Leitor(os.path.join(pasta, nome)) as leitor:
        regs = list(leitor)
        truncado = leitor.truncado
    buraco = (morte - regs[-1].t_ns) / 1e9
    return {"arquivo": nome, "registros_legiveis": len(regs), "truncado": truncado,
            "segundos_perdidos_antes_do_kill": round(buraco, 2), "ok": buraco <= 1.0}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--velocidade", type=float, default=20)
    a = ap.parse_args()
    resultado = {"A_uma_hora": parte_a(a.velocidade), "B_kill9": parte_b()}
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
