"""Gravador: consome a fila do receptor e grava um .f1rec por sessão do jogo.

Grava os bytes exatos do jogo. Do conteúdo só lê o cabeçalho, mais Session
(pista/tipo) e Participants (plataforma) para dar nome e rótulo à sessão.
"""

import collections
import datetime as dt
import json
import os
import queue
import re
import shutil
import sqlite3
import threading
import time

from . import __version__, spec
from .cabecalho import PacoteInvalido, ler_cabecalho, ler_plataforma, ler_sessao, rotulo_jogo
from .formato import ORIGEM_LOCAL, ORIGEM_REDE, Escritor
from .rede import e_local

SESSAO_OCIOSA_S = 60.0  # sem pacote por esse tempo -> sessão fechada
FONTE_OCIOSA_S = 10.0  # outra fonte só assume depois disso
SINCRONIZAR_S = 1.0
SINCRONIZAR_BYTES = 2 * 1024 * 1024
CATALOGO_S = 10.0
DISCO_MINIMO = 1024**3  # abaixo de 1 GB livre, para de gravar
DISCO_RETOMA = 1536 * 1024**2
MAX_FECHADAS = 20  # sessões recentes que podem ser retomadas no mesmo arquivo
JANELA_QUADROS = 240  # quadros pendentes na checagem de perda (memória limitada)

_BIT_QUADRO = {pid: 1 << i for i, pid in enumerate(spec.PACOTES_POR_QUADRO)}
_QUADRO_COMPLETO = (1 << len(spec.PACOTES_POR_QUADRO)) - 1


def _agora_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _limpar_nome(texto: str) -> str:
    texto = texto.lower()
    for a, b in (("á", "a"), ("ã", "a"), ("â", "a"), ("é", "e"), ("ê", "e"), ("í", "i"), ("ó", "o"), ("ô", "o"), ("ú", "u"), ("ç", "c")):
        texto = texto.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-") or "sessao"


