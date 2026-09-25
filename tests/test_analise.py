"""Decodificador + análise com pista sintética cuja resposta é conhecida."""

import struct

import pytest

from f1tele import decodificador as dec
from f1tele import spec
from f1tele.analise import analisar
from f1tele.relatorio import gerar_arquivo, gerar_html

from . import pista_sintetica as ps


@pytest.mark.parametrize("formato,pressao_off", [(2025, 40), (2026, 39)])
def test_telemetria_campos_nos_dois_formatos(formato, pressao_off):
    lay = dec.layout(formato)
    d = bytearray(spec.TAMANHOS_POR_FORMATO[formato][6])
    o = 29 + 5 * lay.tel
    struct.pack_into("<HfffBbH", d, o, 287, 0.75, -0.1, 0.25, 0, 7, 11500)
    struct.pack_into("<4H", d, o + 22, 500, 510, 520, 530)
    struct.pack_into("<4f", d, o + pressao_off, 21.0, 21.5, 23.0, 23.5)
    t = dec.telemetria(bytes(d), lay, 5)
    assert (t["velocidade"], t["marcha"], t["rpm"]) == (287, 7, 11500)
    assert t["acelerador"] == pytest.approx(0.75) and t["freio"] == pytest.approx(0.25)
    assert t["temp_freios"] == (500, 510, 520, 530)
    assert t["pressao_pneus"] == pytest.approx((21.0, 21.5, 23.0, 23.5))


@pytest.mark.parametrize("formato", [2025, 2026])
def test_lapdata_campos(formato):
    lay = dec.layout(formato)
    d = bytearray(spec.TAMANHOS_POR_FORMATO[formato][2])
    o = 29 + (lay.carros - 1) * lay.lap
    struct.pack_into("<IIHBHB", d, o, 83269, 41000, 29030, 0, 19068, 0)
    struct.pack_into("<ff", d, o + 20, 1234.5, 9999.0)
    d[o + 33], d[o + 37] = 4, 1
    ld = dec.lap_data(bytes(d), lay, lay.carros - 1)
    assert ld["ultima_volta_ms"] == 83269 and ld["tempo_volta_ms"] == 41000
    assert ld["distancia"] == pytest.approx(1234.5) and ld["volta"] == 4 and ld["volta_invalida"] == 1


def test_formato_desconhecido_da_erro_claro():
    with pytest.raises(dec.FormatoNaoSuportado):
        dec.layout(2031)


@pytest.fixture(scope="module")
def sessao_sintetica(tmp_path_factory):
    caminho = str(tmp_path_factory.mktemp("sint") / "sessao.f1rec")
    # volta 1 e 2 limpas; volta 3 freia 25 m antes na curva 2 (índice 1)
    tempos = ps.gravar(caminho, [{}, {}, {1: 25}])
    return caminho, tempos


def test_analise_acha_a_curva_e_o_motivo(sessao_sintetica):
    caminho, tempos = sessao_sintetica
    r = analisar(caminho)
    assert r["formato"] == 2026 and r["comprimento_m"] == ps.COMPRIMENTO
    assert [v["numero"] for v in r["voltas"] if v["completa"]] == [1, 2, 3]
    assert tempos[2] > tempos[0]
    apices = [c["dist_apex"] for c in r["curvas"]]
    assert len(apices) == 2 and abs(apices[0] - 600) <= 15 and abs(apices[1] - 1400) <= 15
    assert r["top_curvas"][0] == "C2"
    c2 = r["curvas"][1]
    assert c2["freio_dif_m"] == pytest.approx(12.5, abs=6)  # média de (0 da volta 2, 25 da volta 3)
    v3 = next(v for v in r["voltas"] if v["numero"] == 3)
    assert v3["curvas"]["C2"]["perda_s"] > 0.1 and abs(v3["curvas"]["C1"]["perda_s"]) < 0.05
    # a soma das perdas por curva explica o delta da volta
    assert sum(m["perda_s"] for m in v3["curvas"].values()) == pytest.approx(v3["delta_s"], rel=0.15, abs=0.03)


def test_relatorio_html_autocontido(sessao_sintetica, tmp_path):
    caminho, _ = sessao_sintetica
    html = gerar_html(analisar(caminho))
    assert "<script" in html and "http://" not in html and "https://" not in html
    assert html.count("</script>") == 2  # o JSON embutido não fecha a tag
    destino = gerar_arquivo(caminho, str(tmp_path))
    assert destino.endswith("sessao.html")
    assert gerar_arquivo(caminho, str(tmp_path)) == destino  # cache
