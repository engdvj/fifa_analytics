"""Pivot long → wide das métricas de jogador FIFA (fdh) por jogo.

Espelha `fifa/pivot.py` (que faz o mesmo para times). Lê o `fact_player_match_stats`
(formato long: match_id, id_ifes, id_player, metric, value) e produz uma linha por
(match_id, id_player) com as métricas de interesse em colunas snake_case, já com
nome/posição/camisa/equipe vindos de `fact_lineups`.

A FIFA não expõe pelo lado do jogador algumas métricas das fontes antigas (xA,
grandes chances, cortes, bloqueios, xGP). Onde não há equivalente direto usamos
proxies declarados em METRICS_MAP; o que não tem proxy simplesmente não existe.
"""
from __future__ import annotations

import pandas as pd

from fifa_analytics.utils.text import clean_person_name, person_name_key


def _display_name(value: object) -> object:
    """Normaliza para exibição: a FIFA grava o sobrenome em CAIXA ALTA
    ("Erling HAALAND"). Reduz tokens totalmente maiúsculos a Title Case,
    preservando tokens já bem formatados ("Kristian Thorstvedt")."""
    name = clean_person_name(value)
    if not isinstance(name, str) or not name:
        return name
    out = []
    for tok in name.split(" "):
        if len(tok) > 1 and tok.isupper():
            out.append(tok.capitalize())
        else:
            out.append(tok)
    return " ".join(out)

# Métrica fdh (jogador) → coluna interna snake_case.
METRICS_MAP: dict[str, str] = {
    "MatchesPlayed":                    "jogos_fonte",
    "TimePlayed":                       "minutos",
    "Goals":                            "gols",
    "Assists":                          "assistencias",
    "OwnGoals":                         "gols_contra",
    "XG":                               "xg",
    "Threat":                           "threat",
    "AttemptAtGoal":                    "chutes",
    "AttemptAtGoalOnTarget":            "chutes_no_alvo",
    "AttemptAtGoalBlocked":             "chutes_bloqueados",
    "Passes":                           "passes",
    "PassesCompleted":                  "passes_certos",
    "NumberOfShotEndingSequences":      "sequencias_com_chute",  # proxy de passes-chave
    "CompletedBallProgressions":        "progressoes",
    "TakeOnsCompleted":                 "dribles_certos",
    "Crosses":                          "cruzamentos",
    "CrossesCompleted":                 "cruzamentos_certos",
    "Corners":                          "escanteios",
    "Offsides":                         "impedimentos",
    # defesa / sem-bola
    "ForcedTurnovers":                  "turnovers_forcados",
    "DefensivePressuresApplied":        "pressoes_defensivas",
    "DirectDefensivePressuresApplied":  "pressoes_diretas",
    "GoalkeeperSaves":                  "defesas",
    "GoalkeeperSavesOnTarget":          "defesas_no_alvo",
    "GoalkeeperSavePercentage":         "save_pct",
    "GoalsConceded":                    "gols_sofridos",
    "CleanSheets":                      "jogos_sem_sofrer",
    # disciplina
    "FoulsAgainst":                     "faltas_cometidas",
    "FoulsFor":                         "faltas_sofridas",
    "YellowCards":                      "amarelos",
    "RedCards":                         "vermelhos",
    # físico
    "TotalDistance":                    "distancia_total",
    "Sprints":                          "sprints",
    "SpeedRuns":                        "corridas_velocidade",
    "TopSpeed":                         "velocidade_maxima",
    "NumberOfInvolvements":             "envolvimentos",
}

# Posição FIFA (1 letra) → grupo de perfil usado no dashboard.
POS_TO_PERFIL = {"G": "goleiro", "D": "defensor", "M": "meio", "F": "atacante"}


def _team_name_map(dim_match: pd.DataFrame) -> dict[str, str]:
    """id_team → nome pt-BR via dim_match (home/away)."""
    out: dict[str, str] = {}
    for _, r in dim_match.iterrows():
        h, a = r.get("id_team_home"), r.get("id_team_away")
        if pd.notna(h) and r.get("home_team"):
            out[str(h)] = r["home_team"]
        if pd.notna(a) and r.get("away_team"):
            out[str(a)] = r["away_team"]
    return out


def build_player_match_wide(
    player_stats_long: pd.DataFrame,
    lineups: pd.DataFrame,
    dim_match: pd.DataFrame,
) -> pd.DataFrame:
    """Pivota as stats long de jogador para wide (uma linha por match_id+id_player).

    O universo de jogadores é ANCORADO em `fact_lineups` (o elenco que entrou em
    campo/banco em cada jogo): cada jogador escalado vira uma linha, com as stats
    do fdh juntadas via LEFT JOIN (quem não acumulou métrica fica com 0). Assim o
    roster (escalações) e os snapshots cobrem exatamente os mesmos jogadores.
    """
    if lineups.empty:
        return pd.DataFrame()

    # 1. pivot das stats (long → wide por match_id+id_player)
    stats_wide = pd.DataFrame()
    if not player_stats_long.empty:
        df = player_stats_long.copy()
        df["id_player"] = df["id_player"].astype(str)
        keep = df[df["metric"].isin(METRICS_MAP)]
        if not keep.empty:
            stats_wide = (
                keep.pivot_table(
                    index=["match_id", "id_player"],
                    columns="metric",
                    values="value",
                    aggfunc="sum",
                )
                .reset_index()
                .rename(columns=METRICS_MAP)
            )
            stats_wide.columns.name = None

    # 2. base = escalações (uma linha por jogador escalado por jogo)
    team_map = _team_name_map(dim_match)
    ln = lineups.copy()
    ln["id_player"] = ln["id_player"].astype(str)
    ln["id_team"] = ln["id_team"].astype(str)
    ln["team"] = ln["id_team"].map(team_map)
    ln["perfil"] = ln["position"].map(POS_TO_PERFIL)
    ln["player_name"] = ln["player_name"].map(_display_name)
    base = ln[[
        "match_id", "id_player", "player_name", "team", "perfil",
        "position", "shirt_number", "is_starter",
    ]].drop_duplicates(subset=["match_id", "id_player"])

    # 3. LEFT JOIN das stats; métricas ausentes (não jogou/sem dado) → 0
    wide = base.merge(stats_wide, on=["match_id", "id_player"], how="left") if not stats_wide.empty else base.copy()
    metric_cols = [c for c in METRICS_MAP.values() if c in wide.columns]
    for c in metric_cols:
        wide[c] = pd.to_numeric(wide[c], errors="coerce").fillna(0)

    # métricas derivadas
    wide["participacoes_gol"] = wide.get("gols", pd.Series(0, index=wide.index)).fillna(0) + wide.get("assistencias", pd.Series(0, index=wide.index)).fillna(0)

    # chave de join por nome (para casar com power ranking / roster)
    wide["player_key"] = wide["player_name"].map(person_name_key)

    return wide
