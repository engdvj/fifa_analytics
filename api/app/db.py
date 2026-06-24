"""Engine, sessão e Base do SQLAlchemy.

DATABASE_URL via .env. Default aponta para o Postgres do docker-compose; em
testes, sobrescreve para SQLite (ver tests/conftest).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv(override=True)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://fifa:fifa@localhost:5432/fifa"
)

# check_same_thread só importa pro SQLite (testes); ignorado no Postgres.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, future=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base declarativa de todos os modelos ORM."""


def get_db() -> Iterator[Session]:
    """Dependency do FastAPI: uma sessão por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
