import pandas as pd

from fifa_analytics.validation.match_validation import (
    compare_match_records,
    validate_match_completeness,
)
from fifa_analytics.validation.schemas import validate_required_columns


# ---------------------------------------------------------------------------
# validate_match_completeness — porta de qualidade por jogo
# ---------------------------------------------------------------------------

def _complete_fixtures(home_score=1, away_score=1, n_goal_events=2):
    """Monta um jogo íntegro: placar, 2 fontes primárias finalizadas, eventos
    com o nº certo de gols, stats de time (2), stats de jogador, lineups."""
    mid = "copa_2026_jogo_028"
    match = pd.Series({"canonical_match_id": mid, "home_team": "Tchéquia",
                       "away_team": "África do Sul", "home_score": home_score,
                       "away_score": away_score, "status": "finalizado"})
    source_map = pd.DataFrame([
        {"canonical_match_id": mid, "source": "worldcup2026", "status": "finalizado",
         "home_score": home_score, "away_score": away_score},
        {"canonical_match_id": mid, "source": "espn", "status": "finalizado",
         "home_score": home_score, "away_score": away_score},
    ])
    events = pd.DataFrame([
        {"match_id": mid, "event_type": "gol"} for _ in range(n_goal_events)
    ] + [{"match_id": mid, "event_type": "cartao_amarelo"}])
    team_stats = pd.DataFrame([{"match_id": mid, "team": "Tchéquia"},
                               {"match_id": mid, "team": "África do Sul"}])
    player_stats = pd.DataFrame([{"match_id": mid, "player_name": "X", "goals": 1}])
    lineups = pd.DataFrame([{"match_id": mid, "player_name": "X"}])
    return match, source_map, events, team_stats, player_stats, lineups


def test_completeness_passes_when_all_consistent():
    args = _complete_fixtures()
    assert validate_match_completeness(*args) == []


def test_completeness_blocks_goal_score_mismatch():
    # 3 gols nos eventos mas placar soma 2 (o "gol fantasma" do jogo 003)
    args = _complete_fixtures(home_score=1, away_score=1, n_goal_events=3)
    errors = validate_match_completeness(*args)
    assert any("gol" in e for e in errors)


def test_completeness_blocks_primary_source_not_finalized():
    args = list(_complete_fixtures())
    args[1].loc[args[1]["source"] == "espn", "status"] = "ao_vivo"  # ESPN defasada
    errors = validate_match_completeness(*args)
    assert any("não finalizada" in e for e in errors)


def test_completeness_ignores_stale_wikipedia():
    """Wikipedia atrasada (agendado) NÃO bloqueia — é fonte de referência."""
    match, source_map, events, team_stats, player_stats, lineups = _complete_fixtures()
    source_map = pd.concat([source_map, pd.DataFrame([
        {"canonical_match_id": match["canonical_match_id"], "source": "wikipedia",
         "status": "agendado", "home_score": None, "away_score": None}
    ])], ignore_index=True)
    assert validate_match_completeness(match, source_map, events, team_stats, player_stats, lineups) == []


def test_completeness_blocks_missing_team_stats():
    match, source_map, events, _, player_stats, lineups = _complete_fixtures()
    one_team = pd.DataFrame([{"match_id": match["canonical_match_id"], "team": "Tchéquia"}])
    errors = validate_match_completeness(match, source_map, events, one_team, player_stats, lineups)
    assert any("estatísticas de time" in e for e in errors)


def test_completeness_blocks_missing_score():
    match, source_map, events, team_stats, player_stats, lineups = _complete_fixtures()
    match["home_score"] = None
    errors = validate_match_completeness(match, source_map, events, team_stats, player_stats, lineups)
    assert any("placar ausente" in e for e in errors)


def test_compare_match_records_ok_when_values_match():
    primary = {"home_score": 2, "away_score": 0, "status": "finalizado", "stadium": "México City Stadium"}
    reference = {"home_score": 2, "away_score": 0, "status": "finalizado", "stadium": "México City Stadium"}

    result = compare_match_records(primary, reference)

    assert result["status"] == "ok"


def test_compare_match_records_warns_on_score_difference():
    primary = {"home_score": 2, "away_score": 0, "status": "finalizado", "stadium": "México City Stadium"}
    reference = {"home_score": 1, "away_score": 0, "status": "finalizado", "stadium": "México City Stadium"}

    result = compare_match_records(primary, reference)

    assert result["status"] == "aviso"


def test_validate_required_columns_reports_missing_columns():
    dataframe = pd.DataFrame([{"match_id": "example"}])

    result = validate_required_columns(dataframe, ["match_id", "home_team"])

    assert result["status"] == "ausente"
    assert result["missing_columns"] == ["home_team"]
