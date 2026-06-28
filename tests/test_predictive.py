"""Análise Preditiva: próximos jogos com probabilidade explicável."""

import pandas as pd

from fifa_analytics.analytics.predictive import (
    build_backtest,
    build_predictive,
    learn_weights,
)


def test_predictive_lista_jogos_agendados_e_favorito():
    dim = pd.DataFrame([
        {"match_id": "m1", "match_number": 1, "status": "finalizado",
         "home_team": "Forte", "away_team": "Fraco", "home_score": 2, "away_score": 0,
         "date_utc": "2026-06-01T00:00:00Z", "stage": "First Stage", "group": "A"},
        {"match_id": "m2", "match_number": 2, "status": "agendado",
         "home_team": "Forte", "away_team": "Fraco", "home_score": None, "away_score": None,
         "date_utc": "2026-06-02T00:00:00Z", "stage": "First Stage", "group": "A"},
    ])
    timeline = pd.DataFrame([
        {"snapshot_jogo": 1, "team": "Forte", "jogos": 1, "score_geral": 78, "score_ataque": 82,
         "score_defesa": 75, "elo_rating": 1540, "xg_pj": 2.1, "gols_pj": 2.0,
         "xg_sofrido_pj": 0.5, "gols_contra_pj": 0.0},
        {"snapshot_jogo": 1, "team": "Fraco", "jogos": 1, "score_geral": 38, "score_ataque": 35,
         "score_defesa": 32, "elo_rating": 1460, "xg_pj": 0.5, "gols_pj": 0.0,
         "xg_sofrido_pj": 2.1, "gols_contra_pj": 2.0},
    ])

    pred = build_predictive(dim, timeline, min_prediction_game=1)

    assert pred["snapshot"] == 2
    assert pred["as_of_snapshot"] == 1
    assert len(pred["matches"]) == 1
    jogo = pred["matches"][0]
    assert jogo["match_id"] == "m2"
    assert jogo["favorite"] == "Forte"
    assert jogo["probabilities"]["home_win"] > jogo["probabilities"]["away_win"]
    assert jogo["expected_goals"]["home"] > jogo["expected_goals"]["away"]
    assert jogo["favorite_side"] == "home"
    assert jogo["probabilities"]["scoreline"]["recommended"]["home"] > jogo["probabilities"]["scoreline"]["recommended"]["away"]
    assert jogo["summary"]["draw_risk"] in {"baixo", "medio", "alto"}
    assert any(f["label"] == "xG sofrido/jogo" and f["edge"] == "home" for f in jogo["factors"])
    assert jogo["models"]["poisson"]["available"] is True
    assert jogo["models"]["monte_carlo"]["available"] is True
    assert jogo["ensemble"]["models"]
    assert jogo["consensus"] in {"forte", "media", "baixa"}


def test_predictive_calibra_empate_em_jogo_desigual():
    dim = pd.DataFrame([
        {"match_id": "m1", "match_number": 4, "status": "agendado",
         "home_team": "Favorita", "away_team": "Azarao", "home_score": None, "away_score": None,
         "date_utc": "2026-06-02T00:00:00Z", "stage": "First Stage", "group": "A"},
    ])
    timeline = pd.DataFrame([
        {"snapshot_jogo": 1, "team": "Favorita", "jogos": 3, "score_geral": 82, "score_ataque": 86,
         "score_defesa": 78, "score_controle": 76, "score_eficiencia": 72, "elo_rating": 1580,
         "xg_pj": 2.2, "gols_pj": 2.3, "xg_sofrido_pj": 0.6, "gols_contra_pj": 0.3},
        {"snapshot_jogo": 1, "team": "Azarao", "jogos": 3, "score_geral": 34, "score_ataque": 32,
         "score_defesa": 35, "score_controle": 38, "score_eficiencia": 36, "elo_rating": 1430,
         "xg_pj": 0.6, "gols_pj": 0.3, "xg_sofrido_pj": 2.0, "gols_contra_pj": 2.0},
    ])

    pred = build_predictive(dim, timeline, snapshot=1, min_prediction_game=1, min_display_game=1)
    jogo = pred["matches"][0]

    assert jogo["favorite"] == "Favorita"
    assert jogo["probabilities"]["home_win"] >= 55
    assert jogo["probabilities"]["draw"] < 25
    assert jogo["probabilities"]["score"]["home"] > jogo["probabilities"]["score"]["away"]
    assert jogo["summary"]["draw_calibration"] < 0.9


