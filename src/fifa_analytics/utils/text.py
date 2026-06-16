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
