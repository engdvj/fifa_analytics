"""Snapshot analítico jogo a jogo — fonte única FIFA.

Gera dois artefatos em `data/gold/analytics/`:
  snapshot_timeline.parquet  — scores históricos empilhados (um registro por
                               seleção por snapshot; snapshot = após cada jogo)
  weights.json               — pesos fixos atuais (para o dashboard)

Um snapshot é gerado após cada jogo finalizado, na ordem cronológica do
torneio. Cada snapshot acumula todos os jogos até aquele momento — não é
incremental linha a linha, é uma recalculada completa com os dados disponíveis
até ali.

Uso:
    from fifa_analytics.analytics.snapshot import build_snapshots
    build_snapshots(wide, dim_match)
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from fifa_analytics.analytics.scores import TEAM_SCORE_WEIGHTS, build_team_scores
from fifa_analytics.paths import GOLD_DIR
from fifa_analytics.utils.io import write_dataframe
from fifa_analytics.utils.logging import get_logger

logger = get_logger(__name__)

ANALYTICS_DIR = GOLD_DIR / "analytics"
TIMELINE_PATH = ANALYTICS_DIR / "snapshot_timeline.parquet"
WEIGHTS_PATH = ANALYTICS_DIR / "weights.json"


def build_snapshots(
    wide: pd.DataFrame,
    dim_match: pd.DataFrame,
) -> pd.DataFrame:
    """Recalcula todos os snapshots do torneio e grava os artefatos.

    Retorna o snapshot_timeline completo.
    """
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

    finished = dim_match[dim_match["status"] == "finalizado"].copy()
    if finished.empty:
        logger.warning("snapshot: nenhum jogo finalizado encontrado")
        return pd.DataFrame()

    # Ordem cronológica dos jogos finalizados
    sort_col = "date_utc" if "date_utc" in finished.columns else "match_number"
    ordered = finished.sort_values(sort_col).reset_index(drop=True)

    # Referência fixa de normalização: calculada UMA vez sobre TODOS os jogos
    # finalizados e reusada em cada snapshot. Assim o score de um time só muda
    # quando o próprio time joga, não quando o campo muda (ver scores.build_team_scores).
    ref_stats: dict[str, tuple[float, float]] = {}
    all_ids = set(ordered["match_id"].tolist())
    build_team_scores(
        wide[wide["match_id"].isin(all_ids)],
        dim_match[dim_match["match_id"].isin(all_ids)],
        ref_stats=ref_stats,
    )

    frames: list[pd.DataFrame] = []
    for i, row in enumerate(ordered.itertuples(), start=1):
        match_ids_ate_agora = set(ordered.iloc[:i]["match_id"].tolist())
        wide_ate_agora = wide[wide["match_id"].isin(match_ids_ate_agora)]
        dim_ate_agora = dim_match[dim_match["match_id"].isin(match_ids_ate_agora)]

        scores = build_team_scores(wide_ate_agora, dim_ate_agora, ref_stats=ref_stats)
        if scores.empty:
            continue

        scores["snapshot_jogo"] = i
        scores["match_id_referencia"] = row.match_id
        frames.append(scores)
        logger.info("snapshot %d/%d: %s — %d seleções", i, len(ordered), row.match_id, len(scores))

    if not frames:
        logger.warning("snapshot: nenhum frame gerado")
        return pd.DataFrame()

    timeline = pd.concat(frames, ignore_index=True)
    write_dataframe(TIMELINE_PATH, timeline)
    logger.info("snapshot_timeline gravado: %d linhas", len(timeline))

    # weights.json — pesos fixos para o dashboard
    _save_weights(TEAM_SCORE_WEIGHTS)

    return timeline


def _save_weights(weights: dict[str, float]) -> None:
    payload = {
        "pesos": {k: round(v, 4) for k, v in weights.items()},
        "tipo": "fixo",
    }
    WEIGHTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("weights.json gravado: %s", WEIGHTS_PATH)