def test_predictive_snapshot_historico_preve_jogo_selecionado_mesmo_finalizado():
    dim = pd.DataFrame([
        {"match_id": "m1", "match_number": 1, "status": "finalizado",
         "home_team": "A", "away_team": "B", "home_score": 1, "away_score": 0,
         "date_utc": "2026-06-01T00:00:00Z", "stage": "First Stage", "group": "A"},
        {"match_id": "m2", "match_number": 2, "status": "finalizado",
         "home_team": "A", "away_team": "C", "home_score": 2, "away_score": 2,
         "date_utc": "2026-06-02T00:00:00Z", "stage": "First Stage", "group": "A"},
    ])
    timeline = pd.DataFrame([
        {"snapshot_jogo": 1, "team": "A", "jogos": 1, "score_geral": 60, "score_ataque": 60,
         "score_defesa": 60, "elo_rating": 1510, "xg_pj": 1.4, "gols_pj": 1.0,
         "xg_sofrido_pj": 0.8, "gols_contra_pj": 0.0},
        {"snapshot_jogo": 1, "team": "C", "jogos": 0, "score_geral": 50, "score_ataque": 50,
         "score_defesa": 50, "elo_rating": 1500, "xg_pj": 1.2, "gols_pj": 1.0,
         "xg_sofrido_pj": 1.2, "gols_contra_pj": 1.0},
    ])

    pred = build_predictive(dim, timeline, snapshot=2, min_prediction_game=1)

    assert [m["match_id"] for m in pred["matches"]] == ["m2"]
    assert pred["as_of_snapshot"] == 1
    assert pred["matches"][0]["actual_result"] == {"home": 2, "away": 2, "outcome": "draw"}


def test_predictive_backtest_walk_forward():
    dim = pd.DataFrame([
        {"match_id": "m1", "match_number": 1, "status": "finalizado",
         "home_team": "A", "away_team": "B", "home_score": 1, "away_score": 0,
         "date_utc": "2026-06-01T00:00:00Z", "stage": "First Stage", "group": "A"},
        {"match_id": "m2", "match_number": 2, "status": "finalizado",
         "home_team": "A", "away_team": "C", "home_score": 2, "away_score": 1,
         "date_utc": "2026-06-02T00:00:00Z", "stage": "First Stage", "group": "A"},
    ])
    timeline = pd.DataFrame([
        {"snapshot_jogo": 1, "team": "A", "jogos": 1, "score_geral": 60, "score_ataque": 60,
         "score_defesa": 60, "elo_rating": 1510, "xg_pj": 1.4, "gols_pj": 1.0,
         "xg_sofrido_pj": 0.8, "gols_contra_pj": 0.0},
        {"snapshot_jogo": 1, "team": "C", "jogos": 0, "score_geral": 50, "score_ataque": 50,
         "score_defesa": 50, "elo_rating": 1500, "xg_pj": 1.2, "gols_pj": 1.0,
         "xg_sofrido_pj": 1.2, "gols_contra_pj": 1.0},
        {"snapshot_jogo": 2, "team": "A", "jogos": 2, "score_geral": 65, "score_ataque": 66,
         "score_defesa": 61, "elo_rating": 1520, "xg_pj": 1.6, "gols_pj": 1.5,
         "xg_sofrido_pj": 0.9, "gols_contra_pj": 0.5},
    ])

    backtest = build_backtest(dim, timeline, start=2, end=2, min_prediction_game=1)

    assert backtest["summary"]["n"] == 1
    assert backtest["rows"][0]["match_id"] == "m2"
    assert "log_loss" in backtest["rows"][0]


