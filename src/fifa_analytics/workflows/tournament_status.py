from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fifa_analytics.paths import FINAL_REPORTS_DIR, FRAGMENTS_DIR, GOLD_DIR, MANIFESTS_DIR, SILVER_DIR, TOURNAMENT_REPORTS_DIR
from fifa_analytics.reporting.tournament_reports import build_missing_reports, build_standings_report, build_status_summary
from fifa_analytics.utils.io import ensure_dir, read_dataframe, write_dataframe
from fifa_analytics.utils.time import utc_now_iso


EXPECTED_FRAGMENT_IDS = [
    "00_metadata",
    "01_match_summary",
    "02_context",
    "03_lineups",
    "04_timeline",
    "05_team_stats",
    "06_player_stats",
    "07_key_insights",
    "08_data_quality",
]


def run_tournament_status(source: str = "canonical") -> dict[str, Path | str | int]:
    matches_path = _matches_path(source)
    standings_path = _standings_path(source)

    matches = read_dataframe(matches_path)
    standings = read_dataframe(standings_path) if standings_path.exists() else pd.DataFrame()
    status = build_tournament_status(matches)

    status_path = write_dataframe(GOLD_DIR / "tournament_status" / "tournament_status.parquet", status)
    ensure_dir(TOURNAMENT_REPORTS_DIR)

    status_report_path = TOURNAMENT_REPORTS_DIR / "status.md"
    status_report_path.write_text(build_status_summary(status), encoding="utf-8")

    standings_report_path = TOURNAMENT_REPORTS_DIR / "standings.md"
    standings_report_path.write_text(build_standings_report(standings), encoding="utf-8")

    missing_report_path = TOURNAMENT_REPORTS_DIR / "pendencias_relatorios.md"
    missing_report_path.write_text(build_missing_reports(status), encoding="utf-8")

    return {
        "source": source,
        "matches_path": matches_path,
        "standings_path": standings_path,
        "status_path": status_path,
        "status_report_path": status_report_path,
        "standings_report_path": standings_report_path,
        "missing_report_path": missing_report_path,
        "matches": len(status),
        "relatorios_completos": int((status["report_status"] == "completo").sum()),
        "relatorios_parciais": int((status["report_status"] == "parcial").sum()),
        "relatorios_nao_iniciados": int((status["report_status"] == "nao_iniciado").sum()),
    }


def build_tournament_status(matches: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, match in matches.iterrows():
        match_id = match["match_id"]
        manifest = _read_manifest(match_id)
        missing_sections = _missing_sections(match_id, manifest)
        report_exists = (FINAL_REPORTS_DIR / f"{match_id}.md").exists()
        report_status = _report_status(report_exists, missing_sections)

        rows.append(
            {
                "match_id": match_id,
                "match_number": match.get("match_number"),
                "temporal_order": match.get("temporal_order"),
                "date": match.get("date"),
                "home_team": match.get("home_team"),
                "away_team": match.get("away_team"),
                "stage": match.get("stage"),
                "group": match.get("group"),
                "status": match.get("status", "desconhecido"),
                "last_raw_ingestion_at": None,
                "last_validation_at": None,
                "last_report_build_at": manifest.get("last_updated_at"),
                "has_summary": _has_fragment(match_id, "01_match_summary"),
                "has_context": _has_fragment(match_id, "02_context"),
                "has_lineups": _has_fragment(match_id, "03_lineups"),
                "has_events": _has_fragment(match_id, "04_timeline"),
                "has_team_stats": _has_fragment(match_id, "05_team_stats"),
                "has_player_stats": _has_fragment(match_id, "06_player_stats"),
                "has_insights": _has_fragment(match_id, "07_key_insights"),
                "missing_sections": missing_sections,
                "data_quality_status": manifest.get("data_quality_status", "desconhecido"),
                "report_status": report_status,
                "final_report_path": str(FINAL_REPORTS_DIR / f"{match_id}.md") if report_exists else None,
                "status_updated_at": utc_now_iso(),
            }
        )
    status = pd.DataFrame(rows)
    if "temporal_order" in status.columns:
        return status.sort_values(["temporal_order", "match_id"], na_position="last").reset_index(drop=True)
    return status


def _matches_path(source: str) -> Path:
    if source == "canonical":
        return GOLD_DIR / "dim_match" / "canonical_matches.parquet"
    if source == "wikipedia":
        return SILVER_DIR / "matches" / "wikipedia_matches.parquet"
    if source == "sample":
        return SILVER_DIR / "matches" / "matches.parquet"
    return SILVER_DIR / "matches" / f"{source}_matches.parquet"


def _standings_path(source: str) -> Path:
    if source == "canonical":
        return GOLD_DIR / "standings" / "worldcup2026_calculated_group_standings.parquet"
    if source == "wikipedia":
        return SILVER_DIR / "standings" / "wikipedia_standings.parquet"
    if source == "sample":
        return SILVER_DIR / "standings" / "standings.parquet"
    return SILVER_DIR / "standings" / f"{source}_standings.parquet"


def _read_manifest(match_id: str) -> dict[str, Any]:
    path = MANIFESTS_DIR / f"{match_id}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _has_fragment(match_id: str, fragment_id: str) -> bool:
    return (FRAGMENTS_DIR / match_id / f"{fragment_id}.md").exists()


def _missing_sections(match_id: str, manifest: dict[str, Any]) -> list[str]:
    if "missing_sections" in manifest:
        return list(manifest["missing_sections"] or [])
    return [fragment_id for fragment_id in EXPECTED_FRAGMENT_IDS if not _has_fragment(match_id, fragment_id)]


def _report_status(report_exists: bool, missing_sections: list[str]) -> str:
    if not report_exists:
        return "nao_iniciado"
    if missing_sections:
        return "parcial"
    return "completo"
