import gzip
import shutil

import pytest

from f1tele.formato import ArquivoInvalido, Escritor, Leitor


def test_ida_e_volta(tmp_path):
    caminho = str(tmp_path / "a.f1rec")
    esc = Escritor(caminho, {"x": "ção"})
    regs = [(1_000 + i, i % 2, bytes([i % 256]) * (i + 1)) for i in range(500)]
    for r in regs:
        esc.escrever(*r)
    esc.fechar()
    with Leitor(caminho) as leitor:
        assert leitor.meta == {"x": "ção"}
        lidos = [tuple(r) for r in leitor]
        assert not leitor.truncado
    assert lidos == regs


def test_arquivo_cortado_e_legivel_ate_o_ultimo_flush(tmp_path):
    caminho = str(tmp_path / "a.f1rec")
    esc = Escritor(caminho, {})
    for i in range(300):
        esc.escrever(i, 0, b"A" * 1300)
    esc.sincronizar()
    for i in range(300, 350):
        esc.escrever(i, 0, b"B" * 1300)  # ainda no buffer do compressor
    # simula o processo morrendo: copia o que está no disco sem fechar
    shutil.copy(caminho, tmp_path / "cortado.f1rec")
    with Leitor(str(tmp_path / "cortado.f1rec")) as leitor:
        lidos = list(leitor)
        assert leitor.truncado
    assert len(lidos) >= 300 and all(r.t_ns == i for i, r in enumerate(lidos))
    esc.fechar()


def test_arquivo_que_nao_e_gravacao(tmp_path):
    p = tmp_path / "x.f1rec"
    with gzip.open(p, "wb") as f:
        f.write(b"outra coisa qualquer")
    with pytest.raises(ArquivoInvalido):
        Leitor(str(p))
