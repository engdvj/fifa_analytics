from __future__ import annotations

import time
from datetime import date
from typing import Any

import pandas as pd
import requests

from fifa_analytics.transforms.team_names import traduzir_selecao
from fifa_analytics.utils.time import utc_now_iso


_BASE_URL = "https://webws.365scores.com/web"
_COMPETITION_ID = 5930  # FIFA World Cup 2026
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125",
    "Origin": "https://www.365scores.com",
    "Referer": "https://www.365scores.com/",
}

# stat type id → coluna canônica
_STAT_TYPE_MAP: dict[int, str] = {
    3: "shots",
    4: "shots_on_target",
    5: "shots_off_target",
    9: "offsides",
    19: "accurate_passes",
    20: "long_passes_completed",
    23: "saves",
    26: "assists",
    27: "goals",
    33: "penalties_scored",
    37: "was_fouled",
    42: "fouls",
    45: "touches",
    46: "key_passes",
    54: "dribbles_won",
    60: "was_dribbled_past",
    65: "error_led_to_shot",
    73: "possession_lost",
    78: "expected_assists",
    80: "passes_into_final_third",
    84: "final_third_possession_won",
}

# Stat types que têm numerador/denominador (ex: "32/36 (89%)") — pegar só o numerador
_RATIO_TYPES: set[int] = {19, 20, 54}

# Stat type para minutos jogados (valor como "90'" — remover apóstrofo)
_MINUTES_TYPE = 30

START_DATE = date(2026, 6, 11)
END_DATE = date(2026, 7, 19)

# Ranges de IDs dos jogos da Copa 2026 no 365Scores, descobertos por scan.
# Fase de grupos: cluster A (4627840–4627960)
# Jogos adicionais cluster B (4697690–4697950) — times como Sweden, South Korea,
# Canada, Australia, Iraq, France, Norway, Senegal ficaram fora do cluster A.
# Mata-mata: acrescentar novos ranges à medida que os IDs aparecerem.
_SCAN_RANGES: list[tuple[int, int]] = [
    (4627840, 4627960),
    (4697690, 4697950),
]


# ---------------------------------------------------------------------------
# Coleta
# ---------------------------------------------------------------------------

def discover_game_ids(
    extra_ranges: list[tuple[int, int]] | None = None,
    sleep_seconds: float = 0.1,
) -> list[int]:
    """Varre os ranges conhecidos e retorna IDs que pertencem à Copa 2026."""
    ranges = _SCAN_RANGES + (extra_ranges or [])
    found: list[int] = []
    for start, end in ranges:
        for gid in range(start, end + 1):
            try:
                detail = _get_json(
                    f"{_BASE_URL}/game/",
                    params={"gameId": gid, "langId": 17, "userCountryId": 21},
                )
                g = detail.get("game", {})
                if g.get("competitionId") == _COMPETITION_ID and g.get("sportId") == 1:
                    found.append(gid)
            except Exception:
                pass
            time.sleep(sleep_seconds)
    return sorted(found)


def fetch_game_detail(game_id: int | str) -> dict[str, Any]:
    return _get_json(
        f"{_BASE_URL}/game/",
        params={
            "gameId": int(game_id),
            "langId": 17,
            "sportId": 1,
            "timezoneName": "America/Sao_Paulo",
            "userCountryId": 21,
            "appTypeId": 5,
            "with": "stats,lineups,members",
        },
    )


def fetch_tournament(
    game_ids: list[int] | None = None,
    sleep_seconds: float = 0.3,
) -> dict[str, Any]:
    """Coleta detalhes de todos os jogos da Copa 2026.

    Se ``game_ids`` não for fornecido, executa ``discover_game_ids()`` primeiro.
    """
    if game_ids is None:
        game_ids = discover_game_ids(sleep_seconds=sleep_seconds)

    details: dict[int, Any] = {}
    for gid in game_ids:
        try:
            details[gid] = fetch_game_detail(gid)
        except Exception:
            pass
        time.sleep(sleep_seconds)

    return {"game_ids": game_ids, "details": details, "collected_at": utc_now_iso()}


# ---------------------------------------------------------------------------
# Normalização — team stats
# ---------------------------------------------------------------------------

