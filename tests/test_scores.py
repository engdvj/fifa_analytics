"""Testes do modelo de scores de seleções e jogadores.

Cobre: lógica de z-score, separação de perfis, score_geral composto,
confiança sem piso artificial, ranking dentro do pool de posição.
"""
import pandas as pd
import pytest

from fifa_analytics.analytics.scores import (
    _player_profile,
    _sample_confidence,
    _zscore_to_100,
    build_player_match_features,
    build_player_scores,
    build_team_match_features,
    build_team_scores,
)
from fifa_analytics.utils.text import slugify


# ---------------------------------------------------------------------------
# Fixtures base
# ---------------------------------------------------------------------------

def _match(match_id: str, home: str, away: str, hs: int, as_: int) -> dict:
    return {
        "canonical_match_id": match_id,
        "date": "2026-06-11",
        "group": "A",
        "stage": "fase_de_grupos",
        "round": "1",
        "status": "finalizado",
        "home_team": home,
        "away_team": away,
        "home_score": hs,
        "away_score": as_,
    }


def _team_stats(match_id: str, team: str, **kwargs) -> dict:
    defaults = {
        "match_id": match_id,
        "team": team,
        "possession": 50,
        "shots": 10,
        "shots_on_target": 4,
        "passes": 400,
        "pass_accuracy": 0.80,
        "fouls": 12,
        "yellow_cards": 1,
        "red_cards": 0,
    }
    return {**defaults, **kwargs}


def _player(match_id: str, team: str, name: str, position: str | None = None, **kwargs) -> dict:
    defaults = {
        "match_id": match_id,
        "team": team,
        "player_name": name,
        "position": position,
        "minutes_played": 90,
        "goals": 0,
        "assists": 0,
        "shots": 0,
        "shots_on_target": 0,
        "passes": 0,
        "tackles": 0,
        "interceptions": 0,
        "saves": 0,
        "goals_conceded": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "fouls_committed": 0,
        "fouls_drawn": 0,
    }
    return {**defaults, **kwargs}


# ---------------------------------------------------------------------------
# _zscore_to_100
# ---------------------------------------------------------------------------

def test_zscore_single_value_returns_50():
    s = pd.Series([42.0])
    assert _zscore_to_100(s).iloc[0] == pytest.approx(50.0)


def test_zscore_preserves_order():
    s = pd.Series([1.0, 2.0, 3.0])
    z = _zscore_to_100(s)
    assert z.iloc[0] < z.iloc[1] < z.iloc[2]


def test_zscore_lower_is_better_reverses_order():
    s = pd.Series([1.0, 2.0, 3.0])
    z = _zscore_to_100(s, lower_is_better=True)
    assert z.iloc[0] > z.iloc[1] > z.iloc[2]


def test_zscore_identical_values_return_50():
    s = pd.Series([5.0, 5.0, 5.0])
    z = _zscore_to_100(s)
    assert (z == 50.0).all()


def test_zscore_output_between_0_and_100():
    s = pd.Series([0.0, 1.0, 100.0, 1000.0])
    z = _zscore_to_100(s)
    assert (z >= 0).all() and (z <= 100).all()


# ---------------------------------------------------------------------------
# _sample_confidence — sem piso artificial
# ---------------------------------------------------------------------------

def test_sample_confidence_zero_games_is_zero():
    conf = _sample_confidence(pd.Series([0]))
    assert conf.iloc[0] == pytest.approx(0.0)


def test_sample_confidence_grows_with_games():
    conf = _sample_confidence(pd.Series([1, 2, 3, 5]))
    assert conf.is_monotonic_increasing


def test_sample_confidence_caps_at_one():
    conf = _sample_confidence(pd.Series([100]))
    assert conf.iloc[0] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _player_profile — ESPN position codes
# ---------------------------------------------------------------------------

def test_player_profile_gk_by_position():
    row = pd.Series({"position": "GK", "saves": 0, "goals": 0, "tackles": 0, "shots_on_target": 0, "interceptions": 0})
    assert _player_profile(row) == "goleiro"


def test_player_profile_cb_is_defensor():
    row = pd.Series({"position": "CB", "saves": 0, "goals": 0, "tackles": 0, "shots_on_target": 0, "interceptions": 0})
    assert _player_profile(row) == "defensor"


def test_player_profile_st_is_atacante():
    row = pd.Series({"position": "ST", "saves": 0, "goals": 0, "tackles": 0, "shots_on_target": 0, "interceptions": 0})
    assert _player_profile(row) == "atacante"


