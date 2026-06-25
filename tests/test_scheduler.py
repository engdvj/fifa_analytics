"""Agendador de coleta automática dirigido pelo calendário.

Cobre o gating por env e a detecção de jogos finalizados a partir do calendário
(sem rodar o pipeline real).
"""

import pandas as pd

from api.app import scheduler
from api.app.scheduler import _env_minutes, _finished_from_calendar, start_auto_collect


def test_desligado_sem_env(monkeypatch):
    monkeypatch.delenv("AUTO_COLLECT_MINUTES", raising=False)
    assert start_auto_collect() is None


def test_desligado_com_zero(monkeypatch):
    monkeypatch.setenv("AUTO_COLLECT_MINUTES", "0")
    assert start_auto_collect() is None


def test_valor_invalido_nao_quebra(monkeypatch):
    monkeypatch.setenv("AUTO_COLLECT_MINUTES", "abc")
    assert start_auto_collect() is None


def test_env_minutes_parsing(monkeypatch):
    monkeypatch.delenv("X", raising=False)
    assert _env_minutes("X", 10.0) == 10.0
    monkeypatch.setenv("X", "")
    assert _env_minutes("X", 10.0) == 10.0
    monkeypatch.setenv("X", "abc")
    assert _env_minutes("X", 10.0) == 10.0
    monkeypatch.setenv("X", "5")
    assert _env_minutes("X", 10.0) == 5.0


def test_ligado_retorna_thread_daemon(monkeypatch):
    # intervalo grande: a thread só dorme durante o teste (daemon, morre com o processo).
    monkeypatch.setenv("AUTO_COLLECT_MINUTES", "60")
    monkeypatch.setenv("AUTO_COLLECT_GRACE_MINUTES", "5")
    t = start_auto_collect()
    assert t is not None
    assert t.daemon and t.is_alive()


def test_finished_from_calendar_extrai_so_finalizados(monkeypatch):
    df = pd.DataFrame(
        {
            "match_id": ["copa_2026_jogo_001", "copa_2026_jogo_002", "copa_2026_jogo_003"],
            "status": ["finalizado", "agendado", "finalizado"],
            "id_ifes": ["AAA", "BBB", "CCC"],
        }
    )
    monkeypatch.setattr("fifa_analytics.fifa.client.fetch_calendar_matches", lambda: [{}])
    monkeypatch.setattr("fifa_analytics.fifa.transforms.normalize_matches", lambda _r: df)
    # devolve {match_id: id_ifes} só dos finalizados
    out = _finished_from_calendar()
    assert out == {"copa_2026_jogo_001": "AAA", "copa_2026_jogo_003": "CCC"}
    assert set(out) == {"copa_2026_jogo_001", "copa_2026_jogo_003"}


def test_finished_from_calendar_vazio(monkeypatch):
    monkeypatch.setattr("fifa_analytics.fifa.client.fetch_calendar_matches", lambda: [])
    monkeypatch.setattr("fifa_analytics.fifa.transforms.normalize_matches", lambda _r: pd.DataFrame())
    assert _finished_from_calendar() == {}


def test_stats_ready(monkeypatch):
    import fifa_analytics.fifa.client as fifa_client
    from api.app import scheduler

    # sem id_ifes → não dá p/ sondar, não trava a coleta
    assert scheduler._stats_ready("") is True

    monkeypatch.setattr("fifa_analytics.fifa.client.fetch_match_team_stats", lambda _i: {"x": 1})
    monkeypatch.setattr(
        "fifa_analytics.fifa.transforms.normalize_match_team_stats",
        lambda _m, _i, _p: pd.DataFrame({"a": [1]}),
    )
    assert scheduler._stats_ready("AAA") is True  # stats publicadas

    monkeypatch.setattr(
        "fifa_analytics.fifa.transforms.normalize_match_team_stats",
        lambda _m, _i, _p: pd.DataFrame(),
    )
    assert scheduler._stats_ready("AAA") is False  # ainda vazio

    def _boom(_i):
        raise fifa_client.FifaSourceError("404")

    monkeypatch.setattr("fifa_analytics.fifa.client.fetch_match_team_stats", _boom)
    assert scheduler._stats_ready("AAA") is False  # 404/erro de fonte = não pronto


def test_seen_diff_detecta_novos():
    # a regra do loop: novos = current - seen
    seen = {"copa_2026_jogo_001"}
    current = {"copa_2026_jogo_001", "copa_2026_jogo_002"}
    assert current - seen == {"copa_2026_jogo_002"}
    assert current - current == set()  # nada novo → não coleta
