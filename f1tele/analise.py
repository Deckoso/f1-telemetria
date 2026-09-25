"""Análise pós-sessão: voltas no eixo da distância, curvas e onde se perde tempo.

Só o carro do jogador. Tudo em Python puro (sem numpy), com memória limitada:
as amostras são guardadas por volta e só os campos usados.
"""

import bisect
import math
import statistics
from dataclasses import dataclass, field

from . import decodificador as dec
from . import spec
from .cabecalho import PacoteInvalido, ler_cabecalho, ler_plataforma
from .formato import Leitor

PASSO_M = 5.0  # grade de distância
MARGEM_VOLTA_M = 60.0  # volta completa cobre de <= 60 m até >= comprimento - 60 m
QUEDA_CURVA_KMH = 15.0
FREIO_ON = 0.15
ACEL_CHEIO = 0.95


class SemDados(ValueError):
    pass


@dataclass
class Volta:
    numero: int
    dist: list = field(default_factory=list)
    t_ms: list = field(default_factory=list)
    vel: list = field(default_factory=list)
    acel: list = field(default_factory=list)
    freio: list = field(default_factory=list)
    marcha: list = field(default_factory=list)
    x: list = field(default_factory=list)
    z: list = field(default_factory=list)
    temp_sup: list = field(default_factory=list)  # tuplas (TE, TD, DE, DD) na ordem do jogo: RL, RR, FL, FR
    invalida: bool = False
    pit: bool = False
    tempo_ms: int = 0
    setores_ms: tuple = (0, 0, 0)
    valida_oficial: bool | None = None
    desgaste_fim: tuple | None = None
    composto: str | None = None
    idade_pneu: int | None = None
    combustivel_fim: float | None = None

    def adicionar(self, d, t, vel, acel, freio, marcha, x, z, temp):
        # flashback: a distância volta -> descarta o que ficou "no futuro"
        if self.dist and d < self.dist[-1] - 5.0:
            corte = bisect.bisect_left(self.dist, d)
            for coluna in (self.dist, self.t_ms, self.vel, self.acel, self.freio, self.marcha, self.x, self.z, self.temp_sup):
                del coluna[corte:]
        if self.dist and d <= self.dist[-1]:
            return
        self.dist.append(d)
        self.t_ms.append(t)
        self.vel.append(vel)
        self.acel.append(acel)
        self.freio.append(freio)
        self.marcha.append(marcha)
        self.x.append(x)
        self.z.append(z)
        self.temp_sup.append(temp)

    def completa(self, comprimento: float) -> bool:
        return bool(self.dist) and self.dist[0] <= MARGEM_VOLTA_M and self.dist[-1] >= comprimento - MARGEM_VOLTA_M and self.tempo_ms > 0


def _interp(xs, ys, x):
    i = bisect.bisect_left(xs, x)
    if i <= 0:
        return ys[0]
    if i >= len(xs):
        return ys[-1]
    x0, x1 = xs[i - 1], xs[i]
    if x1 == x0:
        return ys[i]
    return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - x0) / (x1 - x0)


def _reamostrar(volta: Volta, grade: list, comprimento: float) -> dict:
    """Colunas na grade de distância. O tempo no fim é o oficial da volta."""
    xs = list(volta.dist) + [comprimento]
    t = list(volta.t_ms) + [volta.tempo_ms]
    ult = lambda col: list(col) + [col[-1]]  # noqa: E731
    return {
        "t": [_interp(xs, t, d) / 1000.0 for d in grade],
        "vel": [_interp(xs, ult(volta.vel), d) for d in grade],
        "acel": [_interp(xs, ult(volta.acel), d) for d in grade],
        "freio": [_interp(xs, ult(volta.freio), d) for d in grade],
        "marcha": [volta.marcha[min(bisect.bisect_left(volta.dist, d), len(volta.marcha) - 1)] for d in grade],
        "x": [_interp(xs, ult(volta.x), d) for d in grade],
        "z": [_interp(xs, ult(volta.z), d) for d in grade],
    }


def _suavizar(vals, janela=2):
    n = len(vals)
    return [sum(vals[max(0, i - janela):min(n, i + janela + 1)]) / (min(n, i + janela + 1) - max(0, i - janela)) for i in range(n)]


