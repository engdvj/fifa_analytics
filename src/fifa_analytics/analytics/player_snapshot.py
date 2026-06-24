"""Snapshot analítico de JOGADORES jogo a jogo — fonte única FIFA.

Espelha `analytics/snapshot.py` (times). Para cada snapshot (após cada jogo
finalizado, em ordem cronológica) acumula as stats de cada jogador até ali e
calcula médias por jogo. Casa nome/posição/camisa (de `fact_lineups`) e um
`score_geral` por jogador (do Power Ranking FIFA).

Saída: data/gold/analytics/snapshots/player_snapshot_timeline.parquet
       data/gold/analytics/player_match_wide.parquet  (pivot wide por jogo)

As colunas de saída usam o schema (em inglês + sufixo `_por_jogo`) que o
dashboard `scripts/bar_chart_race.py` já consome. Métricas que a FIFA não expõe
pelo lado do jogador (xA, grandes chances, cortes, bloqueios, xGP) saem como None.
"""
from __future__ import annotations

import pandas as pd

from fifa_analytics.analytics.player_scores import (
    RAW_INPUT_COLS,
    build_player_scores,
)
from fifa_analytics.fifa.player_pivot import build_player_match_wide
from fifa_analytics.paths import GOLD_DIR
from fifa_analytics.utils.io import write_dataframe
from fifa_analytics.utils.logging import get_logger

logger = get_logger(__name__)

ANALYTICS_DIR = GOLD_DIR / "analytics"
SNAPSHOTS_DIR = ANALYTICS_DIR / "snapshots"
WIDE_PATH = ANALYTICS_DIR / "player_match_wide.parquet"
TIMELINE_PATH = SNAPSHOTS_DIR / "player_snapshot_timeline.parquet"

# coluna interna (player_pivot, pt-BR) → coluna de saída esperada pelo dashboard
_OUT_RENAME = {
    "gols": "goals",
    "assistencias": "assists",
    "defesas": "saves",
    "gols_sofridos": "goals_conceded",
    "chutes": "shots",
    "chutes_no_alvo": "shots_on_target",
    "faltas_cometidas": "fouls_committed",
    "faltas_sofridas": "fouls_drawn",
    "amarelos": "yellow_cards",
    "vermelhos": "red_cards",
    "xg": "expected_goals",
    "sequencias_com_chute": "key_passes",
    "dribles_certos": "dribbles_won",
    "turnovers_forcados": "tackles_won",
    "pressoes_diretas": "interceptions",
    "pressoes_defensivas": "ball_recovery",
}

# colunas acumuláveis (soma) presentes na saída
_SUM_COLS = list(_OUT_RENAME.values()) + ["participacoes_gol"]

# (coluna acumulada → alias por jogo)
_PER_GAME = [
    ("goals", "gols_por_jogo"),
    ("assists", "assistencias_por_jogo"),
    ("participacoes_gol", "participacoes_por_jogo"),
    ("shots_on_target", "chutes_no_alvo_por_jogo"),
    ("saves", "defesas_por_jogo"),
    ("fouls_committed", "faltas_cometidas_por_jogo"),
    ("fouls_drawn", "faltas_sofridas_por_jogo"),
    ("expected_goals", "expected_goals_por_jogo"),
    ("key_passes", "key_passes_por_jogo"),
    ("dribbles_won", "dribbles_won_por_jogo"),
    ("tackles_won", "tackles_won_por_jogo"),
    ("interceptions", "interceptions_por_jogo"),
    ("ball_recovery", "ball_recovery_por_jogo"),
    ("duels_won", "duels_won_por_jogo"),
]

# colunas que o dashboard espera mas a FIFA não fornece (sem proxy) → None
_MISSING_COLS = [
    "expected_assists", "expected_goals_on_target",
    "big_chances_created", "big_chances_missed", "big_chances_scored",
    "clearances", "shots_blocked", "expected_goals_prevented",
    "penalties_saved", "high_claims", "punches",
    "expected_assists_por_jogo", "expected_goals_on_target_por_jogo",
    "big_chances_created_por_jogo", "big_chances_missed_por_jogo",
    "big_chances_scored_por_jogo", "clearances_por_jogo",
    "shots_blocked_por_jogo", "expected_goals_prevented_por_jogo",
    "penalties_saved_por_jogo", "high_claims_por_jogo", "punches_por_jogo",
]


