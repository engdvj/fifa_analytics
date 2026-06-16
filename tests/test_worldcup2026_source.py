from fifa_analytics.sources.worldcup2026 import (
    normalize_events_payload,
    normalize_matches_payload,
    normalize_standings_payload,
)


def test_normalize_matches_payload_translates_teams_and_stadiums():
    matches = normalize_matches_payload(_fake_games(), _fake_stadiums())

    first = matches.iloc[0]

    assert first["match_id"] == "australia_paraguai_2026_match_6"
    assert first["home_team"] == "Austrália"
    assert first["away_team"] == "Paraguai"
    assert first["date"] == "2026-06-13"
    assert first["kickoff_time"] == "21:00"
    assert first["stadium"] == "Houston Stadium"
    assert first["country"] == "Estados Unidos"
    assert first["status"] == "finalizado"
    assert first["winner"] == "Austrália"


def test_normalize_matches_payload_ignores_zero_scores_for_scheduled_matches():
    games = _fake_games()
    games[0] = {
        **games[0],
        "id": "31",
        "home_score": "0",
        "away_score": "0",
        "finished": "FALSE",
        "time_elapsed": "notstarted",
    }

    matches = normalize_matches_payload(games, _fake_stadiums())
    first = matches.iloc[0]

    assert first["status"] == "agendado"
    assert first["home_score"] is None
    assert first["away_score"] is None
    assert first["winner"] is None


def test_normalize_events_payload_extracts_goal_minutes():
    events = normalize_events_payload(_fake_games())

    assert len(events) == 3
    assert events.iloc[0]["player"] == "Nestory Irankunda"
    assert events.iloc[0]["minute"] == "27"
    assert events.iloc[0]["minute_sort"] == 2700
    assert events.iloc[2]["minute"] == "45+2"
    assert events.iloc[2]["stoppage_minute"] == 2


def test_normalize_standings_payload_uses_portuguese_team_names():
    standings = normalize_standings_payload(_fake_groups(), _fake_teams())

    row = standings[standings["team"] == "Austrália"].iloc[0]

    assert row["group"] == "D"
    assert row["played"] == 1
    assert row["wins"] == 1
    assert row["points"] == 3


def _fake_games():
    return [
        {
            "id": "6",
            "home_team_id": "15",
            "away_team_id": "16",
            "home_score": "2",
            "away_score": "1",
            "home_scorers": "{\"Nestory Irankunda 27'\",\"C. Metcalfe 75'\"}",
            "away_scorers": "{\"Miguel Almiron 45+2'\"}",
            "group": "D",
            "matchday": "1",
            "local_date": "06/13/2026 21:00",
            "stadium_id": "13",
            "finished": "TRUE",
            "time_elapsed": "finished",
            "type": "group",
            "home_team_name_en": "Australia",
            "away_team_name_en": "Paraguay",
        }
    ]


def _fake_stadiums():
    return [
        {
            "id": "13",
            "name_en": "NRG Stadium",
            "fifa_name": "Houston Stadium",
            "city_en": "Houston",
            "country_en": "United States",
            "capacity": 72000,
            "region": "South",
        }
    ]


def _fake_teams():
    return [
        {"id": "15", "name_en": "Australia", "fifa_code": "AUS", "groups": "D"},
        {"id": "16", "name_en": "Paraguay", "fifa_code": "PAR", "groups": "D"},
    ]


def _fake_groups():
    return [
        {
            "name": "D",
            "teams": [
                {"team_id": "15", "mp": "1", "w": "1", "d": "0", "l": "0", "gf": "2", "ga": "1", "gd": "1", "pts": "3"},
                {"team_id": "16", "mp": "1", "w": "0", "d": "0", "l": "1", "gf": "1", "ga": "2", "gd": "-1", "pts": "0"},
            ],
        }
    ]
