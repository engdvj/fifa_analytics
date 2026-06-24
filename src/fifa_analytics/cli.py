import argparse

from fifa_analytics.config import load_config
from fifa_analytics.workflows.basic_reports import run_basic_reports
from fifa_analytics.workflows.fifa_reports import rebuild_match_report
from fifa_analytics.workflows.tournament_status import run_tournament_status


LABELS = {
    "source": "fonte",
    "match_id": "match_id",
    "raw_dir": "diretorio_bruto",
    "matches_path": "caminho_partidas",
    "source_map_path": "caminho_mapa_fontes",
    "events_path": "caminho_eventos",
    "metadata_path": "caminho_metadados",
    "teams_path": "caminho_selecoes",
    "stadiums_path": "caminho_estadios",
    "standings_path": "caminho_classificacao",
    "external_standings_path": "caminho_classificacao_externa",
    "calculated_standings_path": "caminho_classificacao_calculada",
    "gold_events_path": "caminho_eventos_gold",
    "team_stats_path": "caminho_estatisticas_selecoes",
    "lineups_path": "caminho_escalacoes",
    "player_stats_path": "caminho_estatisticas_jogadores",
    "match_info_path": "caminho_info_partidas",
    "commentary_path": "caminho_narracao",
    "shots_path": "caminho_chutes",
    "team_match_features_path": "caminho_features_selecoes_por_jogo",
    "team_scores_path": "caminho_scores_selecoes",
    "player_match_features_path": "caminho_features_jogadores_por_jogo",
    "player_scores_path": "caminho_scores_jogadores",
    "team_reports_dir": "diretorio_relatorios_selecoes",
    "player_reports_dir": "diretorio_relatorios_jogadores",
    "team_index_path": "caminho_indice_selecoes",
    "player_index_path": "caminho_indice_jogadores",
    "rankings_index_path": "caminho_indice_rankings",
    "team_ranking_path": "caminho_ranking_selecoes",
    "player_ranking_path": "caminho_ranking_jogadores",
    "team_rankings": "rankings_selecoes",
    "player_rankings": "rankings_jogadores",
    "modo_atualizacao": "modo_atualizacao",
    "status_relatorios": "status_relatorios",
    "worldcup2026_status": "status_worldcup2026",
    "worldcup2026_partidas": "partidas_worldcup2026",
    "worldcup2026_eventos": "eventos_worldcup2026",
    "espn_status": "status_espn",
    "espn_partidas": "partidas_espn",
    "espn_eventos": "eventos_espn",
    "espn_estatisticas_selecoes": "estatisticas_selecoes_espn",
    "espn_estatisticas_jogadores": "estatisticas_jogadores_espn",
    "365scores_status": "status_365scores",
    "365scores_jogos_coletados": "jogos_coletados_365scores",
    "365scores_jogadores": "jogadores_365scores",
    "game_ids_scanned": "ids_varridos",
    "games_with_stats": "jogos_com_estatisticas",
    "teams": "selecoes",
    "players": "jogadores",
    "team_stat_rows": "linhas_estatisticas_selecoes",
    "player_stat_rows": "linhas_estatisticas_jogadores",
    "team_silver": "caminho_estatisticas_selecoes_silver",
    "player_silver": "caminho_estatisticas_jogadores_silver",
    "team_gold": "caminho_estatisticas_selecoes_gold_365",
    "player_gold": "caminho_estatisticas_jogadores_gold_365",
    "partidas_canonicas": "partidas_canonicas",
    "partidas_processadas": "partidas_processadas",
    "caminho_status_torneio": "caminho_status_torneio",
    "caminho_rankings": "caminho_rankings",
    "gold_team_stats_path": "caminho_estatisticas_selecoes_gold",
    "gold_lineups_path": "caminho_escalacoes_gold",
    "gold_player_stats_path": "caminho_estatisticas_jogadores_gold",
    "gold_match_info_path": "caminho_info_partidas_gold",
    "gold_commentary_path": "caminho_narracao_gold",
    "gold_shots_path": "caminho_chutes_gold",
    "gold_standings_path": "caminho_classificacao_gold",
    "validation_path": "caminho_validacao",
    "status_path": "caminho_status",
    "status_report_path": "caminho_relatorio_status",
    "standings_report_path": "caminho_relatorio_classificacao",
    "missing_report_path": "caminho_relatorio_pendencias",
    "report_path": "caminho_relatorio",
    "manifest_path": "caminho_manifesto",
    "report_status": "status_relatorio",
    "matches": "partidas",
    "source_links": "vinculos_fontes",
    "events": "eventos",
    "team_stats": "estatisticas_selecoes",
    "lineups": "escalacoes",
    "player_stats": "estatisticas_jogadores",
    "match_info": "info_partidas",
    "commentary": "narracao",
    "shots": "chutes",
    "relatorios_completos": "relatorios_completos",
    "relatorios_parciais": "relatorios_parciais",
    "relatorios_nao_iniciados": "relatorios_nao_iniciados",
    "status_processado": "status_processado",
    "partidas_encontradas": "partidas_encontradas",
    "relatorios_gerados": "relatorios_gerados",
    "primeiro_relatorio": "primeiro_relatorio",
    "teams_ranked": "selecoes_ranqueadas",
    "players_ranked": "jogadores_ranqueados",
    "team_reports": "relatorios_selecoes",
    "player_reports": "relatorios_jogadores",
}


