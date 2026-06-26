"""Analytics: endpoints que leem os parquets do gold e retornam JSON.

Sem ORM — lê direto do parquet com pandas. Os dados são imutáveis entre
coletas (somente leitura), então sem write neste router.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import pandas as pd
import yaml
from fastapi import APIRouter, Depends, HTTPException, Query

from api.app.models import User
from api.app.routers.auth import require_admin
from fifa_analytics.paths import CONFIG_DIR, GOLD_DIR
from fifa_analytics.transforms.team_names import traduzir_selecao

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _parquet(name: str) -> pd.DataFrame:
    path = GOLD_DIR / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _safe_val(v) -> Any:
    """Converte NaN/NaT para None para serialização JSON."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _records(df: pd.DataFrame, cols: list[str] | None = None) -> list[dict]:
    """DataFrame → list[dict] com NaN→None. `cols` opcional restringe/ordena."""
    if df.empty:
        return []
    use = [c for c in (cols or df.columns) if c in df.columns]
    return [{k: _safe_val(row[k]) for k in use} for row in df[use].to_dict("records")]


@lru_cache(maxsize=1)
def _load_teams_info() -> dict:
    """Infos curadas das seleções (config/teams_info.yaml) — não vem do pipeline.
    Estrutura: {nome_seleção: {apelido, confederacao, tecnico, titulos_copa,
    vices_copa, participacoes, estreia, melhor_campanha, curiosidade}}."""
    path = CONFIG_DIR / "teams_info.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    teams = data.get("teams", data) if isinstance(data, dict) else {}
    return teams if isinstance(teams, dict) else {}


@router.get("/teams-info")
def teams_info(team: str | None = Query(None, description="filtra uma seleção")) -> dict:
    """Infos curadas (apelido, técnico, história em Copas, curiosidade). Alimenta
    a aba Resumo do modal de seleção — conteúdo de identidade, não de stats."""
    info = _load_teams_info()
    if team is not None:
        return info.get(team, {})
    return info


# ── Jogos ─────────────────────────────────────────────────────────────────────

@router.get("/matches")
def list_matches_analytics(status: str | None = None) -> list[dict]:
    """Todos os 104 jogos do gold parquet."""
    df = _parquet("dim_match.parquet")
    if df.empty:
        return []
    if status:
        df = df[df["status"] == status]
    cols = [
        "match_id", "match_number", "home_team", "away_team",
        "home_team_code", "away_team_code", "id_team_home", "id_team_away",
        "stage", "group", "date_utc", "status", "home_score", "away_score",
        "home_penalty", "away_penalty", "stadium", "id_ifes",
    ]
    return _records(df, cols)


@router.get("/matches/{match_id}/stats")
def match_team_stats(match_id: str) -> dict:
    """Métricas avançadas de time do jogo (fact_team_match_stats)."""
    df = _parquet("fact_team_match_stats.parquet")
    if df.empty:
        raise HTTPException(404, "stats não disponíveis (rode fifa-coletar)")
    rows = df[df["match_id"] == match_id]
    if rows.empty:
        raise HTTPException(404, "sem stats para esse jogo")
    by_team: dict[str, list] = {}
    for r in rows.itertuples():
        tid = str(r.id_team)
        by_team.setdefault(tid, []).append({
            "metric": r.metric,
            "value": _safe_val(r.value),
            "is_official": _safe_val(r.is_official),
        })
    return {"match_id": match_id, "teams": by_team}


@router.get("/matches/{match_id}/lineups")
def match_lineups(match_id: str) -> list[dict]:
    """Escalação dos dois times (fact_lineups)."""
    df = _parquet("fact_lineups.parquet")
    if df.empty:
        raise HTTPException(404, "lineups não disponíveis")
    rows = df[df["match_id"] == match_id]
    if rows.empty:
        raise HTTPException(404, "sem escalação para esse jogo")
    cols = ["team_side", "id_team", "id_player", "player_name",
            "shirt_number", "position", "is_starter", "captain",
            "lineup_x", "lineup_y"]
    available = [c for c in cols if c in rows.columns]
    return [{k: _safe_val(r[k]) for k in available} for r in rows[available].to_dict("records")]