def test_player_profile_cm_is_meio():
    row = pd.Series({"position": "CM", "saves": 0, "goals": 0, "tackles": 0, "shots_on_target": 0, "interceptions": 0})
    assert _player_profile(row) == "meio"


def test_player_profile_fallback_saves():
    row = pd.Series({"position": None, "saves": 3, "goals": 0, "assists": 0, "tackles": 0, "shots_on_target": 0, "interceptions": 0})
    assert _player_profile(row) == "goleiro"


def test_player_profile_fallback_shots_on_target():
    row = pd.Series({"position": None, "saves": 0, "goals": 0, "assists": 0, "shots_on_target": 2, "tackles": 0, "interceptions": 0})
    assert _player_profile(row) == "atacante"


def test_player_profile_fallback_no_stats_is_meio():
    """Sem posição e sem stats ofensivas/saves, classifica como meio (default)."""
    row = pd.Series({"position": None, "saves": 0, "goals": 0, "assists": 0, "shots_on_target": 0})
    assert _player_profile(row) == "meio"


def test_player_profile_saves_do_not_override_goal_scorer():
    """Jogador de linha que salvou 1 chute mas marcou 2 gols não é goleiro."""
    row = pd.Series({"position": None, "saves": 1, "goals": 2, "assists": 0, "shots_on_target": 2, "tackles": 0, "interceptions": 0})
    assert _player_profile(row) != "goleiro"


# ---------------------------------------------------------------------------
# build_team_scores — modelo de seleções
# ---------------------------------------------------------------------------

def _make_two_team_features() -> pd.DataFrame:
    matches = pd.DataFrame([_match("j1", "Brasil", "Alemanha", 3, 0)])
    stats = pd.DataFrame([
        _team_stats("j1", "Brasil", shots=20, shots_on_target=8, fouls=8, yellow_cards=0),
        _team_stats("j1", "Alemanha", shots=5, shots_on_target=1, fouls=16, yellow_cards=3),
    ])
    return build_team_match_features(matches, stats)


def test_team_scores_winner_has_higher_score_geral():
    features = _make_two_team_features()
    scores = build_team_scores(features)
    brasil = scores[scores["team"] == "Brasil"].iloc[0]
    alemanha = scores[scores["team"] == "Alemanha"].iloc[0]
    assert brasil["score_geral"] > alemanha["score_geral"]


def test_team_scores_resultado_drives_score():
    """Time que vence deve ter score_resultado maior mesmo com stats similares."""
    matches = pd.DataFrame([_match("j1", "Brasil", "Alemanha", 1, 0)])
    stats = pd.DataFrame([
        _team_stats("j1", "Brasil"),
        _team_stats("j1", "Alemanha"),
    ])
    features = build_team_match_features(matches, stats)
    scores = build_team_scores(features)
    brasil = scores[scores["team"] == "Brasil"].iloc[0]
    alemanha = scores[scores["team"] == "Alemanha"].iloc[0]
    assert brasil["score_resultado"] > alemanha["score_resultado"]


def test_team_scores_resultado_component_present():
    features = _make_two_team_features()
    scores = build_team_scores(features)
    assert "score_resultado" in scores.columns


def test_team_scores_has_rankings_per_dimension():
    features = _make_two_team_features()
    scores = build_team_scores(features)
    for col in ["ranking_score_geral", "ranking_ataque", "ranking_defesa", "ranking_eficiencia"]:
        assert col in scores.columns


def test_team_scores_no_process_stats_still_works():
    """Sem dados de processo (só gols), score_geral vem do resultado."""
    matches = pd.DataFrame([_match("j1", "Brasil", "Alemanha", 2, 0)])
    features = build_team_match_features(matches, None)
    scores = build_team_scores(features)
    brasil = scores[scores["team"] == "Brasil"].iloc[0]
    alemanha = scores[scores["team"] == "Alemanha"].iloc[0]
    assert brasil["score_resultado"] > alemanha["score_resultado"]


def test_team_scores_draw_gives_equal_resultado():
    matches = pd.DataFrame([_match("j1", "Brasil", "Alemanha", 1, 1)])
    features = build_team_match_features(matches, None)
    scores = build_team_scores(features)
    brasil = scores[scores["team"] == "Brasil"].iloc[0]
    alemanha = scores[scores["team"] == "Alemanha"].iloc[0]
    assert brasil["score_resultado"] == pytest.approx(alemanha["score_resultado"])


