from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from fifa_analytics.paths import GOLD_DIR, RAW_DIR, SILVER_DIR
from fifa_analytics.sources.scores365 import (
    discover_game_ids,
    fetch_tournament,
    normalize_player_stats,
    normalize_team_match_stats,
)
from fifa_analytics.utils.io import ensure_dir, read_dataframe, write_dataframe, write_json
from fifa_analytics.utils.time import utc_timestamp_compact

# Colunas exclusivas da 365Scores que enriquecem o canonical_team_stats —
# os campos em comum (shots, fouls, accurate_passes etc.) já vêm da ESPN e
# foram validados como idênticos entre as duas fontes; não há motivo para
# duplicá-los aqui.
_ENRICHMENT_COLUMNS = [
    "formation",
    "expected_assists",
    "key_passes",
    "touches",
    "dribbles_won",
    "was_dribbled_past",
    "possession_lost",
    "passes_into_final_third",
    "final_third_possession_won",
    "was_fouled",
    "error_led_to_shot",
]

SCORES365_MATCH_MAP_PATH = GOLD_DIR / "dim_match" / "365scores_match_map.parquet"


def run_scores365_pipeline(
    game_ids: list[int] | None = None,
    sleep_seconds: float = 0.3,
) -> dict[str, Any]:
    """Coleta dados da 365Scores e persiste nas camadas raw / silver / gold.

    Fluxo:
      1. Descobre IDs dos jogos da Copa 2026 por scan (ou usa ``game_ids``).
      2. Busca detalhe completo de cada jogo (lineups + stats por jogador).
      3. Salva o payload bruto em data/raw/365scores/.
      4. Normaliza team stats → data/silver/team_match_stats/365scores.parquet.
      5. Normaliza player stats → data/silver/player_match_stats/365scores.parquet.
      6. Copia para data/gold/ (silver é a fonte de verdade; gold é a camada analítica).
    """
    collected_at = utc_timestamp_compact()
    collection_date = collected_at[:8]

    raw_dir = ensure_dir(
        RAW_DIR
        / "365scores"
        / "competition=world_cup_2026"
        / f"date={collection_date}"
        / f"collected_at={collected_at}"
    )

    # --- Coleta ---
    if game_ids is None:
        game_ids = discover_game_ids(sleep_seconds=sleep_seconds)

    payload = fetch_tournament(game_ids=game_ids, sleep_seconds=sleep_seconds)

    write_json(raw_dir / "game_ids.json", payload["game_ids"])
    write_json(raw_dir / "details.json", payload["details"])

    # --- Normalização ---
    team_stats = normalize_team_match_stats(payload)
    player_stats = normalize_player_stats(payload)

    # Silver
    team_silver = write_dataframe(
        SILVER_DIR / "team_match_stats" / "365scores.parquet", team_stats
    )
    player_silver = write_dataframe(
        SILVER_DIR / "player_match_stats" / "365scores.parquet", player_stats
    )

    # Gold
    team_gold = write_dataframe(
        GOLD_DIR / "fact_team_match_stats" / "365scores.parquet", team_stats
    )
    player_gold = write_dataframe(
        GOLD_DIR / "fact_player_match_stats" / "365scores.parquet", player_stats
    )

    # --- Enriquecimento do canonical_team_stats com match_id canônico ---
    enriched = _map_to_canonical_match_id(team_stats)
    match_map_path = SCORES365_MATCH_MAP_PATH
    enrichment_path = write_dataframe(
        GOLD_DIR / "fact_team_match_stats" / "365scores_enrichment.parquet", enriched
    )

    # --- Nota de atuação por jogador, casada ao match_id canônico ---
    player_rating = _map_player_rating_to_canonical(player_stats)
    write_dataframe(
        GOLD_DIR / "fact_player_match_stats" / "365scores_rating.parquet", player_rating
    )

    games_played = team_stats["source_game_id"].nunique() if not team_stats.empty else 0
    teams = team_stats["team"].nunique() if not team_stats.empty else 0
    players = player_stats["player_name"].nunique() if not player_stats.empty else 0

    return {
        "raw_dir": raw_dir,
        "team_silver": team_silver,
        "player_silver": player_silver,
        "team_gold": team_gold,
        "player_gold": player_gold,
        "match_map_path": match_map_path,
        "enrichment_path": enrichment_path,
        "game_ids_scanned": len(payload["game_ids"]),
        "games_with_stats": games_played,
        "matches_mapped": enriched["match_id"].nunique() if not enriched.empty else 0,
        "teams": teams,
        "players": players,
        "team_stat_rows": len(team_stats),
        "player_stat_rows": len(player_stats),
    }


