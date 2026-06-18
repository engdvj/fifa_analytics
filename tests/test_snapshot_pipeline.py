import pandas as pd

import fifa_analytics.workflows.snapshot_pipeline as snapshot_pipeline


def test_player_snapshot_rating_uses_normalized_score_name(tmp_path, monkeypatch):
    player_timeline = tmp_path / "player_snapshot_timeline.parquet"
    monkeypatch.setattr(snapshot_pipeline, "PLAYER_TIMELINE_PATH", player_timeline)

    player_stats = pd.DataFrame(
        [
            {
                "match_id": "j1",
                "team": "Brasil",
                "player_name": "Raphinha ",
                "position": "F",
                "appearances": 1,
                "minutes": 90,
                "rating": 7.1,
                "goals": 0,
                "assists": 0,
                "shots": 1,
                "shots_on_target": 0,
                "saves": 0,
                "goals_conceded": 0,
                "yellow_cards": 0,
                "red_cards": 0,
                "fouls_committed": 0,
                "fouls_drawn": 0,
            }
        ]
    )

    snapshot_pipeline._build_player_snapshot(
        player_stats=player_stats,
        lineups=pd.DataFrame(),
        rosters=pd.DataFrame(),
        ids_ate_agora=["j1"],
        n=1,
        match_id="j1",
    )

    snap = pd.read_parquet(player_timeline)
    row = snap[snap["player_slug"] == "raphinha_brasil"].iloc[0]

    assert row["player_name"] == "Raphinha"
    assert row["rating_365"] == 7.1