def normalize_team_match_stats(payload: dict[str, Any]) -> pd.DataFrame:
    """Uma linha por (jogo, time). Stats agregadas a partir dos membros do lineup."""
    rows: list[dict[str, Any]] = []
    details = payload.get("details", {})

    for game_id_str, detail in details.items():
        g = detail.get("game", {})
        if not g:
            continue
        start_time = g.get("startTime", "")
        match_date = start_time[:10] if start_time else None
        group = g.get("groupName") or None

        for side, competitor in [
            ("home", g.get("homeCompetitor", {})),
            ("away", g.get("awayCompetitor", {})),
        ]:
            opp_side = "away" if side == "home" else "home"
            opp = g.get(f"{opp_side}Competitor", {})

            team_name = traduzir_selecao(competitor.get("name", ""))
            opp_name = traduzir_selecao(opp.get("name", ""))
            team_score = competitor.get("score")
            opp_score = opp.get("score")
            formation = competitor.get("lineups", {}).get("formation")

            stats = _agg_lineup_stats(competitor)

            rows.append(
                {
                    "source_game_id": int(game_id_str),
                    "match_date": match_date,
                    "group": group,
                    "team": team_name,
                    "opponent": opp_name,
                    "side": side,
                    "score_team": team_score,
                    "score_opponent": opp_score,
                    "formation": formation,
                    "source": "365scores",
                    "collected_at": payload.get("collected_at", utc_now_iso()),
                    **stats,
                }
            )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Normalização — player stats
# ---------------------------------------------------------------------------

def normalize_player_stats(payload: dict[str, Any]) -> pd.DataFrame:
    """Uma linha por (jogo, jogador). Inclui nome, posição, time, rating e stats."""
    rows: list[dict[str, Any]] = []
    details = payload.get("details", {})

    for game_id_str, detail in details.items():
        g = detail.get("game", {})
        if not g:
            continue
        start_time = g.get("startTime", "")
        match_date = start_time[:10] if start_time else None

        # Mapa id → nome (array g.members tem nomes; lineups.members têm stats).
        # Alguns membros podem vir sem "id" — ignora esses em vez de quebrar.
        id_to_name: dict[int, str] = {
            m["id"]: m.get("name", "")
            for m in g.get("members", [])
            if isinstance(m, dict) and "id" in m
        }

        for side, competitor in [
            ("home", g.get("homeCompetitor", {})),
            ("away", g.get("awayCompetitor", {})),
        ]:
            opp_side = "away" if side == "home" else "home"
            opp = g.get(f"{opp_side}Competitor", {})
            team_name = traduzir_selecao(competitor.get("name", ""))
            opp_name = traduzir_selecao(opp.get("name", ""))
            lineup_members = competitor.get("lineups", {}).get("members", [])

            for m in lineup_members:
                member_id = m.get("id")
                status = m.get("statusText", "")
                # Reservas que não entraram não têm stats
                if not m.get("hasStats"):
                    continue

                player_name = id_to_name.get(member_id, "")
                position = m.get("position", {}).get("name", "")
                formation_pos = m.get("formation", {}).get("name", "")
                rating = m.get("ranking")
                if rating == -1:
                    rating = None

                stats = _parse_player_stats(m.get("stats", []))

                rows.append(
                    {
                        "source_game_id": int(game_id_str),
                        "match_date": match_date,
                        "team": team_name,
                        "opponent": opp_name,
                        "side": side,
                        "player_id_365": member_id,
                        "player_name": player_name,
                        "position": position,
                        "formation_position": formation_pos,
                        "status": status,
                        "rating": rating,
                        "source": "365scores",
                        "collected_at": payload.get("collected_at", utc_now_iso()),
                        **stats,
                    }
                )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _agg_lineup_stats(competitor: dict[str, Any]) -> dict[str, float]:
    """Soma as stats numéricas de todos os membros do lineup para o time."""
    totals: dict[str, float] = {}
    for m in competitor.get("lineups", {}).get("members", []):
        for stat_name, val in _parse_player_stats(m.get("stats", [])).items():
            totals[stat_name] = totals.get(stat_name, 0.0) + val
    return totals


def _parse_player_stats(stats_list: list[dict[str, Any]]) -> dict[str, float]:
    """Converte a lista de stat objects num dict coluna → valor numérico."""
    result: dict[str, float] = {}
    for s in stats_list:
        stat_type = s.get("type")
        raw = str(s.get("value", "0"))

        # Minutos: tipo 30, valor "90'" → 90
        if stat_type == _MINUTES_TYPE:
            try:
                result["minutes"] = float(raw.replace("'", "").strip())
            except ValueError:
                pass
            continue

        col = _STAT_TYPE_MAP.get(stat_type)
        if not col:
            continue

        # Ratios como "32/36 (89%)" → pegar só o numerador
        try:
            num = float(raw.split("/")[0].split("(")[0].strip())
        except (ValueError, AttributeError):
            continue
        result[col] = num
    return result


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()
