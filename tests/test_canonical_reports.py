import pandas as pd
import pytest

from fifa_analytics.workflows.canonical_reports import (
    build_canonical_dataset,
    build_canonical_events,
    build_canonical_index,
)


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


# ---------------------------------------------------------------------------
# Reconciliação: prioridade de fonte no placar divergente
# ---------------------------------------------------------------------------

def test_build_canonical_index_uses_primary_source_score_when_diverging():
    """Quando worldcup2026 e wikipedia divergem no placar, worldcup2026 prevalece."""
    source_matches = {
        "worldcup2026": pd.DataFrame([{
            "match_id": "brasil_alemanha_2026_match_1",
            "source_match_id": "1",
            "home_team": "Brasil",
            "away_team": "Alemanha",
            "group": "A",
            "stage": "fase_de_grupos",
            "status": "finalizado",
            "home_score": 3,
            "away_score": 1,
        }]),
        "wikipedia": pd.DataFrame([{
            "match_id": "brasil_alemanha_2026_match_1",
            "source_match_id": "Match 1",
            "home_team": "Brasil",
            "away_team": "Alemanha",
            "group": "A",
            "stage": "fase_de_grupos",
            "status": "finalizado",
            "home_score": 2,
            "away_score": 1,
        }]),
    }

    canonical, _ = build_canonical_index(source_matches)

    assert len(canonical) == 1
    row = canonical.iloc[0]
    assert row["home_score"] == 3
    assert row["primary_source"] == "worldcup2026"


def test_build_canonical_index_sources_count_reflects_all_matched():
    source_matches = {
        "worldcup2026": pd.DataFrame([{
            "match_id": "franca_espanha_2026_match_2",
            "source_match_id": "2",
            "home_team": "França",
            "away_team": "Espanha",
            "group": "B",
            "stage": "fase_de_grupos",
            "status": "finalizado",
            "home_score": 1,
            "away_score": 0,
        }]),
        "espn": pd.DataFrame([{
            "match_id": "franca_espanha_espn_99",
            "source_match_id": "99",
            "home_team": "França",
            "away_team": "Espanha",
            "group": "B",
            "stage": "fase_de_grupos",
            "status": "finalizado",
            "home_score": 1,
            "away_score": 0,
        }]),
        "wikipedia": pd.DataFrame([{
            "match_id": "franca_espanha_2026_match_2",
            "source_match_id": "Match 2",
            "home_team": "França",
            "away_team": "Espanha",
            "group": "B",
            "stage": "fase_de_grupos",
            "status": "finalizado",
            "home_score": 1,
            "away_score": 0,
        }]),
    }

    canonical, source_map = build_canonical_index(source_matches)

    assert len(canonical) == 1
    assert canonical.iloc[0]["sources_count"] == 3
    assert set(source_map["source"]) == {"worldcup2026", "espn", "wikipedia"}


# ---------------------------------------------------------------------------
# build_canonical_events: deduplicação por (match, minuto, time, tipo)
# ---------------------------------------------------------------------------

def _make_source_map(*pairs) -> pd.DataFrame:
    """pairs: (canonical_match_id, source, source_match_id)"""
    return pd.DataFrame([
        {"canonical_match_id": cid, "source": src, "source_match_id": smid}
        for cid, src, smid in pairs
    ])


