import pandas as pd

from fifa_analytics.analytics.player_scores import (
    PROFILE_WEIGHTS,
    build_player_scores,
)


def _acc(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_score_is_within_0_100_and_breaks_into_components():
    acc = _acc([
        {"id_player": "1", "perfil": "atacante", "jogos": 2, "minutos": 180,
         "gols": 4, "xg": 2.4, "chutes": 19, "chutes_no_alvo": 9, "assistencias": 0,
         "passes": 60, "passes_certos": 50, "progressoes": 8, "dribles_certos": 3,
         "cruzamentos_certos": 1, "sequencias_com_chute": 4},
        {"id_player": "2", "perfil": "atacante", "jogos": 2, "minutos": 180,
         "gols": 1, "xg": 2.6, "chutes": 38, "chutes_no_alvo": 10, "assistencias": 1,
         "passes": 70, "passes_certos": 55, "progressoes": 12, "dribles_certos": 5,
         "cruzamentos_certos": 2, "sequencias_com_chute": 6},
    ])
    out = build_player_scores(acc)
    assert {"score_proprio", "confianca_score", "nivel_confianca"} <= set(out.columns)
    assert {"prop_finalizacao", "prop_criacao", "prop_eficiencia",
            "prop_progressao", "prop_defesa", "prop_goleiro"} <= set(out.columns)
    assert out["score_proprio"].between(0, 100).all()
    # quem cria mais perigo (jogador 2) tem finalização >= quem fez mais gols,
    # mas a eficiência premia o finalizador clínico (jogador 1).
    p1 = out.set_index("id_player").loc["1"]
    p2 = out.set_index("id_player").loc["2"]
    assert p2["prop_finalizacao"] >= p1["prop_finalizacao"]
    assert p1["prop_eficiencia"] > p2["prop_eficiencia"]


def test_zscore_computed_within_position_not_across():
    # Goleiro com muitas defesas e atacante com muitos gols não devem ser
    # comparados na mesma escala: cada um é normalizado no próprio perfil.
    acc = _acc([
        {"id_player": "gk1", "perfil": "goleiro", "jogos": 2, "minutos": 180,
         "defesas": 10, "gols_sofridos": 1, "jogos_sem_sofrer": 1,
         "passes": 40, "passes_certos": 30},
        {"id_player": "gk2", "perfil": "goleiro", "jogos": 2, "minutos": 180,
         "defesas": 2, "gols_sofridos": 5, "jogos_sem_sofrer": 0,
         "passes": 40, "passes_certos": 25},
        {"id_player": "at1", "perfil": "atacante", "jogos": 2, "minutos": 180,
         "gols": 5, "xg": 3.0, "chutes": 12, "chutes_no_alvo": 8},
    ])
    out = build_player_scores(acc).set_index("id_player")
    # melhor goleiro supera o pior goleiro no componente de goleiro
    assert out.loc["gk1", "prop_goleiro"] > out.loc["gk2", "prop_goleiro"]
    # o atacante não recebe nota pelo componente de goleiro no seu score
    assert "goleiro" not in PROFILE_WEIGHTS["atacante"]


def test_low_minutes_shrinks_toward_50():
    # Mesma produção bruta, minutos muito diferentes: quem jogou pouco tem a nota
    # encolhida para perto de 50 (baixa confiança).
    acc = _acc([
        {"id_player": "full", "perfil": "atacante", "jogos": 3, "minutos": 270,
         "gols": 3, "xg": 2.0, "chutes": 9, "chutes_no_alvo": 6},
        {"id_player": "sub", "perfil": "atacante", "jogos": 1, "minutos": 15,
         "gols": 1, "xg": 0.6, "chutes": 2, "chutes_no_alvo": 1},
    ])
    out = build_player_scores(acc).set_index("id_player")
    assert out.loc["full", "confianca_score"] > out.loc["sub", "confianca_score"]
    assert out.loc["sub", "nivel_confianca"] == "baixa"
    assert abs(out.loc["sub", "score_proprio"] - 50) < abs(out.loc["full", "score_proprio"] - 50) + 1e-9


def test_defender_and_keeper_have_capped_confidence():
    # Defensor/goleiro têm teto de confiança menor (dados pobres), mesmo com
    # minutos plenos: nunca atingem confiança 1.0.
    acc = _acc([
        {"id_player": "d", "perfil": "defensor", "jogos": 4, "minutos": 360,
         "turnovers_forcados": 12, "pressoes_defensivas": 30, "pressoes_diretas": 8,
         "passes": 200, "passes_certos": 180, "progressoes": 20},
        {"id_player": "g", "perfil": "goleiro", "jogos": 4, "minutos": 360,
         "defesas": 16, "gols_sofridos": 3, "jogos_sem_sofrer": 2,
         "passes": 120, "passes_certos": 90},
    ])
    out = build_player_scores(acc).set_index("id_player")
    assert out.loc["d", "confianca_score"] <= 0.8 + 1e-9
    assert out.loc["g", "confianca_score"] <= 0.75 + 1e-9


def test_benched_player_gets_no_score():
    acc = _acc([
        {"id_player": "x", "perfil": "meio", "jogos": 0, "minutos": 0, "gols": 0},
    ])
    out = build_player_scores(acc).set_index("id_player")
    assert pd.isna(out.loc["x", "score_proprio"])
    nivel = out.loc["x", "nivel_confianca"]
    assert nivel is None or pd.isna(nivel)


def test_fixed_reference_makes_score_stable_across_snapshots():
    # Com ref_stats fixo, a nota de um jogador não muda quando OUTRO joga depois.
    ref: dict = {}
    full = _acc([
        {"id_player": "a", "perfil": "atacante", "jogos": 2, "minutos": 180,
         "gols": 3, "xg": 2.0, "chutes": 10, "chutes_no_alvo": 5},
        {"id_player": "b", "perfil": "atacante", "jogos": 2, "minutos": 180,
         "gols": 1, "xg": 1.0, "chutes": 6, "chutes_no_alvo": 2},
    ])
    build_player_scores(full, ref_stats=ref)  # popula a referência

    snap1 = build_player_scores(full[full["id_player"] == "a"].copy(), ref_stats=ref)
    snap2 = build_player_scores(full, ref_stats=ref)
    a1 = snap1.set_index("id_player").loc["a", "score_proprio"]
    a2 = snap2.set_index("id_player").loc["a", "score_proprio"]
    assert a1 == a2
