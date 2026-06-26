"""Análise Exploratória: EDA com sentido (sem rede)."""

import pandas as pd

from fifa_analytics.analytics.exploratory import build_exploratory


def _frames(n=8):
    """n jogos onde a casa cria mais xG e vence — xG deve liderar 'o que decide'."""
    dim_rows, wide_rows = [], []
    for i in range(n):
        mid = f"m{i}"
        dim_rows.append({"match_id": mid, "status": "finalizado", "home_team": f"H{i}", "away_team": f"A{i}",
                         "home_score": 2, "away_score": 0, "date_utc": f"2026-06-{i+1:02d}T00:00:00Z", "stage": "First Stage"})
        wide_rows += [
            {"match_id": mid, "team": f"H{i}", "xg": 2.0 + i * 0.1, "chutes_no_alvo": 6, "posse": 0.6, "final_third_control": 65.0},
            {"match_id": mid, "team": f"A{i}", "xg": 0.5, "chutes_no_alvo": 1, "posse": 0.4, "final_third_control": 35.0},
        ]
    timeline = pd.DataFrame([
        {"snapshot_jogo": n, "team": "H0", "jogos": 2, "points": 6, "xg_pj": 2.5, "gols_pj": 3.0, "xg_sofrido_pj": 0.3,
         "clean_sheet": 1, "estilo_jogo": "Pressão Alta", "estilo_posse": 80.0, "estilo_verticalidade": 30.0,
         "fase_bola_parada": 5.0, "fase_contra_ataque": 2.0, "fase_terceiro_final": 9.0, "fase_bola_longa": 1.0, "fase_pressao_alta": 8.0},
        {"snapshot_jogo": n, "team": "A0", "jogos": 2, "points": 0, "xg_pj": 1.0, "gols_pj": 0.4, "xg_sofrido_pj": 2.0,
         "clean_sheet": 0, "estilo_jogo": "Retranca", "estilo_posse": 30.0, "estilo_verticalidade": 70.0,
         "fase_bola_parada": 2.0, "fase_contra_ataque": 6.0, "fase_terceiro_final": 3.0, "fase_bola_longa": 4.0, "fase_pressao_alta": 3.0},
    ])
    return pd.DataFrame(dim_rows), pd.DataFrame(wide_rows), timeline


def test_decide_xg_lidera():
    dim, wide, tl = _frames()
    d = build_exploratory(dim, wide, tl)
    assert d["amostra"] == 16
    xg = next(x for x in d["decide"] if x["metric"] == "xg")
    assert xg["corr"] > 0.8
    assert d["decide"] == sorted(d["decide"], key=lambda x: x["corr"], reverse=True)


def test_quadrante_e_eficiencia():
    dim, wide, tl = _frames()
    d = build_exploratory(dim, wide, tl)
    # H0 cria acima da média e converte (3.0 gols de 2.5 xG) → Elite
    h0 = next(p for p in d["quadrante"]["pontos"] if p["team"] == "H0")
    assert h0["perfil"] == "Elite" and h0["converte"] > 0
    # eficiência ordenada por overperf desc
    assert d["eficiencia"][0]["team"] == "H0"


def test_estilo_resultado_e_fases_e_defesa():
    dim, wide, tl = _frames()
    d = build_exploratory(dim, wide, tl)
    # Pressão Alta (H0, 6 pts em 2 jogos = 3 pts/jogo) lidera
    assert d["estilo_resultado"][0]["arquetipo"] == "Pressão Alta"
    # líder de cada fase
    fases = {f["fase"]: f["team"] for f in d["fases"]}
    assert fases["Bola parada"] == "H0" and fases["Contra-ataque"] == "A0"
    # melhor defesa = H0 (0.3 xG sofrido)
    assert d["defesa"][0]["team"] == "H0"