def test_build_canonical_events_deduplicates_same_goal_two_sources(tmp_path, monkeypatch):
    """Gol no minuto 9 registrado em espn e worldcup2026 — deve resultar em 1 evento."""
    import fifa_analytics.workflows.canonical_reports as cr_module

    espn_events = pd.DataFrame([{
        "match_id": "espn_match_1",
        "event_type": "gol",
        "minute": "9",
        "minute_sort": 900,
        "team": "Brasil",
        "player": "Vinicius",
    }])
    wc_events = pd.DataFrame([{
        "match_id": "wc_match_1",
        "event_type": "gol",
        "minute": "9",
        "minute_sort": 900,
        "team": "Brasil",
        "player": "Vinicius",
    }])

    def fake_events_path(source: str):
        p = tmp_path / f"{source}_events.parquet"
        if source == "espn":
            espn_events.to_parquet(p, index=False)
        elif source == "worldcup2026":
            wc_events.to_parquet(p, index=False)
        return p

    monkeypatch.setattr(cr_module, "_events_path", fake_events_path)

    source_map = _make_source_map(
        ("copa_2026_jogo_001", "espn", "espn_match_1"),
        ("copa_2026_jogo_001", "worldcup2026", "wc_match_1"),
    )

    events = build_canonical_events(source_map)

    assert len(events) == 1
    assert events.iloc[0]["match_id"] == "copa_2026_jogo_001"
    assert events.iloc[0]["minute"] == "9"


def test_build_canonical_events_keeps_different_goals_same_match(tmp_path, monkeypatch):
    """Dois gols diferentes (minutos distintos) de fontes distintas — ambos devem aparecer."""
    import fifa_analytics.workflows.canonical_reports as cr_module

    espn_events = pd.DataFrame([
        {"match_id": "espn_1", "event_type": "gol", "minute": "9",  "minute_sort": 900,  "team": "Brasil", "player": "Vinicius"},
        {"match_id": "espn_1", "event_type": "gol", "minute": "67", "minute_sort": 6700, "team": "Brasil", "player": "Rodrygo"},
    ])

    def fake_events_path(source: str):
        p = tmp_path / f"{source}_events.parquet"
        if source == "espn":
            espn_events.to_parquet(p, index=False)
        return p

    monkeypatch.setattr(cr_module, "_events_path", fake_events_path)

    source_map = _make_source_map(("copa_2026_jogo_001", "espn", "espn_1"))
    events = build_canonical_events(source_map)

    assert len(events) == 2
    assert set(events["minute"]) == {"9", "67"}


def test_build_canonical_events_empty_when_no_source_files(tmp_path, monkeypatch):
    import fifa_analytics.workflows.canonical_reports as cr_module

    monkeypatch.setattr(cr_module, "_events_path", lambda s: tmp_path / f"nonexistent_{s}.parquet")
    source_map = _make_source_map(("copa_2026_jogo_001", "espn", "espn_1"))
    events = build_canonical_events(source_map)
    assert events.empty


# ---------------------------------------------------------------------------
# build_canonical_dataset: merge por source_map
# ---------------------------------------------------------------------------

def test_build_canonical_dataset_remaps_match_id(tmp_path, monkeypatch):
    """Dataset com match_id de fonte deve sair com canonical_match_id."""
    import fifa_analytics.workflows.canonical_reports as cr_module

    stats = pd.DataFrame([{
        "match_id": "espn_match_99",
        "team": "Brasil",
        "possession": 60,
    }])
    gold_dir = tmp_path / "gold"
    subdir = gold_dir / "fact_team_match_stats"
    subdir.mkdir(parents=True)
    stats.to_parquet(subdir / "espn_team_stats.parquet", index=False)

    monkeypatch.setattr(cr_module, "GOLD_DIR", gold_dir)

    source_map = _make_source_map(("copa_2026_jogo_005", "espn", "espn_match_99"))
    result = build_canonical_dataset(source_map, "fact_team_match_stats", "team_stats")

    assert len(result) == 1
    assert result.iloc[0]["match_id"] == "copa_2026_jogo_005"
    assert result.iloc[0]["team"] == "Brasil"
    assert result.iloc[0]["dataset_source"] == "espn"


def test_build_canonical_dataset_empty_when_no_files(tmp_path, monkeypatch):
    import fifa_analytics.workflows.canonical_reports as cr_module

    monkeypatch.setattr(cr_module, "GOLD_DIR", tmp_path / "gold")
    source_map = _make_source_map(("copa_2026_jogo_001", "espn", "espn_1"))
    result = build_canonical_dataset(source_map, "fact_team_match_stats", "team_stats")
    assert result.empty
