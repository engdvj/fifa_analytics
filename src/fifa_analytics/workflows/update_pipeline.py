from __future__ import annotations

from typing import Any

from fifa_analytics.workflows.basic_reports import run_basic_reports
from fifa_analytics.workflows.canonical_reports import run_canonical_index
from fifa_analytics.workflows.espn_pipeline import run_espn_pipeline
from fifa_analytics.workflows.scores365_pipeline import run_scores365_pipeline
from fifa_analytics.workflows.scores_pipeline import run_scores_pipeline
from fifa_analytics.workflows.tournament_status import run_tournament_status
from fifa_analytics.workflows.worldcup2026_pipeline import run_worldcup2026_pipeline


def run_update_pipeline(
    include_worldcup2026: bool = True,
    include_espn: bool = True,
    include_365scores: bool = True,
    status: str = "finalizado",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "modo_atualizacao": "sob_demanda",
        "status_relatorios": status,
    }

    if include_worldcup2026:
        worldcup_result = run_worldcup2026_pipeline()
        result.update(
            {
                "worldcup2026_status": "executado",
                "worldcup2026_partidas": worldcup_result.get("matches", 0),
                "worldcup2026_eventos": worldcup_result.get("events", 0),
            }
        )
    else:
        result["worldcup2026_status"] = "ignorado"

    if include_espn:
        espn_result = run_espn_pipeline()
        result.update(
            {
                "espn_status": "executado",
                "espn_partidas": espn_result.get("matches", 0),
                "espn_eventos": espn_result.get("events", 0),
                "espn_estatisticas_selecoes": espn_result.get("team_stats", 0),
                "espn_estatisticas_jogadores": espn_result.get("player_stats", 0),
            }
        )
    else:
        result["espn_status"] = "ignorado"

    if include_365scores:
        s365_result = run_scores365_pipeline()
        result.update(
            {
                "365scores_status": "executado",
                "365scores_jogos_coletados": s365_result.get("games_with_stats", 0),
                "365scores_jogadores": s365_result.get("players", 0),
            }
        )
    else:
        result["365scores_status"] = "ignorado"

    # Reconcilia as fontes (silver) no índice canônico (gold). Sem isso, o dim_match
    # nunca reflete novos placares/status — o watcher lê o gold e não veria os jogos
    # que entraram ao vivo ou finalizaram nesta coleta.
    canonical_result = run_canonical_index()
    result["partidas_canonicas_reconciliadas"] = canonical_result.get("info_partidas", 0)

    reports_result = run_basic_reports(status=status)
    status_result = run_tournament_status(source="canonical")
    scores_result = run_scores_pipeline()

    result.update(
        {
            "partidas_canonicas": reports_result.get("matches", 0),
            "partidas_processadas": reports_result.get("partidas_encontradas", 0),
            "relatorios_gerados": reports_result.get("relatorios_gerados", 0),
            "primeiro_relatorio": reports_result.get("primeiro_relatorio"),
            "caminho_status_torneio": status_result.get("status_report_path"),
            "selecoes_ranqueadas": scores_result.get("teams_ranked", 0),
            "jogadores_ranqueados": scores_result.get("players_ranked", 0),
            "caminho_rankings": scores_result.get("rankings_index_path"),
        }
    )
    return result
