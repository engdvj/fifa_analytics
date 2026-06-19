import pandas as pd
import pytest

from fifa_analytics.workflows.canonical_reports import (
    _attach_player_rating,
    _linked_event_description,
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


def test_attach_player_rating_rejects_ambiguous_single_token_matches(tmp_path, monkeypatch):
    import fifa_analytics.workflows.canonical_reports as cr_module

    rating_dir = tmp_path / "fact_player_match_stats"
    rating_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"match_id": "j1", "team": "Mexico", "player_name": "Cesar Montes", "rating": 7.4, "expected_goals": 0.1, "tackles_won": 3},
            {"match_id": "j1", "team": "Mexico", "player_name": "Luis Chavez", "rating": 6.8, "expected_goals": 0.2, "tackles_won": 1},
            {"match_id": "j1", "team": "Brasil", "player_name": "Danilo", "rating": 6.8, "expected_goals": 0.0, "tackles_won": 4},
            {"match_id": "j1", "team": "Inglaterra", "player_name": "Kane", "rating": 8.1, "expected_goals": 1.4, "tackles_won": 0},
        ]
    ).to_parquet(rating_dir / "365scores_rating.parquet")
    monkeypatch.setattr(cr_module, "GOLD_DIR", tmp_path)

    players = pd.DataFrame(
        [
            {"match_id": "j1", "team": "Mexico", "player_name": "César Huerta"},
            {"match_id": "j1", "team": "Mexico", "player_name": "Cesar Montes"},
            {"match_id": "j1", "team": "Mexico", "player_name": "Luis Romo"},
            {"match_id": "j1", "team": "Brasil", "player_name": "Danilo"},
            {"match_id": "j1", "team": "Brasil", "player_name": "Danilo Santos"},
            {"match_id": "j1", "team": "Inglaterra", "player_name": "Harry Kane"},
        ]
    )

    out = _attach_player_rating(players)
    ratings = dict(zip(out["player_name"], out["rating"]))

    assert pd.isna(ratings["César Huerta"])
    assert ratings["Cesar Montes"] == 7.4
    assert pd.isna(ratings["Luis Romo"])
    assert ratings["Danilo"] == 6.8
    assert pd.isna(ratings["Danilo Santos"])
    assert ratings["Harry Kane"] == 8.1
    kane = out[out["player_name"] == "Harry Kane"].iloc[0]
    assert kane["expected_goals"] == 1.4
    assert kane["tackles_won"] == 0


def test_own_goal_links_player_to_opponent_team():
    event = pd.Series(
        {
            "event_type": "gol_contra",
            "team": "Catar",
            "opponent": "Suíça",
            "player": "Miro Muheim",
        }
    )

    description = _linked_event_description(event)

    assert "reports/players/suica/miro_muheim" in description
    assert "reports/teams/catar" in description


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


def test_build_canonical_index_uses_more_advanced_status_when_primary_is_stale():
    """Fonte primária desatualizada não pode manter o jogo 'agendado' quando
    outra fonte já o vê ao vivo. Regressão do bug: worldcup2026 caía (SSL) e
    ficava com status velho, escondendo o jogo ao vivo que a ESPN reportava."""
    source_matches = {
        "worldcup2026": pd.DataFrame([{
            "match_id": "suica_bosnia_2026_match_26",
            "source_match_id": "26",
            "home_team": "Suíça",
            "away_team": "Bósnia e Herzegovina",
            "group": "L",
            "stage": "fase_de_grupos",
            "status": "agendado",  # fonte primária desatualizada
            "home_score": None,
            "away_score": None,
        }]),
        "espn": pd.DataFrame([{
            "match_id": "suica_bosnia_espn_99",
            "source_match_id": "99",
            "source_match_number": 26,
            "home_team": "Suíça",
            "away_team": "Bósnia e Herzegovina",
            "group": "L",
            "stage": "fase_de_grupos",
            "status": "ao_vivo",  # ESPN vê o jogo acontecendo
            "home_score": 3,
            "away_score": 1,
        }]),
    }

    canonical, _ = build_canonical_index(source_matches)

    row = canonical.iloc[0]
    assert row["status"] == "ao_vivo"
    assert row["home_score"] == 3
    assert row["away_score"] == 1
    # campos estáveis continuam vindo da fonte primária
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


