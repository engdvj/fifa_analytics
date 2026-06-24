"""Contrato da API (Pydantic v2)."""

from __future__ import annotations

from datetime import datetime

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
    username: str
    name: str | None = None
    password: str | None = None  # opcional: sem senha = participante sem login
    is_admin: bool = False


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    is_admin: bool | None = None  # só admin pode alterar (ver update_user)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str
    email: str | None = None
    is_admin: bool = False


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    spec: dict
    owner_id: int | None = None


class RuleCreate(BaseModel):
    name: str
    description: str | None = None
    spec: dict


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    spec: dict | None = None


class CriterionOut(BaseModel):
    key: str
    label: str
    description: str | None


class CriteriaOut(BaseModel):
    criteria: list[CriterionOut]
    modes: list[str]


# ── Escopo do bolão ────────────────────────────────────────────────────────────

class PoolScope(BaseModel):
    """Escopo de jogos de um bolão. type='all' ignora os demais campos."""

    type: str = "all"  # "all" | "stage" | "matches"
    stages: list[str] | None = None
    match_ids: list[str] | None = None


class PoolCreate(BaseModel):
    name: str
    scope: PoolScope | None = None
    rule_id: int | None = None
    inline_spec: dict | None = None  # cria uma regra na hora, dona = caller
    parent_id: int | None = None
    nest_by_stage: bool = False


class SalaCreate(BaseModel):
    """Cria uma SALA (liga): bolão-grupo com participantes e regra padrão.
    Os sub-bolões criados dentro herdam os participantes e a regra."""

    name: str
    member_ids: list[int] = []        # participantes da sala
    rule_id: int | None = None        # regra padrão da sala
    inline_spec: dict | None = None   # ou cria uma regra na hora


class MemberIn(BaseModel):
    user_id: int


class MoveIn(BaseModel):
    """Move um bolão para dentro de uma sala (parent_id) ou para a raiz (None)."""

    parent_id: int | None = None


class PoolUpdate(BaseModel):
    """Campos editáveis de um bolão (todos opcionais — só atualiza o que vier)."""

    name: str | None = None
    rule_id: int | None = None
    scope: PoolScope | None = None


class TransferIn(BaseModel):
    """Transferência de posse de um bolão para outro usuário."""

    user_id: int


class AdminPoolOut(BaseModel):
    """Linha da tabela de gestão de bolões (admin): inclui dono e nº de jogadores."""

    id: int
    name: str
    owner_id: int
    owner_name: str
    is_group: bool
    parent_id: int | None = None
    members: int
    rule_name: str | None = None
    scope: dict | None = None


class PoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    rule_id: int
    parent_id: int | None = None
    scope: dict | None = None
    is_group: bool = False


class PoolMemberOut(BaseModel):
    user_id: int
    name: str


class PoolTreeOut(PoolOut):
    """Bolão com filhos aninhados (árvore). members/n_matches/rule_name/status/
    winners são enriquecidos na listagem (`GET /pools`) para os cards."""

    n_members: int = 0
    n_matches: int = 0
    rule_name: str | None = None
    status: str = "a_iniciar"        # a_iniciar | em_andamento | finalizado
    winners: list[str] = []          # vencedor(es) — só quando finalizado
    children: list["PoolTreeOut"] = []


class PoolDetailOut(PoolOut):
    """Detalhe: inclui regra, membros e filhos."""

    rule: RuleOut | None = None
    members: list[PoolMemberOut] = []
    children: list["PoolTreeOut"] = []


class PredictionCreate(BaseModel):
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


class PoolMatchOut(BaseModel):
    """Jogo dentro do escopo de um bolão + palpite do caller, se houver."""

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
    prediction: PredictionOut | None = None


class RankingRow(BaseModel):
    user_id: int
    name: str
    total_points: int
    predictions: int


class ChildRanking(BaseModel):
    child_id: int
    child_name: str
    stage: str | None
    ranking: list[RankingRow]


class GroupRankingOut(BaseModel):
    """Ranking agregado de um bolão-grupo + quebra por filho."""

    ranking: list[RankingRow]
    children: list[ChildRanking] = []


# ── Registro de bolão já encerrado ──────────────────────────────────────────

class RegistroItem(BaseModel):
    """Palpite de um participante num jogo (lançado pelo dono do bolão)."""

    user_id: int
    match_id: str
    home_score: int
    away_score: int


class RegistroBatch(BaseModel):
    """Lote de palpites de um bolão já encerrado, em nome dos participantes."""

    items: list[RegistroItem]


class RegistroResult(BaseModel):
    registered: int  # palpites gravados
    scored: int      # quantos pontuados (jogo finalizado no escopo)
    ranking: list[RankingRow]


# ── Grade de palpites de todos os participantes (visão dono/admin) ──────────

class GridParticipant(BaseModel):
    user_id: int
    name: str


class GridPrediction(BaseModel):
    user_id: int
    match_id: str
    home_score: int
    away_score: int
    points: int | None = None


class PoolGridOut(BaseModel):
    matches: list[PoolMatchOut]
    participants: list[GridParticipant]
    predictions: list[GridPrediction]


# ── Metadados cruzados dos bolões ───────────────────────────────────────────

class ParticipantStat(BaseModel):
    user_id: int
    name: str
    pools: int
    predictions: int
    total_points: int
    exact_scores: int
    correct_winners: int


class ParticipantStatsOut(BaseModel):
    participants: list[ParticipantStat]


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    log: str | None
    triggered_by: int | None
    created_at: datetime
