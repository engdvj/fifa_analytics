import argparse

from fifa_analytics.config import load_config
from fifa_analytics.workflows.sample_pipeline import run_sample_pipeline
from fifa_analytics.workflows.basic_reports import run_basic_reports
from fifa_analytics.workflows.canonical_reports import rebuild_match_report, run_canonical_index
from fifa_analytics.workflows.espn_pipeline import run_espn_pipeline, run_espn_rosters_pipeline
from fifa_analytics.workflows.scores365_pipeline import run_scores365_pipeline
from fifa_analytics.workflows.scores_pipeline import run_calibration_report, run_scores_pipeline
from fifa_analytics.workflows.snapshot_pipeline import run_snapshot_jogo
from fifa_analytics.workflows.tournament_status import run_tournament_status
from fifa_analytics.workflows.update_pipeline import run_update_pipeline
from fifa_analytics.workflows.wiki_pipeline import run_wikipedia_pipeline
from fifa_analytics.workflows.worldcup2026_pipeline import run_worldcup2026_pipeline


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

    sample = subparsers.add_parser("amostra", aliases=["sample"], help="Executa a pipeline local de amostra.")
    sample.add_argument(
        "--match-id",
        default="mexico_africa_do_sul_2026_06_11",
        help="match_id de amostra a processar.",
    )

    wiki = subparsers.add_parser("wikipedia", aliases=["wiki"], help="Executa a pipeline inicial com dados da Wikipedia.")
    wiki.add_argument(
        "--match-id",
        default=None,
        help="match_id derivado da Wikipedia a processar. Por padrao usa o primeiro jogo finalizado.",
    )

    worldcup2026 = subparsers.add_parser(
        "worldcup2026",
        aliases=["operacional"],
        help="Executa a pipeline operacional com a API publica worldcup26.ir.",
    )
    worldcup2026.add_argument(
        "--match-id",
        default=None,
        help="match_id derivado da fonte worldcup2026 a processar. Por padrao usa o primeiro jogo finalizado.",
    )

    subparsers.add_parser(
        "espn",
        help="Executa a coleta de enriquecimento da ESPN com estatisticas, eventos, lineups e jogadores.",
    )

    subparsers.add_parser(
        "espn-elencos",
        help="Coleta o elenco completo (convocacao) de cada selecao na ESPN, com posicao estavel. Roda separado por ser raro mudar durante o torneio.",
    )

    subparsers.add_parser(
        "365scores",
        help="Coleta estatisticas detalhadas por jogador e por selecao na 365Scores (segunda fonte de validacao).",
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

    canonical_index = subparsers.add_parser(
        "indice-canonico",
        help="Reconcilia partidas entre fontes e cria o indice canonico de jogos.",
    )

    rebuild_report = subparsers.add_parser(
        "remontar-relatorio",
        help="Remonta o relatorio final de um jogo a partir dos fragmentos atuais, sem recalcular nada.",
    )
    rebuild_report.add_argument(
        "match_id",
        help="match_id canonico do jogo (ex: copa_2026_jogo_010).",
    )

    subparsers.add_parser(
        "scores",
        help="Gera features, scores e relatorios acumulados por selecao e jogador.",
    )

    subparsers.add_parser(
        "verificar-nomes",
        help="Lista inconsistencias de nome de jogador entre stats e roster (provavel truncamento) para curar em config/player_aliases.yaml.",
    )

    calibrar_pesos = subparsers.add_parser(
        "calibrar-pesos",
        help="Valida cada componente do score contra sua metrica natural e sugere pesos via regressao (RidgeCV). Nao altera os pesos automaticamente.",
    )
    calibrar_pesos.add_argument(
        "--forcar",
        action="store_true",
        help="Gera novo snapshot mesmo sem 2+ jogos novos desde o ultimo.",
    )

    snap = subparsers.add_parser(
        "reprocessar-snapshots",
        help="Processa o próximo jogo (ou --jogo N) e exibe o ranking naquele momento.",
    )
    snap.add_argument(
        "--jogo",
        type=int,
        default=None,
        metavar="N",
        help="Número do jogo a processar. Se omitido, processa o próximo ainda não processado.",
    )

    update = subparsers.add_parser(
        "atualizar",
        aliases=["refresh", "update"],
        help="Atualiza fontes, indice canonico, relatorios, status do torneio e scores.",
    )
    update.add_argument(
        "--sem-worldcup2026",
        action="store_true",
        help="Nao coleta a fonte worldcup2026 nesta rodada.",
    )
    update.add_argument(
        "--sem-espn",
        action="store_true",
        help="Nao coleta a ESPN nesta rodada.",
    )
    update.add_argument(
        "--sem-365scores",
        action="store_true",
        help="Nao coleta a 365Scores nesta rodada (varredura de IDs e mais lenta).",
    )
    update.add_argument(
        "--status",
        default=default_status,
        help=f"Status das partidas a gerar nos relatorios. Padrao: {default_status}.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "fifa-coletar":
        from fifa_analytics.fifa import pipeline as fifa_pipeline

        result = fifa_pipeline.run(only_finished=not args.todos)
        _print_result(result)
    elif args.command in {"amostra", "sample"}:
        result = run_sample_pipeline(match_id=args.match_id)
        _print_result(result)
    elif args.command in {"wikipedia", "wiki"}:
        result = run_wikipedia_pipeline(match_id=args.match_id)
        _print_result(result)
    elif args.command in {"worldcup2026", "operacional"}:
        result = run_worldcup2026_pipeline(match_id=args.match_id)
        _print_result(result)
    elif args.command == "espn":
        result = run_espn_pipeline()
        _print_result(result)
    elif args.command == "espn-elencos":
        result = run_espn_rosters_pipeline()
        _print_result(result)
    elif args.command == "365scores":
        result = run_scores365_pipeline()
        _print_result(result)
    elif args.command in {"status-torneio", "tournament-status"}:
        result = run_tournament_status(source=args.source)
        _print_result(result)
    elif args.command == "relatorios-basicos":
        result = run_basic_reports(source=args.fonte, status=args.status)
        _print_result(result)
    elif args.command == "indice-canonico":
        result = run_canonical_index()
        _print_result(result)
    elif args.command == "remontar-relatorio":
        result = rebuild_match_report(args.match_id)
        _print_result(result)
    elif args.command == "scores":
        result = run_scores_pipeline()
        _print_result(result)
    elif args.command == "verificar-nomes":
        _print_name_mismatches()
    elif args.command == "calibrar-pesos":
        result = run_calibration_report(force=args.forcar)
        if result["status"] == "pulado":
            print(f"Calibracao pulada: {result['motivo']}")
        else:
            print(f"Relatorio salvo em: {result['calibration_report_path']}")
            print(f"Snapshot: {result['snapshot_path']}")
            print(f"Status calibracao geral: {result['weight_calibration'].get('status')}")
    elif args.command == "reprocessar-snapshots":
        result = run_snapshot_jogo(n=args.jogo)
        if result.get("proximo"):
            print(f"Próximo: fifa-analytics reprocessar-snapshots --jogo {result['proximo']}")
        # Exit code não-zero quando o jogo NÃO foi processado (porta de qualidade
        # recusou ou erro) — senão o watcher/scripts acham que deu certo (o bug
        # "snapshot ok" sem snapshot criado, que fazia o jogo reaparecer mudo).
        if result.get("status") in {"bloqueado", "erro"}:
            raise SystemExit(1)
    elif args.command in {"atualizar", "refresh", "update"}:
        result = run_update_pipeline(
            include_worldcup2026=not args.sem_worldcup2026,
            include_espn=not args.sem_espn,
            include_365scores=not args.sem_365scores,
            status=args.status,
        )
        _print_result(result)


def _print_result(result: dict) -> None:
    for key, value in result.items():
        print(f"{LABELS.get(key, key)}: {value}")


def _print_name_mismatches() -> None:
    """Recalcula e imprime as inconsistencias de nome stats x roster do gold atual."""
    from fifa_analytics.analytics.name_reconciliation import (
        apply_player_aliases,
        detect_name_mismatches,
    )
    from fifa_analytics.paths import GOLD_DIR
    from fifa_analytics.utils.io import read_dataframe

    ps_path = GOLD_DIR / "fact_player_match_stats" / "canonical_player_stats.parquet"
    ro_path = GOLD_DIR / "rosters" / "espn_rosters.parquet"
    if not ps_path.exists() or not ro_path.exists():
        print("Sem dados de jogador/roster no gold ainda. Rode 'indice-canonico' antes.")
        return
    player_stats = apply_player_aliases(read_dataframe(ps_path))
    report = detect_name_mismatches(player_stats, read_dataframe(ro_path), persist=False)
    if report.empty:
        print("Nenhuma inconsistencia de nome pendente. (Casos curados ficam em config/player_aliases.yaml.)")
        return
    print(f"{len(report)} inconsistencia(s) de nome a curar em config/player_aliases.yaml:\n")
    for _, r in report.iterrows():
        print(f"  {r['team']}: stats='{r['stats_name']}'  ~  roster='{r['roster_name']}'")
