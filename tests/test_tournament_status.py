import pandas as pd

import fifa_analytics.workflows.tournament_status as tournament_status_module
from fifa_analytics.reporting.tournament_reports import build_missing_reports, build_status_summary


def test_build_tournament_status_marks_partial_report(tmp_path, monkeypatch):
    fragments_dir = tmp_path / "fragments"
    final_reports_dir = tmp_path / "final"
    manifests_dir = tmp_path / "manifests"
    match_id = "mexico_africa_do_sul_2026_match_1"

    match_fragments = fragments_dir / match_id
    match_fragments.mkdir(parents=True)
    final_reports_dir.mkdir(parents=True)
    manifests_dir.mkdir(parents=True)

    (match_fragments / "00_metadata.md").write_text("metadata", encoding="utf-8")
    (match_fragments / "01_match_summary.md").write_text("summary", encoding="utf-8")
    (final_reports_dir / f"{match_id}.md").write_text("report", encoding="utf-8")

    monkeypatch.setattr(tournament_status_module, "FRAGMENTS_DIR", fragments_dir)
    monkeypatch.setattr(tournament_status_module, "FINAL_REPORTS_DIR", final_reports_dir)
    monkeypatch.setattr(tournament_status_module, "MANIFESTS_DIR", manifests_dir)

    matches = pd.DataFrame(
        [
            {
                "match_id": match_id,
                "date": None,
                "home_team": "México",
                "away_team": "África do Sul",
                "stage": "fase_de_grupos",
                "group": "A",
                "status": "finalizado",
            }
        ]
    )

    status = tournament_status_module.build_tournament_status(matches)
    row = status.iloc[0]

    assert row["report_status"] == "parcial"
    assert bool(row["has_summary"]) is True
    assert "03_lineups" in row["missing_sections"]


def test_build_tournament_status_finds_nested_final_report_from_manifest(tmp_path, monkeypatch):
    fragments_dir = tmp_path / "fragments"
    final_reports_dir = tmp_path / "final"
    manifests_dir = tmp_path / "manifests"
    match_id = "copa_2026_jogo_001"
    nested_report = final_reports_dir / "fase_de_grupos" / "rodada_1" / "001_mexico_x_africa_do_sul.md"

    (fragments_dir / match_id).mkdir(parents=True)
    manifests_dir.mkdir(parents=True)
    nested_report.parent.mkdir(parents=True)
    nested_report.write_text("report", encoding="utf-8")
    for fragment_id in tournament_status_module.EXPECTED_FRAGMENT_IDS:
        (fragments_dir / match_id / f"{fragment_id}.md").write_text(fragment_id, encoding="utf-8")
    (manifests_dir / f"{match_id}.yaml").write_text(
        f"missing_sections: []\nfinal_report_path: {nested_report}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tournament_status_module, "FRAGMENTS_DIR", fragments_dir)
    monkeypatch.setattr(tournament_status_module, "FINAL_REPORTS_DIR", final_reports_dir)
    monkeypatch.setattr(tournament_status_module, "MANIFESTS_DIR", manifests_dir)

    status = tournament_status_module.build_tournament_status(
        pd.DataFrame([{"match_id": match_id, "status": "finalizado"}])
    )
    row = status.iloc[0]

    assert row["report_status"] == "completo"
    assert row["final_report_path"] == str(nested_report)


def test_tournament_reports_summarize_status_and_missing_sections():
    status = pd.DataFrame(
        [
            {
                "match_id": "match_1",
                "home_team": "México",
                "away_team": "África do Sul",
                "status": "finalizado",
                "report_status": "parcial",
                "data_quality_status": "aviso",
                "missing_sections": ["03_lineups"],
            }
        ]
    )

    summary = build_status_summary(status)
    missing = build_missing_reports(status)

    assert "Status do torneio" in summary
    assert "parcial" in summary
    assert "match_1" in missing
    assert "03_lineups" in missing
