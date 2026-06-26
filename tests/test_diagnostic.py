"""Análise Diagnóstica: achados do 'porquê' por jogo (sem rede)."""

import json

import pandas as pd

from fifa_analytics.analytics.diagnostic import build_insights


def _dim(rows):
    return pd.DataFrame(rows)


def _keys(df, match_id):
    return set(df[df["match_id"] == match_id]["achado_key"])


def _by_key(df, match_id, key):
    sub = df[(df["match_id"] == match_id) & (df["achado_key"] == key)]
    return sub.iloc[0] if not sub.empty else None


def test_vitoria_eficiente_contra_o_xg():
    """A venceu B 2-1 gerando MENOS xG → vitória eficiente + B mereceu mais."""
    dim = _dim([
        {"match_id": "m1", "match_number": 1, "status": "finalizado",
         "home_team": "A", "away_team": "B", "home_score": 2, "away_score": 1,
         "date_utc": "2026-06-01T00:00:00Z", "stage": "First Stage", "group": "Group A"},
    ])
    wide = pd.DataFrame([
        {"match_id": "m1", "team": "A", "xg": 0.8, "final_third_control": 40.0},
        {"match_id": "m1", "team": "B", "xg": 2.4, "final_third_control": 65.0},
    ])
    df = build_insights(wide, dim, write=False)

    resumo = _by_key(df, "m1", "resumo")
    assert resumo is not None and resumo["team"] == "A" and "eficiente" in resumo["titulo"]

    # B criou mais perigo mas perdeu → resultado contra o xG, sujeito = B.
    rvx = _by_key(df, "m1", "resultado_vs_xg")
    assert rvx is not None and rvx["team"] == "B" and rvx["direcao"] == "negativo"

    # B desperdiçou (2.4 xG, 1 gol → ratio 0.42).
    assert "finalizacao_desperdicio" in _keys(df, "m1")
    # B dominou o terço final (65%) mas perdeu → domínio estéril.
    esteril = _by_key(df, "m1", "dominio_esteril")
    assert esteril is not None and esteril["team"] == "B"
    # A venceu cedendo o controle (40%) → eficiente sem a bola.
    assert "eficiente_sem_bola" in _keys(df, "m1")


def test_evidencia_e_json_e_snapshot_cronologico():
    dim = _dim([
        {"match_id": "m2", "match_number": 8, "status": "finalizado",
         "home_team": "C", "away_team": "D", "home_score": 0, "away_score": 0,
         "date_utc": "2026-06-05T00:00:00Z", "stage": "First Stage", "group": "Group B"},
        {"match_id": "m1", "match_number": 1, "status": "finalizado",
         "home_team": "A", "away_team": "B", "home_score": 3, "away_score": 0,
         "date_utc": "2026-06-01T00:00:00Z", "stage": "First Stage", "group": "Group A"},
    ])
    wide = pd.DataFrame([
        {"match_id": "m1", "team": "A", "xg": 2.5},
        {"match_id": "m1", "team": "B", "xg": 0.3},
        {"match_id": "m2", "team": "C", "xg": 1.0},
        {"match_id": "m2", "team": "D", "xg": 1.1},
    ])
    df = build_insights(wide, dim, write=False)

    # snapshot é cronológico (m1 em 01/06 = snapshot 1; m2 em 05/06 = snapshot 2).
    assert _by_key(df, "m1", "resumo")["snapshot"] == 1
    assert _by_key(df, "m2", "resumo")["snapshot"] == 2

    # evidencia é JSON serializável (volta a dict).
    ev = json.loads(_by_key(df, "m1", "resumo")["evidencia"])
    assert ev["placar"] == "3–0" and ev["vencedor"] == "A"


def test_expulsao_e_contexto_de_forca():
    dim = _dim([
        {"match_id": "m1", "match_number": 1, "status": "finalizado",
         "home_team": "A", "away_team": "B", "home_score": 1, "away_score": 0,
         "date_utc": "2026-06-01T00:00:00Z", "stage": "First Stage", "group": "Group A"},
    ])
    wide = pd.DataFrame([
        {"match_id": "m1", "team": "A", "xg": 1.2, "vermelhos": 0},
        {"match_id": "m1", "team": "B", "xg": 0.4, "vermelhos": 1},
    ])
    # B (o batido) era o 3º colocado → A ganha "vitória de prestígio".
    timeline = pd.DataFrame([
        {"snapshot_jogo": 1, "team": "A", "ranking_score_geral": 10},
        {"snapshot_jogo": 1, "team": "B", "ranking_score_geral": 3},
    ])
    df = build_insights(wide, dim, timeline, write=False)

    exp = _by_key(df, "m1", "expulsao")
    assert exp is not None and exp["team"] == "B" and exp["severidade"] == "alta"

    prestigio = _by_key(df, "m1", "vitoria_prestigio")
    assert prestigio is not None and prestigio["team"] == "A"


def test_sem_jogos_finalizados_grava_vazio():
    dim = _dim([
        {"match_id": "m1", "match_number": 1, "status": "agendado",
         "home_team": "A", "away_team": "B", "home_score": None, "away_score": None,
         "date_utc": "2026-06-01T00:00:00Z", "stage": "First Stage", "group": "Group A"},
    ])
    df = build_insights(pd.DataFrame(), dim, write=False)
    assert df.empty


def test_finalizacao_clinica():
    dim = _dim([
        {"match_id": "m1", "match_number": 1, "status": "finalizado",
         "home_team": "A", "away_team": "B", "home_score": 4, "away_score": 0,
         "date_utc": "2026-06-01T00:00:00Z", "stage": "First Stage", "group": "Group A"},
    ])
    wide = pd.DataFrame([
        {"match_id": "m1", "team": "A", "xg": 1.5},   # 4 gols de 1.5 xG → clínico
        {"match_id": "m1", "team": "B", "xg": 0.5},
    ])
    df = build_insights(wide, dim, write=False)
    clinica = _by_key(df, "m1", "finalizacao_clinica")
    assert clinica is not None and clinica["team"] == "A" and clinica["direcao"] == "positivo"
