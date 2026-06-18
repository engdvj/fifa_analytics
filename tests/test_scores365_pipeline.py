import pandas as pd

from fifa_analytics.workflows.scores365_pipeline import _map_player_rating_to_canonical


def test_map_player_rating_to_canonical_uses_source_game_id_and_date_gap(tmp_path, monkeypatch):
    import fifa_analytics.workflows.scores365_pipeline as pipeline

    gold = tmp_path / "gold"
    matches_dir = gold / "dim_match"
    matches_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "canonical_match_id": "copa_2026_jogo_001",
                "home_team": "Brasil",
                "away_team": "Argentina",
                "date": "2026-06-11",
            },
            {
                "canonical_match_id": "copa_2026_jogo_099",
                "home_team": "Brasil",
                "away_team": "Argentina",
                "date": "2026-07-01",
            },
        ]
    ).to_parquet(matches_dir / "canonical_matches.parquet")

    monkeypatch.setattr(pipeline, "GOLD_DIR", gold)
    monkeypatch.setattr(pipeline, "SCORES365_MATCH_MAP_PATH", matches_dir / "365scores_match_map.parquet")

    stats = pd.DataFrame(
        [
            {
                "source_game_id": 111,
                "match_date": "2026-06-12",
                "team": "Brasil",
                "opponent": "Argentina",
                "player_id_365": 1,
                "player_name": "Jogador A",
                "rating": 7.1,
            },
            {
                "source_game_id": 222,
                "match_date": "2026-07-01",
                "team": "Brasil",
                "opponent": "Argentina",
                "player_id_365": 2,
                "player_name": "Jogador B",
                "rating": 8.2,
            },
        ]
    )

    mapped = _map_player_rating_to_canonical(stats)

    assert dict(zip(mapped["source_game_id"], mapped["match_id"])) == {
        111: "copa_2026_jogo_001",
        222: "copa_2026_jogo_099",
    }
    assert (matches_dir / "365scores_match_map.parquet").exists()
