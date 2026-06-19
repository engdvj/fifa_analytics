"""raw JSON da FIFA -> DataFrames (silver/gold).

Sem dependência de rede: recebe os dicts crus do client e devolve DataFrames
com schema estável. Toda string localizada da FIFA vem como lista
[{Locale, Description}] -> usar `_loc()`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from fifa_analytics.transforms.team_names import traduzir_selecao
from fifa_analytics.utils.time import utc_now_iso

# MatchStatus da v3: 0 = finalizado, 1 = agendado (live tem outros códigos).
_STATUS = {0: "finalizado", 1: "agendado"}


def _loc(value: Any) -> str | None:
    """Extrai a descrição de um campo localizado [{Locale, Description}, ...]."""
    if isinstance(value, list) and value:
        return value[0].get("Description")
    if isinstance(value, str):
        return value
    return None


def _team_name(team: dict[str, Any] | None) -> str | None:
    if not team:
        return None
    return _loc(team.get("TeamName") or team.get("Name"))


def make_match_id(match_number: Any) -> str:
    """ID canônico copa_2026_jogo_NNN a partir do MatchNumber (1..104)."""
    return f"copa_2026_jogo_{int(match_number):03d}"


def normalize_matches(results: list[dict[str, Any]]) -> pd.DataFrame:
    """calendar/matches -> dim_match (uma linha por jogo)."""
    collected_at = utc_now_iso()
    rows = []
    for m in results:
        status = _STATUS.get(m.get("MatchStatus"), "agendado")
        home = m.get("Home") or {}
        away = m.get("Away") or {}
        home_score = m.get("HomeTeamScore")
        away_score = m.get("AwayTeamScore")
        if status == "agendado":
            home_score = away_score = None

        rows.append(
            {
                "match_id": make_match_id(m.get("MatchNumber")),
                "match_number": int(m["MatchNumber"]),
                "id_match": str(m.get("IdMatch") or ""),
                "id_ifes": str((m.get("Properties") or {}).get("IdIFES") or ""),
                "id_stage": str(m.get("IdStage") or ""),
                "id_group": str(m.get("IdGroup") or ""),
                "home_team": traduzir_selecao(_team_name(home)),
                "away_team": traduzir_selecao(_team_name(away)),
                "home_team_code": home.get("IdCountry") or home.get("Abbreviation"),
                "away_team_code": away.get("IdCountry") or away.get("Abbreviation"),
                "id_team_home": str(home.get("IdTeam") or ""),
                "id_team_away": str(away.get("IdTeam") or ""),
                "date_utc": m.get("Date"),
                "date_local": m.get("LocalDate"),
                "group": _loc(m.get("GroupName")),
                "stage": _loc(m.get("StageName")),
                "stadium": _loc((m.get("Stadium") or {}).get("Name")),
                "status": status,
                "home_score": home_score,
                "away_score": away_score,
                "home_penalty": m.get("HomeTeamPenaltyScore"),
                "away_penalty": m.get("AwayTeamPenaltyScore"),
                "attendance": m.get("Attendance"),
                "main_source": "fifa",
                "collected_at": collected_at,
            }
        )

    df = pd.DataFrame(rows)
    return df.sort_values("match_number").reset_index(drop=True)


def normalize_match_team_stats(
    match_id: str, id_ifes: str, payload: dict[str, Any]
) -> pd.DataFrame:
    """stats/match/{ifes}/teams.json -> fact long: uma linha por (time, métrica).

    Formato longo (não wide) porque são 142 métricas e o conjunto pode variar
    entre jogos — long evita schema explodindo e colunas esparsas.
    """
    collected_at = utc_now_iso()
    rows = []
    for id_team, metrics in payload.items():
        for metric in metrics:
            name, value = metric[0], metric[1]
            is_official = metric[2] if len(metric) > 2 else None
            rows.append(
                {
                    "match_id": match_id,
                    "id_ifes": str(id_ifes),
                    "id_team": str(id_team),
                    "metric": name,
                    "value": value,
                    "is_official": is_official,
                    "collected_at": collected_at,
                }
            )
    return pd.DataFrame(rows)
