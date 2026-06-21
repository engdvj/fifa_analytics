"""Transforms da FIFA: raw JSON -> DataFrames (sem rede)."""

import json

import pandas as pd

from fifa_analytics.fifa import transforms


def _match(num, status, hs=None, as_=None):
    return {
        "MatchNumber": num,
        "MatchStatus": status,
        "IdMatch": f"40000{num}",
        "IdStage": "289273",
        "IdGroup": "289275",
        "Properties": {"IdIFES": f"15160{num}"},
        "Home": {"TeamName": [{"Locale": "en-GB", "Description": "Mexico"}], "IdTeam": "1", "IdCountry": "MEX"},
        "Away": {"TeamName": [{"Locale": "en-GB", "Description": "South Africa"}], "IdTeam": "2", "IdCountry": "RSA"},
        "HomeTeamScore": hs,
        "AwayTeamScore": as_,
        "Date": "2026-06-11T19:00:00Z",
        "LocalDate": "2026-06-11T13:00:00Z",
        "GroupName": [{"Locale": "en-GB", "Description": "Group A"}],
        "StageName": [{"Locale": "en-GB", "Description": "First Stage"}],
        "Stadium": {"Name": [{"Locale": "en-GB", "Description": "Estadio Azteca"}]},
    }


def _live_payload():
    """Payload sintético espelhando a estrutura real da v3 /live/football/...

    Times em HomeTeam/AwayTeam; Goals/Bookings/Substitutions dentro de cada
    time; Minute como string "N'"; Position como int; Card usa campo Card (int).
    """
    return {
        "IdMatch": "400001",
        "HomeTeam": {
            "IdTeam": "10",
            "Players": [
                {
                    "IdPlayer": "P1",
                    "PlayerName": [{"Locale": "en-GB", "Description": "Alisson"}],
                    "ShirtNumber": 1,
                    "Status": 1,
                    "Captain": False,
                    "Position": 0,   # G
                    "LineupX": 50,
                    "LineupY": 5,
                },
                {
                    "IdPlayer": "P2",
                    "PlayerName": [{"Locale": "en-GB", "Description": "Rodrygo"}],
                    "ShirtNumber": 11,
                    "Status": 0,
                    "Captain": False,
                    "Position": 3,   # F
                    "LineupX": None,
                    "LineupY": None,
                },
            ],
            "Goals": [
                {"IdTeam": "10", "IdPlayer": "P1", "Minute": "34'", "Type": 0, "IdAssistPlayer": None},
            ],
            "Bookings": [
                {"IdTeam": "10", "IdPlayer": "P1", "Minute": "55'", "Card": 1},  # yellow
            ],
            "Substitutions": [
                {
                    "IdTeam": "10",
                    "IdPlayerOff": "P1",
                    "PlayerOffName": [{"Locale": "en-GB", "Description": "Alisson"}],
                    "IdPlayerOn": "P2",
                    "PlayerOnName": [{"Locale": "en-GB", "Description": "Rodrygo"}],
                    "Minute": "70'",
                    "Reason": 0,
                },
            ],
        },
        "AwayTeam": {
            "IdTeam": "20",
            "Players": [
                {
                    "IdPlayer": "P3",
                    "PlayerName": [{"Locale": "en-GB", "Description": "Ederson"}],
                    "ShirtNumber": 1,
                    "Status": 1,
                    "Captain": True,
                    "Position": 0,   # G
                    "LineupX": 50,
                    "LineupY": 95,
                },
            ],
            "Goals": [
                {"IdTeam": "20", "IdPlayer": "P3", "Minute": "78'", "Type": 1, "IdAssistPlayer": None},  # own goal
            ],
            "Bookings": [],
            "Substitutions": [],
        },
    }


# ── calendário ────────────────────────────────────────────────────────────────

def test_normalize_matches_id_e_status():
    df = transforms.normalize_matches([_match(2, 1), _match(1, 0, 2, 0)])
    # ordena por match_number e gera id canônico
    assert list(df["match_id"]) == ["copa_2026_jogo_001", "copa_2026_jogo_002"]
    row = df.iloc[0]
    assert row["status"] == "finalizado"
    assert row["home_score"] == 2 and row["away_score"] == 0
    assert row["id_ifes"] == "151601"
    # jogo agendado não expõe placar (vira NaN na coluna mista; loader trata)
    assert df.iloc[1]["status"] == "agendado"
    assert pd.isna(df.iloc[1]["home_score"])
    assert row["home_team"] == "México"  # traduzido pt-BR


def test_normalize_match_team_stats_long():
    payload = {
        "43911": [["XG", 1.78, True], ["Possession", 0.57, True]],
        "43883": [["XG", 0.10, True]],
    }
    df = transforms.normalize_match_team_stats("copa_2026_jogo_001", "151600", payload)
    assert len(df) == 3
    xg = df[(df.id_team == "43911") & (df.metric == "XG")].iloc[0]
    assert xg["value"] == 1.78 and bool(xg["is_official"]) is True
    assert set(df["id_team"]) == {"43911", "43883"}


# ── escalações ────────────────────────────────────────────────────────────────

def test_normalize_lineups_colunas_e_lados():
    df = transforms.normalize_lineups("copa_2026_jogo_001", _live_payload())
    assert set(df["team_side"]) == {"home", "away"}
    assert len(df) == 3  # 2 home + 1 away
    titular = df[(df.team_side == "home") & (df.id_player == "P1")].iloc[0]
    assert titular["is_starter"] == True
    assert titular["position"] == "G"   # int 0 → "G"
    assert titular["lineup_x"] == 50
    banco = df[(df.team_side == "home") & (df.id_player == "P2")].iloc[0]
    assert banco["is_starter"] == False
    capitan = df[df.id_player == "P3"].iloc[0]
    assert capitan["captain"] == True


