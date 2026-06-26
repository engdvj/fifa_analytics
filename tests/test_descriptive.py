"""Análise Descritiva: panorama agregado (total + tendência por rodada)."""

import pandas as pd

from fifa_analytics.analytics.descriptive import build_digest


def _frames():
    dim = pd.DataFrame([
        {"match_id": "m1", "status": "finalizado", "home_team": "A", "away_team": "B",
         "home_score": 3, "away_score": 0, "date_utc": "2026-06-01T00:00:00Z", "stage": "First Stage"},
        {"match_id": "m2", "status": "finalizado", "home_team": "C", "away_team": "D",
         "home_score": 1, "away_score": 1, "date_utc": "2026-06-02T00:00:00Z", "stage": "First Stage"},
        {"match_id": "m3", "status": "agendado", "home_team": "E", "away_team": "F",
         "home_score": None, "away_score": None, "date_utc": "2026-06-03T00:00:00Z", "stage": "First Stage"},
    ])
    wide = pd.DataFrame([
        {"match_id": "m1", "team": "A", "xg": 2.5, "amarelos": 1, "vermelhos": 0, "defesas_goleiro": 2, "save_pct_goleiro": 1.0},
        {"match_id": "m1", "team": "B", "xg": 0.3, "amarelos": 3, "vermelhos": 1, "defesas_goleiro": 7, "save_pct_goleiro": 0.7},
        {"match_id": "m2", "team": "C", "xg": 1.0, "amarelos": 0, "vermelhos": 0, "defesas_goleiro": 3, "save_pct_goleiro": 0.75},
        {"match_id": "m2", "team": "D", "xg": 1.1, "amarelos": 1, "vermelhos": 0, "defesas_goleiro": 4, "save_pct_goleiro": 0.8},
    ])
    timeline = pd.DataFrame([
        {"snapshot_jogo": 2, "team": "A", "jogos": 2, "gols": 5.0, "xg": 2.0, "xg_pj": 2.5, "xg_sofrido_pj": 0.3,
         "clean_sheet": 1, "posse": 0.6, "final_third_control": 70.0},
        {"snapshot_jogo": 2, "team": "B", "jogos": 2, "gols": 1.0, "xg": 3.0, "xg_pj": 0.3, "xg_sofrido_pj": 2.5,
         "clean_sheet": 0, "posse": 0.4, "final_third_control": 30.0},
    ])
    insights = pd.DataFrame([
        {"snapshot": 1, "match_id": "m1", "achado_key": "resumo", "detalhe": "A venceu", "evidencia": "{}"},
        {"snapshot": 2, "match_id": "m2", "achado_key": "resultado_vs_xg", "detalhe": "x", "evidencia": "{}"},
    ])
    return dim, wide, timeline, insights


def test_totais_total():
    dim, wide, timeline, insights = _frames()
    d = build_digest(dim, wide, timeline, insights)
    t = d["totais"]
    assert t["jogos"] == 2          # só finalizados
    assert t["gols"] == 5
    assert t["empates"] == 1
    assert t["decisivos"] == 1
    assert t["goleadas"] == 1
    assert d["fase"] == "Fase de Grupos"


def test_tendencia_por_rodada():
    dim, wide, timeline, insights = _frames()
    d = build_digest(dim, wide, timeline, insights)
    # 2 jogos da fase de grupos → uma única "Rodada 1" (bloco de até 24).
    assert len(d["tendencia"]) == 1
    r1 = d["tendencia"][0]
    assert r1["rodada"] == "Rodada 1" and r1["jogos"] == 2


def test_lideres_eficiencia_e_zebras():
    dim, wide, timeline, insights = _frames()
    d = build_digest(dim, wide, timeline, insights)
    cats = {l["categoria"]: l for l in d["lideres"]}
    assert cats["Melhor ataque"]["team"] == "A"
    assert cats["Melhor defesa"]["team"] == "A"
    # eficiência gols-xG: B fez 1 de 3.0 xG (-2.0) → menos aproveitou
    assert cats["Menos aproveitou (gols − xG)"]["team"] == "B"
    # zebra autossuficiente: traz o placar (C 1–1 D)
    assert d["zebras"] and "C" in d["zebras"][0]["titulo"]


def test_goleiro_em_recordes():
    dim, wide, timeline, insights = _frames()
    d = build_digest(dim, wide, timeline, insights)
    gk = next((r for r in d["recordes"] if r["label"] == "Goleiro da fase"), None)
    assert gk is not None and "B" in gk["valor"]  # 7 defesas
