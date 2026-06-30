"""Seed de dev (idempotente), sem criar schema — o schema vem do Alembic.

Seeda as regras builtin, carrega o gold parquet no DB e garante um usuário/
bolão de teste. Use depois de `alembic upgrade head`.

Uso: DATABASE_URL=postgresql+... python scripts/seed_dev.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.app.auth import hash_password
from api.app.db import SessionLocal
from api.app.loaders.load_matches import load_matches
from api.app.models import Pool, PoolMember, ScoringRule, User
from api.app.seed import seed_rules
from sqlalchemy import func, select

print("=== Seed Dev ===")

db = SessionLocal()
try:
    n = seed_rules(db)
    print(f"✓ Regras seedadas ({n} novas)")

    result = load_matches(db)
    print(f"✓ Matches: {result}")

    existing = db.scalar(select(User).where(User.username == "teste"))
    if existing is None:
        user = User(
            username="teste",
            name="Davi (teste)",
            password_hash=hash_password("copa2026"),
        )
        db.add(user)
        db.flush()
        rule = db.scalar(select(ScoringRule).where(ScoringRule.name == "Clássico"))
        if rule:
            pool = Pool(name="Bolão Teste", owner_id=user.id, rule_id=rule.id)
            db.add(pool)
            db.flush()
            db.add(PoolMember(pool_id=pool.id, user_id=user.id))
        db.commit()
        print("✓ Usuário de teste criado: teste / copa2026")
    else:
        print("✓ Usuário de teste já existe")

    from api.app.models import Match

    total = db.scalar(select(func.count()).select_from(Match))
    fin = db.scalar(
        select(func.count()).select_from(Match).where(Match.status == "finalizado")
    )
    print(f"\nResumo: {total} jogos carregados, {fin} finalizados")
finally:
    db.close()
