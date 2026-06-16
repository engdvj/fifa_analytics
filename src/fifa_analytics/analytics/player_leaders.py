import pandas as pd


def top_players(player_stats: pd.DataFrame, metric: str, limit: int = 10) -> pd.DataFrame:
    if metric not in player_stats.columns:
        return pd.DataFrame()
    return player_stats.sort_values(metric, ascending=False).head(limit).reset_index(drop=True)

