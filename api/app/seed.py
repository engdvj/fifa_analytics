"""Seed das regras builtin de pontuação. Idempotente."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.models import ScoringRule
from api.app.scoring.engine import BUILTIN_RULES


def seed_rules(db: Session) -> int:
    """Insere as regras builtin que ainda não existem. Retorna quantas criou."""
    existing = {r.name for r in db.scalars(select(ScoringRule)).all()}
    created = 0
    for name, data in BUILTIN_RULES.items():
        if name in existing:
            continue
        db.add(ScoringRule(name=name, description=data["description"], spec=data["spec"]))
        created += 1
    db.commit()
    return created
