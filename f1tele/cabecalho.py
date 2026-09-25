"""Leitura do cabeçalho e dos poucos campos usados para rótulos."""

from typing import NamedTuple

from . import spec


class Cabecalho(NamedTuple):
    formato: int
    ano: int
    versao_major: int
    versao_minor: int
    versao_pacote: int
    id_pacote: int
    sessao_uid: int
    tempo_sessao: float
    quadro: int
    quadro_geral: int
    carro_jogador: int
    carro_secundario: int


class PacoteInvalido(ValueError):
    pass


def ler_cabecalho(dados: bytes) -> Cabecalho:
    """Lê os 29 bytes iniciais. Lança PacoteInvalido se não parecer F1."""
    if len(dados) < spec.HEADER_SIZE:
        raise PacoteInvalido(f"curto demais ({len(dados)} bytes)")
    cab = Cabecalho(*spec.HEADER.unpack_from(dados, 0))
    if not 2018 <= cab.formato <= 2099:
        raise PacoteInvalido(f"formato fora do esperado ({cab.formato})")
    if cab.id_pacote > 31:
        raise PacoteInvalido(f"id de pacote fora do esperado ({cab.id_pacote})")
    return cab


def rotulo_jogo(cab: Cabecalho) -> str:
    """Ex.: 'F1 25 v1.12 · UDP 2025'."""
    jogo = f"F1 {cab.ano:02d} v{cab.versao_major}.{cab.versao_minor:02d}"
    if cab.formato == 2026:
        return f"{jogo} · UDP 2026 (Season Pack)"
    return f"{jogo} · UDP {cab.formato}"


def ler_sessao(dados: bytes) -> dict | None:
    """Pista e tipo de sessão de um pacote Session (id 1)."""
    if len(dados) <= spec.SESSION_FORMULA:
        return None
    tipo = dados[spec.SESSION_TIPO]
    pista = int.from_bytes(dados[spec.SESSION_PISTA : spec.SESSION_PISTA + 1], "little", signed=True)
    return {
        "pista_id": pista,
        "pista": spec.PISTAS.get(pista, f"pista {pista}" if pista >= 0 else "desconhecida"),
        "tipo_id": tipo,
        "tipo": spec.TIPOS_SESSAO.get(tipo, f"sessao {tipo}"),
    }


def ler_plataforma(dados: bytes, carro: int) -> int | None:
    """Código m_platform do carro indicado num pacote Participants (id 4).

    O tamanho do registro por carro varia entre formatos (2023/2024/2025);
    ele é deduzido do tamanho do pacote. Formato desconhecido -> None.
    """
    corpo = len(dados) - spec.PARTICIPANTS_BASE
    if corpo <= 0 or corpo % spec.PARTICIPANTS_CARROS or carro >= spec.PARTICIPANTS_CARROS:
        return None
    registro = corpo // spec.PARTICIPANTS_CARROS
    offset = spec.PLATAFORMA_OFFSET_POR_REGISTRO.get(registro)
    if offset is None:
        return None
    return dados[spec.PARTICIPANTS_BASE + carro * registro + offset]
