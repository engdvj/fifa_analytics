"""Critérios de pontuação e regras (builtin + do usuário).

Alimenta o construtor de regras da UI: lista os critérios disponíveis com
rótulos pt-BR e expõe CRUD básico de regras (criação owned pelo caller).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from api.app.db import get_db
from api.app.models import Pool, PoolMember, ScoringRule, User
from api.app.routers.auth import get_current_user
from api.app.scoring import rules as rules_mod
from api.app.scoring.recompute import recompute_pool_points
from api.app.schemas import CriteriaOut, RuleCreate, RuleOut, RuleUpdate

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.get("/criteria", response_model=CriteriaOut)
def list_criteria():
    """Critérios disponíveis (key, label pt-BR, descrição) + modos do spec."""
    return CriteriaOut(criteria=rules_mod.criteria_meta(), modes=rules_mod.MODES)


@router.get("/rules", response_model=list[RuleOut])
def list_rules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Regras builtin + as do usuário + as usadas pelos bolões dele.

    Incluir as regras usadas pelos seus bolões garante que, ao receber um bolão
    transferido, o novo dono enxergue (e mantenha) a regra mesmo sem tê-la criado.
    """
    pool_ids = {m.pool_id for m in db.scalars(select(PoolMember).where(PoolMember.user_id == user.id))}
    pool_ids |= set(db.scalars(select(Pool.id).where(Pool.owner_id == user.id)))
    used_rule_ids = set(db.scalars(select(Pool.rule_id).where(Pool.id.in_(pool_ids)))) if pool_ids else set()
    stmt = (
        select(ScoringRule)
        .where(or_(
            ScoringRule.owner_id.is_(None),
            ScoringRule.owner_id == user.id,
            ScoringRule.id.in_(used_rule_ids),
        ))
        .order_by(ScoringRule.id)
    )
    return db.scalars(stmt).all()


def _validate_spec(spec: dict) -> None:
    """Valida o spec: critérios conhecidos e `_mode` válido (se presente)."""
    known = set(rules_mod.available_keys())
    mode = spec.get("_mode", "max")
    if mode not in rules_mod.MODES:
        raise HTTPException(400, f"_mode inválido: {mode}")
    criterios = [k for k in spec if not k.startswith("_")]
    if not criterios:
        raise HTTPException(400, "spec sem critérios")
    desconhecidos = [k for k in criterios if k not in known]
    if desconhecidos:
        raise HTTPException(400, f"critérios desconhecidos: {desconhecidos}")


@router.post("/rules", response_model=RuleOut, status_code=201)
def create_rule(
    payload: RuleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cria uma regra própria (owner = caller). Valida as chaves do spec."""
    _validate_spec(payload.spec)
    if db.scalar(select(ScoringRule).where(ScoringRule.name == payload.name)):
        raise HTTPException(400, "já existe uma regra com esse nome")
    rule = ScoringRule(
        name=payload.name,
        description=payload.description,
        spec=payload.spec,
        owner_id=user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def _guard_rule(rule: ScoringRule, user: User) -> None:
    """Builtins (owner_id nulo) só admin mexe; regra de usuário, só o dono/admin."""
    if rule.owner_id is None and not user.is_admin:
        raise HTTPException(403, "regra builtin não pode ser alterada")
    if rule.owner_id is not None and rule.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "sem permissão para esta regra")


@router.patch("/rules/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: int,
    payload: RuleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Edita uma regra própria (nome/descrição/spec). Mudar o spec recalcula os
    pontos de todos os bolões que usam a regra."""
    rule = db.get(ScoringRule, rule_id)
    if rule is None:
        raise HTTPException(404, "regra não encontrada")
    _guard_rule(rule, user)
    if payload.name is not None and payload.name != rule.name:
        if db.scalar(select(ScoringRule).where(ScoringRule.name == payload.name)):
            raise HTTPException(400, "já existe uma regra com esse nome")
        rule.name = payload.name
    if payload.description is not None:
        rule.description = payload.description
    if payload.spec is not None:
        _validate_spec(payload.spec)
        rule.spec = payload.spec
        db.flush()
        recompute_pool_points(db)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exclui uma regra própria. Bloqueia se algum bolão ainda a usa."""
    rule = db.get(ScoringRule, rule_id)
    if rule is None:
        raise HTTPException(404, "regra não encontrada")
    _guard_rule(rule, user)
    if db.scalar(select(Pool.id).where(Pool.rule_id == rule_id)) is not None:
        raise HTTPException(400, "regra em uso por um bolão; troque a regra do bolão antes")
    db.delete(rule)
    db.commit()
    return {"deleted": rule_id}
