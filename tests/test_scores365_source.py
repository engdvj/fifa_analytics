from fifa_analytics.sources import scores365
from fifa_analytics.sources.scores365 import _parse_player_stats


def test_parse_player_stats_includes_defensive_goalkeeper_and_xg_metrics():
    stats = _parse_player_stats(
        [
            {"type": 39, "value": "2/3 (67%)"},
            {"type": 41, "value": "4"},
            {"type": 40, "value": "7"},
            {"type": 86, "value": "9"},
            {"type": 55, "value": "5/8 (63%)"},
            {"type": 56, "value": "3/4 (75%)"},
            {"type": 83, "value": "1.24"},
            {"type": 76, "value": "0.62"},
            {"type": 53, "value": "6/10 (60%)"},
            {"type": 35, "value": "1"},
            {"type": 24, "value": "2"},
            {"type": 25, "value": "1"},
            {"type": 44, "value": "1"},
            {"type": 57, "value": "3"},
            {"type": 66, "value": "1"},
            {"type": 87, "value": "2"},
        ]
    )

    assert stats["tackles_won"] == 2
    assert stats["interceptions"] == 4
    assert stats["clearances"] == 7
    assert stats["ball_recovery"] == 9
    assert stats["ground_duels_won"] == 5
    assert stats["aerial_duels_won"] == 3
    assert stats["expected_goals_prevented"] == 1.24
    assert stats["expected_goals"] == 0.62
    assert stats["long_passes_completed"] == 6
    assert stats["goals_conceded"] == 1
    assert stats["big_chances_created"] == 2
    assert stats["shots_woodwork"] == 1
    assert stats["penalties_saved"] == 1
    assert stats["high_claims"] == 3
    assert stats["error_led_to_goal"] == 1
    assert stats["big_chances_scored"] == 2


def test_scores365_source_reads_base_url_and_competition_from_config(monkeypatch):
    monkeypatch.setattr(
        scores365,
        "load_config",
        lambda _name: {"sources": {"scores365": {"base_url": "https://example.test/web", "competition_id": 999}}},
    )

    assert scores365._base_url() == "https://example.test/web"
    assert scores365._competition_id() == 999
