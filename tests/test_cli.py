import pytest

from fifa_analytics.cli import build_parser


def test_parser_requires_subcommand():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_amostra_default_match_id():
    parser = build_parser()
    args = parser.parse_args(["amostra"])
    assert args.match_id == "mexico_africa_do_sul_2026_06_11"


def test_parser_amostra_custom_match_id():
    parser = build_parser()
    args = parser.parse_args(["amostra", "--match-id", "copa_2026_jogo_001"])
    assert args.match_id == "copa_2026_jogo_001"


def test_parser_relatorios_basicos_defaults():
    parser = build_parser()
    args = parser.parse_args(["relatorios-basicos"])
    assert args.fonte == "canonical"
    assert args.status == "finalizado"


def test_parser_relatorios_basicos_custom_status():
    parser = build_parser()
    args = parser.parse_args(["relatorios-basicos", "--status", "todos"])
    assert args.status == "todos"


def test_parser_status_torneio_default_source():
    parser = build_parser()
    args = parser.parse_args(["status-torneio"])
    assert args.source == "canonical"


def test_parser_atualizar_flags():
    parser = build_parser()
    args = parser.parse_args(["atualizar", "--sem-worldcup2026", "--sem-espn"])
    assert args.sem_worldcup2026 is True
    assert args.sem_espn is True


def test_parser_atualizar_default_status():
    parser = build_parser()
    args = parser.parse_args(["atualizar"])
    assert args.status == "finalizado"


def test_parser_wikipedia_alias():
    parser = build_parser()
    args = parser.parse_args(["wiki"])
    assert args.command == "wiki"
    assert args.match_id is None


def test_parser_worldcup2026_alias():
    parser = build_parser()
    args = parser.parse_args(["operacional"])
    assert args.command == "operacional"
