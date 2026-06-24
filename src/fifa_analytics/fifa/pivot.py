"""Pivot das métricas fdh: long -> wide por (match_id, team).

O `fact_team_match_stats.parquet` armazena 145 métricas em formato long
(uma linha por métrica). Este módulo pivota para wide — uma linha por
(match_id, team) com cada métrica como coluna — e resolve o nome do time
via join com dim_match.

Saída: `data/gold/analytics/team_match_wide.parquet`
"""
from __future__ import annotations

import pandas as pd

# Métricas que nos interessam para analytics e dashboard.
# Renomeadas para snake_case interno; as demais são descartadas do wide
# (ainda existem no long para consulta direta).
METRICS_MAP: dict[str, str] = {
    # Resultado
    "Goals":                                    "gols",
    "GoalsConceded":                            "gols_sofridos",
    "OwnGoals":                                 "gols_contra",
    # Ataque / Chutes
    "XG":                                       "xg",
    "Threat":                                   "threat",
    "AttemptAtGoal":                            "chutes",
    "AttemptAtGoalOnTarget":                    "chutes_no_alvo",
    "AttemptAtGoalOffTarget":                   "chutes_fora",
    "AttemptAtGoalBlocked":                     "chutes_bloqueados",
    "AttemptAtGoalInsideThePenaltyArea":        "chutes_dentro_area",
    "AttemptAtGoalOutsideThePenaltyArea":       "chutes_fora_area",
    "AttemptAtGoalFromCorner":                  "chutes_de_escanteio",
    "AttemptAtGoalFromFreeKicks":               "chutes_de_falta",
    "AttemptAtGoalFromPenalty":                 "chutes_de_penalti",
    "HeadedAttemptAtGoal":                      "chutes_de_cabeca",
    # Contra (sofridos)
    "AttemptAtGoalAgainst":                     "chutes_sofridos",
    "AttemptAtGoalAgainstOnTarget":             "chutes_sofridos_no_alvo",
    # Goleiro
    "GoalkeeperSaves":                          "defesas_goleiro",
    "GoalkeeperSavesOnTarget":                  "defesas_goleiro_no_alvo",
    "GoalkeeperSavePercentage":                 "save_pct_goleiro",
    "GoalkeeperDefensiveActionsInsidePenaltyArea":  "acoes_gk_dentro_area",
    "GoalkeeperDefensiveActionsOutsidePenaltyArea": "acoes_gk_fora_area",
    # Posse / Controle territorial
    "Possession":                               "posse",          # decimal 0-1
    "PitchControl":                             "pitch_control",  # %
    "FinalThirdPitchControl":                   "final_third_control",
    # Passe / Progressão
    "Passes":                                   "passes",
    "PassesCompleted":                          "passes_certos",
    "Crosses":                                  "cruzamentos",
    "CrossesCompleted":                         "cruzamentos_certos",
    "CompletedBallProgressions":                "progressoes_bola",
    "AttemptedBallProgressions":                "progressoes_tentadas",
    "CompletedSwitchesOfPlay":                  "trocas_lado_certas",
    "AttemptedSwitchesOfPlay":                  "trocas_lado_tentadas",
    # Linebreaks (quebras de linha de pressão)
    "LinebreaksAttemptedCompleted":             "linebreaks",
    "LinebreaksAttemptedAllLines":              "linebreaks_tentados",
    # Pressão / Turnover
    "ForcedTurnovers":                          "turnovers_forcados",
    "DefensivePressuresApplied":                "pressoes_defensivas",
    "DirectDefensivePressuresApplied":          "pressoes_diretas",
    "DistributionsUnderPressure":               "distribuicoes_sob_pressao",
    "DistributionsCompletedUnderPressure":      "distribuicoes_certas_sob_pressao",
    # Entradas no terço final
    "FinalThirdEntriesReceptionCentralChannel": "entradas_3o_central",
    "FinalThirdEntriesReceptionLeftChannel":    "entradas_3o_esq",
    "FinalThirdEntriesReceptionRightChannel":   "entradas_3o_dir",
    # Físico
    "TotalDistance":                            "distancia_total",   # metros
    "Sprints":                                  "sprints",
    "SpeedRuns":                                "corridas_alta_vel",
    "AvgSpeed":                                 "velocidade_media",
    "TopSpeed":                                 "velocidade_maxima",
    "DistanceHighSpeedRunning":                 "distancia_alta_vel",
    "DistanceHighSpeedSprinting":               "distancia_sprint",
    "DistanceJogging":                          "distancia_trote",
    "DistanceWalking":                          "distancia_caminhada",
    # Disciplina
    "FoulsFor":                                 "faltas_sofridas",
    "FoulsAgainst":                             "faltas_cometidas",
    "YellowCards":                              "amarelos",
    "RedCards":                                 "vermelhos",
    "DirectRedCards":                           "vermelhos_diretos",
    "Offsides":                                 "impedimentos",
    "Corners":                                  "escanteios",
    "Penalties":                                "penaltis",
    "PenaltiesScored":                          "penaltis_marcados",
    # Fases de jogo (Phase*)
    "PhaseAggregateAttackingTransition":        "fase_transicao_ofensiva",
    "PhaseAggregateBuildUpOpposed":             "fase_construcao_pressionada",
    "PhaseAggregateBuildUpUnopposed":           "fase_construcao_livre",
    "PhaseAggregateCounterattack":              "fase_contra_ataque",
    "PhaseAggregateCounterPress":               "fase_contra_pressao",
    "PhaseAggregateDefensiveTransition":        "fase_transicao_defensiva",
    "PhaseAggregateFinalThird":                 "fase_terceiro_final",
    "PhaseAggregateHighBlock":                  "fase_bloco_alto",
    "PhaseAggregateHighPress":                  "fase_pressao_alta",
    "PhaseAggregateLongBall":                   "fase_bola_longa",
    "PhaseAggregateLowBlock":                   "fase_bloco_baixo",
    "PhaseAggregateLowPress":                   "fase_pressao_baixa",
    "PhaseAggregateMidBlock":                   "fase_bloco_medio",
    "PhaseAggregateMidPress":                   "fase_pressao_media",
    "PhaseAggregateProgression":                "fase_progressao",
    "PhaseAggregateRecovery":                   "fase_recuperacao",
    "PhaseAggregateSetPieces":                  "fase_bola_parada",
    # Outros
    "BallRecoveryTime":                         "tempo_recuperacao_bola",
    "TakeOnsCompleted":                         "dribles_certos",
    "CleanSheets":                              "jogos_sem_sofrer_gol",
    "GoalsFromDirectFreeKicks":                 "gols_de_falta",
    "GoalsInsideThePenaltyArea":                "gols_dentro_area",
    "GoalsOutsideThePenaltyArea":               "gols_fora_area",
}


