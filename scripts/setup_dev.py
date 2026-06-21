"""Setup rápido do ambiente de dev local (SQLite).

Roda migrations (via create_all), seeda as regras builtin, carrega o gold
parquet no DB e cria um usuário/bolão de teste.

Uso: DATABASE_URL=sqlite:///./dev.db python scripts/setup_dev.py
"""

from __future__ import annotations

import os
import sys

# Garante que src/ está no path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# SQLite de dev por padrão
os.environ.setdefault("DATABASE_URL", "sqlite:///./dev.db")

from api.app.auth import hash_password
from api.app.db import Base, SessionLocal, engine
from api.app.loaders.load_matches import load_matches
from api.app.models import Pool, PoolMember, User
from api.app.seed import seed_rules
from sqlalchemy import select

print("=== Setup Dev ===")

# 1. Schema
Base.metadata.create_all(engine)
print("✓ Schema criado")

db = SessionLocal()
try:
    # 2. Regras builtin
    n = seed_rules(db)
    print(f"✓ Regras seedadas ({n} novas)")

    # 3. Jogos do gold
    result = load_matches(db)
    print(f"✓ Matches: {result}")

    # 4. Usuário de teste
    existing = db.scalar(select(User).where(User.email == "teste@copa2026.dev"))
    if existing is None:
        user = User(
            email="teste@copa2026.dev",
            name="Davi (teste)",
            password_hash=hash_password("copa2026"),
        )
        db.add(user)
        db.flush()

        # Pega a regra Clássico
        from api.app.models import ScoringRule
        rule = db.scalar(select(ScoringRule).where(ScoringRule.name == "Clássico"))
        if rule:
            pool = Pool(name="Bolão Teste", owner_id=user.id, rule_id=rule.id)
            db.add(pool)
            db.flush()
            db.add(PoolMember(pool_id=pool.id, user_id=user.id))

        db.commit()
        print(f"✓ Usuário de teste criado: {user.email} / senha: copa2026")
        print(f"  Pool criado: Bolão Teste (id={pool.id if rule else 'sem regra'})")
    else:
        db.commit()
        print(f"✓ Usuário de teste já existe: {existing.email}")

    # Resumo
    from sqlalchemy import func, select as sel
    from api.app.models import Match
    total = db.scalar(sel(func.count()).select_from(Match))
    fin = db.scalar(sel(func.count()).select_from(Match).where(Match.status == "finalizado"))
    print(f"\nResumo: {total} jogos carregados, {fin} finalizados")
    print("Ambiente de dev pronto. Rode: uvicorn api.app.main:app --reload")

finally:
    db.close()
