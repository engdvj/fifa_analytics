from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any

import pandas as pd
import requests

from fifa_analytics.config import load_config
from fifa_analytics.transforms.matches import make_match_id
from fifa_analytics.transforms.team_names import traduzir_selecao
from fifa_analytics.utils.time import utc_now_iso


_FALLBACK_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"


def _base_url() -> str:
    try:
        return load_config("sources.yaml")["sources"]["espn"]["base_url"] or _FALLBACK_BASE_URL
    except Exception:
        return _FALLBACK_BASE_URL

START_DATE = date(2026, 6, 11)
END_DATE = date(2026, 7, 19)
TEAM_STAT_COLUMNS = {
    "possession": "possessionPct",
    "shots": "totalShots",
    "shots_on_target": "shotsOnTarget",
    "blocked_shots": "blockedShots",
    "passes": "totalPasses",
    "accurate_passes": "accuratePasses",
    "pass_accuracy": "passPct",
    "corners": "wonCorners",
    "fouls": "foulsCommitted",
    "offsides": "offsides",
    "saves": "saves",
    "yellow_cards": "yellowCards",
    "red_cards": "redCards",
    "crosses": "totalCrosses",
    "accurate_crosses": "accurateCrosses",
    "tackles": "totalTackles",
    "effective_tackles": "effectiveTackles",
    "interceptions": "interceptions",
    "clearances": "totalClearance",
}
PLAYER_STAT_COLUMNS = {
    "appearances": "appearances",
    "goals": "totalGoals",
    "assists": "goalAssists",
    "shots": "totalShots",
    "shots_on_target": "shotsOnTarget",
    "saves": "saves",
    "goals_conceded": "goalsConceded",
    "shots_faced": "shotsFaced",
    "yellow_cards": "yellowCards",
    "red_cards": "redCards",
    "fouls_committed": "foulsCommitted",
    "fouls_drawn": "foulsSuffered",
    "offsides": "offsides",
    "own_goals": "ownGoals",
}


def fetch_scoreboard(match_date: date) -> dict[str, Any]:
    return _get_json(f"{_base_url()}/scoreboard", params={"dates": match_date.strftime("%Y%m%d")})


def fetch_summary(event_id: str) -> dict[str, Any]:
    return _get_json(f"{_base_url()}/summary", params={"event": event_id})


def fetch_teams() -> dict[str, Any]:
    return _get_json(f"{_base_url()}/teams", params={"limit": "100"})


def fetch_team_roster(team_id: str) -> dict[str, Any]:
    return _get_json(f"{_base_url()}/teams/{team_id}/roster")


def fetch_all_rosters(sleep_seconds: float = 0.1) -> dict[str, Any]:
    """Coleta o roster (elenco completo, com posicao estavel independente de ter
    jogado) de cada selecao listada pela ESPN. Usado para corrigir o perfil de
    jogadores reservas que nunca entraram em campo — esses so tem posicao "SUB"
    nos dados de lineup por partida, o que gera classificacao incorreta."""
    teams_payload = fetch_teams()
    rosters: dict[str, Any] = {}
    team_names: dict[str, str] = {}
    teams = teams_payload.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    for entry in teams:
        team = entry.get("team", {})
        team_id = str(team.get("id"))
        if not team_id:
            continue
        team_names[team_id] = team.get("displayName")
        rosters[team_id] = fetch_team_roster(team_id)
        time.sleep(sleep_seconds)
    return {"rosters": rosters, "team_names": team_names}


def normalize_rosters_payload(payload: dict[str, Any]) -> pd.DataFrame:
    rows = []
    team_names = payload.get("team_names", {})
    for team_id, roster_payload in payload.get("rosters", {}).items():
        team_name = traduzir_selecao(team_names.get(team_id))
        for athlete in roster_payload.get("athletes", []):
            position = athlete.get("position") or {}
            player_name = (athlete.get("fullName") or athlete.get("displayName") or "").strip()
            rows.append(
                {
                    "team": team_name,
                    "team_id": team_id,
                    "player_name": player_name,
                    "squad_position": position.get("abbreviation"),
                    "squad_position_name": position.get("name"),
                    "shirt_number": athlete.get("jersey"),
                    "source": "espn",
                    "collected_at": utc_now_iso(),
                }
            )
    return pd.DataFrame(rows)