@router.get("/matches/{match_id}/events")
def match_events(match_id: str) -> list[dict]:
    """Gols, cartões e substituições do jogo (fact_events)."""
    df = _parquet("fact_events.parquet")
    if df.empty:
        raise HTTPException(404, "eventos não disponíveis")
    rows = df[df["match_id"] == match_id]
    if rows.empty:
        return []
    cols = ["event_type", "minute", "id_team", "id_player", "player_name",
            "detail", "id_assist", "id_player2", "player2_name"]
    available = [c for c in cols if c in rows.columns]
    return [{k: _safe_val(r[k]) for k in available} for r in rows[available].to_dict("records")]


@router.get("/matches/{match_id}/player-stats")
def match_player_stats(match_id: str) -> dict:
    """Métricas por jogador no jogo (fact_player_match_stats)."""
    df = _parquet("fact_player_match_stats.parquet")
    if df.empty:
        raise HTTPException(404, "player stats não disponíveis")
    rows = df[df["match_id"] == match_id]
    if rows.empty:
        raise HTTPException(404, "sem player stats para esse jogo")
    by_player: dict[str, list] = {}
    for r in rows.itertuples():
        pid = str(r.id_player)
        by_player.setdefault(pid, []).append({
            "metric": r.metric,
            "value": _safe_val(r.value),
            "is_official": _safe_val(r.is_official),
        })
    return {"match_id": match_id, "players": by_player}


# ── Power Ranking ──────────────────────────────────────────────────────────────

@router.get("/power-ranking")
def power_ranking(
    player_type: str | None = Query(None, description="outfield ou goalkeeper"),
    team: str | None = None,
) -> list[dict]:
    """Power Ranking FIFA por jogador."""
    df = _parquet("fact_power_ranking.parquet")
    if df.empty:
        raise HTTPException(404, "power ranking não disponível (rode fifa-coletar)")
    if player_type:
        df = df[df["player_type"] == player_type]
    if team:
        team_pt = traduzir_selecao(team)
        df = df[df["team_name"].isin([team, team_pt])]

    cols = [
        "id_player", "player_name", "id_team", "team_name", "player_type",
        "attacking_score", "attacking_rank", "attacking_rank_change",
        "defensive_score", "defensive_rank", "defensive_rank_change",
        "creativity_score", "creativity_rank", "creativity_rank_change",
    ]
    available = [c for c in cols if c in df.columns]
    return [{k: _safe_val(r[k]) for k in available} for r in df[available].to_dict("records")]


# ── Times: estatísticas agregadas ─────────────────────────────────────────────

@router.get("/teams/stats-by-game")
def teams_stats_by_game(
    metric: str = Query("XG", description="nome da métrica no fact_team_match_stats"),
) -> list[dict]:
    """Valor de uma métrica por time por jogo (para construir curvas de trajetória)."""
    stats = _parquet("fact_team_match_stats.parquet")
    matches = _parquet("dim_match.parquet")
    if stats.empty or matches.empty:
        return []

    filtered = stats[stats["metric"] == metric][["match_id", "id_team", "value"]].copy()
    if filtered.empty:
        return []

    merged = filtered.merge(
        matches[["match_id", "match_number", "home_team", "away_team",
                 "id_team_home", "id_team_away"]],
        on="match_id", how="left",
    )
    return [
        {
            "match_id": r["match_id"],
            "match_number": _safe_val(r["match_number"]),
            "id_team": r["id_team"],
            "value": _safe_val(r["value"]),
        }
        for r in merged.to_dict("records")
    ]


@router.get("/teams/available-metrics")
def available_metrics() -> list[str]:
    """Lista de métricas disponíveis no fact_team_match_stats."""
    df = _parquet("fact_team_match_stats.parquet")
    if df.empty or "metric" not in df.columns:
        return []
    return sorted(df["metric"].dropna().unique().tolist())


# ── Snapshots: scores históricos (jogo a jogo) ───────────────────────────────

