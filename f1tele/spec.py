"""Constantes da especificação UDP do F1 25.

Fonte: "Data Output from F1 25 v3" (EA, docs/spec/Data-Output-from-F1-25-v3.pdf).
O gravador só depende do cabeçalho; o resto daqui serve para rótulos
(pista, tipo de sessão, plataforma) e para validar pacotes sintéticos.
"""

import struct

# Cabeçalho comum a todos os pacotes (29 bytes, little-endian, empacotado).
HEADER = struct.Struct("<HBBBBBQfIIBB")
HEADER_SIZE = HEADER.size  # 29

# Formatos de UDP que o F1 25 pode emitir (menu "UDP Format").
# 2026 = F1 25 com o 2026 Season Pack (layout próprio, spec separada da EA).
FORMATOS_CONHECIDOS = {2023, 2024, 2025, 2026}

NOMES_PACOTE = {
    0: "Motion",
    1: "Session",
    2: "LapData",
    3: "Event",
    4: "Participants",
    5: "CarSetups",
    6: "CarTelemetry",
    7: "CarStatus",
    8: "FinalClassification",
    9: "LobbyInfo",
    10: "CarDamage",
    11: "SessionHistory",
    12: "TyreSets",
    13: "MotionEx",
    14: "TimeTrial",
    15: "LapPositions",
    16: "Novo2026",  # só no formato 2026; 269 bytes, 1 por quadro (spec 2026 não obtida)
}

# Tamanho de cada pacote no formato 2025 (spec v3).
TAMANHOS_2025 = {
    0: 1349,
    1: 753,
    2: 1285,
    3: 45,
    4: 1284,
    5: 1133,
    6: 1352,
    7: 1239,
    8: 1042,
    9: 954,
    10: 1041,
    11: 1460,
    12: 231,
    13: 273,
    14: 101,
    15: 1131,
}

# Tamanhos observados no formato 2026 (F1 25 v1.26 + 2026 Season Pack, gravação
# real de 2026-09-25). Arrays passaram de 22 para 24 carros.
TAMANHOS_2026 = {
    0: 1325,
    1: 926,
    2: 1399,
    3: 45,
    4: 1470,
    5: 1233,
    6: 1448,
    7: 1445,
    8: 1134,
    10: 1133,
    11: 1460,
    12: 231,
    13: 273,
    14: 104,
    15: 1231,
    16: 269,
}

TAMANHOS_POR_FORMATO = {2025: TAMANHOS_2025, 2026: TAMANHOS_2026}

# Pacotes enviados a cada quadro na taxa escolhida no menu. LapData, CarTelemetry
# e CarStatus saem sempre juntos com o mesmo frameIdentifier: se um quadro chega
# sem os três, houve perda no caminho.
PACOTES_POR_QUADRO = (2, 6, 7)

# Session: offsets a partir do início do pacote (cabeçalho incluído).
SESSION_TIPO = 29 + 6  # uint8 m_sessionType
SESSION_PISTA = 29 + 7  # int8 m_trackId
SESSION_FORMULA = 29 + 8  # uint8 m_formula

# Participants: 29 cabeçalho + 1 m_numActiveCars + N carros.
# Tamanho do pacote -> (carros no array, bytes por carro, offset de m_platform no registro).
PARTICIPANTS_BASE = 30
PARTICIPANTS_LAYOUTS = {
    1284: (22, 57, 43),  # 2025 (nome 32 chars + techLevel)
    1350: (22, 60, 59),  # 2024 (nome 48 chars + techLevel)
    1306: (22, 58, 57),  # 2023 (nome 48 chars, sem techLevel)
    1470: (24, 60, 46),  # 2026 Season Pack: 24 carros, 3 bytes novos antes de m_platform
    #                      (confirmado em gravação real do F1 25 v1.26, 2026-09-25)
}

PLATAFORMAS = {
    1: "Steam",
    3: "PlayStation",
    4: "Xbox",
    6: "EA",
    255: None,
}

PISTAS = {
    0: "Melbourne",
    2: "Shanghai",
    3: "Bahrein",
    4: "Catalunha",
    5: "Monaco",
    6: "Montreal",
    7: "Silverstone",
    9: "Hungaroring",
    10: "Spa",
    11: "Monza",
    12: "Singapura",
    13: "Suzuka",
    14: "Abu Dhabi",
    15: "Texas",
    16: "Interlagos",
    17: "Austria",
    19: "Mexico",
    20: "Baku",
    26: "Zandvoort",
    27: "Imola",
    29: "Jeddah",
    30: "Miami",
    31: "Las Vegas",
    32: "Losail",
    39: "Silverstone invertida",
    40: "Austria invertida",
    41: "Zandvoort invertida",
}

TIPOS_SESSAO = {
    0: "Desconhecida",
    1: "Treino 1",
    2: "Treino 2",
    3: "Treino 3",
    4: "Treino curto",
    5: "Q1",
    6: "Q2",
    7: "Q3",
    8: "Classificacao curta",
    9: "Classificacao volta unica",
    10: "Sprint Shootout 1",
    11: "Sprint Shootout 2",
    12: "Sprint Shootout 3",
    13: "Sprint Shootout curto",
    14: "Sprint Shootout volta unica",
    15: "Corrida",
    16: "Corrida 2",
    17: "Corrida 3",
    18: "Time Trial",
}
