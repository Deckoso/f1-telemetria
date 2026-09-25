# f1tele: gravador e análise de telemetria do F1 25

Grava a telemetria UDP do **F1 25** com o jogo no **Xbox, PlayStation ou PC** (vários pilotos ao mesmo tempo), sessão por sessão, sem perder pacote, e mostra **onde você perde tempo**: cada volta comparada com a sua melhor, curva a curva (frenagem, ápice, retomada), com gráficos, mapa da pista e pneus. Formatos UDP 2025 e 2026 (Season Pack).

- Guia para o piloto: [`GUIA-DO-PILOTO.md`](GUIA-DO-PILOTO.md)

## Download (Windows)
Na página de **[Releases](../../releases/latest)**, baixe `F1Telemetria-windows.zip`: executável, atalhos (`Gravar com F1 Laps.bat`, `Testar sem o jogo.bat`) e o [guia do piloto](GUIA-DO-PILOTO.md). Não precisa instalar Python.

O executável não tem assinatura digital: na primeira vez o Windows mostra "O Windows protegeu o computador" (**Mais informações → Executar assim mesmo**). Se preferir, confira o SHA-256 publicado no release ou gere o `.exe` você mesmo pelo workflow deste repositório.

## Princípios
1. **Grava bruto, decodifica depois.** O `.f1rec` guarda os bytes exatos do jogo, com horário de chegada. Se a spec mudar (UDP 2026 / Season Pack), a gravação continua valendo.
2. **Detecta, não configura.** Versão do jogo pelo cabeçalho. Plataforma por `Participants.m_platform` do carro do jogador, com a origem do pacote como reserva (este computador = PC; outro IP = console).
3. **Não rouba o F1 Laps**: `--repassar host:porta` reenvia cópia idêntica.
4. **Memória limitada**: fila com teto (20 000) entre o receptor e o disco; descarte é contado, nunca acumula.
5. **Rede mínima**: só recebe UDP na porta do jogo; o painel ouve **apenas 127.0.0.1** (com checagem de Host); nada vai para a internet.

## Uso
```bash
python -m f1tele gravar [--porta 20777] [--pasta DIR] [--repassar 127.0.0.1:20778] [--sem-navegador]
python -m f1tele reproduzir ARQ.f1rec [--velocidade 1|2|10|0] [--desde MIN] [--loop] [--porta 20777]
python -m f1tele inventario ARQ.f1rec          # contagem por tipo, Hz, perdas, formato, plataforma
python -m f1tele analisar ARQ.f1rec            # análise pós-sessão (HTML autocontido em analises/)
python -m f1tele sintetico --minutos 1         # pacotes falsos (formato 2025) para testar o encanamento
```
Sem argumentos (duplo clique no `.exe`) = `gravar`.

## Formato `.f1rec`
Stream gzip: `F1REC\0` · u16 versão · u32 tamanho · JSON de metadados · registros `u32 tamanho | u64 t_recv_ns | u8 origem | bytes`. Flush de sincronização a cada 1 s ou 2 MB: arquivo cortado é legível até o último flush. Catálogo em `sessoes.sqlite` na mesma pasta.

Nome: `AAAA-MM-DD_HHMM_<pista>_<sessao>.f1rec`. Durante a gravação, `...<uid>.f1rec.parcial`; se o programa cair, vira `_interrompida.f1rec` na próxima execução. Se a mesma sessão do jogo voltar depois de uma pausa (ou a tela de resultado chegar depois), ela continua no mesmo arquivo. Sessões só de menu, sem volta nem pista, vão para `menus/`.

## Estrutura
| Arquivo | Papel |
|---|---|
| `f1tele/spec.py` | cabeçalho, ids, tamanhos 2025, pistas, sessões, plataformas |
| `f1tele/cabecalho.py` | leitura do cabeçalho + Session (pista/tipo) + Participants (plataforma) |
| `f1tele/receptor.py` | socket UDP → repasse → fila com teto |
| `f1tele/gravador.py` | sessões por `m_sessionUID`, detecção, arquivo, catálogo, disco |
| `f1tele/formato.py` | escrita/leitura `.f1rec` |
| `f1tele/reprodutor.py` | reproduzir + inventário |
| `f1tele/sintetico.py` | gerador de pacotes (só encanamento) |
| `f1tele/decodificador.py` | campos por formato (2025 spec / 2026 validado) |
| `f1tele/analise.py` | voltas por distância, curvas, perdas, conselhos |
| `f1tele/relatorio.py` | HTML autocontido (SVG próprio) |
| `f1tele/painel.py` | painel `127.0.0.1:8750` + `/analise` |

## Desenvolvimento
```bash
python3.12 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest -q              # suíte (CP-0, CP-2 e demais)
.venv/bin/python tests/cp1_uma_hora.py     # CP-1: 1 h a 60 Hz acelerada + kill -9 (macOS/Linux)
```
O `.exe` do Windows sai do GitHub Actions (`.github/workflows/build.yml`, PyInstaller). Uma tag `v*` publica o release com o zip e o SHA-256.

## Spec
`docs/spec/README.md`. O PDF oficial da EA não é versionado; o link está lá.
