from functools import lru_cache

from fifa_analytics.config import load_config


@lru_cache(maxsize=1)
def team_mapping() -> dict[str, str]:
    config = load_config("teams_mapping.yaml")
    return config.get("teams", {})


def traduzir_selecao(nome: str | None) -> str | None:
    if nome is None:
        return None
    return team_mapping().get(nome, nome)
