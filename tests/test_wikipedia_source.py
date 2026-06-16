import pandas as pd

from fifa_analytics.sources.wikipedia import (
    GROUPS,
    GROUP_START_INDEX,
    TABLES_PER_GROUP,
    clean_team_name,
    parse_group_events,
    parse_group_matches,
    parse_score,
)


def test_clean_team_name_removes_hosts_footnotes_and_extra_spaces():
    assert clean_team_name("México (H)[a]\xa0") == "México"


def test_parse_score_identifies_finished_and_scheduled_matches():
    assert parse_score("2–0") == (2, 0, "finalizado")
    assert parse_score("Match 25") == (None, None, "agendado")


def test_parse_group_matches_reads_score_and_match_number():
    tables = _fake_wikipedia_tables()

    records = parse_group_matches(tables)
    first = records[0]
    scheduled = records[2]

    assert len(records) == len(GROUPS) * 6
    assert first["group"] == "A"
    assert first["home_team"] == "México"
    assert first["away_team"] == "África do Sul"
    assert first["home_score"] == 2
    assert first["away_score"] == 0
    assert first["status"] == "finalizado"
    assert first["source_match_id"] == "Match 1"
    assert scheduled["status"] == "agendado"
    assert scheduled["source_match_id"] == "Match 25"


def test_parse_group_events_reads_goal_scorers_and_minutes():
    tables = _fake_wikipedia_tables()

    events = parse_group_events(tables)
    first = events[0]

    assert first["match_id"] == "mexico_africa_do_sul_2026_match_1"
    assert first["event_type"] == "gol"
    assert first["minute"] == "9"
    assert first["team"] == "México"
    assert first["player"] == "Quiñones"
    assert first["description"] == "Gol de Quiñones (México)"
    assert first["minute_sort"] == 900


def _fake_wikipedia_tables():
    total = GROUP_START_INDEX + len(GROUPS) * TABLES_PER_GROUP
    tables = [pd.DataFrame() for _ in range(total)]

    for group_index, group in enumerate(GROUPS):
        start = GROUP_START_INDEX + group_index * TABLES_PER_GROUP
        tables[start] = pd.DataFrame(
            [
                {"Pos": 1, "Teamvte": f"Team {group}1", "Pld": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "GD": 0, "Pts": 0},
            ]
        )
        for offset in range(1, TABLES_PER_GROUP):
            middle = "Match 25" if group == "A" and offset == 3 else "2–0"
            home = "México (H)" if group == "A" and offset == 1 else f"Team {group}{offset}"
            away = "África do Sul" if group == "A" and offset == 1 else f"Team {group}{offset + 1}"
            report = "[Report 1]" if group == "A" and offset == 1 else "[Report 99]"
            home_goals = "Quiñones 9' Jiménez 67'" if group == "A" and offset == 1 else None
            tables[start + offset] = pd.DataFrame([[home_goals, report, None]], columns=[home, middle, away])

    return tables
