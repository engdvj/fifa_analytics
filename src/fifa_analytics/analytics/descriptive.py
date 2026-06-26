"""Análise Descritiva — panorama AGREGADO do torneio (o que aconteceu).

Diferente da Diagnóstica (um jogo, o porquê), a Descritiva sintetiza o estado da
competição no **total** da fase: totais, tendência por rodada (a cada 24 jogos),
líderes, recordes e surpresas.

Escopo = TODOS os jogos finalizados (não cumulativo por slider). A leitura temporal
vem da **tendência por rodada** (R1 × R2 × R3 na fase de grupos; fases do mata-mata
por stage). Computado sob demanda, reusando o gold:
  - dim_match            → resultados (totais, goleadas, blocos por rodada/fase)
  - team_match_wide      → xG por jogo, recordes (maior xG, cartões, goleiro)
  - snapshot_timeline    → líderes acumulados (ataque, defesa, eficiência, estilo)
  - fact_insights        → surpresas (zebras: contra o xG, vitórias de prestígio)

Uso:
    from fifa_analytics.analytics.descriptive import build_digest
    digest = build_digest(dim_match, wide, timeline, insights)
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

# Rótulos pt-BR das fases (o gold guarda em inglês).
STAGE_PT = {
    "First Stage": "Fase de Grupos", "Round of 32": "16-avos", "Round of 16": "Oitavas",
    "Quarter-final": "Quartas", "Semi-final": "Semifinal",
    "Play-off for third place": "3º lugar", "Final": "Final",
}
_ROUND_SIZE = 24  # uma rodada da fase de grupos = 48 seleções / 2


def _num(v: Any, default: float = float("nan")) -> float:
    try:
        f = float(v)
        return default if np.isnan(f) else f
    except (TypeError, ValueError):
        return default


def _round(v: Any, n: int = 2) -> float | None:
    f = _num(v)
    return None if np.isnan(f) else round(f, n)


def _match_label(row: pd.Series) -> str:
    return f"{row['home_team']} {int(_num(row['home_score'], 0))}–{int(_num(row['away_score'], 0))} {row['away_team']}"


def _block_stats(chunk: pd.DataFrame, xg_match: pd.Series) -> dict[str, Any]:
    hs = chunk["home_score"].apply(_num)
    as_ = chunk["away_score"].apply(_num)
    n = len(chunk)
    gols = int((hs + as_).sum())
    empates = int((hs == as_).sum())
    goleadas = int(((hs - as_).abs() >= 3).sum())
    xg_vals = xg_match.reindex(chunk["match_id"]).dropna()
    return {
        "jogos": n,
        "gols_por_jogo": round(gols / n, 2) if n else 0,
        "xg_medio": round(float(xg_vals.mean()), 2) if len(xg_vals) else None,
        "empates": empates,
        "goleadas": goleadas,
    }


def _blocks(games: pd.DataFrame):
    """(label, subset) por rodada (fase de grupos, blocos de 24) e por fase (mata-mata)."""
    out = []
    fs = games[games["stage"] == "First Stage"]
    for k in range(0, len(fs), _ROUND_SIZE):
        chunk = fs.iloc[k:k + _ROUND_SIZE]
        if not chunk.empty:
            out.append((f"Rodada {k // _ROUND_SIZE + 1}", chunk))
    for stage in [s for s in games["stage"].dropna().unique() if s != "First Stage"]:
        out.append((STAGE_PT.get(stage, stage), games[games["stage"] == stage]))
    return out


def build_digest(
    dim_match: pd.DataFrame,
    wide: pd.DataFrame,
    timeline: pd.DataFrame,
    insights: pd.DataFrame,
    snapshot: int | None = None,
) -> dict[str, Any]:
    """Panorama agregado, **cumulativo** até `snapshot` (default: tudo finalizado).

    Escopa os jogos aos primeiros `snapshot` finalizados (ordem cronológica), de
    modo que o panorama cresce conforme o slider avança e as rodadas aparecem à
    medida que acontecem.
    """
    if dim_match.empty:
        return {}
    finished = dim_match[dim_match["status"] == "finalizado"].copy()
    if finished.empty:
        return {}
    sort_col = "date_utc" if "date_utc" in finished.columns else "match_number"
    games = finished.sort_values(sort_col).reset_index(drop=True)
    if snapshot is not None:
        games = games.head(snapshot).reset_index(drop=True)
    if games.empty:
        return {}
    mids = set(games["match_id"])
    n = len(games)

    # xG por jogo (soma dos dois times) — base de recordes e tendência.
    w = wide[wide["match_id"].isin(mids)] if not wide.empty else pd.DataFrame()
    xg_match = (w.groupby("match_id")["xg"].sum() if (not w.empty and "xg" in w.columns)
                else pd.Series(dtype=float))

    # ── Totais (toda a fase) ─────────────────────────────────────────────────
    hs = games["home_score"].apply(_num)
    as_ = games["away_score"].apply(_num)
    gols = int((hs + as_).sum())
    empates = int((hs == as_).sum())
    mandante = int((hs > as_).sum())
    decisivos = n - empates
    goleadas = int(((hs - as_).abs() >= 3).sum())
    fase = STAGE_PT.get(str(games.iloc[-1]["stage"]), "Competição")
    totais = {
        "jogos": n, "gols": gols,
        "gols_por_jogo": round(gols / n, 2) if n else 0,
        "xg_por_jogo": round(float(xg_match.mean()), 2) if len(xg_match) else None,
        "empates": empates, "decisivos": decisivos,
        "pct_decisivos": round(decisivos / n * 100) if n else 0,
        "vitorias_mandante": mandante, "pct_mandante": round(mandante / n * 100) if n else 0,
        "goleadas": goleadas,
    }

    # ── Tendência por rodada/fase ────────────────────────────────────────────
    tendencia = [{"rodada": label, **_block_stats(chunk, xg_match)} for label, chunk in _blocks(games)]

    # ── Líderes (acumulado total = último snapshot) ──────────────────────────
    lideres: list[dict[str, Any]] = []
    if not timeline.empty and "snapshot_jogo" in timeline.columns:
        last = int(timeline["snapshot_jogo"].max())
        target = last if snapshot is None else min(snapshot, last)
        snap = timeline[timeline["snapshot_jogo"] == target].copy()
        snap = snap[snap["jogos"] >= 1] if "jogos" in snap.columns else snap

        def push(col, ascending, label, fmt, mask=None):
            s = snap if mask is None else snap[mask(snap)]
            s = s[s[col].notna()] if col in s.columns else pd.DataFrame()
            if s.empty:
                return
            r = s.sort_values(col, ascending=ascending).iloc[0]
            lideres.append({"categoria": label, "team": r["team"], "valor": fmt(r)})

        push("xg_pj", False, "Melhor ataque", lambda r: f"{_num(r['xg_pj']):.2f} xG/jogo")
        push("xg_sofrido_pj", True, "Melhor defesa",
             lambda r: f"{_num(r['xg_sofrido_pj']):.2f} xG sofrido/jogo"
                       + (f" · {int(_num(r['clean_sheet'],0))} sem sofrer" if "clean_sheet" in r else ""))
        if {"gols", "xg"}.issubset(snap.columns):
            snap["_overperf"] = snap["gols"] - snap["xg"]
            relevante = lambda s: (s["jogos"] >= 2) & (s["xg"] >= 1.0)
            push("_overperf", False, "Mais eficiente (gols − xG)",
                 lambda r: f"+{r['_overperf']:.1f} gols vs. esperado", mask=relevante)
            push("_overperf", True, "Menos aproveitou (gols − xG)",
                 lambda r: f"{r['_overperf']:.1f} gols vs. esperado", mask=relevante)
        if "posse" in snap.columns:
            push("posse", False, "Mais com a bola", lambda r: f"{_num(r['posse'])*100:.0f}% de posse")
        if "final_third_control" in snap.columns:
            push("final_third_control", False, "Maior controle territorial",
                 lambda r: f"{_num(r['final_third_control']):.0f}% no terço final")

    # ── Recordes / atuações únicas ───────────────────────────────────────────
    recordes: list[dict[str, Any]] = []
    gi = (hs - as_).abs().idxmax()
    recordes.append({"label": "Maior goleada", "valor": _match_label(games.loc[gi]), "match_id": games.loc[gi, "match_id"]})
    if len(xg_match):
        top_xg = xg_match.sort_values(ascending=False)
        row = games[games["match_id"] == top_xg.index[0]]
        if not row.empty:
            recordes.append({"label": "Jogo de maior perigo (xG)",
                             "valor": f"{_match_label(row.iloc[0])} · xG {top_xg.iloc[0]:.2f}",
                             "match_id": top_xg.index[0]})
    if not w.empty and {"amarelos", "vermelhos"}.issubset(w.columns):
        cards = (w["amarelos"].fillna(0) + w["vermelhos"].fillna(0)).groupby(w["match_id"]).sum().sort_values(ascending=False)
        if len(cards) and cards.iloc[0] > 0:
            row = games[games["match_id"] == cards.index[0]]
            if not row.empty:
                recordes.append({"label": "Jogo mais quente", "valor": f"{_match_label(row.iloc[0])} · {int(cards.iloc[0])} cartões",
                                 "match_id": cards.index[0]})
    if not w.empty and "defesas_goleiro" in w.columns:
        ws = w[w["defesas_goleiro"].notna()]
        if not ws.empty:
            gk = ws.sort_values("defesas_goleiro", ascending=False).iloc[0]
            pct = _num(gk.get("save_pct_goleiro"))
            val = f"{gk.get('team', '—')} · {int(_num(gk['defesas_goleiro'],0))} defesas"
            if not np.isnan(pct):
                val += f" ({pct*100:.0f}%)"
            recordes.append({"label": "Goleiro da fase", "valor": val, "match_id": gk.get("match_id")})

    # ── Surpresas (zebras) — autossuficientes ────────────────────────────────
    zebras: list[dict[str, Any]] = []
    if not insights.empty and {"match_id", "achado_key"}.issubset(insights.columns):
        z = insights[insights["achado_key"].isin(["resultado_vs_xg", "vitoria_prestigio"])]
        z = z.sort_values("snapshot", ascending=False) if "snapshot" in z.columns else z
        label_by_match = {m: _match_label(games[games["match_id"] == m].iloc[0])
                          for m in z["match_id"].unique() if (games["match_id"] == m).any()}
        seen: set[str] = set()
        for r in z.itertuples():
            if r.match_id in seen or r.match_id not in label_by_match:
                continue
            seen.add(r.match_id)
            ev = {}
            try:
                ev = json.loads(r.evidencia) if isinstance(getattr(r, "evidencia", None), str) else {}
            except (json.JSONDecodeError, TypeError):
                ev = {}
            if r.achado_key == "vitoria_prestigio":
                rk = ev.get("ranking_adversario")
                nota = f"venceu o {rk}º colocado do ranking" if rk else "vitória de prestígio"
            else:
                nota = "criou mais perigo e não venceu"
            zebras.append({"titulo": label_by_match[r.match_id], "nota": nota, "match_id": r.match_id})
            if len(zebras) >= 6:
                break

    return {
        "fase": fase,
        "totais": totais,
        "tendencia": tendencia,
        "lideres": lideres,
        "recordes": recordes,
        "zebras": zebras,
    }