@router.get("/snapshots/teams")
def team_snapshots(snapshot: int | None = Query(None, description="filtra um snapshot_jogo")) -> list[dict]:
    """Scores de seleção por snapshot (analytics/snapshot_timeline).

    Um registro por seleção por snapshot: score_geral + componentes, ranking,
    Elo, eixos de estilo e métricas acumuladas/por-jogo. É a base da aba Ranking
    Race e dos cards de Seleções."""
    df = _parquet("analytics/snapshot_timeline.parquet")
    if df.empty:
        raise HTTPException(404, "snapshots não disponíveis (rode fifa-coletar)")
    if snapshot is not None:
        df = df[df["snapshot_jogo"] == snapshot]
    return _records(df)


@router.get("/snapshots/players")
def player_snapshots(
    snapshot: int | None = Query(None, description="filtra um snapshot_jogo (default: último)"),
    team: str | None = None,
) -> list[dict]:
    """Scores/stats acumulados de jogador por snapshot (player_snapshot_timeline).

    São ~31k linhas no total; por padrão devolve só o último snapshot. Use
    `?snapshot=N` para um momento específico e `?team=` para filtrar a seleção."""
    df = _parquet("analytics/snapshots/player_snapshot_timeline.parquet")
    if df.empty:
        raise HTTPException(404, "player snapshots não disponíveis (rode fifa-coletar)")
    if snapshot is None:
        snapshot = int(df["snapshot_jogo"].max())
    df = df[df["snapshot_jogo"] == snapshot]
    if team:
        team_pt = traduzir_selecao(team)
        df = df[df["team"].isin([team, team_pt])]
    return _records(df)


@router.get("/weights")
def score_weights() -> dict:
    """Pesos fixos do score_geral (analytics/weights.json)."""
    path = GOLD_DIR / "analytics" / "weights.json"
    if not path.exists():
        raise HTTPException(404, "weights não disponíveis (rode fifa-coletar)")
    return json.loads(path.read_text(encoding="utf-8"))


# ── Análise (insights) — RESTRITO A ADMIN ─────────────────────────────────────

@router.get("/insights")
def insights(
    tipo: str = Query("diagnostica", description="tipo de análise (diagnostica, …)"),
    snapshot: int | None = Query(None, description="filtra um snapshot_jogo"),
    match_id: str | None = Query(None, description="filtra um jogo"),
    _admin: User = Depends(require_admin),
) -> list[dict]:
    """Achados de análise do `fact_insights` (camada de inferência da plataforma).

    Cada item carrega a evidência numérica que o sustenta. Acesso restrito a
    administradores — é a leitura analítica, não conteúdo público."""
    df = _parquet("analytics/insights/fact_insights.parquet")
    if df.empty:
        return []
    if tipo and "tipo_analise" in df.columns:
        df = df[df["tipo_analise"] == tipo]
    if snapshot is not None:
        df = df[df["snapshot"] == snapshot]
    if match_id:
        df = df[df["match_id"] == match_id]
    df = df.sort_values(["snapshot", "match_id"]) if "snapshot" in df.columns else df
    out = []
    for r in df.to_dict("records"):
        item = {k: _safe_val(v) for k, v in r.items()}
        # evidencia é JSON serializado no parquet — devolve como objeto.
        ev = item.get("evidencia")
        if isinstance(ev, str):
            try:
                item["evidencia"] = json.loads(ev)
            except (json.JSONDecodeError, TypeError):
                pass
        out.append(item)
    return out


# Métricas do confronto, lado a lado (alimenta o head-to-head da aba Analytics).
_COMPARISON_COLS = [
    "xg", "posse", "final_third_control", "threat",
    "chutes", "chutes_no_alvo", "chutes_dentro_area",
    "passes", "precisao_passes",
    "defesas_goleiro", "turnovers_forcados", "pressoes_defensivas",
    "faltas_cometidas", "amarelos", "vermelhos", "escanteios",
    "distancia_total_km", "sprints",
]


