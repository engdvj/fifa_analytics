import pandas as pd


def teams_from_matches(matches: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, match in matches.iterrows():
        rows.append({"team_name": match["home_team"], "team_code": match.get("home_team_code"), "group": match.get("group")})
        rows.append({"team_name": match["away_team"], "team_code": match.get("away_team_code"), "group": match.get("group")})
    teams = pd.DataFrame(rows).drop_duplicates(subset=["team_name"]).reset_index(drop=True)
    teams.insert(0, "team_id", teams["team_name"].str.lower().str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_"))
    return teams