def _curvas(ref: dict, grade: list) -> list:
    """Curvas na volta de referência: mínimos de velocidade com queda >= 15 km/h."""
    v = _suavizar(ref["vel"])
    n = len(v)
    passos = lambda m: max(1, int(m / PASSO_M))  # noqa: E731
    w = passos(60)
    minimos = []
    for i in range(n):
        janela = v[max(0, i - w):min(n, i + w + 1)]
        if v[i] != min(janela):
            continue
        antes = max(v[max(0, i - passos(400)):i + 1])
        depois = max(v[i:min(n, i + passos(400)) + 1])
        if antes - v[i] >= QUEDA_CURVA_KMH and depois - v[i] >= QUEDA_CURVA_KMH * 0.6:
            if minimos and i - minimos[-1] < passos(80):
                if v[i] < v[minimos[-1]]:
                    minimos[-1] = i
                continue
            minimos.append(i)
    curvas = []
    for k, a in enumerate(minimos):
        lim_ini = minimos[k - 1] if k else 0
        lim_fim = minimos[k + 1] if k + 1 < len(minimos) else n - 1
        ini_busca = max(lim_ini, a - passos(350))
        ini = max(range(ini_busca, a + 1), key=lambda j: v[j])  # pico de velocidade antes
        fim = a
        for j in range(a, min(lim_fim, a + passos(350)) + 1):
            fim = j
            if ref["acel"][j] >= ACEL_CHEIO and v[j] > v[a] + 5:
                break
        curvas.append({"nome": f"C{k + 1}", "ini": ini, "apex": a, "fim": max(fim, a + 1), "lim_ini": lim_ini})
    return curvas


def _metricas_curva(col: dict, c: dict, delta: list) -> dict:
    a, ini, fim = c["apex"], c["ini"], c["fim"]
    # frenagem procurada só a partir do pico de velocidade (−30 m), nunca na curva anterior
    lo = max(c.get("lim_ini", 0) + 1 if c.get("lim_ini") else 0, ini - int(30 / PASSO_M))
    freio_idx = next((j for j in range(lo, a + 1) if col["freio"][j] >= FREIO_ON), None)
    ret_idx = next((j for j in range(a, len(col["acel"])) if col["acel"][j] >= ACEL_CHEIO), None)
    zona = range(max(0, a - int(60 / PASSO_M)), min(len(col["vel"]), a + int(60 / PASSO_M) + 1))
    vmin_j = min(zona, key=lambda j: col["vel"][j])
    return {
        "perda_s": (delta[fim] - delta[ini]) if delta is not None else 0.0,
        "freio_m_antes_apex": (a - freio_idx) * PASSO_M if freio_idx is not None else None,
        "vmin": round(col["vel"][vmin_j], 1),
        "retomada_m_apos_apex": (ret_idx - a) * PASSO_M if ret_idx is not None else None,
        "marcha_min": min(col["marcha"][j] for j in zona),
        "freio_max": round(max(col["freio"][j] for j in range(ini, a + 1)), 2),
    }


def _conselho(nome: str, med: dict) -> str:
    if med.get("perda_media_s", 0) <= 0.02:
        return f"Na {nome} você está no nível da sua melhor volta (ou melhor)."
    partes = []
    f, v, r = med.get("freio_dif_m"), med.get("vmin_dif"), med.get("retomada_dif_m")
    if med.get("freia_sem_ref_m") is not None:
        partes.append(
            f"freia (em média {med['freia_sem_ref_m']:.0f} m antes do ápice) onde na sua melhor volta passou sem frear"
        )
        if v is not None and v < -3:
            partes.append(f"e o ápice sai {abs(v):.0f} km/h mais lento")
        return f"Na {nome} você " + " ".join(partes) + "."
    if f is not None and f > 8:
        partes.append(f"freia em média {f:.0f} m antes do que na sua melhor volta")
    elif f is not None and f < -8 and v is not None and v < -3:
        partes.append(f"freia {abs(f):.0f} m mais tarde, mas chega rápido demais e o ápice sai {abs(v):.0f} km/h mais lento")
    if v is not None and v < -3 and not (f is not None and f < -8):
        partes.append(f"passa pelo ápice {abs(v):.0f} km/h mais lento")
    if r is not None and r > 10:
        partes.append(f"volta ao acelerador cheio {r:.0f} m depois")
    if not partes:
        if v is not None and v > 3:
            partes.append(f"leva {v:.0f} km/h a mais no ápice, mas perde na saída: provavelmente entrou rápido demais")
        else:
            return f"Na {nome} a perda está espalhada pela zona (trajetória/linha): compare o gráfico de velocidade."
    return f"Na {nome} você " + "; ".join(partes) + "."


