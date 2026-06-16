from pathlib import Path

import pandas as pd

from fifa_analytics.paths import GOLD_DIR, RAW_DIR, SILVER_DIR
from fifa_analytics.reporting.build_report import build_match_report
from fifa_analytics.reporting.fragments import render_template, write_fragment
from fifa_analytics.sources.sample import fetch_match, fetch_matches
from fifa_analytics.transforms.matches import normalize_matches
from fifa_analytics.transforms.standings import calculate_group_standings
from fifa_analytics.transforms.teams import teams_from_matches
from fifa_analytics.utils.io import ensure_dir, write_dataframe, write_json
from fifa_analytics.utils.time import utc_now_iso, utc_timestamp_compact


def run_sample_pipeline(match_id: str = "mexico_africa_do_sul_2026_06_11") -> dict[str, Path | str]:
    collected_at = utc_timestamp_compact()
    raw_dir = ensure_dir(RAW_DIR / "sample" / "competition=world_cup_2026" / "date=sample" / f"collected_at={collected_at}")

    raw_matches = fetch_matches()
    raw_match = fetch_match(match_id)
    write_json(raw_dir / "matches.json", raw_matches)
    write_json(raw_dir / f"{match_id}.json", raw_match)

    matches = normalize_matches(raw_matches, source="sample")
    teams = teams_from_matches(matches)
    standings = calculate_group_standings(matches)

    matches_path = write_dataframe(SILVER_DIR / "matches" / "matches.parquet", matches)
    teams_path = write_dataframe(SILVER_DIR / "teams" / "teams.parquet", teams)
    standings_path = write_dataframe(SILVER_DIR / "standings" / "standings.parquet", standings)
    gold_standings_path = write_dataframe(GOLD_DIR / "standings" / "group_standings.parquet", standings)

    match = matches[matches["match_id"] == match_id].iloc[0].to_dict()
    scoreline = None
    if pd.notna(match.get("home_score")) and pd.notna(match.get("away_score")):
        scoreline = f"{int(match['home_score'])} x {int(match['away_score'])}"

    generated_at = utc_now_iso()
    write_fragment(
        match_id,
        "00_metadata",
        render_template(
            "fragments/00_metadata.md.j2",
            {
                "match_id": match_id,
                "generated_at": generated_at,
                "status": match.get("status", "desconhecido"),
                "group": match.get("group"),
                "stadium": match.get("stadium"),
                "sources": "amostra",
                "data_quality_status": "aviso",
            },
        ),
    )
    write_fragment(
        match_id,
        "01_match_summary",
        render_template(
            "fragments/01_match_summary.md.j2",
            {
                "home_team": match["home_team"],
                "away_team": match["away_team"],
                "scoreline": scoreline,
                "status": match.get("status", "desconhecido"),
            },
        ),
    )

    report_result = build_match_report(match_id, data_quality_status="aviso")

    return {
        "match_id": match_id,
        "raw_dir": raw_dir,
        "matches_path": matches_path,
        "teams_path": teams_path,
        "standings_path": standings_path,
        "gold_standings_path": gold_standings_path,
        "report_path": report_result["report_path"],
        "manifest_path": report_result["manifest_path"],
        "report_status": report_result["report_status"],
    }
