import pandas as pd
import pytest

from fifa_analytics.validation.schemas import validate_required_columns


def test_validate_ok_with_all_required_columns():
    df = pd.DataFrame([{"match_id": "x", "home_team": "Brasil", "away_team": "Alemanha", "date": "2026-06-11", "status": "finalizado"}])
    result = validate_required_columns(df, schema="matches.yaml")
    assert result["status"] == "ok"
    assert result["missing_columns"] == []


def test_validate_ausente_with_missing_columns():
    df = pd.DataFrame([{"match_id": "x"}])
    result = validate_required_columns(df, schema="matches.yaml")
    assert result["status"] == "ausente"
    assert "home_team" in result["missing_columns"]
    assert "away_team" in result["missing_columns"]


def test_validate_explicit_list_takes_precedence_over_schema():
    df = pd.DataFrame([{"match_id": "x"}])
    result = validate_required_columns(df, required_columns=["match_id"], schema="matches.yaml")
    assert result["status"] == "ok"


def test_validate_raises_without_columns_or_schema():
    df = pd.DataFrame([{"match_id": "x"}])
    with pytest.raises(ValueError):
        validate_required_columns(df)


def test_validate_events_schema():
    df = pd.DataFrame([{"match_id": "x", "event_type": "gol", "minute": "9"}])
    result = validate_required_columns(df, schema="events.yaml")
    assert result["status"] == "ok"


def test_validate_events_schema_missing():
    df = pd.DataFrame([{"match_id": "x"}])
    result = validate_required_columns(df, schema="events.yaml")
    assert result["status"] == "ausente"
    assert "event_type" in result["missing_columns"]
    assert "minute" in result["missing_columns"]
