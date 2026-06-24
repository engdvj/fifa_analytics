"""Geração de relatórios Markdown por jogo — fonte única FIFA.

Substitui o antigo `canonical_reports` (reconciliação multi-fonte). Lê o gold
FIFA e escreve os fragmentos por jogo; a montagem final reusa o
`reporting.build_report.build_match_report` (genérico, lê fragmentos +
`config/report_sections.yaml`).

Fontes lidas (todas geradas por `fifa/pipeline.py`):
  data/gold/dim_match.parquet
  data/gold/analytics/team_match_wide.parquet
  data/gold/fact_lineups.parquet
  data/gold/fact_events.parquet
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from fifa_analytics.fifa.player_pivot import _display_name
from fifa_analytics.paths import FINAL_REPORTS_DIR, GOLD_DIR, MANIFESTS_DIR
from fifa_analytics.reporting.build_report import build_match_report
from fifa_analytics.reporting.fragments import render_template, write_fragment
from fifa_analytics.utils.io import read_dataframe
from fifa_analytics.utils.logging import get_logger
from fifa_analytics.utils.time import utc_now_iso

logger = get_logger(__name__)

# Métricas comparativas exibidas na seção "Estatísticas comparativas".
# (rótulo, coluna em team_match_wide, é percentual 0-1?)
_STAT_ROWS = [
    ("Gols", "gols", False),
    ("xG", "xg", False),
    ("Finalizações", "chutes", False),
    ("No alvo", "chutes_no_alvo", False),
    ("Posse", "posse", True),
    ("Passes", "passes", False),
    ("Precisão de passe", "precisao_passes", True),
    ("Escanteios", "escanteios", False),
    ("Faltas", "faltas_cometidas", False),
]

_POS_ORDER = {"G": 0, "D": 1, "M": 2, "F": 3}


def _fmt(value, pct: bool) -> str:
    if value is None or pd.isna(value):
        return "—"
    if pct:
        v = float(value) * 100 if float(value) <= 1.0 else float(value)
        return f"{v:.0f}%"
    f = float(value)
    return f"{f:.2f}".rstrip("0").rstrip(".") if f % 1 else f"{int(f)}"


def _metadata_fragment(match: dict) -> str:
    return render_template(
        "fragments/00_metadata.md.j2",
        {
            "match_id": match["match_id"],
            "generated_at": utc_now_iso(),
            "status": match.get("status") or "desconhecido",
            "group": match.get("group") or "",
            "date": match.get("date_utc") or "",
            "stadium": match.get("stadium") or "",
            "attendance": match.get("attendance") or "",
            "sources": "fifa",
            "data_quality_status": "ok",
        },
    )


def _summary_fragment(match: dict) -> str:
    home, away = match.get("home_team", "?"), match.get("away_team", "?")
    hs, as_ = match.get("home_score"), match.get("away_score")
    stage = match.get("stage") or ""
    group = match.get("group") or ""
    date = str(match.get("date_utc") or "")[:10]
    if hs is not None and not pd.isna(hs):
        header = f"# {home} {int(hs)}–{int(as_)} {away}"
        # pênaltis, se houver
        hp, ap = match.get("home_penalty"), match.get("away_penalty")
        if hp is not None and not pd.isna(hp) and (hp or ap):
            header += f" *(pên. {int(hp)}–{int(ap)})*"
    else:
        header = f"# {home} x {away}\n\n*Placar ainda indisponível.*"
    ctx = " · ".join(p for p in (stage, group, date) if p)
    body = f"{header}\n\n*{ctx}*" if ctx else header
    if match.get("status") and match["status"] != "finalizado":
        body += f"\n\n*Status: {match['status']}*"
    return body + "\n"


def _story_fragment(match: dict) -> str:
    """Template automático da narrativa. O marcador `<!-- narrativa-manual -->`
    (escrito pela skill atualizar-jogo) protege versões manuais — por isso o
    write_fragment usa skip_if_manual=True para esta seção."""
    home, away = match.get("home_team", "?"), match.get("away_team", "?")
    return (
        "## A história do jogo\n\n"
        f"*Narrativa pendente para {home} x {away}. "
        "Gere com a skill `atualizar-jogo` (será reescrita como prosa a partir dos dados).*\n"
    )


def _lineups_fragment(match_id: str, lineups: pd.DataFrame, match: dict) -> str:
    if lineups.empty:
        return "## Escalações titulares\n\nSeção pendente: escalações ainda não disponíveis.\n"
    ml = lineups[(lineups["match_id"] == match_id) & (lineups["is_starter"])]
    if ml.empty:
        return "## Escalações titulares\n\nSeção pendente: escalações ainda não disponíveis.\n"

    def _col(side: str, team_name: str) -> str:
        sub = ml[ml["team_side"] == side].copy()
        if sub.empty:
            return ""
        sub["_o"] = sub["position"].map(lambda p: _POS_ORDER.get(p, 9))
        sub = sub.sort_values(["_o", "shirt_number"])
        lines = [f"**{team_name}**", ""]
        for _, r in sub.iterrows():
            num = "" if pd.isna(r.get("shirt_number")) else f"{int(r['shirt_number'])}. "
            pos = f" ({r['position']})" if r.get("position") else ""
            lines.append(f"- {num}{_display_name(r['player_name'])}{pos}")
        return "\n".join(lines)

    home_col = _col("home", match.get("home_team", "Casa"))
    away_col = _col("away", match.get("away_team", "Visitante"))
    return "## Escalações titulares\n\n" + "\n\n".join(c for c in (home_col, away_col) if c) + "\n"


def _team_stats_fragment(match_id: str, wide: pd.DataFrame, match: dict) -> str:
    if wide.empty:
        return "## Estatísticas comparativas\n\nSeção pendente: estatísticas ainda não disponíveis.\n"
    mw = wide[wide["match_id"] == match_id]
    if mw.empty:
        return "## Estatísticas comparativas\n\nSeção pendente: estatísticas ainda não disponíveis.\n"
    home, away = match.get("home_team"), match.get("away_team")
    by_team = {r["team"]: r for _, r in mw.iterrows()}
    hr, ar = by_team.get(home), by_team.get(away)
    if hr is None or ar is None:  # fallback: usa as duas linhas na ordem dada
        rows = list(mw.itertuples(index=False))
        if len(rows) < 2:
            return "## Estatísticas comparativas\n\nSeção pendente: estatísticas incompletas.\n"
        hr = mw.iloc[0]; ar = mw.iloc[1]
        home, away = hr["team"], ar["team"]
    lines = ["## Estatísticas comparativas", "", f"| {home} | Métrica | {away} |", "|---:|:---:|:---|"]
    for label, col, pct in _STAT_ROWS:
        if col not in mw.columns:
            continue
        lines.append(f"| {_fmt(hr.get(col), pct)} | {label} | {_fmt(ar.get(col), pct)} |")
    return "\n".join(lines) + "\n"


def _filter_matches(matches: pd.DataFrame, status: str) -> pd.DataFrame:
    if status == "todos":
        return matches.copy()
    return matches[matches["status"] == status].copy()


def write_fifa_fragments(match: dict, wide: pd.DataFrame, lineups: pd.DataFrame) -> None:
    mid = match["match_id"]
    write_fragment(mid, "00_metadata", _metadata_fragment(match))
    write_fragment(mid, "01_match_summary", _summary_fragment(match))
    write_fragment(mid, "01b_story", _story_fragment(match), skip_if_manual=True)
    write_fragment(mid, "03_lineups", _lineups_fragment(mid, lineups, match))
    write_fragment(mid, "05_team_stats", _team_stats_fragment(mid, wide, match))


def run_fifa_reports(status: str = "finalizado") -> dict[str, object]:
    """Gera os relatórios por jogo a partir do gold FIFA."""
    matches = read_dataframe(GOLD_DIR / "dim_match.parquet")
    wide_path = GOLD_DIR / "analytics" / "team_match_wide.parquet"
    lineups_path = GOLD_DIR / "fact_lineups.parquet"
    wide = read_dataframe(wide_path) if wide_path.exists() else pd.DataFrame()
    lineups = read_dataframe(lineups_path) if lineups_path.exists() else pd.DataFrame()

    selected = _filter_matches(matches, status)
    results = []
    for _, row in selected.iterrows():
        match = row.to_dict()
        write_fifa_fragments(match, wide, lineups)
        results.append(
            build_match_report(
                match["match_id"],
                data_quality_status="ok",
                extra_manifest={"sources_used": ["fifa"], "primary_source": "fifa"},
                report_filename=match["match_id"],
            )
        )

    return {
        "fonte": "fifa",
        "status_processado": status,
        "partidas_encontradas": int(len(selected)),
        "relatorios_gerados": len(results),
        "primeiro_relatorio": str(results[0]["report_path"]) if results else None,
    }


def rebuild_match_report(match_id: str) -> dict[str, object]:
    """Remonta o relatório final de um jogo a partir dos fragmentos atuais em
    reports/fragments/{match_id}/, sem recalcular nada — usado após editar um
    fragmento manualmente (ex.: 01b_story.md reescrito como narrativa)."""
    manifest_path = MANIFESTS_DIR / f"{match_id}.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Manifest não encontrado para {match_id}: rode 'fifa-analytics relatorios-basicos' primeiro."
        )
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    final_report_path = Path(manifest["final_report_path"])
    report_subdir = str(final_report_path.parent.relative_to(FINAL_REPORTS_DIR))
    return build_match_report(
        match_id,
        data_quality_status=manifest.get("data_quality_status", "desconhecido"),
        extra_manifest={
            "sources_used": manifest.get("sources_used"),
            "primary_source": manifest.get("primary_source"),
        },
        report_subdir="" if report_subdir == "." else report_subdir,
        report_filename=final_report_path.stem,
    )
