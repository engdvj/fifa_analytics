import pandas as pd

from fifa_analytics.transforms.standings import calculate_group_standings


def test_calculate_group_standings_scores_points_and_goal_difference():
    matches = pd.DataFrame(
        [
            {
                "group": "A",
                "home_team": "México",
                "away_team": "África do Sul",
                "home_score": 2,
                "away_score": 0,
                "status": "finalizado",
            },
            {
                "group": "A",
                "home_team": "Coreia do Sul",
                "away_team": "Tchéquia",
                "home_score": 1,
                "away_score": 1,
                "status": "finalizado",
            },
        ]
    )

    standings = calculate_group_standings(matches)
    mexico = standings[standings["team"] == "México"].iloc[0]
    czechia = standings[standings["team"] == "Tchéquia"].iloc[0]

    assert mexico["points"] == 3
    assert mexico["goal_difference"] == 2
    assert czechia["points"] == 1
    assert czechia["draws"] == 1


def test_calculate_group_standings_keeps_unfinished_teams_without_points():
    matches = pd.DataFrame(
        [
            {
                "group": "A",
                "home_team": "México",
                "away_team": "África do Sul",
                "home_score": None,
                "away_score": None,
                "status": "agendado",
            }
        ]
    )

    standings = calculate_group_standings(matches)
    mexico = standings[standings["team"] == "México"].iloc[0]

    assert len(standings) == 2
    assert mexico["played"] == 0
    assert mexico["points"] == 0