def _map_to_canonical_match_id(team_stats: pd.DataFrame) -> pd.DataFrame:
    """Liga as linhas da 365Scores ao match_id canônico via (team, opponent).

    A 365Scores não compartilha IDs de partida com nenhuma outra fonte. A chave
    estável é o CONFRONTO (time/adversário) — cada par de seleções se enfrenta
    uma única vez na fase de grupos, então o par já identifica a partida.

    NÃO usamos a data no casamento: a 365Scores às vezes traz a data ERRADA
    (ex.: Turquia×Austrália marcado em 14/06 quando o canônico tem 13/06), e um
    merge por data descartava silenciosamente esses jogos — o key_passes/dribbles
    deles se perdia e o time aparecia zerado. Casando só pelo confronto, o dado
    chega ao match_id correto independente da data divergente da fonte.

    No mata-mata (onde um confronto poderia, em tese, repetir), a data entra como
    desempate: entre os match_ids candidatos do mesmo par, escolhe o de data mais
    próxima da que a 365Scores reporta.
    """
    if team_stats.empty:
        return pd.DataFrame()

    available = [c for c in _ENRICHMENT_COLUMNS if c in team_stats.columns]
    subset = team_stats[["team", "opponent", "match_date"] + available].copy()
    if "source_game_id" in team_stats.columns:
        subset["source_game_id"] = team_stats["source_game_id"].values

    match_map = _build_scores365_match_map(team_stats)
    if match_map.empty:
        return pd.DataFrame()
    join_cols = ["source_game_id", "team", "opponent"] if "source_game_id" in subset.columns else ["team", "opponent"]
    merged = subset.merge(match_map[["match_id", *join_cols]], on=join_cols, how="inner")
    return merged[["match_id", "team", "opponent"] + available]


def _build_scores365_match_map(stats_365: pd.DataFrame) -> pd.DataFrame:
    """Cria/persiste um mapa robusto source_game_id → match_id canônico.

    A chave primária real da 365Scores é ``source_game_id``. O confronto segue
    sendo usado para descobrir o match canônico, mas a descoberta fica
    materializada e todas as etapas seguintes passam a se apoiar no id de fonte.
    """
    matches_path = GOLD_DIR / "dim_match" / "canonical_matches.parquet"
    if not matches_path.exists() or stats_365.empty:
        return pd.DataFrame()

    required = {"team", "opponent", "match_date"}
    if not required.issubset(stats_365.columns):
        return pd.DataFrame()

    matches = read_dataframe(matches_path)[
        ["canonical_match_id", "home_team", "away_team", "date"]
    ]
    home_side = matches.rename(columns={"home_team": "team", "away_team": "opponent"})[
        ["canonical_match_id", "team", "opponent", "date"]
    ]
    away_side = matches.rename(columns={"away_team": "team", "home_team": "opponent"})[
        ["canonical_match_id", "team", "opponent", "date"]
    ]
    match_lookup = pd.concat([home_side, away_side], ignore_index=True).rename(
        columns={"canonical_match_id": "match_id", "date": "canonical_date"}
    )

    source_cols = ["team", "opponent", "match_date"]
    if "source_game_id" in stats_365.columns:
        source_cols.insert(0, "source_game_id")
    source_rows = stats_365[source_cols].drop_duplicates().copy()
    merged = source_rows.merge(match_lookup, on=["team", "opponent"], how="inner")
    if merged.empty:
        return pd.DataFrame()

    merged["_d365"] = pd.to_datetime(merged["match_date"], errors="coerce")
    merged["_dcan"] = pd.to_datetime(merged["canonical_date"], errors="coerce")
    merged["_gap"] = (merged["_dcan"] - merged["_d365"]).abs()
    if "source_game_id" in merged.columns:
        dedupe_cols = ["source_game_id", "team", "opponent"]
    else:
        dedupe_cols = ["team", "opponent"]
    merged = (
        merged.sort_values(["_gap", "match_id"], na_position="last")
        .drop_duplicates(subset=dedupe_cols, keep="first")
        .drop(columns=["_d365", "_dcan"])
        .reset_index(drop=True)
    )
    if "_gap" in merged.columns:
        merged["date_gap_days"] = merged["_gap"].dt.days
        merged = merged.drop(columns=["_gap"])

    cols = [c for c in ["source_game_id", "match_id", "team", "opponent", "match_date", "canonical_date", "date_gap_days"] if c in merged.columns]
    out = merged[cols]
    write_dataframe(SCORES365_MATCH_MAP_PATH, out)
    return out