def test_normalize_lineups_payload_vazio():
    df = transforms.normalize_lineups("copa_2026_jogo_001", {})
    assert df.empty


# ── eventos ───────────────────────────────────────────────────────────────────

def test_normalize_match_events_tipos_e_contagem():
    df = transforms.normalize_match_events("copa_2026_jogo_001", _live_payload())
    assert len(df) == 4  # 2 gols + 1 cartão + 1 substituição
    assert set(df["event_type"]) == {"goal", "card", "substitution"}


def test_normalize_match_events_goal_detail():
    df = transforms.normalize_match_events("copa_2026_jogo_001", _live_payload())
    gols = df[df.event_type == "goal"].sort_values("minute")
    assert gols.iloc[0]["detail"] == "normal"
    assert gols.iloc[1]["detail"] == "own_goal"
    # Minute é string como retorna a v3 ("34'", "78'")
    assert gols.iloc[0]["minute"] == "34'"


def test_normalize_match_events_card_detail():
    df = transforms.normalize_match_events("copa_2026_jogo_001", _live_payload())
    card = df[df.event_type == "card"].iloc[0]
    assert card["detail"] == "yellow"
    assert card["minute"] == "55'"


def test_normalize_match_events_sub_detalhes():
    df = transforms.normalize_match_events("copa_2026_jogo_001", _live_payload())
    sub = df[df.event_type == "substitution"].iloc[0]
    assert sub["detail"] == "tactical"
    assert sub["player_name"] == "Alisson"   # saiu
    assert sub["player2_name"] == "Rodrygo"  # entrou
    assert sub["id_player2"] == "P2"


def test_normalize_match_events_payload_sem_eventos():
    df = transforms.normalize_match_events("copa_2026_jogo_001", {"HomeTeam": {}, "AwayTeam": {}})
    assert df.empty


# ── player stats ──────────────────────────────────────────────────────────────

def test_normalize_match_player_stats_long():
    payload = {
        "P1": [["Goals", 1, True], ["Passes", 42, True]],
        "P2": [["Goals", 0, True]],
    }
    df = transforms.normalize_match_player_stats("copa_2026_jogo_001", "151600", payload)
    assert len(df) == 3
    assert set(df["id_player"]) == {"P1", "P2"}
    goals_p1 = df[(df.id_player == "P1") & (df.metric == "Goals")].iloc[0]
    assert goals_p1["value"] == 1 and bool(goals_p1["is_official"]) is True


def test_normalize_match_player_stats_sem_is_official():
    payload = {"P1": [["XG", 0.45]]}  # sem 3º elemento
    df = transforms.normalize_match_player_stats("copa_2026_jogo_001", "151600", payload)
    assert df.iloc[0]["is_official"] is None


# ── power ranking ─────────────────────────────────────────────────────────────

def test_normalize_power_ranking_season_outfield_e_gk():
    """Estrutura real: playerId/teamId (int), playerName localizado,
    tournamentHistory no ROOT (não por jogador), 3 sets de rank/score/change."""
    payload = {
        "outfieldPlayers": [
            {
                "playerId": 1001, "teamId": 10,
                "playerName": [{"locale": "en-GB", "description": "Vinicius Jr"}],
                "teamName": [{"locale": "en-GB", "description": "Brazil"}],
                "attackingScore": 8.5, "attackingRank": 1,
                "attackingRankChange": 2, "attackingRankWithinTeam": 1,
                "defensiveScore": 5.0, "defensiveRank": 120,
                "defensiveRankChange": -1, "defensiveRankWithinTeam": 5,
                "creativityScore": 7.8, "creativityRank": 3,
                "creativityRankChange": 0, "creativityRankWithinTeam": 2,
            }
        ],
        "goalkeepers": [
            {
                # Goleiros usam inPossession/defendingTheGoal (não attacking/defensive)
                "playerId": 1002, "teamId": 10,
                "playerName": [{"locale": "en-GB", "description": "Alisson"}],
                "teamName": [{"locale": "en-GB", "description": "Brazil"}],
                "inPossessionScore": 6.5, "inPossessionRank": 3, "inPossessionRankChange": 1,
                "defendingTheGoalScore": 8.8, "defendingTheGoalRank": 1, "defendingTheGoalRankChange": 2,
            }
        ],
        # tournamentHistory no ROOT indexado por playerId
        "tournamentHistory": [
            {"playerId": 1001, "history": [{"round": 1, "attackingRank": 3, "attackingScore": 7.2}]},
        ],
    }
    df = transforms.normalize_power_ranking_season(payload)
    assert len(df) == 2
    assert set(df["player_type"]) == {"outfield", "goalkeeper"}

    vini = df[df.id_player == "1001"].iloc[0]
    assert vini["player_name"] == "Vinicius Jr"
    assert vini["team_name"] == "Brasil"  # traduzido pt-BR
    assert vini["attacking_score"] == 8.5
    assert vini["attacking_rank"] == 1
    assert vini["attacking_rank_change"] == 2
    history = json.loads(vini["tournament_history"])
    assert len(history) == 1
    assert history[0]["round"] == 1

    ali = df[df.id_player == "1002"].iloc[0]
    assert ali["player_type"] == "goalkeeper"
    # inPossession → attacking slot; defendingTheGoal → defensive slot
    assert ali["attacking_score"] == 6.5
    assert ali["attacking_rank"] == 3
    assert ali["defensive_score"] == 8.8
    assert ali["defensive_rank"] == 1
    assert pd.isna(ali["creativity_score"])
    assert json.loads(ali["tournament_history"]) == []  # sem history no root


def test_normalize_power_ranking_season_payload_vazio():
    df = transforms.normalize_power_ranking_season({})
    assert df.empty
