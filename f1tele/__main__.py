"""f1tele gravar | reproduzir | inventario | sintetico"""

import argparse
import json
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path

from . import __version__, rede, sintetico
from .gravador import Gravador
from .painel import Painel
from .receptor import Receptor
from .reprodutor import inventario, reproduzir

PORTA_JOGO = 20777
PORTA_PAINEL = 8750


def pasta_padrao() -> str:
    return str(Path.home() / "Documents" / "F1 Telemetria" / "gravacoes")


def _destino(texto: str) -> tuple[str, int]:
    host, _, porta = texto.rpartition(":")
    if not host or not porta.isdigit():
        raise argparse.ArgumentTypeError("use host:porta, ex.: 127.0.0.1:20778")
    return host, int(porta)


def _pausar_se_janela() -> None:
    # Duplo clique no .exe: a janela não pode sumir antes de a pessoa ler o erro.
    if getattr(sys, "frozen", False):
        try:
            input("\nAperte Enter para fechar.")
        except EOFError:
            pass


def _fechar_janela_no_windows(parar: threading.Event, gravador) -> None:
    """Fechar a janela do console dá ~5 s ao processo: usa esse tempo para fechar as sessões."""
    import ctypes

    @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
    def tratador(_evento):
        parar.set()
        gravador.join(4)
        return 1

    ctypes.windll.kernel32.SetConsoleCtrlHandler(tratador, 1)
    _fechar_janela_no_windows.ref = tratador  # mantém vivo enquanto o programa roda


def cmd_gravar(args) -> int:
    locais = rede.ips_locais()
    ip = rede.ip_principal()
    try:
        receptor = Receptor(args.porta, repasses=args.repassar or ())
    except OSError as exc:
        print(f"Não consegui ouvir a porta {args.porta}: {exc}")
        print("Outro programa de telemetria (ex.: F1 Laps) pode estar usando essa porta.")
        print("Feche-o ou use --repassar para os dois funcionarem juntos (veja o guia).")
        _pausar_se_janela()
        return 2
    gravador = Gravador(args.pasta, receptor.fila, locais, receptor.porta, receptor)
    aberto = time.monotonic()
    perfil = rede.perfil_rede_windows()

    def estado():
        return {
            "versao": __version__,
            "ip_rede": ip,
            "perfil_rede": perfil,
            "segundos_aberto": round(time.monotonic() - aberto),
            "receptor": receptor.estado(),
            "gravador": gravador.estado(),
        }

    try:
        painel = Painel(estado, args.pasta, args.painel_porta)
    except OSError as exc:
        print(f"Painel indisponível na porta {args.painel_porta} ({exc}); o gravador segue sem painel.")
        painel = None

    receptor.start()
    gravador.start()
    if painel:
        painel.iniciar()
    print(f"Gravador F1 25 v{__version__}")
    print(f"Ouvindo UDP na porta {receptor.porta}. IP deste computador na rede: {ip or 'desconhecido'}")
    print(f"Gravações em: {args.pasta}")
    if args.repassar:
        print("Repassando para: " + ", ".join(f"{h}:{p}" for h, p in args.repassar))
    if perfil == "Public":
        print("ATENÇÃO: a rede está como Pública no Windows; mude para Privada ou o console pode ser bloqueado.")
    if painel:
        print(f"Painel: {painel.url}")
        if not args.sem_navegador:
            webbrowser.open(painel.url)
    print("Para encerrar: Ctrl+C ou feche esta janela.\n")

    parar = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: parar.set())
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: parar.set())
    if sys.platform == "win32":
        _fechar_janela_no_windows(parar, gravador)
    ultimo = ""
    while not parar.wait(1.0) and gravador.is_alive():
        g = gravador.estado()
        linha = g["sessao"]["rotulo"] if g.get("sessao") else ""
        if g.get("estado") == "gravando" and linha != ultimo:
            print(f"Gravando: {linha}")
            ultimo = linha
    print("Encerrando…")
    receptor.parar()
    receptor.join(2)
    gravador.parar()
    gravador.join(10)
    if painel:
        painel.parar()
    if gravador.erro:
        print(f"Erro no gravador: {gravador.erro}")
        _pausar_se_janela()
        return 1
    print("Sessões salvas.")
    return 0


