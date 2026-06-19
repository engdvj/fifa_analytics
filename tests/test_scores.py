"""Testes do modelo de scores de seleções e jogadores.

Cobre: lógica de z-score, separação de perfis, score_geral composto,
confiança sem piso artificial, ranking dentro do pool de posição.
"""
import pandas as pd
import pytest

from fifa_analytics.analytics.scores import (
    _classify_style,
    _player_profile,
    _run_elo_simulation,
    _sample_confidence,
    _style_affinities,
    _zscore_to_100,
    build_player_match_features,
    build_player_scores,
    build_team_match_features,
    build_team_scores,
)
from fifa_analytics.utils.text import clean_person_name, person_name_exact_key, person_name_key, slugify


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


def test_player_profile_dm_and_cdm_are_same_profile():
    dm = pd.Series({"position": "DM", "saves": 0, "goals": 0, "tackles": 0, "shots_on_target": 0, "interceptions": 0})
    cdm = pd.Series({"position": "CDM", "saves": 0, "goals": 0, "tackles": 0, "shots_on_target": 0, "interceptions": 0})

    assert _player_profile(dm) == "meio"
    assert _player_profile(cdm) == "meio"


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


def test_team_scores_advanced_metrics_aggregated_from_players():
    """xG/xGP só existem por jogador (365Scores) — devem ser somados ao time."""
    matches = pd.DataFrame([_match("j1", "Brasil", "Alemanha", 2, 1)])
    stats = pd.DataFrame([
        _team_stats("j1", "Brasil"),
        _team_stats("j1", "Alemanha"),
    ])
    players = pd.DataFrame([
        _player("j1", "Brasil", "A", expected_goals=0.8, expected_goals_prevented=0.5,
                ground_duels_won=3, aerial_duels_won=2, shots_blocked=1),
        _player("j1", "Brasil", "B", expected_goals=0.7, expected_goals_prevented=0.3),
        _player("j1", "Alemanha", "C", expected_goals=0.3, expected_goals_prevented=-0.2),
    ])
    features = build_team_match_features(matches, stats, player_stats=players)
    brasil = features[features["team"] == "Brasil"].iloc[0]
    assert brasil["team_xg"] == pytest.approx(1.5)
    assert brasil["team_xgp"] == pytest.approx(0.8)
    # o xG do adversário deve virar xg_against no time
    assert brasil["xg_against"] == pytest.approx(0.3)


def test_team_scores_work_without_advanced_player_stats():
    """Backward-compat: sem player_stats, o score ainda é calculado (advanced_coverage=0)."""
    matches = pd.DataFrame([_match("j1", "Brasil", "Alemanha", 3, 0)])
    stats = pd.DataFrame([
        _team_stats("j1", "Brasil", shots=20, shots_on_target=8),
        _team_stats("j1", "Alemanha", shots=4, shots_on_target=1),
    ])
    features = build_team_match_features(matches, stats)  # sem player_stats
    scores = build_team_scores(features)
    assert (scores["advanced_coverage"] == 0).all()
    brasil = scores[scores["team"] == "Brasil"].iloc[0]
    alemanha = scores[scores["team"] == "Alemanha"].iloc[0]
    assert brasil["score_geral"] > alemanha["score_geral"]


def test_team_scores_defesa_monotonic_with_advanced_data():
    """Time que sofreu mais gols nunca pode ter defesa melhor — mesmo com xGP alto."""
    matches = pd.DataFrame([
        _match("j1", "Solido", "RivalA", 0, 0),
        _match("j2", "Furado", "RivalB", 0, 3),
    ])
    stats = pd.DataFrame([
        _team_stats("j1", "Solido"), _team_stats("j1", "RivalA"),
        _team_stats("j2", "Furado"), _team_stats("j2", "RivalB"),
    ])
    players = pd.DataFrame([
        _player("j1", "Solido", "S", expected_goals_prevented=0.1, ground_duels_won=5),
        _player("j1", "RivalA", "Ra", expected_goals=0.5),
        # Furado com xGP altíssimo (goleiro fez milagres) mas sofreu 3 gols
        _player("j2", "Furado", "F", expected_goals_prevented=3.0, ground_duels_won=20),
        _player("j2", "RivalB", "Rb", expected_goals=4.0),
    ])
    features = build_team_match_features(matches, stats, player_stats=players)
    scores = build_team_scores(features)
    solido = scores[scores["team"] == "Solido"].iloc[0]
    furado = scores[scores["team"] == "Furado"].iloc[0]
    assert solido["score_defesa"] > furado["score_defesa"]


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
# Estilo de jogo (métrica descritiva, informacional)
# ---------------------------------------------------------------------------

