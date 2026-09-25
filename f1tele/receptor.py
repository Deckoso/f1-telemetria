"""Receptor UDP: só lê, repassa (opcional) e enfileira. Nunca decodifica nem escreve em disco."""

import queue
import socket
import threading
import time

TAMANHO_FILA = 20000  # ~40 s a 60 Hz com todos os pacotes; com teto, a RAM não cresce
BUFFER_SO = 4 * 1024 * 1024


class Receptor(threading.Thread):
    def __init__(self, porta: int = 20777, host: str = "0.0.0.0", repasses=(), fila: queue.Queue | None = None):
        super().__init__(name="receptor", daemon=True)
        self.fila = fila or queue.Queue(maxsize=TAMANHO_FILA)
        self.repasses = [(h, int(p)) for h, p in repasses]
        self.recebidos = 0
        self.descartes = 0
        self.repassados = 0
        self.erros_repasse = 0
        self.ultimo_recebido = 0.0
        self._parar = threading.Event()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Sem SO_REUSEADDR: se outro programa (ex.: F1 Laps) já ouve a porta,
        # o bind falha com erro claro em vez de dividir os pacotes em silêncio.
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SO)
        except OSError:
            pass
        self.sock.bind((host, porta))  # erro aqui = porta ocupada (ex.: F1 Laps aberto)
        self.porta = self.sock.getsockname()[1]
        self.sock.settimeout(0.5)
        self._saida = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) if self.repasses else None

    def run(self) -> None:
        recv = self.sock.recvfrom
        put = self.fila.put_nowait
        while not self._parar.is_set():
            try:
                dados, (ip, _porta) = recv(2048)
            except socket.timeout:
                continue
            except OSError:
                if self._parar.is_set():
                    break
                continue
            t_ns = time.time_ns()
            self.recebidos += 1
            self.ultimo_recebido = time.monotonic()
            for destino in self.repasses:
                try:
                    self._saida.sendto(dados, destino)
                    self.repassados += 1
                except OSError:
                    self.erros_repasse += 1
            try:
                put((t_ns, ip, dados))
            except queue.Full:
                self.descartes += 1

    def parar(self) -> None:
        self._parar.set()
        try:
            self.sock.close()
        except OSError:
            pass
        if self._saida:
            self._saida.close()

    def estado(self) -> dict:
        return {
            "porta": self.porta,
            "recebidos": self.recebidos,
            "descartes_fila": self.descartes,
            "fila": self.fila.qsize(),
            "repasses": [f"{h}:{p}" for h, p in self.repasses],
            "repassados": self.repassados,
            "erros_repasse": self.erros_repasse,
            "segundos_sem_sinal": round(time.monotonic() - self.ultimo_recebido, 1) if self.ultimo_recebido else None,
        }
