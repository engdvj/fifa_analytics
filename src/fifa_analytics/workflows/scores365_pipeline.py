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
    matches_path = GOLD_DIR / "dim_match" / "canonical_matches.parquet"
    if not matches_path.exists() or team_stats.empty:
        return pd.DataFrame()

    matches = read_dataframe(matches_path)[
        ["canonical_match_id", "home_team", "away_team", "date"]
    ]

    home_side = matches.rename(
        columns={"home_team": "team", "away_team": "opponent"}
    )[["canonical_match_id", "team", "opponent", "date"]]
    away_side = matches.rename(
        columns={"away_team": "team", "home_team": "opponent"}
    )[["canonical_match_id", "team", "opponent", "date"]]
    match_lookup = pd.concat([home_side, away_side], ignore_index=True)
    match_lookup = match_lookup.rename(columns={"date": "canonical_date"})

    available = [c for c in _ENRICHMENT_COLUMNS if c in team_stats.columns]
    subset = team_stats[["team", "opponent", "match_date"] + available].copy()

    # casa pelo CONFRONTO (sem data) — robusto a datas divergentes da fonte
    merged = subset.merge(match_lookup, on=["team", "opponent"], how="inner")

    # desempate (só importa se o mesmo confronto tiver >1 match_id candidato):
    # escolhe o de data canônica mais próxima da reportada pela 365Scores.
    if merged.duplicated(subset=["team", "opponent"], keep=False).any():
        merged["_d365"] = pd.to_datetime(merged["match_date"], errors="coerce")
        merged["_dcan"] = pd.to_datetime(merged["canonical_date"], errors="coerce")
        merged["_gap"] = (merged["_dcan"] - merged["_d365"]).abs()
        merged = (
            merged.sort_values("_gap")
            .drop_duplicates(subset=["team", "opponent"], keep="first")
        )

    merged = merged.rename(columns={"canonical_match_id": "match_id"})
    return merged[["match_id", "team", "opponent"] + available]


def _map_player_rating_to_canonical(player_stats: pd.DataFrame) -> pd.DataFrame:
    """Liga a nota de atuação (365Scores rating) ao match_id canônico, via o
    mesmo casamento por CONFRONTO (team, opponent) usado para o team stats —
    robusto à data divergente da fonte. Retorna [match_id, team, player_name,
    rating]; o nome fica como vem da 365Scores e é reconciliado ao canônico no
    merge final (ver _attach_player_rating em canonical_reports)."""
    matches_path = GOLD_DIR / "dim_match" / "canonical_matches.parquet"
    if not matches_path.exists() or player_stats.empty or "rating" not in player_stats.columns:
        return pd.DataFrame(columns=["match_id", "team", "player_name", "rating"])

    matches = read_dataframe(matches_path)[["canonical_match_id", "home_team", "away_team"]]
    home_side = matches.rename(columns={"home_team": "team", "away_team": "opponent"})
    away_side = matches.rename(columns={"away_team": "team", "home_team": "opponent"})
    match_lookup = pd.concat([home_side, away_side], ignore_index=True)[
        ["canonical_match_id", "team", "opponent"]
    ]

    sub = player_stats[["team", "opponent", "player_name", "rating"]].copy()
    sub["rating"] = pd.to_numeric(sub["rating"], errors="coerce")
    sub = sub.dropna(subset=["rating"])
    merged = sub.merge(match_lookup, on=["team", "opponent"], how="inner")
    merged = merged.rename(columns={"canonical_match_id": "match_id"})
    return merged[["match_id", "team", "player_name", "rating"]]