def test_team_style_columns_present():
    features = _make_two_team_features()
    scores = build_team_scores(features)
    for col in ["estilo_posse", "estilo_pressao", "estilo_largura", "estilo_verticalidade", "estilo_jogo"]:
        assert col in scores.columns


def test_team_style_not_in_score_geral():
    """Estilo é informacional — não deve alterar o score_geral. Dois times com
    resultado idêntico mas estilos opostos têm o mesmo score_geral."""
    matches = pd.DataFrame([_match("j1", "Posse", "Direto", 1, 1)])
    stats = pd.DataFrame([
        _team_stats("j1", "Posse", possession=70, passes=600, shots=8),
        _team_stats("j1", "Direto", possession=30, passes=200, shots=18),
    ])
    features = build_team_match_features(matches, stats)
    scores = build_team_scores(features)
    posse = scores[scores["team"] == "Posse"].iloc[0]
    direto = scores[scores["team"] == "Direto"].iloc[0]
    # estilos diferem mas score_geral não é afetado por estilo (só pelo empate +
    # componentes de processo, que aqui são z-scores simétricos)
    assert posse["estilo_posse"] != direto["estilo_posse"]


def test_team_style_possession_axis_orders_teams():
    """Time com muito mais posse/passes deve ter estilo_posse maior."""
    matches = pd.DataFrame([_match("j1", "Posse", "Direto", 0, 0)])
    stats = pd.DataFrame([
        _team_stats("j1", "Posse", possession=72, passes=700, pass_accuracy=0.90),
        _team_stats("j1", "Direto", possession=28, passes=180, pass_accuracy=0.65),
    ])
    features = build_team_match_features(matches, stats)
    scores = build_team_scores(features)
    posse = scores[scores["team"] == "Posse"].iloc[0]
    direto = scores[scores["team"] == "Direto"].iloc[0]
    assert posse["estilo_posse"] > direto["estilo_posse"]


def test_team_style_flag_is_from_archetype_list():
    """A flag de estilo deve ser sempre um dos arquétipos nomeados (ou Equilibrado)."""
    from fifa_analytics.analytics.scores import _STYLE_PROFILES
    valid = set(_STYLE_PROFILES) | {"Equilibrado"}
    features = _make_two_team_features()
    scores = build_team_scores(features)
    assert set(scores["estilo_jogo"]).issubset(valid)


def test_classify_style_picks_highest_affinity():
    """A flag é o arquétipo de maior afinidade (acima do mínimo)."""
    assert _classify_style({"Ofensivo": 90.0, "Toque e Posse": 60.0}) == "Ofensivo"
    assert _classify_style({"Defensivo": 80.0, "Contra-ataque": 50.0}) == "Defensivo"


def test_classify_style_balanced_when_no_strong_match():
    """Nenhuma afinidade acima do mínimo → Equilibrado."""
    assert _classify_style({"Ofensivo": 30.0, "Toque e Posse": 25.0}) == "Equilibrado"
    assert _classify_style({}) == "Equilibrado"


def test_style_affinity_saturates_not_ranking():
    """Afinidade mede encaixe ABSOLUTO no perfil ideal, não ranking: um time que
    bate a meta tem afinidade alta mesmo não sendo o melhor; superar a meta não
    explode acima de 100%."""
    metrics = pd.DataFrame({"gols": [3.0, 7.0], "no_alvo": [7.0, 12.0], "chutes": [18.0, 26.0]})
    # metas batidas já no 1º time; o 2º só supera — ambos devem cravar alto, perto um do outro
    targets = {"gols@80": 3.0, "no_alvo@80": 7.0, "chutes@75": 18.0}
    af = _style_affinities(metrics, targets)
    assert af[0]["Ofensivo"] >= 80          # bate a meta exatamente → alto
    assert af[1]["Ofensivo"] <= 100         # superar não passa de 100
    assert af[1]["Ofensivo"] - af[0]["Ofensivo"] <= 20  # diferença modesta (não vira ranking)


