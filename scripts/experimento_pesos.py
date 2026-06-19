#!/usr/bin/env python3
"""Experimento: compara 3 estratégias de calibração de pesos do score_geral,
reconstruindo a série completa de snapshots (jogo 1→N) de forma ISOLADA (não
toca os artefatos de produção). Mede 3 critérios objetivos por variante.

Variantes:
  A) 6-soltos        — regressão recalibra os 6 pesos (sem fixar nada). É o
                       comportamento que dava resultado=4%/controle=37%.
  B) 2fixos+4soltos  — Resultado/Força fixos (35/15), 4 de processo calibrados
                       com teto (cap). Configuração NOVA recomendada.
  C) antiga          — sem cap nos de processo; preditivo solto quando ativa
                       (≈ A nos jogos com histórico, processo-sem-cap antes).

Critérios:
  1. Correlação score_geral → desempenho real acumulado (pontos+saldo+xG).
  2. Sanidade do ranking (top/bottom no último snapshot + checagem de anomalia).
  3. Estabilidade jogo a jogo (oscilação média dos pesos e do ranking).

Uso: python scripts/experimento_pesos.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fifa_analytics.analytics.calibration import (  # noqa: E402
    MAX_PROCESS_WEIGHT,
    _cap_and_redistribute,
    calibrate_full_weights_predictive,
    calibrate_team_score_weights,
)
from fifa_analytics.analytics.scores import TEAM_SCORE_WEIGHTS, build_team_scores  # noqa: E402
from fifa_analytics.utils.io import read_dataframe  # noqa: E402

GOLD = ROOT / "data" / "gold"
FIXOS = ("score_resultado", "score_forca_relativa")
PROC = ["score_ataque", "score_defesa", "score_eficiencia", "score_controle"]
ALL6 = ["score_resultado", *PROC, "score_forca_relativa"]


def _match_order() -> list[str]:
    import json
    return json.loads((GOLD / "analytics" / "snapshots" / "match_order.json").read_text())


def _apply(base, cal, variant):
    """Calcula os pesos efetivos conforme a variante."""
    if cal.get("status") != "ok":
        return dict(base)
    sug = cal.get("pesos_sugeridos", {})

    if variant == "A_6soltos":
        # 6 pesos da regressão, normalizados — sem fixar nada (precisa do preditivo)
        if cal.get("modo") == "preditivo_6_pesos":
            total = sum(sug.get(c, 0.0) for c in base) or 1.0
            return {c: sug.get(c, 0.0) / total for c in base}
        # processo não estima resultado/força → cai no base p/ esses
        out = dict(base)
        s = sum(sug.get(c, 0.0) for c in PROC) or 1.0
        rem = 1.0 - sum(base[c] for c in FIXOS)
        for c in PROC:
            out[c] = rem * sug.get(c, 0.0) / s
        return out

    if variant == "C_antiga":
        # preditivo solto (6) quando ativa; senão processo SEM cap
        if cal.get("modo") == "preditivo_6_pesos":
            total = sum(sug.get(c, 0.0) for c in base) or 1.0
            return {c: sug.get(c, 0.0) / total for c in base}
        out = dict(base)
        s = sum(sug.get(c, 0.0) for c in PROC) or 1.0
        rem = 1.0 - sum(base[c] for c in FIXOS)
        for c in PROC:
            out[c] = rem * sug.get(c, 0.0) / s   # SEM cap
        return out

    # B_nova: fixos preservados + processo com cap (vale p/ ambos os modos)
    out = dict(base)
    rem = 1.0 - sum(base[c] for c in FIXOS)
    comp = [c for c in PROC if c in sug]
    s = sum(sug[c] for c in comp) or 1.0
    raw = {c: rem * sug[c] / s for c in comp}
    capped = _cap_and_redistribute(raw, MAX_PROCESS_WEIGHT)
    for c in comp:
        out[c] = capped[c]
    return out


def run_variant(variant: str, all_features: pd.DataFrame, order: list[str]):
    """Reconstrói snapshots 1→N para uma variante. Retorna (scores_por_jogo, pesos_por_jogo)."""
    history = []          # acumula score_history por snapshot (p/ o preditivo)
    weights_log = []
    scores_log = []
    for n, mid in enumerate(order, 1):
        ids = order[:n]
        feats = all_features[all_features["match_id"].isin(ids)].copy()
        if feats.empty:
            continue
        # history: 1 linha por (team, jogos) — mantém a última gravada (mais recente)
        hist_df = pd.DataFrame(history) if history else pd.DataFrame()
        if not hist_df.empty:
            hist_df = hist_df.drop_duplicates(["team", "jogos"], keep="last")

        # escolhe a calibração como o pipeline faz
        if variant in ("A_6soltos", "C_antiga") and not hist_df.empty:
            cal = calibrate_full_weights_predictive(feats, hist_df)
            if cal.get("status") != "ok":
                cal = calibrate_team_score_weights(feats)
        else:
            cal = calibrate_team_score_weights(feats)

        w = _apply(TEAM_SCORE_WEIGHTS, cal, variant)
        sc = build_team_scores(feats, weights=w)
        sc["snapshot_jogo"] = n
        scores_log.append(sc)
        weights_log.append({"snapshot_jogo": n, **w})

        # history p/ o próximo preditivo: 1 linha por time COM O Nº REAL DE JOGOS
        # daquele time até agora (não o índice global do snapshot). O preditivo
        # exige 'jogos' por time p/ formar os pares (N-1→N) — sem isso nunca ativa.
        jogos_por_time = feats.groupby("team")["match_id"].nunique()
        for _, r in sc.iterrows():
            jt = int(jogos_por_time.get(r["team"], 0))
            if jt <= 0:
                continue
            # remove entrada antiga desse time nesse nível e regrava (idempotente)
            history.append({"team": r["team"], "jogos": jt, **{c: r.get(c) for c in ALL6}})

    return pd.concat(scores_log, ignore_index=True), pd.DataFrame(weights_log)


def metric_correlation(scores_all: pd.DataFrame, feats: pd.DataFrame) -> float:
    """Correlação do score_geral final com desempenho real acumulado (pontos+saldo+xG z)."""
    last = scores_all["snapshot_jogo"].max()
    final = scores_all[scores_all["snapshot_jogo"] == last]
    agg = feats.groupby("team").agg(
        points=("points", "sum"),
        gd=("goals_for", "sum"),
        ga=("goals_against", "sum"),
    ).reset_index()
    agg["gd"] = agg["gd"] - agg["ga"]
    if "team_xg" in feats.columns:
        xg = feats.groupby("team").agg(xgf=("team_xg", "sum"), xga=("xg_against", "sum")).reset_index()
        agg = agg.merge(xg, on="team", how="left")
        agg["xgd"] = agg["xgf"].fillna(0) - agg["xga"].fillna(0)
    else:
        agg["xgd"] = 0.0
    z = lambda s: (s - s.mean()) / (s.std(ddof=0) or 1)
    agg["real"] = 0.6 * z(agg["points"]) + 0.2 * z(agg["gd"]) + 0.2 * z(agg["xgd"])
    m = final.merge(agg, on="team")
    return float(m["score_geral"].corr(m["real"]))


def metric_weight_stability(weights_df: pd.DataFrame) -> float:
    """Oscilação média (desvio absoluto entre snapshots consecutivos) dos pesos de processo."""
    diffs = weights_df[PROC].diff().abs().iloc[1:]
    return float(diffs.mean().mean())


def metric_rank_stability(scores_all: pd.DataFrame) -> float:
    """Oscilação média de posição no ranking geral entre snapshots consecutivos."""
    moves = []
    snaps = sorted(scores_all["snapshot_jogo"].unique())
    prev = None
    for s in snaps:
        cur = scores_all[scores_all["snapshot_jogo"] == s].copy()
        cur["rank"] = cur["score_geral"].rank(ascending=False, method="min")
        rk = cur.set_index("team")["rank"]
        if prev is not None:
            common = rk.index.intersection(prev.index)
            moves.append((rk[common] - prev[common]).abs().mean())
        prev = rk
    return float(np.mean(moves)) if moves else 0.0


def main():
    all_features = read_dataframe(GOLD / "analytics" / "team_match_features.parquet")
    order = _match_order()
    variants = ["A_6soltos", "B_nova", "C_antiga"]
    results = {}
    series = {}
    for v in variants:
        scores_all, weights_df = run_variant(v, all_features, order)
        results[v] = {
            "corr_real": metric_correlation(scores_all, all_features),
            "estab_pesos": metric_weight_stability(weights_df),
            "estab_rank": metric_rank_stability(scores_all),
        }
        series[v] = (scores_all, weights_df)

    print("\n" + "=" * 78)
    print(f"{'Variante':<18}{'Corr→real':>12}{'Oscil.pesos':>14}{'Oscil.rank':>13}")
    print("-" * 78)
    for v in variants:
        r = results[v]
        print(f"{v:<18}{r['corr_real']:>12.3f}{r['estab_pesos']:>14.4f}{r['estab_rank']:>13.3f}")
    print("=" * 78)
    print("Corr→real: MAIOR = melhor (nota reflete desempenho). Oscilações: MENOR = melhor (menos ruído).\n")

    # pesos finais + top/bottom de cada variante p/ sanidade
    for v in variants:
        scores_all, weights_df = series[v]
        wlast = weights_df.iloc[-1]
        sc = scores_all[scores_all["snapshot_jogo"] == scores_all["snapshot_jogo"].max()].sort_values("score_geral", ascending=False)
        print(f"--- {v} | pesos finais: " + " ".join(f"{c.replace('score_','')[:4]}={wlast[c]*100:.0f}%" for c in ALL6))
        top = ", ".join(f"{r.team}({r.score_geral:.0f})" for r in sc.head(4).itertuples())
        bot = ", ".join(f"{r.team}({r.score_geral:.0f})" for r in sc.tail(3).itertuples())
        print(f"    TOP: {top}")
        print(f"    BOTTOM: {bot}")
        # anomalia Argélia×Curaçao
        for t in ("Argélia", "Curaçao"):
            row = sc[sc["team"] == t]
            if not row.empty:
                print(f"    {t}: score={row.iloc[0]['score_geral']:.1f}")
        print()


if __name__ == "__main__":
    main()
