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


def _opponent_goals_map(dim_match: pd.DataFrame) -> dict[tuple[str, str], float]:
    """(match_id, nome_time) → gols sofridos por aquele time (gols do adversário)."""
    out: dict[tuple[str, str], float] = {}
    for _, m in dim_match.iterrows():
        hs, as_ = m.get("home_score"), m.get("away_score")
        if pd.isna(hs) or pd.isna(as_):
            continue
        h, a = m.get("home_team"), m.get("away_team")
        if h:
            out[(m["match_id"], h)] = float(as_)
        if a:
            out[(m["match_id"], a)] = float(hs)
    return out


def _backfill_goalkeeper_conceded(
    wide: pd.DataFrame,
    player_stats_long: pd.DataFrame,
    dim_match: pd.DataFrame,
) -> pd.DataFrame:
    """Preenche `gols_sofridos`/`jogos_sem_sofrer` do goleiro titular pelo placar
    quando a fonte fdh não trouxe GoalsConceded para aquele jogo."""
    if wide.empty or "position" not in wide.columns:
        return wide

    # (match_id, id_player) que TÊM GoalsConceded de verdade na fonte.
    has_gc: set[tuple[str, str]] = set()
    if not player_stats_long.empty:
        gc = player_stats_long[player_stats_long["metric"] == "GoalsConceded"]
        has_gc = set(zip(gc["match_id"], gc["id_player"].astype(str)))

    opp_goals = _opponent_goals_map(dim_match)
    minutos = wide["minutos"] if "minutos" in wide.columns else pd.Series(1.0, index=wide.index)
    starter = wide["is_starter"] if "is_starter" in wide.columns else pd.Series(True, index=wide.index)

    def _fill(row, idx) -> float | None:
        played = pd.to_numeric(minutos.loc[idx], errors="coerce") or 0
        if row["position"] != "G" or not bool(starter.loc[idx]) or played <= 0:
            return None
        if (row["match_id"], str(row["id_player"])) in has_gc:
            return None  # fonte trouxe — não sobrescreve
        return opp_goals.get((row["match_id"], row.get("team")))

    if "gols_sofridos" not in wide.columns:
        wide["gols_sofridos"] = 0.0
    if "jogos_sem_sofrer" not in wide.columns:
        wide["jogos_sem_sofrer"] = 0.0

    for idx, row in wide.iterrows():
        val = _fill(row, idx)
        if val is not None:
            wide.at[idx, "gols_sofridos"] = val
            wide.at[idx, "jogos_sem_sofrer"] = 1.0 if val == 0 else 0.0
    return wide


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

    # Quem não entrou em campo (minutos==0) não tem estatística. A fonte fdh às
    # vezes credita métricas de súmula a quem ficou no banco — em especial os
    # GoalsConceded/CleanSheets do time vão para TODOS os goleiros, mesmo reservas
    # que não jogaram. Isso inflava o acumulado de goleiros que revezam. Zeramos
    # tudo de quem não jogou; o backfill abaixo recompõe só o goleiro titular.
    if "minutos" in wide.columns:
        nao_jogou = pd.to_numeric(wide["minutos"], errors="coerce").fillna(0) <= 0
        stat_cols = [c for c in metric_cols if c != "minutos"]
        wide.loc[nao_jogou, stat_cols] = 0.0

    # Backfill de gols sofridos do GOLEIRO pelo placar. A fonte fdh omite
    # GoalsConceded/CleanSheets de goleiros em jogos recentes (lag do Data Hub:
    # ~38% dos jogos), o que faria o goleiro parecer sofrer menos do que sofreu.
    # Para o goleiro titular que jogou, o placar é a verdade: gols sofridos = gols
    # do adversário. Só preenchemos quando a fonte NÃO trouxe a métrica (não
    # sobrescreve dado real); o reserva que entrou fica como está (raro).
    wide = _backfill_goalkeeper_conceded(wide, player_stats_long, dim_match)

    # métricas derivadas
    wide["participacoes_gol"] = wide.get("gols", pd.Series(0, index=wide.index)).fillna(0) + wide.get("assistencias", pd.Series(0, index=wide.index)).fillna(0)

    # chave de join por nome (para casar com power ranking / roster)
    wide["player_key"] = wide["player_name"].map(person_name_key)

    return wide
