"""Gating de admin e ciclo de vida dos jobs de coleta/recálculo.

Usa o mesmo SQLite temporário do test_platform_api. O pipeline FIFA não roda de
verdade aqui (sem rede/gold) — o runner é resiliente e ainda assim conclui o
job, gravando o desfecho no log."""

import warnings

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from api.app.db import Base, get_db
from api.app.main import app
from api.app.models import User
from api.app.routers import admin as admin_router
from api.app.seed import seed_rules

warnings.filterwarnings("ignore")


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path/'t.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = TestingSession()
    seed_rules(s)
    s.close()
    yield TestingSession
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
    # runner de background usa a mesma base SQLite do teste
    admin_router.set_session_factory(db_session)
    with TestClient(app) as c:
        c._SessionLocal = db_session
        yield c
    app.dependency_overrides.clear()
    admin_router.set_session_factory(admin_router.SessionLocal)


def _register(client, username, name="U", password="senha123"):
    return client.post(
        "/auth/register", json={"username": username, "name": name, "password": password}
    ).json()["access_token"]


def _make_admin(client, username):
    s = client._SessionLocal()
    u = s.scalar(select(User).where(User.username == username))
    u.is_admin = True
    s.commit()
    s.close()


def test_nao_admin_recebe_403(client):
    tok = _register(client, "user@x.com")
    h = {"Authorization": f"Bearer {tok}"}
    assert client.post("/admin/recalc", headers=h).status_code == 403
    assert client.get("/admin/jobs", headers=h).status_code == 403


def test_sem_token_401(client):
    assert client.post("/admin/recalc").status_code == 401


def test_insights_restrito_a_admin(client):
    # sem token → 401
    assert client.get("/analytics/insights").status_code == 401
    # usuário comum → 403
    tok = _register(client, "user@x.com")
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/analytics/insights", headers=h).status_code == 403
    # admin → 200 (lista; pode ser vazia se não houver gold)
    _make_admin(client, "user@x.com")
    r = client.get("/analytics/insights", headers=h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_insight_narrative_restrito_a_admin(client):
    assert client.get("/analytics/insights/narrative").status_code == 401
    tok = _register(client, "user@x.com")
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/analytics/insights/narrative", headers=h).status_code == 403
    _make_admin(client, "user@x.com")
    r = client.get("/analytics/insights/narrative", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "exists" in body and "paragraphs" in body


def test_me_expoe_is_admin(client):
    tok = _register(client, "adm@x.com")
    _make_admin(client, "adm@x.com")
    h = {"Authorization": f"Bearer {tok}"}
    me = client.get("/auth/me", headers=h).json()
    assert me["is_admin"] is True


def test_admin_dispara_recalc_e_job_conclui(client):
    tok = _register(client, "adm@x.com")
    _make_admin(client, "adm@x.com")
    h = {"Authorization": f"Bearer {tok}"}

    r = client.post("/admin/recalc", headers=h)
    assert r.status_code == 202
    job = r.json()
    assert job["kind"] == "recalc"
    # BackgroundTasks roda ao final do request no TestClient → já concluído.
    detail = client.get(f"/admin/jobs/{job['id']}", headers=h).json()
    assert detail["status"] in ("success", "error")
    assert detail["finished_at"] is not None
    assert detail["log"]  # tem registro do que aconteceu

    jobs = client.get("/admin/jobs", headers=h).json()
    assert jobs[0]["id"] == job["id"]  # mais recente primeiro


def test_admin_collect_resiliente(client, monkeypatch):
    """Pipeline falhando não derruba o servidor; job termina registrado como
    error mas com reload/recompute tentados (resiliência)."""
    def _boom():
        raise RuntimeError("sem rede")

    monkeypatch.setattr(admin_router, "_run_pipeline", _boom)

    tok = _register(client, "adm@x.com")
    _make_admin(client, "adm@x.com")
    h = {"Authorization": f"Bearer {tok}"}

    r = client.post("/admin/collect", headers=h)
    assert r.status_code == 202
    job = r.json()
    detail = client.get(f"/admin/jobs/{job['id']}", headers=h).json()
    assert detail["kind"] == "coleta"
    assert detail["status"] in ("success", "error")
    assert "pipeline falhou" in (detail["log"] or "")
