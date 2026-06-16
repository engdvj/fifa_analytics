import pandas as pd


STANDINGS_COLUMN_LABELS = {
    "group": "grupo",
    "team": "selecao",
    "played": "jogos",
    "wins": "vitorias",
    "draws": "empates",
    "losses": "derrotas",
    "goals_for": "gols_pro",
    "goals_against": "gols_contra",
    "goal_difference": "saldo_gols",
    "points": "pontos",
    "source": "fonte",
}


def format_standings_table(standings: pd.DataFrame) -> str:
    if standings.empty:
        return ""
    display = standings.rename(columns=STANDINGS_COLUMN_LABELS)
    return display.to_markdown(index=False)


def build_standings_report(standings: pd.DataFrame, title: str = "Classificacao da Copa 2026") -> str:
    lines = [f"# {title}", ""]
    if standings.empty:
        lines.append("Nenhuma classificacao disponivel.")
        return "\n".join(lines) + "\n"

    for group, group_table in standings.groupby("group", dropna=False):
        lines.append(f"## Grupo {group}")
        lines.append("")
        lines.append(format_standings_table(group_table))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_daily_summary(matches: pd.DataFrame, match_date: str) -> str:
    day_matches = matches[matches["date"] == match_date]
    lines = [f"# Resumo diario - {match_date}", ""]
    if day_matches.empty:
        lines.append("Nenhum jogo encontrado para esta data.")
    for _, match in day_matches.iterrows():
        score = "x"
        if pd.notna(match.get("home_score")) and pd.notna(match.get("away_score")):
            score = f"{int(match['home_score'])} x {int(match['away_score'])}"
        lines.append(f"- {match['home_team']} {score} {match['away_team']} ({match.get('status', 'desconhecido')})")
    return "\n".join(lines) + "\n"


def build_missing_reports(status: pd.DataFrame) -> str:
    lines = ["# Pendencias de relatorios", ""]
    if status.empty:
        lines.append("Nenhuma partida encontrada.")
        return "\n".join(lines) + "\n"

    pending = status[status["report_status"] != "completo"].copy()
    if pending.empty:
        lines.append("Todos os relatorios estao completos.")
        return "\n".join(lines) + "\n"

    for _, match in pending.iterrows():
        missing = match.get("missing_sections") or []
        if not isinstance(missing, list):
            missing = []
        missing_text = ", ".join(missing) if missing else "sem manifesto/fragmentos"
        lines.append(
            f"- `{match['match_id']}`: {match['home_team']} x {match['away_team']} "
            f"({match['status']}) - faltando: {missing_text}"
        )
    return "\n".join(lines) + "\n"


def build_status_summary(status: pd.DataFrame) -> str:
    lines = ["# Status do torneio", ""]
    if status.empty:
        lines.append("Nenhuma partida encontrada.")
        return "\n".join(lines) + "\n"

    lines.append("## Partidas por status")
    lines.append("")
    lines.append(status["status"].value_counts(dropna=False).rename_axis("status").reset_index(name="partidas").to_markdown(index=False))
    lines.append("")
    lines.append("## Relatorios por status")
    lines.append("")
    lines.append(
        status["report_status"].value_counts(dropna=False).rename_axis("status_relatorio").reset_index(name="partidas").to_markdown(index=False)
    )
    lines.append("")
    lines.append("## Qualidade dos dados")
    lines.append("")
    lines.append(
        status["data_quality_status"]
        .value_counts(dropna=False)
        .rename_axis("qualidade_dados")
        .reset_index(name="partidas")
        .to_markdown(index=False)
    )
    return "\n".join(lines) + "\n"