def fetch_tournament(start_date: date = START_DATE, end_date: date = END_DATE, sleep_seconds: float = 0.05) -> dict[str, Any]:
    scoreboards = []
    summaries = {}
    seen_event_ids = set()

    current = start_date
    while current <= end_date:
        scoreboard = fetch_scoreboard(current)
        scoreboards.append({"date": current.isoformat(), "payload": scoreboard})
        for event in scoreboard.get("events", []):
            event_id = str(event.get("id"))
            if not event_id or event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)
            if _should_fetch_summary(event):
                summaries[event_id] = fetch_summary(event_id)
                time.sleep(sleep_seconds)
        current += timedelta(days=1)
        time.sleep(sleep_seconds)

    return {"scoreboards": scoreboards, "summaries": summaries}


def normalize_matches_payload(scoreboards: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for event in _iter_events(scoreboards):
        competition = _competition(event)
        competitors = _competitors_by_home_away(competition)
        home = competitors.get("home", {})
        away = competitors.get("away", {})
        home_team = traduzir_selecao(home.get("team", {}).get("displayName"))
        away_team = traduzir_selecao(away.get("team", {}).get("displayName"))
        event_id = str(event.get("id"))
        match_id = make_match_id(home_team or "a_definir", away_team or "a_definir", f"espn_{event_id}")
        status = _normalize_status(competition.get("status") or event.get("status") or {})
        group = _parse_group(competition.get("altGameNote"))

        rows.append(
            {
                "match_id": match_id,
                "source_match_id": event_id,
                "fifa_match_id": None,
                "home_team": home_team,
                "away_team": away_team,
                "home_team_code": home.get("team", {}).get("abbreviation"),
                "away_team_code": away.get("team", {}).get("abbreviation"),
                "date": _date_part(event.get("date")),
                "kickoff_time": _time_part(event.get("date")),
                "timezone": "UTC",
                "group": group,
                "stage": _normalize_stage(event.get("season", {}).get("slug")),
                "round": None,
                "stadium": _venue(competition).get("fullName") or _venue(event).get("displayName"),
                "city": _venue(competition).get("address", {}).get("city"),
                "country": traduzir_selecao(_venue(competition).get("address", {}).get("country")),
                "status": status,
                "home_score": _score(home, status),
                "away_score": _score(away, status),
                "winner": _winner(home_team, away_team, home, away, status),
                "main_source": "espn",
                "official_reference": _event_link(event, "summary") or "https://www.espn.com/soccer/",
                "last_updated_at": utc_now_iso(),
            }
        )
    return pd.DataFrame(rows)


def normalize_team_stats_payload(scoreboards: list[dict[str, Any]], summaries: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for event in _iter_events(scoreboards):
        event_id = str(event.get("id"))
        summary = summaries.get(event_id, {})
        event_for_stats = summary.get("header", {}).get("competitions", [None])[0] or _competition(event)
        match_id = _match_id_from_event(event_for_stats, event)
        teams = summary.get("boxscore", {}).get("teams") or _competition(event).get("competitors", [])

        for team_entry in teams:
            team_info = team_entry.get("team", {})
            stats = _stats_map(team_entry.get("statistics", []))
            row = {
                "match_id": match_id,
                "source_match_id": event_id,
                "team": traduzir_selecao(team_info.get("displayName")),
                "team_code": team_info.get("abbreviation"),
                "home_away": team_entry.get("homeAway"),
                "source": "espn",
                "collected_at": utc_now_iso(),
            }
            for output_column, espn_column in TEAM_STAT_COLUMNS.items():
                row[output_column] = stats.get(espn_column)
            rows.append(row)
    return pd.DataFrame(rows)


def normalize_events_payload(scoreboards: list[dict[str, Any]], summaries: dict[str, Any]) -> pd.DataFrame:
    rows = []
    collected_at = utc_now_iso()
    for event in _iter_events(scoreboards):
        event_id = str(event.get("id"))
        match_id = _match_id_from_event(_competition(event), event)
        team_by_id = _team_by_id(_competition(event))
        summary = summaries.get(event_id, {})
        summary_competition = (summary.get("header", {}).get("competitions") or [{}])[0]
        details = _best_details(
            summary_competition.get("details"),
            _competition(event).get("details"),
            summary.get("keyEvents"),
        )
        for index, detail in enumerate(details, start=1):
            event_type = _event_type(detail)
            if not event_type:
                continue
            athlete = (detail.get("athletesInvolved") or [{}])[0]
            minute = _minute(detail.get("clock", {}))
            team = team_by_id.get(str(detail.get("team", {}).get("id")))
            rows.append(
                {
                    "match_id": match_id,
                    "event_id": str(detail.get("id") or f"{event_id}_{index}"),
                    "source_match_id": event_id,
                    "event_type": event_type,
                    "minute": minute,
                    "stoppage_minute": _stoppage_minute(minute),
                    "team": team,
                    "team_code": None,
                    "player": athlete.get("displayName") or athlete.get("fullName"),
                    "player_id": athlete.get("id"),
                    "related_player": None,
                    "period": str(detail.get("period", {}).get("displayValue") or detail.get("period", {}).get("number") or ""),
                    "description": _event_description(detail, athlete, team),
                    "source": "espn",
                    "collected_at": collected_at,
                    "minute_sort": _minute_sort(minute),
                }
            )
    return pd.DataFrame(rows)


def normalize_lineups_payload(summaries: dict[str, Any]) -> pd.DataFrame:
    rows = []
    collected_at = utc_now_iso()
    for event_id, summary in summaries.items():
        event = (summary.get("header", {}).get("competitions") or [{}])[0]
        match_id = _match_id_from_event(event, {"id": event_id, "date": event.get("date")})
        for roster in summary.get("rosters", []):
            team = traduzir_selecao(roster.get("team", {}).get("displayName"))
            for player in roster.get("roster", []):
                athlete = player.get("athlete", {})
                rows.append(
                    {
                        "match_id": match_id,
                        "source_match_id": str(event_id),
                        "team": team,
                        "player_id": athlete.get("id"),
                        "player_name": athlete.get("displayName") or athlete.get("fullName"),
                        "shirt_number": player.get("jersey"),
                        "position": player.get("position", {}).get("abbreviation") or player.get("position", {}).get("displayName"),
                        "is_starter": bool(player.get("starter")),
                        "is_substitute": not bool(player.get("starter")),
                        "formation_slot": player.get("formationPlace"),
                        "formation": roster.get("formation"),
                        "minutes_played": _stats_map(player.get("stats", [])).get("minutes"),
                        "source": "espn",
                        "collected_at": collected_at,
                    }
                )
    return pd.DataFrame(rows)


def normalize_player_stats_payload(summaries: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for event_id, summary in summaries.items():
        event = (summary.get("header", {}).get("competitions") or [{}])[0]
        match_id = _match_id_from_event(event, {"id": event_id, "date": event.get("date")})
        for roster in summary.get("rosters", []):
            team = traduzir_selecao(roster.get("team", {}).get("displayName"))
            for player in roster.get("roster", []):
                stats = _stats_map(player.get("stats", []))
                if not stats:
                    continue
                athlete = player.get("athlete", {})
                row = {
                    "match_id": match_id,
                    "source_match_id": str(event_id),
                    "team": team,
                    "player_id": athlete.get("id"),
                    "player_name": athlete.get("displayName") or athlete.get("fullName"),
                    "source": "espn",
                    "collected_at": utc_now_iso(),
                }
                for output_column, espn_column in PLAYER_STAT_COLUMNS.items():
                    row[output_column] = stats.get(espn_column)
                rows.append(row)
    return pd.DataFrame(rows)


def normalize_match_info_payload(scoreboards: list[dict[str, Any]], summaries: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for event in _iter_events(scoreboards):
        event_id = str(event.get("id"))
        summary = summaries.get(event_id, {})
        competition = (summary.get("header", {}).get("competitions") or [_competition(event)])[0]
        game_info = summary.get("gameInfo") or {}
        article = summary.get("article") or {}
        broadcasts = summary.get("broadcasts") or _competition(event).get("broadcasts") or []
        venue = game_info.get("venue") or _venue(competition) or _venue(event)

        rows.append(
            {
                "match_id": _match_id_from_event(competition, event),
                "source_match_id": event_id,
                "attendance": game_info.get("attendance") or _competition(event).get("attendance"),
                "referee": _official_name(game_info.get("officials", []), "Referee"),
                "venue": venue.get("fullName") or venue.get("displayName"),
                "city": venue.get("address", {}).get("city"),
                "country": traduzir_selecao(venue.get("address", {}).get("country")),
                "broadcasts": ", ".join(_broadcast_names(broadcasts)),
                "article_headline": article.get("headline"),
                "article_description": article.get("description"),
                "article_url": (article.get("links") or {}).get("web", {}).get("href") or article.get("link"),
                "image_url": _article_image(article),
                "commentary_available": bool(summary.get("commentary")),
                "commentary_count": len(summary.get("commentary") or []),
                "source": "espn",
                "collected_at": utc_now_iso(),
            }
        )
    return pd.DataFrame(rows)


def normalize_commentary_payload(summaries: dict[str, Any]) -> pd.DataFrame:
    rows = []
    collected_at = utc_now_iso()
    for event_id, summary in summaries.items():
        competition = (summary.get("header", {}).get("competitions") or [{}])[0]
        match_id = _match_id_from_event(competition, {"id": event_id, "date": competition.get("date")})
        team_by_name = _team_by_display_name(competition)
        for item in summary.get("commentary") or []:
            play = item.get("play") or {}
            minute = _minute(item.get("time") or play.get("clock") or {})
            team_name = play.get("team", {}).get("displayName")
            rows.append(
                {
                    "match_id": match_id,
                    "source_match_id": str(event_id),
                    "sequence": item.get("sequence"),
                    "minute": minute,
                    "minute_sort": _minute_sort(minute),
                    "period": play.get("period", {}).get("number"),
                    "play_id": play.get("id"),
                    "play_type": play.get("type", {}).get("type") or play.get("type", {}).get("text"),
                    "team": traduzir_selecao(team_name) if team_name else None,
                    "team_code": team_by_name.get(team_name),
                    "text": item.get("text"),
                    "play_text": play.get("text"),
                    "short_text": play.get("shortText"),
                    "participants": ", ".join(
                        participant.get("athlete", {}).get("displayName")
                        for participant in play.get("participants", [])
                        if participant.get("athlete", {}).get("displayName")
                    ),
                    "field_position_x": play.get("fieldPositionX"),
                    "field_position_y": play.get("fieldPositionY"),
                    "wallclock": play.get("wallclock"),
                    "source": "espn",
                    "collected_at": collected_at,
                }
            )
    return pd.DataFrame(rows)


def normalize_shots_payload(summaries: dict[str, Any]) -> pd.DataFrame:
    rows = []
    collected_at = utc_now_iso()
    for event_id, summary in summaries.items():
        competition = (summary.get("header", {}).get("competitions") or [{}])[0]
        match_id = _match_id_from_event(competition, {"id": event_id, "date": competition.get("date")})
        team_by_name = _team_by_display_name(competition)
        for item in summary.get("commentary") or []:
            play = item.get("play") or {}
            play_type = play.get("type", {}).get("type") or play.get("type", {}).get("text")
            if not _is_shot_play(play_type):
                continue
            participants = [
                participant.get("athlete", {}).get("displayName")
                for participant in play.get("participants", [])
                if participant.get("athlete", {}).get("displayName")
            ]
            team_name = play.get("team", {}).get("displayName")
            minute = _minute(item.get("time") or play.get("clock") or {})
            text = item.get("text") or play.get("text") or ""
            rows.append(
                {
                    "match_id": match_id,
                    "shot_id": play.get("id") or f"{event_id}_{item.get('sequence')}",
                    "source_match_id": str(event_id),
                    "minute": minute,
                    "minute_sort": _minute_sort(minute),
                    "team": traduzir_selecao(team_name) if team_name else None,
                    "team_code": team_by_name.get(team_name),
                    "player": participants[0] if participants else None,
                    "assist_player": participants[1] if len(participants) > 1 else None,
                    "outcome": _shot_outcome(play_type),
                    "body_part": _shot_body_part(text),
                    "situation": _shot_situation(text),
                    "location_x": play.get("fieldPositionX"),
                    "location_y": play.get("fieldPositionY"),
                    "xg": None,
                    "description": text,
                    "source": "espn",
                    "collected_at": collected_at,
                }
            )
    return pd.DataFrame(rows)


def normalize_player_stats_from_commentary(summaries: dict[str, Any]) -> pd.DataFrame:
    """Agrega eventos do commentary ESPN em estatísticas individuais por jogador por partida.

    Extrai chutes (no alvo, fora, bloqueados, na trave), faltas cometidas/sofridas,
    impedimentos e cantos ganhos — com nome do jogador identificado em cada evento.
    Combina com os stats dos rosters (goals, assists, saves, goals_conceded) para
    produzir um DataFrame enriquecido por (match_id, team, player_name).
    """
    # Mapeamento de play_type → (coluna, participante_index)
    # participante 0 = jogador principal; 1 = jogador secundário (bloqueador, assistente)
    EVENT_TO_STAT: dict[str, tuple[str, int]] = {
        "shot-on-target":   ("shots_on_target_commentary", 0),
        "shot-off-target":  ("shots_off_target", 0),
        "shot-blocked":     ("shots_blocked_att", 0),   # atacante que chutou
        "shot-hit-woodwork": ("shots_woodwork", 0),
        "goal":             ("goals_commentary", 0),
        "goal---header":    ("goals_commentary", 0),
        "goal---volley":    ("goals_commentary", 0),
        "penalty---scored": ("goals_commentary", 0),
        "own-goal":         ("own_goals_commentary", 0),
        "foul":             ("fouls_committed_commentary", 0),   # quem fez a falta
        "handball":         ("fouls_committed_commentary", 0),
        "offside":          ("offsides_commentary", 0),
        "corner-awarded":   ("corners_won", 1),          # quem concedeu o canto (time adversário)
    }
    # fouls sofridos: participante 1 nos eventos de falta
    FOUL_VICTIM_STAT = "fouls_drawn_commentary"

    collected_at = utc_now_iso()
    rows: list[dict[str, Any]] = []

    for event_id, summary in summaries.items():
        competition = (summary.get("header", {}).get("competitions") or [{}])[0]
        match_id = _match_id_from_event(competition, {"id": event_id, "date": competition.get("date")})
        team_by_display = _team_by_display_name(competition)

        # Contadores por (player_name, team_display)
        counters: dict[tuple[str, str], dict[str, float]] = {}

        def _inc(player_display: str, team_display: str, stat: str, val: float = 1.0) -> None:
            key = (player_display, team_display)
            if key not in counters:
                counters[key] = {}
            counters[key][stat] = counters[key].get(stat, 0.0) + val

        for item in summary.get("commentary") or []:
            play = item.get("play") or {}
            ptype = (play.get("type") or {}).get("type", "")
            if ptype not in EVENT_TO_STAT:
                continue
            team_display = (play.get("team") or {}).get("displayName", "")
            participants = play.get("participants", [])

            stat_col, p_idx = EVENT_TO_STAT[ptype]
            if p_idx < len(participants):
                name = (participants[p_idx].get("athlete") or {}).get("displayName", "")
                if name:
                    _inc(name, team_display, stat_col)

            # Jogador que sofreu a falta (participante 1 em eventos de foul)
            if ptype == "foul" and len(participants) > 1:
                victim = (participants[1].get("athlete") or {}).get("displayName", "")
                if victim:
                    # vítima pertence ao time oposto — descobrimos pelo team_by_display
                    _inc(victim, "", FOUL_VICTIM_STAT)  # team resolvido depois pelo merge

        # Montar linhas
        for (player_name, team_display), stats in counters.items():
            team = traduzir_selecao(team_display) if team_display else None
            rows.append({
                "match_id": match_id,
                "source_match_id": str(event_id),
                "player_name": player_name,
                "team_display": team_display,
                "team": team,
                "source": "espn_commentary",
                "collected_at": collected_at,
                **stats,
            })

    return pd.DataFrame(rows)


def _get_json(url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    response = requests.get(url, params=params, timeout=30, headers={"User-Agent": "fifa-analytics/0.1"})
    response.raise_for_status()
    return response.json()


def _should_fetch_summary(event: dict[str, Any]) -> bool:
    status = (_competition(event).get("status") or event.get("status") or {}).get("type", {})
    return status.get("state") in {"post", "in"} or bool(_competition(event).get("details"))


def _iter_events(scoreboards: list[dict[str, Any]]):
    seen = set()
    for item in scoreboards:
        payload = item.get("payload", item)
        for event in payload.get("events", []):
            event_id = str(event.get("id"))
            if event_id in seen:
                continue
            seen.add(event_id)
            yield event


def _competition(event: dict[str, Any]) -> dict[str, Any]:
    return (event.get("competitions") or [{}])[0]


def _competitors_by_home_away(competition: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {competitor.get("homeAway"): competitor for competitor in competition.get("competitors", [])}


def _venue(record: dict[str, Any]) -> dict[str, Any]:
    return record.get("venue") or {}


def _date_part(value: str | None) -> str | None:
    if not value:
        return None
    return value[:10]


def _time_part(value: str | None) -> str | None:
    if not value or "T" not in value:
        return None
    return value.split("T", 1)[1].replace("Z", "")[:5]


def _normalize_status(status: dict[str, Any]) -> str:
    state = status.get("type", {}).get("state")
    completed = status.get("type", {}).get("completed")
    if completed or state == "post":
        return "finalizado"
    if state == "in":
        return "ao_vivo"
    return "agendado"


def _normalize_stage(slug: str | None) -> str | None:
    mapping = {
        "group-stage": "fase_de_grupos",
        "round-of-32": "dezesseis_avos",
        "round-of-16": "oitavas_de_final",
        "quarterfinals": "quartas_de_final",
        "semifinals": "semifinal",
        "third-place": "terceiro_lugar",
        "final": "final",
    }
    return mapping.get(str(slug or "").lower(), slug)


def _parse_group(note: str | None) -> str | None:
    if not note or "Group" not in note:
        return None
    return note.rsplit("Group", 1)[-1].strip()


def _score(competitor: dict[str, Any], status: str) -> int | None:
    if status == "agendado":
        return None
    score = competitor.get("score")
    return int(score) if str(score).isdigit() else None


def _winner(home_team: str | None, away_team: str | None, home: dict[str, Any], away: dict[str, Any], status: str) -> str | None:
    if status == "agendado":
        return None
    if home.get("winner"):
        return home_team
    if away.get("winner"):
        return away_team
    return "empate"


def _event_link(event: dict[str, Any], rel: str) -> str | None:
    for link in event.get("links", []):
        if rel in link.get("rel", []):
            return link.get("href")
    return None


def _match_id_from_event(competition: dict[str, Any], fallback_event: dict[str, Any]) -> str:
    event_id = str(competition.get("id") or fallback_event.get("id"))
    competitors = _competitors_by_home_away(competition)
    home_team = traduzir_selecao(competitors.get("home", {}).get("team", {}).get("displayName"))
    away_team = traduzir_selecao(competitors.get("away", {}).get("team", {}).get("displayName"))
    return make_match_id(home_team or "a_definir", away_team or "a_definir", f"espn_{event_id}")


def _stats_map(stats: list[dict[str, Any]]) -> dict[str, float | int | None]:
    return {stat.get("name"): _number(stat.get("value", stat.get("displayValue"))) for stat in stats}


def _number(value: Any) -> float | int | None:
    if value is None:
        return None
    text = str(value).replace("%", "").strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _team_by_id(competition: dict[str, Any]) -> dict[str, str]:
    rows = {}
    for competitor in competition.get("competitors", []):
        team = competitor.get("team", {})
        rows[str(team.get("id"))] = traduzir_selecao(team.get("displayName"))
    return rows


def _team_by_display_name(competition: dict[str, Any]) -> dict[str, str | None]:
    rows = {}
    for competitor in competition.get("competitors", []):
        team = competitor.get("team", {})
        rows[team.get("displayName")] = team.get("abbreviation")
    return rows


def _event_type(detail: dict[str, Any]) -> str | None:
    text = str(detail.get("type", {}).get("text") or detail.get("text") or "").lower()
    if "yellow card" in text:
        return "cartao_amarelo"
    if "red card" in text:
        return "cartao_vermelho"
    if "own goal" in text:
        return "gol_contra"
    if "penalty" in text and ("scored" in text or detail.get("scoringPlay")):
        return "gol_penalti"
    if "goal" in text or detail.get("scoringPlay"):
        return "gol"
    return None


def _official_name(officials: list[dict[str, Any]], role: str) -> str | None:
    for official in officials:
        if official.get("position", {}).get("displayName") == role:
            return official.get("displayName") or official.get("fullName")
    return None


def _broadcast_names(broadcasts: list[dict[str, Any]]) -> list[str]:
    names = []
    for broadcast in broadcasts:
        media = broadcast.get("media", {})
        name = media.get("shortName") or media.get("name") or media.get("callLetters")
        if name and name not in names:
            names.append(name)
    return names


def _article_image(article: dict[str, Any]) -> str | None:
    images = article.get("images") or []
    if not images:
        return None
    return images[0].get("url")


def _minute(clock: dict[str, Any]) -> str:
    display = str(clock.get("displayValue") or "").replace("'", "").strip()
    if display:
        return display
    value = clock.get("value")
    if value is None:
        return ""
    return str(int(round(float(value) / 60)))


def _stoppage_minute(minute: str) -> int | None:
    if "+" not in minute:
        return None
    return int(minute.split("+", 1)[1])


def _minute_sort(minute: str) -> int:
    if not minute:
        return 0
    if "+" in minute:
        base, extra = minute.split("+", 1)
        return int(base) * 100 + int(extra)
    return int(minute) * 100


def _event_description(detail: dict[str, Any], athlete: dict[str, Any], team: str | None) -> str:
    event_type = _event_type_label(detail)
    player = athlete.get("displayName") or athlete.get("fullName")
    if player and team:
        return f"{event_type}: {player} ({team})"
    if player:
        return f"{event_type}: {player}"
    return str(event_type)


def _best_details(*candidates: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    valid = [candidate for candidate in candidates if candidate]
    if not valid:
        return []
    return sorted(valid, key=lambda rows: (_details_have_athletes(rows), len(rows)), reverse=True)[0]


def _details_have_athletes(details: list[dict[str, Any]]) -> bool:
    return any(detail.get("athletesInvolved") for detail in details)


def _event_type_label(detail: dict[str, Any]) -> str:
    event_type = _event_type(detail)
    labels = {
        "gol": "Gol",
        "gol_penalti": "Gol de pênalti",
        "gol_contra": "Gol contra",
        "cartao_amarelo": "Cartão amarelo",
        "cartao_vermelho": "Cartão vermelho",
    }
    return labels.get(event_type or "", detail.get("type", {}).get("text") or detail.get("text") or "Evento")


def _is_shot_play(play_type: str | None) -> bool:
    return str(play_type or "").lower() in {
        "shot-off-target",
        "shot-blocked",
        "shot-on-target",
        "shot-hit-woodwork",
        "goal",
        "goal---header",
        "goal---volley",
        "own-goal",
        "penalty---scored",
    }


def _shot_outcome(play_type: str | None) -> str:
    text = str(play_type or "").lower()
    if "goal" in text or "penalty---scored" in text:
        return "gol"
    if "on-target" in text:
        return "no_alvo"
    if "blocked" in text:
        return "bloqueado"
    if "woodwork" in text:
        return "trave"
    return "fora"


def _shot_body_part(text: str) -> str | None:
    lower = text.lower()
    if "header" in lower:
        return "cabeca"
    if "left foot" in lower:
        return "pe_esquerdo"
    if "right foot" in lower:
        return "pe_direito"
    return None


def _shot_situation(text: str) -> str | None:
    lower = text.lower()
    if "penalty" in lower:
        return "penalti"
    if "following a corner" in lower:
        return "escanteio"
    if "set piece" in lower:
        return "bola_parada"
    if "fast break" in lower:
        return "contra_ataque"
    return "jogo_corrido"
