"""Fundação da plataforma: loader + fluxo de bolão + pontuação na API.

Usa SQLite temporário e sobrescreve a dependência get_db. Não precisa de
Postgres nem de rede (parquet de matches é montado in-line).
"""

import warnings

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.app.db import Base, get_db
from api.app.loaders.load_matches import _rescore_match, load_matches
from api.app.main import app
from api.app.models import Match
from api.app.seed import seed_rules

warnings.filterwarnings("ignore")


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = TestingSession()
    seed_rules(s)  # regras builtin (lifespan não seeda o banco de teste)
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
    with TestClient(app) as c:
        c._SessionLocal = db_session  # acesso ao mesmo banco nos testes
        yield c
    app.dependency_overrides.clear()


def _auth_headers(client, username="davi", name="Davi", password="senha123"):
    """Registra um usuário e devolve o header Authorization Bearer.

    A API migrou para autenticação JWT por usuário: criar bolão / palpite deriva
    o usuário do token (não mais de owner_id/user_id no corpo).
    """
    tok = client.post(
        "/auth/register", json={"username": username, "name": name, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _matches_parquet(path):
    df = pd.DataFrame(
        [
            {
                "match_id": "copa_2026_jogo_001", "match_number": 1, "id_ifes": "1",
                "home_team": "A", "away_team": "B", "home_team_code": "A",
                "away_team_code": "B", "stage": "First Stage", "group": "Group A",
                "date_utc": "2026-06-11T19:00:00Z", "status": "agendado",
                "home_score": None, "away_score": None,
            }
        ]
    )
    df.to_parquet(path, index=False)
    return path


def test_loader_upsert_idempotente(client, tmp_path):
    parquet = _matches_parquet(tmp_path / "dim_match.parquet")
    s = client._SessionLocal()
    r1 = load_matches(s, parquet)
    r2 = load_matches(s, parquet)
    s.close()
    assert r1["inserted"] == 1 and r1["updated"] == 0
    assert r2["inserted"] == 0 and r2["updated"] == 1  # 2ª carga só atualiza
    assert client.get("/matches").json()[0]["match_id"] == "copa_2026_jogo_001"


def test_fluxo_bolao_e_pontuacao(client, tmp_path):
    s = client._SessionLocal()
    load_matches(s, _matches_parquet(tmp_path / "dim_match.parquet"))
    s.close()

    h = _auth_headers(client, username="davi", name="Davi")
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post(
        "/pools", json={"name": "P", "rule_id": rules["Clássico"]["id"]}, headers=h
    ).json()

    pred = client.post(
        f"/pools/{pool['id']}/predictions",
        json={"match_id": "copa_2026_jogo_001", "home_score": 2, "away_score": 0},
        headers=h,
    )
    assert pred.status_code == 201

    # jogo finaliza 2x0 → re-pontua (o que o loader faz ao detectar finalização)
    s = client._SessionLocal()
    m = s.get(Match, "copa_2026_jogo_001")
    m.status, m.home_score, m.away_score = "finalizado", 2, 0
    s.commit()
    _rescore_match(s, m)
    s.commit()
    s.close()

    ranking = client.get(f"/pools/{pool['id']}/ranking").json()["ranking"]
    assert ranking[0]["total_points"] == 5  # placar exato na regra Clássico


def test_palpite_em_jogo_finalizado_bloqueado(client, tmp_path):
    s = client._SessionLocal()
    load_matches(s, _matches_parquet(tmp_path / "dim_match.parquet"))
    m = s.get(Match, "copa_2026_jogo_001")
    m.status = "finalizado"
    s.commit()
    s.close()

    h = _auth_headers(client, username="ana", name="Ana")
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post(
        "/pools", json={"name": "P2", "rule_id": rules["Clássico"]["id"]}, headers=h
    ).json()
    r = client.post(
        f"/pools/{pool['id']}/predictions",
        json={"match_id": "copa_2026_jogo_001", "home_score": 1, "away_score": 1},
        headers=h,
    )
    assert r.status_code == 400
