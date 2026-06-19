"""App FastAPI — plataforma de bolão com analytics (Copa 2026)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.app.db import Base, SessionLocal, engine
from api.app.routers import matches, pools, predictions, users
from api.app.seed import seed_rules


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cria tabelas se ainda não existem (Alembic é a fonte de verdade em prod;
    # isto facilita dev/SQLite) e seeda as regras builtin. Tolerante a banco
    # ausente: em testes o schema/seed vêm da fixture, não daqui.
    try:
        Base.metadata.create_all(engine)
        db = SessionLocal()
        try:
            seed_rules(db)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 — não derruba o app se o banco real não existe
        pass
    yield


app = FastAPI(title="FIFA Bolão Analytics", version="0.1.0", lifespan=lifespan)

app.include_router(matches.router)
app.include_router(users.router)
app.include_router(pools.router)
app.include_router(predictions.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
