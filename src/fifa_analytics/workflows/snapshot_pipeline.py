from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from fifa_analytics.analytics.calibration import (
    apply_calibrated_weights,
    calibrate_full_weights_predictive,
    calibrate_team_score_weights,
)
from fifa_analytics.analytics.scores import (
    TEAM_SCORE_WEIGHTS,
    build_team_match_features,
    build_team_scores,
)
from fifa_analytics.paths import GOLD_DIR
from fifa_analytics.transforms.standings import calculate_group_standings
from fifa_analytics.utils.io import ensure_dir, read_dataframe, write_dataframe
from fifa_analytics.utils.time import utc_now_iso
from fifa_analytics.workflows.scores_pipeline import (
    _ranking_trend,
    _record_team_score_history,
    write_rankings_index,
    write_team_index,
    write_team_rankings,
)


ANALYTICS_DIR = GOLD_DIR / "analytics"
SNAPSHOTS_DIR = ANALYTICS_DIR / "snapshots"
SCORE_HISTORY_PATH = SNAPSHOTS_DIR / "score_history_acum.parquet"
MATCH_ORDER_PATH = SNAPSHOTS_DIR / "match_order.json"


def _read_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return read_dataframe(path)


def _load_match_order() -> list[str]:
    """Carrega a ordem canônica de jogos, em ordem cronológica.

    Persiste a ordem para que as posições dos jogos já processados não mudem,
    mas ESTENDE a lista com jogos finalizados novos (anexados ao fim, na ordem
    cronológica). Sem isso, um jogo recém-finalizado nunca entraria na ordem e
    o pipeline o ignoraria — bug que já apareceu algumas vezes.
    """
    matches = _read_optional(GOLD_DIR / "dim_match" / "canonical_matches.parquet")
    if matches.empty:
        if MATCH_ORDER_PATH.exists():
            return json.loads(MATCH_ORDER_PATH.read_text())
        raise FileNotFoundError("Índice canônico ausente. Rode `fifa-analytics indice-canonico` primeiro.")

    team_stats = _read_optional(GOLD_DIR / "fact_team_match_stats" / "canonical_team_stats.parquet")
    events = _read_optional(GOLD_DIR / "fact_events" / "canonical_events.parquet")
    lineups = _read_optional(GOLD_DIR / "lineups" / "canonical_lineups.parquet")
    stats_365 = _read_optional(GOLD_DIR / "fact_team_match_stats" / "365scores_enrichment.parquet")
    all_features = build_team_match_features(matches, team_stats, events, lineups, stats_365)

    sort_cols = [c for c in ("date", "kickoff_time") if c in all_features.columns] or ["date"]
    chronological = (
        all_features[["match_id"] + [c for c in sort_cols if c in all_features.columns]]
        .drop_duplicates("match_id")
        .sort_values(sort_cols)["match_id"].tolist()
    )

    # preserva a ordem já persistida; anexa jogos novos ao fim (na ordem cronológica)
    existing = json.loads(MATCH_ORDER_PATH.read_text()) if MATCH_ORDER_PATH.exists() else []
    seen = set(existing)
    order = existing + [mid for mid in chronological if mid not in seen]

    ensure_dir(SNAPSHOTS_DIR)
    MATCH_ORDER_PATH.write_text(json.dumps(order), encoding="utf-8")
    return order


def _last_processed_jogo() -> int:
    """Retorna o número do último jogo já processado (0 se nenhum)."""
    snapshots = sorted(SNAPSHOTS_DIR.glob("snapshot_jogo_*.parquet"))
    if not snapshots:
        return 0
    return int(snapshots[-1].stem.split("_")[-1])


def _print_ranking(scores: pd.DataFrame, match_id: str, n: int, n_total: int,
                   weights: dict, cal: dict, all_features: pd.DataFrame) -> None:
    teams_in_match = all_features[all_features["match_id"] == match_id]["team"].tolist()
    cal_modo = cal.get("modo", "processo_4_pesos")
    r2 = cal.get("r2")

    print(f"\n{'='*60}")
    print(f"  Jogo {n}/{n_total} — {match_id}")
    print(f"  Times: {' x '.join(teams_in_match)}")
    print(f"  Calibração: {cal_modo} | R²: {r2 if r2 is not None else '—'}")
    print(f"  Pesos: resultado={weights['score_resultado']:.0%} ataque={weights['score_ataque']:.0%} "
          f"defesa={weights['score_defesa']:.0%} efic={weights['score_eficiencia']:.0%} "
          f"controle={weights['score_controle']:.0%} forca={weights['score_forca_relativa']:.0%}")
    print(f"{'='*60}")

    ranking = scores.sort_values("ranking_snapshot")[
        ["ranking_snapshot", "team", "score_geral",
         "score_resultado", "score_ataque", "score_defesa",
         "score_eficiencia", "score_forca_relativa", "jogos"]
    ].rename(columns={
        "ranking_snapshot": "pos", "score_geral": "geral",
        "score_resultado": "result", "score_ataque": "atq",
        "score_defesa": "def", "score_eficiencia": "efic",
        "score_forca_relativa": "forca", "jogos": "J",
    })

    # Destaca os times que jogaram nesse jogo
    for _, row in ranking.iterrows():
        marker = " ◄" if row["team"] in teams_in_match else ""
        print(
            f"  {int(row['pos']):>2}. {row['team']:<25} {row['geral']:>5.1f}"
            f"  (res={row['result']:.0f} atq={row['atq']:.0f} def={row['def']:.0f}"
            f" efic={row['efic']:.0f} forca={row['forca']:.0f})  J={int(row['J'])}{marker}"
        )
    print()


