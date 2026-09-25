"""Informações de rede da máquina (somente leitura, nada é aberto ou enviado)."""

import ipaddress
import socket
import subprocess
import sys


def ips_locais() -> set[str]:
    """IPs desta máquina. Serve para saber se o jogo está 'neste PC'."""
    ips = {"127.0.0.1", "::1"}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ips.add(info[4][0])
    except OSError:
        pass
    ip = ip_principal()
    if ip:
        ips.add(ip)
    return ips


def ip_principal() -> str | None:
    """IP desta máquina na rede local (o que se digita no Xbox).

    `connect` em UDP não envia pacote nenhum: só pede ao sistema a rota.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # TEST-NET-1, nunca roteado de verdade
        ip = s.getsockname()[0]
        return None if ip.startswith("0.") else ip
    except OSError:
        return None
    finally:
        s.close()


def e_local(ip: str, locais: set[str]) -> bool:
    try:
        if ipaddress.ip_address(ip).is_loopback:
            return True
    except ValueError:
        return False
    return ip in locais


def perfil_rede_windows() -> str | None:
    """'Public', 'Private' ou 'DomainAuthenticated' no Windows; None fora dele."""
    if sys.platform != "win32":
        return None
    try:
        saida = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-NetConnectionProfile | Select-Object -First 1).NetworkCategory",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        valor = saida.stdout.strip()
        return valor or None
    except (OSError, subprocess.SubprocessError):
        return None
