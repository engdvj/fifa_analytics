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


def _confidence(sample: int) -> dict[str, Any]:
    """Leitura simples de estabilidade para a UI."""
    if sample >= 80:
        return {"nivel": "robusto", "label": "amostra robusta"}
    if sample >= 30:
        return {"nivel": "moderado", "label": "amostra moderada"}
    if sample >= _MIN_GAMES:
        return {"nivel": "baixo", "label": "amostra baixa"}
    return {"nivel": "insuficiente", "label": "amostra insuficiente"}


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


def _team_results(dim_match: pd.DataFrame, snapshot: int | None) -> pd.DataFrame:
    finished = dim_match[dim_match["status"] == "finalizado"].copy()
    sort_col = "date_utc" if "date_utc" in finished.columns else "match_number"
    finished = finished.sort_values(sort_col)
    if snapshot is not None:
        finished = finished.head(snapshot)
    if finished.empty:
        return pd.DataFrame()

    out = []
    for m in finished.itertuples():
        hs, as_ = _num(m.home_score), _num(m.away_score)
        if np.isnan(hs) or np.isnan(as_):
            continue
        for team, gf, ga in [(m.home_team, hs, as_), (m.away_team, as_, hs)]:
            out.append({
                "team": str(team),
                "vitorias": int(gf > ga),
                "empates": int(gf == ga),
                "derrotas": int(gf < ga),
                "gols_feitos": gf,
                "gols_sofridos": ga,
            })
    if not out:
        return pd.DataFrame()
    df = pd.DataFrame(out)
    return df.groupby("team", as_index=False).agg({
        "vitorias": "sum",
        "empates": "sum",
        "derrotas": "sum",
        "gols_feitos": "sum",
        "gols_sofridos": "sum",
    })


def _finished_matches(dim_match: pd.DataFrame, snapshot: int | None) -> pd.DataFrame:
    finished = dim_match[dim_match["status"] == "finalizado"].copy()
    sort_col = "date_utc" if "date_utc" in finished.columns else "match_number"
    finished = finished.sort_values(sort_col)
    return finished.head(snapshot) if snapshot is not None else finished


