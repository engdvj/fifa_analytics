"""Palpites: criar/atualizar e listar. Pontua na hora se o jogo já finalizou."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db import get_db
from api.app.models import Match, Pool, PoolMember, Prediction, User
from api.app.routers.auth import get_current_user
from api.app.scoring.recompute import match_in_scope
from api.app.schemas import PredictionCreate, PredictionOut

router = APIRouter(prefix="/pools/{pool_id}/predictions", tags=["predictions"])


@router.get("", response_model=list[PredictionOut])
def list_predictions(
    pool_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Prediction).where(
        Prediction.pool_id == pool_id,
        Prediction.user_id == user.id,
    )
    return db.scalars(stmt).all()


@router.post("", response_model=PredictionOut, status_code=201)
def upsert_prediction(
    pool_id: int,
    payload: PredictionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    match = db.get(Match, payload.match_id)
    if match is None:
        raise HTTPException(404, "jogo não encontrado")
    # Bolão de grupo não recebe palpite direto — palpita-se nos filhos.
    if pool.is_group:
        raise HTTPException(400, "bolão de grupo não recebe palpites diretos")
    # Jogo precisa estar no escopo do bolão.
    if not match_in_scope(match, pool.scope):
        raise HTTPException(400, "jogo fora do escopo deste bolão")
    # Bloqueia escrita apenas para jogos já finalizados; jogos agendados sem
    # times definidos (mata-mata) ainda são permitidos.
    if match.status == "finalizado":
        raise HTTPException(400, "jogo já finalizou; palpite encerrado")

    is_member = db.scalar(
        select(PoolMember).where(
            PoolMember.pool_id == pool_id, PoolMember.user_id == user.id
        )
    )
    if is_member is None:
        db.add(PoolMember(pool_id=pool_id, user_id=user.id))

    pred = db.scalar(
        select(Prediction).where(
            Prediction.pool_id == pool_id,
            Prediction.user_id == user.id,
            Prediction.match_id == payload.match_id,
        )
    )
    if pred is None:
        pred = Prediction(
            pool_id=pool_id,
            user_id=user.id,
            match_id=payload.match_id,
            home_score=payload.home_score,
            away_score=payload.away_score,
        )
        db.add(pred)
    else:
        # Palpite já salvo é definitivo para o participante — só o admin pode
        # alterar (ele edita por `/pools/{id}/registro`, não por aqui).
        if not user.is_admin:
            raise HTTPException(403, "palpite já salvo; só o admin pode alterar")
        pred.home_score = payload.home_score
        pred.away_score = payload.away_score
        pred.points = None  # invalida pontuação anterior

    db.commit()
    db.refresh(pred)
    return pred