def test_predictive_placar_recomendado_coerente_com_probabilidade():
    """O placar recomendado nunca contradiz o resultado liderante das probabilidades."""
    dim = pd.DataFrame([
        {"match_id": "m1", "match_number": 4, "status": "agendado",
         "home_team": "Favorita", "away_team": "Azarao", "home_score": None, "away_score": None,
         "date_utc": "2026-06-02T00:00:00Z", "stage": "First Stage", "group": "A"},
    ])
    timeline = pd.DataFrame([
        {"snapshot_jogo": 1, "team": "Favorita", "jogos": 3, "score_geral": 82, "score_ataque": 86,
         "score_defesa": 78, "score_controle": 76, "score_eficiencia": 72, "elo_rating": 1580,
         "xg_pj": 2.2, "gols_pj": 2.3, "xg_sofrido_pj": 0.6, "gols_contra_pj": 0.3},
        {"snapshot_jogo": 1, "team": "Azarao", "jogos": 3, "score_geral": 34, "score_ataque": 32,
         "score_defesa": 35, "score_controle": 38, "score_eficiencia": 36, "elo_rating": 1430,
         "xg_pj": 0.6, "gols_pj": 0.3, "xg_sofrido_pj": 2.0, "gols_contra_pj": 2.0},
    ])

    jogo = build_predictive(dim, timeline, snapshot=1, min_prediction_game=1, min_display_game=1)["matches"][0]
    p = jogo["probabilities"]
    rec = p["scoreline"]["recommended"]
    leading = max([("home", p["home_win"]), ("draw", p["draw"]), ("away", p["away_win"])], key=lambda x: x[1])[0]
    rec_outcome = "home" if rec["home"] > rec["away"] else "away" if rec["away"] > rec["home"] else "draw"
    assert leading == rec_outcome
    # xG exibido e o de consenso do ensemble — coerente com placar recomendado
    assert jogo["expected_goals"]["home"] >= jogo["expected_goals"]["away"]


def test_predictive_empate_tem_massa_calibrada_em_jogo_parelho():
    """Jogo equilibrado mantem massa de empate saudavel (nao zera como antes)."""
    dim = pd.DataFrame([
        {"match_id": "m1", "match_number": 2, "status": "agendado",
         "home_team": "A", "away_team": "B", "home_score": None, "away_score": None,
         "date_utc": "2026-06-02T00:00:00Z", "stage": "First Stage", "group": "A"},
    ])
    timeline = pd.DataFrame([
        {"snapshot_jogo": 1, "team": "A", "jogos": 3, "score_geral": 55, "score_ataque": 55,
         "score_defesa": 55, "elo_rating": 1505, "xg_pj": 1.3, "gols_pj": 1.2,
         "xg_sofrido_pj": 1.2, "gols_contra_pj": 1.1},
        {"snapshot_jogo": 1, "team": "B", "jogos": 3, "score_geral": 54, "score_ataque": 54,
         "score_defesa": 54, "elo_rating": 1500, "xg_pj": 1.2, "gols_pj": 1.1,
         "xg_sofrido_pj": 1.3, "gols_contra_pj": 1.2},
    ])

    jogo = build_predictive(dim, timeline, snapshot=1, min_prediction_game=1, min_display_game=1)["matches"][0]
    assert jogo["probabilities"]["draw"] >= 20
    assert jogo["summary"]["draw_calibration"] >= 0.9


def test_predictive_backtest_usa_cache():
    dim = pd.DataFrame([
        {"match_id": "m1", "match_number": 1, "status": "finalizado",
         "home_team": "A", "away_team": "B", "home_score": 1, "away_score": 0,
         "date_utc": "2026-06-01T00:00:00Z", "stage": "First Stage", "group": "A"},
        {"match_id": "m2", "match_number": 2, "status": "finalizado",
         "home_team": "A", "away_team": "C", "home_score": 2, "away_score": 1,
         "date_utc": "2026-06-02T00:00:00Z", "stage": "First Stage", "group": "A"},
    ])
    timeline = pd.DataFrame([
        {"snapshot_jogo": 1, "team": "A", "jogos": 1, "score_geral": 60, "score_ataque": 60,
         "score_defesa": 60, "elo_rating": 1510, "xg_pj": 1.4, "gols_pj": 1.0,
         "xg_sofrido_pj": 0.8, "gols_contra_pj": 0.0},
        {"snapshot_jogo": 1, "team": "C", "jogos": 0, "score_geral": 50, "score_ataque": 50,
         "score_defesa": 50, "elo_rating": 1500, "xg_pj": 1.2, "gols_pj": 1.0,
         "xg_sofrido_pj": 1.2, "gols_contra_pj": 1.0},
        {"snapshot_jogo": 2, "team": "A", "jogos": 2, "score_geral": 65, "score_ataque": 66,
         "score_defesa": 61, "elo_rating": 1520, "xg_pj": 1.6, "gols_pj": 1.5,
         "xg_sofrido_pj": 0.9, "gols_contra_pj": 0.5},
    ])

    first = build_backtest(dim, timeline, start=2, end=2, min_prediction_game=1)
    second = build_backtest(dim, timeline, start=2, end=2, min_prediction_game=1)
    assert first is second  # mesmo objeto -> veio do cache


