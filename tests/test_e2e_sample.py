"""Teste de integração end-to-end com dados de amostra.

Executa o fluxo completo: ingest → silver → gold → fragments → relatório final.
Usa monkeypatch nos paths para isolar I/O em tmp_path.
"""
import fifa_analytics.paths as paths_module
import fifa_analytics.workflows.sample_pipeline as sample_module
import fifa_analytics.reporting.fragments as fragments_module
import fifa_analytics.reporting.build_report as build_report_module


def test_sample_pipeline_produces_report(tmp_path, monkeypatch):
    raw_dir = tmp_path / "data" / "raw"
    silver_dir = tmp_path / "data" / "silver"
    gold_dir = tmp_path / "data" / "gold"
    reports_dir = tmp_path / "reports"
    fragments_dir = reports_dir / "fragments"
    final_dir = reports_dir / "final"
    manifests_dir = tmp_path / "manifests"

    monkeypatch.setattr(paths_module, "RAW_DIR", raw_dir)
    monkeypatch.setattr(paths_module, "SILVER_DIR", silver_dir)
    monkeypatch.setattr(paths_module, "GOLD_DIR", gold_dir)
    monkeypatch.setattr(paths_module, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(paths_module, "FRAGMENTS_DIR", fragments_dir)
    monkeypatch.setattr(paths_module, "FINAL_REPORTS_DIR", final_dir)
    monkeypatch.setattr(paths_module, "MANIFESTS_DIR", manifests_dir)

    monkeypatch.setattr(sample_module, "RAW_DIR", raw_dir)
    monkeypatch.setattr(sample_module, "SILVER_DIR", silver_dir)
    monkeypatch.setattr(sample_module, "GOLD_DIR", gold_dir)
    monkeypatch.setattr(fragments_module, "FRAGMENTS_DIR", fragments_dir)
    monkeypatch.setattr(fragments_module, "TEMPLATES_DIR", paths_module.PROJECT_ROOT / "templates")
    monkeypatch.setattr(build_report_module, "FRAGMENTS_DIR", fragments_dir)
    monkeypatch.setattr(build_report_module, "FINAL_REPORTS_DIR", final_dir)
    monkeypatch.setattr(build_report_module, "MANIFESTS_DIR", manifests_dir)

    match_id = "mexico_africa_do_sul_2026_06_11"
    result = sample_module.run_sample_pipeline(match_id=match_id)

    assert result["match_id"] == match_id
    assert result["report_status"] in {"completo", "parcial"}

    assert (silver_dir / "matches" / "matches.parquet").exists()
    assert (silver_dir / "teams" / "teams.parquet").exists()
    assert (silver_dir / "standings" / "standings.parquet").exists()

    report_path = final_dir / f"{match_id}.md"
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "México" in content or "mexico" in content.lower()

    manifest_path = manifests_dir / f"{match_id}.yaml"
    assert manifest_path.exists()


def test_sample_pipeline_silver_matches_have_required_columns(tmp_path, monkeypatch):
    from fifa_analytics.utils.io import read_dataframe
    from fifa_analytics.validation.schemas import validate_required_columns

    raw_dir = tmp_path / "data" / "raw"
    silver_dir = tmp_path / "data" / "silver"
    gold_dir = tmp_path / "data" / "gold"
    fragments_dir = tmp_path / "reports" / "fragments"
    final_dir = tmp_path / "reports" / "final"
    manifests_dir = tmp_path / "manifests"

    monkeypatch.setattr(sample_module, "RAW_DIR", raw_dir)
    monkeypatch.setattr(sample_module, "SILVER_DIR", silver_dir)
    monkeypatch.setattr(sample_module, "GOLD_DIR", gold_dir)
    import fifa_analytics.reporting.fragments as frag
    import fifa_analytics.reporting.build_report as br
    monkeypatch.setattr(frag, "FRAGMENTS_DIR", fragments_dir)
    monkeypatch.setattr(frag, "TEMPLATES_DIR", paths_module.PROJECT_ROOT / "templates")
    monkeypatch.setattr(br, "FRAGMENTS_DIR", fragments_dir)
    monkeypatch.setattr(br, "FINAL_REPORTS_DIR", final_dir)
    monkeypatch.setattr(br, "MANIFESTS_DIR", manifests_dir)

    sample_module.run_sample_pipeline()

    matches = read_dataframe(silver_dir / "matches" / "matches.parquet")
    result = validate_required_columns(matches, schema="matches.yaml")
    assert result["status"] == "ok", f"Colunas faltando: {result['missing_columns']}"