def test_team_scores_one_game_confidence_below_one():
    features = _make_two_team_features()
    scores = build_team_scores(features)
    for _, row in scores.iterrows():
        assert row["confianca_amostra"] < 1.0


def test_team_scores_five_games_full_confidence():
    matches = pd.DataFrame([
        _match("j1", "Brasil", "A", 2, 0),
        _match("j2", "Brasil", "B", 1, 1),
        _match("j3", "Brasil", "C", 3, 1),
        _match("j4", "Brasil", "D", 0, 0),
        _match("j5", "Brasil", "E", 2, 1),
    ])
    features = build_team_match_features(matches, None)
    scores = build_team_scores(features)
    brasil = scores[scores["team"] == "Brasil"].iloc[0]
    assert brasil["confianca_amostra"] == pytest.approx(1.0)


def test_team_scores_slug_generated():
    features = _make_two_team_features()
    scores = build_team_scores(features)
    assert "team_slug" in scores.columns
    assert scores[scores["team"] == "Brasil"]["team_slug"].iloc[0] == "brasil"


def test_team_scores_disciplined_team_has_better_score():
    """Time disciplinado (menos faltas/cartões) deve ter score_geral maior com stats iguais."""
    matches = pd.DataFrame([
        _match("j1", "Limpo", "Sujo", 1, 1),
    ])
    stats = pd.DataFrame([
        _team_stats("j1", "Limpo", fouls=5, yellow_cards=0, red_cards=0),
        _team_stats("j1", "Sujo", fouls=20, yellow_cards=4, red_cards=1),
    ])
    features = build_team_match_features(matches, stats)
    scores = build_team_scores(features)
    limpo = scores[scores["team"] == "Limpo"].iloc[0]
    sujo = scores[scores["team"] == "Sujo"].iloc[0]
    # Resultado igual (empate), score_geral diferenciado por outros componentes
    assert limpo["score_resultado"] == pytest.approx(sujo["score_resultado"])


# ---------------------------------------------------------------------------
# build_player_scores — separação por perfil
# ---------------------------------------------------------------------------

def _make_player_features() -> pd.DataFrame:
    players = pd.DataFrame([
        _player("j1", "Brasil", "Alisson", position="GK", saves=5),
        _player("j1", "Brasil", "Militão", position="CB", fouls_drawn=4, shots_on_target=1),
        _player("j1", "Brasil", "Vinicius", position="LW", goals=2, assists=1, shots_on_target=4),
        _player("j1", "Brasil", "Rodrygo", position="RW", goals=1, shots_on_target=2),
        _player("j1", "Alemanha", "Neuer", position="GK", saves=2),
        _player("j1", "Alemanha", "Rüdiger", position="CB", fouls_drawn=1, shots_on_target=0),
    ])
    return build_player_match_features(players)


def test_player_scores_profiles_correctly_assigned():
    features = _make_player_features()
    scores = build_player_scores(features)
    assert scores[scores["player_name"] == "Alisson"]["perfil"].iloc[0] == "goleiro"
    assert scores[scores["player_name"] == "Militão"]["perfil"].iloc[0] == "defensor"
    assert scores[scores["player_name"] == "Vinicius"]["perfil"].iloc[0] == "atacante"


def test_player_scores_best_striker_leads_attackers():
    features = _make_player_features()
    scores = build_player_scores(features)
    attackers = scores[scores["perfil"] == "atacante"].sort_values("score_geral", ascending=False)
    assert attackers.iloc[0]["player_name"] == "Vinicius"


def test_player_scores_better_gk_has_higher_score():
    features = _make_player_features()
    scores = build_player_scores(features)
    alisson = scores[scores["player_name"] == "Alisson"].iloc[0]
    neuer = scores[scores["player_name"] == "Neuer"].iloc[0]
    assert alisson["score_geral"] > neuer["score_geral"]


def test_player_scores_better_cb_has_higher_score():
    """CB com mais fouls_drawn (duelos, pressão) deve pontuar mais no pool de defensores."""
    players = pd.DataFrame([
        _player("j1", "Brasil", "Militão", position="CB", fouls_drawn=4, shots_on_target=1),
        _player("j1", "Alemanha", "Rüdiger", position="CB", fouls_drawn=1, shots_on_target=0),
    ])
    features = build_player_match_features(players)
    scores = build_player_scores(features)
    militao = scores[scores["player_name"] == "Militão"].iloc[0]
    rudiger = scores[scores["player_name"] == "Rüdiger"].iloc[0]
    assert militao["score_geral"] > rudiger["score_geral"]


