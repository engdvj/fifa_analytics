"""Análise Exploratória — que padrões existem.

Sai do descrever (totais/líderes) e do explicar-um-jogo (diagnóstica) para achar
RELAÇÕES e PADRÕES que atravessam todos os jogos da fase. Cumulativo até
`snapshot` (cresce conforme o torneio avança). Quatro leituras:

  1. decisao      — o que decide os jogos: correlação de cada métrica (diferencial
                    time − adversário) com o saldo de gols. O que importa pra vencer.
  2. estilos      — mapa de estilos: cada seleção nos eixos posse × verticalidade
                    (+ pressão), colorida pelo arquétipo (estilo_jogo).
  3. eficiencia   — paisagem xG × gols por jogo: acima da diagonal rende acima do
                    esperado (clínico/sorte), abaixo desperdiça.
  4. correlacoes  — quais métricas andam juntas (redundância) ou se opõem.

Tudo a partir do gold: team_match_wide (métricas por jogo), dim_match (resultado),
snapshot_timeline (eixos de estilo e médias acumuladas).

Uso:
    from fifa_analytics.analytics.exploratory import build_exploratory
    data = build_exploratory(dim_match, wide, timeline, snapshot=60)
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# Métricas candidatas (presentes no team_match_wide) e rótulos pt-BR.
METRIC_LABELS: dict[str, str] = {
    "xg": "xG (perigo criado)",
    "threat": "Ameaça",
    "chutes_no_alvo": "Chutes no alvo",
    "chutes_dentro_area": "Chutes na área",
    "final_third_control": "Controle (terço final)",
    "posse": "Posse de bola",
    "precisao_passes": "Precisão de passe",
    "progressoes_bola": "Progressões de bola",
    "linebreaks": "Quebras de linha",
    "turnovers_forcados": "Roubadas de bola",
    "pressoes_defensivas": "Pressões defensivas",
    "escanteios": "Escanteios",
    "faltas_cometidas": "Faltas",
    "distancia_total_km": "Distância (km)",
    "sprints": "Sprints",
}
_MIN_GAMES = 6  # amostra mínima para uma correlação valer


def _num(v: Any) -> float:
    try:
        f = float(v)
        return float("nan") if np.isnan(f) else f
    except (TypeError, ValueError):
        return float("nan")


def _team_games(dim_match: pd.DataFrame, wide: pd.DataFrame, snapshot: int | None) -> pd.DataFrame:
    """Uma linha por time por jogo, com métricas próprias, do adversário e o diff."""
    finished = dim_match[dim_match["status"] == "finalizado"].copy()
    sort_col = "date_utc" if "date_utc" in finished.columns else "match_number"
    finished = finished.sort_values(sort_col)
    if snapshot is not None:
        finished = finished.head(snapshot)
    if finished.empty or wide.empty:
        return pd.DataFrame()

    metrics = [m for m in METRIC_LABELS if m in wide.columns]
    w = wide.set_index(["match_id", "team"])

    def row(mid: str, team: str) -> dict[str, float]:
        try:
            r = w.loc[(mid, str(team))]
        except KeyError:
            return {}
        return {m: _num(r[m]) for m in metrics}

    out: list[dict[str, Any]] = []
    for m in finished.itertuples():
        hs, as_ = _num(m.home_score), _num(m.away_score)
        me_h, me_a = row(m.match_id, m.home_team), row(m.match_id, m.away_team)
        for team, me, op, gf, ga in [
            (m.home_team, me_h, me_a, hs, as_),
            (m.away_team, me_a, me_h, as_, hs),
        ]:
            rec: dict[str, Any] = {
                "team": team,
                "goal_diff": gf - ga,
                "points": 3 if gf > ga else (1 if gf == ga else 0),
            }
            for k in metrics:
                rec[k] = me.get(k, float("nan"))
                rec[f"{k}_diff"] = me.get(k, float("nan")) - op.get(k, float("nan"))
            out.append(rec)
    return pd.DataFrame(out)


def build_exploratory(
    dim_match: pd.DataFrame,
    wide: pd.DataFrame,
    timeline: pd.DataFrame,
    snapshot: int | None = None,
) -> dict[str, Any]:
    """As quatro leituras exploratórias, cumulativas até `snapshot`."""
    if dim_match.empty or wide.empty:
        return {}
    tg = _team_games(dim_match, wide, snapshot)
    if tg.empty or len(tg) < _MIN_GAMES:
        return {"amostra": len(tg)}

    metrics = [m for m in METRIC_LABELS if m in tg.columns]

    # ── 1. O que decide os jogos (diff da métrica × saldo de gols) ───────────
    decisao: list[dict[str, Any]] = []
    for m in metrics:
        s = pd.to_numeric(tg[f"{m}_diff"], errors="coerce")
        gd = pd.to_numeric(tg["goal_diff"], errors="coerce")
        valid = s.notna() & gd.notna()
        if valid.sum() < _MIN_GAMES:
            continue
        c = s[valid].corr(gd[valid])
        if pd.notna(c):
            decisao.append({"metric": m, "label": METRIC_LABELS[m], "corr": round(float(c), 2)})
    decisao.sort(key=lambda d: d["corr"], reverse=True)

    # ── 2. Mapa de estilos (do snapshot_timeline) ────────────────────────────
    estilos: list[dict[str, Any]] = []
    if not timeline.empty and "snapshot_jogo" in timeline.columns:
        last = int(timeline["snapshot_jogo"].max())
        target = last if snapshot is None else min(snapshot, last)
        snap = timeline[timeline["snapshot_jogo"] == target]
        axes = {"estilo_posse": "posse", "estilo_verticalidade": "verticalidade", "estilo_pressao": "pressao"}
        if all(c in snap.columns for c in axes) and "estilo_jogo" in snap.columns:
            for r in snap.itertuples():
                ponto = {"team": r.team, "arquetipo": getattr(r, "estilo_jogo", None)}
                for col, key in axes.items():
                    ponto[key] = round(_num(getattr(r, col)), 1)
                if not np.isnan(ponto["posse"]):
                    estilos.append(ponto)

    # ── 3. Paisagem de eficiência (xG × gols por jogo) ───────────────────────
    eficiencia: list[dict[str, Any]] = []
    if not timeline.empty and {"xg_pj", "gols_pj"}.issubset(timeline.columns):
        last = int(timeline["snapshot_jogo"].max())
        target = last if snapshot is None else min(snapshot, last)
        snap = timeline[timeline["snapshot_jogo"] == target]
        for r in snap.itertuples():
            xg, gols = _num(getattr(r, "xg_pj")), _num(getattr(r, "gols_pj"))
            if not np.isnan(xg) and not np.isnan(gols):
                eficiencia.append({"team": r.team, "xg": round(xg, 2), "gols": round(gols, 2)})

    # ── 4. Correlações entre métricas (redundância / oposição) ───────────────
    correlacoes: list[dict[str, Any]] = []
    mat = tg[metrics].apply(pd.to_numeric, errors="coerce")
    cm = mat.corr()
    seen: set[frozenset[str]] = set()
    pares: list[tuple[float, str, str]] = []
    for a in metrics:
        for b in metrics:
            if a == b or frozenset({a, b}) in seen:
                continue
            seen.add(frozenset({a, b}))
            c = cm.loc[a, b]
            if pd.notna(c):
                pares.append((float(c), a, b))
    pares.sort(key=lambda p: abs(p[0]), reverse=True)
    for c, a, b in pares[:10]:
        correlacoes.append({
            "a": a, "b": b, "label_a": METRIC_LABELS[a], "label_b": METRIC_LABELS[b],
            "corr": round(c, 2),
        })

    return {
        "amostra": len(tg),
        "decisao": decisao,
        "estilos": estilos,
        "eficiencia": eficiencia,
        "correlacoes": correlacoes,
    }
