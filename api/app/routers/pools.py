"""Bolões: criação, listagem e ranking."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db import get_db
from api.app.models import Pool, PoolMember, Prediction, ScoringRule, User
from api.app.schemas import PoolCreate, PoolOut, RankingRow, RuleOut

router = APIRouter(prefix="/pools", tags=["pools"])


@router.get("/rules", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.scalars(select(ScoringRule).order_by(ScoringRule.id)).all()


@router.get("", response_model=list[PoolOut])
def list_pools(db: Session = Depends(get_db)):
    return db.scalars(select(Pool).order_by(Pool.id)).all()


@router.post("", response_model=PoolOut, status_code=201)
def create_pool(payload: PoolCreate, db: Session = Depends(get_db)):
    if db.get(User, payload.owner_id) is None:
        raise HTTPException(404, "owner não encontrado")
    if db.get(ScoringRule, payload.rule_id) is None:
        raise HTTPException(404, "regra não encontrada")
    pool = Pool(name=payload.name, owner_id=payload.owner_id, rule_id=payload.rule_id)
    db.add(pool)
    db.flush()
    # dono já entra como membro
    db.add(PoolMember(pool_id=pool.id, user_id=payload.owner_id))
    db.commit()
    db.refresh(pool)
    return pool


@router.get("/{pool_id}/ranking", response_model=list[RankingRow])
def pool_ranking(pool_id: int, db: Session = Depends(get_db)):
    if db.get(Pool, pool_id) is None:
        raise HTTPException(404, "bolão não encontrado")

    preds = db.scalars(
        select(Prediction).where(Prediction.pool_id == pool_id)
    ).all()
    points: dict[int, int] = defaultdict(int)
    counts: dict[int, int] = defaultdict(int)
    for p in preds:
        points[p.user_id] += p.points or 0
        counts[p.user_id] += 1

    names = {u.id: u.name for u in db.scalars(select(User)).all()}
    rows = [
        RankingRow(
            user_id=uid,
            name=names.get(uid, str(uid)),
            total_points=points[uid],
            predictions=counts[uid],
        )
        for uid in points
    ]
    rows.sort(key=lambda r: (-r.total_points, r.name))
    return rows
