import pandas as pd


def compare_standings(calculated: pd.DataFrame, external: pd.DataFrame) -> dict[str, str | list[dict[str, str | None]]]:
    if external.empty:
        return {"status": "ausente", "message": "Classificacao externa indisponivel."}

    key_columns = ["group", "team"]
    metric_columns = ["played", "wins", "draws", "losses", "goals_for", "goals_against", "goal_difference", "points"]
    merged = calculated.merge(external, on=key_columns, how="outer", suffixes=("_calculated", "_external"), indicator=True)
    differences = []

    for _, row in merged.iterrows():
        if row["_merge"] != "both":
            differences.append({"group": row.get("group"), "team": row.get("team"), "field": "_merge"})
            continue
        for metric in metric_columns:
            if row.get(f"{metric}_calculated") != row.get(f"{metric}_external"):
                differences.append({"group": row["group"], "team": row["team"], "field": metric})

    return {"status": "ok" if not differences else "aviso", "differences": differences}