def _carregar(caminho: str) -> dict:
    voltas: dict[int, Volta] = {}
    info = {}
    hist = None
    lay = None
    formato = None
    carro = None
    plataforma = None
    taxa_quadros = []
    pendentes: dict[int, dict] = {}
    ult_status = ult_dano = None
    temp_atual = (0, 0, 0, 0)
    meta = {}
    with Leitor(caminho) as leitor:
        meta = leitor.meta
        for reg in leitor:
            try:
                cab = ler_cabecalho(reg.dados)
            except PacoteInvalido:
                continue
            if lay is None:
                if cab.formato not in dec.LAYOUTS:
                    if cab.id_pacote in (2, 6):
                        raise dec.FormatoNaoSuportado(f"formato UDP {cab.formato} ainda não é decodificado")
                    continue
                formato, lay = cab.formato, dec.layout(cab.formato)
            if cab.formato != formato:
                continue
            carro = cab.carro_jogador
            if carro >= lay.carros:
                continue
            pid = cab.id_pacote
            d = reg.dados
            if pid == 1:
                info = dec.sessao(d)
            elif pid == 4:
                codigo = ler_plataforma(d, carro)
                if codigo not in (None, 255):
                    plataforma = codigo
            elif pid == 11:
                if d[29] == carro:
                    hist = dec.historico(d)
            elif pid == 7:
                ult_status = dec.status(d, lay, carro)
            elif pid == 10:
                ult_dano = dec.dano(d, lay, carro)
            elif pid in (0, 2, 6):
                q = pendentes.setdefault(cab.quadro_geral, {})
                if pid == 0:
                    q["m"] = dec.movimento(d, lay, carro)
                elif pid == 2:
                    q["l"] = dec.lap_data(d, lay, carro)
                    q["t"] = cab.tempo_sessao
                else:
                    q["tel"] = dec.telemetria(d, lay, carro)
                if "l" in q and "tel" in q and ("m" in q or len(pendentes) > 3):
                    l, tel, m = q["l"], q["tel"], q.get("m")
                    del pendentes[cab.quadro_geral]
                    taxa_quadros.append(q["t"])
                    if len(taxa_quadros) > 400:
                        del taxa_quadros[:200]
                    if l["distancia"] < 0 or l["volta"] == 0:
                        continue
                    v = voltas.get(l["volta"])
                    if v is None:
                        v = voltas[l["volta"]] = Volta(l["volta"])
                        # a volta anterior terminou: fecha pneus/combustível dela
                        ant = voltas.get(l["volta"] - 1)
                        if ant is not None:
                            if ult_dano:
                                ant.desgaste_fim = tuple(round(x, 1) for x in ult_dano["desgaste_pneus"])
                            if ult_status:
                                ant.combustivel_fim = round(ult_status["combustivel"], 2)
                            if not ant.tempo_ms and l["ultima_volta_ms"]:
                                ant.tempo_ms = l["ultima_volta_ms"]
                    if l["volta_invalida"]:
                        v.invalida = True
                    if l["pit"]:
                        v.pit = True
                    if ult_status:
                        v.composto = dec.COMPOSTOS_VISUAIS.get(ult_status["composto_visual"], str(ult_status["composto_visual"]))
                        v.idade_pneu = ult_status["idade_pneu"]
                    temp_atual = tel["temp_pneu_superficie"]
                    v.adicionar(l["distancia"], l["tempo_volta_ms"], tel["velocidade"], tel["acelerador"], tel["freio"],
                                tel["marcha"], m["x"] if m else 0.0, m["z"] if m else 0.0, temp_atual)
                # descarta quadros antigos incompletos (memória limitada)
                if len(pendentes) > 8:
                    for k in sorted(pendentes)[:-4]:
                        del pendentes[k]
    if lay is None:
        raise SemDados("a gravação não tem pacotes de volta/telemetria")
    if hist:
        for h in hist["voltas"]:
            v = voltas.get(h["numero"])
            if v is not None and h["tempo_ms"]:
                v.tempo_ms = h["tempo_ms"]
                v.setores_ms = h["setores_ms"]
                v.valida_oficial = h["valida"]
    hz = None
    if len(taxa_quadros) > 20:
        difs = [b - a for a, b in zip(taxa_quadros, taxa_quadros[1:]) if 0 < b - a < 1]
        if difs:
            hz = round(1 / statistics.median(difs))
    return {"voltas": voltas, "info": info, "formato": formato, "plataforma": plataforma, "meta": meta, "hz": hz}


