"""Seed das regras builtin de pontuação e do admin inicial. Idempotente."""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.auth import hash_password
from api.app.models import ScoringRule, User
from api.app.scoring.engine import BUILTIN_RULES


def seed_rules(db: Session) -> int:
    """Insere as regras builtin (owner_id=None) que ainda não existem.

    Retorna quantas criou."""
    existing = {r.name for r in db.scalars(select(ScoringRule)).all()}
    created = 0
    for name, data in BUILTIN_RULES.items():
        if name in existing:
            continue
        db.add(
            ScoringRule(
                name=name,
                description=data["description"],
                spec=data["spec"],
                owner_id=None,  # builtin/global
            )
        )
        created += 1
    db.commit()
    return created


def seed_admin(db: Session) -> bool:
    """Cria/garante o admin a partir de ADMIN_USERNAME/ADMIN_PASSWORD.

    Aceita ADMIN_EMAIL como apelido legado de ADMIN_USERNAME. Se as variáveis não
    estiverem setadas, não faz nada. Se o usuário existir, garante is_admin=True.
    Retorna True se criou um novo usuário."""
    username = os.getenv("ADMIN_USERNAME") or os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    if not username or not password:
        return False

    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            username=username,
            name=os.getenv("ADMIN_NAME", "Admin"),
            password_hash=hash_password(password),
            is_admin=True,
        )
        db.add(user)
        db.commit()
        return True

    if not user.is_admin:
        user.is_admin = True
        db.commit()
    return False
