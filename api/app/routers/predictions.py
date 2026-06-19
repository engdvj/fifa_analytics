"""Palpites: criar/atualizar e listar. Pontua na hora se o jogo já finalizou."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db import get_db
from api.app.models import Match, Pool, PoolMember, Prediction
from api.app.schemas import PredictionCreate, PredictionOut

router = APIRouter(prefix="/pools/{pool_id}/predictions", tags=["predictions"])


@router.get("", response_model=list[PredictionOut])
def list_predictions(
    pool_id: int, user_id: int | None = None, db: Session = Depends(get_db)
):
    stmt = select(Prediction).where(Prediction.pool_id == pool_id)
    if user_id is not None:
        stmt = stmt.where(Prediction.user_id == user_id)
    return db.scalars(stmt).all()


@router.post("", response_model=PredictionOut, status_code=201)
def upsert_prediction(
    pool_id: int, payload: PredictionCreate, db: Session = Depends(get_db)
):
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    match = db.get(Match, payload.match_id)
    if match is None:
        raise HTTPException(404, "jogo não encontrado")
    if match.status == "finalizado":
        raise HTTPException(400, "jogo já finalizou; palpite encerrado")

    is_member = db.scalar(
        select(PoolMember).where(
            PoolMember.pool_id == pool_id, PoolMember.user_id == payload.user_id
        )
    )
    if is_member is None:
        db.add(PoolMember(pool_id=pool_id, user_id=payload.user_id))

    pred = db.scalar(
        select(Prediction).where(
            Prediction.pool_id == pool_id,
            Prediction.user_id == payload.user_id,
            Prediction.match_id == payload.match_id,
        )
    )
    if pred is None:
        pred = Prediction(
            pool_id=pool_id,
            user_id=payload.user_id,
            match_id=payload.match_id,
            home_score=payload.home_score,
            away_score=payload.away_score,
        )
        db.add(pred)
    else:
        pred.home_score = payload.home_score
        pred.away_score = payload.away_score
        pred.points = None  # invalida pontuação anterior

    db.commit()
    db.refresh(pred)
    return pred