def _style_matchup_metrics(
    dim_match: pd.DataFrame,
    wide: pd.DataFrame,
    snap: pd.DataFrame,
    snapshot: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    needed = {"team", "estilo_jogo"}
    if snap.empty or not needed.issubset(snap.columns):
        return [], []

    finished = _finished_matches(dim_match, snapshot)
    if finished.empty:
        return [], []

    snap_by_team = {str(row["team"]): row for _, row in snap.iterrows() if pd.notna(row.get("team"))}
    wide_by_team = {
        (str(row["match_id"]), str(row["team"])): row
        for _, row in wide.iterrows()
        if pd.notna(row.get("match_id")) and pd.notna(row.get("team"))
    }

    def row_metric(mid: Any, team: Any, col: str) -> float:
        row = wide_by_team.get((str(mid), str(team)))
        return _num(row.get(col)) if row is not None and col in row else float("nan")

    def snap_metric(team: Any, col: str) -> float:
        row = snap_by_team.get(str(team))
        return _num(row.get(col)) if row is not None and col in row else float("nan")

    games: list[dict[str, Any]] = []
    for m in finished.itertuples():
        home, away = str(m.home_team), str(m.away_team)
        home_info, away_info = snap_by_team.get(home), snap_by_team.get(away)
        if home_info is None or away_info is None:
            continue
        home_style, away_style = home_info.get("estilo_jogo"), away_info.get("estilo_jogo")
        if not home_style or not away_style:
            continue
        hs, aws = _num(m.home_score), _num(m.away_score)
        if np.isnan(hs) or np.isnan(aws):
            continue

        hxg = row_metric(m.match_id, home, "xg")
        axg = row_metric(m.match_id, away, "xg")

        sides = [
            (home, away, str(home_style), str(away_style), hs, aws, hxg, axg),
            (away, home, str(away_style), str(home_style), aws, hs, axg, hxg),
        ]
        for team, opp, style, against, gf, ga, xg_for, xg_against in sides:
            points = 3 if gf > ga else 1 if gf == ga else 0
            games.append({
                "estilo": style,
                "contra": against,
                "team": team,
                "adversario": opp,
                "points": points,
                "goal_diff": gf - ga,
                "xg_diff": xg_for - xg_against if not np.isnan(xg_for) and not np.isnan(xg_against) else float("nan"),
                "score_diff": snap_metric(team, "score_geral") - snap_metric(opp, "score_geral"),
                "attack_diff": snap_metric(team, "score_ataque") - snap_metric(opp, "score_ataque"),
                "defense_diff": snap_metric(team, "score_defesa") - snap_metric(opp, "score_defesa"),
            })

    if not games:
        return [], []

    base = pd.DataFrame(games)

    def mean_or_none(d: pd.DataFrame, col: str) -> float | None:
        value = pd.to_numeric(d[col], errors="coerce").mean() if col in d.columns else np.nan
        return round(float(value), 2) if pd.notna(value) else None

    matchups: list[dict[str, Any]] = []
    for (style, against), d in base.groupby(["estilo", "contra"]):
        jogos = int(len(d))
        points = float(pd.to_numeric(d["points"], errors="coerce").sum())
        matchups.append({
            "estilo": style,
            "contra": against,
            "jogos": jogos,
            "vitorias": int((d["points"] == 3).sum()),
            "empates": int((d["points"] == 1).sum()),
            "derrotas": int((d["points"] == 0).sum()),
            "pts_jogo": round(points / jogos, 2) if jogos else 0.0,
            "aproveitamento": round(points / (jogos * 3) * 100) if jogos else 0,
            "saldo_pj": mean_or_none(d, "goal_diff"),
            "xg_diff_pj": mean_or_none(d, "xg_diff"),
            "score_diff_medio": mean_or_none(d, "score_diff"),
            "times": sorted(str(t) for t in d["team"].dropna().unique()),
        })
    matchups.sort(key=lambda r: (r["jogos"], r["pts_jogo"], r["saldo_pj"] or 0), reverse=True)

    influences: list[dict[str, Any]] = []
    target = pd.to_numeric(base["goal_diff"], errors="coerce")
    factors = [
        ("Score geral", "score_diff", "forca relativa acumulada antes do recorte"),
        ("Score de ataque", "attack_diff", "vantagem ofensiva acumulada"),
        ("Score de defesa", "defense_diff", "vantagem defensiva acumulada"),
        ("xG do jogo", "xg_diff", "perigo criado no confronto"),
    ]
    for label, col, note in factors:
        values = pd.to_numeric(base[col], errors="coerce")
        valid = values.notna() & target.notna()
        corr: float | None = None
        if valid.sum() >= 3 and values[valid].nunique() > 1 and target[valid].nunique() > 1:
            value = values[valid].corr(target[valid])
            corr = round(float(value), 2) if pd.notna(value) else None
        strength = "amostra baixa"
        if corr is not None:
            a = abs(corr)
            strength = "forte" if a >= 0.55 else "moderada" if a >= 0.3 else "fraca"
        influences.append({
            "fator": label,
            "corr": corr,
            "n": int(valid.sum()),
            "leitura": strength,
            "nota": note,
        })
    influences.sort(key=lambda r: abs(r["corr"]) if r["corr"] is not None else -1, reverse=True)
    return matchups, influences


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
            decide.append({"metric": m, "label": label, "corr": round(float(c), 2), "n": int(valid.sum())})
    decide.sort(key=lambda d: d["corr"], reverse=True)

    # ── leituras por seleção (snapshot acumulado) ────────────────────────────
    eficiencia: list[dict[str, Any]] = []
    quadrante: dict[str, Any] = {"pontos": [], "cria_ref": None}
    estilo_resultado: list[dict[str, Any]] = []
    estilos_mapa: list[dict[str, Any]] = []
    confrontos_estilo: list[dict[str, Any]] = []
    influencias_confronto: list[dict[str, Any]] = []
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
                                   "gols": round(_num(r.gols_pj), 2), "overperf": round(r.convPj, 2),
                                   "jogos": int(_num(getattr(r, "jogos", 0)))})
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
                                            "converte": round(r.convPj, 2), "perfil": perfil,
                                            "jogos": int(_num(getattr(r, "jogos", 0)))})

        # estilo × resultado
        if {"estilo_jogo", "points", "jogos"}.issubset(snap.columns):
            results = _team_results(dim_match, snapshot)
            style_base = snap.merge(results, on="team", how="left") if not results.empty else snap.copy()
            for arq, d in style_base.groupby("estilo_jogo"):
                jg = float(pd.to_numeric(d["jogos"], errors="coerce").sum())
                pts = float(pd.to_numeric(d["points"], errors="coerce").sum())
                if jg <= 0 or not arq:
                    continue
                def mean_col(col: str) -> float | None:
                    if col not in d.columns:
                        return None
                    val = pd.to_numeric(d[col], errors="coerce").mean()
                    return round(float(val), 2) if pd.notna(val) else None
                def sum_col(col: str) -> float:
                    if col not in d.columns:
                        return 0.0
                    return float(pd.to_numeric(d[col], errors="coerce").fillna(0).sum())
                def per_game(total_col: str, fallback_pj_col: str) -> float | None:
                    if total_col in d.columns:
                        return round(float(sum_col(total_col) / jg), 2)
                    return mean_col(fallback_pj_col)
                def weighted_col(col: str) -> float | None:
                    if col not in d.columns:
                        return None
                    values = pd.to_numeric(d[col], errors="coerce")
                    weights = pd.to_numeric(d["jogos"], errors="coerce").fillna(0)
                    valid = values.notna() & (weights > 0)
                    if not valid.any():
                        return None
                    return round(float((values[valid] * weights[valid]).sum() / weights[valid].sum()), 2)
                def pct_col(col: str) -> float | None:
                    val = weighted_col(col)
                    if val is None:
                        return None
                    return round(val * 100, 1) if val <= 1 else round(val, 1)
                def metric(label: str, value: float | None, unit: str = "", decimals: int = 2) -> dict[str, Any] | None:
                    if value is None or np.isnan(value):
                        return None
                    return {"label": label, "valor": round(float(value), decimals), "unit": unit, "decimals": decimals}
                def style_metrics(arq_nome: str) -> list[dict[str, Any]]:
                    saldo_pj = round(float(sum_col("saldo_gols") / jg), 2)
                    clean_pct = round(float(sum_col("clean_sheet") / jg * 100), 1) if "clean_sheet" in d.columns else None
                    base: list[dict[str, Any] | None]
                    if arq_nome == "Pressão Alta":
                        base = [
                            metric("Pressão alta", weighted_col("fase_pressao_alta"), decimals=1),
                            metric("Roubadas/jogo", per_game("turnovers_forcados", "turnovers_forcados_pj")),
                            metric("xG sofrido/jogo", per_game("xg_sofrido", "xg_sofrido_pj")),
                            metric("Saldo/jogo", saldo_pj),
                        ]
                    elif arq_nome == "Posse":
                        base = [
                            metric("Posse média", pct_col("posse"), "%", 1),
                            metric("Controle terço final", pct_col("final_third_control"), "%", 1),
                            metric("Precisão passe", pct_col("precisao_passes"), "%", 1),
                            metric("xG sofrido/jogo", per_game("xg_sofrido", "xg_sofrido_pj")),
                        ]
                    elif arq_nome == "Retranca":
                        base = [
                            metric("xG sofrido/jogo", per_game("xg_sofrido", "xg_sofrido_pj")),
                            metric("Gols sofridos/jogo", per_game("gols_contra", "gols_contra_pj")),
                            metric("Clean sheets", clean_pct, "%", 1),
                            metric("Chutes no alvo sofridos/jogo", per_game("chutes_sofridos_no_alvo", "chutes_sofridos_no_alvo_pj")),
                        ]
                    elif arq_nome == "Jogo Direto":
                        base = [
                            metric("Bola longa", weighted_col("fase_bola_longa"), decimals=1),
                            metric("Quebras de linha/jogo", per_game("linebreaks", "linebreaks_pj")),
                            metric("Progressões/jogo", per_game("progressoes_bola", "progressoes_bola_pj")),
                            metric("xG/jogo", per_game("xg", "xg_pj")),
                        ]
                    elif arq_nome == "Contra-ataque":
                        base = [
                            metric("Contra-ataque", weighted_col("fase_contra_ataque"), decimals=1),
                            metric("Verticalidade", weighted_col("estilo_verticalidade"), decimals=1),
                            metric("xG/jogo", per_game("xg", "xg_pj")),
                            metric("Saldo/jogo", saldo_pj),
                        ]
                    elif arq_nome == "Bola Parada":
                        base = [
                            metric("Bola parada", weighted_col("fase_bola_parada"), decimals=1),
                            metric("Escanteios/jogo", per_game("escanteios", "escanteios_pj")),
                            metric("xG/jogo", per_game("xg", "xg_pj")),
                            metric("Gols/jogo", per_game("gols", "gols_pj")),
                        ]
                    else:
                        base = [
                            metric("Gols/jogo", per_game("gols", "gols_pj")),
                            metric("xG/jogo", per_game("xg", "xg_pj")),
                            metric("xG sofrido/jogo", per_game("xg_sofrido", "xg_sofrido_pj")),
                            metric("Saldo/jogo", saldo_pj),
                        ]
                    return [m for m in base if m is not None]
                def team_detail(row: pd.Series, arq_nome: str) -> dict[str, Any]:
                    team_jogos = _num(row.get("jogos"))
                    team_jogos = team_jogos if not np.isnan(team_jogos) and team_jogos > 0 else 0.0
                    team_points = _num(row.get("points"))
                    team_points = 0.0 if np.isnan(team_points) else team_points
                    def row_num(col: str) -> float | None:
                        val = _num(row.get(col))
                        return None if np.isnan(val) else val
                    def row_per_game(total_col: str, fallback_pj_col: str) -> float | None:
                        total = row_num(total_col)
                        if total is not None and team_jogos > 0:
                            return round(float(total / team_jogos), 2)
                        val = row_num(fallback_pj_col)
                        return round(float(val), 2) if val is not None else None
                    def row_pct(col: str) -> float | None:
                        val = row_num(col)
                        if val is None:
                            return None
                        return round(val * 100, 1) if val <= 1 else round(val, 1)
                    def row_metric(label: str, value: float | None, unit: str = "", decimals: int = 2) -> dict[str, Any] | None:
                        if value is None or np.isnan(value):
                            return None
                        return {"label": label, "valor": round(float(value), decimals), "unit": unit, "decimals": decimals}
                    saldo_team = row_per_game("saldo_gols", "saldo_gols_pj")
                    clean_sheets = row_num("clean_sheet")
                    clean_pct_team = round(float(clean_sheets / team_jogos * 100), 1) if clean_sheets is not None and team_jogos > 0 else None
                    if arq_nome == "Pressão Alta":
                        metrics = [
                            row_metric("Pressão alta", row_num("fase_pressao_alta"), decimals=1),
                            row_metric("Roubadas/jogo", row_per_game("turnovers_forcados", "turnovers_forcados_pj")),
                            row_metric("xG sofrido/jogo", row_per_game("xg_sofrido", "xg_sofrido_pj")),
                            row_metric("Saldo/jogo", saldo_team),
                        ]
                    elif arq_nome == "Posse":
                        metrics = [
                            row_metric("Posse média", row_pct("posse"), "%", 1),
                            row_metric("Controle terço final", row_pct("final_third_control"), "%", 1),
                            row_metric("Precisão passe", row_pct("precisao_passes"), "%", 1),
                            row_metric("xG sofrido/jogo", row_per_game("xg_sofrido", "xg_sofrido_pj")),
                        ]
                    elif arq_nome == "Retranca":
                        metrics = [
                            row_metric("xG sofrido/jogo", row_per_game("xg_sofrido", "xg_sofrido_pj")),
                            row_metric("Gols sofridos/jogo", row_per_game("gols_contra", "gols_contra_pj")),
                            row_metric("Clean sheets", clean_pct_team, "%", 1),
                            row_metric("Chutes no alvo sofridos/jogo", row_per_game("chutes_sofridos_no_alvo", "chutes_sofridos_no_alvo_pj")),
                        ]
                    elif arq_nome == "Jogo Direto":
                        metrics = [
                            row_metric("Bola longa", row_num("fase_bola_longa"), decimals=1),
                            row_metric("Quebras de linha/jogo", row_per_game("linebreaks", "linebreaks_pj")),
                            row_metric("Progressões/jogo", row_per_game("progressoes_bola", "progressoes_bola_pj")),
                            row_metric("xG/jogo", row_per_game("xg", "xg_pj")),
                        ]
                    elif arq_nome == "Contra-ataque":
                        metrics = [
                            row_metric("Contra-ataque", row_num("fase_contra_ataque"), decimals=1),
                            row_metric("Verticalidade", row_num("estilo_verticalidade"), decimals=1),
                            row_metric("xG/jogo", row_per_game("xg", "xg_pj")),
                            row_metric("Saldo/jogo", saldo_team),
                        ]
                    elif arq_nome == "Bola Parada":
                        metrics = [
                            row_metric("Bola parada", row_num("fase_bola_parada"), decimals=1),
                            row_metric("Escanteios/jogo", row_per_game("escanteios", "escanteios_pj")),
                            row_metric("xG/jogo", row_per_game("xg", "xg_pj")),
                            row_metric("Gols/jogo", row_per_game("gols", "gols_pj")),
                        ]
                    else:
                        metrics = [
                            row_metric("Gols/jogo", row_per_game("gols", "gols_pj")),
                            row_metric("xG/jogo", row_per_game("xg", "xg_pj")),
                            row_metric("xG sofrido/jogo", row_per_game("xg_sofrido", "xg_sofrido_pj")),
                            row_metric("Saldo/jogo", saldo_team),
                        ]
                    v_team = int(row_num("vitorias") or 0)
                    e_team = int(row_num("empates") or 0)
                    d_team = int(row_num("derrotas") or 0)
                    return {
                        "team": str(row.get("team")),
                        "arquetipo": arq_nome,
                        "jogos": int(team_jogos),
                        "points": round(float(team_points), 2),
                        "pts_jogo": round(float(team_points / team_jogos), 2) if team_jogos > 0 else 0.0,
                        "aproveitamento": round(float(team_points / (team_jogos * 3) * 100)) if team_jogos > 0 else 0,
                        "vitorias": v_team,
                        "empates": e_team,
                        "derrotas": d_team,
                        "gols_pj": row_per_game("gols", "gols_pj"),
                        "xg_pj": row_per_game("xg", "xg_pj"),
                        "xg_sofrido_pj": row_per_game("xg_sofrido", "xg_sofrido_pj"),
                        "saldo_pj": saldo_team,
                        "metricas_chave": [m for m in metrics if m is not None],
                    }

                v = int(sum_col("vitorias"))
                e = int(sum_col("empates"))
                der = int(sum_col("derrotas"))
                saldo_pj = round(float(sum_col("saldo_gols") / jg), 2)
                detalhes = [team_detail(row, str(arq)) for _, row in d.iterrows()]
                estilo_resultado.append({
                    "arquetipo": arq, "n": int(len(d)),
                    "pts_jogo": round(pts / jg, 2),
                    "aproveitamento": round(pts / (jg * 3) * 100),
                    "jogos": int(jg),
                    "vitorias": v,
                    "empates": e,
                    "derrotas": der,
                    "gols_pj": per_game("gols", "gols_pj"),
                    "xg_pj": per_game("xg", "xg_pj"),
                    "xg_sofrido_pj": per_game("xg_sofrido", "xg_sofrido_pj"),
                    "saldo_pj": saldo_pj,
                    "metricas_chave": style_metrics(str(arq)),
                    "times": sorted([str(t) for t in d["team"].dropna().tolist()]),
                    "times_detalhe": sorted(detalhes, key=lambda x: str(x["team"])),
                })
            estilo_resultado.sort(key=lambda e: e["pts_jogo"], reverse=True)

        # mapa de estilos
        if all(c in snap.columns for c in ("estilo_posse", "estilo_verticalidade", "estilo_jogo")):
            for r in snap.itertuples():
                p, v = _num(r.estilo_posse), _num(r.estilo_verticalidade)
                if not np.isnan(p) and not np.isnan(v):
                    estilos_mapa.append({"team": r.team, "posse": round(p, 1),
                                         "verticalidade": round(v, 1), "arquetipo": getattr(r, "estilo_jogo", None),
                                         "jogos": int(_num(getattr(r, "jogos", 0)))})

        confrontos_estilo, influencias_confronto = _style_matchup_metrics(dim_match, wide, snap, snapshot)

        # de onde vem o perigo (líder por fase)
        for col, label in _PHASES:
            if col in snap.columns:
                s = snap[snap[col].notna()]
                if not s.empty:
                    top_rows = s.sort_values(col, ascending=False).head(3)
                    top = top_rows.iloc[0]
                    fases.append({
                        "fase": label,
                        "team": top["team"],
                        "top": [
                            {"team": r["team"], "valor": round(float(_num(r[col])), 2),
                             "jogos": int(_num(r.get("jogos", 0)))}
                            for _, r in top_rows.iterrows()
                        ],
                    })

        # defesa: o que segura (melhores por xG sofrido)
        if "xg_sofrido_pj" in snap.columns:
            d = snap[snap["xg_sofrido_pj"].notna()].sort_values("xg_sofrido_pj").head(5)
            for r in d.itertuples():
                defesa.append({
                    "team": r.team,
                    "xg_sofrido": round(_num(r.xg_sofrido_pj), 2),
                    "clean_sheets": int(_num(getattr(r, "clean_sheet", 0))),
                    "jogos": int(_num(getattr(r, "jogos", 0))),
                    "estilo": getattr(r, "estilo_jogo", None),
                })

    return {
        "amostra": len(tg),
        "confianca": _confidence(len(tg)),
        "decide": decide,
        "eficiencia": eficiencia,
        "quadrante": quadrante,
        "estilo_resultado": estilo_resultado,
        "estilos_mapa": estilos_mapa,
        "confrontos_estilo": confrontos_estilo,
        "influencias_confronto": influencias_confronto,
        "fases": fases,
        "defesa": defesa,
    }
