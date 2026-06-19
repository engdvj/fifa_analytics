import re
import time
import warnings
from datetime import datetime
from typing import Any

import pandas as pd
import requests

from fifa_analytics.config import load_config
from fifa_analytics.transforms.matches import make_match_id
from fifa_analytics.transforms.team_names import traduzir_selecao
from fifa_analytics.utils.time import utc_now_iso


_FALLBACK_BASE_URL = "https://worldcup26.ir"
DEFAULT_TIMEOUT = 25
# A worldcup26.ir é instável: ~60% de sucesso por tentativa, com SSLError
# (UNEXPECTED_EOF) e HTTP 500 transitórios, e resposta lenta (7-8s) quando
# funciona. Mais tentativas elevam muito a chance de sucesso no conjunto
# (1 - 0.4^6 ≈ 99.6% vs 0.4^4 ≈ 97.4%), e o backoff com jitter evita martelar
# o servidor durante a janela ruim.
DEFAULT_RETRIES = 6


def _base_url() -> str:
    try:
        return load_config("sources.yaml")["sources"]["worldcup2026"]["base_url"] or _FALLBACK_BASE_URL
    except Exception:
        return _FALLBACK_BASE_URL


class WorldCup2026SourceError(RuntimeError):
    """Erro de coleta da API publica worldcup26.ir."""


def fetch_endpoint(
    endpoint: str,
    *,
    base_url: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    verify_tls: bool = False,
) -> dict[str, Any]:
    """Busca um endpoint da API worldcup26.ir com retry resiliente.

    A fonte é instável (SSLError UNEXPECTED_EOF, HTTP 500 transitórios). Cada
    tentativa abre uma CONEXÃO NOVA — uma conexão TLS que caiu no meio pode
    deixar a sessão num estado ruim, então reusá-la propaga a falha. O backoff
    é exponencial com jitter (evita martelar o servidor em sincronia durante a
    janela ruim e dá tempo do EOF de SSL passar)."""
    import random

    resolved_base = base_url or _base_url()
    url = f"{resolved_base.rstrip('/')}/{endpoint.lstrip('/')}"

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with warnings.catch_warnings():
                if not verify_tls:
                    warnings.simplefilter("ignore")
                # conexão nova por tentativa: não reusa sessão potencialmente
                # corrompida por um EOF de TLS anterior.
                with requests.Session() as session:
                    session.headers.update({"User-Agent": "fifa-analytics/0.1"})
                    response = session.get(url, timeout=timeout, verify=verify_tls)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                # backoff exponencial (1.5, 3, 4.5, 6, 8…) capado em 10s, + jitter
                base_wait = min(1.5 * (1.6 ** (attempt - 1)), 10.0)
                time.sleep(base_wait + random.uniform(0, 1.0))

    raise WorldCup2026SourceError(
        f"Falha ao buscar {url} apos {retries} tentativas: {last_error}"
    ) from last_error


def fetch_all() -> dict[str, Any]:
    return {
        "health": fetch_endpoint("api/health"),
        "teams": fetch_endpoint("get/teams"),
        "stadiums": fetch_endpoint("get/stadiums"),
        "groups": fetch_endpoint("get/groups"),
        "games": fetch_endpoint("get/games"),
    }


def fetch_matches() -> list[dict[str, Any]]:
    return fetch_endpoint("get/games").get("games", [])


def fetch_match(match_id: str) -> dict[str, Any]:
    return fetch_endpoint(f"get/game/{match_id}").get("game", {})


