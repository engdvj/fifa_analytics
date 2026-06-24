import pandas as pd

from fifa_analytics.analytics.scores import build_team_scores


def test_distancia_total_km_pj_uses_match_average_once():
    dim_match = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "status": "finalizado",
                "home_team": "A",
                "away_team": "B",
                "home_score": 1,
                "away_score": 0,
                "date_utc": "2026-06-01T00:00:00Z",
            },
            {
                "match_id": "m2",
                "status": "finalizado",
                "home_team": "A",
                "away_team": "C",
                "home_score": 0,
                "away_score": 0,
                "date_utc": "2026-06-02T00:00:00Z",
            },
        ]
    )
    wide = pd.DataFrame(
        [
            {"match_id": "m1", "team": "A", "distancia_total": 110_000, "sprints": 400, "xg": 1.0, "chutes_no_alvo": 3, "posse": 0.55},
            {"match_id": "m1", "team": "B", "distancia_total": 108_000, "sprints": None, "xg": 0.5, "chutes_no_alvo": 1, "posse": 0.45},
            {"match_id": "m2", "team": "A", "distancia_total": 120_000, "sprints": 500, "xg": 0.8, "chutes_no_alvo": 2, "posse": 0.50},
            {"match_id": "m2", "team": "C", "distancia_total": 112_000, "sprints": 300, "xg": 0.7, "chutes_no_alvo": 2, "posse": 0.50},
        ]
    )

    scores = build_team_scores(wide, dim_match)
    team_a = scores.loc[scores["team"] == "A"].iloc[0]
    team_b = scores.loc[scores["team"] == "B"].iloc[0]

    assert team_a["jogos"] == 2
    assert team_a["distancia_total_km_pj"] == 115.0
    assert team_a["sprints_pj"] == 450.0
    assert pd.isna(team_b["sprints_pj"])
