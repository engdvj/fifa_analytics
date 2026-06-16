import pandas as pd


def validate_required_columns(dataframe: pd.DataFrame, required_columns: list[str]) -> dict[str, object]:
    missing = [column for column in required_columns if column not in dataframe.columns]
    return {
        "status": "ok" if not missing else "ausente",
        "missing_columns": missing,
    }