def build_team_match_wide(
    team_stats_long: pd.DataFrame,
    dim_match: pd.DataFrame,
) -> pd.DataFrame:
    """Pivot do long (match_id, id_team, metric, value) para wide.

    Resolve `team` (nome pt-BR) via join com dim_match usando id_team_home /
    id_team_away. Retorna uma linha por (match_id, team) com as colunas
    definidas em METRICS_MAP.
    """
    if team_stats_long.empty:
        return pd.DataFrame()

    wanted = team_stats_long[team_stats_long["metric"].isin(METRICS_MAP)]
    wide = (
        wanted
        .pivot_table(
            index=["match_id", "id_team"],
            columns="metric",
            values="value",
            aggfunc="first",
        )
        .reset_index()
    )
    wide = wide.rename(columns=METRICS_MAP)

    # Resolve nome do time via dim_match
    home = dim_match[["match_id", "id_team_home", "home_team",
                       "date_utc", "stage", "group"]].rename(
        columns={"id_team_home": "id_team", "home_team": "team"}
    )
    away = dim_match[["match_id", "id_team_away", "away_team",
                       "date_utc", "stage", "group"]].rename(
        columns={"id_team_away": "id_team", "away_team": "team"}
    )
    team_map = pd.concat([home, away], ignore_index=True)
    team_map["id_team"] = team_map["id_team"].astype(str)
    wide["id_team"] = wide["id_team"].astype(str)

    wide = wide.merge(team_map, on=["match_id", "id_team"], how="left")

    # Métricas derivadas (calculadas aqui, não no fdh)
    wide["precisao_passes"] = _safe_divide(wide.get("passes_certos"), wide.get("passes"))
    wide["precisao_cruzamentos"] = _safe_divide(wide.get("cruzamentos_certos"), wide.get("cruzamentos"))
    wide["precisao_progressoes"] = _safe_divide(
        wide.get("progressoes_bola"), wide.get("progressoes_tentadas")
    )
    wide["precisao_linebreaks"] = _safe_divide(
        wide.get("linebreaks"), wide.get("linebreaks_tentados")
    )
    wide["conversao_chutes"] = _safe_divide(wide.get("gols"), wide.get("chutes"))
    wide["precisao_chutes"] = _safe_divide(wide.get("chutes_no_alvo"), wide.get("chutes"))
    wide["gols_por_xg"] = _safe_divide(wide.get("gols"), wide.get("xg"))
    # distância em km (fdh entrega em metros)
    if "distancia_total" in wide.columns:
        wide["distancia_total_km"] = (wide["distancia_total"] / 1000).round(2)

    col_order = ["match_id", "id_team", "team", "date_utc", "stage", "group"]
    metric_cols = [c for c in wide.columns if c not in col_order]
    return wide[col_order + metric_cols].sort_values(["date_utc", "match_id", "team"]).reset_index(drop=True)


def _safe_divide(num: pd.Series | None, den: pd.Series | None) -> pd.Series:
    if num is None or den is None:
        return pd.Series(dtype=float)
    return num.where(den.fillna(0) > 0, other=float("nan")) / den.where(den.fillna(0) > 0, other=1)
