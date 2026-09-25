"""Painel de status em http://127.0.0.1:8750 (só este computador enxerga)."""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGINA = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gravador F1 25</title>
<style>
:root { --fundo:#f4f4f5; --cartao:#fff; --texto:#18181b; --suave:#71717a; --linha:#e4e4e7;
        --ok:#15803d; --espera:#a16207; --erro:#b91c1c; }
@media (prefers-color-scheme: dark) {
  :root { --fundo:#101012; --cartao:#1a1a1d; --texto:#f4f4f5; --suave:#a1a1aa; --linha:#2a2a2e;
          --ok:#4ade80; --espera:#facc15; --erro:#f87171; }
}
* { box-sizing:border-box; }
body { margin:0; font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; background:var(--fundo); color:var(--texto); }
main { max-width:880px; margin:0 auto; padding:20px 16px 40px; }
h1 { font-size:15px; font-weight:600; color:var(--suave); margin:0 0 12px; }
.cartao { background:var(--cartao); border:1px solid var(--linha); border-radius:12px; padding:16px 18px; margin-bottom:14px; }
#estado { font-size:30px; font-weight:700; }
.gravando { color:var(--ok); } .aguardando { color:var(--espera); } .pausado_disco, .erro { color:var(--erro); }
#rotulo { font-size:17px; margin-top:4px; }
.grade { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin-top:12px; }
.num b { display:block; font-size:20px; } .num span { color:var(--suave); font-size:13px; }
table { width:100%; border-collapse:collapse; font-size:14px; }
td, th { text-align:left; padding:6px 4px; border-bottom:1px solid var(--linha); }
th { color:var(--suave); font-weight:500; }
.aviso { border-color:var(--espera); } .aviso b { color:var(--espera); }
ol { margin:6px 0 0; padding-left:20px; } li { margin:4px 0; }
code { font-size:16px; font-weight:700; }
button { font:inherit; padding:8px 14px; border-radius:8px; border:1px solid var(--linha); background:var(--cartao); color:var(--texto); cursor:pointer; }
.escondido { display:none; }
.rolagem { overflow-x:auto; }
</style>
</head>
<body>
<main>
  <h1>Gravador de telemetria · F1 25</h1>
  <section class="cartao">
    <div id="estado" class="aguardando">Aguardando o jogo…</div>
    <div id="rotulo">Nenhum sinal ainda.</div>
    <div class="grade">
      <div class="num"><b id="pista">–</b><span>pista</span></div>
      <div class="num"><b id="tipo">–</b><span>sessão</span></div>
      <div class="num"><b id="tempo">0:00</b><span>tempo gravado</span></div>
      <div class="num"><b id="tamanho">0 MB</b><span>arquivo</span></div>
      <div class="num"><b id="perdas">0</b><span>quadros com perda</span></div>
      <div class="num"><b id="descartes">0</b><span>descartados</span></div>
    </div>
  </section>

  <section id="config" class="cartao">
    <b>Para ligar no jogo</b> (Configurações → Telemetria):
    <ol>
      <li>Telemetria UDP: <b>Ligada</b> · Taxa de envio: <b>60 Hz</b> · Porta: <code id="porta">20777</code></li>
      <li>Xbox / PlayStation: IP de destino = <code id="ip">?</code> (este computador) — ou ligue o <b>modo Broadcast</b></li>
      <li>Jogo neste PC: IP de destino = <code>127.0.0.1</code></li>
    </ol>
    <div id="repasse" class="escondido" style="margin-top:8px"></div>
  </section>

  <section id="diagnostico" class="cartao aviso escondido">
    <b>Nenhum sinal há mais de 30 s.</b> Confira:
    <ol>
      <li>No jogo, a telemetria UDP está <b>Ligada</b>?</li>
      <li>O IP digitado no jogo é <code class="ip2">?</code> e a porta é a mesma daqui?</li>
      <li>O console e o PC estão na <b>mesma rede</b>? Wi-Fi de convidado costuma isolar os aparelhos.</li>
      <li>No Windows, o firewall liberou o programa em <b>Redes privadas</b>? (a rede do PC precisa estar como Privada)</li>
      <li>Outro programa de telemetria (ex.: F1 Laps) aberto na mesma porta? Veja o repasse no guia.</li>
    </ol>
  </section>

  <section id="alertas" class="cartao aviso escondido"></section>

  <section class="cartao">
    <b>Pacotes por segundo</b>
    <div class="rolagem"><table id="taxas"><tr><td>—</td></tr></table></div>
  </section>

  <section class="cartao">
    <b>Últimas sessões</b> <button id="abrir" style="float:right">Abrir pasta</button>
    <div class="rolagem"><table id="historico"><tr><td>—</td></tr></table></div>
  </section>
</main>
<script>
const $ = (id) => document.getElementById(id);
const esc = (t) => String(t ?? "–").replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const mb = (b) => (b / 1048576).toFixed(1) + " MB";
const relogio = (s) => { const h = Math.floor(s/3600), m = Math.floor(s%3600/60), x = String(s%60).padStart(2,"0");
  return h ? `${h}:${String(m).padStart(2,"0")}:${x}` : `${m}:${x}`; };
const NOMES = { gravando: "Gravando", aguardando: "Aguardando o jogo…", pausado_disco: "Parado: disco quase cheio" };

async function atualizar() {
  let e;
  try { e = await (await fetch("/estado", { cache: "no-store" })).json(); }
  catch { $("estado").textContent = "Programa fechado"; $("estado").className = "erro"; return; }
  const g = e.gravador, r = e.receptor, s = g.sessao;
  $("estado").textContent = g.erro ? "Erro ao gravar" : NOMES[g.estado] || g.estado;
  $("estado").className = g.erro ? "erro" : g.estado;
  $("rotulo").textContent = s ? s.rotulo : "Nenhum sinal ainda.";
  $("pista").textContent = s?.pista ?? "–"; $("tipo").textContent = s?.tipo ?? "–";
  $("tempo").textContent = relogio(g.tempo_gravado_s || 0);
  $("tamanho").textContent = mb(s?.bytes_disco || 0);
  $("perdas").textContent = s?.quadros_incompletos ?? 0;
  $("descartes").textContent = r.descartes_fila + g.descartados_disco;
  $("porta").textContent = r.porta;
  document.querySelectorAll("#ip, .ip2").forEach((n) => n.textContent = e.ip_rede || "(sem rede)");
  if (r.repasses.length) { $("repasse").classList.remove("escondido");
    $("repasse").textContent = `Repassando cada pacote para ${r.repasses.join(", ")} (${r.repassados} enviados, ${r.erros_repasse} erros).`; }
  const semSinal = r.segundos_sem_sinal === null ? e.segundos_aberto : r.segundos_sem_sinal;
  $("diagnostico").classList.toggle("escondido", !(semSinal > 30));
  const alertas = [];
  if (g.erro) alertas.push(`Erro: ${esc(g.erro)}`);
  if (e.perfil_rede === "Public") alertas.push("A rede deste PC está como <b>Pública</b> no Windows: o firewall pode bloquear o console. Mude para <b>Privada</b> (Configurações → Rede e Internet).");
  for (const [ip, n] of Object.entries(g.outras_fontes || {})) alertas.push(`Outro aparelho (${esc(ip)}) também está mandando telemetria: ${n} pacotes ignorados. Só a primeira fonte é gravada.`);
  if (s?.tamanhos_inesperados) alertas.push(`${s.tamanhos_inesperados} pacotes com tamanho diferente da spec 2025 (gravados normalmente; versão do jogo/UDP pode ter mudado).`);
  if (s && ![2023,2024,2025,2026].includes(s.formato_udp)) alertas.push(`Formato UDP ${s.formato_udp} desconhecido: gravando mesmo assim.`);
  if (g.invalidos) alertas.push(`${g.invalidos} pacotes que não são do F1 foram ignorados.`);
  $("alertas").innerHTML = alertas.map((a) => `<div>${a}</div>`).join("");
  $("alertas").classList.toggle("escondido", !alertas.length);
  const taxas = Object.entries(g.taxas || {});
  $("taxas").innerHTML = taxas.length ? "<tr><th>Pacote</th><th>por segundo</th></tr>" +
    taxas.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v}</td></tr>`).join("") : "<tr><td>—</td></tr>";
  const h = g.historico || [];
  $("historico").innerHTML = h.length ? "<tr><th>Início</th><th>Pista</th><th>Sessão</th><th>Plataforma</th><th>Tamanho</th></tr>" +
    h.map((x) => `<tr><td>${esc((x.inicio||"").replace("T"," ").slice(0,16))}</td><td>${esc(x.pista)}</td><td>${esc(x.tipo)}</td><td>${esc(x.plataforma)}</td><td>${mb(x.bytes_disco||0)}</td></tr>`).join("")
    : "<tr><td>Nenhuma sessão gravada ainda.</td></tr>";
}
$("abrir").onclick = () => fetch("/abrir-pasta", { method: "POST", headers: { "X-F1Tele": "1" } });
atualizar(); setInterval(atualizar, 1000);
</script>
</body>
</html>
"""


def abrir_pasta(caminho: str) -> None:
    if sys.platform == "win32":
        os.startfile(caminho)  # noqa: S606 - pasta local fixa, não vem do navegador
    elif sys.platform == "darwin":
        subprocess.Popen(["open", caminho])
    else:
        subprocess.Popen(["xdg-open", caminho])


class Painel:
    def __init__(self, obter_estado, pasta: str, porta: int = 8750):
        self.obter_estado = obter_estado
        self.pasta = pasta
        permitidos = set()
        painel = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def _host_ok(self) -> bool:
                # Bloqueia DNS rebinding: só aceita os nomes locais.
                return self.headers.get("Host", "") in permitidos

            def _responder(self, codigo: int, corpo: bytes, tipo: str) -> None:
                self.send_response(codigo)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(corpo)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'")
                self.end_headers()
                self.wfile.write(corpo)

            def do_GET(self):
                if not self._host_ok():
                    return self._responder(403, b"host", "text/plain")
                if self.path == "/":
                    return self._responder(200, PAGINA.encode("utf-8"), "text/html; charset=utf-8")
                if self.path == "/estado":
                    corpo = json.dumps(painel.obter_estado(), ensure_ascii=False, default=str).encode("utf-8")
                    return self._responder(200, corpo, "application/json; charset=utf-8")
                self._responder(404, b"nao encontrado", "text/plain")

            def do_POST(self):
                # Cabeçalho próprio: um site qualquer não consegue mandá-lo sem permissão (CORS).
                if not self._host_ok() or self.headers.get("X-F1Tele") != "1":
                    return self._responder(403, b"proibido", "text/plain")
                if self.path == "/abrir-pasta":
                    abrir_pasta(painel.pasta)
                    return self._responder(204, b"", "text/plain")
                self._responder(404, b"nao encontrado", "text/plain")

        self.servidor = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
        self.porta = self.servidor.server_address[1]
        permitidos.update({f"127.0.0.1:{self.porta}", f"localhost:{self.porta}"})
        self.url = f"http://127.0.0.1:{self.porta}/"
        self._thread = threading.Thread(target=self.servidor.serve_forever, name="painel", daemon=True)

    def iniciar(self) -> None:
        self._thread.start()

    def parar(self) -> None:
        self.servidor.shutdown()
        self.servidor.server_close()
