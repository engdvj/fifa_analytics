"""Contrato da API (Pydantic v2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    match_id: str
    match_number: int
    home_team: str | None
    away_team: str | None
    home_team_code: str | None
    away_team_code: str | None
    stage: str | None
    group: str | None
    date_utc: str | None
    status: str
    home_score: int | None
    away_score: int | None


class TeamMetric(BaseModel):
    id_team: str
    metric: str
    value: float | None
    is_official: bool | None


class MatchStatsOut(BaseModel):
    match_id: str
    teams: list[TeamMetric]


class UserCreate(BaseModel):
    email: str  # validação de e-mail entra na fase de auth (pydantic[email])
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    spec: dict


class PoolCreate(BaseModel):
    name: str
    owner_id: int
    rule_id: int


class PoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    rule_id: int


class PredictionCreate(BaseModel):
    user_id: int
    match_id: str
    home_score: int
    away_score: int


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pool_id: int
    user_id: int
    match_id: str
    home_score: int
    away_score: int
    points: int | None


class RankingRow(BaseModel):
    user_id: int
    name: str
    total_points: int
    predictions: int
