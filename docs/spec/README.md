# Especificação UDP usada

- **Fonte:** "Data Output from F1® 25 Game" v3 (EA), baixado em 2026-09-25 de
  `https://forums.ea.com/t5/s/tghpe58374/attachments/tghpe58374/f1-games-game-info-hub-en/61/4/Data%20Output%20from%20F1%2025%20v3.pdf`
  (não versionado aqui: baixar para `docs/spec/`).
- **Cabeçalho:** 29 bytes, `<HBBBBBQfIIBB`, `m_packetFormat = 2025`, `m_gameYear = 25`.
- **Tamanhos (formato 2025):** Motion 1349 · Session 753 · LapData 1285 · Event 45 · Participants 1284 · CarSetups 1133 · CarTelemetry 1352 · CarStatus 1239 · FinalClassification 1042 · LobbyInfo 954 · CarDamage 1041 · SessionHistory 1460 · TyreSets 231 · MotionEx 273 · TimeTrial 101 · LapPositions 1131.
- **Frequências:** Motion, LapData, CarTelemetry, CarStatus e MotionEx na taxa do menu; Session e CarSetups 2/s; Participants a cada 5 s; CarDamage 10/s; SessionHistory e TyreSets 20/s (alternando carros); TimeTrial e LapPositions 1/s.
- **`m_platform`** (Participants e LobbyInfo): 1 Steam · 3 PlayStation · 4 Xbox · 6 Origin/EA · 255 desconhecido.

## Diferenças entre formatos (o que muda para este gravador)
| Formato UDP | Onde aparece | Situação |
|---|---|---|
| 2025 | F1 25 (opção "UDP Format") | Spec v3 acima: tamanhos validados |
| 2024 / 2023 | F1 25 pode emitir os formatos antigos | Participants com registro de 60 / 58 bytes (nome de 48 chars): offset de `m_platform` tratado. **Tamanhos de 2023/2024 vêm dos jogos anteriores e não foram reconferidos na spec deles** |
| 2026 | F1 25 com o **2026 Season Pack** ("UDP Format" = 2026 é o padrão para quem começou já com o pack) | Spec separada da EA (fórum retornou 403 sem login em 2026-09-25). O gravador aceita e grava; se Participants mantiver o registro de 57 bytes, a plataforma sai normalmente. **Conferir em CP-5 com a gravação real** |

Regra: nada do gravador depende do corpo além de Session (pista/tipo, offsets 35–37) e Participants (plataforma). O restante é decodificado na Onda 2, a partir da spec do formato que a gravação real mostrar.