def cmd_reproduzir(args) -> int:
    n = reproduzir(args.arquivo, args.host, args.porta, args.velocidade, args.desde * 60, args.loop)
    print(f"{n} pacotes enviados para {args.host}:{args.porta}")
    return 0


def cmd_inventario(args) -> int:
    print(json.dumps(inventario(args.arquivo), ensure_ascii=False, indent=2))
    return 0


def cmd_analisar(args) -> int:
    from .analise import SemDados
    from .decodificador import FormatoNaoSuportado
    from .relatorio import gerar_arquivo

    try:
        destino = gerar_arquivo(args.arquivo, args.saida)
    except (SemDados, FormatoNaoSuportado) as exc:
        print(f"Não deu para analisar: {exc}")
        return 1
    print(f"Análise: {destino}")
    if not args.sem_navegador:
        webbrowser.open(Path(destino).resolve().as_uri())
    return 0


def cmd_sintetico(args) -> int:
    pacotes = sintetico.gerar(args.minutos * 60, args.hz, plataforma=args.plataforma, pista=args.pista,
                              tipo_sessao=args.tipo, perder_a_cada=args.perder_a_cada)
    n = sintetico.enviar(pacotes, args.host, args.porta, args.velocidade)
    print(f"{n} pacotes sintéticos enviados para {args.host}:{args.porta}")
    return 0


def main(argv=None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        try:  # console do Windows redirecionado (cp1252) não pode derrubar o programa por um acento
            fluxo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog="f1tele", description="Gravador de telemetria do F1 25 (Xbox, PlayStation ou PC).")
    p.add_argument("--versao", action="version", version=f"f1tele {__version__}")
    sub = p.add_subparsers(dest="comando")

    g = sub.add_parser("gravar", help="ouve o jogo e grava as sessões (padrão)")
    g.add_argument("--porta", type=int, default=PORTA_JOGO)
    g.add_argument("--pasta", default=pasta_padrao())
    g.add_argument("--repassar", type=_destino, action="append", metavar="HOST:PORTA",
                   help="reenvia cada pacote idêntico (ex.: F1 Laps em 127.0.0.1:20778); até 3")
    g.add_argument("--painel-porta", type=int, default=PORTA_PAINEL)
    g.add_argument("--sem-navegador", action="store_true")
    g.set_defaults(func=cmd_gravar)

    r = sub.add_parser("reproduzir", help="reenvia uma gravação como se o jogo estivesse ligado")
    r.add_argument("arquivo")
    r.add_argument("--host", default="127.0.0.1")
    r.add_argument("--porta", type=int, default=PORTA_JOGO)
    r.add_argument("--velocidade", type=float, default=1.0, help="1 = tempo real, 2 = dobro, 0 = máximo")
    r.add_argument("--desde", type=float, default=0.0, help="começar a partir deste minuto")
    r.add_argument("--loop", action="store_true")
    r.set_defaults(func=cmd_reproduzir)

    i = sub.add_parser("inventario", help="resumo de uma gravação")
    i.add_argument("arquivo")
    i.set_defaults(func=cmd_inventario)

    a = sub.add_parser("analisar", help="gera a análise pós-sessão (HTML) de uma gravação")
    a.add_argument("arquivo")
    a.add_argument("--saida", help="pasta do HTML (padrão: analises/ ao lado da gravação)")
    a.add_argument("--sem-navegador", action="store_true")
    a.set_defaults(func=cmd_analisar)

    s = sub.add_parser("sintetico", help="envia pacotes falsos (formato 2025) para testar o encanamento")
    s.add_argument("--minutos", type=float, default=1.0)
    s.add_argument("--hz", type=int, default=60)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--porta", type=int, default=PORTA_JOGO)
    s.add_argument("--velocidade", type=float, default=1.0)
    s.add_argument("--plataforma", type=int, default=4, help="1 Steam, 3 PlayStation, 4 Xbox, 6 EA")
    s.add_argument("--pista", type=int, default=11)
    s.add_argument("--tipo", type=int, default=18)
    s.add_argument("--perder-a-cada", type=int, default=0)
    s.set_defaults(func=cmd_sintetico)

    args = p.parse_args(argv)
    if args.comando is None:  # duplo clique no .exe
        args = p.parse_args(["gravar", *(argv or [])])
    if getattr(args, "repassar", None) and len(args.repassar) > 3:
        p.error("no máximo 3 destinos de repasse")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
