from fifa_analytics.sources.espn import (
    normalize_commentary_payload,
    normalize_events_payload,
    normalize_lineups_payload,
    normalize_match_info_payload,
    normalize_matches_payload,
    normalize_team_stats_payload,
    normalize_shots_payload,
)


def test_normalize_espn_matches_and_team_stats():
    scoreboards = [{"date": "2026-06-13", "payload": {"events": [_fake_event()]}}]
    summaries = {"760419": _fake_summary()}

    matches = normalize_matches_payload(scoreboards)
    team_stats = normalize_team_stats_payload(scoreboards, summaries)

    assert matches.iloc[0]["match_id"] == "brasil_marrocos_espn_760419"
    assert matches.iloc[0]["home_team"] == "Brasil"
    assert matches.iloc[0]["away_team"] == "Marrocos"
    assert matches.iloc[0]["group"] == "C"
    assert matches.iloc[0]["status"] == "finalizado"

    brazil = team_stats[team_stats["team"] == "Brasil"].iloc[0]
    assert brazil["possession"] == 51.4
    assert brazil["shots"] == 12
    assert brazil["shots_on_target"] == 5
    assert brazil["passes"] == 514


def test_normalize_espn_events_and_lineups():
    scoreboards = [{"date": "2026-06-13", "payload": {"events": [_fake_event()]}}]
    summaries = {"760419": _fake_summary()}

    events = normalize_events_payload(scoreboards, summaries)
    lineups = normalize_lineups_payload(summaries)

    assert events.iloc[0]["event_type"] == "gol"
    assert events.iloc[0]["team"] == "Marrocos"
    assert events.iloc[0]["player"] == "Ismael Saibari"
    assert events.iloc[1]["event_type"] == "cartao_amarelo"
    assert lineups.iloc[0]["team"] == "Brasil"
    assert lineups.iloc[0]["player_name"] == "Alisson Becker"
    assert bool(lineups.iloc[0]["is_starter"]) is True


def test_normalize_espn_match_info_and_commentary():
    scoreboards = [{"date": "2026-06-13", "payload": {"events": [_fake_event()]}}]
    summaries = {"760419": _fake_summary()}

    match_info = normalize_match_info_payload(scoreboards, summaries)
    commentary = normalize_commentary_payload(summaries)
    shots = normalize_shots_payload(summaries)

    assert match_info.iloc[0]["attendance"] == 80663
    assert match_info.iloc[0]["referee"] == "Slavko Vincic"
    assert match_info.iloc[0]["broadcasts"] == "FOX, Tele"
    assert match_info.iloc[0]["article_headline"] == "Brasil empata com Marrocos"
    assert commentary.iloc[0]["play_type"] == "shot-blocked"
    assert commentary.iloc[0]["team"] == "Brasil"
    assert commentary.iloc[0]["participants"] == "Casemiro, Achraf Hakimi"
    assert shots.iloc[0]["outcome"] == "bloqueado"
    assert shots.iloc[0]["player"] == "Casemiro"
    assert shots.iloc[0]["assist_player"] == "Achraf Hakimi"
    assert shots.iloc[0]["location_x"] == 44.4
    assert shots.iloc[0]["location_y"] == 90.4


def _fake_event():
    return {
        "id": "760419",
        "date": "2026-06-13T22:00Z",
        "season": {"slug": "group-stage"},
        "links": [{"rel": ["summary"], "href": "https://www.espn.com/soccer/match/_/gameId/760419"}],
        "competitions": [
            {
                "id": "760419",
                "date": "2026-06-13T22:00Z",
                "altGameNote": "FIFA World Cup, Group C",
                "status": {"type": {"state": "post", "completed": True}},
                "venue": {"fullName": "MetLife Stadium", "address": {"city": "East Rutherford", "country": "USA"}},
                "competitors": [
                    {
                        "homeAway": "home",
                        "winner": False,
                        "score": "1",
                        "team": {"id": "205", "displayName": "Brazil", "abbreviation": "BRA"},
                    },
                    {
                        "homeAway": "away",
                        "winner": False,
                        "score": "1",
                        "team": {"id": "2869", "displayName": "Morocco", "abbreviation": "MAR"},
                    },
                ],
                "details": [],
            }
        ],
    }


def _fake_summary():
    event = _fake_event()["competitions"][0]
    return {
        "header": {"competitions": [event]},
        "boxscore": {
            "teams": [
                {
                    "homeAway": "home",
                    "team": {"id": "205", "displayName": "Brazil", "abbreviation": "BRA"},
                    "statistics": [
                        {"name": "possessionPct", "value": 51.4},
                        {"name": "totalShots", "value": 12},
                        {"name": "shotsOnTarget", "value": 5},
                        {"name": "totalPasses", "value": 514},
                    ],
                },
                {
                    "homeAway": "away",
                    "team": {"id": "2869", "displayName": "Morocco", "abbreviation": "MAR"},
                    "statistics": [
                        {"name": "possessionPct", "value": 48.6},
                        {"name": "totalShots", "value": 10},
                        {"name": "shotsOnTarget", "value": 3},
                    ],
                },
            ]
        },
        "keyEvents": [
            {
                "id": "event_1",
                "type": {"text": "Goal"},
                "clock": {"displayValue": "21'"},
                "period": {"number": 1},
                "team": {"id": "2869"},
                "scoringPlay": True,
                "athletesInvolved": [{"id": "304572", "displayName": "Ismael Saibari"}],
            },
            {
                "id": "event_2",
                "type": {"text": "Yellow Card"},
                "clock": {"displayValue": "37'"},
                "period": {"number": 1},
                "team": {"id": "205"},
                "athletesInvolved": [{"id": "173666", "displayName": "Casemiro"}],
            },
        ],
        "gameInfo": {
            "attendance": 80663,
            "officials": [
                {"displayName": "Slavko Vincic", "position": {"displayName": "Referee"}},
            ],
            "venue": {"fullName": "MetLife Stadium", "address": {"city": "East Rutherford", "country": "USA"}},
        },
        "broadcasts": [
            {"media": {"shortName": "FOX"}},
            {"media": {"shortName": "Tele"}},
        ],
        "article": {
            "headline": "Brasil empata com Marrocos",
            "description": "Resumo curto.",
            "links": {"web": {"href": "https://example.com/report"}},
            "images": [{"url": "https://example.com/image.jpg"}],
        },
        "commentary": [
            {
                "sequence": 2,
                "time": {"value": 64.0, "displayValue": "2'"},
                "text": "Foul by Casemiro.",
                "play": {
                    "id": "play_1",
                    "type": {"type": "shot-blocked", "text": "Shot Blocked"},
                    "period": {"number": 1},
                    "team": {"displayName": "Brazil"},
                    "text": "Attempt blocked. Casemiro (Brazil) right footed shot from outside the box is blocked. Assisted by Achraf Hakimi.",
                    "participants": [
                        {"athlete": {"displayName": "Casemiro"}},
                        {"athlete": {"displayName": "Achraf Hakimi"}},
                    ],
                    "fieldPositionX": 44.4,
                    "fieldPositionY": 90.4,
                },
            }
        ],
        "rosters": [
            {
                "formation": "4-2-3-1",
                "team": {"displayName": "Brazil"},
                "roster": [
                    {
                        "starter": True,
                        "jersey": "1",
                        "athlete": {"id": "196876", "displayName": "Alisson Becker"},
                        "position": {"abbreviation": "G"},
                        "formationPlace": 1,
                        "stats": [{"name": "minutes", "value": 90}],
                    }
                ],
            }
        ],
    }
