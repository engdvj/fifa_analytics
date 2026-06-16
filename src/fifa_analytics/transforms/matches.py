import re
import unicodedata
from typing import Any

import pandas as pd

from fifa_analytics.transforms.team_names import traduzir_selecao


def make_match_id(home_team: str, away_team: str, date: str) -> str:
    raw = f"{home_team}_{away_team}_{date}"
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    normalized = raw.lower().replace("-", "_")
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def normalize_matches(records: list[dict[str, Any]], source: str) -> pd.DataFrame:
    rows = []
    for record in records:
        home_team = traduzir_selecao(record.get("home_team") or record.get("homeTeam"))
        away_team = traduzir_selecao(record.get("away_team") or record.get("awayTeam"))
        date = record.get("date") or record.get("match_date")
        match_id = record.get("match_id") or make_match_id(str(home_team), str(away_team), str(date))
        winner = traduzir_selecao(record.get("winner"))
        rows.append(
            {
                "match_id": match_id,
                "source_match_id": record.get("source_match_id") or record.get("id"),
                "fifa_match_id": record.get("fifa_match_id"),
                "home_team": home_team,
                "away_team": away_team,
                "home_team_code": record.get("home_team_code"),
                "away_team_code": record.get("away_team_code"),
                "date": date,
                "kickoff_time": record.get("kickoff_time"),
                "timezone": record.get("timezone"),
                "group": record.get("group"),
                "stage": record.get("stage"),
                "round": record.get("round"),
                "stadium": record.get("stadium"),
                "city": record.get("city"),
                "country": record.get("country"),
                "status": record.get("status", "desconhecido"),
                "home_score": record.get("home_score"),
                "away_score": record.get("away_score"),
                "winner": winner,
                "main_source": source,
                "official_reference": record.get("official_reference"),
                "last_updated_at": record.get("last_updated_at"),
            }
        )
    return pd.DataFrame(rows)
