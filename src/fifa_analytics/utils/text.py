from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd


_DASH_TRANSLATION = str.maketrans({
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2015": "-",  # horizontal bar
    "\u2212": "-",  # minus sign
})
_SPACE_TRANSLATION = str.maketrans({
    "\u00a0": " ",
    "\u1680": " ",
    "\u2000": " ",
    "\u2001": " ",
    "\u2002": " ",
    "\u2003": " ",
    "\u2004": " ",
    "\u2005": " ",
    "\u2006": " ",
    "\u2007": " ",
    "\u2008": " ",
    "\u2009": " ",
    "\u200a": " ",
    "\u202f": " ",
    "\u205f": " ",
    "\u3000": " ",
})
_ZERO_WIDTH_TRANSLATION = str.maketrans({
    "\u200b": "",
    "\u200c": "",
    "\u200d": "",
    "\ufeff": "",
})
_APOSTROPHE_TRANSLATION = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u2032": "'",
})


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def slugify(value: Any) -> str:
    text = "" if _is_missing(value) else str(value)
    text = text.translate(
        str.maketrans(
            {
                "ø": "o",
                "Ø": "O",
                "ð": "d",
                "Ð": "D",
                "þ": "th",
                "Þ": "Th",
                "ł": "l",
                "Ł": "L",
                "æ": "ae",
                "Æ": "Ae",
                "œ": "oe",
                "Œ": "Oe",
            }
        )
    )
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_") or "sem_nome"


def clean_person_name(value: Any) -> str:
    """Nome de pessoa limpo para exibição e joins internos.

    Mantém acentos e hífen canônico, mas remove sujeiras comuns de scraping:
    espaços invisíveis, NBSP, hífens Unicode, espaços ao redor do hífen e
    sufixo literal "null".
    """
    if _is_missing(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.translate(_ZERO_WIDTH_TRANSLATION)
    text = text.translate(_SPACE_TRANSLATION)
    text = text.translate(_DASH_TRANSLATION)
    text = text.translate(_APOSTROPHE_TRANSLATION)
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text.casefold().endswith(" null"):
        text = text[:-5].strip()
    return text


def person_name_key(value: Any) -> str:
    """Chave ampla de casamento: acento/caixa ignorados e hífen = espaço."""
    text = clean_person_name(value)
    if not text:
        return ""
    return slugify(text.replace("-", " "))


def person_name_words_key(value: Any) -> str:
    """Mesma chave ampla, em formato de palavras separado por espaço."""
    return person_name_key(value).replace("_", " ")


def person_name_exact_key(value: Any) -> str:
    """Chave exata: preserva acentos e diferença hífen/espaço, mas limpa ruído."""
    return clean_person_name(value).casefold()


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