class Sessao:
    def __init__(self, pasta: str, cab, ip: str, origem: int, porta: int):
        self.uid = cab.sessao_uid
        self.pasta = pasta
        self.bytes_brutos = 0
        self.inicio = dt.datetime.now().astimezone()
        self.ip = ip
        self.origem = origem
        self.formato = cab.formato
        self.jogo = rotulo_jogo(cab)
        self.info_sessao = None
        self.plataforma_codigo = None
        self.contagem = collections.Counter()
        self.tamanhos_inesperados = 0
        self.quadros = collections.OrderedDict()
        self.quadros_total = 0
        self.quadros_incompletos = 0
        self.ultimo_pacote = time.monotonic()
        self.ultimo_sync = time.monotonic()
        self.bytes_desde_sync = 0
        nome = f"{self.inicio:%Y-%m-%d_%H%M%S}_{self.uid:016x}.f1rec.parcial"
        self.caminho = os.path.join(pasta, nome)
        self.escritor = Escritor(
            self.caminho,
            {
                "gravador": f"f1tele {__version__}",
                "formato_arquivo": 1,
                "sessao_uid": f"{self.uid:016x}",
                "inicio": self.inicio.isoformat(timespec="seconds"),
                "jogo": self.jogo,
                "formato_udp": cab.formato,
                "origem_ip": ip,
                "origem": "este computador" if origem == ORIGEM_LOCAL else "rede",
                "porta": porta,
            },
        )

    # --- rótulos -----------------------------------------------------------
    @property
    def plataforma(self) -> str:
        nome = spec.PLATAFORMAS.get(self.plataforma_codigo) if self.plataforma_codigo is not None else None
        if nome in ("Steam", "EA"):
            return f"PC ({nome})"
        if nome:
            return nome
        return "PC" if self.origem == ORIGEM_LOCAL else "outro aparelho da rede"

    @property
    def divergencia(self) -> bool:
        """Jogo 'neste PC' dizendo ser console (ou o contrário). Registrado, não bloqueia."""
        nome = spec.PLATAFORMAS.get(self.plataforma_codigo)
        if not nome:
            return False
        console = nome in ("Xbox", "PlayStation")
        return console == (self.origem == ORIGEM_LOCAL)

    @property
    def rotulo(self) -> str:
        onde = "este computador" if self.origem == ORIGEM_LOCAL else self.ip
        return f"{self.jogo} · {self.plataforma} · {onde}"

    # --- gravação ----------------------------------------------------------
    def registrar(self, cab, t_ns: int, dados: bytes) -> None:
        self.escritor.escrever(t_ns, self.origem, dados)
        self.bytes_brutos += len(dados)
        self.ultimo_pacote = time.monotonic()
        self.bytes_desde_sync += len(dados)
        pid = cab.id_pacote
        self.contagem[pid] += 1
        esperado = spec.TAMANHOS_POR_FORMATO.get(cab.formato, {}).get(pid)
        if esperado is not None and esperado != len(dados):
            self.tamanhos_inesperados += 1
        if pid == 1:
            info = ler_sessao(dados)
            if info:
                self.info_sessao = info
        elif pid == 4:
            codigo = ler_plataforma(dados, cab.carro_jogador)
            if codigo is not None and codigo != 255:
                self.plataforma_codigo = codigo
        bit = _BIT_QUADRO.get(pid)
        if bit:
            self.quadros[cab.quadro] = self.quadros.get(cab.quadro, 0) | bit
            while len(self.quadros) > JANELA_QUADROS:
                self._fechar_quadro(self.quadros.popitem(last=False)[1])

    def _fechar_quadro(self, mascara: int) -> None:
        self.quadros_total += 1
        if mascara != _QUADRO_COMPLETO:
            self.quadros_incompletos += 1

    def talvez_sincronizar(self, forcar: bool = False) -> None:
        agora = time.monotonic()
        if forcar or self.bytes_desde_sync >= SINCRONIZAR_BYTES or (
            self.bytes_desde_sync and agora - self.ultimo_sync >= SINCRONIZAR_S
        ):
            self.escritor.sincronizar()
            self.ultimo_sync = agora
            self.bytes_desde_sync = 0

    def tamanho_disco(self) -> int:
        try:
            return os.path.getsize(self.caminho)
        except OSError:
            return 0

    @property
    def so_menu(self) -> bool:
        """Sessão sem nenhuma volta nem pista (telas de menu, lobby, resultado solto)."""
        return self.quadros_total == 0 and not self.quadros and self.info_sessao is None

    def fechar(self) -> str:
        """Fecha e dá o nome final 'AAAA-MM-DD_HHMM_<pista>_<tipo>.f1rec'.

        Sessão só de menu vai para a subpasta 'menus/' (nada é apagado).
        """
        # Fecha a janela de quadros; os 2 últimos podem ter sido cortados pela
        # própria parada do jogo e não contam como perda.
        pendentes = list(self.quadros.values())
        self.quadros.clear()
        for mascara in pendentes[:-2]:
            self._fechar_quadro(mascara)
        self.escritor.fechar()
        pasta = os.path.join(self.pasta, "menus") if self.so_menu else self.pasta
        if os.path.dirname(self.caminho) == pasta and not self.caminho.endswith(".parcial"):
            return self.caminho  # retomada que já tinha o nome certo
        os.makedirs(pasta, exist_ok=True)
        if self.so_menu:
            base = f"{self.inicio:%Y-%m-%d_%H%M}_menus"
        else:
            pista = self.info_sessao["pista"] if self.info_sessao else "pista-desconhecida"
            tipo = self.info_sessao["tipo"] if self.info_sessao else "sessao"
            base = f"{self.inicio:%Y-%m-%d_%H%M}_{_limpar_nome(pista)}_{_limpar_nome(tipo)}"
        destino = os.path.join(pasta, base + ".f1rec")
        n = 2
        while os.path.exists(destino):
            destino = os.path.join(pasta, f"{base}_{n}.f1rec")
            n += 1
        os.replace(self.caminho, destino)
        self.caminho = destino
        return destino

    def reabrir(self) -> None:
        """A mesma sessão do jogo voltou (pausa longa, tela de resultado): continua no mesmo arquivo."""
        self.escritor = Escritor(self.caminho, None, anexar=True)
        self.ultimo_pacote = time.monotonic()
        self.ultimo_sync = time.monotonic()
        self.bytes_desde_sync = 0

    def resumo(self) -> dict:
        return {
            "uid": f"{self.uid:016x}",
            "arquivo": os.path.basename(self.caminho),
            "inicio": self.inicio.isoformat(timespec="seconds"),
            "pista": self.info_sessao["pista"] if self.info_sessao else None,
            "tipo": self.info_sessao["tipo"] if self.info_sessao else None,
            "jogo": self.jogo,
            "formato_udp": self.formato,
            "plataforma": self.plataforma,
            "origem_ip": self.ip,
            "rotulo": self.rotulo,
            "divergencia_plataforma": self.divergencia,
            "pacotes": sum(self.contagem.values()),
            "bytes_brutos": self.bytes_brutos,
            "bytes_disco": self.tamanho_disco(),
            "contagem": {spec.NOMES_PACOTE.get(k, str(k)): v for k, v in sorted(self.contagem.items())},
            "quadros": self.quadros_total,
            "quadros_incompletos": self.quadros_incompletos,
            "tamanhos_inesperados": self.tamanhos_inesperados,
        }


