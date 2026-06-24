"""Recálculo centralizado de pontos e resolução de escopo de bolão.

Escopo de um bolão (`Pool.scope`, JSON) define quais jogos ele aceita/pontua:
    {"type": "all"}                            — todos os jogos
    {"type": "stage", "stages": [<stage>...]}  — jogos cujo stage está na lista
    {"type": "matches", "match_ids": [...]}    — match_ids explícitos

`recompute_pool_points` percorre os jogos finalizados e reescreve
`Prediction.points` usando a regra do bolão e respeitando o escopo. Reusa
`scoring/engine.score_prediction`.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.models import Match, Pool, Prediction
from api.app.scoring.engine import score_prediction


def match_in_scope(match: Match, scope: dict | None) -> bool:
    """True se o jogo pertence ao escopo. Escopo nulo/ausente = todos."""
    if not scope:
        return True
    stype = scope.get("type", "all")
    if stype == "all":
        return True
    if stype == "stage":
        return match.stage in (scope.get("stages") or [])
    if stype == "matches":
        return match.match_id in (scope.get("match_ids") or [])
    return True


def matches_in_scope(db: Session, scope: dict | None) -> list[Match]:
    """Jogos do banco dentro do escopo, ordenados por match_number."""
    matches = db.scalars(select(Match).order_by(Match.match_number)).all()
    return [m for m in matches if match_in_scope(m, scope)]


def recompute_pool_points(db: Session) -> int:
    """Recalcula os pontos de TODOS os palpites de jogos finalizados.

    Para cada palpite, pontua segundo a regra do seu bolão, mas só se o jogo
    estiver no escopo do bolão (fora do escopo → points=None). Retorna quantos
    palpites foram pontuados. Não dá commit (cabe ao chamador)."""
    matches = {m.match_id: m for m in db.scalars(select(Match)).all()}
    pools = {p.id: p for p in db.scalars(select(Pool)).all()}
    preds = db.scalars(select(Prediction)).all()

    scored = 0
    for pred in preds:
        pool = pools.get(pred.pool_id)
        match = matches.get(pred.match_id)
        if pool is None or match is None:
            continue
        if match.status != "finalizado" or match.home_score is None or match.away_score is None:
            pred.points = None
            continue
        if not match_in_scope(match, pool.scope):
            pred.points = None
            continue
        spec = pool.rule.spec if pool.rule else {}
        pred.points = score_prediction(
            spec, (pred.home_score, pred.away_score), (match.home_score, match.away_score)
        )
        scored += 1
    return scored
