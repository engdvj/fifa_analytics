from functools import lru_cache

from fifa_analytics.config import load_config


@lru_cache(maxsize=1)
def team_mapping() -> dict[str, str]:
    # Sem o YAML (ex.: config/ ausente num container mal empacotado) degrada para
    # mapa vazio em vez de derrubar quem chama com 500 — os nomes já vêm
    # traduzidos no gold, então traduzir_selecao apenas devolve a entrada.
    try:
        config = load_config("teams_mapping.yaml")
    except FileNotFoundError:
        return {}
    return config.get("teams", {})


def traduzir_selecao(nome: str | None) -> str | None:
    if nome is None:
        return None
    return team_mapping().get(nome, nome)
