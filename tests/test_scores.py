import pandas as pd

from fifa_analytics.analytics.scores import (
    build_player_match_features,
    build_player_scores,
    build_team_match_features,
    build_team_scores,
)
from fifa_analytics.utils.text import slugify


def test_build_team_scores_ranks_stronger_match_profile():
    matches = pd.DataFrame(
        [
            {
                "canonical_match_id": "jogo_001",
                "date": "2026-06-11",
                "group": "A",
                "stage": "fase_de_grupos",
                "round": "1",
                "status": "finalizado",
                "home_team": "México",
                "away_team": "África do Sul",
                "home_score": 2,
                "away_score": 0,
            }
        ]
    )
    team_stats = pd.DataFrame(
        [
            {
                "match_id": "jogo_001",
                "team": "México",
                "possession": 60,
                "shots": 16,
                "shots_on_target": 4,
                "passes": 520,
                "pass_accuracy": 0.9,
                "fouls": 12,
                "yellow_cards": 1,
                "red_cards": 0,
            },
            {
                "match_id": "jogo_001",
                "team": "África do Sul",
                "possession": 40,
                "shots": 3,
                "shots_on_target": 1,
                "passes": 330,
                "pass_accuracy": 0.8,
                "fouls": 14,
                "yellow_cards": 2,
                "red_cards": 1,
            },
        ]
    )

    features = build_team_match_features(matches, team_stats)
    scores = build_team_scores(features)

    assert scores.iloc[0]["team"] == "México"
    assert scores.iloc[0]["score_geral"] > scores.iloc[1]["score_geral"]
    assert scores.iloc[0]["team_slug"] == "mexico"


def test_build_player_scores_uses_impact_per_match():
    player_stats = pd.DataFrame(
        [
            {
                "match_id": "jogo_001",
                "team": "México",
                "player_name": "Julián Quiñones",
                "goals": 1,
                "assists": 0,
                "shots": 5,
                "shots_on_target": 2,
                "saves": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            {
                "match_id": "jogo_001",
                "team": "México",
                "player_name": "Raúl Rangel",
                "goals": 0,
                "assists": 0,
                "shots": 0,
                "shots_on_target": 0,
                "saves": 2,
                "yellow_cards": 0,
                "red_cards": 0,
            },
        ]
    )

    features = build_player_match_features(player_stats)
    scores = build_player_scores(features)

    assert scores.iloc[0]["player_name"] == "Julián Quiñones"
    assert scores.iloc[0]["score_geral"] > scores.iloc[1]["score_geral"]
    assert slugify("Julián Quiñones_México") == "julian_quinones_mexico"
