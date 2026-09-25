"""Formato de gravação .f1rec.

Arquivo = stream gzip contendo:
    b"F1REC\\0" | u16 versão | u32 tamanho | JSON de metadados
    registros: u32 tamanho | u64 t_recv_ns | u8 origem | bytes exatos do pacote

`origem`: 0 = este computador, 1 = outro aparelho da rede.
O gravador faz flush de sincronização periódico: um arquivo interrompido
(queda de energia, processo morto) continua legível até o último flush.
"""

import gzip
import json
import struct
import zlib
from typing import Iterator, NamedTuple

MAGICA = b"F1REC\0"
VERSAO_FORMATO = 1
_PREFIXO = struct.Struct("<HI")
_REGISTRO = struct.Struct("<IQB")

ORIGEM_LOCAL = 0
ORIGEM_REDE = 1


class Registro(NamedTuple):
    t_ns: int
    origem: int
    dados: bytes


class ArquivoInvalido(ValueError):
    pass


class Escritor:
    def __init__(self, caminho: str, meta: dict, nivel: int = 6):
        self.caminho = caminho
        self._arq = gzip.open(caminho, "wb", compresslevel=nivel)
        bruto = json.dumps(meta, ensure_ascii=False).encode("utf-8")
        self._arq.write(MAGICA + _PREFIXO.pack(VERSAO_FORMATO, len(bruto)) + bruto)
        self.bytes_brutos = 0
        self.registros = 0

    def escrever(self, t_ns: int, origem: int, dados: bytes) -> None:
        self._arq.write(_REGISTRO.pack(len(dados), t_ns, origem))
        self._arq.write(dados)
        self.bytes_brutos += len(dados)
        self.registros += 1

    def sincronizar(self) -> None:
        """Descarrega o compressor até um ponto legível e manda ao disco."""
        self._arq.flush(zlib_mode=zlib.Z_SYNC_FLUSH)
        self._arq.fileobj.flush()

    def fechar(self) -> None:
        self._arq.close()


def _ler_exato(arq, n: int) -> bytes | None:
    """Lê n bytes; None se o arquivo acabou (inclusive truncado)."""
    try:
        bloco = arq.read(n)
    except (EOFError, zlib.error, OSError):
        return None
    if len(bloco) < n:
        return None
    return bloco


class Leitor:
    """Lê metadados e registros. Tolera arquivo truncado: para no último registro completo."""

    def __init__(self, caminho: str):
        self.caminho = caminho
        self._arq = gzip.open(caminho, "rb")
        inicio = _ler_exato(self._arq, len(MAGICA) + _PREFIXO.size)
        if inicio is None or not inicio.startswith(MAGICA):
            self._arq.close()
            raise ArquivoInvalido(f"{caminho} não é uma gravação .f1rec")
        versao, tamanho = _PREFIXO.unpack_from(inicio, len(MAGICA))
        if versao > VERSAO_FORMATO:
            self._arq.close()
            raise ArquivoInvalido(f"versão de arquivo {versao} é mais nova que este programa")
        bruto = _ler_exato(self._arq, tamanho)
        if bruto is None:
            self._arq.close()
            raise ArquivoInvalido(f"{caminho}: metadados incompletos")
        self.meta = json.loads(bruto.decode("utf-8"))
        self.truncado = False

    def __iter__(self) -> Iterator[Registro]:
        while True:
            cab = _ler_exato(self._arq, _REGISTRO.size)
            if cab is None:
                self.truncado = self._acabou_sem_fim()
                return
            tamanho, t_ns, origem = _REGISTRO.unpack(cab)
            dados = _ler_exato(self._arq, tamanho)
            if dados is None:
                self.truncado = True
                return
            yield Registro(t_ns, origem, dados)

    def _acabou_sem_fim(self) -> bool:
        # gzip.read devolve b"" no fim limpo; um EOFError indica stream sem trailer.
        try:
            self._arq.read(1)
            return False
        except (EOFError, zlib.error, OSError):
            return True

    def fechar(self) -> None:
        self._arq.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fechar()