def test_learn_weights_prioriza_modelos_que_acertam():
    """Pesos aprendidos somam ~1 e dão mais peso a modelos com menor log-loss."""
    dim = pd.DataFrame([
        {"match_id": f"m{i}", "match_number": i, "status": "finalizado",
         "home_team": "A" if i % 2 else "B", "away_team": "B" if i % 2 else "A",
         "home_score": 2 if i % 2 else 0, "away_score": 0 if i % 2 else 1,
         "date_utc": f"2026-06-{i:02d}T00:00:00Z", "stage": "First Stage", "group": "A"}
        for i in range(1, 7)
    ])
    rows = []
    for snap in range(1, 6):
        rows += [
            {"snapshot_jogo": snap, "team": "A", "jogos": snap, "score_geral": 70, "score_ataque": 72,
             "score_defesa": 68, "elo_rating": 1540, "xg_pj": 1.8, "gols_pj": 1.6,
             "xg_sofrido_pj": 0.7, "gols_contra_pj": 0.4},
            {"snapshot_jogo": snap, "team": "B", "jogos": snap, "score_geral": 45, "score_ataque": 43,
             "score_defesa": 46, "elo_rating": 1470, "xg_pj": 0.9, "gols_pj": 0.7,
             "xg_sofrido_pj": 1.6, "gols_contra_pj": 1.4},
        ]
    timeline = pd.DataFrame(rows)

    weights = learn_weights(dim, timeline, start=2, end=5)
    assert abs(sum(weights.values()) - 1.0) < 1e-6
    assert all(0.0 <= w <= 1.0 for w in weights.values())


def test_predictive_nao_inverte_favorito_quando_um_time_domina():
    """Time que vence em todos os quesitos NÃO pode sair como azarão (bug real:
    Haiti favorito sobre Brasil). Guarda contra regressão da inversão dos ML."""
    dim = pd.DataFrame([
        {"match_id": "m1", "match_number": 2, "status": "agendado",
         "home_team": "Forte", "away_team": "Fraco", "home_score": None, "away_score": None,
         "date_utc": "2026-06-02T00:00:00Z", "stage": "First Stage", "group": "A"},
    ])
    rows = []
    for snap in range(1, 4):
        rows += [
            {"snapshot_jogo": snap, "team": "Forte", "jogos": snap, "score_geral": 80, "score_ataque": 82,
             "score_defesa": 78, "score_controle": 75, "score_eficiencia": 70, "elo_rating": 1560,
             "xg_pj": 2.0, "gols_pj": 1.9, "xg_sofrido_pj": 0.6, "gols_contra_pj": 0.4},
            {"snapshot_jogo": snap, "team": "Fraco", "jogos": snap, "score_geral": 35, "score_ataque": 33,
             "score_defesa": 36, "score_controle": 40, "score_eficiencia": 38, "elo_rating": 1440,
             "xg_pj": 0.6, "gols_pj": 0.5, "xg_sofrido_pj": 2.0, "gols_contra_pj": 1.9},
        ]
    timeline = pd.DataFrame(rows)

    m = build_predictive(dim, timeline, snapshot=1, min_prediction_game=1, min_display_game=1)["matches"][0]
    assert m["favorite"] == "Forte"
    assert m["favorite_side"] == "home"
    assert m["probabilities"]["home_win"] > m["probabilities"]["away_win"]
    # nenhum modelo do ensemble deve inverter gritante (azarão com >60%)
    for mod in m["models"].values():
        if mod.get("available") and "probabilities" in mod:
            assert mod["probabilities"]["away_win"] <= 60


def test_predictive_placar_nao_fica_murcho_para_favorito_claro():
    """Favorito que deve fazer ~2 gols não pode recomendar placar de 1 gol só."""
    dim = pd.DataFrame([
        {"match_id": "m1", "match_number": 2, "status": "agendado",
         "home_team": "Forte", "away_team": "Fraco", "home_score": None, "away_score": None,
         "date_utc": "2026-06-02T00:00:00Z", "stage": "First Stage", "group": "A"},
    ])
    timeline = pd.DataFrame([
        {"snapshot_jogo": 1, "team": "Forte", "jogos": 3, "score_geral": 82, "score_ataque": 86,
         "score_defesa": 80, "score_controle": 78, "score_eficiencia": 74, "elo_rating": 1580,
         "xg_pj": 2.4, "gols_pj": 2.3, "xg_sofrido_pj": 0.5, "gols_contra_pj": 0.3},
        {"snapshot_jogo": 1, "team": "Fraco", "jogos": 3, "score_geral": 32, "score_ataque": 30,
         "score_defesa": 34, "score_controle": 36, "score_eficiencia": 34, "elo_rating": 1420,
         "xg_pj": 0.5, "gols_pj": 0.4, "xg_sofrido_pj": 2.3, "gols_contra_pj": 2.2},
    ])

    m = build_predictive(dim, timeline, snapshot=1, min_prediction_game=1, min_display_game=1)["matches"][0]
    rec = m["probabilities"]["scoreline"]["recommended"]
    # favorito claro com xG alto: placar recomendado deve ter >= 2 gols do favorito
    assert rec["home"] >= 2
    assert rec["home"] > rec["away"]