def _player_scores(power_ranking: pd.DataFrame) -> pd.DataFrame:
    """Power Ranking FIFA → score_geral (0-100) por id_player.

    O power ranking traz attacking/defensive/creativity em escala ~0-10. Combinamos
    conforme o tipo do jogador e reescalamos para 0-100 (×10) para casar com a escala
    de score dos times no dashboard.
    """
    if power_ranking.empty:
        return pd.DataFrame(columns=["id_player", "score_geral"])
    pr = power_ranking.copy()
    pr["id_player"] = pr["id_player"].astype(str)

    def _f(v) -> float:
        # NaN é "truthy": `nan or 0` devolve nan. Goleiros têm creativity_score
        # ausente (None→NaN no parquet) — sem esta coerção todo GK vira NaN.
        return 0.0 if v is None or pd.isna(v) else float(v)

    def _score(r) -> float:
        a = _f(r.get("attacking_score"))
        d = _f(r.get("defensive_score"))
        c = _f(r.get("creativity_score"))
        if str(r.get("player_type")) == "goalkeeper":
            base = d * 0.60 + c * 0.25 + a * 0.15
        else:
            base = a * 0.40 + c * 0.35 + d * 0.25
        return round(base * 10.0, 1)

    pr["score_geral"] = pr.apply(_score, axis=1)
    return pr[["id_player", "score_geral"]].drop_duplicates("id_player")


def _accumulate_for_scores(wide_subset: pd.DataFrame) -> pd.DataFrame:
    """Acumula (soma) as colunas brutas do score próprio por jogador no conjunto
    de jogos dado, com perfil e nº de jogos efetivamente jogados (minutos>0).
    Alimenta `player_scores.build_player_scores`."""
    raw_cols = [c for c in RAW_INPUT_COLS if c in wide_subset.columns]
    acc = wide_subset.groupby("id_player")[raw_cols].sum(numeric_only=True).reset_index()
    if "minutos" in wide_subset.columns:
        played = (pd.to_numeric(wide_subset["minutos"], errors="coerce").fillna(0) > 0).astype(int)
        jogos = played.groupby(wide_subset["id_player"]).sum()
    else:
        jogos = wide_subset.groupby("id_player").size()
    acc["jogos"] = jogos.reindex(acc["id_player"]).fillna(0).astype(int).values
    if "perfil" in wide_subset.columns:
        perfil = wide_subset.dropna(subset=["perfil"]).groupby("id_player")["perfil"].last()
        acc["perfil"] = acc["id_player"].map(perfil)
    else:
        acc["perfil"] = "meio"
    return acc