def test_build_canonical_events_merges_corrupted_names_keeps_stoppage_distinct(tmp_path, monkeypatch):
    """Dedup robusto a ruído de fonte: nome corrompido no MESMO minuto funde
    (worldcup2026 'Jvhan Mnzambi' = espn 'Johan Manzambi'); gol de acréscimo com
    OUTRO jogador é mantido (Xhaka 90'+7) — o gol extra que só uma fonte tinha."""
    import fifa_analytics.workflows.canonical_reports as cr_module

    espn_events = pd.DataFrame([
        {"match_id": "espn_1", "event_type": "gol",        "minute": "90",   "minute_sort": 9000, "team": "Suíça", "player": "Johan Manzambi"},
        {"match_id": "espn_1", "event_type": "gol_penalti", "minute": "90+7", "minute_sort": 9007, "team": "Suíça", "player": "Granit Xhaka"},
    ])
    wc_events = pd.DataFrame([
        # mesmo gol do Manzambi aos 90', nome corrompido pela fonte
        {"match_id": "wc_1", "event_type": "gol", "minute": "90", "minute_sort": 9000, "team": "Suíça", "player": "Jvhan Mnzambi"},
    ])

    def fake_events_path(source: str):
        p = tmp_path / f"{source}_events.parquet"
        if source == "espn":
            espn_events.to_parquet(p, index=False)
        elif source == "worldcup2026":
            wc_events.to_parquet(p, index=False)
        return p

    monkeypatch.setattr(cr_module, "_events_path", fake_events_path)
    source_map = _make_source_map(
        ("copa_2026_jogo_001", "espn", "espn_1"),
        ("copa_2026_jogo_001", "worldcup2026", "wc_1"),
    )
    events = build_canonical_events(source_map)
    gols = events[events["event_type"].astype(str).str.contains("gol")]
    # 2 gols distintos (Manzambi 90' fundido + Xhaka 90'+7 mantido), não 3
    assert len(gols) == 2
    assert set(gols["minute"]) == {"90", "90+7"}


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


def test_build_canonical_dataset_deduplicates_player_entities_by_source_priority(tmp_path, monkeypatch):
    import fifa_analytics.workflows.canonical_reports as cr_module

    gold_dir = tmp_path / "gold"
    subdir = gold_dir / "fact_player_match_stats"
    subdir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"match_id": "espn_1", "team": "Brasil", "player_name": "Vinícius Júnior", "goals": 1},
        ]
    ).to_parquet(subdir / "espn_player_stats.parquet", index=False)
    pd.DataFrame(
        [
            {"match_id": "wiki_1", "team": "Brasil", "player_name": "Vinicius Junior", "goals": 0},
        ]
    ).to_parquet(subdir / "wikipedia_player_stats.parquet", index=False)

    monkeypatch.setattr(cr_module, "GOLD_DIR", gold_dir)

    source_map = _make_source_map(
        ("copa_2026_jogo_005", "espn", "espn_1"),
        ("copa_2026_jogo_005", "wikipedia", "wiki_1"),
    )
    result = build_canonical_dataset(source_map, "fact_player_match_stats", "player_stats")

    assert len(result) == 1
    assert result.iloc[0]["dataset_source"] == "espn"
    assert result.iloc[0]["goals"] == 1


def test_build_canonical_dataset_empty_when_no_files(tmp_path, monkeypatch):
    import fifa_analytics.workflows.canonical_reports as cr_module

    monkeypatch.setattr(cr_module, "GOLD_DIR", tmp_path / "gold")
    source_map = _make_source_map(("copa_2026_jogo_001", "espn", "espn_1"))
    result = build_canonical_dataset(source_map, "fact_team_match_stats", "team_stats")
    assert result.empty
