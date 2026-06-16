from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd


def slugify(value: Any) -> str:
    text = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_") or "sem_nome"


def goals_per_shot(goals: int | float | None, shots: int | float | None) -> float | None:
    if shots in (None, 0):
        return None
    if goals is None:
        return None
    return float(goals) / float(shots)


# Códigos de posição como vêm da ESPN (coordenada de formação, não nome de
# posição) traduzidos para rótulo legível em pt-BR. "-L"/"-R"/"-C" indicam o
# lado dentro da linha (esquerda/direita/centro), preservado no rótulo.
_POSITION_LABELS: dict[str, str] = {
    "G": "Goleiro", "GK": "Goleiro",
    "SW": "Líbero",
    "CD": "Zagueiro", "CD-L": "Zagueiro esquerdo", "CD-R": "Zagueiro direito",
    "CB": "Zagueiro", "D": "Defensor",
    "RB": "Lateral direito", "LB": "Lateral esquerdo",
    "RWB": "Ala direito", "LWB": "Ala esquerdo",
    "DM": "Volante", "CDM": "Volante",
    "CM": "Meio-campo", "CM-L": "Meio-campo esquerdo", "CM-R": "Meio-campo direito",
    "M": "Meio-campo", "MF": "Meio-campo",
    "AM": "Meia-atacante", "AM-L": "Meia-atacante esquerdo", "AM-R": "Meia-atacante direito",
    "CAM": "Meia-atacante",
    "RM": "Meia direito", "LM": "Meia esquerdo",
    "CF": "Centroavante", "CF-L": "Atacante", "CF-R": "Atacante",
    "ST": "Atacante", "SS": "Segundo atacante",
    "F": "Atacante", "LF": "Atacante esquerdo", "RF": "Atacante direito",
    "RW": "Ponta direito", "LW": "Ponta esquerdo",
    "SUB": "Reserva",
}


def position_label(position: Any) -> str:
    if position is None or (isinstance(position, float) and pd.isna(position)):
        return ""
    code = str(position).strip().upper()
    return _POSITION_LABELS.get(code, code)


# Ordem tática de exibição (goleiro → defesa → meio → ataque). A ordem bruta
# da fonte (formation_slot) segue a numeração interna da ESPN, não a posição
# em campo — por isso "Raphinha" podia aparecer antes dos zagueiros.
_POSITION_ORDER: dict[str, int] = {
    "G": 0, "GK": 0,
    "SW": 1, "CD": 1, "CD-L": 1, "CD-R": 1, "CB": 1, "D": 1,
    "RB": 2, "LB": 2, "RWB": 2, "LWB": 2,
    "DM": 3, "CDM": 3,
    "CM": 4, "CM-L": 4, "CM-R": 4, "M": 4, "MF": 4,
    "RM": 5, "LM": 5,
    "AM": 6, "AM-L": 6, "AM-R": 6, "CAM": 6,
    "RW": 7, "LW": 7,
    "CF": 8, "CF-L": 8, "CF-R": 8, "ST": 8, "SS": 8, "F": 8, "LF": 8, "RF": 8,
    "SUB": 9,
}


def position_order(position: Any) -> int:
    if position is None or (isinstance(position, float) and pd.isna(position)):
        return 99
    code = str(position).strip().upper()
    return _POSITION_ORDER.get(code, 99)
