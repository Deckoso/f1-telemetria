"""CP-0: cabeçalho, tamanhos da spec e campos de rótulo."""

import struct

import pytest

from f1tele import spec
from f1tele.cabecalho import PacoteInvalido, ler_cabecalho, ler_plataforma, ler_sessao, rotulo_jogo
from f1tele.sintetico import montar_pacote, pacote_lixo


def test_cabecalho_tem_29_bytes():
    assert spec.HEADER_SIZE == 29


@pytest.mark.parametrize("pid", sorted(spec.TAMANHOS_2025))
def test_16_tipos_com_tamanho_da_spec(pid):
    dados = montar_pacote(pid, 0xABCDEF, 12.5, 900)
    assert len(dados) == spec.TAMANHOS_2025[pid]
    cab = ler_cabecalho(dados)
    assert (cab.formato, cab.ano, cab.id_pacote, cab.sessao_uid, cab.quadro) == (2025, 25, pid, 0xABCDEF, 900)
    assert cab.tempo_sessao == pytest.approx(12.5)


def test_cabecalho_montado_a_mao_campo_a_campo():
    bruto = struct.pack("<HBBBBBQfIIBB", 2025, 25, 1, 7, 1, 6, 42, 3.0, 10, 11, 5, 255)
    cab = ler_cabecalho(bruto + b"\0" * 10)
    assert cab.versao_major == 1 and cab.versao_minor == 7
    assert cab.quadro_geral == 11 and cab.carro_jogador == 5 and cab.carro_secundario == 255
    assert rotulo_jogo(cab) == "F1 25 v1.07 · UDP 2025"


@pytest.mark.parametrize("dados", [b"", b"\x01" * 10, pacote_lixo(), b"\xff" * 40])
def test_lixo_nao_passa(dados):
    with pytest.raises(PacoteInvalido):
        ler_cabecalho(dados)


def test_formato_2026_e_desconhecido_sao_aceitos_no_cabecalho():
    assert "Season Pack" in rotulo_jogo(ler_cabecalho(montar_pacote(6, 1, 0, 0, formato=2026)))
    assert ler_cabecalho(montar_pacote(6, 1, 0, 0, formato=2031)).formato == 2031


def test_sessao_pista_e_tipo():
    info = ler_sessao(montar_pacote(1, 1, 0, 0, pista=13, tipo_sessao=15))
    assert info["pista"] == "Suzuka" and info["tipo"] == "Corrida"
    assert ler_sessao(montar_pacote(1, 1, 0, 0, pista=-1))["pista"] == "desconhecida"


@pytest.mark.parametrize("registro,offset,tamanho", [(57, 43, 1284), (60, 59, 1350), (58, 57, 1306)])
def test_plataforma_nos_tres_layouts(registro, offset, tamanho):
    assert spec.PARTICIPANTS_BASE + 22 * registro == tamanho
    dados = bytearray(tamanho)
    dados[spec.PARTICIPANTS_BASE + 3 * registro + offset] = 4
    assert ler_plataforma(bytes(dados), 3) == 4
    assert ler_plataforma(bytes(dados), 2) == 0


def test_plataforma_layout_desconhecido_devolve_none():
    assert ler_plataforma(bytes(30 + 22 * 61), 0) is None
    assert ler_plataforma(bytes(100), 0) is None
