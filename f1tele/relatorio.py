"""Relatório HTML autocontido da análise (sem internet, sem bibliotecas externas)."""

import html
import json

from . import __version__

# vai no <head>: relatório gerado por versão antiga é refeito
VERSAO_RELATORIO = f"<!-- f1tele-relatorio {__version__} -->"

MODELO = r"""<!doctype html>
<html lang="pt-BR">
<head>
__VERSAO__
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Análise · __TITULO__</title>
<style>
:root { --fundo:#f4f4f5; --cartao:#fff; --texto:#18181b; --suave:#71717a; --linha:#e4e4e7;
        --ref:#a1a1aa; --volta:#2563eb; --ganho:#16a34a; --perda:#dc2626; --freio:#dc2626; --acel:#16a34a; --roxo:#7c3aed; }
@media (prefers-color-scheme: dark) {
  :root { --fundo:#101012; --cartao:#1a1a1d; --texto:#f4f4f5; --suave:#a1a1aa; --linha:#2a2a2e;
          --ref:#71717a; --volta:#60a5fa; --ganho:#4ade80; --perda:#f87171; --freio:#f87171; --acel:#4ade80; --roxo:#a78bfa; }
}
* { box-sizing:border-box; }
body { margin:0; font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; background:var(--fundo); color:var(--texto); }
main { max-width:1100px; margin:0 auto; padding:20px 16px 48px; }
h1 { font-size:24px; margin:0; } h2 { font-size:17px; margin:0 0 10px; }
.sub { color:var(--suave); margin-top:4px; }
.cartao { background:var(--cartao); border:1px solid var(--linha); border-radius:12px; padding:16px 18px; margin-top:14px; }
.grade { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; }
.num b { display:block; font-size:22px; font-variant-numeric:tabular-nums; } .num span { color:var(--suave); font-size:13px; }
.aviso { border-left:4px solid #ca8a04; padding:8px 12px; margin-top:10px; background:var(--cartao); border-radius:6px; }
.top { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:10px; }
.top .cartao { margin:0; } .top b.perda { color:var(--perda); font-size:20px; }
table { width:100%; border-collapse:collapse; font-size:14px; font-variant-numeric:tabular-nums; }
td, th { text-align:left; padding:6px 6px; border-bottom:1px solid var(--linha); white-space:nowrap; }
th { color:var(--suave); font-weight:500; }
tr.clicavel { cursor:pointer; } tr.sel td { background:color-mix(in srgb, var(--volta) 12%, transparent); }
.melhor { color:var(--roxo); font-weight:700; } .inval { color:var(--suave); text-decoration:line-through; }
.rolagem { overflow-x:auto; }
svg { width:100%; height:auto; display:block; }
.eixo { stroke:var(--linha); } .rot { fill:var(--suave); font-size:11px; }
.leg { display:flex; gap:16px; flex-wrap:wrap; color:var(--suave); font-size:13px; margin:6px 0; }
.leg i { display:inline-block; width:14px; height:3px; vertical-align:middle; margin-right:6px; }
select { font:inherit; padding:6px 8px; border-radius:8px; border:1px solid var(--linha); background:var(--cartao); color:var(--texto); }
#dica { position:fixed; pointer-events:none; background:var(--cartao); border:1px solid var(--linha); border-radius:8px; padding:6px 8px; font-size:12px; display:none; z-index:9; }
.mapa { display:grid; grid-template-columns:minmax(0,1fr) 260px; gap:14px; align-items:start; }
@media (max-width:720px) { .mapa { grid-template-columns:1fr; } }
</style>
</head>
<body>
<main id="app"></main>
<div id="dica"></div>
<script id="dados" type="application/json">__DADOS__</script>
<script>
"use strict";
const D = JSON.parse(document.getElementById("dados").textContent);
const app = document.getElementById("app");
const esc = (t) => String(t ?? "–").replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const tempo = (ms) => { if (!ms) return "–"; const m = Math.floor(ms/60000), s = ((ms%60000)/1000).toFixed(3).padStart(6,"0"); return m ? `${m}:${s}` : s; };
const setor = (ms) => ms ? (ms/1000).toFixed(3) : "–";
const sinal = (x, d=3) => x === null || x === undefined ? "–" : (x > 0 ? "+" : "") + x.toFixed(d);
const R = D.resumo || {};
const S = D.series;

let h = `<h1>${esc(D.pista)} · ${esc(D.sessao)}</h1>
<div class="sub">${esc(D.plataforma ? (["Steam","EA"].includes(D.plataforma) ? "PC (" + D.plataforma + ")" : D.plataforma) : "plataforma ?")}
 · ${esc((D.inicio || "").replace("T"," ").slice(0,16))} · ${esc(D.jogo)}${D.clima ? " · " + esc(D.clima) : ""}
 ${D.temp_pista !== null && D.temp_pista !== undefined ? ` · pista ${D.temp_pista} °C, ar ${D.temp_ar} °C` : ""}
 · ${D.hz ? D.hz + " Hz" : ""}</div>`;
for (const a of D.avisos || []) h += `<div class="aviso">${esc(a)}</div>`;

if (R.melhor_volta_ms) {
  const ideal = R.volta_ideal_ms ? `${tempo(R.volta_ideal_ms)} <small style="color:var(--suave)">(${sinal((R.volta_ideal_ms - R.melhor_volta_ms)/1000)})</small>` : "–";
  h += `<section class="cartao grade">
    <div class="num"><b>${tempo(R.melhor_volta_ms)}</b><span>melhor volta (volta ${R.melhor_volta_numero})</span></div>
    <div class="num"><b>${ideal}</b><span>volta ideal (melhores setores)</span></div>
    <div class="num"><b>${tempo(R.media_validas_ms)}</b><span>média das válidas</span></div>
    <div class="num"><b>${R.consistencia_ms !== null ? "± " + (R.consistencia_ms/1000).toFixed(3) + " s" : "–"}</b><span>consistência</span></div>
    <div class="num"><b>${R.voltas_validas} / ${R.voltas_completas}</b><span>voltas válidas / completas</span></div>
  </section>`;
  const top = (D.top_curvas || []).map((n) => D.curvas.find((c) => c.nome === n));
  h += `<section class="cartao"><h2>Onde você perde tempo</h2>`;
  if (!top.length) h += `<div class="sub">Sem perda relevante por curva: as voltas estão no nível da melhor, ou há só uma volta válida.</div>`;
  else {
    h += `<div class="sub" style="margin-bottom:10px">Média das voltas contra a sua melhor volta. Somando as 3: <b>${R.perda_top3_s.toFixed(3)} s por volta</b>.</div><div class="top">`;
    for (const c of top) h += `<div class="cartao"><div style="display:flex;justify-content:space-between;align-items:baseline">
      <b style="font-size:18px">${esc(c.nome)}</b><b class="perda">−${c.perda_media_s.toFixed(3)} s</b></div>
      <div class="sub">a ${Math.round(c.dist_apex)} m da largada · ápice ${c.ref.vmin} km/h na melhor volta</div>
      <p style="margin:8px 0 0">${esc(c.conselho)}</p></div>`;
    h += `</div>`;
  }
  h += `</section>`;
}

// voltas
const melhores = [0,1,2].map((i) => Math.min(...D.voltas.filter((v) => v.valida && v.setores_ms[i]).map((v) => v.setores_ms[i]), Infinity));
h += `<section class="cartao"><h2>Voltas</h2><div class="sub" style="margin-bottom:6px">Clique numa volta completa para vê-la nos gráficos. Roxo = melhor setor entre as voltas válidas.</div><div class="rolagem"><table>
<tr><th>Volta</th><th>Tempo</th><th>S1</th><th>S2</th><th>S3</th><th>Δ melhor</th><th>Pneu</th><th>Temp. média (DE DD TE TD)</th><th>Desgaste no fim (DE DD TE TD)</th></tr>`;
for (const v of D.voltas) {
  const cl = v.completa ? "clicavel" : "";
  const tcl = v.referencia ? "melhor" : (v.completa && !v.valida ? "inval" : "");
  const sets = (v.setores_ms || [0,0,0]).map((ms, i) => `<td class="${v.valida && ms && ms === melhores[i] ? "melhor" : ""}">${setor(ms)}</td>`).join("");
  const tp = v.temp_pneus_media ? [2,3,0,1].map((i) => Math.round(v.temp_pneus_media[i])).join(" · ") + " °C" : "–";
  const dg = v.desgaste_fim ? [2,3,0,1].map((i) => v.desgaste_fim[i].toFixed(0)).join(" · ") + " %" : "–";
  h += `<tr class="${cl}" data-volta="${v.numero}"><td>${v.numero}${v.referencia ? " ★" : ""}${v.completa ? (v.valida ? "" : " (inválida)") : " (incompleta)"}</td>
    <td class="${tcl}">${tempo(v.tempo_ms)}</td>${sets}<td>${v.delta_s !== null ? sinal(v.delta_s) : "–"}</td>
    <td>${esc(v.composto)}${v.idade_pneu !== null && v.idade_pneu !== undefined ? " · " + v.idade_pneu + " v." : ""}</td><td>${tp}</td><td>${dg}</td></tr>`;
}
h += `</table></div></section>`;

if (S) {
  const opcoes = Object.keys(S.voltas).map((n) => `<option value="${n}">Volta ${n}${+n === S.referencia ? " (melhor)" : ""}</option>`).join("");
  h += `<section class="cartao"><div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap"><h2 style="margin:0">Volta a volta</h2>
    <label>Comparar <select id="sel">${opcoes}</select> com a melhor volta (${S.referencia})</label></div>
    <div class="leg"><span><i style="background:var(--volta)"></i>volta escolhida</span><span><i style="background:var(--ref)"></i>melhor volta</span>
    <span><i style="background:var(--acel)"></i>acelerador</span><span><i style="background:var(--freio)"></i>freio</span></div>
    <svg id="g-vel" viewBox="0 0 1000 230"></svg>
    <svg id="g-delta" viewBox="0 0 1000 130"></svg>
    <svg id="g-pedal" viewBox="0 0 1000 120"></svg>
    <div class="sub">Eixo horizontal: distância na volta (m). Delta acima de zero = mais lento que a melhor volta naquele ponto. Tracejado = ápice das curvas.</div></section>
    <section class="cartao mapa"><div><h2>Mapa: onde a volta escolhida ganha e perde</h2><svg id="mapa" viewBox="0 0 600 420"></svg>
    <div class="leg"><span><i style="background:var(--ganho)"></i>ganhando da melhor</span><span><i style="background:var(--perda)"></i>perdendo</span></div></div>
    <div id="lado"></div></section>`;
}

// curvas
if (D.curvas.length) {
  h += `<section class="cartao"><h2>Todas as curvas</h2><div class="sub" style="margin-bottom:6px">Curvas detectadas pela queda de velocidade na sua melhor volta (C1, C2… na ordem da pista, não é a numeração oficial).</div><div class="rolagem"><table>
  <tr><th>Curva</th><th>Ápice (m)</th><th>Ápice na melhor</th><th>Frenagem na melhor</th><th>Perda média</th><th>O que muda</th></tr>`;
  for (const c of D.curvas) h += `<tr><td>${esc(c.nome)}</td><td>${Math.round(c.dist_apex)}</td><td>${c.ref.vmin} km/h · ${c.ref.marcha_min}ª</td>
    <td>${c.ref.freio_m_antes_apex !== null ? c.ref.freio_m_antes_apex + " m antes" : "sem frear"}</td>
    <td style="color:${c.perda_media_s > 0.02 ? "var(--perda)" : "inherit"}">${sinal(c.perda_media_s)} s</td><td style="white-space:normal">${esc(c.conselho)}</td></tr>`;
  h += `</table></div></section>`;
}
h += `<div class="sub" style="margin-top:16px">Gerado pelo gravador de telemetria F1 25 · ${esc(D.arquivo.split(/[\\/]/).pop())}</div>`;
app.innerHTML = h;

document.querySelectorAll("tr.clicavel").forEach((tr) => tr.onclick = () => { const s = document.getElementById("sel"); if (s) { s.value = tr.dataset.volta; desenhar(); s.scrollIntoView({behavior:"smooth", block:"center"}); } });

const cor = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
function linha(xs, ys, x0, x1, y0, y1, W, H, pad) {
  let d = "";
  for (let i = 0; i < xs.length; i++) {
    const x = pad + (xs[i] - x0) / (x1 - x0) * (W - pad - 8), y = H - 18 - (ys[i] - y0) / ((y1 - y0) || 1) * (H - 30);
    d += (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1);
  }
  return d;
}
function eixoX(W, H, pad, x1) {
  let s = "";
  for (let m = 0; m <= x1; m += 500) { const x = pad + m / x1 * (W - pad - 8); s += `<line class="eixo" x1="${x}" x2="${x}" y1="6" y2="${H-18}"/><text class="rot" x="${x}" y="${H-4}" text-anchor="middle">${m}</text>`; }
  for (const c of D.curvas) { const x = pad + c.dist_apex / x1 * (W - pad - 8); s += `<line x1="${x}" x2="${x}" y1="6" y2="${H-18}" stroke="${cor("--suave")}" stroke-dasharray="3 4" opacity=".5"/><text class="rot" x="${x+2}" y="14">${c.nome}</text>`; }
  return s;
}
function desenhar() {
  if (!S) return;
  const sel = document.getElementById("sel").value, ref = String(S.referencia);
  const V = S.voltas[sel], F = S.voltas[ref], xs = S.dist, x1 = xs[xs.length - 1], pad = 40;
  document.querySelectorAll("tr[data-volta]").forEach((tr) => tr.classList.toggle("sel", tr.dataset.volta === sel));
  // velocidade
  const vmax = Math.max(...V.vel, ...F.vel) + 10;
  let s = eixoX(1000, 230, pad, x1);
  for (let k = 0; k <= vmax; k += 50) { const y = 230 - 18 - k / vmax * 200; s += `<text class="rot" x="4" y="${y+4}">${k}</text>`; }
  s += `<path d="${linha(xs, F.vel, 0, x1, 0, vmax, 1000, 230, pad)}" fill="none" stroke="${cor("--ref")}" stroke-width="2"/>`;
  s += `<path d="${linha(xs, V.vel, 0, x1, 0, vmax, 1000, 230, pad)}" fill="none" stroke="${cor("--volta")}" stroke-width="2"/>`;
  s += `<text class="rot" x="${pad}" y="26">km/h</text><line id="cursor-vel" y1="6" y2="212" stroke="${cor("--texto")}" opacity="0"/>`;
  document.getElementById("g-vel").innerHTML = s;
  // delta
  const dmax = Math.max(0.2, ...V.delta.map(Math.abs));
  s = eixoX(1000, 130, pad, x1);
  const y0 = 130 - 18 - (0 + dmax) / (2 * dmax) * 100;
  s += `<line x1="${pad}" x2="992" y1="${y0}" y2="${y0}" stroke="${cor("--suave")}"/>`;
  s += `<path d="${linha(xs, V.delta, 0, x1, -dmax, dmax, 1000, 130, pad)}" fill="none" stroke="${cor("--volta")}" stroke-width="2"/>`;
  s += `<text class="rot" x="4" y="22">+${dmax.toFixed(2)}s</text><text class="rot" x="4" y="112">−${dmax.toFixed(2)}s</text><text class="rot" x="${pad}" y="26">delta</text>`;
  document.getElementById("g-delta").innerHTML = s;
  // pedais
  s = eixoX(1000, 120, pad, x1);
  s += `<path d="${linha(xs, V.acel, 0, x1, 0, 1, 1000, 120, pad)}" fill="none" stroke="${cor("--acel")}" stroke-width="1.6"/>`;
  s += `<path d="${linha(xs, V.freio, 0, x1, 0, 1, 1000, 120, pad)}" fill="none" stroke="${cor("--freio")}" stroke-width="1.6"/>`;
  s += `<text class="rot" x="${pad}" y="26">pedais</text>`;
  document.getElementById("g-pedal").innerHTML = s;
  // mapa colorido pelo ganho/perda por trecho
  const X = S.mapa.x, Z = S.mapa.z;
  const minX = Math.min(...X), maxX = Math.max(...X), minZ = Math.min(...Z), maxZ = Math.max(...Z);
  const esc2 = Math.min(560 / ((maxX - minX) || 1), 380 / ((maxZ - minZ) || 1));
  const px = (i) => 20 + (X[i] - minX) * esc2, pz = (i) => 20 + (Z[i] - minZ) * esc2;
  s = "";
  const J = 3;  // ±30 m: tira o ruído de 20 Hz e mostra o trecho, não o ponto
  for (let i = 1; i < X.length; i++) {
    const a = Math.max(0, i - 1 - J), b = Math.min(X.length - 1, i + J);
    const g = (V.delta[b] - V.delta[a]) / (b - a);
    const c = Math.abs(g) < 0.0025 ? cor("--ref") : (g > 0 ? cor("--perda") : cor("--ganho"));
    s += `<line x1="${px(i-1).toFixed(1)}" y1="${pz(i-1).toFixed(1)}" x2="${px(i).toFixed(1)}" y2="${pz(i).toFixed(1)}" stroke="${c}" stroke-width="5" stroke-linecap="round"/>`;
  }
  s += `<circle cx="${px(0)}" cy="${pz(0)}" r="6" fill="${cor("--texto")}"/>`;
  for (const c of D.curvas) { const i = Math.min(X.length - 1, Math.round(c.dist_apex / (xs[1] - xs[0]))); s += `<text x="${px(i)+7}" y="${pz(i)-7}" font-size="13" font-weight="700" fill="${cor("--texto")}">${c.nome}</text>`; }
  document.getElementById("mapa").innerHTML = s;
  const vs = D.voltas.find((v) => String(v.numero) === sel), cs = vs && vs.curvas ? vs.curvas : {};
  let lado = `<h2>Volta ${sel}${+sel === S.referencia ? " (melhor)" : ""}: ${tempo(vs.tempo_ms)}</h2><table><tr><th>Curva</th><th>Δ</th><th>Ápice</th></tr>`;
  for (const c of D.curvas) { const m = cs[c.nome]; if (!m) continue;
    lado += `<tr><td>${c.nome}</td><td style="color:${m.perda_s > 0.02 ? "var(--perda)" : m.perda_s < -0.02 ? "var(--ganho)" : "inherit"}">${sinal(m.perda_s)}</td><td>${m.vmin} km/h</td></tr>`; }
  document.getElementById("lado").innerHTML = lado + "</table>";
}
if (S) {
  const sel = document.getElementById("sel");
  const pior = D.voltas.filter((v) => v.completa && !v.referencia).sort((a, b) => b.tempo_ms - a.tempo_ms)[0];
  sel.value = String(pior ? pior.numero : S.referencia);
  sel.onchange = desenhar;
  desenhar();
  const dica = document.getElementById("dica");
  ["g-vel","g-delta","g-pedal"].forEach((id) => {
    const g = document.getElementById(id);
    g.onmousemove = (e) => {
      const r = g.getBoundingClientRect(), fx = (e.clientX - r.left) / r.width * 1000;
      const x1 = S.dist[S.dist.length - 1], d = (fx - 40) / (1000 - 48) * x1;
      if (d < 0 || d > x1) { dica.style.display = "none"; return; }
      const i = Math.round(d / (S.dist[1] - S.dist[0])), V = S.voltas[document.getElementById("sel").value], F = S.voltas[String(S.referencia)];
      dica.innerHTML = `<b>${Math.round(S.dist[i])} m</b><br>escolhida ${V.vel[i]} km/h · ${V.marcha[i]}ª<br>melhor ${F.vel[i]} km/h · ${F.marcha[i]}ª<br>delta ${sinal(V.delta[i])} s`;
      dica.style.display = "block"; dica.style.left = (e.clientX + 14) + "px"; dica.style.top = (e.clientY + 14) + "px";
    };
    g.onmouseleave = () => dica.style.display = "none";
  });
}
</script>
</body>
</html>
"""


