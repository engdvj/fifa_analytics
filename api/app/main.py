"""App FastAPI — plataforma de bolão com analytics (Copa 2026)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.db import Base, SessionLocal, engine
from api.app.routers import (
    admin,
    analytics,
    auth,
    matches,
    pools,
    predictions,
    scoring,
    stats,
    users,
)
from api.app.seed import seed_admin, seed_rules


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(engine)
        db = SessionLocal()
        try:
            seed_rules(db)
            seed_admin(db)
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        pass
    yield


app = FastAPI(title="FIFA Bolão Analytics", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics.router)
app.include_router(auth.router)
app.include_router(matches.router)
app.include_router(users.router)
app.include_router(scoring.router)
app.include_router(pools.router)
app.include_router(predictions.router)
app.include_router(stats.router)
app.include_router(admin.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
