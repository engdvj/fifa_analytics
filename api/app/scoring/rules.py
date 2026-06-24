"""Handlers builtin de pontuação, registrados por chave do spec.

Cada handler recebe o palpite e o resultado (placares) e devolve quantos pontos
aquele critério vale (0 se não bate). O `spec` da regra mapeia chave -> valor de
pontos, ex.: {"exact_score": 5, "correct_winner": 3}. Adicionar um critério novo
= registrar um handler aqui; o motor não muda. Isso abre caminho para o usuário
montar a própria regra escolhendo critérios e pesos.
"""

from __future__ import annotations

from collections.abc import Callable

# (home, away) de palpite e de resultado.
Handler = Callable[[int, int, int, int], bool]
_REGISTRY: dict[str, Handler] = {}
# Metadados pt-BR de cada critério, para o construtor de regras da UI.
_LABELS: dict[str, dict[str, str | None]] = {}

# Modos de acumulação do spec (ver scoring/engine.py).
MODES: list[str] = ["max", "sum"]


def register(key: str, label: str, description: str | None = None) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _REGISTRY[key] = fn
        _LABELS[key] = {"label": label, "description": description or fn.__doc__}
        return fn

    return deco


def get_handler(key: str) -> Handler | None:
    return _REGISTRY.get(key)


def available_keys() -> list[str]:
    return sorted(_REGISTRY)


def criteria_meta() -> list[dict[str, str | None]]:
    """Lista de critérios com rótulo/descrição pt-BR para o builder da UI."""
    return [
        {"key": key, "label": _LABELS[key]["label"], "description": _LABELS[key]["description"]}
        for key in available_keys()
    ]


def _winner(home: int, away: int) -> int:
    """1 = mandante, -1 = visitante, 0 = empate."""
    return (home > away) - (home < away)


@register("exact_score", "Placar exato", "Acertou o placar exato do jogo.")
def exact_score(ph: int, pa: int, rh: int, ra: int) -> bool:
    """Placar exato."""
    return ph == rh and pa == ra


@register("correct_winner", "Vencedor/empate", "Acertou quem venceu (ou o empate).")
def correct_winner(ph: int, pa: int, rh: int, ra: int) -> bool:
    """Acertou quem venceu (ou o empate)."""
    return _winner(ph, pa) == _winner(rh, ra)


@register("correct_goal_diff", "Saldo de gols", "Acertou o saldo de gols (ex.: 2-0 e 3-1 têm saldo +2).")
def correct_goal_diff(ph: int, pa: int, rh: int, ra: int) -> bool:
    """Acertou o saldo de gols (ex.: 2-0 e 3-1 têm saldo +2)."""
    return (ph - pa) == (rh - ra)


@register("correct_home_goals", "Gols do mandante", "Acertou o número de gols do mandante.")
def correct_home_goals(ph: int, pa: int, rh: int, ra: int) -> bool:
    """Acertou o número de gols do mandante."""
    return ph == rh


@register("correct_away_goals", "Gols do visitante", "Acertou o número de gols do visitante.")
def correct_away_goals(ph: int, pa: int, rh: int, ra: int) -> bool:
    """Acertou o número de gols do visitante."""
    return pa == ra
