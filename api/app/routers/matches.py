"""Jogos e estatísticas de time (leitura)."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db import get_db
from api.app.models import Match
from api.app.schemas import MatchOut, MatchStatsOut, TeamMetric
from fifa_analytics.paths import GOLD_DIR

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("", response_model=list[MatchOut])
def list_matches(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Match).order_by(Match.match_number)
    if status:
        stmt = stmt.where(Match.status == status)
    return db.scalars(stmt).all()


@router.get("/{match_id}", response_model=MatchOut)
def get_match(match_id: str, db: Session = Depends(get_db)):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(404, "jogo não encontrado")
    return match


def _load_stats() -> pd.DataFrame:
    path = GOLD_DIR / "fact_team_match_stats.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


@router.get("/{match_id}/stats", response_model=MatchStatsOut)
def get_match_stats(match_id: str):
    """Métricas avançadas de time do jogo, lidas direto do gold (parquet)."""
    df = _load_stats()
    if df.empty:
        raise HTTPException(404, "sem stats no gold (rode fifa-coletar)")
    rows = df[df["match_id"] == match_id]
    if rows.empty:
        raise HTTPException(404, "sem stats para esse jogo (ainda não finalizou?)")
    teams = [
        TeamMetric(
            id_team=str(r.id_team),
            metric=r.metric,
            value=None if pd.isna(r.value) else float(r.value),
            is_official=None if pd.isna(r.is_official) else bool(r.is_official),
        )
        for r in rows.itertuples()
    ]
    return MatchStatsOut(match_id=match_id, teams=teams)
