from pathlib import Path

from fifa_analytics.paths import GOLD_DIR, RAW_DIR, SILVER_DIR
import pandas as pd

from fifa_analytics.sources.espn import (
    fetch_all_rosters,
    fetch_tournament,
    normalize_commentary_payload,
    normalize_events_payload,
    normalize_lineups_payload,
    normalize_match_info_payload,
    normalize_matches_payload,
    normalize_player_stats_from_commentary,
    normalize_player_stats_payload,
    normalize_rosters_payload,
    normalize_shots_payload,
    normalize_team_stats_payload,
)
from fifa_analytics.transforms.teams import teams_from_matches
from fifa_analytics.utils.io import ensure_dir, write_dataframe, write_json
from fifa_analytics.utils.time import utc_timestamp_compact


def run_espn_rosters_pipeline() -> dict[str, Path | int]:
    """Coleta o elenco completo (convocacao) de cada selecao, com posicao estavel
    independente do jogador ter entrado em campo. Diferente de run_espn_pipeline,
    que coleta a escalacao titular por partida — aqui e o roster do time, que nao
    muda durante o torneio, por isso roda separado e nao precisa ser repetido a
    cada atualizacao de resultados."""
    collected_at = utc_timestamp_compact()
    collection_date = collected_at[:8]
    raw_dir = ensure_dir(
        RAW_DIR / "espn" / "competition=world_cup_2026" / f"date={collection_date}" / f"collected_at={collected_at}"
    )

    payload = fetch_all_rosters()
    write_json(raw_dir / "rosters.json", payload)

    rosters = normalize_rosters_payload(payload)
    rosters_path = write_dataframe(SILVER_DIR / "rosters" / "espn_rosters.parquet", rosters)
    gold_rosters_path = write_dataframe(GOLD_DIR / "rosters" / "espn_rosters.parquet", rosters)

    return {
        "raw_dir": raw_dir,
        "rosters_path": rosters_path,
        "gold_rosters_path": gold_rosters_path,
        "rosters": len(rosters),
        "times": rosters["team"].nunique() if not rosters.empty else 0,
    }


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
    player_stats_roster = normalize_player_stats_payload(payload["summaries"])
    player_stats_commentary = normalize_player_stats_from_commentary(payload["summaries"])
    match_info = normalize_match_info_payload(payload["scoreboards"], payload["summaries"])
    commentary = normalize_commentary_payload(payload["summaries"])
    shots = normalize_shots_payload(payload["summaries"])

    # Merge: stats dos rosters (goals, assists, saves, goals_conceded) +
    # stats do commentary (shots, fouls, offsides por jogador)
    player_stats = _merge_player_stats(player_stats_roster, player_stats_commentary, lineups)
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


def _merge_player_stats(
    roster_stats: pd.DataFrame,
    commentary_stats: pd.DataFrame,
    lineups: pd.DataFrame,
) -> pd.DataFrame:
    """Enriquece os stats dos rosters com eventos individuais extraídos do commentary.

    O commentary não tem time para a vítima de faltas (fouls_drawn_commentary),
    então resolve o time pelo match via lineups antes do merge.
    """
    if roster_stats.empty:
        return roster_stats

    if commentary_stats.empty or "player_name" not in commentary_stats.columns:
        return roster_stats

    # Resolver time dos jogadores sem team no commentary (vítimas de falta)
    if not lineups.empty and {"match_id", "player_name", "team"}.issubset(lineups.columns):
        name_to_team = (
            lineups[["match_id", "player_name", "team"]]
            .drop_duplicates(["match_id", "player_name"])
        )
        comm = commentary_stats.copy()
        # Para linhas sem team, preenche via lineup
        missing_team = comm["team"].isna() | (comm["team"] == "")
        if missing_team.any():
            filled = comm[missing_team].drop(columns=["team"]).merge(
                name_to_team, on=["match_id", "player_name"], how="left"
            )
            comm.loc[missing_team, "team"] = filled["team"].values
    else:
        comm = commentary_stats.copy()

    # Agrupar commentary por (match_id, player_name, team) — pode haver duplicatas
    # por jogadores sem team resolvido
    num_cols = [c for c in comm.columns if c not in ("match_id", "player_name", "team", "team_display", "source", "collected_at", "source_match_id")]
    for col in num_cols:
        comm[col] = pd.to_numeric(comm[col], errors="coerce").fillna(0)
    comm_agg = comm.groupby(["match_id", "player_name", "team"], dropna=False)[num_cols].sum().reset_index()

    # Merge com roster_stats
    merged = roster_stats.merge(comm_agg, on=["match_id", "player_name", "team"], how="left")

    # Substituir colunas quando o commentary tem dados melhores (mais granulares)
    # shots_on_target do commentary é por evento, mais confiável que o roster aggregado
    if "shots_on_target_commentary" in merged.columns:
        # Preenche onde o roster tem 0 mas o commentary tem dados
        roster_sot = pd.to_numeric(merged.get("shots_on_target", 0), errors="coerce").fillna(0)
        comm_sot = pd.to_numeric(merged["shots_on_target_commentary"], errors="coerce").fillna(0)
        merged["shots_on_target"] = roster_sot.where(roster_sot > 0, comm_sot)
        merged = merged.drop(columns=["shots_on_target_commentary"])

    if "goals_commentary" in merged.columns:
        roster_g = pd.to_numeric(merged.get("goals", 0), errors="coerce").fillna(0)
        comm_g = pd.to_numeric(merged["goals_commentary"], errors="coerce").fillna(0)
        merged["goals"] = roster_g.where(roster_g > 0, comm_g)
        merged = merged.drop(columns=["goals_commentary"])

    if "fouls_committed_commentary" in merged.columns:
        roster_fc = pd.to_numeric(merged.get("fouls_committed", 0), errors="coerce").fillna(0)
        comm_fc = pd.to_numeric(merged["fouls_committed_commentary"], errors="coerce").fillna(0)
        merged["fouls_committed"] = roster_fc.where(roster_fc > 0, comm_fc)
        merged = merged.drop(columns=["fouls_committed_commentary"])

    if "fouls_drawn_commentary" in merged.columns:
        roster_fd = pd.to_numeric(merged.get("fouls_drawn", 0), errors="coerce").fillna(0)
        comm_fd = pd.to_numeric(merged["fouls_drawn_commentary"], errors="coerce").fillna(0)
        merged["fouls_drawn"] = roster_fd.where(roster_fd > 0, comm_fd)
        merged = merged.drop(columns=["fouls_drawn_commentary"])

    # Novas colunas do commentary que não existiam no roster
    for col in ["shots_off_target", "shots_blocked_att", "shots_woodwork", "offsides_commentary", "corners_won"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)

    if "offsides_commentary" in merged.columns:
        merged = merged.rename(columns={"offsides_commentary": "offsides_player"})
    if "own_goals_commentary" in merged.columns:
        merged = merged.rename(columns={"own_goals_commentary": "own_goals_player"})

    return merged