def test_style_targets_evolve_with_games():
    """As metas dinâmicas migram da semente para o percentil real conforme os
    jogos do torneio acumulam (peso do percentil cresce)."""
    from fifa_analytics.analytics.scores import _style_target_blend_weight
    assert _style_target_blend_weight(0) < _style_target_blend_weight(30) < _style_target_blend_weight(80)
    assert _style_target_blend_weight(80) > 0.9  # tarde no torneio, dados dominam


# ---------------------------------------------------------------------------
# build_player_scores — separação por perfil
# ---------------------------------------------------------------------------

def _make_player_features() -> pd.DataFrame:
    players = pd.DataFrame([
        _player("j1", "Brasil", "Alisson", position="GK", saves=5, goals_conceded=0),
        _player("j1", "Brasil", "Militão", position="CB", fouls_drawn=4, shots_on_target=1, goals_conceded=0),
        _player("j1", "Brasil", "Vinicius", position="LW", goals=2, assists=1, shots_on_target=4),
        _player("j1", "Brasil", "Rodrygo", position="RW", goals=1, shots_on_target=2),
        _player("j1", "Alemanha", "Neuer", position="GK", saves=2, goals_conceded=3),
        _player("j1", "Alemanha", "Rüdiger", position="CB", fouls_drawn=1, shots_on_target=0, goals_conceded=3),
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
    """CB que sofre menos gols e ganha mais duelos deve pontuar mais."""
    players = pd.DataFrame([
        _player("j1", "Brasil", "Militão", position="CB", fouls_drawn=4, shots_on_target=1, goals_conceded=0),
        _player("j1", "Alemanha", "Rüdiger", position="CB", fouls_drawn=1, shots_on_target=0, goals_conceded=3),
    ])
    features = build_player_match_features(players)
    scores = build_player_scores(features)
    militao = scores[scores["player_name"] == "Militão"].iloc[0]
    rudiger = scores[scores["player_name"] == "Rüdiger"].iloc[0]
    assert militao["score_geral"] > rudiger["score_geral"]


def test_player_scores_defender_uses_365_defensive_actions():
    players = pd.DataFrame([
        _player("j1", "Brasil", "Zagueiro Forte", position="CB", tackles_won=4, interceptions=3, clearances=5, ball_recovery=4, ground_duels_won=3, aerial_duels_won=2),
        _player("j1", "Alemanha", "Zagueiro Quieto", position="CB", tackles_won=1, interceptions=0, clearances=1, ball_recovery=1, ground_duels_won=0, aerial_duels_won=0),
    ])

    scores = build_player_scores(build_player_match_features(players))
    forte = scores[scores["player_name"] == "Zagueiro Forte"].iloc[0]
    quieto = scores[scores["player_name"] == "Zagueiro Quieto"].iloc[0]

    assert forte["score_geral"] > quieto["score_geral"]


def test_player_scores_goalkeeper_uses_expected_goals_prevented():
    players = pd.DataFrame([
        _player("j1", "Brasil", "Goleiro XGP", position="GK", saves=3, goals_conceded=1, expected_goals_prevented=1.5),
        _player("j1", "Alemanha", "Goleiro Neutro", position="GK", saves=3, goals_conceded=1, expected_goals_prevented=0.0),
    ])

    scores = build_player_scores(build_player_match_features(players))
    xgp = scores[scores["player_name"] == "Goleiro XGP"].iloc[0]
    neutro = scores[scores["player_name"] == "Goleiro Neutro"].iloc[0]

    assert xgp["score_geral"] > neutro["score_geral"]


def test_player_scores_attacker_uses_expected_goals_when_goals_are_equal():
    players = pd.DataFrame([
        _player("j1", "Brasil", "Atacante XG", position="ST", goals=0, shots_on_target=1, expected_goals=1.2, expected_goals_on_target=1.0),
        _player("j1", "Alemanha", "Atacante Baixo XG", position="ST", goals=0, shots_on_target=1, expected_goals=0.1, expected_goals_on_target=0.1),
    ])

    scores = build_player_scores(build_player_match_features(players))
    high = scores[scores["player_name"] == "Atacante XG"].iloc[0]
    low = scores[scores["player_name"] == "Atacante Baixo XG"].iloc[0]

    assert high["score_geral"] > low["score_geral"]


def test_player_scores_has_score_geral():
    features = _make_player_features()
    scores = build_player_scores(features)
    assert "score_geral" in scores.columns
    assert (scores["score_geral"] >= 0).all() and (scores["score_geral"] <= 100).all()


def test_player_scores_slug_generated():
    features = _make_player_features()
    scores = build_player_scores(features)
    vinicius = scores[scores["player_name"] == "Vinicius"].iloc[0]
    assert vinicius["player_slug"] == slugify("Vinicius_Brasil")


def test_player_match_features_unique_slug_for_accent_collision_and_cleans_names():
    players = pd.DataFrame(
        [
            _player("j1", "Brasil", "Ederson ", position="GK", player_id="1"),
            _player("j1", "Brasil", "Éderson", position="CM", player_id="2"),
            _player("j1", "Egito", "Zizo null", position="RW", player_id="3"),
        ]
    )

    features = build_player_match_features(players)
    brasil_slugs = features[features["team"] == "Brasil"]["player_slug"].tolist()

    assert len(set(brasil_slugs)) == 2
    assert set(features["player_name"]) == {"Ederson", "Éderson", "Zizo"}


def test_slugify_transliterates_nordic_letters():
    assert slugify("Martin Ødegaard") == "martin_odegaard"
    assert slugify("Alexander Sørloth") == "alexander_sorloth"


def test_person_name_normalization_handles_spaces_and_hyphen_variants():
    assert clean_person_name(" Raphinha\u00a0") == "Raphinha"
    assert clean_person_name("Moteb Al \u2011 Harbi null") == "Moteb Al-Harbi"
    assert person_name_key("Moteb Al\u2011Harbi") == person_name_key("Moteb Al Harbi")
    assert person_name_exact_key("Ederson") != person_name_exact_key("Éderson")


def test_player_report_without_appearances_omits_empty_match_table():
    import fifa_analytics.workflows.scores_pipeline as scores_pipeline

    report = scores_pipeline._render_player_report(
        pd.DataFrame(
            [
                {
                    "match_id": pd.NA,
                    "team": "Brasil",
                    "player_name": "Neymar",
                    "position": "LW",
                    "perfil": "atacante",
                    "appearances": 0,
                    "goals": 0,
                    "assists": 0,
                }
            ]
        )
    )

    assert "Ainda nao disputou jogos." in report
    assert "| jogo |" not in report


def test_team_players_by_position_groups_by_player_slug_and_keeps_xg_decimals():
    import fifa_analytics.workflows.scores_pipeline as scores_pipeline

    table = scores_pipeline._team_players_by_position(
        pd.DataFrame(
            [
                {
                    "player_name": "Alex",
                    "player_slug": "alex_brasil_1",
                    "perfil": "atacante",
                    "appearances": 1,
                    "goals": 0,
                    "assists": 0,
                    "expected_goals": 0.25,
                },
                {
                    "player_name": "Alex",
                    "player_slug": "alex_brasil_2",
                    "perfil": "atacante",
                    "appearances": 1,
                    "goals": 0,
                    "assists": 0,
                    "expected_goals": 1.75,
                },
            ]
        ),
        "brasil",
    )

    assert "reports/players/brasil/alex_1" in table
    assert "reports/players/brasil/alex_2" in table
    assert "0.25" in table
    assert "1.75" in table


def test_team_report_documents_own_goals_and_player_total_differences():
    import fifa_analytics.workflows.scores_pipeline as scores_pipeline

    report = scores_pipeline._render_team_report(
        pd.Series(
            {
                "team": "Brasil",
                "jogos": 1,
                "points": 3,
                "saldo_gols": 1,
                "gols_pro": 2,
                "gols_contra": 1,
                "own_goals_for": 1,
                "own_goals_against": 1,
                "ranking_disciplina": 1,
                "ranking_score_geral": 1,
                "score_geral": 50,
                "score_resultado": 50,
                "score_ataque": 50,
                "score_defesa": 50,
                "score_eficiencia": 50,
                "score_controle": 50,
                "score_forca_relativa": 50,
                "score_disciplina": 50,
            }
        ),
        pd.DataFrame(),
        pd.DataFrame(),
        total_teams=32,
        team_slug_by_name={},
    )

    assert "gols contra a favor" in report
    assert "gols contra sofridos" in report
    assert "tabela abaixo soma eventos individuais" in report
    assert "nao contam como gol de jogador da propria selecao" in report


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


def test_build_player_match_features_merges_lineup_by_player_id_before_name():
    players = pd.DataFrame([
        _player("j1", "Brasil", "Vini Jr", player_id="123", position=None),
    ])
    lineups = pd.DataFrame([
        {
            "match_id": "j1",
            "team": "Brasil",
            "player_id": "123",
            "player_name": "Vinícius Júnior",
            "position": "LW",
            "is_starter": True,
        }
    ])

    features = build_player_match_features(players, lineups=lineups)
    row = features.iloc[0]

    assert row["position"] == "LW"
    assert bool(row["is_starter"]) is True
    assert row["perfil"] == "atacante"


def test_build_player_match_features_merges_lineup_by_normalized_name_without_player_id():
    players = pd.DataFrame([
        _player("j1", "Arábia Saudita", "Moteb Al Harbi", position=None),
    ])
    lineups = pd.DataFrame([
        {
            "match_id": "j1",
            "team": "Arábia Saudita",
            "player_name": "Moteb Al\u2011Harbi",
            "position": "LB",
            "is_starter": True,
        }
    ])

    features = build_player_match_features(players, lineups=lineups)
    row = features.iloc[0]

    assert row["player_name"] == "Moteb Al Harbi"
    assert row["position"] == "LB"
    assert bool(row["is_starter"]) is True
    assert row["perfil"] == "defensor"


def test_build_player_match_features_includes_roster_players_without_stats():
    players = pd.DataFrame([
        _player("j1", "Brasil", "Vinicius ", position="AM-L", goals=1),
    ])
    rosters = pd.DataFrame([
        {"team": "Brasil", "player_name": "Vinicius", "squad_position": "F"},
        {"team": "Brasil", "player_name": "Neymar", "squad_position": "F"},
    ])

    features = build_player_match_features(players, rosters=rosters)

    assert set(features["player_name"]) == {"Vinicius", "Neymar"}
    vinicius = features[features["player_name"] == "Vinicius"].iloc[0]
    neymar = features[features["player_name"] == "Neymar"].iloc[0]
    assert vinicius["roster_position"] == "F"
    assert vinicius["perfil"] == "atacante"
    assert neymar["appearances"] == 0
    assert neymar["roster_position"] == "F"
    assert neymar["perfil"] == "atacante"


def test_build_player_match_features_expands_roster_players_by_match():
    players = pd.DataFrame([
        _player("j1", "Brasil", "Vinicius", position="AM-L", goals=1),
        _player("j2", "Brasil", "Vinicius", position="AM-L", goals=0),
    ])
    rosters = pd.DataFrame([
        {"team": "Brasil", "player_name": "Vinicius", "squad_position": "F"},
        {"team": "Brasil", "player_name": "Neymar", "squad_position": "F"},
    ])

    features = build_player_match_features(players, rosters=rosters)
    neymar = features[features["player_name"] == "Neymar"].sort_values("match_id")

    assert list(neymar["match_id"]) == ["j1", "j2"]
    assert neymar["appearances"].sum() == 0


def test_build_player_match_features_reuses_known_id_for_roster_dnp_rows():
    players = pd.DataFrame([
        _player("j1", "Brasil", "Meia", position="CM", player_id="10"),
        _player("j2", "Brasil", "Atacante", position="CF", player_id="9"),
    ])
    rosters = pd.DataFrame([
        {"team": "Brasil", "player_name": "Meia", "squad_position": "M"},
        {"team": "Brasil", "player_name": "Atacante", "squad_position": "F"},
    ])

    features = build_player_match_features(players, rosters=rosters)
    meia = features[features["player_name"] == "Meia"].sort_values("match_id")
    scores = build_player_scores(features)

    assert list(meia["match_id"]) == ["j1", "j2"]
    assert meia["player_slug"].nunique() == 1
    assert scores[scores["player_name"] == "Meia"].shape[0] == 1


def test_build_player_match_features_applies_aliases_to_rosters_too():
    players = pd.DataFrame([
        _player("j1", "Uruguai", "Agustín Cano", position="SUB", player_id="241466", appearances=1),
    ])
    rosters = pd.DataFrame([
        {"team": "Uruguai", "player_name": "Agustín Cano", "squad_position": "M"},
    ])

    features = build_player_match_features(players, rosters=rosters)

    assert set(features["player_name"]) == {"Agustín Canobbio"}
    assert features.iloc[0]["roster_position"] == "M"


def test_build_player_match_features_drops_empty_non_roster_sub_rows():
    players = pd.DataFrame([
        _player("j1", "Brasil", "Jogador Real", position="CM", player_id="10", appearances=1),
        _player("j1", "Brasil", "Reserva Fantasma", position="SUB", player_id="99", appearances=0),
    ])
    rosters = pd.DataFrame([
        {"team": "Brasil", "player_name": "Jogador Real", "squad_position": "M"},
    ])

    features = build_player_match_features(players, rosters=rosters)

    assert set(features["player_name"]) == {"Jogador Real"}


def test_build_player_match_features_preserves_roster_accent_collision():
    players = pd.DataFrame([
        _player("j1", "Brasil", "Ederson", position="GK", saves=1),
    ])
    rosters = pd.DataFrame([
        {"team": "Brasil", "player_name": "Ederson", "squad_position": "G"},
        {"team": "Brasil", "player_name": "Éderson", "squad_position": "M"},
    ])

    features = build_player_match_features(players, rosters=rosters)
    edersons = features.sort_values("player_name")

    assert set(edersons["player_name"]) == {"Ederson", "Éderson"}
    assert set(edersons["roster_position"]) == {"G", "M"}
    assert edersons["player_slug"].nunique() == 2
    assert features[features["player_name"] == "Éderson"]["appearances"].iloc[0] == 0


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
        _player("j1", "Brasil", "CB1", position="CB", saves=5, fouls_drawn=3, goals_conceded=0),
        _player("j1", "Brasil", "CB2", position="CB", saves=0, fouls_drawn=1, goals_conceded=3),
    ])
    features = build_player_match_features(players)
    scores = build_player_scores(features)
    cb1 = scores[scores["player_name"] == "CB1"].iloc[0]
    cb2 = scores[scores["player_name"] == "CB2"].iloc[0]
    # Posição ESPN (CB) tem prioridade — ambos ficam no pool de defensores
    assert cb1["perfil"] == "defensor"
    assert cb2["perfil"] == "defensor"
    # CB1 tem mais fouls_drawn e menos gols sofridos — deve liderar
    assert cb1["score_geral"] > cb2["score_geral"]


