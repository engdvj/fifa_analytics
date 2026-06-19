"""Modelos ORM do domínio (Postgres).

Dois mundos: `matches` espelha o gold da FIFA (atualizado pelo loader); o resto
é transacional do bolão (users, pools, predictions). Métricas avançadas ficam
nos parquets — o DB guarda só o essencial pra resolver palpites e rankear.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.app.db import Base


class Match(Base):
    """Espelho de data/gold/dim_match.parquet (uma linha por jogo)."""

    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(String, primary_key=True)  # copa_2026_jogo_NNN
    match_number: Mapped[int] = mapped_column(Integer, index=True)
    id_ifes: Mapped[str | None] = mapped_column(String)
    home_team: Mapped[str | None] = mapped_column(String)
    away_team: Mapped[str | None] = mapped_column(String)
    home_team_code: Mapped[str | None] = mapped_column(String)
    away_team_code: Mapped[str | None] = mapped_column(String)
    stage: Mapped[str | None] = mapped_column(String)
    group: Mapped[str | None] = mapped_column(String)
    date_utc: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True, default="agendado")
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="match")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str | None] = mapped_column(String)  # auth real vem depois
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ScoringRule(Base):
    """Regra de pontuação como dados (spec JSONB). Builtin seedado; no futuro
    o usuário cria a sua. O `spec` é interpretado por scoring/engine.py."""

    __tablename__ = "scoring_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str | None] = mapped_column(String)
    spec: Mapped[dict] = mapped_column(JSON)  # JSONB no Postgres, JSON no SQLite


class Pool(Base):
    __tablename__ = "pools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    rule_id: Mapped[int] = mapped_column(ForeignKey("scoring_rules.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    rule: Mapped["ScoringRule"] = relationship()
    members: Mapped[list["PoolMember"]] = relationship(back_populates="pool")


class PoolMember(Base):
    __tablename__ = "pool_members"
    __table_args__ = (UniqueConstraint("pool_id", "user_id", name="uq_pool_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pool_id: Mapped[int] = mapped_column(ForeignKey("pools.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    pool: Mapped["Pool"] = relationship(back_populates="members")


class Prediction(Base):
    """Palpite de um usuário num jogo, dentro de um bolão. Único por trio."""

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("pool_id", "user_id", "match_id", name="uq_prediction"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pool_id: Mapped[int] = mapped_column(ForeignKey("pools.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.match_id"), index=True)
    home_score: Mapped[int] = mapped_column(Integer)
    away_score: Mapped[int] = mapped_column(Integer)
    points: Mapped[int | None] = mapped_column(Integer)  # calculado quando o jogo finaliza
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="predictions")
