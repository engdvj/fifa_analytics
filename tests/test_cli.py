import pytest

from fifa_analytics.cli import build_parser


def test_parser_requires_subcommand():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_fifa_coletar_default():
    parser = build_parser()
    args = parser.parse_args(["fifa-coletar"])
    assert args.command == "fifa-coletar"
    assert args.todos is False


def test_parser_fifa_coletar_todos():
    parser = build_parser()
    args = parser.parse_args(["fifa-coletar", "--todos"])
    assert args.todos is True


def test_parser_relatorios_basicos_defaults():
    parser = build_parser()
    args = parser.parse_args(["relatorios-basicos"])
    assert args.fonte == "fifa"
    assert args.status == "finalizado"


def test_parser_uses_pipeline_yaml_defaults(monkeypatch):
    import fifa_analytics.cli as cli

    monkeypatch.setattr(
        cli,
        "load_config",
        lambda _name: {"defaults": {"source": "fifa", "match_status_filter": "todos"}},
    )

    parser = cli.build_parser()
    reports = parser.parse_args(["relatorios-basicos"])
    status = parser.parse_args(["status-torneio"])

    assert reports.fonte == "fifa"
    assert reports.status == "todos"
    assert status.source == "fifa"


def test_parser_relatorios_basicos_custom_status():
    parser = build_parser()
    args = parser.parse_args(["relatorios-basicos", "--status", "todos"])
    assert args.status == "todos"


def test_parser_status_torneio_default_source():
    parser = build_parser()
    args = parser.parse_args(["status-torneio"])
    assert args.source == "fifa"


def test_parser_status_torneio_alias():
    parser = build_parser()
    args = parser.parse_args(["tournament-status"])
    assert args.command == "tournament-status"


def test_parser_remontar_relatorio_requires_match_id():
    parser = build_parser()
    args = parser.parse_args(["remontar-relatorio", "copa_2026_jogo_010"])
    assert args.match_id == "copa_2026_jogo_010"


def test_parser_rejects_legacy_commands():
    parser = build_parser()
    for legacy in ("wikipedia", "worldcup2026", "espn", "365scores", "atualizar", "indice-canonico", "amostra"):
        with pytest.raises(SystemExit):
            parser.parse_args([legacy])
