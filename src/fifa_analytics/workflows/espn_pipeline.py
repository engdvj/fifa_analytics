from pathlib import Path

from fifa_analytics.paths import GOLD_DIR, RAW_DIR, SILVER_DIR
from fifa_analytics.sources.espn import (
    fetch_tournament,
    normalize_commentary_payload,
    normalize_events_payload,
    normalize_lineups_payload,
    normalize_match_info_payload,
    normalize_matches_payload,
    normalize_player_stats_payload,
    normalize_shots_payload,
    normalize_team_stats_payload,
)
from fifa_analytics.transforms.teams import teams_from_matches
from fifa_analytics.utils.io import ensure_dir, write_dataframe, write_json
from fifa_analytics.utils.time import utc_timestamp_compact


def run_espn_pipeline() -> dict[str, Path | int]:
    collected_at = utc_timestamp_compact()
    collection_date = collected_at[:8]
    raw_dir = ensure_dir(
        RAW_DIR
        / "espn"
        / "competition=world_cup_2026"
        / f"date={collection_date}"
        / f"collected_at={collected_at}"
    )

    payload = fetch_tournament()
    write_json(raw_dir / "scoreboards.json", payload["scoreboards"])
    write_json(raw_dir / "summaries.json", payload["summaries"])

    matches = normalize_matches_payload(payload["scoreboards"])
    team_stats = normalize_team_stats_payload(payload["scoreboards"], payload["summaries"])
    events = normalize_events_payload(payload["scoreboards"], payload["summaries"])
    lineups = normalize_lineups_payload(payload["summaries"])
    player_stats = normalize_player_stats_payload(payload["summaries"])
    match_info = normalize_match_info_payload(payload["scoreboards"], payload["summaries"])
    commentary = normalize_commentary_payload(payload["summaries"])
    shots = normalize_shots_payload(payload["summaries"])
    teams = teams_from_matches(matches.dropna(subset=["home_team", "away_team"]))

    matches_path = write_dataframe(SILVER_DIR / "matches" / "espn_matches.parquet", matches)
    teams_path = write_dataframe(SILVER_DIR / "teams" / "espn_teams.parquet", teams)
    events_path = write_dataframe(SILVER_DIR / "events" / "espn_events.parquet", events)
    team_stats_path = write_dataframe(SILVER_DIR / "team_stats" / "espn_team_stats.parquet", team_stats)
    lineups_path = write_dataframe(SILVER_DIR / "lineups" / "espn_lineups.parquet", lineups)
    player_stats_path = write_dataframe(SILVER_DIR / "player_stats" / "espn_player_stats.parquet", player_stats)
    match_info_path = write_dataframe(SILVER_DIR / "match_info" / "espn_match_info.parquet", match_info)
    commentary_path = write_dataframe(SILVER_DIR / "commentary" / "espn_commentary.parquet", commentary)
    shots_path = write_dataframe(SILVER_DIR / "shots" / "espn_shots.parquet", shots)

    gold_events_path = write_dataframe(GOLD_DIR / "fact_events" / "espn_events.parquet", events)
    gold_team_stats_path = write_dataframe(GOLD_DIR / "fact_team_match_stats" / "espn_team_stats.parquet", team_stats)
    gold_lineups_path = write_dataframe(GOLD_DIR / "lineups" / "espn_lineups.parquet", lineups)
    gold_player_stats_path = write_dataframe(GOLD_DIR / "fact_player_match_stats" / "espn_player_stats.parquet", player_stats)
    gold_match_info_path = write_dataframe(GOLD_DIR / "match_info" / "espn_match_info.parquet", match_info)
    gold_commentary_path = write_dataframe(GOLD_DIR / "fact_commentary" / "espn_commentary.parquet", commentary)
    gold_shots_path = write_dataframe(GOLD_DIR / "fact_shots" / "espn_shots.parquet", shots)

    return {
        "raw_dir": raw_dir,
        "matches_path": matches_path,
        "teams_path": teams_path,
        "events_path": events_path,
        "team_stats_path": team_stats_path,
        "lineups_path": lineups_path,
        "player_stats_path": player_stats_path,
        "match_info_path": match_info_path,
        "commentary_path": commentary_path,
        "shots_path": shots_path,
        "gold_events_path": gold_events_path,
        "gold_team_stats_path": gold_team_stats_path,
        "gold_lineups_path": gold_lineups_path,
        "gold_player_stats_path": gold_player_stats_path,
        "gold_match_info_path": gold_match_info_path,
        "gold_commentary_path": gold_commentary_path,
        "gold_shots_path": gold_shots_path,
        "matches": len(matches),
        "events": len(events),
        "team_stats": len(team_stats),
        "lineups": len(lineups),
        "player_stats": len(player_stats),
        "match_info": len(match_info),
        "commentary": len(commentary),
        "shots": len(shots),
    }
