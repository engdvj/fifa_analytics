import fifa_analytics.workflows.update_pipeline as update_module


def test_run_update_pipeline_orchestrates_full_refresh(monkeypatch):
    calls = []

    def fake_worldcup2026():
        calls.append("worldcup2026")
        return {"matches": 104, "events": 12}

    def fake_espn():
        calls.append("espn")
        return {"matches": 104, "events": 40, "team_stats": 64, "player_stats": 900}

    def fake_reports(status):
        calls.append(f"reports:{status}")
        return {"matches": 104, "partidas_encontradas": 24, "relatorios_gerados": 24, "primeiro_relatorio": "reports/final/jogo.md"}

    def fake_status(source):
        calls.append(f"status:{source}")
        return {"status_report_path": "reports/tournament/status.md"}

    def fake_scores():
        calls.append("scores")
        return {"teams_ranked": 32, "players_ranked": 900, "rankings_index_path": "reports/rankings/index.md"}

    def fake_scores365():
        calls.append("365scores")
        return {"games_with_stats": 16, "players": 374}

    monkeypatch.setattr(update_module, "run_worldcup2026_pipeline", fake_worldcup2026)
    monkeypatch.setattr(update_module, "run_espn_pipeline", fake_espn)
    monkeypatch.setattr(update_module, "run_basic_reports", fake_reports)
    monkeypatch.setattr(update_module, "run_tournament_status", fake_status)
    monkeypatch.setattr(update_module, "run_scores_pipeline", fake_scores)
    monkeypatch.setattr(update_module, "run_scores365_pipeline", fake_scores365)

    result = update_module.run_update_pipeline(status="finalizado")

    assert calls == ["worldcup2026", "espn", "365scores", "reports:finalizado", "status:canonical", "scores"]
    assert result["worldcup2026_status"] == "executado"
    assert result["espn_status"] == "executado"
    assert result["365scores_status"] == "executado"
    assert result["partidas_processadas"] == 24
    assert result["selecoes_ranqueadas"] == 32


def test_run_update_pipeline_can_skip_sources(monkeypatch):
    calls = []

    monkeypatch.setattr(update_module, "run_worldcup2026_pipeline", lambda: calls.append("worldcup2026"))
    monkeypatch.setattr(update_module, "run_espn_pipeline", lambda: calls.append("espn"))
    monkeypatch.setattr(update_module, "run_basic_reports", lambda status: calls.append(f"reports:{status}") or {})
    monkeypatch.setattr(update_module, "run_tournament_status", lambda source: calls.append(f"status:{source}") or {})
    monkeypatch.setattr(update_module, "run_scores_pipeline", lambda: calls.append("scores") or {})
    monkeypatch.setattr(update_module, "run_scores365_pipeline", lambda: calls.append("365scores") or {})

    result = update_module.run_update_pipeline(
        include_worldcup2026=False, include_espn=False, include_365scores=False, status="todos"
    )

    assert calls == ["reports:todos", "status:canonical", "scores"]
    assert result["worldcup2026_status"] == "ignorado"
    assert result["espn_status"] == "ignorado"
    assert result["365scores_status"] == "ignorado"