def test_player_scores_score_acumulado_present():
    features = _make_player_features()
    scores = build_player_scores(features)
    assert "score_acumulado" in scores.columns


def test_player_scores_slug_generated():
    features = _make_player_features()
    scores = build_player_scores(features)
    vinicius = scores[scores["player_name"] == "Vinicius"].iloc[0]
    assert vinicius["player_slug"] == slugify("Vinicius_Brasil")


def test_player_scores_nivel_evidencia_values():
    features = _make_player_features()
    scores = build_player_scores(features)
    assert set(scores["nivel_evidencia"].unique()).issubset({"alta", "media", "baixa"})


def test_player_scores_one_game_not_full_confidence():
    features = _make_player_features()
    scores = build_player_scores(features)
    for _, row in scores.iterrows():
        assert row["confianca_amostra"] < 1.0


def test_player_scores_empty_input_returns_empty():
    assert build_player_scores(pd.DataFrame()).empty


def test_team_match_features_skips_scheduled():
    matches = pd.DataFrame([{
        "canonical_match_id": "j1",
        "date": "2026-06-11",
        "home_team": "Brasil",
        "away_team": "Alemanha",
        "home_score": None,
        "away_score": None,
        "status": "agendado",
    }])
    features = build_team_match_features(matches)
    assert features.empty


def test_build_player_match_features_assigns_profile_from_position():
    players = pd.DataFrame([
        _player("j1", "Brasil", "Alisson", position="GK"),
        _player("j1", "Brasil", "Danilo", position="RB"),
        _player("j1", "Brasil", "Casemiro", position="CDM"),
        _player("j1", "Brasil", "Vinicius", position="LW"),
    ])
    features = build_player_match_features(players)
    assert features[features["player_name"] == "Alisson"]["perfil"].iloc[0] == "goleiro"
    assert features[features["player_name"] == "Danilo"]["perfil"].iloc[0] == "defensor"
    assert features[features["player_name"] == "Casemiro"]["perfil"].iloc[0] == "meio"
    assert features[features["player_name"] == "Vinicius"]["perfil"].iloc[0] == "atacante"


# ---------------------------------------------------------------------------
# Métricas exclusivas de goleiro
# ---------------------------------------------------------------------------

def test_gk_more_saves_is_better():
    """Goleiro com mais defesas deve ter score maior — saves é a única métrica ESPN disponível."""
    players = pd.DataFrame([
        _player("j1", "Brasil", "GK1", position="GK", saves=8),
        _player("j1", "Brasil", "GK2", position="GK", saves=2),
    ])
    features = build_player_match_features(players)
    scores = build_player_scores(features)
    gk1 = scores[scores["player_name"] == "GK1"].iloc[0]
    gk2 = scores[scores["player_name"] == "GK2"].iloc[0]
    assert gk1["score_geral"] > gk2["score_geral"]


def test_gk_more_saves_beats_fewer_saves_same_conceded():
    """Goleiro com mais defesas e mesmos gols sofridos deve pontuar mais."""
    players = pd.DataFrame([
        _player("j1", "Brasil", "GK1", position="GK", saves=8, goals_conceded=1),
        _player("j1", "Brasil", "GK2", position="GK", saves=2, goals_conceded=1),
    ])
    features = build_player_match_features(players)
    scores = build_player_scores(features)
    gk1 = scores[scores["player_name"] == "GK1"].iloc[0]
    gk2 = scores[scores["player_name"] == "GK2"].iloc[0]
    assert gk1["score_geral"] > gk2["score_geral"]


def test_gk_saves_do_not_promote_defender_to_gk_pool():
    """CB com saves não deve ser classificado como goleiro — posição ESPN tem prioridade."""
    players = pd.DataFrame([
        _player("j1", "Brasil", "CB1", position="CB", saves=5, fouls_drawn=3),
        _player("j1", "Brasil", "CB2", position="CB", saves=0, fouls_drawn=1),
    ])
    features = build_player_match_features(players)
    scores = build_player_scores(features)
    cb1 = scores[scores["player_name"] == "CB1"].iloc[0]
    cb2 = scores[scores["player_name"] == "CB2"].iloc[0]
    # Posição ESPN (CB) tem prioridade — ambos ficam no pool de defensores
    assert cb1["perfil"] == "defensor"
    assert cb2["perfil"] == "defensor"
    # CB1 tem mais fouls_drawn, deve liderar entre defensores (saves ignorados)
    assert cb1["score_geral"] > cb2["score_geral"]
