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
    build_player_match_features,
    build_player_scores,
    build_team_match_features,
    build_team_scores,
)
from fifa_analytics.paths import GOLD_DIR
from fifa_analytics.validation.match_validation import validate_match_completeness
from fifa_analytics.transforms.standings import calculate_group_standings
from fifa_analytics.utils.io import ensure_dir, read_dataframe, write_dataframe
from fifa_analytics.utils.text import clean_person_name, person_name_exact_key
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
# Timeline de jogadores empilhada por snapshot (espelho do snapshot_timeline de
# seleções) — alimenta a aba Jogadores do dashboard com scores acumulados até
# cada jogo. Colunas-chave de jogador são fixadas para um payload enxuto.
PLAYER_TIMELINE_PATH = SNAPSHOTS_DIR / "player_snapshot_timeline.parquet"
_PLAYER_SNAP_COLS = [
    "player_slug", "player_name", "team", "perfil", "shirt_number", "jogos",
    "score_geral", "ranking_score_geral", "nivel_evidencia",
    "rating_365",  # nota de atuação média (365scores), escala ~2.9-9.8
    "goals", "assists", "participacoes_gol", "saves", "goals_conceded",
    "shots", "shots_on_target", "fouls_committed", "fouls_drawn",
    "yellow_cards", "red_cards",
    "expected_goals", "expected_assists", "expected_goals_on_target",
    "key_passes", "big_chances_created", "big_chances_missed",
    "big_chances_scored", "dribbles_won", "tackles_won",
    "interceptions", "clearances", "ball_recovery", "duels_won",
    "shots_blocked", "expected_goals_prevented", "penalties_saved",
    "high_claims", "punches",
    "gols_por_jogo", "assistencias_por_jogo", "participacoes_por_jogo",
    "chutes_no_alvo_por_jogo", "defesas_por_jogo",
    "faltas_cometidas_por_jogo", "faltas_sofridas_por_jogo",
    "expected_goals_por_jogo", "expected_assists_por_jogo",
    "expected_goals_on_target_por_jogo", "key_passes_por_jogo",
    "big_chances_created_por_jogo", "big_chances_missed_por_jogo",
    "big_chances_scored_por_jogo", "dribbles_won_por_jogo",
    "tackles_won_por_jogo", "interceptions_por_jogo",
    "clearances_por_jogo", "ball_recovery_por_jogo",
    "duels_won_por_jogo", "shots_blocked_por_jogo",
    "expected_goals_prevented_por_jogo", "penalties_saved_por_jogo",
    "high_claims_por_jogo", "punches_por_jogo",
]


def _read_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return read_dataframe(path)


def _shirt_numbers_for(scores: pd.DataFrame, lineups: pd.DataFrame, rosters: pd.DataFrame) -> list:
    """Número da camisa por (nome exato, time): moda do shirt_number nos lineups,
    com fallback no roster. Nome casado SEM dobrar acento (Ederson ≠ Éderson)."""
    num_by: dict[tuple[str, str], int] = {}
    for src in (lineups, rosters):
        if src is None or src.empty or "shirt_number" not in src.columns:
            continue
        tmp = src.dropna(subset=["player_name"]).copy()
        tmp["_k"] = tmp["player_name"].map(person_name_exact_key)
        tmp["_n"] = pd.to_numeric(tmp["shirt_number"], errors="coerce")
        tmp = tmp.dropna(subset=["_n"])
        for (nm, tm), grp in tmp.groupby(["_k", "team"]):
            key = (nm, tm)
            if key not in num_by:  # lineups têm prioridade (vêm primeiro)
                num_by[key] = int(grp["_n"].mode().iloc[0])
    return [
        num_by.get((person_name_exact_key(nm), tm)) for nm, tm in zip(scores["player_name"], scores["team"])
    ]


