from pathlib import Path

import pandas as pd

from fifa_analytics.paths import GOLD_DIR, RAW_DIR, SILVER_DIR
from fifa_analytics.reporting.fragments import render_template, write_fragment
from fifa_analytics.reporting.tournament_reports import format_standings_table
from fifa_analytics.sources.wikipedia import fetch_html, fetch_tables, parse_group_events, parse_group_matches, parse_group_standings
from fifa_analytics.transforms.matches import normalize_matches
from fifa_analytics.transforms.standings import calculate_group_standings
from fifa_analytics.transforms.teams import teams_from_matches
from fifa_analytics.validation.standings_validation import compare_standings
from fifa_analytics.utils.io import ensure_dir, write_dataframe, write_json
from fifa_analytics.utils.time import utc_now_iso, utc_timestamp_compact


def run_wikipedia_pipeline(match_id: str | None = None) -> dict[str, Path | str | int]:
    collected_at = utc_timestamp_compact()
    raw_dir = ensure_dir(RAW_DIR / "wikipedia" / "competition=world_cup_2026" / "date=inicial" / f"collected_at={collected_at}")

    html = fetch_html()
    (raw_dir / "page.html").write_text(html, encoding="utf-8")
    tables = fetch_tables(html)
    raw_matches = parse_group_matches(tables)
    raw_events = parse_group_events(tables)
    external_standings = parse_group_standings(tables)
    write_json(raw_dir / "matches.json", raw_matches)
    write_json(raw_dir / "events.json", raw_events)

    matches = normalize_matches(raw_matches, source="wikipedia")
    events = pd.DataFrame(raw_events)
    teams = teams_from_matches(matches)
    calculated_standings = calculate_group_standings(matches)
    standings_validation = compare_standings(calculated_standings, external_standings)

    matches_path = write_dataframe(SILVER_DIR / "matches" / "wikipedia_matches.parquet", matches)
    events_path = write_dataframe(SILVER_DIR / "events" / "wikipedia_events.parquet", events)
    teams_path = write_dataframe(SILVER_DIR / "teams" / "wikipedia_teams.parquet", teams)
    external_standings_path = write_dataframe(SILVER_DIR / "standings" / "wikipedia_standings.parquet", external_standings)
    calculated_standings_path = write_dataframe(
        GOLD_DIR / "standings" / "wikipedia_calculated_group_standings.parquet",
        calculated_standings,
    )
    gold_events_path = write_dataframe(GOLD_DIR / "fact_events" / "wikipedia_events.parquet", events)
    validation_path = write_json(
        SILVER_DIR / "validation_results" / "wikipedia_standings_validation.json",
        standings_validation,
    )

    return {
        "raw_dir": raw_dir,
        "matches_path": matches_path,
        "events_path": events_path,
        "teams_path": teams_path,
        "external_standings_path": external_standings_path,
        "calculated_standings_path": calculated_standings_path,
        "gold_events_path": gold_events_path,
        "validation_path": validation_path,
        "matches": len(matches),
    }


def _select_match(matches: pd.DataFrame, match_id: str | None) -> dict:
    if match_id:
        filtered = matches[matches["match_id"] == match_id]
        if filtered.empty:
            available = ", ".join(matches["match_id"].head(5).tolist())
            raise KeyError(f"match_id not found: {match_id}. Examples: {available}")
        return filtered.iloc[0].to_dict()

    finished = matches[matches["status"] == "finalizado"]
    if not finished.empty:
        return finished.iloc[0].to_dict()
    return matches.iloc[0].to_dict()


def write_basic_fragments(
    match: dict,
    standings: pd.DataFrame,
    standings_validation: dict,
    events: pd.DataFrame | None = None,
    fonte_descricao: str = "Dados carregados da Wikipedia como fonte publica inicial.",
    fonte_status: str = "wikipedia_inicial",
    data_quality_status: str = "aviso",
) -> None:
    match_id = match["match_id"]
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
                "date": match.get("date"),
                "stadium": match.get("stadium"),
                "city": match.get("city"),
                "country": match.get("country"),
            },
        ),
    )
    write_fragment(
        match_id,
        "02_context",
        render_template(
            "fragments/02_context.md.j2",
            {
                "context": (
                    f"Partida do Grupo {match.get('group')} na fase de grupos. "
                    f"{fonte_descricao}"
                )
            },
        ),
    )
    group_standings = standings[standings["group"] == match.get("group")]
    write_fragment(
        match_id,
        "05_team_stats",
        render_template(
            "fragments/05_team_stats.md.j2",
            {"team_stats": format_standings_table(group_standings)},
        ),
    )
    match_events = _events_for_match(events, match_id)
    write_fragment(
        match_id,
        "04_timeline",
        render_template(
            "fragments/04_timeline.md.j2",
            {"events": match_events},
        ),
    )
    write_fragment(
        match_id,
        "08_data_quality",
        render_template(
            "fragments/08_data_quality.md.j2",
            {
                "data_quality_status": data_quality_status,
                "checks": [
                    {"field": "fonte", "status": fonte_status},
                    {"field": "oficial", "status": "nao"},
                    {"field": "classificacao_fonte_vs_calculada", "status": standings_validation["status"]},
                ],
            },
        ),
    )


def _events_for_match(events: pd.DataFrame | None, match_id: str) -> list[dict]:
    if events is None or events.empty:
        return []
    match_events = events[events["match_id"] == match_id].copy()
    if match_events.empty:
        return []
    return match_events.sort_values(["minute_sort", "team"]).to_dict("records")
