import pytest

import fifa_analytics.workflows.basic_reports as basic_reports_module


def test_run_basic_reports_rejects_source_specific_final_reports():
    with pytest.raises(ValueError, match="Relatorios finais usam a fonte 'canonical'"):
        basic_reports_module.run_basic_reports(source="wikipedia", status="finalizado")


def test_run_basic_reports_delegates_to_canonical_reports(monkeypatch):
    called = {}

    def fake_run_canonical_reports(status):
        called["status"] = status
        return {"fonte": "canonical", "status_processado": status}

    monkeypatch.setattr(basic_reports_module, "run_canonical_reports", fake_run_canonical_reports)

    result = basic_reports_module.run_basic_reports(status="finalizado")

    assert result == {"fonte": "canonical", "status_processado": "finalizado"}
    assert called["status"] == "finalizado"


def test_legacy_source_path_helpers_still_point_to_expected_files(tmp_path, monkeypatch):
    silver_dir = tmp_path / "silver"
    gold_dir = tmp_path / "gold"
    (silver_dir / "matches").mkdir(parents=True)
    (silver_dir / "validation_results").mkdir(parents=True)
    (gold_dir / "standings").mkdir(parents=True)

    monkeypatch.setattr(basic_reports_module, "SILVER_DIR", silver_dir)
    monkeypatch.setattr(basic_reports_module, "GOLD_DIR", gold_dir)

    assert basic_reports_module._matches_path("wikipedia") == silver_dir / "matches" / "wikipedia_matches.parquet"
    assert basic_reports_module._standings_path("wikipedia") == gold_dir / "standings" / "wikipedia_calculated_group_standings.parquet"
