import pandas as pd


def build_match_summary(match: pd.Series | dict) -> dict[str, str]:
    home_team = match.get("home_team")
    away_team = match.get("away_team")
    home_score = match.get("home_score")
    away_score = match.get("away_score")
    status = match.get("status", "desconhecido")
    return {
        "title": f"{home_team} x {away_team}",
        "scoreline": f"{home_score} x {away_score}" if home_score is not None and away_score is not None else "Placar indisponivel",
        "status": status,
    }