def run_snapshot_jogo(n: int | None = None) -> dict[str, Any]:
    """Processa o jogo N (ou o próximo ainda não processado) e exibe o ranking.

    Lê o estado acumulado do disco (histórico de scores, ordem de jogos) para
    não recalcular os jogos anteriores — cada chamada é incremental.

    Passa --jogo N para processar um jogo específico (útil para reprocessar
    um jogo anterior sem perder o histórico dos seguintes).
    """
    ensure_dir(SNAPSHOTS_DIR)
    match_order = _load_match_order()
    n_total = len(match_order)
    last = _last_processed_jogo()

    if n is None:
        n = last + 1

    if n > n_total:
        print(f"Todos os {n_total} jogos já foram processados.")
        return {"status": "completo", "n_jogos": n_total}

    if n < 1:
        print("Número de jogo inválido. Use --jogo N com N >= 1.")
        return {"status": "erro"}

    # Carrega dados brutos completos (leve — só lê parquet, não recalcula)
    matches = _read_optional(GOLD_DIR / "dim_match" / "canonical_matches.parquet")
    team_stats = _read_optional(GOLD_DIR / "fact_team_match_stats" / "canonical_team_stats.parquet")
    events = _read_optional(GOLD_DIR / "fact_events" / "canonical_events.parquet")
    lineups = _read_optional(GOLD_DIR / "lineups" / "canonical_lineups.parquet")
    stats_365 = _read_optional(GOLD_DIR / "fact_team_match_stats" / "365scores_enrichment.parquet")
    all_features = build_team_match_features(matches, team_stats, events, lineups, stats_365)

    match_id = match_order[n - 1]
    ids_ate_agora = match_order[:n]
    features_n = all_features[all_features["match_id"].isin(ids_ate_agora)].copy()

    # Histórico acumulado até o jogo anterior (persistido no disco)
    score_history_acum = _read_optional(SCORE_HISTORY_PATH)
    # Filtra só snapshots até N-1 para não usar lookahead
    if not score_history_acum.empty and "snapshot_jogo" in score_history_acum.columns:
        score_history_acum = score_history_acum[score_history_acum["snapshot_jogo"] < n]

    # Calibração: preditiva se houver histórico suficiente, processo caso contrário
    if not score_history_acum.empty:
        cal = calibrate_full_weights_predictive(features_n, score_history_acum)
        if cal.get("status") != "ok":
            cal = calibrate_team_score_weights(features_n)
    else:
        cal = calibrate_team_score_weights(features_n)

    weights = apply_calibrated_weights(TEAM_SCORE_WEIGHTS, cal)
    cal_modo = cal.get("modo", "processo_4_pesos")

    scores_n = build_team_scores(features_n, weights=weights)
    scores_n["snapshot_jogo"] = n
    scores_n["match_id_referencia"] = match_id
    scores_n["cal_modo"] = cal_modo
    scores_n["cal_r2"] = cal.get("r2")
    scores_n["cal_alpha_hibrido"] = cal.get("alpha_hibrido")
    scores_n["snapshot_at"] = utc_now_iso()
    scores_n["ranking_snapshot"] = (
        scores_n["score_geral"].rank(ascending=False, method="min").astype(int)
    )

    # Persiste snapshot e pesos deste jogo
    write_dataframe(SNAPSHOTS_DIR / f"snapshot_jogo_{n:03d}.parquet", scores_n)
    (SNAPSHOTS_DIR / f"weights_jogo_{n:03d}.json").write_text(
        json.dumps({"jogo": n, "match_id": match_id, "modo": cal_modo,
                    "r2": cal.get("r2"), "alpha_hibrido": cal.get("alpha_hibrido"),
                    "pesos": weights}, default=float),
        encoding="utf-8",
    )

    # Atualiza histórico acumulado para os próximos jogos
    hist_snap = scores_n[["team", "score_geral", "score_resultado", "score_ataque",
                           "score_defesa", "score_eficiencia", "score_controle",
                           "score_forca_relativa", "jogos", "snapshot_jogo"]].copy()
    if not score_history_acum.empty:
        combined = pd.concat([score_history_acum, hist_snap], ignore_index=True)
        combined = combined.drop_duplicates(subset=["team", "snapshot_jogo"], keep="last")
    else:
        combined = hist_snap
    write_dataframe(SCORE_HISTORY_PATH, combined)

    # Atualiza timeline empilhada
    timeline_path = SNAPSHOTS_DIR / "snapshot_timeline.parquet"
    existing = _read_optional(timeline_path)
    if not existing.empty:
        existing = existing[existing["snapshot_jogo"] != n]
        timeline = pd.concat([existing, scores_n], ignore_index=True)
    else:
        timeline = scores_n
    write_dataframe(timeline_path, timeline)

    # Atualiza os parquets que o scores_pipeline usa (para rankings funcionarem)
    write_dataframe(ANALYTICS_DIR / "team_match_features.parquet", features_n)
    write_dataframe(ANALYTICS_DIR / "team_scores.parquet", scores_n)

    # Regenera rankings e relatórios de seleções com o estado deste jogo
    team_score_history = _record_team_score_history(scores_n)
    scores_for_rankings = scores_n.copy()
    scores_for_rankings["tendencia_ranking"] = _ranking_trend(scores_n, team_score_history)
    write_team_rankings(scores_for_rankings, weights)
    write_team_index(scores_n)
    write_rankings_index()

    _print_ranking(scores_n, match_id, n, n_total, weights, cal, all_features)

    return {
        "status": "ok",
        "jogo": n,
        "match_id": match_id,
        "proximo": n + 1 if n < n_total else None,
    }
