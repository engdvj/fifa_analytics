"""Bolões flexíveis: escopo, regra inline, aninhamento por fase, ranking de grupo.

SQLite temporário; matches montados in-line com fases distintas para exercitar
escopo e nest_by_stage."""

import warnings

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from api.app.db import Base, get_db
from api.app.loaders.load_matches import load_matches
from api.app.main import app
from api.app.models import Match, User
from api.app.scoring.recompute import recompute_pool_points
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
    with TestClient(app) as c:
        c._SessionLocal = db_session
        yield c
    app.dependency_overrides.clear()


def _headers(client, username="davi", name="Davi"):
    tok = client.post(
        "/auth/register", json={"username": username, "name": name, "password": "senha123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _seed_matches(client):
    """3 jogos: 2 na fase de grupos, 1 nas oitavas."""
    rows = [
        {
            "match_id": "copa_2026_jogo_001", "match_number": 1, "id_ifes": "1",
            "home_team": "A", "away_team": "B", "home_team_code": "A",
            "away_team_code": "B", "stage": "First Stage", "group": "Group A",
            "date_utc": "2026-06-11T19:00:00Z", "status": "agendado",
            "home_score": None, "away_score": None,
        },
        {
            "match_id": "copa_2026_jogo_002", "match_number": 2, "id_ifes": "2",
            "home_team": "C", "away_team": "D", "home_team_code": "C",
            "away_team_code": "D", "stage": "First Stage", "group": "Group A",
            "date_utc": "2026-06-12T19:00:00Z", "status": "agendado",
            "home_score": None, "away_score": None,
        },
        {
            "match_id": "copa_2026_jogo_050", "match_number": 50, "id_ifes": "50",
            "home_team": "E", "away_team": "F", "home_team_code": "E",
            "away_team_code": "F", "stage": "Round of 16", "group": None,
            "date_utc": "2026-07-01T19:00:00Z", "status": "agendado",
            "home_score": None, "away_score": None,
        },
    ]
    import os
    import tempfile

    df = pd.DataFrame(rows)
    p = os.path.join(tempfile.mkdtemp(), "dim_match.parquet")
    df.to_parquet(p, index=False)
    s = client._SessionLocal()
    load_matches(s, p)
    s.close()


def _criteria(client, h):
    return client.get("/scoring/criteria", headers=h).json()


def test_criteria_endpoint(client):
    h = _headers(client)
    data = _criteria(client, h)
    keys = {c["key"] for c in data["criteria"]}
    assert keys == {
        "exact_score", "correct_winner", "correct_goal_diff",
        "correct_home_goals", "correct_away_goals",
    }
    labels = {c["key"]: c["label"] for c in data["criteria"]}
    assert labels["exact_score"] == "Placar exato"
    assert labels["correct_winner"] == "Vencedor/empate"
    assert "max" in data["modes"] and "sum" in data["modes"]


def test_inline_spec_cria_regra(client):
    _seed_matches(client)
    h = _headers(client)
    pool = client.post(
        "/pools",
        json={"name": "Inline", "inline_spec": {"exact_score": 10}},
        headers=h,
    ).json()
    # a regra criada aparece na lista do usuário
    rules = client.get("/scoring/rules", headers=h).json()
    assert any(r["spec"] == {"exact_score": 10} and r["owner_id"] for r in rules)
    detail = client.get(f"/pools/{pool['id']}", headers=h).json()
    assert detail["rule"]["spec"] == {"exact_score": 10}


def test_palpite_salvo_so_admin_altera(client, db_session):
    _seed_matches(client)
    h = _headers(client, "ze", "Zé")
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post(
        "/pools",
        json={"name": "Lock", "rule_id": rules["Clássico"]["id"], "scope": {"type": "all"}},
        headers=h,
    ).json()
    body = {"match_id": "copa_2026_jogo_001", "home_score": 1, "away_score": 0}
    assert client.post(f"/pools/{pool['id']}/predictions", json=body, headers=h).status_code == 201
    # participante comum não pode alterar depois de salvo
    body2 = {"match_id": "copa_2026_jogo_001", "home_score": 3, "away_score": 3}
    assert client.post(f"/pools/{pool['id']}/predictions", json=body2, headers=h).status_code == 403
    # admin consegue alterar
    s = db_session()
    s.scalar(select(User).where(User.username == "ze")).is_admin = True
    s.commit()
    s.close()
    assert client.post(f"/pools/{pool['id']}/predictions", json=body2, headers=h).status_code == 201


def test_inline_spec_invalido_400(client):
    h = _headers(client)
    r = client.post(
        "/pools", json={"name": "X", "inline_spec": {"nao_existe": 5}}, headers=h
    )
    assert r.status_code == 400


def test_escopo_restringe_palpites(client):
    _seed_matches(client)
    h = _headers(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    # bolão só da fase de grupos
    pool = client.post(
        "/pools",
        json={
            "name": "Só grupos",
            "rule_id": rules["Clássico"]["id"],
            "scope": {"type": "stage", "stages": ["First Stage"]},
        },
        headers=h,
    ).json()

    # /matches devolve só os 2 jogos da fase de grupos
    ms = client.get(f"/pools/{pool['id']}/matches", headers=h).json()
    assert {m["match_id"] for m in ms} == {"copa_2026_jogo_001", "copa_2026_jogo_002"}

    # palpite num jogo no escopo: ok
    ok = client.post(
        f"/pools/{pool['id']}/predictions",
        json={"match_id": "copa_2026_jogo_001", "home_score": 2, "away_score": 0},
        headers=h,
    )
    assert ok.status_code == 201
    # palpite num jogo fora do escopo (oitavas): 400
    fora = client.post(
        f"/pools/{pool['id']}/predictions",
        json={"match_id": "copa_2026_jogo_050", "home_score": 1, "away_score": 0},
        headers=h,
    )
    assert fora.status_code == 400


def test_escopo_so_pontua_in_scope(client):
    """Palpite de jogo finalizado só conta se estiver no escopo do bolão."""
    _seed_matches(client)
    h = _headers(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post(
        "/pools",
        json={
            "name": "Grupos",
            "rule_id": rules["Clássico"]["id"],
            "scope": {"type": "matches", "match_ids": ["copa_2026_jogo_001"]},
        },
        headers=h,
    ).json()
    client.post(
        f"/pools/{pool['id']}/predictions",
        json={"match_id": "copa_2026_jogo_001", "home_score": 2, "away_score": 0},
        headers=h,
    )

    # finaliza o jogo e recalcula
    s = client._SessionLocal()
    m = s.get(Match, "copa_2026_jogo_001")
    m.status, m.home_score, m.away_score = "finalizado", 2, 0
    s.commit()
    recompute_pool_points(s)
    s.commit()
    s.close()

    ranking = client.get(f"/pools/{pool['id']}/ranking").json()["ranking"]
    assert ranking[0]["total_points"] == 5


def test_nest_by_stage_cria_filhos(client):
    _seed_matches(client)
    h = _headers(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    parent = client.post(
        "/pools",
        json={
            "name": "Copa toda",
            "rule_id": rules["Clássico"]["id"],
            "scope": {"type": "all"},
            "nest_by_stage": True,
        },
        headers=h,
    ).json()
    assert parent["is_group"] is True
    stages_filhos = {c["scope"]["stages"][0] for c in parent["children"]}
    assert stages_filhos == {"First Stage", "Round of 16"}


def test_ranking_grupo_agrega_filhos(client):
    _seed_matches(client)
    h = _headers(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    parent = client.post(
        "/pools",
        json={
            "name": "Grupo agregado",
            "rule_id": rules["Clássico"]["id"],
            "scope": {"type": "all"},
            "nest_by_stage": True,
        },
        headers=h,
    ).json()
    # acha o filho da fase de grupos e palpita nele
    child_grupos = next(
        c for c in parent["children"] if c["scope"]["stages"][0] == "First Stage"
    )
    child_oitavas = next(
        c for c in parent["children"] if c["scope"]["stages"][0] == "Round of 16"
    )
    client.post(
        f"/pools/{child_grupos['id']}/predictions",
        json={"match_id": "copa_2026_jogo_001", "home_score": 2, "away_score": 0},
        headers=h,
    )
    client.post(
        f"/pools/{child_oitavas['id']}/predictions",
        json={"match_id": "copa_2026_jogo_050", "home_score": 1, "away_score": 1},
        headers=h,
    )

    # finaliza ambos e recalcula
    s = client._SessionLocal()
    for mid, hs, as_ in [("copa_2026_jogo_001", 2, 0), ("copa_2026_jogo_050", 1, 1)]:
        m = s.get(Match, mid)
        m.status, m.home_score, m.away_score = "finalizado", hs, as_
    s.commit()
    recompute_pool_points(s)
    s.commit()
    s.close()

    grp = client.get(f"/pools/{parent['id']}/ranking").json()
    # exato nos dois (5+5) na regra Clássico
    assert grp["ranking"][0]["total_points"] == 10
    assert grp["ranking"][0]["predictions"] == 2
    # quebra por filho presente
    assert len(grp["children"]) == 2
    by_stage = {c["stage"]: c for c in grp["children"]}
    assert by_stage["First Stage"]["ranking"][0]["total_points"] == 5
    assert by_stage["Round of 16"]["ranking"][0]["total_points"] == 5


def _finaliza(client, *placares):
    """placares: (match_id, home, away)…"""
    s = client._SessionLocal()
    for mid, hs, as_ in placares:
        m = s.get(Match, mid)
        m.status, m.home_score, m.away_score = "finalizado", hs, as_
    s.commit()
    s.close()


def test_registro_bolao_encerrado(client):
    _seed_matches(client)
    h = _headers(client)  # davi = dono
    _finaliza(client, ("copa_2026_jogo_001", 2, 0), ("copa_2026_jogo_002", 1, 1))

    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post(
        "/pools",
        json={
            "name": "Bolão arquivado",
            "rule_id": rules["Clássico"]["id"],
            "scope": {"type": "stage", "stages": ["First Stage"]},
        },
        headers=h,
    ).json()

    ana = client.post("/users", json={"username": "ana", "name": "Ana"}).json()
    bia = client.post("/users", json={"username": "bia", "name": "Bia"}).json()

    # Ana crava os dois placares; Bia erra placar mas acerta o vencedor do jogo 1.
    payload = {"items": [
        {"user_id": ana["id"], "match_id": "copa_2026_jogo_001", "home_score": 2, "away_score": 0},
        {"user_id": ana["id"], "match_id": "copa_2026_jogo_002", "home_score": 1, "away_score": 1},
        {"user_id": bia["id"], "match_id": "copa_2026_jogo_001", "home_score": 3, "away_score": 1},
    ]}
    r = client.post(f"/pools/{pool['id']}/registro", json=payload, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["registered"] == 3 and data["scored"] == 3
    rank = {row["name"]: row["total_points"] for row in data["ranking"]}
    assert rank["Ana"] == 10   # exato (5) + exato (5)
    assert rank["Bia"] == 3    # só vencedor

    # o ranking público concorda com o resultado do registro
    rk2 = client.get(f"/pools/{pool['id']}/ranking").json()["ranking"]
    assert rk2[0]["name"] == "Ana" and rk2[0]["total_points"] == 10


def test_registro_so_dono(client):
    _seed_matches(client)
    h = _headers(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post(
        "/pools", json={"name": "X", "rule_id": rules["Clássico"]["id"]}, headers=h
    ).json()
    ana = client.post("/users", json={"username": "ana", "name": "Ana"}).json()
    h2 = _headers(client, username="outro", name="Outro")  # não é o dono
    r = client.post(
        f"/pools/{pool['id']}/registro",
        json={"items": [
            {"user_id": ana["id"], "match_id": "copa_2026_jogo_001", "home_score": 1, "away_score": 0},
        ]},
        headers=h2,
    )
    assert r.status_code == 403


def test_stats_participants_cruza_boloes(client):
    _seed_matches(client)
    h = _headers(client)
    _finaliza(client, ("copa_2026_jogo_001", 2, 0), ("copa_2026_jogo_002", 1, 1))
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post(
        "/pools", json={"name": "Arq", "rule_id": rules["Clássico"]["id"]}, headers=h
    ).json()
    ana = client.post("/users", json={"username": "ana", "name": "Ana"}).json()
    client.post(
        f"/pools/{pool['id']}/registro",
        json={"items": [
            {"user_id": ana["id"], "match_id": "copa_2026_jogo_001", "home_score": 2, "away_score": 0},
            {"user_id": ana["id"], "match_id": "copa_2026_jogo_002", "home_score": 0, "away_score": 0},
        ]},
        headers=h,
    )
    parts = client.get("/stats/participants", headers=h).json()["participants"]
    ana_row = next(p for p in parts if p["name"] == "Ana")
    assert ana_row["predictions"] == 2
    assert ana_row["pools"] == 1
    assert ana_row["exact_scores"] == 1        # cravou 2-0; errou 0-0 (real 1-1)
    assert ana_row["correct_winners"] == 2     # 2-0 e empate (0-0 vs 1-1) acertam o resultado
    assert ana_row["total_points"] == 8        # 5 (exato) + 3 (vencedor/empate)


def test_delete_pool_remove_palpites(client):
    _seed_matches(client)
    h = _headers(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post(
        "/pools", json={"name": "Apagável", "rule_id": rules["Clássico"]["id"]}, headers=h
    ).json()
    client.post(
        f"/pools/{pool['id']}/predictions",
        json={"match_id": "copa_2026_jogo_001", "home_score": 1, "away_score": 0},
        headers=h,
    )
    r = client.delete(f"/pools/{pool['id']}", headers=h)
    assert r.status_code == 200 and r.json()["deleted"] == 1
    # sumiu da listagem e o GET dá 404
    assert client.get(f"/pools/{pool['id']}", headers=h).status_code == 404
    assert all(p["id"] != pool["id"] for p in client.get("/pools", headers=h).json())


def test_delete_pool_so_dono(client):
    _seed_matches(client)
    h = _headers(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post(
        "/pools", json={"name": "X", "rule_id": rules["Clássico"]["id"]}, headers=h
    ).json()
    h2 = _headers(client, username="outro", name="Outro")
    assert client.delete(f"/pools/{pool['id']}", headers=h2).status_code == 403


def test_delete_grupo_cascateia_filhos(client):
    _seed_matches(client)
    h = _headers(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    parent = client.post(
        "/pools",
        json={"name": "Grupo", "rule_id": rules["Clássico"]["id"],
              "scope": {"type": "all"}, "nest_by_stage": True},
        headers=h,
    ).json()
    child_id = parent["children"][0]["id"]
    assert client.delete(f"/pools/{parent['id']}", headers=h).status_code == 200
    # filho também sumiu
    assert client.get(f"/pools/{child_id}", headers=h).status_code == 404


def _make_admin(client, username="davi"):
    s = client._SessionLocal()
    u = s.scalar(select(User).where(User.username == username))
    u.is_admin = True
    s.commit()
    s.close()


def _user_id(client, username):
    s = client._SessionLocal()
    uid = s.scalar(select(User.id).where(User.username == username))
    s.close()
    return uid


def test_update_pool_renomeia_e_repontua(client):
    _seed_matches(client)
    h = _headers(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post("/pools", json={"name": "Antigo", "rule_id": rules["Clássico"]["id"]}, headers=h).json()
    client.post(
        f"/pools/{pool['id']}/predictions",
        json={"match_id": "copa_2026_jogo_001", "home_score": 2, "away_score": 0},
        headers=h,
    )
    _finaliza(client, ("copa_2026_jogo_001", 2, 0))
    s = client._SessionLocal(); recompute_pool_points(s); s.commit(); s.close()
    # Clássico: placar exato = 5
    assert client.get(f"/pools/{pool['id']}/ranking").json()["ranking"][0]["total_points"] == 5

    # renomeia + troca regra → repontua (Soma de acertos: vencedor 2 + mandante 1 + visitante 1 = 4)
    r = client.patch(f"/pools/{pool['id']}", json={"name": "Novo", "rule_id": rules["Soma de acertos"]["id"]}, headers=h)
    assert r.status_code == 200 and r.json()["name"] == "Novo"
    assert client.get(f"/pools/{pool['id']}/ranking").json()["ranking"][0]["total_points"] == 4


def test_update_pool_so_dono(client):
    _seed_matches(client)
    h = _headers(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post("/pools", json={"name": "X", "rule_id": rules["Clássico"]["id"]}, headers=h).json()
    h2 = _headers(client, username="outro", name="Outro")
    assert client.patch(f"/pools/{pool['id']}", json={"name": "hack"}, headers=h2).status_code == 403


def test_update_user(client):
    h = _headers(client)
    _make_admin(client)
    ana = client.post("/users", json={"username": "ana", "name": "Ana"}).json()
    r = client.patch(f"/users/{ana['id']}", json={"name": "Ana Maria"}, headers=h)
    assert r.status_code == 200 and r.json()["name"] == "Ana Maria"
    assert client.get(f"/users/{ana['id']}").json()["name"] == "Ana Maria"


def test_delete_user_remove_historico(client):
    _seed_matches(client)
    h = _headers(client)
    _make_admin(client)
    _finaliza(client, ("copa_2026_jogo_001", 2, 0))
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post("/pools", json={"name": "P", "rule_id": rules["Clássico"]["id"]}, headers=h).json()
    ana = client.post("/users", json={"username": "ana", "name": "Ana"}).json()
    client.post(
        f"/pools/{pool['id']}/registro",
        json={"items": [{"user_id": ana["id"], "match_id": "copa_2026_jogo_001", "home_score": 2, "away_score": 0}]},
        headers=h,
    )
    assert any(r["name"] == "Ana" for r in client.get(f"/pools/{pool['id']}/ranking").json()["ranking"])
    assert client.delete(f"/users/{ana['id']}", headers=h).status_code == 200
    assert client.get(f"/users/{ana['id']}").status_code == 404
    assert all(r["name"] != "Ana" for r in client.get(f"/pools/{pool['id']}/ranking").json()["ranking"])


def test_delete_user_bloqueia_se_dono(client):
    _seed_matches(client)
    h = _headers(client)
    _make_admin(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    client.post("/pools", json={"name": "Meu", "rule_id": rules["Clássico"]["id"]}, headers=h)
    davi = _user_id(client, "davi")
    assert client.delete(f"/users/{davi}", headers=h).status_code == 400


def test_rules_crud(client):
    h = _headers(client)
    rule = client.post("/scoring/rules", json={"name": "Minha", "spec": {"exact_score": 9}}, headers=h).json()
    r = client.patch(
        f"/scoring/rules/{rule['id']}",
        json={"name": "Minha v2", "spec": {"exact_score": 7, "correct_winner": 2}},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Minha v2" and r.json()["spec"]["exact_score"] == 7
    assert client.delete(f"/scoring/rules/{rule['id']}", headers=h).status_code == 200


def test_rule_builtin_protegida(client):
    h = _headers(client)
    rules = {r["name"]: r for r in client.get("/scoring/rules", headers=h).json()}
    cid = rules["Clássico"]["id"]
    assert client.patch(f"/scoring/rules/{cid}", json={"name": "x"}, headers=h).status_code == 403
    assert client.delete(f"/scoring/rules/{cid}", headers=h).status_code == 403


def test_rule_em_uso_nao_exclui(client):
    _seed_matches(client)
    h = _headers(client)
    rule = client.post("/scoring/rules", json={"name": "EmUso", "spec": {"exact_score": 5}}, headers=h).json()
    client.post("/pools", json={"name": "P", "rule_id": rule["id"]}, headers=h)
    assert client.delete(f"/scoring/rules/{rule['id']}", headers=h).status_code == 400


def test_admin_nao_vira_membro(client):
    _seed_matches(client)
    h = _headers(client)
    _make_admin(client)  # davi = admin → só administra, não joga
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post("/pools", json={"name": "P", "rule_id": rules["Clássico"]["id"]}, headers=h).json()
    detail = client.get(f"/pools/{pool['id']}", headers=h).json()
    assert detail["members"] == []


def test_transfer_pool(client):
    _seed_matches(client)
    h = _headers(client)
    _make_admin(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post("/pools", json={"name": "P", "rule_id": rules["Clássico"]["id"]}, headers=h).json()
    ana = client.post("/users", json={"username": "ana", "name": "Ana"}).json()
    r = client.post(f"/pools/{pool['id']}/transfer", json={"user_id": ana["id"]}, headers=h)
    assert r.status_code == 200
    assert r.json()["owner_id"] == ana["id"]
    assert ana["id"] in {m["user_id"] for m in r.json()["members"]}  # novo dono vira jogador


def test_admin_all_pools(client):
    _seed_matches(client)
    h = _headers(client)
    _make_admin(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    client.post("/pools", json={"name": "P1", "rule_id": rules["Clássico"]["id"]}, headers=h)
    all_pools = client.get("/pools/admin/all", headers=h).json()
    p1 = next(p for p in all_pools if p["name"] == "P1")
    assert p1["owner_name"] and "members" in p1 and "rule_name" in p1
    # não-admin não acessa
    h2 = _headers(client, username="outro", name="Outro")
    assert client.get("/pools/admin/all", headers=h2).status_code == 403


def test_admin_ve_todos_boloes(client):
    _seed_matches(client)
    h = _headers(client)  # davi (comum) cria um bolão
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post("/pools", json={"name": "Do Davi", "rule_id": rules["Clássico"]["id"]}, headers=h).json()
    # admin separado, que NÃO participa, deve ver mesmo assim
    h2 = _headers(client, username="adm", name="Adm")
    _make_admin(client, "adm")
    pools = client.get("/pools", headers=h2).json()
    assert any(p["id"] == pool["id"] for p in pools)


def test_pool_grid(client):
    _seed_matches(client)
    h = _headers(client)
    _make_admin(client)  # davi = admin
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    pool = client.post("/pools", json={"name": "P", "rule_id": rules["Clássico"]["id"]}, headers=h).json()
    ana = client.post("/users", json={"username": "ana", "name": "Ana"}).json()
    client.post(f"/pools/{pool['id']}/registro", json={"items": [
        {"user_id": ana["id"], "match_id": "copa_2026_jogo_001", "home_score": 2, "away_score": 0},
    ]}, headers=h)
    grid = client.get(f"/pools/{pool['id']}/grid", headers=h).json()
    assert any(p["name"] == "Ana" for p in grid["participants"])
    assert any(gp["user_id"] == ana["id"] and gp["match_id"] == "copa_2026_jogo_001" for gp in grid["predictions"])
    assert len(grid["matches"]) >= 1
    # quem não é dono nem admin não acessa a grade
    h2 = _headers(client, username="x", name="X")
    assert client.get(f"/pools/{pool['id']}/grid", headers=h2).status_code == 403


def test_grupo_nao_recebe_palpite_direto(client):
    _seed_matches(client)
    h = _headers(client)
    rules = {r["name"]: r for r in client.get("/pools/rules", headers=h).json()}
    parent = client.post(
        "/pools",
        json={
            "name": "G", "rule_id": rules["Clássico"]["id"],
            "scope": {"type": "all"}, "nest_by_stage": True,
        },
        headers=h,
    ).json()
    r = client.post(
        f"/pools/{parent['id']}/predictions",
        json={"match_id": "copa_2026_jogo_001", "home_score": 1, "away_score": 0},
        headers=h,
    )
    assert r.status_code == 400
