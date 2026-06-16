import pandas as pd

from fifa_analytics.validation.match_validation import compare_match_records
from fifa_analytics.validation.schemas import validate_required_columns


def test_compare_match_records_ok_when_values_match():
    primary = {"home_score": 2, "away_score": 0, "status": "finalizado", "stadium": "México City Stadium"}
    reference = {"home_score": 2, "away_score": 0, "status": "finalizado", "stadium": "México City Stadium"}

    result = compare_match_records(primary, reference)

    assert result["status"] == "ok"


def test_compare_match_records_warns_on_score_difference():
    primary = {"home_score": 2, "away_score": 0, "status": "finalizado", "stadium": "México City Stadium"}
    reference = {"home_score": 1, "away_score": 0, "status": "finalizado", "stadium": "México City Stadium"}

    result = compare_match_records(primary, reference)

    assert result["status"] == "aviso"


def test_validate_required_columns_reports_missing_columns():
    dataframe = pd.DataFrame([{"match_id": "example"}])

    result = validate_required_columns(dataframe, ["match_id", "home_team"])

    assert result["status"] == "ausente"
    assert result["missing_columns"] == ["home_team"]
