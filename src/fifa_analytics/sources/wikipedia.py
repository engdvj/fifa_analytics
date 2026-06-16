from __future__ import annotations

import re
from io import StringIO
from typing import Any

import pandas as pd
import requests

from fifa_analytics.config import load_config
from fifa_analytics.transforms.matches import make_match_id
from fifa_analytics.transforms.team_names import traduzir_selecao


_FALLBACK_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup"


def _wikipedia_url() -> str:
    try:
        return load_config("sources.yaml")["sources"]["wikipedia"]["base_url"] or _FALLBACK_WIKIPEDIA_URL
    except Exception:
        return _FALLBACK_WIKIPEDIA_URL
GROUPS = list("ABCDEFGHIJKL")
GROUP_START_INDEX = 11
TABLES_PER_GROUP = 7
SCORE_PATTERN = re.compile(r"^(\d+)[–-](\d+)$")
GOAL_PATTERN = re.compile(r"([A-Za-zÀ-ÿØ-öø-ÿĀ-ž' .-]+?)\s+(\d{1,3}(?:\+\d+)?)['’]")


def fetch_html(url: str | None = None) -> str:
    url = url or _wikipedia_url()
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 fifa_analytics/0.1"},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def fetch_tables(html: str | None = None) -> list[pd.DataFrame]:
    html = html if html is not None else fetch_html()
    return pd.read_html(StringIO(html))


def clean_team_name(value: Any) -> str:
    text = str(value)
    text = re.sub(r"\[[^\]]+\]", "", text)
    text = re.sub(r"\s*\([^)]*\)", "", text)
    text = text.replace("\xa0", " ")
    cleaned = re.sub(r"\s+", " ", text).strip()
    return traduzir_selecao(cleaned) or cleaned


def parse_score(value: Any) -> tuple[int | None, int | None, str]:
    text = str(value).strip()
    match = SCORE_PATTERN.match(text)
    if not match:
        return None, None, "agendado"
    return int(match.group(1)), int(match.group(2)), "finalizado"


def parse_match_number(score_or_label: Any, table: pd.DataFrame) -> str | None:
    label = str(score_or_label)
    if label.lower().startswith("match"):
        return label

    values = " ".join(str(value) for value in table.to_numpy().ravel())
    report = re.search(r"Report\s+(\d+)", values)
    if report:
        return f"Match {report.group(1)}"
    return None


def parse_group_matches(tables: list[pd.DataFrame]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for group_index, group in enumerate(GROUPS):
        start = GROUP_START_INDEX + group_index * TABLES_PER_GROUP
        for table_index in range(start + 1, start + TABLES_PER_GROUP):
            table = tables[table_index]
            if len(table.columns) < 3:
                continue

            home_team = clean_team_name(table.columns[0])
            score_or_label = str(table.columns[1]).strip()
            away_team = clean_team_name(table.columns[2])
            home_score, away_score, status = parse_score(score_or_label)
            source_match_id = parse_match_number(score_or_label, table)
            match_id_seed = source_match_id.lower().replace(" ", "_") if source_match_id else "fase_de_grupos"
            match_id = make_match_id(home_team, away_team, f"2026_{match_id_seed}")

            records.append(
                {
                    "match_id": match_id,
                    "source_match_id": source_match_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "date": None,
                    "group": group,
                    "stage": "fase_de_grupos",
                    "status": status,
                    "home_score": home_score,
                    "away_score": away_score,
                    "winner": _winner(home_team, away_team, home_score, away_score),
                    "main_source": "wikipedia",
                    "official_reference": _wikipedia_url(),
                }
            )
    return records


def parse_group_events(tables: list[pd.DataFrame]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for group_index, group in enumerate(GROUPS):
        start = GROUP_START_INDEX + group_index * TABLES_PER_GROUP
        for table_index in range(start + 1, start + TABLES_PER_GROUP):
            table = tables[table_index]
            if len(table.columns) < 3:
                continue

            home_team = clean_team_name(table.columns[0])
            score_or_label = str(table.columns[1]).strip()
            away_team = clean_team_name(table.columns[2])
            _, _, status = parse_score(score_or_label)
            if status != "finalizado" or table.empty:
                continue

            source_match_id = parse_match_number(score_or_label, table)
            match_id_seed = source_match_id.lower().replace(" ", "_") if source_match_id else "fase_de_grupos"
            match_id = make_match_id(home_team, away_team, f"2026_{match_id_seed}")

            home_text = table.iloc[0, 0] if table.shape[1] >= 1 else None
            away_text = table.iloc[0, 2] if table.shape[1] >= 3 else None
            records.extend(_parse_goal_events(match_id, home_team, home_text))
            records.extend(_parse_goal_events(match_id, away_team, away_text))

    return sorted(records, key=lambda event: (event["match_id"], event["minute_sort"], event["team"]))


def parse_group_standings(tables: list[pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for group_index, group in enumerate(GROUPS):
        table = tables[GROUP_START_INDEX + group_index * TABLES_PER_GROUP]
        for _, row in table.iterrows():
            rows.append(
                {
                    "group": group,
                    "team": clean_team_name(row["Teamvte"]),
                    "played": _to_int(row["Pld"]),
                    "wins": _to_int(row["W"]),
                    "draws": _to_int(row["D"]),
                    "losses": _to_int(row["L"]),
                    "goals_for": _to_int(row["GF"]),
                    "goals_against": _to_int(row["GA"]),
                    "goal_difference": _to_int(str(row["GD"]).replace("−", "-").replace("+", "")),
                    "points": _to_int(row["Pts"]),
                    "source": "wikipedia",
                }
            )
    return pd.DataFrame(rows)


def fetch_matches() -> list[dict[str, Any]]:
    return parse_group_matches(fetch_tables())


def fetch_standings() -> pd.DataFrame:
    return parse_group_standings(fetch_tables())


def fetch_events() -> list[dict[str, Any]]:
    return parse_group_events(fetch_tables())


def _winner(home_team: str, away_team: str, home_score: int | None, away_score: int | None) -> str | None:
    if home_score is None or away_score is None or home_score == away_score:
        return None
    return home_team if home_score > away_score else away_team


def _to_int(value: Any) -> int:
    text = str(value)
    text = text.replace("−", "-").replace("+", "")
    match = re.search(r"-?\d+", text)
    return int(match.group(0)) if match else 0


def _parse_goal_events(match_id: str, team: str, value: Any) -> list[dict[str, Any]]:
    if value is None or pd.isna(value):
        return []

    text = re.sub(r"\[[^\]]+\]", "", str(value)).replace("\xa0", " ").strip()
    if not text or text.lower() == "nan":
        return []

    events = []
    for index, match in enumerate(GOAL_PATTERN.finditer(text), start=1):
        player = re.sub(r"\s+", " ", match.group(1)).strip(" ,;'’")
        minute = match.group(2)
        events.append(
            {
                "match_id": match_id,
                "event_id": f"{match_id}_gol_{team}_{index}_{minute}".lower().replace(" ", "_"),
                "event_type": "gol",
                "minute": minute,
                "minute_sort": _minute_sort(minute),
                "team": team,
                "player": player,
                "description": f"Gol de {player} ({team})",
                "source": "wikipedia",
            }
        )
    return events


def _minute_sort(minute: str) -> int:
    if "+" not in minute:
        return int(minute) * 100
    base, extra = minute.split("+", 1)
    return int(base) * 100 + int(extra)
