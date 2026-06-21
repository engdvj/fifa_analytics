"""Analytics: endpoints que leem os parquets do gold e retornam JSON.

Sem ORM — lê direto do parquet com pandas. Os dados são imutáveis entre
coletas (somente leitura), então sem write neste router.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from fifa_analytics.paths import GOLD_DIR
from fifa_analytics.transforms.team_names import traduzir_selecao

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _parquet(name: str) -> pd.DataFrame:
    path = GOLD_DIR / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _safe_val(v) -> Any:
    """Converte NaN/NaT para None para serialização JSON."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


# ── Jogos ─────────────────────────────────────────────────────────────────────

@router.get("/matches")
def list_matches_analytics(status: str | None = None) -> list[dict]:
    """Todos os 104 jogos do gold parquet."""
    df = _parquet("dim_match.parquet")
    if df.empty:
        return []
    if status:
        df = df[df["status"] == status]
    cols = [
        "match_id", "match_number", "home_team", "away_team",
        "home_team_code", "away_team_code", "stage", "group",
        "date_utc", "status", "home_score", "away_score",
        "home_penalty", "away_penalty", "stadium", "id_ifes",
    ]
    available = [c for c in cols if c in df.columns]
    return [
        {k: _safe_val(row[k]) for k in available}
        for row in df[available].to_dict("records")
    ]


@router.get("/matches/{match_id}/stats")
def match_team_stats(match_id: str) -> dict:
    """Métricas avançadas de time do jogo (fact_team_match_stats)."""
    df = _parquet("fact_team_match_stats.parquet")
    if df.empty:
        raise HTTPException(404, "stats não disponíveis (rode fifa-coletar)")
    rows = df[df["match_id"] == match_id]
    if rows.empty:
        raise HTTPException(404, "sem stats para esse jogo")
    by_team: dict[str, list] = {}
    for r in rows.itertuples():
        tid = str(r.id_team)
        by_team.setdefault(tid, []).append({
            "metric": r.metric,
            "value": _safe_val(r.value),
            "is_official": _safe_val(r.is_official),
        })
    return {"match_id": match_id, "teams": by_team}


@router.get("/matches/{match_id}/lineups")
def match_lineups(match_id: str) -> list[dict]:
    """Escalação dos dois times (fact_lineups)."""
    df = _parquet("fact_lineups.parquet")
    if df.empty:
        raise HTTPException(404, "lineups não disponíveis")
    rows = df[df["match_id"] == match_id]
    if rows.empty:
        raise HTTPException(404, "sem escalação para esse jogo")
    cols = ["team_side", "id_team", "id_player", "player_name",
            "shirt_number", "position", "is_starter", "captain",
            "lineup_x", "lineup_y"]
    available = [c for c in cols if c in rows.columns]
    return [{k: _safe_val(r[k]) for k in available} for r in rows[available].to_dict("records")]


@router.get("/matches/{match_id}/events")
def match_events(match_id: str) -> list[dict]:
    """Gols, cartões e substituições do jogo (fact_events)."""
    df = _parquet("fact_events.parquet")
    if df.empty:
        raise HTTPException(404, "eventos não disponíveis")
    rows = df[df["match_id"] == match_id]
    if rows.empty:
        return []
    cols = ["event_type", "minute", "id_team", "id_player", "player_name",
            "detail", "id_assist", "id_player2", "player2_name"]
    available = [c for c in cols if c in rows.columns]
    return [{k: _safe_val(r[k]) for k in available} for r in rows[available].to_dict("records")]


@router.get("/matches/{match_id}/player-stats")
def match_player_stats(match_id: str) -> dict:
    """Métricas por jogador no jogo (fact_player_match_stats)."""
    df = _parquet("fact_player_match_stats.parquet")
    if df.empty:
        raise HTTPException(404, "player stats não disponíveis")
    rows = df[df["match_id"] == match_id]
    if rows.empty:
        raise HTTPException(404, "sem player stats para esse jogo")
    by_player: dict[str, list] = {}
    for r in rows.itertuples():
        pid = str(r.id_player)
        by_player.setdefault(pid, []).append({
            "metric": r.metric,
            "value": _safe_val(r.value),
            "is_official": _safe_val(r.is_official),
        })
    return {"match_id": match_id, "players": by_player}


# ── Power Ranking ──────────────────────────────────────────────────────────────

@router.get("/power-ranking")
def power_ranking(
    player_type: str | None = Query(None, description="outfield ou goalkeeper"),
    team: str | None = None,
) -> list[dict]:
    """Power Ranking FIFA por jogador."""
    df = _parquet("fact_power_ranking.parquet")
    if df.empty:
        raise HTTPException(404, "power ranking não disponível (rode fifa-coletar)")
    if player_type:
        df = df[df["player_type"] == player_type]
    if team:
        team_pt = traduzir_selecao(team)
        df = df[df["team_name"].isin([team, team_pt])]

    cols = [
        "id_player", "player_name", "id_team", "team_name", "player_type",
        "attacking_score", "attacking_rank", "attacking_rank_change",
        "defensive_score", "defensive_rank", "defensive_rank_change",
        "creativity_score", "creativity_rank", "creativity_rank_change",
    ]
    available = [c for c in cols if c in df.columns]
    return [{k: _safe_val(r[k]) for k in available} for r in df[available].to_dict("records")]


# ── Times: estatísticas agregadas ─────────────────────────────────────────────

@router.get("/teams/stats-by-game")
def teams_stats_by_game(
    metric: str = Query("XG", description="nome da métrica no fact_team_match_stats"),
) -> list[dict]:
    """Valor de uma métrica por time por jogo (para construir curvas de trajetória)."""
    stats = _parquet("fact_team_match_stats.parquet")
    matches = _parquet("dim_match.parquet")
    if stats.empty or matches.empty:
        return []

    filtered = stats[stats["metric"] == metric][["match_id", "id_team", "value"]].copy()
    if filtered.empty:
        return []

    merged = filtered.merge(
        matches[["match_id", "match_number", "home_team", "away_team",
                 "id_team_home", "id_team_away"]],
        on="match_id", how="left",
    )
    return [
        {
            "match_id": r["match_id"],
            "match_number": _safe_val(r["match_number"]),
            "id_team": r["id_team"],
            "value": _safe_val(r["value"]),
        }
        for r in merged.to_dict("records")
    ]


@router.get("/teams/available-metrics")
def available_metrics() -> list[str]:
    """Lista de métricas disponíveis no fact_team_match_stats."""
    df = _parquet("fact_team_match_stats.parquet")
    if df.empty or "metric" not in df.columns:
        return []
    return sorted(df["metric"].dropna().unique().tolist())


@router.get("/teams/{id_team}/stats")
def team_stats(id_team: str) -> dict:
    """Todas as métricas de um time, todos os jogos."""
    stats = _parquet("fact_team_match_stats.parquet")
    if stats.empty:
        raise HTTPException(404, "stats não disponíveis")
    rows = stats[stats["id_team"] == id_team]
    if rows.empty:
        raise HTTPException(404, f"sem stats para time {id_team}")
    by_match: dict[str, list] = {}
    for r in rows.itertuples():
        by_match.setdefault(r.match_id, []).append({
            "metric": r.metric,
            "value": _safe_val(r.value),
        })
    return {"id_team": id_team, "matches": by_match}
