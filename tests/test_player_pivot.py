import pandas as pd

from fifa_analytics.fifa.player_pivot import build_player_match_wide


def _dim():
    return pd.DataFrame([
        {"match_id": "copa_2026_jogo_001", "home_team": "Alemanha", "away_team": "Curacao",
         "home_score": 7, "away_score": 1, "id_team_home": "GER", "id_team_away": "CUR"},
        {"match_id": "copa_2026_jogo_002", "home_team": "Alemanha", "away_team": "Costa do Marfim",
         "home_score": 2, "away_score": 1, "id_team_home": "GER", "id_team_away": "CIV"},
    ])


def _lineups():
    # Mesmo goleiro titular nos dois jogos pela Alemanha.
    return pd.DataFrame([
        {"match_id": "copa_2026_jogo_001", "id_player": "GK1", "player_name": "Manuel NEUER",
         "id_team": "GER", "position": "G", "shirt_number": 1, "is_starter": True},
        {"match_id": "copa_2026_jogo_002", "id_player": "GK1", "player_name": "Manuel NEUER",
         "id_team": "GER", "position": "G", "shirt_number": 1, "is_starter": True},
    ])


def test_goalkeeper_conceded_backfilled_from_scoreline_when_source_missing():
    # Fonte só trouxe GoalsConceded no jogo 1 (1 gol). No jogo 2 está ausente —
    # deve ser preenchido pelo placar (Costa do Marfim fez 1).
    long = pd.DataFrame([
        {"match_id": "copa_2026_jogo_001", "id_player": "GK1", "metric": "GoalsConceded", "value": 1},
        {"match_id": "copa_2026_jogo_001", "id_player": "GK1", "metric": "TimePlayed", "value": 95},
        {"match_id": "copa_2026_jogo_002", "id_player": "GK1", "metric": "TimePlayed", "value": 96},
        {"match_id": "copa_2026_jogo_002", "id_player": "GK1", "metric": "GoalkeeperSaves", "value": 3},
    ])
    wide = build_player_match_wide(long, _lineups(), _dim()).set_index("match_id")
    assert wide.loc["copa_2026_jogo_001", "gols_sofridos"] == 1  # fonte, intacto
    assert wide.loc["copa_2026_jogo_002", "gols_sofridos"] == 1  # backfill pelo placar
    assert wide["gols_sofridos"].sum() == 2


def test_backfill_sets_clean_sheet_on_zero_zero():
    long = pd.DataFrame([
        {"match_id": "copa_2026_jogo_001", "id_player": "GK1", "metric": "TimePlayed", "value": 90},
    ])
    dim = pd.DataFrame([
        {"match_id": "copa_2026_jogo_001", "home_team": "Alemanha", "away_team": "Curacao",
         "home_score": 0, "away_score": 0, "id_team_home": "GER", "id_team_away": "CUR"},
    ])
    ln = pd.DataFrame([
        {"match_id": "copa_2026_jogo_001", "id_player": "GK1", "player_name": "Manuel NEUER",
         "id_team": "GER", "position": "G", "shirt_number": 1, "is_starter": True},
    ])
    wide = build_player_match_wide(long, ln, dim).iloc[0]
    assert wide["gols_sofridos"] == 0
    assert wide["jogos_sem_sofrer"] == 1


def test_benched_goalkeeper_phantom_conceded_is_zeroed():
    # A FIFA credita GoalsConceded do time a TODOS os goleiros da súmula. O reserva
    # que não jogou (minutos=0) não pode acumular gols sofridos fantasma.
    long = pd.DataFrame([
        {"match_id": "copa_2026_jogo_002", "id_player": "GK_TIT", "metric": "GoalsConceded", "value": 1},
        {"match_id": "copa_2026_jogo_002", "id_player": "GK_TIT", "metric": "TimePlayed", "value": 96},
        # reserva: a fonte credita 1 sofrido mesmo sem jogar
        {"match_id": "copa_2026_jogo_002", "id_player": "GK_RES", "metric": "GoalsConceded", "value": 1},
        {"match_id": "copa_2026_jogo_002", "id_player": "GK_RES", "metric": "TimePlayed", "value": 0},
    ])
    ln = pd.DataFrame([
        {"match_id": "copa_2026_jogo_002", "id_player": "GK_TIT", "player_name": "Titular",
         "id_team": "GER", "position": "G", "shirt_number": 1, "is_starter": True},
        {"match_id": "copa_2026_jogo_002", "id_player": "GK_RES", "player_name": "Reserva",
         "id_team": "GER", "position": "G", "shirt_number": 12, "is_starter": False},
    ])
    wide = build_player_match_wide(long, ln, _dim()).set_index("id_player")
    assert wide.loc["GK_TIT", "gols_sofridos"] == 1   # titular mantém
    assert wide.loc["GK_RES", "gols_sofridos"] == 0   # reserva zerado


def test_backfill_does_not_touch_outfield_players():
    long = pd.DataFrame([
        {"match_id": "copa_2026_jogo_002", "id_player": "AT1", "metric": "Goals", "value": 1},
        {"match_id": "copa_2026_jogo_002", "id_player": "AT1", "metric": "TimePlayed", "value": 90},
    ])
    ln = pd.DataFrame([
        {"match_id": "copa_2026_jogo_002", "id_player": "AT1", "player_name": "Kai HAVERTZ",
         "id_team": "GER", "position": "F", "shirt_number": 7, "is_starter": True},
    ])
    wide = build_player_match_wide(long, ln, _dim()).iloc[0]
    # atacante não recebe gols sofridos do placar
    assert wide.get("gols_sofridos", 0) == 0
