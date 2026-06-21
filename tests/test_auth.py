"""Testes da camada de autenticação JWT."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.app.db import Base, get_db
from api.app.main import app
from api.app.seed import seed_rules


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 't.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = Session()
    seed_rules(s)
    s.close()
    yield Session
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session):
    def override():
        s = db_session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_register_e_login(client):
    r = client.post(
        "/auth/register",
        json={"email": "a@test.com", "name": "Ana", "password": "senha123"},
    )
    assert r.status_code == 201
    token = r.json()["access_token"]
    assert token

    # /me com token válido
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@test.com"


def test_login_retorna_token(client):
    client.post(
        "/auth/register",
        json={"email": "b@test.com", "name": "Bob", "password": "abc"},
    )
    r = client.post("/auth/login", data={"username": "b@test.com", "password": "abc"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_senha_errada(client):
    client.post(
        "/auth/register",
        json={"email": "c@test.com", "name": "Carla", "password": "certa"},
    )
    r = client.post("/auth/login", data={"username": "c@test.com", "password": "errada"})
    assert r.status_code == 401


def test_email_duplicado(client):
    client.post(
        "/auth/register",
        json={"email": "d@test.com", "name": "D", "password": "x"},
    )
    r = client.post(
        "/auth/register",
        json={"email": "d@test.com", "name": "D2", "password": "y"},
    )
    assert r.status_code == 400


def test_me_sem_token(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_token_invalido(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer token_invalido"})
    assert r.status_code == 401