def normalize_matches_payload(games: list[dict[str, Any]], stadiums: list[dict[str, Any]] | None = None) -> pd.DataFrame:
    stadium_by_id = {str(stadium.get("id")): stadium for stadium in stadiums or []}
    rows = []

    for game in games:
        source_match_id = str(game.get("id") or "")
        home_team = traduzir_selecao(game.get("home_team_name_en"))
        away_team = traduzir_selecao(game.get("away_team_name_en"))
        date, kickoff_time = _parse_local_datetime(game.get("local_date"))
        stadium = stadium_by_id.get(str(game.get("stadium_id")), {})
        status = _normalize_status(game)
        home_score = _to_int_or_none(game.get("home_score"))
        away_score = _to_int_or_none(game.get("away_score"))
        if status == "agendado":
            home_score = None
            away_score = None

        if home_team and away_team:
            match_id = make_match_id(home_team, away_team, f"2026_match_{source_match_id}")
        else:
            match_id = f"worldcup2026_match_{source_match_id}"

        rows.append(
            {
                "match_id": match_id,
                "source_match_id": source_match_id,
                "fifa_match_id": None,
                "home_team": home_team,
                "away_team": away_team,
                "home_team_code": None,
                "away_team_code": None,
                "date": date,
                "kickoff_time": kickoff_time,
                "timezone": "local",
                "group": game.get("group"),
                "stage": _normalize_stage(game.get("type")),
                "round": game.get("matchday"),
                "stadium": stadium.get("fifa_name") or stadium.get("name_en"),
                "city": stadium.get("city_en"),
                "country": traduzir_selecao(stadium.get("country_en")),
                "status": status,
                "home_score": home_score,
                "away_score": away_score,
                "winner": _winner(home_team, away_team, home_score, away_score),
                "main_source": "worldcup2026",
                "official_reference": _base_url(),
                "last_updated_at": utc_now_iso(),
            }
        )

    return pd.DataFrame(rows)


