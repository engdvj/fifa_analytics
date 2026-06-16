from typing import Any


def fetch_matches() -> list[dict[str, Any]]:
    """Retorna um conjunto pequeno de dados locais para testes ponta a ponta."""
    return [
        {
            "match_id": "mexico_africa_do_sul_2026_06_11",
            "source_match_id": "sample-001",
            "home_team": "Mexico",
            "away_team": "África do Sul",
            "home_team_code": "MEX",
            "away_team_code": "RSA",
            "date": "2026-06-11",
            "kickoff_time": "20:00",
            "timezone": "UTC",
            "group": "A",
            "stage": "fase_de_grupos",
            "round": "rodada_1",
            "stadium": "Mexico City Stadium",
            "city": "Mexico City",
            "country": "Mexico",
            "status": "finalizado",
            "home_score": 2,
            "away_score": 0,
            "winner": "Mexico",
            "last_updated_at": "2026-06-11T23:00:00Z",
        },
        {
            "match_id": "coreia_do_sul_tchequia_2026_06_11",
            "source_match_id": "sample-002",
            "home_team": "Coreia do Sul",
            "away_team": "Tchéquia",
            "home_team_code": "KOR",
            "away_team_code": "CZE",
            "date": "2026-06-11",
            "kickoff_time": "03:00",
            "timezone": "UTC",
            "group": "A",
            "stage": "fase_de_grupos",
            "round": "rodada_1",
            "stadium": "Guadalajara Stadium",
            "city": "Guadalajara",
            "country": "Mexico",
            "status": "finalizado",
            "home_score": 1,
            "away_score": 1,
            "winner": None,
            "last_updated_at": "2026-06-11T23:30:00Z",
        },
        {
            "match_id": "estados_unidos_paraguai_2026_06_12",
            "source_match_id": "sample-003",
            "home_team": "Estados Unidos",
            "away_team": "Paraguai",
            "home_team_code": "USA",
            "away_team_code": "PAR",
            "date": "2026-06-12",
            "kickoff_time": "02:00",
            "timezone": "UTC",
            "group": "D",
            "stage": "fase_de_grupos",
            "round": "rodada_1",
            "stadium": "Los Angeles Stadium",
            "city": "Los Angeles",
            "country": "Estados Unidos",
            "status": "finalizado",
            "home_score": 4,
            "away_score": 1,
            "winner": "Estados Unidos",
            "last_updated_at": "2026-06-12T05:00:00Z",
        },
    ]


def fetch_match(match_id: str) -> dict[str, Any]:
    for match in fetch_matches():
        if match["match_id"] == match_id:
            return match
    raise KeyError(f"Jogo de amostra nao encontrado: {match_id}")
