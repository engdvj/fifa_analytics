"""Metadados cruzados dos bolões.

Agrega os palpites de TODOS os bolões por participante, para responder perguntas
de meta-análise: quem fez mais pontos no total, quem acertou mais placares exatos,
quem mais cravou o vencedor. Lê só do banco transacional (predictions + matches).
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db import get_db
from api.app.models import Match, Prediction, User
from api.app.routers.auth import get_current_user
from api.app.schemas import ParticipantStat, ParticipantStatsOut

router = APIRouter(prefix="/stats", tags=["stats"])


def _winner(home: int, away: int) -> int:
    """1 = mandante, -1 = visitante, 0 = empate."""
    return (home > away) - (home < away)


@router.get("/participants", response_model=ParticipantStatsOut)
def participant_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ranking de meta-análise por participante, somando todos os bolões."""
    matches = {m.match_id: m for m in db.scalars(select(Match)).all()}
    names = {u.id: u.name for u in db.scalars(select(User)).all()}
    preds = db.scalars(select(Prediction)).all()

    pools_of: dict[int, set[int]] = defaultdict(set)
    n_pred: dict[int, int] = defaultdict(int)
    total: dict[int, int] = defaultdict(int)
    exact: dict[int, int] = defaultdict(int)
    winners: dict[int, int] = defaultdict(int)

    for p in preds:
        pools_of[p.user_id].add(p.pool_id)
        n_pred[p.user_id] += 1
        m = matches.get(p.match_id)
        if (
            m is None
            or m.status != "finalizado"
            or m.home_score is None
            or m.away_score is None
        ):
            continue
        total[p.user_id] += p.points or 0
        if p.home_score == m.home_score and p.away_score == m.away_score:
            exact[p.user_id] += 1
        if _winner(p.home_score, p.away_score) == _winner(m.home_score, m.away_score):
            winners[p.user_id] += 1

    rows = [
        ParticipantStat(
            user_id=uid,
            name=names.get(uid, str(uid)),
            pools=len(pools_of[uid]),
            predictions=n_pred[uid],
            total_points=total[uid],
            exact_scores=exact[uid],
            correct_winners=winners[uid],
        )
        for uid in n_pred
    ]
    rows.sort(key=lambda r: (-r.total_points, -r.exact_scores, r.name))
    return ParticipantStatsOut(participants=rows)