def gerar_html(resultado: dict) -> str:
    dados = json.dumps(resultado, ensure_ascii=False, separators=(",", ":"))
    # JSON dentro de <script>: impede fechar a tag com "</script>" vindo dos dados
    dados = dados.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    titulo = html.escape(f"{resultado.get('pista')} · {resultado.get('sessao')}")
    return MODELO.replace("__VERSAO__", VERSAO_RELATORIO).replace("__TITULO__", titulo).replace("__DADOS__", dados)


def gerar_arquivo(caminho: str, pasta_saida: str | None = None) -> str:
    """Analisa um .f1rec e grava o HTML em <pasta>/analises/. Reaproveita se a gravação não mudou.

    Gravação em andamento (.parcial) é sempre reanalisada: mostra até o último segundo salvo.
    """
    import os

    from .analise import analisar

    pasta_saida = pasta_saida or os.path.join(os.path.dirname(os.path.abspath(caminho)), "analises")
    os.makedirs(pasta_saida, exist_ok=True)
    nome = os.path.basename(caminho).replace(".f1rec.parcial", "").replace(".f1rec", "") + ".html"
    destino = os.path.join(pasta_saida, nome)
    parcial = caminho.endswith(".parcial")
    if not parcial and os.path.exists(destino) and os.path.getmtime(destino) >= os.path.getmtime(caminho):
        with open(destino, encoding="utf-8") as f:
            if VERSAO_RELATORIO in f.read(4096):
                return destino
    conteudo = gerar_html(analisar(caminho))
    temporario = destino + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        f.write(conteudo)
    os.replace(temporario, destino)
    return destino
