"""Análise Exploratória — que padrões existem (EDA com sentido).

Sai do descrever e do explicar-um-jogo para responder PERGUNTAS sobre a Copa,
cada uma com leitura clara. Cumulativo até `snapshot`. Seções:

  decide        — o que decide os jogos: correlação do diferencial de cada
                  métrica (time − adversário) com o saldo. O que pesa × o que engana.
  eficiencia    — quem rende além/aquém do que cria (gols − xG por jogo).
  quadrante     — cada seleção em cria (xG) × converte (gols−xG): elite,
                  frustrados, oportunistas, em apuros.
  estilo_resultado — qual estilo está rendendo (pontos/jogo por arquétipo).
  estilos_mapa  — mapa posse × verticalidade, colorido por arquétipo.
  fases         — de onde vem o perigo (líder por fase: bola parada, contra-ataque…).
  defesa        — o que segura atrás (melhores defesas por xG sofrido + estilo).

Tudo do gold: team_match_wide (métricas por jogo), dim_match (resultado),
snapshot_timeline (médias/estilo/pontos acumulados).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

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
_PHASES = [
    ("fase_bola_parada", "Bola parada"),
    ("fase_contra_ataque", "Contra-ataque"),
    ("fase_terceiro_final", "Ataque posicional"),
    ("fase_bola_longa", "Jogo direto (bola longa)"),
    ("fase_pressao_alta", "Pressão alta"),
]
_MIN_GAMES = 6


def _num(v: Any) -> float:
    try:
        f = float(v)
        return float("nan") if np.isnan(f) else f
    except (TypeError, ValueError):
        return float("nan")


def _team_games(dim_match: pd.DataFrame, wide: pd.DataFrame, snapshot: int | None) -> pd.DataFrame:
    finished = dim_match[dim_match["status"] == "finalizado"].copy()
    sort_col = "date_utc" if "date_utc" in finished.columns else "match_number"
    finished = finished.sort_values(sort_col)
    if snapshot is not None:
        finished = finished.head(snapshot)
    if finished.empty or wide.empty:
        return pd.DataFrame()
    metrics = [m for m in METRIC_LABELS if m in wide.columns]
    lookup = {(t.match_id, str(t.team)): t for t in wide.itertuples()}

    def row(mid, team):
        r = lookup.get((mid, str(team)))
        return {m: _num(getattr(r, m, float("nan"))) for m in metrics} if r else {}

    out = []
    for m in finished.itertuples():
        hs, as_ = _num(m.home_score), _num(m.away_score)
        meh, mea = row(m.match_id, m.home_team), row(m.match_id, m.away_team)
        for me, op, gf, ga in [(meh, mea, hs, as_), (mea, meh, as_, hs)]:
            rec = {"goal_diff": gf - ga}
            for k in metrics:
                rec[f"{k}_diff"] = me.get(k, float("nan")) - op.get(k, float("nan"))
            out.append(rec)
    return pd.DataFrame(out)


def build_exploratory(
    dim_match: pd.DataFrame,
    wide: pd.DataFrame,
    timeline: pd.DataFrame,
    snapshot: int | None = None,
) -> dict[str, Any]:
    if dim_match.empty or wide.empty:
        return {}
    tg = _team_games(dim_match, wide, snapshot)
    if tg.empty or len(tg) < _MIN_GAMES:
        return {"amostra": len(tg)}

    # ── decide: correlação do diferencial × saldo de gols ────────────────────
    decide = []
    gd = pd.to_numeric(tg["goal_diff"], errors="coerce")
    for m, label in METRIC_LABELS.items():
        col = f"{m}_diff"
        if col not in tg.columns:
            continue
        s = pd.to_numeric(tg[col], errors="coerce")
        valid = s.notna() & gd.notna()
        if valid.sum() < _MIN_GAMES:
            continue
        c = s[valid].corr(gd[valid])
        if pd.notna(c):
            decide.append({"metric": m, "label": label, "corr": round(float(c), 2)})
    decide.sort(key=lambda d: d["corr"], reverse=True)

    # ── leituras por seleção (snapshot acumulado) ────────────────────────────
    eficiencia: list[dict[str, Any]] = []
    quadrante: dict[str, Any] = {"pontos": [], "cria_ref": None}
    estilo_resultado: list[dict[str, Any]] = []
    estilos_mapa: list[dict[str, Any]] = []
    fases: list[dict[str, Any]] = []
    defesa: list[dict[str, Any]] = []

    if not timeline.empty and "snapshot_jogo" in timeline.columns:
        last = int(timeline["snapshot_jogo"].max())
        target = last if snapshot is None else min(snapshot, last)
        snap = timeline[timeline["snapshot_jogo"] == target].copy()
        if "jogos" in snap.columns:
            snap = snap[snap["jogos"] >= 1]

        # eficiência (gols − xG por jogo) + quadrante (cria × converte)
        if {"xg_pj", "gols_pj"}.issubset(snap.columns):
            snap["criaPj"] = pd.to_numeric(snap["xg_pj"], errors="coerce")
            snap["convPj"] = pd.to_numeric(snap["gols_pj"], errors="coerce") - snap["criaPj"]
            ef = snap[snap["criaPj"].notna() & snap["convPj"].notna()]
            for r in ef.sort_values("convPj", ascending=False).itertuples():
                eficiencia.append({"team": r.team, "xg": round(r.criaPj, 2),
                                   "gols": round(_num(r.gols_pj), 2), "overperf": round(r.convPj, 2)})
            cria_ref = float(ef["criaPj"].median()) if not ef.empty else 0.0
            # Zona neutra: quem está perto do centro nos DOIS eixos não é cravado
            # num perfil (números próximos das linhas = classificação incerta).
            mx = 0.5 * float(ef["criaPj"].std(ddof=0) or 0.0)
            my = 0.5 * float(ef["convPj"].std(ddof=0) or 0.0)
            quadrante["cria_ref"] = round(cria_ref, 2)
            quadrante["mx"] = round(mx, 2)
            quadrante["my"] = round(my, 2)
            for r in ef.itertuples():
                if abs(r.criaPj - cria_ref) <= mx and abs(r.convPj) <= my:
                    perfil = "Neutro"
                else:
                    cria_hi = r.criaPj >= cria_ref
                    conv_pos = r.convPj >= 0
                    perfil = ("Elite" if (cria_hi and conv_pos) else
                              "Frustrados" if (cria_hi and not conv_pos) else
                              "Oportunistas" if (not cria_hi and conv_pos) else "Em apuros")
                quadrante["pontos"].append({"team": r.team, "cria": round(r.criaPj, 2),
                                            "converte": round(r.convPj, 2), "perfil": perfil})

        # estilo × resultado
        if {"estilo_jogo", "points", "jogos"}.issubset(snap.columns):
            for arq, d in snap.groupby("estilo_jogo"):
                jg = float(pd.to_numeric(d["jogos"], errors="coerce").sum())
                pts = float(pd.to_numeric(d["points"], errors="coerce").sum())
                if jg <= 0 or not arq:
                    continue
                estilo_resultado.append({
                    "arquetipo": arq, "n": int(len(d)),
                    "pts_jogo": round(pts / jg, 2),
                    "aproveitamento": round(pts / (jg * 3) * 100),
                })
            estilo_resultado.sort(key=lambda e: e["pts_jogo"], reverse=True)

        # mapa de estilos
        if all(c in snap.columns for c in ("estilo_posse", "estilo_verticalidade", "estilo_jogo")):
            for r in snap.itertuples():
                p, v = _num(r.estilo_posse), _num(r.estilo_verticalidade)
                if not np.isnan(p) and not np.isnan(v):
                    estilos_mapa.append({"team": r.team, "posse": round(p, 1),
                                         "verticalidade": round(v, 1), "arquetipo": getattr(r, "estilo_jogo", None)})

        # de onde vem o perigo (líder por fase)
        for col, label in _PHASES:
            if col in snap.columns:
                s = snap[snap[col].notna()]
                if not s.empty:
                    top = s.sort_values(col, ascending=False).iloc[0]
                    fases.append({"fase": label, "team": top["team"]})

        # defesa: o que segura (melhores por xG sofrido)
        if "xg_sofrido_pj" in snap.columns:
            d = snap[snap["xg_sofrido_pj"].notna()].sort_values("xg_sofrido_pj").head(5)
            for r in d.itertuples():
                defesa.append({
                    "team": r.team,
                    "xg_sofrido": round(_num(r.xg_sofrido_pj), 2),
                    "clean_sheets": int(_num(getattr(r, "clean_sheet", 0))),
                    "estilo": getattr(r, "estilo_jogo", None),
                })

    return {
        "amostra": len(tg),
        "decide": decide,
        "eficiencia": eficiencia,
        "quadrante": quadrante,
        "estilo_resultado": estilo_resultado,
        "estilos_mapa": estilos_mapa,
        "fases": fases,
        "defesa": defesa,
    }