@router.get("/matches/{match_id}/comparison")
def match_comparison(match_id: str) -> dict:
    """Métricas-chave das duas seleções no jogo, lado a lado (de team_match_wide).

    Base do comparativo head-to-head da análise diagnóstica."""
    wide = _parquet("analytics/team_match_wide.parquet")
    dim = _parquet("dim_match.parquet")
    if wide.empty or dim.empty:
        raise HTTPException(404, "dados não disponíveis (rode fifa-coletar)")
    md = dim[dim["match_id"] == match_id]
    if md.empty:
        raise HTTPException(404, "jogo não encontrado")
    m = md.iloc[0]
    rows = wide[wide["match_id"] == match_id]
    cols = [c for c in _COMPARISON_COLS if c in rows.columns]

    def metrics_for(team: str) -> dict:
        r = rows[rows["team"] == team]
        if r.empty:
            return {}
        rec = r.iloc[0]
        return {c: _safe_val(rec[c]) for c in cols}

    return {
        "match_id": match_id,
        "home_team": _safe_val(m["home_team"]),
        "away_team": _safe_val(m["away_team"]),
        "home_score": _safe_val(m.get("home_score")),
        "away_score": _safe_val(m.get("away_score")),
        "home": metrics_for(str(m["home_team"])),
        "away": metrics_for(str(m["away_team"])),
    }


@router.get("/descriptive")
def descriptive_digest(
    snapshot: int | None = Query(None, description="panorama cumulativo até este snapshot (default: tudo)"),
    _admin: User = Depends(require_admin),
) -> dict:
    """Panorama agregado da fase (camada Descritiva), **cumulativo** até `snapshot`.

    Cresce conforme o slider avança: totais, tendência por rodada (as rodadas
    aparecem à medida que acontecem), líderes, recordes e surpresas. Admin."""
    from fifa_analytics.analytics.descriptive import build_digest

    dim = _parquet("dim_match.parquet")
    if dim.empty:
        return {}
    return build_digest(
        dim,
        _parquet("analytics/team_match_wide.parquet"),
        _parquet("analytics/snapshot_timeline.parquet"),
        _parquet("analytics/insights/fact_insights.parquet"),
        snapshot,
    )


@router.get("/insights/narrative")
def insight_narrative(
    tipo: str = Query("diagnostica", description="tipo de análise"),
    snapshot: int | None = Query(None, description="snapshot (default: o mais recente disponível)"),
    _admin: User = Depends(require_admin),
) -> dict:
    """Leitura analítica em prosa de um snapshot (a 'memória semântica').

    Escrita pela skill `analisar-snapshot` — Claude lê os achados estruturados +
    a narrativa do snapshot anterior e escreve a leitura. Arquivos em
    `data/gold/analytics/insights/narrative/{tipo}/snapshot_NNN.md`. Restrito a
    admin."""
    base = GOLD_DIR / "analytics" / "insights" / "narrative" / tipo
    if snapshot is None:
        # Mais recente disponível.
        existing = sorted(base.glob("snapshot_*.md")) if base.exists() else []
        if not existing:
            return {"tipo": tipo, "snapshot": None, "exists": False, "paragraphs": []}
        path = existing[-1]
        snapshot = int(path.stem.split("_")[-1])
    else:
        path = base / f"snapshot_{snapshot:03d}.md"

    if not path.exists():
        return {"tipo": tipo, "snapshot": snapshot, "exists": False, "paragraphs": []}

    text = path.read_text(encoding="utf-8")
    # Remove o marcador <!-- analise-manual --> e parágrafos vazios.
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("<!--")]
    body = "\n".join(lines).strip()
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    return {"tipo": tipo, "snapshot": snapshot, "exists": True, "paragraphs": paragraphs}


@router.get("/teams/{id_team}/stats")
def team_stats(id_team: str) -> dict:
    """Todas as métricas de um time, todos os jogos."""
    stats = _parquet("fact_team_match_stats.parquet")
    if stats.empty:
        raise HTTPException(404, "stats não disponíveis")
    rows = stats[stats["id_team"] == id_team]
    if rows.empty:
        raise HTTPException(404, f"sem stats para time {id_team}")
    by_match: dict[str, list] = {}
    for r in rows.itertuples():
        by_match.setdefault(r.match_id, []).append({
            "metric": r.metric,
            "value": _safe_val(r.value),
        })
    return {"id_team": id_team, "matches": by_match}
