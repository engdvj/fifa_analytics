"""Transforms da FIFA: raw JSON -> DataFrames (sem rede)."""

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
