"""Cliente HTTP das APIs oficiais da FIFA.

Duas APIs públicas, sem autenticação (ver DESCOBERTA_API_OFICIAL_FIFA.md):
- v3   (api.fifa.com/api/v3)     — estrutural: calendário, jogos, escalações
- fdh  (fdh-api.fifa.com/v1)     — avançado: 145 métricas/time, power ranking

São SPAs com backend exposto: basta um User-Agent de browser. Cada chamada
abre conexão nova e faz retry com backoff (a fdh às vezes dá 5xx transitório).
"""

from __future__ import annotations

import random
import time
from typing import Any

import requests

V3_BASE = "https://api.fifa.com/api/v3"
FDH_BASE = "https://fdh-api.fifa.com/v1"

# IDs da Copa 2026 (ver doc da descoberta).
ID_COMPETITION = "17"
ID_SEASON = "285023"

DEFAULT_TIMEOUT = 25
DEFAULT_RETRIES = 4
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


class FifaSourceError(RuntimeError):
    """Falha ao coletar uma das APIs da FIFA."""


def _get(url: str, *, timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES) -> Any:
    """GET com retry/backoff. Conexão nova por tentativa.

    404 é definitivo (não tem por que repetir) e propaga direto — é o sinal de
    que um jogo futuro ainda não tem dados no fdh-api.
    """
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with requests.Session() as session:
                session.headers.update(
                    {"User-Agent": _USER_AGENT, "Accept": "application/json"}
                )
                response = session.get(url, timeout=timeout)
            if response.status_code == 404:
                raise FifaSourceError(f"404 (sem dados ainda?): {url}")
            response.raise_for_status()
            return response.json()
        except FifaSourceError:
            raise
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                wait = min(1.5 * (1.6 ** (attempt - 1)), 10.0)
                time.sleep(wait + random.uniform(0, 1.0))

    raise FifaSourceError(
        f"Falha ao buscar {url} após {retries} tentativas: {last_error}"
    ) from last_error


# --- v3: estrutural -------------------------------------------------------


def fetch_calendar_matches(
    *, id_competition: str = ID_COMPETITION, id_season: str = ID_SEASON, count: int = 200
) -> list[dict[str, Any]]:
    """Os 104 jogos da Copa: placar, status, stage, grupo e Properties.IdIFES.

    O IdIFES (id interno usado pela fdh-api) já vem aqui em cada jogo — não
    precisa de chamada extra para mapeá-lo.
    """
    url = (
        f"{V3_BASE}/calendar/matches?idCompetition={id_competition}"
        f"&idSeason={id_season}&language=en&count={count}"
    )
    return _get(url).get("Results", [])


# --- fdh: avançado --------------------------------------------------------


def fetch_match_team_stats(id_ifes: str) -> dict[str, Any]:
    """145 métricas por time, para um jogo (dict idTeam -> [[nome, valor, oficial], ...]).

    Levanta FifaSourceError(404) se o jogo ainda não finalizou.
    """
    return _get(f"{FDH_BASE}/stats/match/{id_ifes}/teams.json")
