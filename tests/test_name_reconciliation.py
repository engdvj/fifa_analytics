import pandas as pd

from fifa_analytics.analytics.name_reconciliation import (
    _looks_truncated,
    _name_key,
    apply_player_aliases,
    detect_name_mismatches,
)


def test_name_key_normalizes_accent_case_and_hyphen():
    assert _name_key("Agustín  Cano") == "agustin cano"
    assert _name_key("Moteb Al-Harbi") == _name_key("Moteb Al Harbi")


def test_looks_truncated_detects_surname_prefix():
    assert _looks_truncated("agustin cano", "agustin canobbio")
    # nomes iguais não são truncamento
    assert not _looks_truncated("harry kane", "harry kane")
    # sobrenome diferente (não prefixo) não conta
    assert not _looks_truncated("agustin silva", "agustin canobbio")
    # último token curto demais evita falso positivo
    assert not _looks_truncated("a b", "a barcelona")


def test_apply_player_aliases_uses_curated_config():
    # o config real mapeia Uruguai: "Agustín Cano" -> "Agustín Canobbio"
    frame = pd.DataFrame([{"team": "Uruguai", "player_name": "Agustín Cano"}])
    out = apply_player_aliases(frame)
    assert out["player_name"].iloc[0] == "Agustín Canobbio"


def test_apply_player_aliases_leaves_unknown_names_untouched():
    frame = pd.DataFrame([{"team": "Brasil", "player_name": "Vinícius Júnior"}])
    out = apply_player_aliases(frame)
    assert out["player_name"].iloc[0] == "Vinícius Júnior"


def test_detect_name_mismatches_flags_truncated_surname():
    stats = pd.DataFrame([{"team": "Uruguai", "player_name": "Agustín Cano"}])
    rosters = pd.DataFrame([{"team": "Uruguai", "player_name": "Agustín Canobbio"}])
    report = detect_name_mismatches(stats, rosters, persist=False)
    assert len(report) == 1
    assert report.iloc[0]["stats_name"] == "Agustín Cano"
    assert report.iloc[0]["roster_name"] == "Agustín Canobbio"


def test_detect_name_mismatches_silent_on_exact_match():
    stats = pd.DataFrame([{"team": "Brasil", "player_name": "Vini Jr"}])
    rosters = pd.DataFrame([{"team": "Brasil", "player_name": "Vini Jr"}])
    assert detect_name_mismatches(stats, rosters, persist=False).empty