def _build_player_snapshot(
    player_stats: pd.DataFrame,
    lineups: pd.DataFrame,
    rosters: pd.DataFrame,
    ids_ate_agora: list[str],
    n: int,
    match_id: str,
) -> None:
    """Calcula o score de jogadores acumulado até o jogo N e empilha na
    player_snapshot_timeline. Cada linha = jogador no snapshot daquele jogo,
    com score/ranking dentro do perfil considerando só os jogos disputados até N.
    A nota de atuação média (`rating_365`) vem da coluna `rating` já casada no
    canonical_player_stats (fonte única) — aqui só fazemos a média por jogador.

    Não usa lookahead: filtra player_stats pelos match_ids até o jogo N. Se não
    há dados de jogador (fonte ausente), não escreve nada e segue."""
    if player_stats is None or player_stats.empty:
        return

    ps_ate = player_stats[player_stats["match_id"].isin(ids_ate_agora)].copy()
    if ps_ate.empty:
        return

    feats = build_player_match_features(
        ps_ate,
        lineups if lineups is not None and not lineups.empty else None,
        rosters if rosters is not None and not rosters.empty else None,
    )
    scores = build_player_scores(feats)
    if scores.empty:
        return

    scores = scores.copy()
    # Usa a média de rating calculada por build_player_scores() sobre as features
    # já normalizadas. Recalcular aqui a partir do canonical cru reabria bugs de
    # string, como "Raphinha " (com espaço final) não casar com "Raphinha".
    if "rating_medio" in scores.columns:
        scores["rating_365"] = pd.to_numeric(scores["rating_medio"], errors="coerce").round(2)
    else:
        scores["rating_365"] = pd.NA
    # quem não disputou nenhum jogo não tem nota (mesma regra do score)
    if "jogos" in scores.columns:
        scores.loc[pd.to_numeric(scores["jogos"], errors="coerce").fillna(0) <= 0, "rating_365"] = pd.NA
    # normaliza o nome (tira espaços nas pontas) — a fonte às vezes traz "Ederson "
    # com espaço, que aparece como jogador "diferente" e quebra joins por nome.
    scores["player_name"] = scores["player_name"].map(clean_person_name)

    # número da camisa por (jogador, time): moda do shirt_number nos lineups; cai
    # pro roster se faltar. Casado por nome EXATO (preserva acento) p/ não colidir
    # homônimos como Ederson/Éderson.
    scores["shirt_number"] = _shirt_numbers_for(scores, lineups, rosters)

    scores["snapshot_jogo"] = n
    scores["match_id_referencia"] = match_id
    keep = [c for c in _PLAYER_SNAP_COLS if c in scores.columns] + ["snapshot_jogo", "match_id_referencia"]
    snap = scores[keep]

    existing = _read_optional(PLAYER_TIMELINE_PATH)
    if not existing.empty:
        existing = existing[existing["snapshot_jogo"] != n]
        timeline = pd.concat([existing, snap], ignore_index=True)
    else:
        timeline = snap
    write_dataframe(PLAYER_TIMELINE_PATH, timeline)


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

    match_ids_with_features = set(all_features["match_id"].dropna())
    order_cols = [c for c in ("match_id", "temporal_order", "date", "kickoff_time") if c in matches.columns]
    order_frame = matches[matches["match_id"].isin(match_ids_with_features)][order_cols].drop_duplicates("match_id")
    sort_cols = [c for c in ("temporal_order", "date", "kickoff_time", "match_id") if c in order_frame.columns]
    chronological = order_frame.sort_values(sort_cols, na_position="last")["match_id"].tolist()

    # Regrava a ordem com a lista canônica atual. Preserva a posição de jogos que
    # continuam válidos, mas remove IDs órfãos que desapareceram das features; se
    # eles ficarem no fim, viram snapshots fantasma no dashboard.
    existing = json.loads(MATCH_ORDER_PATH.read_text()) if MATCH_ORDER_PATH.exists() else []
    valid = set(chronological)
    order = [mid for mid in existing if mid in valid]
    seen = set(order)
    order.extend(mid for mid in chronological if mid not in seen)

    ensure_dir(SNAPSHOTS_DIR)
    MATCH_ORDER_PATH.write_text(json.dumps(order), encoding="utf-8")
    return order


def _snapshot_index(path: Path, prefix: str) -> int | None:
    stem = path.stem if path.suffix != ".json" else path.name.removesuffix(".json")
    if not stem.startswith(prefix):
        return None
    try:
        return int(stem.split("_")[-1])
    except (TypeError, ValueError):
        return None


def _prune_stale_snapshot_artifacts(n_total: int) -> None:
    """Remove snapshots acima do total válido da ordem canônica atual."""
    for pattern, prefix in (("snapshot_jogo_*.parquet", "snapshot_jogo"), ("weights_jogo_*.json", "weights_jogo")):
        for path in SNAPSHOTS_DIR.glob(pattern):
            idx = _snapshot_index(path, prefix)
            if idx is not None and idx > n_total:
                path.unlink(missing_ok=True)

    for path in (SCORE_HISTORY_PATH, SNAPSHOTS_DIR / "snapshot_timeline.parquet", PLAYER_TIMELINE_PATH):
        existing = _read_optional(path)
        if existing.empty or "snapshot_jogo" not in existing.columns:
            continue
        filtered = existing[pd.to_numeric(existing["snapshot_jogo"], errors="coerce").le(n_total)].copy()
        if len(filtered) != len(existing):
            write_dataframe(path, filtered.reset_index(drop=True))


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
    _prune_stale_snapshot_artifacts(n_total)
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
    player_stats = _read_optional(GOLD_DIR / "fact_player_match_stats" / "canonical_player_stats.parquet")
    rosters = _read_optional(GOLD_DIR / "rosters" / "espn_rosters.parquet")
    all_features = build_team_match_features(matches, team_stats, events, lineups, stats_365)

    match_id = match_order[n - 1]
    ids_ate_agora = match_order[:n]
    features_n = all_features[all_features["match_id"].isin(ids_ate_agora)].copy()

    # ── PORTA DE QUALIDADE: não processa jogo com dado incompleto/inconsistente.
    # Valida o jogo N em todas as dimensões (placar, eventos, stats de time e
    # jogador, lineups, coerência entre fontes primárias) — dado quebrado aqui
    # corromperia o snapshot, a narrativa, os scores. Se houver erro, ABORTA e
    # devolve a lista, sem escrever nada.
    source_map = _read_optional(GOLD_DIR / "dim_match" / "source_match_map.parquet")
    match_row = matches[matches["canonical_match_id"] == match_id]
    if not match_row.empty:
        errors = validate_match_completeness(
            match_row.iloc[0], source_map, events, team_stats, player_stats, lineups
        )
        if errors:
            print(f"\n⚠️  Jogo {n} ({match_id}) NÃO processado — dados incompletos/inconsistentes:")
            for e in errors:
                print(f"     • {e}")
            print("     Corrija a coleta/reconciliação e rode de novo.\n")
            return {"status": "bloqueado", "n": n, "match_id": match_id, "erros": errors}

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

    # --- Snapshot de JOGADORES acumulado até o jogo N (espelha o de seleções) ---
    # Mesma janela de jogos (ids_ate_agora): scores recalculados só com o que
    # aconteceu até aqui, sem lookahead. Alimenta a aba Jogadores do dashboard.
    _build_player_snapshot(player_stats, lineups, rosters, ids_ate_agora, n, match_id)

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