def build_player_snapshots(
    player_stats_long: pd.DataFrame,
    lineups: pd.DataFrame,
    dim_match: pd.DataFrame,
    team_timeline: pd.DataFrame,
    power_ranking: pd.DataFrame,
) -> pd.DataFrame:
    """Gera o player_snapshot_timeline e grava os artefatos. Retorna a timeline."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    wide = build_player_match_wide(player_stats_long, lineups, dim_match)
    if wide.empty:
        logger.warning("player snapshot: sem stats de jogador — pulado")
        return pd.DataFrame()
    write_dataframe(WIDE_PATH, wide)

    # renomeia para o schema do dashboard
    w = wide.rename(columns={k: v for k, v in _OUT_RENAME.items() if k in wide.columns})

    # ordem cronológica dos snapshots = a mesma do snapshot de times
    if team_timeline.empty or "snapshot_jogo" not in team_timeline.columns:
        logger.warning("player snapshot: team_timeline ausente — pulado")
        return pd.DataFrame()
    snap_order = (
        team_timeline[["snapshot_jogo", "match_id_referencia"]]
        .drop_duplicates()
        .sort_values("snapshot_jogo")
    )
    cumulative: list[str] = []
    snap_mids: dict[int, list[str]] = {}
    for _, r in snap_order.iterrows():
        cumulative.append(r["match_id_referencia"])
        snap_mids[int(r["snapshot_jogo"])] = list(cumulative)

    scores = _player_scores(power_ranking)

    # Referência fixa do score próprio: média/desvio por (perfil, métrica)
    # calculados UMA vez sobre o estado final (todos os jogos) e reusados em cada
    # snapshot — assim a nota de um jogador só muda quando ELE joga.
    prop_ref: dict[tuple[str, str], tuple[float, float]] = {}
    build_player_scores(_accumulate_for_scores(wide), ref_stats=prop_ref)

    # metadados estáveis por jogador (última aparição)
    meta_cols = [c for c in ("player_name", "team", "perfil", "position", "shirt_number") if c in w.columns]
    info = (
        w.dropna(subset=["player_name"]) if "player_name" in w.columns else w
    ).groupby("id_player")[meta_cols].last().reset_index() if meta_cols else pd.DataFrame({"id_player": w["id_player"].unique()})

    frames: list[pd.DataFrame] = []
    sum_cols = [c for c in _SUM_COLS if c in w.columns]
    for n, mids in snap_mids.items():
        subset = w[w["match_id"].isin(mids)]
        if subset.empty:
            continue
        agg = subset.groupby("id_player")[sum_cols].sum(numeric_only=True).reset_index()
        # jogos = partidas EFETIVAMENTE jogadas (minutos > 0), não convocações.
        # Um jogador no banco que não entrou não deve diluir as médias por jogo.
        if "minutos" in subset.columns:
            played = (pd.to_numeric(subset["minutos"], errors="coerce").fillna(0) > 0).astype(int)
            jogos_por_player = played.groupby(subset["id_player"]).sum()
        else:
            jogos_por_player = subset.groupby("id_player").size()
        agg["jogos"] = jogos_por_player.reindex(agg["id_player"]).fillna(0).astype(int).values

        agg = agg.merge(info, on="id_player", how="left")
        agg = agg.merge(scores, on="id_player", how="left")

        # score próprio (nosso, por posição) — convive com a PR FIFA (score_geral)
        prop = build_player_scores(
            _accumulate_for_scores(wide[wide["match_id"].isin(mids)]),
            ref_stats=prop_ref,
        )
        prop_cols = ["score_proprio", "confianca_score", "nivel_confianca"] + [
            c for c in prop.columns if c.startswith("prop_")
        ]
        agg = agg.merge(prop[["id_player", *prop_cols]], on="id_player", how="left")

        # duelos ganhos = desarmes (proxy) + dribles ganhos
        tw = agg.get("tackles_won", pd.Series(0.0, index=agg.index)).fillna(0)
        dw = agg.get("dribbles_won", pd.Series(0.0, index=agg.index)).fillna(0)
        agg["duels_won"] = tw + dw

        # jogos=0 (só banco) → média por jogo indefinida (NaN, não 0).
        jogos = agg["jogos"].replace(0, float("nan"))
        for col, alias in _PER_GAME:
            if col in agg.columns:
                agg[alias] = (agg[col].fillna(0) / jogos).astype(float).round(3)

        agg["snapshot_jogo"] = n
        agg["player_slug"] = agg["id_player"].astype(str)
        agg["rating_365"] = agg.get("score_geral")
        frames.append(agg)

    if not frames:
        logger.warning("player snapshot: nenhum frame gerado")
        return pd.DataFrame()

    timeline = pd.concat(frames, ignore_index=True)

    # ranking de score_geral por snapshot
    timeline["ranking_score_geral"] = (
        timeline.groupby("snapshot_jogo")["score_geral"]
        .rank(ascending=False, method="min")
    )
    if "score_proprio" in timeline.columns:
        timeline["ranking_score_proprio"] = (
            timeline.groupby("snapshot_jogo")["score_proprio"]
            .rank(ascending=False, method="min")
        )

    for col in _MISSING_COLS:
        if col not in timeline.columns:
            timeline[col] = None

    # só jogadores com nome e time (presentes em lineups)
    if "player_name" in timeline.columns and "team" in timeline.columns:
        timeline = timeline[timeline["player_name"].notna() & timeline["team"].notna()]

    write_dataframe(TIMELINE_PATH, timeline)
    logger.info(
        "player_snapshot_timeline gravado: %d linhas, %d jogadores",
        len(timeline), timeline["id_player"].nunique(),
    )
    return timeline