def analisar(caminho: str) -> dict:
    dados = _carregar(caminho)
    info = dados["info"]
    comprimento = float(info.get("comprimento_pista") or 0)
    voltas = dados["voltas"]
    if not comprimento and voltas:
        comprimento = max(max(v.dist) for v in voltas.values() if v.dist)
    completas = [v for v in sorted(voltas.values(), key=lambda v: v.numero) if v.completa(comprimento)]
    validas = [v for v in completas if not v.invalida and v.valida_oficial is not False and not v.pit]
    pista = spec.PISTAS.get(info.get("pista"), "pista desconhecida") if info else "pista desconhecida"
    resultado = {
        "arquivo": caminho,
        "jogo": dados["meta"].get("jogo"),
        "inicio": dados["meta"].get("inicio"),
        "plataforma": spec.PLATAFORMAS.get(dados["plataforma"]) if dados["plataforma"] is not None else None,
        "origem": dados["meta"].get("origem"),
        "pista": pista,
        "sessao": spec.TIPOS_SESSAO.get(info.get("tipo"), "sessão") if info else "sessão",
        "clima": dec.CLIMA.get(info.get("clima")) if info else None,
        "temp_pista": info.get("temp_pista"),
        "temp_ar": info.get("temp_ar"),
        "comprimento_m": comprimento,
        "hz": dados["hz"],
        "formato": dados["formato"],
        "voltas": [],
        "curvas": [],
        "avisos": [],
    }
    if dados["hz"] and dados["hz"] < 40:
        resultado["avisos"].append(
            f"Telemetria a {dados['hz']} Hz: pontos de frenagem com precisão de ~{200 / 3.6 / dados['hz']:.0f} m. "
            "Para mais detalhe, coloque a Taxa de envio UDP em 60 Hz."
        )
    if not completas:
        resultado["avisos"].append("Nenhuma volta completa nesta sessão (é preciso cruzar a linha de chegada duas vezes).")
        resultado["voltas"] = [{"numero": v.numero, "tempo_ms": v.tempo_ms, "completa": False} for v in voltas.values()]
        return resultado
    ref = min(validas or completas, key=lambda v: v.tempo_ms)
    if not validas:
        resultado["avisos"].append("Nenhuma volta válida: a referência é a volta completa mais rápida, mesmo inválida.")
    grade = [i * PASSO_M for i in range(int(comprimento // PASSO_M) + 1)]
    cols = {v.numero: _reamostrar(v, grade, comprimento) for v in completas}
    cref = cols[ref.numero]
    curvas = _curvas(cref, grade)
    deltas = {n: [a - b for a, b in zip(c["t"], cref["t"])] for n, c in cols.items()}
    met_ref = {c["nome"]: _metricas_curva(cref, c, deltas[ref.numero]) for c in curvas}

    # voltas
    melhores_setores = [min((v.setores_ms[i] for v in validas or completas if v.setores_ms[i]), default=0) for i in range(3)]
    for v in sorted(voltas.values(), key=lambda v: v.numero):
        comp = v in completas
        item = {
            "numero": v.numero,
            "tempo_ms": v.tempo_ms,
            "setores_ms": list(v.setores_ms),
            "completa": comp,
            "valida": comp and v in validas,
            "referencia": v is ref,
            "delta_s": round((v.tempo_ms - ref.tempo_ms) / 1000, 3) if comp else None,
            "composto": v.composto,
            "idade_pneu": v.idade_pneu,
            "desgaste_fim": v.desgaste_fim,
            "combustivel_fim": v.combustivel_fim,
            "temp_pneus_media": [round(statistics.fmean(t[i] for t in v.temp_sup), 1) for i in range(4)] if v.temp_sup else None,
        }
        if comp:
            item["curvas"] = {}
            for c in curvas:
                m = _metricas_curva(cols[v.numero], c, deltas[v.numero])
                item["curvas"][c["nome"]] = {k: (round(x, 3) if isinstance(x, float) else x) for k, x in m.items()}
        resultado["voltas"].append(item)

    # curvas: médias das voltas válidas (menos a referência) contra a referência
    outras = [v for v in (validas or completas) if v is not ref]
    for c in curvas:
        r = met_ref[c["nome"]]
        perdas, fdif, vdif, rdif, freia_extra = [], [], [], [], []
        for v in outras:
            m = _metricas_curva(cols[v.numero], c, deltas[v.numero])
            perdas.append(m["perda_s"])
            if m["freio_m_antes_apex"] is not None and r["freio_m_antes_apex"] is not None:
                fdif.append(m["freio_m_antes_apex"] - r["freio_m_antes_apex"])
            elif m["freio_m_antes_apex"] is not None and r["freio_m_antes_apex"] is None:
                freia_extra.append(m["freio_m_antes_apex"])
            vdif.append(m["vmin"] - r["vmin"])
            if m["retomada_m_apos_apex"] is not None and r["retomada_m_apos_apex"] is not None:
                rdif.append(m["retomada_m_apos_apex"] - r["retomada_m_apos_apex"])
        med = {
            "perda_media_s": round(statistics.fmean(perdas), 3) if perdas else 0.0,
            "freio_dif_m": round(statistics.fmean(fdif), 1) if fdif else None,
            "vmin_dif": round(statistics.fmean(vdif), 1) if vdif else None,
            "retomada_dif_m": round(statistics.fmean(rdif), 1) if rdif else None,
            "freia_sem_ref_m": round(statistics.fmean(freia_extra), 0)
            if freia_extra and len(freia_extra) * 2 >= len(outras) else None,
        }
        resultado["curvas"].append({
            "nome": c["nome"],
            "dist_ini": grade[c["ini"]], "dist_apex": grade[c["apex"]], "dist_fim": grade[c["fim"]],
            "ref": r,
            **med,
            "conselho": _conselho(c["nome"], med) if outras else None,
        })
    ordem = sorted((c for c in resultado["curvas"] if c["perda_media_s"] > 0.02), key=lambda c: -c["perda_media_s"])
    resultado["top_curvas"] = [c["nome"] for c in ordem[:3]]
    tempos_validos = [v.tempo_ms for v in validas]
    resultado["resumo"] = {
        "melhor_volta_ms": ref.tempo_ms,
        "melhor_volta_numero": ref.numero,
        "volta_ideal_ms": sum(melhores_setores) if all(melhores_setores) else None,
        "voltas_completas": len(completas),
        "voltas_validas": len(validas),
        "media_validas_ms": round(statistics.fmean(tempos_validos)) if tempos_validos else None,
        "consistencia_ms": round(statistics.pstdev(tempos_validos)) if len(tempos_validos) >= 2 else None,
        "perda_top3_s": round(sum(c["perda_media_s"] for c in ordem[:3]), 3),
    }
    # séries para os gráficos (grade de 10 m para o HTML ficar leve)
    passo = max(1, int(10 / PASSO_M))
    resultado["series"] = {
        "dist": grade[::passo],
        "referencia": ref.numero,
        "voltas": {
            str(n): {
                "vel": [round(x) for x in c["vel"][::passo]],
                "acel": [round(x, 2) for x in c["acel"][::passo]],
                "freio": [round(x, 2) for x in c["freio"][::passo]],
                "marcha": c["marcha"][::passo],
                "delta": [round(x, 3) for x in deltas[n][::passo]],
            }
            for n, c in cols.items()
        },
        "mapa": {"x": [round(x, 1) for x in cref["x"][::passo]], "z": [round(z, 1) for z in cref["z"][::passo]]},
    }
    return resultado