class Catalogo:
    """`sessoes.sqlite` na pasta de gravações. Usado só pela thread do gravador."""

    def __init__(self, caminho: str):
        self.caminho = caminho
        self._db = None

    def _con(self):
        if self._db is None:
            self._db = sqlite3.connect(self.caminho)
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS sessoes (
                    uid TEXT, inicio TEXT, fim TEXT, arquivo TEXT, pista TEXT, tipo TEXT,
                    jogo TEXT, formato_udp INTEGER, plataforma TEXT, origem_ip TEXT,
                    pacotes INTEGER, bytes_brutos INTEGER, bytes_disco INTEGER,
                    quadros INTEGER, quadros_incompletos INTEGER, descartes_fila INTEGER,
                    estado TEXT, detalhes TEXT, PRIMARY KEY (uid, inicio))"""
            )
        return self._db

    def salvar(self, resumo: dict, estado: str, descartes: int, fim: str | None = None) -> None:
        db = self._con()
        db.execute(
            """INSERT OR REPLACE INTO sessoes VALUES
               (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                resumo["uid"], resumo["inicio"], fim, resumo["arquivo"], resumo["pista"], resumo["tipo"],
                resumo["jogo"], resumo["formato_udp"], resumo["plataforma"], resumo["origem_ip"],
                resumo["pacotes"], resumo["bytes_brutos"], resumo["bytes_disco"], resumo["quadros"],
                resumo["quadros_incompletos"], descartes, estado,
                json.dumps({"contagem": resumo["contagem"], "tamanhos_inesperados": resumo["tamanhos_inesperados"],
                            "divergencia_plataforma": resumo["divergencia_plataforma"]}, ensure_ascii=False),
            ),
        )
        db.commit()

    def marcar_interrompida(self, antigo: str, novo: str) -> None:
        db = self._con()
        db.execute("UPDATE sessoes SET arquivo=?, estado='interrompida' WHERE arquivo=?", (novo, antigo))
        db.commit()

    def ultimas(self, n: int = 10) -> list[dict]:
        cur = self._con().execute(
            "SELECT inicio, fim, arquivo, pista, tipo, plataforma, pacotes, bytes_disco, estado "
            "FROM sessoes WHERE pista IS NOT NULL OR quadros > 0 ORDER BY inicio DESC LIMIT ?",
            (n,),
        )
        campos = [c[0] for c in cur.description]
        return [dict(zip(campos, linha)) for linha in cur.fetchall()]

    def fechar(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None


class Gravador(threading.Thread):
    def __init__(self, pasta: str, fila: queue.Queue, locais: set[str], porta: int, receptor=None):
        super().__init__(name="gravador", daemon=True)
        self.pasta = pasta
        os.makedirs(pasta, exist_ok=True)
        self.fila = fila
        self.locais = locais
        self.porta = porta
        self.receptor = receptor
        self.catalogo = Catalogo(os.path.join(pasta, "sessoes.sqlite"))
        self.sessoes: dict[int, Sessao] = {}
        self.fechadas: collections.OrderedDict[int, Sessao] = collections.OrderedDict()  # para retomar
        self.fonte: str | None = None
        self.fonte_visto = 0.0
        self.outras_fontes = collections.Counter()
        self.invalidos = 0
        self.pausado_disco = False
        self.descartados_disco = 0
        self.historico = collections.deque(maxlen=10)
        self.erro: str | None = None
        self._parar = threading.Event()
        self._lock = threading.Lock()
        self._estado: dict = {}
        self._ultimo_catalogo = 0.0
        self._ultimo_disco = 0.0
        self._contagem_anterior = collections.Counter()
        self._ultima_taxa = time.monotonic()
        self._taxas: dict = {}
        self._ultimo_publicar = 0.0

    # --- ciclo -------------------------------------------------------------
    def run(self) -> None:
        try:
            self._recuperar_interrompidas()
            self.historico.extend(self.catalogo.ultimas(10))
            while not self._parar.is_set():
                try:
                    item = self.fila.get(timeout=0.25)
                except queue.Empty:
                    item = None
                if item is not None:
                    self._processar(*item)
                    # esvazia o que já está na fila antes da manutenção
                    for _ in range(2000):
                        try:
                            self._processar(*self.fila.get_nowait())
                        except queue.Empty:
                            break
                self._manutencao()
            self._drenar()
        except Exception as exc:  # erro de disco, permissão etc.: aparece no painel
            self.erro = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            for s in list(self.sessoes.values()):
                self._fechar_sessao(s)
            self.catalogo.fechar()
            self._publicar()

    def parar(self) -> None:
        self._parar.set()

    def _recuperar_interrompidas(self) -> None:
        """Sessões '.parcial' de uma execução que caiu viram '..._interrompida.f1rec'."""
        for nome in os.listdir(self.pasta):
            if nome.endswith(".f1rec.parcial"):
                base = nome[: -len(".f1rec.parcial")]
                try:
                    os.replace(os.path.join(self.pasta, nome), os.path.join(self.pasta, base + "_interrompida.f1rec"))
                except OSError:
                    pass
                self.catalogo.marcar_interrompida(nome, base + "_interrompida.f1rec")

    def _drenar(self) -> None:
        while True:
            try:
                self._processar(*self.fila.get_nowait())
            except queue.Empty:
                return

    def _processar(self, t_ns: int, ip: str, dados: bytes) -> None:
        try:
            cab = ler_cabecalho(dados)
        except PacoteInvalido:
            self.invalidos += 1
            return
        agora = time.monotonic()
        if self.fonte != ip:
            if self.fonte is None or agora - self.fonte_visto > FONTE_OCIOSA_S:
                self.fonte = ip
            else:
                self.outras_fontes[ip] += 1
                return
        self.fonte_visto = agora
        if self.pausado_disco:
            self.descartados_disco += 1
            return
        sessao = self.sessoes.get(cab.sessao_uid)
        if sessao is None and cab.sessao_uid in self.fechadas:
            sessao = self.fechadas.pop(cab.sessao_uid)
            sessao.reabrir()
            self.sessoes[cab.sessao_uid] = sessao
        if sessao is None:
            origem = ORIGEM_LOCAL if e_local(ip, self.locais) else ORIGEM_REDE
            sessao = Sessao(self.pasta, cab, ip, origem, self.porta)
            self.sessoes[cab.sessao_uid] = sessao
            self.catalogo.salvar(sessao.resumo(), "gravando", self._descartes())
        sessao.registrar(cab, t_ns, dados)
        sessao.talvez_sincronizar()

    def _descartes(self) -> int:
        return self.receptor.descartes if self.receptor else 0

    def _manutencao(self) -> None:
        agora = time.monotonic()
        for s in list(self.sessoes.values()):
            if agora - s.ultimo_pacote > SESSAO_OCIOSA_S:
                self._fechar_sessao(s)
            else:
                s.talvez_sincronizar()
        if agora - self._ultimo_disco > 10:
            self._ultimo_disco = agora
            livre = shutil.disk_usage(self.pasta).free
            if livre < DISCO_MINIMO:
                if not self.pausado_disco:
                    for s in list(self.sessoes.values()):
                        self._fechar_sessao(s)
                self.pausado_disco = True
            elif livre > DISCO_RETOMA:
                self.pausado_disco = False
        if agora - self._ultimo_catalogo > CATALOGO_S:
            self._ultimo_catalogo = agora
            for s in self.sessoes.values():
                self.catalogo.salvar(s.resumo(), "gravando", self._descartes())
        if agora - self._ultima_taxa >= 1.0:
            self._calcular_taxas(agora)
        if agora - self._ultimo_publicar >= 0.25:
            self._ultimo_publicar = agora
            self._publicar()

    def _calcular_taxas(self, agora: float) -> None:
        total = collections.Counter()
        for s in self.sessoes.values():
            total.update(s.contagem)
        dt_s = agora - self._ultima_taxa
        self._taxas = {
            spec.NOMES_PACOTE.get(k, str(k)): round((total[k] - self._contagem_anterior.get(k, 0)) / dt_s, 1)
            for k in sorted(total)
        }
        self._contagem_anterior = total
        self._ultima_taxa = agora

    def _fechar_sessao(self, s: Sessao) -> None:
        self.sessoes.pop(s.uid, None)
        s.fechar()
        self.fechadas[s.uid] = s
        while len(self.fechadas) > MAX_FECHADAS:
            self.fechadas.popitem(last=False)
        resumo = s.resumo()
        self.catalogo.salvar(resumo, "fechada", self._descartes(), _agora_iso())
        if not s.so_menu:
            item = {k: resumo[k] for k in ("uid", "inicio", "arquivo", "pista", "tipo", "plataforma", "pacotes", "bytes_disco")}
            outros = [h for h in self.historico if (h.get("uid"), h.get("inicio")) != (item["uid"], item["inicio"])]
            self.historico.clear()
            self.historico.extend([item | {"estado": "fechada"}] + outros[:9])
        self._contagem_anterior = collections.Counter()

    # --- estado para o painel ---------------------------------------------
    def _publicar(self) -> None:
        ativa = max(self.sessoes.values(), key=lambda s: s.ultimo_pacote, default=None)
        if self.pausado_disco:
            estado = "pausado_disco"
        elif ativa and time.monotonic() - ativa.ultimo_pacote < 3:
            estado = "gravando"
        else:
            estado = "aguardando"
        with self._lock:
            self._estado = {
                "estado": estado,
                "sessao": ativa.resumo() if ativa else None,
                "tempo_gravado_s": round((dt.datetime.now().astimezone() - ativa.inicio).total_seconds()) if ativa else 0,
                "taxas": self._taxas if estado == "gravando" else {},
                "fonte": self.fonte,
                "outras_fontes": dict(self.outras_fontes),
                "invalidos": self.invalidos,
                "descartados_disco": self.descartados_disco,
                "historico": list(self.historico),
                "pasta": self.pasta,
                "erro": self.erro,
            }

    def estado(self) -> dict:
        with self._lock:
            return dict(self._estado)
