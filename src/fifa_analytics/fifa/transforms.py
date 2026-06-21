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
    """Extrai a descrição de um campo localizado.

    A v3 usa chaves capitalizadas ({Locale, Description}) nos endpoints
    estruturais e minúsculas ({locale, description}) no power ranking.
    """
    if isinstance(value, list) and value:
        first = value[0]
        return first.get("Description") or first.get("description")
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


# Posição numérica v3 → abreviação.
_POSITION = {0: "G", 1: "D", 2: "M", 3: "F"}
# Campo Card da v3 (Bookings): 1=yellow, 3=red_direct, 5=second_yellow.
_CARD_TYPE = {1: "yellow", 3: "red", 5: "second_yellow"}
# Campo Type dos gols: 0=normal, 1=own_goal, 2=penalty.
_GOAL_TYPE = {0: "normal", 1: "own_goal", 2: "penalty"}


def normalize_lineups(match_id: str, live: dict[str, Any]) -> pd.DataFrame:
    """live/football -> fact_lineups: uma linha por jogador por jogo.

    Na v3 os times ficam em HomeTeam/AwayTeam (não Home/Away). Cada time tem
    Players[] com Status (1=titular, 0=banco), LineupX/Y (pode ser None),
    Position (int), Captain (bool).
    """
    collected_at = utc_now_iso()
    rows = []
    for side, key in (("home", "HomeTeam"), ("away", "AwayTeam")):
        team = live.get(key) or {}
        id_team = str(team.get("IdTeam") or "")
        for p in team.get("Players") or []:
            rows.append(
                {
                    "match_id": match_id,
                    "team_side": side,
                    "id_team": id_team,
                    "id_player": str(p.get("IdPlayer") or ""),
                    "player_name": _loc(p.get("PlayerName") or p.get("ShortName")),
                    "shirt_number": p.get("ShirtNumber"),
                    "position": _POSITION.get(p.get("Position"), str(p.get("Position") or "")),
                    "is_starter": int(p.get("Status") or 0) == 1,
                    "captain": bool(p.get("Captain")),
                    "lineup_x": p.get("LineupX"),
                    "lineup_y": p.get("LineupY"),
                    "collected_at": collected_at,
                }
            )
    return pd.DataFrame(rows)


def normalize_match_events(match_id: str, live: dict[str, Any]) -> pd.DataFrame:
    """live/football -> fact_events: gols, cartões e substituições.

    Na v3 os eventos ficam dentro de cada time (HomeTeam.Goals, .Bookings,
    .Substitutions), não no nível raiz. Minute é string "N'" ou "N+M'".
    Player name não vem nos eventos de gol/cartão — apenas IdPlayer.
    Para subs vem PlayerOffName/PlayerOnName (localizados).
    """
    collected_at = utc_now_iso()
    rows = []

    for side, key in (("home", "HomeTeam"), ("away", "AwayTeam")):
        team = live.get(key) or {}
        id_team = str(team.get("IdTeam") or "")

        for goal in team.get("Goals") or []:
            rows.append(
                {
                    "match_id": match_id,
                    "event_type": "goal",
                    "minute": goal.get("Minute"),
                    "id_team": str(goal.get("IdTeam") or id_team),
                    "id_player": str(goal.get("IdPlayer") or ""),
                    "player_name": None,
                    "detail": _GOAL_TYPE.get(goal.get("Type"), "normal"),
                    "id_assist": str(goal.get("IdAssistPlayer") or ""),
                    "id_player2": None,
                    "player2_name": None,
                    "collected_at": collected_at,
                }
            )

        for booking in team.get("Bookings") or []:
            rows.append(
                {
                    "match_id": match_id,
                    "event_type": "card",
                    "minute": booking.get("Minute"),
                    "id_team": str(booking.get("IdTeam") or id_team),
                    "id_player": str(booking.get("IdPlayer") or ""),
                    "player_name": None,
                    "detail": _CARD_TYPE.get(booking.get("Card"), "yellow"),
                    "id_assist": None,
                    "id_player2": None,
                    "player2_name": None,
                    "collected_at": collected_at,
                }
            )

        for sub in team.get("Substitutions") or []:
            rows.append(
                {
                    "match_id": match_id,
                    "event_type": "substitution",
                    "minute": sub.get("Minute"),
                    "id_team": str(sub.get("IdTeam") or id_team),
                    "id_player": str(sub.get("IdPlayerOff") or ""),
                    "player_name": _loc(sub.get("PlayerOffName")),
                    "detail": "injury" if sub.get("Reason") == 1 else "tactical",
                    "id_assist": None,
                    "id_player2": str(sub.get("IdPlayerOn") or ""),
                    "player2_name": _loc(sub.get("PlayerOnName")),
                    "collected_at": collected_at,
                }
            )

    return pd.DataFrame(rows)


