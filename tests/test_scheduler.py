"""Agendador de coleta automática: gating por env (sem rodar o pipeline)."""

from api.app.scheduler import start_auto_collect


def test_desligado_sem_env(monkeypatch):
    monkeypatch.delenv("AUTO_COLLECT_MINUTES", raising=False)
    assert start_auto_collect() is None


def test_desligado_com_zero(monkeypatch):
    monkeypatch.setenv("AUTO_COLLECT_MINUTES", "0")
    assert start_auto_collect() is None


def test_valor_invalido_nao_quebra(monkeypatch):
    monkeypatch.setenv("AUTO_COLLECT_MINUTES", "abc")
    assert start_auto_collect() is None
