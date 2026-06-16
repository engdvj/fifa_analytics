from __future__ import annotations

from pathlib import Path

from fifa_analytics.paths import GOLD_DIR, SILVER_DIR
from fifa_analytics.workflows.canonical_reports import run_canonical_reports


def run_basic_reports(source: str = "canonical", status: str = "finalizado") -> dict[str, object]:
    if source == "canonical":
        return run_canonical_reports(status=status)
    raise ValueError(
        "Relatorios finais usam a fonte 'canonical'. Rode as coletas por fonte e depois use "
        "`python -m fifa_analytics relatorios-basicos` para evitar duplicidade."
    )


def _matches_path(source: str) -> Path:
    if source == "wikipedia":
        return SILVER_DIR / "matches" / "wikipedia_matches.parquet"
    if source == "sample":
        return SILVER_DIR / "matches" / "matches.parquet"
    return SILVER_DIR / "matches" / f"{source}_matches.parquet"


def _standings_path(source: str) -> Path:
    if source == "wikipedia":
        return GOLD_DIR / "standings" / "wikipedia_calculated_group_standings.parquet"
    if source == "sample":
        return GOLD_DIR / "standings" / "group_standings.parquet"
    return GOLD_DIR / "standings" / f"{source}_calculated_group_standings.parquet"
