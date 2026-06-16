from pathlib import Path

import fifa_analytics.reporting.build_report as build_report_module


def test_build_match_report_orders_fragments_and_records_missing_sections(tmp_path, monkeypatch):
    match_id = "mexico_africa_do_sul_2026_06_11"
    fragments_dir = tmp_path / "fragments"
    final_dir = tmp_path / "final"
    manifests_dir = tmp_path / "manifests"
    match_dir = fragments_dir / match_id
    match_dir.mkdir(parents=True)

    (match_dir / "00_metadata.md").write_text("<!-- metadata -->", encoding="utf-8")
    (match_dir / "01_match_summary.md").write_text("# México x África do Sul", encoding="utf-8")

    monkeypatch.setattr(build_report_module, "FRAGMENTS_DIR", fragments_dir)
    monkeypatch.setattr(build_report_module, "FINAL_REPORTS_DIR", final_dir)
    monkeypatch.setattr(build_report_module, "MANIFESTS_DIR", manifests_dir)

    result = build_report_module.build_match_report(match_id)

    report_path = Path(result["report_path"])
    assert report_path.exists()
    assert "# México x África do Sul" in report_path.read_text(encoding="utf-8")
    assert result["report_status"] == "parcial"
    assert "01b_story" in result["missing_sections"]
    assert "03_lineups" in result["missing_sections"]
