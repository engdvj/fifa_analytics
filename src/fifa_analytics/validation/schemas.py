from __future__ import annotations

import pandas as pd

from fifa_analytics.config import load_schema


def validate_required_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str] | None = None,
    schema: str | None = None,
) -> dict[str, object]:
    """Valida colunas obrigatórias de um DataFrame.

    Aceita lista explícita via required_columns ou nome de schema YAML via schema
    (ex: schema="matches.yaml"). Se ambos forem passados, a lista tem precedência.
    """
    if required_columns is None:
        if schema is None:
            raise ValueError("Informe required_columns ou schema.")
        required_columns = load_schema(schema).get("required_columns", [])

    missing = [col for col in required_columns if col not in dataframe.columns]
    return {
        "status": "ok" if not missing else "ausente",
        "missing_columns": missing,
    }
