from pathlib import Path

from fifa_analytics.paths import GOLD_DIR, RAW_DIR, SILVER_DIR
from fifa_analytics.sources.worldcup2026 import (
    fetch_all,
    normalize_events_payload,
    normalize_matches_payload,
    normalize_stadiums_payload,
    normalize_standings_payload,
    normalize_teams_payload,
)
from fifa_analytics.transforms.standings import calculate_group_standings
from fifa_analytics.utils.io import ensure_dir, write_dataframe, write_json
from fifa_analytics.utils.time import utc_timestamp_compact
from fifa_analytics.validation.standings_validation import compare_standings


def run_worldcup2026_pipeline(match_id: str | None = None) -> dict[str, Path | str | int]:
    collected_at = utc_timestamp_compact()
    collection_date = collected_at[:8]
    raw_dir = ensure_dir(
        RAW_DIR
        / "worldcup2026"
        / "competition=world_cup_2026"
        / f"date={collection_date}"
        / f"collected_at={collected_at}"
    )

    payload = fetch_all()
    write_json(raw_dir / "health.json", payload["health"])
    write_json(raw_dir / "teams.json", payload["teams"])
    write_json(raw_dir / "stadiums.json", payload["stadiums"])
    write_json(raw_dir / "groups.json", payload["groups"])
    write_json(raw_dir / "games.json", payload["games"])

    raw_games = payload["games"].get("games", [])
    raw_teams = payload["teams"].get("teams", [])
    raw_stadiums = payload["stadiums"].get("stadiums", [])
    raw_groups = payload["groups"].get("groups", [])

    matches = normalize_matches_payload(raw_games, raw_stadiums)
    events = normalize_events_payload(raw_games)
    teams = normalize_teams_payload(raw_teams)
    stadiums = normalize_stadiums_payload(raw_stadiums)
    external_standings = normalize_standings_payload(raw_groups, raw_teams)
    calculated_standings = calculate_group_standings(matches)
    standings_validation = compare_standings(calculated_standings, external_standings)

    matches_path = write_dataframe(SILVER_DIR / "matches" / "worldcup2026_matches.parquet", matches)
    events_path = write_dataframe(SILVER_DIR / "events" / "worldcup2026_events.parquet", events)
    teams_path = write_dataframe(SILVER_DIR / "teams" / "worldcup2026_teams.parquet", teams)
    stadiums_path = write_dataframe(SILVER_DIR / "stadiums" / "worldcup2026_stadiums.parquet", stadiums)
    external_standings_path = write_dataframe(SILVER_DIR / "standings" / "worldcup2026_standings.parquet", external_standings)
    calculated_standings_path = write_dataframe(
        GOLD_DIR / "standings" / "worldcup2026_calculated_group_standings.parquet",
        calculated_standings,
    )
    gold_events_path = write_dataframe(GOLD_DIR / "fact_events" / "worldcup2026_events.parquet", events)
    validation_path = write_json(
        SILVER_DIR / "validation_results" / "worldcup2026_standings_validation.json",
        standings_validation,
    )

    return {
        "raw_dir": raw_dir,
        "matches_path": matches_path,
        "events_path": events_path,
        "teams_path": teams_path,
        "stadiums_path": stadiums_path,
        "external_standings_path": external_standings_path,
        "calculated_standings_path": calculated_standings_path,
        "gold_events_path": gold_events_path,
        "validation_path": validation_path,
        "matches": len(matches),
        "events": len(events),
    }
