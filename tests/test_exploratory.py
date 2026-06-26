"""Análise Exploratória: padrões e correlações (sem rede)."""

import numpy as np
import pandas as pd

from fifa_analytics.analytics.exploratory import build_exploratory


def _frames(n=8):
    """n jogos sintéticos onde quem cria mais xG vence — correlação xG×saldo ~ +1."""
    dim_rows, wide_rows, tl_rows = [], [], []
    for i in range(n):
        mid = f"m{i}"
        # casa cria mais xG e vence por mais gols
        hs, as_ = 2, 0
        xg_h, xg_a = 2.0 + i * 0.1, 0.5
        dim_rows.append({"match_id": mid, "status": "finalizado", "home_team": f"H{i}", "away_team": f"A{i}",
                         "home_score": hs, "away_score": as_, "date_utc": f"2026-06-{i+1:02d}T00:00:00Z", "stage": "First Stage"})
        wide_rows += [
            {"match_id": mid, "team": f"H{i}", "xg": xg_h, "chutes_no_alvo": 6, "posse": 0.6, "final_third_control": 65.0},
            {"match_id": mid, "team": f"A{i}", "xg": xg_a, "chutes_no_alvo": 1, "posse": 0.4, "final_third_control": 35.0},
        ]
    timeline = pd.DataFrame([
        {"snapshot_jogo": n, "team": "H0", "xg_pj": 2.5, "gols_pj": 3.0,
         "estilo_jogo": "Posse", "estilo_posse": 80.0, "estilo_verticalidade": 30.0, "estilo_pressao": 60.0},
        {"snapshot_jogo": n, "team": "A0", "xg_pj": 1.5, "gols_pj": 0.5,
         "estilo_jogo": "Retranca", "estilo_posse": 30.0, "estilo_verticalidade": 70.0, "estilo_pressao": 40.0},
    ])
    return pd.DataFrame(dim_rows), pd.DataFrame(wide_rows), timeline


def test_decisao_xg_lidera():
    dim, wide, tl = _frames()
    d = build_exploratory(dim, wide, tl)
    assert d["amostra"] == 16
    # xG entre as métricas mais correlacionadas com o saldo (forte e positiva)
    xg = next(x for x in d["decisao"] if x["metric"] == "xg")
    assert xg["corr"] > 0.8
    assert d["decisao"] == sorted(d["decisao"], key=lambda x: x["corr"], reverse=True)


def test_eficiencia_e_estilos():
    dim, wide, tl = _frames()
    d = build_exploratory(dim, wide, tl)
    # eficiência: H0 rende acima do xG (3.0 gols de 2.5 xG)
    h0 = next(e for e in d["eficiencia"] if e["team"] == "H0")
    assert h0["gols"] > h0["xg"]
    # mapa de estilos traz arquétipo e eixos
    estilo = next(p for p in d["estilos"] if p["team"] == "H0")
    assert estilo["arquetipo"] == "Posse" and estilo["posse"] == 80.0


def test_correlacoes_pares():
    dim, wide, tl = _frames()
    d = build_exploratory(dim, wide, tl)
    assert d["correlacoes"]  # ao menos um par
    assert all({"a", "b", "corr"}.issubset(c) for c in d["correlacoes"])


def test_amostra_insuficiente():
    dim, wide, tl = _frames(n=2)  # 4 team-games < mínimo
    d = build_exploratory(dim, wide, tl)
    assert "decisao" not in d  # retorna só {amostra}