def _map_player_rating_to_canonical(player_stats: pd.DataFrame) -> pd.DataFrame:
    """Liga stats de jogador da 365Scores ao match_id canônico via o mesmo
    casamento por CONFRONTO (team, opponent) usado para o team stats — robusto à
    data divergente da fonte. O nome fica como vem da 365Scores e é reconciliado
    ao canônico no merge final (ver _attach_player_rating em canonical_reports)."""
    if player_stats.empty or "rating" not in player_stats.columns:
        return pd.DataFrame(columns=["match_id", "team", "player_name", "rating"])

    id_cols = [c for c in ["source_game_id", "player_id_365"] if c in player_stats.columns]
    passthrough_cols = [
        c
        for c in [
            "rating",
            "minutes",
            "expected_goals",
            "expected_assists",
            "expected_goals_on_target",
            "big_chances_created",
            "big_chances_missed",
            "big_chances_scored",
            "shots_woodwork",
            "key_passes",
            "dribbles_won",
            "was_dribbled_past",
            "possession_lost",
            "fouls",
            "was_fouled",
            "tackles_won",
            "interceptions",
            "clearances",
            "ball_recovery",
            "ground_duels_won",
            "aerial_duels_won",
            "shots_blocked",
            "crosses_completed",
            "long_passes_completed",
            "expected_goals_prevented",
            "expected_goals_on_target_conceded",
            "punches",
            "penalties_saved",
            "high_claims",
            "played_sweeper",
            "penalty_won",
            "penalty_committed",
            "penalties_missed",
            "error_led_to_goal",
            "goals_conceded",
        ]
        if c in player_stats.columns
    ]
    sub = player_stats[["team", "opponent", "player_name", *passthrough_cols, *id_cols]].copy()
    sub["rating"] = pd.to_numeric(sub["rating"], errors="coerce")
    sub = sub.dropna(subset=["rating"])
    match_map = _build_scores365_match_map(player_stats)
    if match_map.empty:
        return pd.DataFrame(columns=["match_id", "team", "player_name", *passthrough_cols, *id_cols])
    join_cols = ["source_game_id", "team", "opponent"] if "source_game_id" in sub.columns and "source_game_id" in match_map.columns else ["team", "opponent"]
    merged = sub.merge(match_map[["match_id", *join_cols]], on=join_cols, how="inner")
    dedupe_cols = ["match_id", "team"]
    if "player_id_365" in merged.columns:
        dedupe_cols.append("player_id_365")
    else:
        dedupe_cols.append("player_name")
    merged = merged.sort_values(["match_id", "team", "player_name"]).drop_duplicates(dedupe_cols, keep="first")
    return merged[["match_id", "team", "player_name", *passthrough_cols, *id_cols]]