def normalize_match_player_stats(
    match_id: str, id_ifes: str, payload: dict[str, Any]
) -> pd.DataFrame:
    """stats/match/{ifes}/players.json -> fact long: uma linha por (jogador, métrica).

    Mesmo formato do team stats: dict idPlayer -> [[nome, valor, oficial], ...].
    """
    collected_at = utc_now_iso()
    rows = []
    for id_player, metrics in payload.items():
        for metric in metrics:
            name, value = metric[0], metric[1]
            is_official = metric[2] if len(metric) > 2 else None
            rows.append(
                {
                    "match_id": match_id,
                    "id_ifes": str(id_ifes),
                    "id_player": str(id_player),
                    "metric": name,
                    "value": value,
                    "is_official": is_official,
                    "collected_at": collected_at,
                }
            )
    return pd.DataFrame(rows)


def normalize_power_ranking_season(payload: dict[str, Any]) -> pd.DataFrame:
    """powerranking/season/{id}.json -> fact_power_ranking.

    Estrutura real da v3:
    - outfieldPlayers / goalkeepers: lista com campos playerId, teamId,
      playerName (localizado), 3 scores, 3 ranks, 3 rankChanges, 3 rankWithinTeam.
    - tournamentHistory no ROOT (não por jogador): [{playerId, history:[{round,...}]}].
    - tournament_history gravado como JSON string (lista de rodadas por jogador).
    """
    import json

    collected_at = utc_now_iso()

    # Mapeia playerId -> history (lista de rodadas) a partir do root
    th_by_player: dict[str, list] = {
        str(item["playerId"]): item.get("history") or []
        for item in payload.get("tournamentHistory") or []
    }

    rows = []
    for p in payload.get("outfieldPlayers") or []:
        player_id = str(p.get("playerId") or "")
        rows.append(
            {
                "id_player": player_id,
                "player_name": _loc(p.get("playerName")),
                "id_team": str(p.get("teamId") or ""),
                "team_name": traduzir_selecao(_loc(p.get("teamName"))),
                "player_type": "outfield",
                "attacking_score": p.get("attackingScore"),
                "attacking_rank": p.get("attackingRank"),
                "attacking_rank_change": p.get("attackingRankChange"),
                "attacking_rank_in_team": p.get("attackingRankWithinTeam"),
                "defensive_score": p.get("defensiveScore"),
                "defensive_rank": p.get("defensiveRank"),
                "defensive_rank_change": p.get("defensiveRankChange"),
                "defensive_rank_in_team": p.get("defensiveRankWithinTeam"),
                "creativity_score": p.get("creativityScore"),
                "creativity_rank": p.get("creativityRank"),
                "creativity_rank_change": p.get("creativityRankChange"),
                "creativity_rank_in_team": p.get("creativityRankWithinTeam"),
                "tournament_history": json.dumps(th_by_player.get(player_id, [])),
                "collected_at": collected_at,
            }
        )

    # Goleiros têm esquema próprio: inPossession (≈attacking) e defendingTheGoal (≈defensive).
    for p in payload.get("goalkeepers") or []:
        player_id = str(p.get("playerId") or "")
        rows.append(
            {
                "id_player": player_id,
                "player_name": _loc(p.get("playerName")),
                "id_team": str(p.get("teamId") or ""),
                "team_name": traduzir_selecao(_loc(p.get("teamName"))),
                "player_type": "goalkeeper",
                # inPossession → attacking slot (distribuição/saída de bola)
                "attacking_score": p.get("inPossessionScore"),
                "attacking_rank": p.get("inPossessionRank"),
                "attacking_rank_change": p.get("inPossessionRankChange"),
                "attacking_rank_in_team": None,
                # defendingTheGoal → defensive slot
                "defensive_score": p.get("defendingTheGoalScore"),
                "defensive_rank": p.get("defendingTheGoalRank"),
                "defensive_rank_change": p.get("defendingTheGoalRankChange"),
                "defensive_rank_in_team": None,
                # goleiros não têm creativity
                "creativity_score": None,
                "creativity_rank": None,
                "creativity_rank_change": None,
                "creativity_rank_in_team": None,
                "tournament_history": json.dumps(th_by_player.get(player_id, [])),
                "collected_at": collected_at,
            }
        )

    return pd.DataFrame(rows)


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
