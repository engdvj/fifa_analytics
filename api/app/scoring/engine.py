"""Motor de pontuação: interpreta o spec de uma regra contra um resultado.

Data-driven — não conhece regras específicas, só percorre o spec e delega aos
handlers de rules.py. Para evitar acúmulo indevido (ex.: somar exact_score E
correct_winner no mesmo palpite), critérios são exclusivos por padrão: vale o
critério acertado de MAIOR pontuação. Spec pode pedir soma com {"_mode": "sum"}.
"""

from __future__ import annotations

from typing import Any

from api.app.scoring import rules

# Builtin: nome -> (descrição, spec). Seedado no banco pela migration/seed.
BUILTIN_RULES: dict[str, dict[str, Any]] = {
    "Clássico": {
        "description": "Placar exato 5, vencedor 3 (vale o maior acertado).",
        "spec": {"exact_score": 5, "correct_winner": 3},
    },
    "Detalhado": {
        "description": "Exato 6, saldo 3, vencedor 2 (vale o maior acertado).",
        "spec": {"exact_score": 6, "correct_goal_diff": 3, "correct_winner": 2},
    },
    "Soma de acertos": {
        "description": "Soma todos os critérios acertados.",
        "spec": {
            "_mode": "sum",
            "correct_winner": 2,
            "correct_home_goals": 1,
            "correct_away_goals": 1,
        },
    },
}


def score_prediction(
    spec: dict[str, Any],
    prediction: tuple[int, int],
    result: tuple[int, int],
) -> int:
    """Pontos de um palpite (ph, pa) contra um resultado (rh, ra) segundo o spec.

    Chaves começando com '_' são opções (ex.: '_mode'). As demais são critérios
    chave->pontos. 'sum' soma todos os acertos; o default ('max') vale só o maior.
    """
    ph, pa = prediction
    rh, ra = result
    mode = spec.get("_mode", "max")

    acertos: list[int] = []
    for key, pts in spec.items():
        if key.startswith("_"):
            continue
        handler = rules.get_handler(key)
        if handler is None:
            continue  # critério desconhecido é ignorado (robustez p/ regra do usuário)
        if handler(ph, pa, rh, ra):
            acertos.append(int(pts))

    if not acertos:
        return 0
    return sum(acertos) if mode == "sum" else max(acertos)
