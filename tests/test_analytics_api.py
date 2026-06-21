"""Testes dos endpoints de analytics (leitura de parquet).

Os endpoints de analytics lêem direto do gold parquet — sem banco.
Os testes usam os parquets reais em data/gold/ se disponíveis;
caso não existam, os testes são pulados graciosamente.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.app.main import app
from fifa_analytics.paths import GOLD_DIR

pytestmark = pytest.mark.analytics

client = TestClient(app)


def _has_gold(name: str) -> bool:
    return (GOLD_DIR / name).exists()


# ── /analytics/matches ────────────────────────────────────────────────────────

def test_list_matches_analytics():
    r = client.get("/analytics/matches")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "match_id" in first
        assert "status" in first
        assert "home_team" in first


def test_list_matches_filter_status():
    r = client.get("/analytics/matches?status=finalizado")
    assert r.status_code == 200
    data = r.json()
    for m in data:
        assert m["status"] == "finalizado"


# ── Alemanha vs Costa do Marfim ──────────────────────────────────────────────

MATCH_ID = "copa_2026_jogo_033"


@pytest.mark.skipif(not _has_gold("dim_match.parquet"), reason="gold não disponível")
def test_alemanha_ivory_coast_exists():
    r = client.get("/analytics/matches")
    ids = {m["match_id"] for m in r.json()}
    assert MATCH_ID in ids, "jogo 033 não encontrado no gold"


@pytest.mark.skipif(not _has_gold("fact_team_match_stats.parquet"), reason="gold não disponível")
def test_alemanha_ivory_coast_team_stats():
    r = client.get(f"/analytics/matches/{MATCH_ID}/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["match_id"] == MATCH_ID
    assert len(data["teams"]) == 2  # dois times
    # deve ter ao menos XG e Possession
    all_metrics = {m["metric"] for stats in data["teams"].values() for m in stats}
    assert "XG" in all_metrics
    assert "Possession" in all_metrics


@pytest.mark.skipif(not _has_gold("fact_lineups.parquet"), reason="gold não disponível")
def test_alemanha_ivory_coast_lineups():
    r = client.get(f"/analytics/matches/{MATCH_ID}/lineups")
    assert r.status_code == 200
    players = r.json()
    assert len(players) > 0
    sides = {p["team_side"] for p in players}
    assert "home" in sides and "away" in sides
    starters = [p for p in players if p["is_starter"]]
    assert len(starters) == 22, f"esperava 22 titulares, achei {len(starters)}"
    # Neuer deve estar na escalação
    names = [p["player_name"] for p in players if p["player_name"]]
    assert any("NEUER" in n.upper() for n in names), "Neuer não encontrado"


@pytest.mark.skipif(not _has_gold("fact_events.parquet"), reason="gold não disponível")
def test_alemanha_ivory_coast_events():
    r = client.get(f"/analytics/matches/{MATCH_ID}/events")
    assert r.status_code == 200
    events = r.json()
    goals = [e for e in events if e["event_type"] == "goal"]
    subs = [e for e in events if e["event_type"] == "substitution"]
    assert len(goals) == 3, f"esperava 3 gols (2-1), achei {len(goals)}"
    assert len(subs) >= 6


# ── Power Ranking ─────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _has_gold("fact_power_ranking.parquet"), reason="gold não disponível")
def test_power_ranking_outfield():
    r = client.get("/analytics/power-ranking?player_type=outfield")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 100  # deve ter muitos jogadores de linha
    first = data[0]
    assert "player_name" in first
    assert "attacking_score" in first
    assert "creativity_score" in first


@pytest.mark.skipif(not _has_gold("fact_power_ranking.parquet"), reason="gold não disponível")
def test_power_ranking_goalkeepers():
    r = client.get("/analytics/power-ranking?player_type=goalkeeper")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0
    for p in data:
        assert p["player_type"] == "goalkeeper"
        assert p["creativity_score"] is None  # goleiros não têm creativity


@pytest.mark.skipif(not _has_gold("fact_power_ranking.parquet"), reason="gold não disponível")
def test_power_ranking_filter_by_team():
    r = client.get("/analytics/power-ranking?team=Alemanha")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0
    for p in data:
        assert p["team_name"] in ("Alemanha", "Germany")


# ── Métricas disponíveis ──────────────────────────────────────────────────────

@pytest.mark.skipif(not _has_gold("fact_team_match_stats.parquet"), reason="gold não disponível")
def test_available_metrics():
    r = client.get("/analytics/teams/available-metrics")
    assert r.status_code == 200
    metrics = r.json()
    assert "XG" in metrics
    assert "Possession" in metrics
    assert len(metrics) > 10


@pytest.mark.skipif(not _has_gold("fact_team_match_stats.parquet"), reason="gold não disponível")
def test_stats_by_game_xg():
    r = client.get("/analytics/teams/stats-by-game?metric=XG")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0
    # deve ter dados do jogo 033 (Alemanha vs CI)
    match_ids = {d["match_id"] for d in data}
    assert MATCH_ID in match_ids


# ── Erros esperados ───────────────────────────────────────────────────────────

def test_match_stats_jogo_inexistente():
    r = client.get("/analytics/matches/copa_2026_jogo_999/stats")
    assert r.status_code in (404,)


def test_match_lineups_jogo_inexistente():
    r = client.get("/analytics/matches/copa_2026_jogo_999/lineups")
    # pode retornar 404 ou lista vazia (se o gold não existir)
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert r.json() == []
