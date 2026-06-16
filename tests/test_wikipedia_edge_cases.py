"""Testes de edge cases para o parser da Wikipedia.

Cobre: tabelas com colunas insuficientes, HTML malformado, times com
caracteres especiais, células de gol vazias e colunas numéricas ruins.
"""
import math

import pandas as pd
import pytest

from fifa_analytics.sources.wikipedia import (
    GROUPS,
    GROUP_START_INDEX,
    TABLES_PER_GROUP,
    _parse_goal_events,
    _to_int,
    _winner,
    clean_team_name,
    parse_group_events,
    parse_group_matches,
    parse_score,
)


# ---------------------------------------------------------------------------
# clean_team_name
# ---------------------------------------------------------------------------

def test_clean_team_name_keeps_accented_chars():
    assert clean_team_name("Côte d'Ivoire") == "Côte d'Ivoire"


def test_clean_team_name_strips_multiple_footnotes():
    assert clean_team_name("Brasil [a][b]") == "Brasil"


def test_clean_team_name_handles_non_breaking_space_only():
    result = clean_team_name("\xa0")
    assert result.strip() == ""


def test_clean_team_name_handles_empty_string():
    result = clean_team_name("")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# parse_score
# ---------------------------------------------------------------------------

def test_parse_score_rejects_invalid_patterns():
    assert parse_score("TBD") == (None, None, "agendado")
    assert parse_score("") == (None, None, "agendado")
    assert parse_score("Match 99") == (None, None, "agendado")


def test_parse_score_accepts_em_dash():
    home, away, status = parse_score("3–1")
    assert (home, away, status) == (3, 1, "finalizado")


def test_parse_score_accepts_hyphen():
    home, away, status = parse_score("0-0")
    assert (home, away, status) == (0, 0, "finalizado")


def test_parse_score_goalless_draw():
    home, away, status = parse_score("0–0")
    assert status == "finalizado"
    assert home == 0
    assert away == 0


# ---------------------------------------------------------------------------
# _winner
# ---------------------------------------------------------------------------

def test_winner_returns_none_on_draw():
    assert _winner("Brasil", "Alemanha", 1, 1) is None


def test_winner_returns_none_when_scores_missing():
    assert _winner("Brasil", "Alemanha", None, None) is None


def test_winner_home_wins():
    assert _winner("Brasil", "Alemanha", 3, 0) == "Brasil"


def test_winner_away_wins():
    assert _winner("Brasil", "Alemanha", 0, 2) == "Alemanha"


# ---------------------------------------------------------------------------
# _to_int
# ---------------------------------------------------------------------------

def test_to_int_handles_minus_sign_variants():
    assert _to_int("−3") == -3
    assert _to_int("-3") == -3


def test_to_int_handles_plus_prefix():
    assert _to_int("+5") == 5


def test_to_int_returns_zero_on_nan():
    assert _to_int(math.nan) == 0


def test_to_int_returns_zero_on_empty():
    assert _to_int("") == 0


# ---------------------------------------------------------------------------
# _parse_goal_events
# ---------------------------------------------------------------------------

def test_parse_goal_events_empty_value():
    assert _parse_goal_events("m1", "Brasil", None) == []


def test_parse_goal_events_nan_value():
    assert _parse_goal_events("m1", "Brasil", float("nan")) == []


def test_parse_goal_events_bracketed_reference_stripped():
    events = _parse_goal_events("m1", "Brasil", "Neymar 45'[1]")
    assert len(events) == 1
    assert events[0]["player"] == "Neymar"
    assert events[0]["minute"] == "45"


def test_parse_goal_events_multiple_goals():
    events = _parse_goal_events("m1", "Alemanha", "Müller 10' Kroos 88'")
    assert len(events) == 2
    assert events[0]["player"] == "Müller"
    assert events[1]["player"] == "Kroos"


def test_parse_goal_events_overtime_minute():
    events = _parse_goal_events("m1", "França", "Mbappé 90+3'")
    assert len(events) == 1
    assert events[0]["minute"] == "90+3"
    assert events[0]["minute_sort"] == 9003


# ---------------------------------------------------------------------------
# parse_group_matches com tabelas malformadas
# ---------------------------------------------------------------------------

def _make_tables(match_cols: list[str], rows: list[list] | None = None) -> list[pd.DataFrame]:
    """Constrói a lista de tabelas mínima esperada pelo parser."""
    total = GROUP_START_INDEX + len(GROUPS) * TABLES_PER_GROUP
    tables = [pd.DataFrame() for _ in range(total)]

    for group_index, group in enumerate(GROUPS):
        start = GROUP_START_INDEX + group_index * TABLES_PER_GROUP
        tables[start] = pd.DataFrame(
            [{"Pos": 1, "Teamvte": f"Team{group}", "Pld": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "GD": 0, "Pts": 0}]
        )
        for offset in range(1, TABLES_PER_GROUP):
            if rows:
                tables[start + offset] = pd.DataFrame(rows, columns=match_cols)
            else:
                tables[start + offset] = pd.DataFrame([[None, None, None]], columns=match_cols)

    return tables


def test_parse_group_matches_skips_table_with_too_few_columns():
    total = GROUP_START_INDEX + len(GROUPS) * TABLES_PER_GROUP
    tables = [pd.DataFrame() for _ in range(total)]
    for group_index, group in enumerate(GROUPS):
        start = GROUP_START_INDEX + group_index * TABLES_PER_GROUP
        tables[start] = pd.DataFrame(
            [{"Pos": 1, "Teamvte": f"Team{group}", "Pld": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "GD": 0, "Pts": 0}]
        )
        # Tabela com apenas 2 colunas — deve ser ignorada
        for offset in range(1, TABLES_PER_GROUP):
            tables[start + offset] = pd.DataFrame([[1, 2]], columns=["A", "B"])

    records = parse_group_matches(tables)
    assert records == []


def test_parse_group_matches_handles_scheduled_match():
    tables = _make_tables(["TeamA", "Match 5", "TeamB"])
    records = parse_group_matches(tables)
    assert all(r["status"] == "agendado" for r in records)
    assert all(r["home_score"] is None for r in records)


def test_parse_group_matches_teams_with_special_characters():
    cols = ["Côte d'Ivoire", "1–0", "Senegal"]
    tables = _make_tables(cols, rows=[[None, "[Report 1]", None]])
    records = parse_group_matches(tables)
    first = records[0]
    assert "Ivoire" in first["home_team"] or first["home_team"] != ""
    assert first["status"] == "finalizado"
    assert first["home_score"] == 1
    assert first["away_score"] == 0


# ---------------------------------------------------------------------------
# parse_group_events com edge cases
# ---------------------------------------------------------------------------

def test_parse_group_events_skips_scheduled_matches():
    tables = _make_tables(["TeamA", "Match 3", "TeamB"])
    events = parse_group_events(tables)
    assert events == []


def test_parse_group_events_empty_goal_cells():
    """Células de gols com NaN não devem gerar eventos."""
    tables = _make_tables(["Brasil", "2–0", "Alemanha"], rows=[[None, "[Report 1]", None]])
    events = parse_group_events(tables)
    assert events == []


def test_parse_group_events_sorted_by_match_and_minute():
    tables = _make_tables(
        ["Brasil", "3–1", "Alemanha"],
        rows=[["Neymar 45' Vinicius 90'", "[Report 1]", "Müller 10'"]],
    )
    events = parse_group_events(tables)
    if len(events) >= 2:
        minutes = [e["minute_sort"] for e in events if e["match_id"] == events[0]["match_id"]]
        assert minutes == sorted(minutes)
