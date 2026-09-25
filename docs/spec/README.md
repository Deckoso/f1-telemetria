# Especificação UDP usada

- **Fonte:** "Data Output from F1® 25 Game" v3 (EA), baixado em 2026-09-25 de
  `https://forums.ea.com/t5/s/tghpe58374/attachments/tghpe58374/f1-games-game-info-hub-en/61/4/Data%20Output%20from%20F1%2025%20v3.pdf`
  (não versionado aqui: baixar para `docs/spec/`).
- **Cabeçalho:** 29 bytes, `<HBBBBBQfIIBB`, `m_packetFormat = 2025`, `m_gameYear = 25`.
- **Tamanhos (formato 2025):** Motion 1349 · Session 753 · LapData 1285 · Event 45 · Participants 1284 · CarSetups 1133 · CarTelemetry 1352 · CarStatus 1239 · FinalClassification 1042 · LobbyInfo 954 · CarDamage 1041 · SessionHistory 1460 · TyreSets 231 · MotionEx 273 · TimeTrial 101 · LapPositions 1131.
- **Frequências:** Motion, LapData, CarTelemetry, CarStatus e MotionEx na taxa do menu; Session e CarSetups 2/s; Participants a cada 5 s; CarDamage 10/s; SessionHistory e TyreSets 20/s (alternando carros); TimeTrial e LapPositions 1/s.
- **`m_platform`** (Participants e LobbyInfo): 1 Steam · 3 PlayStation · 4 Xbox · 6 Origin/EA · 255 desconhecido (carros da IA vêm sempre com 255).

## Diferenças entre formatos (o que muda para este gravador)
| Formato UDP | Onde aparece | Situação |
|---|---|---|
| 2025 | F1 25 (opção "UDP Format") | Spec v3 acima: tamanhos validados |
| 2024 / 2023 | F1 25 pode emitir os formatos antigos | Participants com registro de 60 / 58 bytes (nome de 48 chars): offset de `m_platform` tratado. **Tamanhos de 2023/2024 vêm dos jogos anteriores e não foram reconferidos na spec deles** |
| 2026 | F1 25 com o **2026 Season Pack** ("UDP Format" = 2026 é o padrão para quem começou já com o pack) | **Confirmado com gravação real (F1 25 v1.26, PC Steam, 2026-09-25):** arrays de **24 carros** (antes 22); Participants = 1470 bytes (24 × 60), `m_platform` no byte **46** do registro (3 bytes novos antes dele); **pacote novo id 16** (269 bytes, 1 por quadro, conteúdo ainda não documentado); tamanhos em `spec.TAMANHOS_2026`. Session mantém pista/tipo nos mesmos offsets |

Regra: nada do gravador depende do corpo além de Session (pista/tipo, offsets 35–37) e Participants (plataforma). O restante é decodificado na Onda 2, a partir da spec do formato que a gravação real mostrar.


## Decodificação usada na análise (v0.3)
Campos por carro (offset dentro do registro). 2025 = spec v3; 2026 = deduzido de gravação real e validado fisicamente.
| Pacote | 2025 | 2026 | Campos usados |
|---|---|---|---|
| LapData | 57 B × 22 | 57 B × 24 | último/atual tempo (0/4), setores (8–13), `lapDistance` (20), posição (32), volta (33), pit (34), setor (36), inválida (37), status (44) |
| CarTelemetry | 60 B | 59 B (`engineTemperature` virou uint8) | velocidade (0), acelerador (2), volante (6), freio (10), marcha (15), rpm (16), DRS (18), freios (22), pneu superfície (30), interno (34), pressões (40 no 2025 / **39** no 2026) |
| Motion | 60 B | 54 B | posição xyz (0), velocidade xyz (12). Forças G/ângulos do 2026: **não decodificados** (compactados) |
| CarStatus | 55 B | 59 B (float novo antes de `networkPaused`) | TC, ABS, mistura, balanço (0–3), combustível (5), composto real/visual (25/26), idade do pneu (27) |
| CarDamage | 46 B | 46 B | desgaste dos pneus (0) |
| SessionHistory | 1460 B | 1460 B | carro (29), voltas (30), 100 × 14 B a partir de 36: tempo, setores, flags de validade |

Validação 2026 (Melbourne, 14 716 quadros): d(lapDistance)/dt − velocidade = −0,16 m/s; \|v\| do Motion = velocidade do painel; tempos do SessionHistory = `lastLapTime` do LapData; setores somam o tempo da volta.
Ordem das rodas nos arrays: RL, RR, FL, FR (traseira esq., traseira dir., dianteira esq., dianteira dir.).