def _pipeline_defaults() -> dict:
    try:
        return load_config("pipeline.yaml").get("defaults", {})
    except Exception:
        return {}


def build_parser() -> argparse.ArgumentParser:
    defaults = _pipeline_defaults()
    default_source = defaults.get("source", "canonical")
    default_status = defaults.get("match_status_filter", "finalizado")

    parser = argparse.ArgumentParser(prog="fifa_analytics")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fifa_coletar = subparsers.add_parser(
        "fifa-coletar",
        help="Coleta a fonte oficial FIFA (v3 + fdh) e grava o gold (parquet).",
    )
    fifa_coletar.add_argument(
        "--todos",
        action="store_true",
        help="Tenta stats de todos os jogos com IdIFES, não só os finalizados.",
    )

    tournament_status = subparsers.add_parser(
        "status-torneio",
        aliases=["tournament-status"],
        help="Gera o status do torneio e relatorios agregados.",
    )
    tournament_status.add_argument(
        "--source",
        default=default_source,
        help=f"Fonte de dados a usar. Padrao: {default_source}.",
    )

    basic_reports = subparsers.add_parser(
        "relatorios-basicos",
        help="Gera relatorios basicos em lote a partir dos dados ja coletados.",
    )
    basic_reports.add_argument(
        "--fonte",
        default=default_source,
        help=f"Fonte de dados a usar. Para relatorios finais, use canonical. Padrao: {default_source}.",
    )
    basic_reports.add_argument(
        "--status",
        default=default_status,
        help=f"Status das partidas a processar. Use 'todos' para processar todas. Padrao: {default_status}.",
    )

    rebuild_report = subparsers.add_parser(
        "remontar-relatorio",
        help="Remonta o relatorio final de um jogo a partir dos fragmentos atuais, sem recalcular nada.",
    )
    rebuild_report.add_argument(
        "match_id",
        help="match_id canonico do jogo (ex: copa_2026_jogo_010).",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "fifa-coletar":
        from fifa_analytics.fifa import pipeline as fifa_pipeline

        result = fifa_pipeline.run(only_finished=not args.todos)
        _print_result(result)
    elif args.command in {"status-torneio", "tournament-status"}:
        result = run_tournament_status(source=args.source)
        _print_result(result)
    elif args.command == "relatorios-basicos":
        result = run_basic_reports(source=args.fonte, status=args.status)
        _print_result(result)
    elif args.command == "remontar-relatorio":
        result = rebuild_match_report(args.match_id)
        _print_result(result)


def _print_result(result: dict) -> None:
    for key, value in result.items():
        print(f"{LABELS.get(key, key)}: {value}")