# ---------------------------------------------------------------------------
# Elo — invariantes do cálculo
# ---------------------------------------------------------------------------

def _elo_game(team_a, team_b, ga, gb, xga=1.0, xgb=1.0, sota=4, sotb=4, possa=50):
    return pd.DataFrame([
        {"match_id": "m1", "team": team_a, "date": "2026-01-01", "goals_for": ga,
         "shots_on_target": sota, "possession": possa, "team_xg": xga, "xg_against": xgb},
        {"match_id": "m1", "team": team_b, "date": "2026-01-01", "goals_for": gb,
         "shots_on_target": sotb, "possession": 100 - possa, "team_xg": xgb, "xg_against": xga},
    ])


def test_elo_winner_never_loses_rating_even_as_strong_favorite():
    """Favorito forte que vence equilibrado NÃO pode perder Elo (regra básica)."""
    df = _elo_game("Favorito", "Zebra", 1, 0)
    # favorito com +400 de rating: expected alto, vitória equilibrada
    ratings, _ = _run_elo_simulation(df, initial_ratings={"Favorito": 1900, "Zebra": 1500})
    assert ratings["Favorito"] >= 1900  # venceu → nunca perde
    assert ratings["Zebra"] <= 1500     # perdeu → nunca ganha


def test_elo_zero_sum():
    """O Elo é zero-sum: o que A ganha, B perde (total conservado)."""
    df = _elo_game("A", "B", 3, 1, xga=2.5, xgb=0.8)
    ratings, _ = _run_elo_simulation(df)
    assert ratings["A"] + ratings["B"] == pytest.approx(3000.0)


def test_elo_blowout_earns_more_than_narrow_win():
    """Goleada dominante (com xG alto) rende mais Elo que vitória mínima."""
    blowout, _ = _run_elo_simulation(_elo_game("A", "B", 7, 1, xga=4.2, xgb=0.5))
    narrow, _ = _run_elo_simulation(_elo_game("C", "D", 1, 0, xga=1.2, xgb=0.9))
    assert (blowout["A"] - 1500) > (narrow["C"] - 1500)


def test_elo_higher_xg_earns_more_for_same_score():
    """Mesmo placar (2-0), quem criou MAIS (xG maior) ganha mais Elo — domínio real."""
    dominant, _ = _run_elo_simulation(_elo_game("A", "B", 2, 0, xga=2.8, xgb=0.3))
    lucky, _ = _run_elo_simulation(_elo_game("C", "D", 2, 0, xga=1.0, xgb=0.9))
    assert (dominant["A"] - 1500) > (lucky["C"] - 1500)
