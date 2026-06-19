"""Carrega data/gold/dim_match.parquet -> tabela matches (upsert idempotente).

Roda após cada `fifa-analytics fifa-coletar`. Quando um jogo passa a
'finalizado', recalcula os pontos dos palpites daquele jogo.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db import SessionLocal
from api.app.models import Match
from api.app.scoring.engine import score_prediction
from fifa_analytics.paths import GOLD_DIR

_COLS = [
    "match_id", "match_number", "id_ifes", "home_team", "away_team",
    "home_team_code", "away_team_code", "stage", "group", "date_utc",
    "status", "home_score", "away_score",
]


def _to_int(value) -> int | None:
    return None if pd.isna(value) else int(value)


def load_matches(db: Session, parquet_path=None) -> dict[str, int]:
    """Upsert dos jogos. Retorna contadores. Recalcula pontos dos jogos que
    finalizaram nesta carga."""
    path = parquet_path or (GOLD_DIR / "dim_match.parquet")
    df = pd.read_parquet(path)

    existing = {m.match_id: m for m in db.scalars(select(Match)).all()}
    inserted = updated = newly_finished = 0

    for row in df[_COLS].itertuples(index=False):
        data = dict(row._asdict())
        data["home_score"] = _to_int(data["home_score"])
        data["away_score"] = _to_int(data["away_score"])
        data["match_number"] = int(data["match_number"])

        match = existing.get(data["match_id"])
        if match is None:
            db.add(Match(**data))
            inserted += 1
            continue

        was_finished = match.status == "finalizado"
        for key, value in data.items():
            setattr(match, key, value)
        updated += 1
        if not was_finished and match.status == "finalizado":
            newly_finished += 1
            _rescore_match(db, match)

    db.commit()
    return {
        "inserted": inserted,
        "updated": updated,
        "newly_finished": newly_finished,
        "total": len(df),
    }


def _rescore_match(db: Session, match: Match) -> None:
    """Recalcula os pontos de todos os palpites de um jogo finalizado."""
    if match.home_score is None or match.away_score is None:
        return
    result = (match.home_score, match.away_score)
    for pred in match.predictions:
        spec = pred_pool_spec(db, pred.pool_id)
        pred.points = score_prediction(spec, (pred.home_score, pred.away_score), result)


def pred_pool_spec(db: Session, pool_id: int) -> dict:
    """Spec da regra do bolão de um palpite."""
    from api.app.models import Pool

    pool = db.get(Pool, pool_id)
    return pool.rule.spec if pool and pool.rule else {}


def main() -> None:
    db = SessionLocal()
    try:
        result = load_matches(db)
        print("matches carregados:", result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