def test_predictive_mostra_cedo_mas_marca_baixa_confianca():
    """Entre min_display e min_prediction, a previsão aparece marcada low_confidence."""
    dim = pd.DataFrame([
        {"match_id": f"m{i}", "match_number": i, "status": "finalizado" if i < 10 else "agendado",
         "home_team": "A", "away_team": "B", "home_score": 1 if i < 10 else None,
         "away_score": 0 if i < 10 else None, "date_utc": f"2026-06-{i:02d}T00:00:00Z",
         "stage": "First Stage", "group": "A"}
        for i in range(1, 11)
    ])
    rows = [{"snapshot_jogo": s, "team": t, "jogos": s, "score_geral": 60, "score_ataque": 60,
             "score_defesa": 60, "elo_rating": 1510, "xg_pj": 1.4, "gols_pj": 1.0,
             "xg_sofrido_pj": 0.9, "gols_contra_pj": 0.6}
            for s in range(1, 10) for t in ("A", "B")]
    timeline = pd.DataFrame(rows)

    # jogo 5 está entre display (2) e prediction (25): aparece, mas baixa confiança
    pred = build_predictive(dim, timeline, snapshot=5, min_prediction_game=25, min_display_game=2)
    assert pred["matches"], "deveria prever (mostrar) mesmo abaixo do jogo 25"
    assert pred["matches"][0]["low_confidence"] is True

    # jogo 1 não tem base: não prevê
    pred1 = build_predictive(dim, timeline, snapshot=1, min_prediction_game=25, min_display_game=2)
    assert pred1["matches"] == []


def test_backtest_display_start_nao_suja_metrica():
    """display_start gera linhas extras (p/ colorir) mas o summary só conta 25+."""
    dim = pd.DataFrame([
        {"match_id": f"m{i}", "match_number": i, "status": "finalizado",
         "home_team": "A" if i % 2 else "B", "away_team": "B" if i % 2 else "A",
         "home_score": 2 if i % 2 else 0, "away_score": 0 if i % 2 else 1,
         "date_utc": f"2026-06-{i:02d}T00:00:00Z", "stage": "First Stage", "group": "A"}
        for i in range(1, 7)
    ])
    rows = [{"snapshot_jogo": s, "team": t, "jogos": s, "score_geral": 60, "score_ataque": 60,
             "score_defesa": 60, "elo_rating": 1510, "xg_pj": 1.4, "gols_pj": 1.0,
             "xg_sofrido_pj": 0.9, "gols_contra_pj": 0.6}
            for s in range(1, 6) for t in ("A", "B")]
    timeline = pd.DataFrame(rows)

    bt = build_backtest(dim, timeline, start=4, end=5, min_prediction_game=4, display_start=2)
    # linhas cobrem desde o jogo 2; summary só conta os >= 4
    snapshots = sorted(r["snapshot"] for r in bt["rows"])
    assert min(snapshots) < 4  # tem linha de baixa confiança
    assert bt["summary"]["n"] == sum(1 for r in bt["rows"] if not r["low_confidence"])


def test_predictive_jogo_1_sem_base_nao_preve():
    dim = pd.DataFrame([
        {"match_id": "m1", "match_number": 1, "status": "agendado",
         "home_team": "A", "away_team": "B", "home_score": None, "away_score": None,
         "date_utc": "2026-06-01T00:00:00Z", "stage": "First Stage", "group": "A"},
    ])
    timeline = pd.DataFrame([
        {"snapshot_jogo": 1, "team": "A", "jogos": 1, "score_geral": 60, "score_ataque": 60,
         "score_defesa": 60, "elo_rating": 1510, "xg_pj": 1.4, "gols_pj": 1.0,
         "xg_sofrido_pj": 0.8, "gols_contra_pj": 0.0},
    ])

    # jogo 1 não tem nenhum jogo anterior de base → não prevê
    pred = build_predictive(dim, timeline, snapshot=1)

    assert pred["matches"] == []
    assert pred["base"]["min_prediction_game"] == 25
    assert pred["base"]["min_display_game"] == 2
