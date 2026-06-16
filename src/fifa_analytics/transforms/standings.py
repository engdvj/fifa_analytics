import pandas as pd


def calculate_group_standings(matches: pd.DataFrame) -> pd.DataFrame:
    rows: dict[tuple[str | None, str], dict[str, object]] = {}

    for _, match in matches.iterrows():
        group = match.get("group")
        for team in [match.get("home_team"), match.get("away_team")]:
            if pd.isna(team):
                continue
            rows.setdefault(
                (group, team),
                {
                    "group": group,
                    "team": team,
                    "played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "goal_difference": 0,
                    "points": 0,
                },
            )

    finished = matches[matches["status"].isin(["finalizado", "consolidado"])].copy()

    for _, match in finished.iterrows():
        if pd.isna(match.get("home_score")) or pd.isna(match.get("away_score")):
            continue

        group = match.get("group")
        home_team = match["home_team"]
        away_team = match["away_team"]
        home_score = int(match["home_score"])
        away_score = int(match["away_score"])

        home = rows[(group, home_team)]
        away = rows[(group, away_team)]

        home["played"] += 1
        away["played"] += 1
        home["goals_for"] += home_score
        home["goals_against"] += away_score
        away["goals_for"] += away_score
        away["goals_against"] += home_score

        if home_score > away_score:
            home["wins"] += 1
            home["points"] += 3
            away["losses"] += 1
        elif home_score < away_score:
            away["wins"] += 1
            away["points"] += 3
            home["losses"] += 1
        else:
            home["draws"] += 1
            away["draws"] += 1
            home["points"] += 1
            away["points"] += 1

        home["goal_difference"] = home["goals_for"] - home["goals_against"]
        away["goal_difference"] = away["goals_for"] - away["goals_against"]

    if not rows:
        return pd.DataFrame(
            columns=[
                "group",
                "team",
                "played",
                "wins",
                "draws",
                "losses",
                "goals_for",
                "goals_against",
                "goal_difference",
                "points",
            ]
        )

    return (
        pd.DataFrame(rows.values())
        .sort_values(["group", "points", "goal_difference", "goals_for"], ascending=[True, False, False, False])
        .reset_index(drop=True)
    )
