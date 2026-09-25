"""Decodificador dos campos usados na análise, formatos UDP 2025 e 2026.

2025: spec oficial v3. 2026 (F1 25 + 2026 Season Pack): layout deduzido de
gravação real e validado contra a física (docs/spec/README.md). Só entram
campos validados; formato fora da tabela -> FormatoNaoSuportado.
"""

import struct
from dataclasses import dataclass


class FormatoNaoSuportado(ValueError):
    pass


@dataclass(frozen=True)
class Layout:
    carros: int
    lap: int  # bytes por carro em LapData
    tel: int  # CarTelemetry
    motion: int
    status: int
    damage: int
    tel_motor_u8: bool  # engineTemperature uint8 (2026) em vez de uint16


LAYOUTS = {
    2025: Layout(carros=22, lap=57, tel=60, motion=60, status=55, damage=46, tel_motor_u8=False),
    2026: Layout(carros=24, lap=57, tel=59, motion=54, status=59, damage=46, tel_motor_u8=True),
}

H = 29  # cabeçalho

_LAP = struct.Struct("<IIHBHB")  # último, atual, s1 ms, s1 min, s2 ms, s2 min
_LAP_DIST = struct.Struct("<fff")  # distância na volta, total, safety car (offset 20)
_TEL = struct.Struct("<HfffBbH")  # velocidade, acel., volante, freio, embreagem, marcha, rpm
_TEL_TEMPS = struct.Struct("<4H4B4B")  # freios, superfície, interno (offset 22)
_MOTION = struct.Struct("<6f")  # posição xyz, velocidade xyz
_STATUS_COMB = struct.Struct("<fff")  # combustível no tanque, capacidade, voltas restantes (offset 5)
_DANO = struct.Struct("<4f")  # desgaste dos pneus
_HIST_VOLTA = struct.Struct("<IHBHBHBB")  # 14 bytes


def layout(formato: int) -> Layout:
    try:
        return LAYOUTS[formato]
    except KeyError:
        raise FormatoNaoSuportado(
            f"formato UDP {formato} ainda não é decodificado (suportados: {sorted(LAYOUTS)})"
        ) from None


def _ms(ms_parte: int, minutos: int) -> int:
    return minutos * 60000 + ms_parte


def lap_data(dados: bytes, lay: Layout, carro: int) -> dict:
    o = H + carro * lay.lap
    ultimo, atual, s1ms, s1min, s2ms, s2min = _LAP.unpack_from(dados, o)
    dist, total, _sc = _LAP_DIST.unpack_from(dados, o + 20)
    return {
        "ultima_volta_ms": ultimo,
        "tempo_volta_ms": atual,
        "setor1_ms": _ms(s1ms, s1min),
        "setor2_ms": _ms(s2ms, s2min),
        "distancia": dist,
        "distancia_total": total,
        "posicao": dados[o + 32],
        "volta": dados[o + 33],
        "pit": dados[o + 34],
        "setor": dados[o + 36],
        "volta_invalida": dados[o + 37],
        "status_piloto": dados[o + 44],
    }


def telemetria(dados: bytes, lay: Layout, carro: int) -> dict:
    o = H + carro * lay.tel
    vel, acel, volante, freio, _embr, marcha, rpm = _TEL.unpack_from(dados, o)
    freios_t = _TEL_TEMPS.unpack_from(dados, o + 22)
    return {
        "velocidade": vel,
        "acelerador": acel,
        "volante": volante,
        "freio": freio,
        "marcha": marcha,
        "rpm": rpm,
        "drs": dados[o + 18],
        "temp_freios": freios_t[0:4],
        "temp_pneu_superficie": freios_t[4:8],
        "temp_pneu_interna": freios_t[8:12],
        "pressao_pneus": struct.unpack_from("<4f", dados, o + (39 if lay.tel_motor_u8 else 40)),
    }


def movimento(dados: bytes, lay: Layout, carro: int) -> dict:
    x, y, z, vx, vy, vz = _MOTION.unpack_from(dados, H + carro * lay.motion)
    return {"x": x, "y": y, "z": z, "vx": vx, "vy": vy, "vz": vz}


def status(dados: bytes, lay: Layout, carro: int) -> dict:
    o = H + carro * lay.status
    comb, cap, voltas_comb = _STATUS_COMB.unpack_from(dados, o + 5)
    return {
        "controle_tracao": dados[o],
        "abs": dados[o + 1],
        "mistura": dados[o + 2],
        "balanco_freio": dados[o + 3],
        "combustivel": comb,
        "combustivel_voltas": voltas_comb,
        "composto_real": dados[o + 25],
        "composto_visual": dados[o + 26],
        "idade_pneu": dados[o + 27],
    }


def dano(dados: bytes, lay: Layout, carro: int) -> dict:
    return {"desgaste_pneus": _DANO.unpack_from(dados, H + carro * lay.damage)}


def historico(dados: bytes) -> dict:
    """SessionHistory (id 11): voltas de UM carro (o pacote alterna entre carros)."""
    carro, n_voltas = dados[H], dados[H + 1]
    voltas = []
    for i in range(min(n_voltas, 100)):
        t, s1ms, s1m, s2ms, s2m, s3ms, s3m, flags = _HIST_VOLTA.unpack_from(dados, H + 7 + i * 14)
        voltas.append({
            "numero": i + 1,
            "tempo_ms": t,
            "setores_ms": (_ms(s1ms, s1m), _ms(s2ms, s2m), _ms(s3ms, s3m)),
            "valida": bool(flags & 0x01),
            "setores_validos": (bool(flags & 0x02), bool(flags & 0x04), bool(flags & 0x08)),
        })
    return {"carro": carro, "voltas": voltas, "melhor_volta": dados[H + 3]}


def sessao(dados: bytes) -> dict:
    return {
        "clima": dados[H],
        "temp_pista": int.from_bytes(dados[H + 1:H + 2], "little", signed=True),
        "temp_ar": int.from_bytes(dados[H + 2:H + 3], "little", signed=True),
        "voltas_total": dados[H + 3],
        "comprimento_pista": struct.unpack_from("<H", dados, H + 4)[0],
        "tipo": dados[H + 6],
        "pista": int.from_bytes(dados[H + 7:H + 8], "little", signed=True),
        "formula": dados[H + 8],
    }


COMPOSTOS = {16: "C5", 17: "C4", 18: "C3", 19: "C2", 20: "C1", 21: "C0", 22: "C6", 7: "Intermediário", 8: "Chuva"}
COMPOSTOS_VISUAIS = {16: "Macio", 17: "Médio", 18: "Duro", 7: "Intermediário", 8: "Chuva"}
CLIMA = {0: "Limpo", 1: "Poucas nuvens", 2: "Nublado", 3: "Chuva fraca", 4: "Chuva forte", 5: "Tempestade"}
