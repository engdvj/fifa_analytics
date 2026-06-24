import pytest

import fifa_analytics.workflows.basic_reports as basic_reports_module


def test_run_basic_reports_rejects_unknown_source():
    with pytest.raises(ValueError, match="não suportada"):
        basic_reports_module.run_basic_reports(source="wikipedia", status="finalizado")


def test_run_basic_reports_delegates_to_fifa_reports(monkeypatch):
    called = {}

    def fake_run_fifa_reports(status):
        called["status"] = status
        return {"fonte": "fifa", "status_processado": status}

    monkeypatch.setattr(basic_reports_module, "run_fifa_reports", fake_run_fifa_reports)

    result = basic_reports_module.run_basic_reports(status="finalizado")

    assert result == {"fonte": "fifa", "status_processado": "finalizado"}
    assert called["status"] == "finalizado"
