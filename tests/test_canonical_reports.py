import pandas as pd

from fifa_analytics.workflows.canonical_reports import build_canonical_index


def test_build_canonical_index_merges_same_match_from_multiple_sources():
    source_matches = {
        "worldcup2026": pd.DataFrame(
            [
                {
                    "match_id": "australia_turquia_2026_match_6",
                    "source_match_id": "6",
                    "home_team": "Austrália",
                    "away_team": "Turquia",
                    "group": "D",
                    "stage": "fase_de_grupos",
                    "status": "finalizado",
                    "home_score": 2,
                    "away_score": 0,
                }
            ]
        ),
        "wikipedia": pd.DataFrame(
            [
                {
                    "match_id": "australia_turquia_2026_match_20",
                    "source_match_id": "Match 20",
                    "home_team": "Austrália",
                    "away_team": "Turquia",
                    "group": "D",
                    "stage": "fase_de_grupos",
                    "status": "finalizado",
                    "home_score": 2,
                    "away_score": 0,
                }
            ]
        ),
    }

    canonical, source_map = build_canonical_index(source_matches)

    assert len(canonical) == 1
    assert canonical.iloc[0]["canonical_match_id"] == "copa_2026_jogo_006"
    assert canonical.iloc[0]["primary_source"] == "worldcup2026"
    assert canonical.iloc[0]["worldcup2026_source_match_id"] == "6"
    assert canonical.iloc[0]["wikipedia_source_match_id"] == "Match 20"
    assert set(source_map["source"]) == {"worldcup2026", "wikipedia"}


def test_build_canonical_index_keeps_source_number_and_adds_temporal_order():
    source_matches = {
        "worldcup2026": pd.DataFrame(
            [
                {
                    "match_id": "late_match_13",
                    "source_match_id": "13",
                    "home_team": "Irã",
                    "away_team": "Nova Zelândia",
                    "group": "G",
                    "stage": "fase_de_grupos",
                    "date": "2026-06-15",
                    "kickoff_time": "18:00",
                    "status": "finalizado",
                },
                {
                    "match_id": "early_match_14",
                    "source_match_id": "14",
                    "home_team": "Espanha",
                    "away_team": "Cabo Verde",
                    "group": "H",
                    "stage": "fase_de_grupos",
                    "date": "2026-06-15",
                    "kickoff_time": "12:00",
                    "status": "finalizado",
                },
            ]
        )
    }

    canonical, _ = build_canonical_index(source_matches)

    early = canonical[canonical["canonical_match_id"] == "copa_2026_jogo_014"].iloc[0]
    late = canonical[canonical["canonical_match_id"] == "copa_2026_jogo_013"].iloc[0]
    assert early["match_number"] == 14
    assert late["match_number"] == 13
    assert early["temporal_order"] == 1
    assert late["temporal_order"] == 2


def test_build_canonical_index_keeps_knockout_match_without_defined_teams():
    source_matches = {
        "worldcup2026": pd.DataFrame(
            [
                {
                    "match_id": "worldcup2026_match_104",
                    "source_match_id": "104",
                    "home_team": None,
                    "away_team": None,
                    "group": "FINAL",
                    "stage": "final",
                    "status": "agendado",
                }
            ]
        )
    }

    canonical, source_map = build_canonical_index(source_matches)

    assert len(canonical) == 1
    assert canonical.iloc[0]["canonical_match_id"] == "copa_2026_jogo_104"
    assert source_map.iloc[0]["source_source_match_id"] == "104"


def test_build_canonical_index_avoids_source_number_collision_for_unmatched_secondary_source():
    source_matches = {
        "worldcup2026": pd.DataFrame(
            [
                {
                    "match_id": "argentina_argelia_2026_match_19",
                    "source_match_id": "19",
                    "home_team": "Argentina",
                    "away_team": "Argélia",
                    "group": "J",
                    "stage": "fase_de_grupos",
                    "status": "agendado",
                }
            ]
        ),
        "wikipedia": pd.DataFrame(
            [
                {
                    "match_id": "estados_unidos_paraguai_2026_match_19",
                    "source_match_id": "Match 19",
                    "home_team": "Estados Unidos",
                    "away_team": "Paraguai",
                    "group": "D",
                    "stage": "fase_de_grupos",
                    "status": "finalizado",
                }
            ]
        ),
    }

    canonical, source_map = build_canonical_index(source_matches)

    assert set(canonical["canonical_match_id"]) == {"copa_2026_jogo_019", "copa_2026_wikipedia_jogo_019"}
    assert len(source_map[source_map["canonical_match_id"] == "copa_2026_jogo_019"]) == 1


def test_build_canonical_index_matches_knockout_placeholders_by_order():
    source_matches = {
        "worldcup2026": pd.DataFrame(
            [
                {
                    "match_id": "worldcup2026_match_73",
                    "source_match_id": "73",
                    "home_team": None,
                    "away_team": None,
                    "stage": "r32",
                    "date": "2026-06-28",
                    "status": "agendado",
                },
                {
                    "match_id": "worldcup2026_match_74",
                    "source_match_id": "74",
                    "home_team": None,
                    "away_team": None,
                    "stage": "r32",
                    "date": "2026-06-29",
                    "status": "agendado",
                },
            ]
        ),
        "espn": pd.DataFrame(
            [
                {
                    "match_id": "group_a_2nd_place_group_b_2nd_place_espn_760486",
                    "source_match_id": "760486",
                    "home_team": "Group A 2nd Place",
                    "away_team": "Group B 2nd Place",
                    "stage": "dezesseis_avos",
                    "date": "2026-06-28",
                    "status": "agendado",
                },
                {
                    "match_id": "group_c_winner_group_f_2nd_place_espn_760487",
                    "source_match_id": "760487",
                    "home_team": "Group C Winner",
                    "away_team": "Group F 2nd Place",
                    "stage": "dezesseis_avos",
                    "date": "2026-06-29",
                    "status": "agendado",
                },
            ]
        ),
    }

    canonical, source_map = build_canonical_index(source_matches)

    assert len(canonical) == 2
    assert set(canonical["canonical_match_id"]) == {"copa_2026_jogo_073", "copa_2026_jogo_074"}
    assert len(source_map[source_map["canonical_match_id"] == "copa_2026_jogo_073"]) == 2