def normalize_teams_payload(teams: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for team in teams:
        rows.append(
            {
                "team_id": str(team.get("id")),
                "source_team_id": str(team.get("id")),
                "team_name": traduzir_selecao(team.get("name_en")),
                "team_name_source": team.get("name_en"),
                "team_code": team.get("fifa_code"),
                "iso2": team.get("iso2"),
                "group": team.get("groups"),
                "flag": team.get("flag"),
                "main_source": "worldcup2026",
            }
        )
    return pd.DataFrame(rows)


def normalize_stadiums_payload(stadiums: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for stadium in stadiums:
        rows.append(
            {
                "stadium_id": str(stadium.get("id")),
                "source_stadium_id": str(stadium.get("id")),
                "stadium": stadium.get("fifa_name") or stadium.get("name_en"),
                "stadium_name_source": stadium.get("name_en"),
                "city": stadium.get("city_en"),
                "country": traduzir_selecao(stadium.get("country_en")),
                "capacity": _to_int_or_none(stadium.get("capacity")),
                "region": stadium.get("region"),
                "main_source": "worldcup2026",
            }
        )
    return pd.DataFrame(rows)


def normalize_standings_payload(groups: list[dict[str, Any]], teams: list[dict[str, Any]]) -> pd.DataFrame:
    team_by_id = {str(team.get("id")): team for team in teams}
    rows = []

    for group in groups:
        group_name = group.get("name")
        for standing in group.get("teams", []):
            team_id = str(standing.get("team_id"))
            team = team_by_id.get(team_id, {})
            rows.append(
                {
                    "group": group_name,
                    "team": traduzir_selecao(team.get("name_en")) or team_id,
                    "played": _to_int_or_zero(standing.get("mp")),
                    "wins": _to_int_or_zero(standing.get("w")),
                    "draws": _to_int_or_zero(standing.get("d")),
                    "losses": _to_int_or_zero(standing.get("l")),
                    "goals_for": _to_int_or_zero(standing.get("gf")),
                    "goals_against": _to_int_or_zero(standing.get("ga")),
                    "goal_difference": _to_int_or_zero(standing.get("gd")),
                    "points": _to_int_or_zero(standing.get("pts")),
                    "source_team_id": team_id,
                    "main_source": "worldcup2026",
                }
            )

    return pd.DataFrame(rows).sort_values(
        ["group", "points", "goal_difference", "goals_for"],
        ascending=[True, False, False, False],
    ).reset_index(drop=True)


def normalize_events_payload(games: list[dict[str, Any]]) -> pd.DataFrame:
    collected_at = utc_now_iso()
    rows = []

    for game in games:
        source_match_id = str(game.get("id") or "")
        home_team = traduzir_selecao(game.get("home_team_name_en"))
        away_team = traduzir_selecao(game.get("away_team_name_en"))
        if home_team and away_team:
            match_id = make_match_id(home_team, away_team, f"2026_match_{source_match_id}")
        else:
            match_id = f"worldcup2026_match_{source_match_id}"

        for side, team, raw_scorers in [
            ("home", home_team, game.get("home_scorers")),
            ("away", away_team, game.get("away_scorers")),
        ]:
            for index, scorer in enumerate(_parse_scorers(raw_scorers), start=1):
                event_type = "gol_contra" if scorer.get("qualifier") == "o.g." else "gol"
                rows.append(
                    {
                        "match_id": match_id,
                        "event_id": f"{match_id}_{side}_gol_{index}",
                        "source_match_id": source_match_id,
                        "event_type": event_type,
                        "minute": scorer["minute"],
                        "stoppage_minute": scorer.get("stoppage_minute"),
                        "team": team,
                        "team_code": None,
                        "player": scorer["player"],
                        "player_id": None,
                        "related_player": None,
                        "period": _period_from_minute(scorer["minute_sort"]),
                        "description": f"Gol de {scorer['player']} ({team})",
                        "source": "worldcup2026",
                        "collected_at": collected_at,
                        "minute_sort": scorer["minute_sort"],
                    }
                )

    return pd.DataFrame(rows)


def _parse_local_datetime(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    try:
        parsed = datetime.strptime(value, "%m/%d/%Y %H:%M")
    except ValueError:
        return value, None
    return parsed.date().isoformat(), parsed.strftime("%H:%M")


def _normalize_stage(value: str | None) -> str | None:
    mapping = {
        "group": "fase_de_grupos",
        "round_of_32": "dezesseis_avos",
        "round_of_16": "oitavas_de_final",
        "quarter": "quartas_de_final",
        "semi": "semifinal",
        "third_place": "terceiro_lugar",
        "final": "final",
        # códigos curtos que a API do worldcup26.ir usa de fato (games.json type):
        # mapeados pro MESMO vocabulário longo da ESPN p/ o canônico ficar
        # consistente entre fontes (senão wc2026='r32' conflita com ESPN=
        # 'dezesseis_avos' no mesmo jogo quando o mata-mata for coletado).
        "r32": "dezesseis_avos",
        "r16": "oitavas_de_final",
        "qf": "quartas_de_final",
        "sf": "semifinal",
        "third": "terceiro_lugar",
    }
    return mapping.get(str(value or "").lower(), value)


def _normalize_status(game: dict[str, Any]) -> str:
    finished = str(game.get("finished") or "").strip().lower()
    elapsed = str(game.get("time_elapsed") or "").strip().lower()
    if finished == "true" or elapsed == "finished":
        return "finalizado"
    if elapsed in {"live", "halftime"} or elapsed.isdigit():
        return "ao_vivo"
    return "agendado"


def _winner(home_team: str | None, away_team: str | None, home_score: int | None, away_score: int | None) -> str | None:
    if home_score is None or away_score is None:
        return None
    if home_score > away_score:
        return home_team
    if away_score > home_score:
        return away_team
    return "empate"


def _parse_scorers(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() == "null":
        return []

    scorers = []
    pattern = re.compile(r'"?([^"{},]+?)\s+(\d+(?:\+\d+)?)\'(?:\s*\(([^)]+)\))?')
    for match in pattern.finditer(text):
        minute = match.group(2)
        minute_sort, stoppage_minute = _minute_parts(minute)
        scorers.append(
            {
                "player": match.group(1).strip(),
                "minute": minute,
                "stoppage_minute": stoppage_minute,
                "qualifier": (match.group(3) or "").strip().lower() or None,
                "minute_sort": minute_sort,
            }
        )
    return scorers


def _minute_parts(value: str) -> tuple[int, int | None]:
    if "+" in value:
        base, extra = value.split("+", 1)
        return int(base) * 100 + int(extra), int(extra)
    return int(value) * 100, None


def _period_from_minute(minute_sort: int) -> str:
    if minute_sort <= 4500:
        return "1T"
    if minute_sort <= 9000:
        return "2T"
    return "prorrogacao"


def _to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    return int(float(text))


def _to_int_or_zero(value: Any) -> int:
    parsed = _to_int_or_none(value)
    return parsed if parsed is not None else 0
