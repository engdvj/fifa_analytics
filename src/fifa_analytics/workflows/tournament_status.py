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


def run_tournament_status(source: str = "fifa") -> dict[str, Path | str | int]:
    # Fonte única FIFA: lê o dim_match do gold e calcula a classificação de grupos
    # a partir dos jogos finalizados (sem parquet de standings pré-computado).
    matches_path = GOLD_DIR / "dim_match.parquet"
    matches = read_dataframe(matches_path)
    standings = compute_group_standings(matches)
    standings_path = write_dataframe(GOLD_DIR / "standings" / "fifa_group_standings.parquet", standings) if not standings.empty else None
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
        final_report_path = _final_report_path(match_id, manifest)
        report_exists = final_report_path is not None
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
                "final_report_path": str(final_report_path) if final_report_path else None,
                "status_updated_at": utc_now_iso(),
            }
        )
    status = pd.DataFrame(rows)
    if "temporal_order" in status.columns:
        return status.sort_values(["temporal_order", "match_id"], na_position="last").reset_index(drop=True)
    return status


def compute_group_standings(matches: pd.DataFrame) -> pd.DataFrame:
    """Classificação de grupos a partir dos jogos FINALIZADOS da fase de grupos.

    Vitória=3, empate=1. Colunas: group, team, played, won, drawn, lost,
    goals_for, goals_against, goal_difference, points — ordenadas por grupo e
    pontos (desempate por saldo e gols pró)."""
    if matches.empty or "group" not in matches.columns:
        return pd.DataFrame()
    fin = matches[
        (matches["status"] == "finalizado")
        & matches["group"].notna()
        & matches["home_score"].notna()
        & matches["away_score"].notna()
    ]
    if fin.empty:
        return pd.DataFrame()

    acc: dict[tuple, dict] = {}

    def _row(group, team) -> dict:
        return acc.setdefault(
            (group, team),
            {"group": group, "team": team, "played": 0, "won": 0, "drawn": 0,
             "lost": 0, "goals_for": 0, "goals_against": 0, "points": 0},
        )

    for _, m in fin.iterrows():
        g = m["group"]
        hs, as_ = int(m["home_score"]), int(m["away_score"])
        h, a = _row(g, m["home_team"]), _row(g, m["away_team"])
        for side, gf, ga in ((h, hs, as_), (a, as_, hs)):
            side["played"] += 1
            side["goals_for"] += gf
            side["goals_against"] += ga
        if hs > as_:
            h["won"] += 1; h["points"] += 3; a["lost"] += 1
        elif hs < as_:
            a["won"] += 1; a["points"] += 3; h["lost"] += 1
        else:
            h["drawn"] += 1; a["drawn"] += 1; h["points"] += 1; a["points"] += 1

    df = pd.DataFrame(acc.values())
    df["goal_difference"] = df["goals_for"] - df["goals_against"]
    return df.sort_values(
        ["group", "points", "goal_difference", "goals_for"],
        ascending=[True, False, False, False],
    ).reset_index(drop=True)


def _read_manifest(match_id: str) -> dict[str, Any]:
    path = MANIFESTS_DIR / f"{match_id}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _final_report_path(match_id: str, manifest: dict[str, Any]) -> Path | None:
    manifest_path = manifest.get("final_report_path")
    if manifest_path:
        path = Path(str(manifest_path))
        if path.exists():
            return path

    legacy_path = FINAL_REPORTS_DIR / f"{match_id}.md"
    if legacy_path.exists():
        return legacy_path

    match_number = str(match_id).rsplit("_", 1)[-1]
    for path in FINAL_REPORTS_DIR.rglob(f"{match_number}_*.md"):
        return path
    return None


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
