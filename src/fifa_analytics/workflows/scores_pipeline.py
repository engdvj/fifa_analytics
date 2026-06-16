from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fifa_analytics.analytics.scores import (
    build_player_match_features,
    build_team_match_features,
    build_team_recent_form,
    build_team_scores,
)
from fifa_analytics.paths import GOLD_DIR, MANIFESTS_DIR, REPORTS_DIR
from fifa_analytics.utils.io import ensure_dir, read_dataframe, write_dataframe
from fifa_analytics.utils.text import position_label, slugify
from fifa_analytics.utils.time import utc_now_iso


ANALYTICS_DIR = GOLD_DIR / "analytics"
TEAM_SCORE_HISTORY_PATH = ANALYTICS_DIR / "team_score_history.parquet"
_HISTORY_COLUMNS = [
    "team", "jogos", "score_geral", "score_resultado", "score_ataque",
    "score_defesa", "score_eficiencia", "score_controle", "recorded_at",
]
TEAM_REPORTS_DIR = REPORTS_DIR / "teams"
PLAYER_REPORTS_DIR = REPORTS_DIR / "players"
RANKINGS_DIR = REPORTS_DIR / "rankings"
TEAM_RANKINGS_DIR = RANKINGS_DIR / "selecoes"

PROFILE_LABELS = {"goleiro": "Goleiro", "defensor": "Defensor", "meio": "Meia", "atacante": "Atacante"}
# Colunas relevantes por perfil — goleiro nao marca gol nem chuta a gol como
# metrica relevante, atacante nao defende. Cada perfil mostra so o que importa.
PROFILE_STATS: dict[str, list[str]] = {
    "goleiro": ["saves", "goals_conceded", "yellow_cards", "red_cards"],
    "defensor": ["goals", "assists", "fouls_committed", "fouls_drawn", "yellow_cards", "red_cards"],
    "meio": ["goals", "assists", "shots_on_target", "shots_off_target", "fouls_drawn", "yellow_cards", "red_cards"],
    "atacante": ["goals", "assists", "shots_on_target", "shots_off_target", "yellow_cards", "red_cards"],
}
STAT_COL_LABELS = {
    "goals": "gols", "assists": "assist", "shots_on_target": "no_alvo",
    "shots_off_target": "fora_do_alvo", "saves": "defesas", "goals_conceded": "gols_sofridos",
    "fouls_committed": "faltas_com", "fouls_drawn": "faltas_sof",
    "yellow_cards": "amarelos", "red_cards": "vermelhos",
}
TEAM_RANKINGS = [
    ("geral", "score_geral", "nota geral"),
    ("resultado", "score_resultado", "resultado"),
    ("ataque", "score_ataque", "ataque"),
    ("defesa", "score_defesa", "defesa"),
    ("eficiencia", "score_eficiencia", "eficiencia"),
    ("controle", "score_controle", "controle"),
    ("forma", "forma_score", "forma recente"),
]


def run_scores_pipeline() -> dict[str, Any]:
    matches = _read_optional(GOLD_DIR / "dim_match" / "canonical_matches.parquet")
    if matches.empty:
        raise FileNotFoundError("Indice canonico ausente. Rode `python -m fifa_analytics indice-canonico` primeiro.")

    team_stats = _read_optional(GOLD_DIR / "fact_team_match_stats" / "canonical_team_stats.parquet")
    player_stats = _read_optional(GOLD_DIR / "fact_player_match_stats" / "canonical_player_stats.parquet")
    lineups = _read_optional(GOLD_DIR / "lineups" / "canonical_lineups.parquet")
    rosters = _read_optional(GOLD_DIR / "rosters" / "espn_rosters.parquet")

    team_match_features = build_team_match_features(matches, team_stats)
    team_scores = build_team_scores(team_match_features)
    team_recent_form = build_team_recent_form(team_match_features, n=3)
    player_match_features = build_player_match_features(player_stats, lineups, rosters)

    team_match_features_path = write_dataframe(ANALYTICS_DIR / "team_match_features.parquet", team_match_features)
    team_scores_path = write_dataframe(ANALYTICS_DIR / "team_scores.parquet", team_scores)
    team_recent_form_path = write_dataframe(ANALYTICS_DIR / "team_recent_form.parquet", team_recent_form)
    player_match_features_path = write_dataframe(ANALYTICS_DIR / "player_match_features.parquet", player_match_features)
    team_score_history = _record_team_score_history(team_scores)

    team_report_paths = write_team_reports(team_scores, team_match_features, player_match_features, team_recent_form, team_score_history)
    player_report_paths = write_player_reports(player_match_features)
    team_index_path = write_team_index(team_scores)
    rankings_index_path = write_rankings_index()
    team_ranking_paths = write_team_rankings(team_scores)

    return {
        "team_match_features_path": team_match_features_path,
        "team_scores_path": team_scores_path,
        "team_recent_form_path": team_recent_form_path,
        "player_match_features_path": player_match_features_path,
        "team_reports_dir": TEAM_REPORTS_DIR,
        "player_reports_dir": PLAYER_REPORTS_DIR,
        "team_index_path": team_index_path,
        "rankings_index_path": rankings_index_path,
        "team_ranking_path": team_ranking_paths[0] if team_ranking_paths else None,
        "team_rankings": len(team_ranking_paths),
        "teams_ranked": len(team_scores),
        "team_reports": len(team_report_paths),
        "player_reports": len(player_report_paths),
    }


def write_team_reports(
    team_scores: pd.DataFrame,
    team_match_features: pd.DataFrame,
    player_match_features: pd.DataFrame,
    team_recent_form: pd.DataFrame | None = None,
    team_score_history: pd.DataFrame | None = None,
) -> list[Path]:
    ensure_dir(TEAM_REPORTS_DIR)
    paths = []
    total_teams = len(team_scores)
    team_slug_by_name = dict(zip(team_scores["team"], team_scores["team_slug"]))
    form_by_team: dict[str, pd.Series] = {}
    if team_recent_form is not None and not team_recent_form.empty:
        for _, row in team_recent_form.iterrows():
            form_by_team[str(row["team"])] = row
    for _, team in team_scores.iterrows():
        matches = team_match_features[team_match_features["team"] == team["team"]].sort_values("date")
        player_events = player_match_features[player_match_features["team"] == team["team"]] if not player_match_features.empty else pd.DataFrame()
        recent = form_by_team.get(str(team["team"]))
        history = (
            team_score_history[team_score_history["team"] == team["team"]].sort_values("jogos")
            if team_score_history is not None and not team_score_history.empty
            else pd.DataFrame()
        )
        path = TEAM_REPORTS_DIR / f"{team['team_slug']}.md"
        path.write_text(_render_team_report(team, matches, player_events, total_teams, team_slug_by_name, recent, history), encoding="utf-8")
        paths.append(path)
    return paths


def _record_team_score_history(team_scores: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta um snapshot do score de cada selecao ao historico acumulado,
    usando 'jogos' (nao a data de geracao) como chave de versao — assim rodar
    o pipeline varias vezes no mesmo dia nao duplica entradas, e cada rodada
    de jogos disputados gera exatamente um ponto na evolucao."""
    if team_scores.empty:
        return _read_optional(TEAM_SCORE_HISTORY_PATH)

    snapshot = team_scores[[c for c in _HISTORY_COLUMNS if c != "recorded_at" and c in team_scores.columns]].copy()
    snapshot["recorded_at"] = utc_now_iso()

    history = _read_optional(TEAM_SCORE_HISTORY_PATH)
    if not history.empty:
        combined = pd.concat([history, snapshot], ignore_index=True)
        combined = combined.drop_duplicates(subset=["team", "jogos"], keep="last")
    else:
        combined = snapshot

    write_dataframe(TEAM_SCORE_HISTORY_PATH, combined)
    return combined


def write_team_index(team_scores: pd.DataFrame) -> Path:
    ensure_dir(TEAM_REPORTS_DIR)
    path = TEAM_REPORTS_DIR / "index.md"
    path.write_text(_render_team_ranking(team_scores, "geral", "score_geral", "nota geral"), encoding="utf-8")
    return path


def write_rankings_index() -> Path:
    ensure_dir(RANKINGS_DIR)
    path = RANKINGS_DIR / "index.md"
    content = f"""# Rankings

Atualizado em `{utc_now_iso()}`.

- [[reports/rankings/selecoes/index\\|Rankings de selecoes]]
"""
    path.write_text(content, encoding="utf-8")
    return path


def write_team_rankings(team_scores: pd.DataFrame) -> list[Path]:
    ensure_dir(TEAM_RANKINGS_DIR)
    paths = []
    index_path = TEAM_RANKINGS_DIR / "index.md"
    index_path.write_text(_render_team_rankings_index(team_scores), encoding="utf-8")
    paths.append(index_path)
    for slug, metric, title in TEAM_RANKINGS:
        path = TEAM_RANKINGS_DIR / f"{slug}.md"
        path.write_text(_render_team_ranking(team_scores, slug, metric, title), encoding="utf-8")
        paths.append(path)
    return paths


def _render_team_rankings_index(team_scores: pd.DataFrame) -> str:
    links = "\n".join(f"- [[reports/rankings/selecoes/{slug}\\|{title.title()}]]" for slug, _, title in TEAM_RANKINGS)
    return f"# Rankings de selecoes\n\nAtualizado em `{utc_now_iso()}`.\n\n{links}\n\n{_render_team_ranking(team_scores, 'geral', 'score_geral', 'nota geral')}"


def _render_team_ranking(team_scores: pd.DataFrame, ranking_slug: str, metric: str, title: str) -> str:
    # Para forma recente, a coluna pode não existir se o pipeline não rodou ainda
    if metric not in team_scores.columns:
        return f"# Ranking de selecoes - {title.title()}\n\nDados de `{metric}` ainda nao disponiveis.\n"
    ranked = team_scores.sort_values([metric, "score_geral", "points", "saldo_gols"], ascending=[False, False, False, False]).reset_index(drop=True)
    ranked["rank_metrica"] = ranked.index + 1
    score_columns = ["score_geral", "score_resultado", "score_ataque", "score_defesa", "score_eficiencia", "score_controle"]
    if "forma_score" in ranked.columns:
        score_columns.append("forma_score")
    ordered_columns = [
        "rank_metrica",
        "team",
        metric,
        *[column for column in score_columns if column != metric and column in ranked.columns],
        "nivel_evidencia",
        "jogos",
        "points",
        "saldo_gols",
    ]
    display = ranked[ordered_columns].copy()
    display["team"] = display.apply(lambda row: _team_link(row["team"], row.get("team_slug")), axis=1)
    display = display.rename(columns=_team_ranking_labels(metric, title))
    nav = _team_rankings_nav(ranking_slug)
    return f"# Ranking de selecoes - {title.title()}\n\nAtualizado em `{utc_now_iso()}`.\n\n{nav}\n\n{_team_score_explanation()}\n\n{display.to_markdown(index=False)}\n"


def write_player_reports(player_match_features: pd.DataFrame) -> list[Path]:
    if player_match_features.empty:
        return []
    paths = []
    for player_slug, group in player_match_features.groupby("player_slug", sort=False):
        team_slug = slugify(group.iloc[0].get("team", ""))
        team_dir = ensure_dir(PLAYER_REPORTS_DIR / team_slug)
        # slug do arquivo = apenas o nome do jogador (sem sufixo _selecao)
        name_slug = player_slug[: -(len(team_slug) + 1)] if player_slug.endswith(f"_{team_slug}") else player_slug
        path = team_dir / f"{name_slug}.md"
        path.write_text(_render_player_report(group), encoding="utf-8")
        paths.append(path)
    return paths


def _render_player_report(matches: pd.DataFrame) -> str:
    row = matches.iloc[0]
    player_name = row.get("player_name", "")
    team = row.get("team", "")
    position = position_label(row.get("position", ""))
    perfil = row.get("perfil", "")
    perfil_label = PROFILE_LABELS.get(perfil, perfil.title() if perfil else "")

    # Colunas relevantes para o perfil deste jogador — goleiro nunca mostra
    # "gols", atacante nunca mostra "defesas".
    profile_cols = PROFILE_STATS.get(perfil, [])
    avail_stats = [c for c in profile_cols if c in matches.columns]
    totals = matches[avail_stats].apply(pd.to_numeric, errors="coerce").fillna(0).sum() if avail_stats else pd.Series(dtype=float)

    summary_rows = [
        ["selecao", _team_link(team, slugify(team))],
        ["posicao", position],
        ["perfil", perfil_label],
        ["jogos", int(matches["appearances"].fillna(0).sum()) if "appearances" in matches.columns else len(matches)],
    ]
    for col in avail_stats:
        if totals.get(col, 0) > 0:
            summary_rows.append([STAT_COL_LABELS.get(col, col), int(totals[col])])

    summary = _markdown_table(summary_rows, ["metrica", "valor"])

    # Tabela por jogo — mesmas colunas do perfil, só as que tiveram algum evento
    match_cols = ["match_id"] + avail_stats
    avail_match = [c for c in match_cols if c in matches.columns]
    match_display = matches.sort_values("match_id")[avail_match].copy()
    if "match_id" in match_display.columns:
        match_display["match_id"] = match_display["match_id"].apply(_match_link)
    event_cols_match = [c for c in avail_match if c != "match_id"]
    has_any = match_display[event_cols_match].apply(pd.to_numeric, errors="coerce").fillna(0).gt(0).any() if event_cols_match else pd.Series(dtype=bool)
    keep_cols = ["match_id"] + [c for c in event_cols_match if has_any.get(c, False)]
    match_display = match_display[keep_cols].rename(columns={"match_id": "jogo", **STAT_COL_LABELS})
    match_table = match_display.fillna(0).to_markdown(index=False)

    return f"""<!--
player: {player_name}
team: {team}
perfil: {perfil}
generated_at: {utc_now_iso()}
-->

# {player_name}

{_team_link(team, slugify(team))}

## Resumo no torneio

{summary}

## Por jogo

{match_table}
"""


_COMPONENT_EXPLANATIONS = {
    "Resultado": "aproveitamento real de pontos (40% da nota geral)",
    "Ataque": "gols e chutes no alvo por jogo — mede qualidade, nao volume bruto (20%)",
    "Defesa": "gols sofridos, chutes no alvo sofridos e jogos sem tomar gol (25%)",
    "Eficiencia": "conversao de chutes em gol e chutes no alvo por chute (10%)",
    "Controle": "posse, passes e precisao — estilo de jogo, peso baixo (5%)",
}


def _render_team_report(
    team: pd.Series,
    matches: pd.DataFrame,
    player_events: pd.DataFrame,
    total_teams: int,
    team_slug_by_name: dict[str, str],
    recent: pd.Series | None = None,
    history: pd.DataFrame | None = None,
) -> str:
    generated_at = utc_now_iso()
    jogos = int(team.get("jogos", 0) or 0)

    # Cada componente aparece com nota + explicacao do calculo juntos — sem
    # repetir a mesma explicacao numa secao "Como ler" e numa "Auditoria"
    # separadas (eram redundantes e o usuario apontou a confusao).
    components = _markdown_table(
        [
            ["Resultado", team.get("score_resultado", 0), _COMPONENT_EXPLANATIONS["Resultado"]],
            ["Ataque", team.get("score_ataque", 0), _COMPONENT_EXPLANATIONS["Ataque"]],
            ["Defesa", team.get("score_defesa", 0), _COMPONENT_EXPLANATIONS["Defesa"]],
            ["Eficiencia", team.get("score_eficiencia", 0), _COMPONENT_EXPLANATIONS["Eficiencia"]],
            ["Controle", team.get("score_controle", 0), _COMPONENT_EXPLANATIONS["Controle"]],
        ],
        ["componente", "nota", "como e calculado"],
    )

    evolution_section = _team_score_evolution(history)

    gols_label = "gols marcados"
    gols_value: Any = team.get("gols_pro", 0)
    if jogos > 1:
        # mediana so agrega informacao a partir de 2+ jogos — com 1 jogo
        # ela e identica ao total e mostrar os dois e redundante.
        gols_label = "gols marcados (mediana por jogo)"
        gols_value = f"{team.get('gols_pro', 0)} ({_format_value(team.get('mediana_gols_pro'))})"
    summary_rows = [
        ["jogos disputados", jogos],
        ["pontos", team.get("points", 0)],
        ["saldo de gols", team.get("saldo_gols", 0)],
        [gols_label, gols_value],
        ["gols sofridos", team.get("gols_contra", 0)],
        ["aproveitamento de pontos", _percent(team.get("aproveitamento"))],
    ]
    consistency_label = _consistency_label(team.get("consistencia_resultado"))
    if consistency_label:
        summary_rows.append(["consistencia de resultado", consistency_label])
    trend_label = _trend_label(team.get("tendencia_resultado"))
    if trend_label:
        summary_rows.append(["tendencia", trend_label])
    forma_n = int(recent.get("forma_n", 3)) if recent is not None else 3
    if recent is not None and jogos > forma_n:
        # so mostra "forma recente" separada quando ela de fato recorta uma
        # janela menor que o total de jogos — com jogos <= forma_n os dois
        # numeros sao identicos e mostrar os dois e redundante. So passa a
        # divergir no mata-mata, quando ha mais de 3 jogos no torneio.
        summary_rows.append([f"forma nos ultimos {forma_n} jogos", f"{recent.get('forma_sequencia', '')} ({_percent(recent.get('forma_aproveitamento'))})"])
    summary = _markdown_table(summary_rows, ["metrica", "valor"])

    team_slug = slugify(team.get("team", ""))
    match_table = _team_matches_table(matches, team_slug_by_name)
    players_section = _team_players_by_position(player_events, team_slug)
    return f"""<!--
team: {team.get('team')}
generated_at: {generated_at}
jogos: {jogos}
nivel_evidencia: {team.get('nivel_evidencia', '')}
-->

# {team.get('team')}

[[reports/rankings/selecoes/index|Ranking de selecoes]]

## Nota geral: {_format_score(team.get('score_geral'))}/100

Ranking: **{_format_value(team.get('ranking_score_geral'))} de {total_teams}** selecoes — nivel de evidencia **{team.get('nivel_evidencia', '')}** ({jogos} jogo{'s' if jogos != 1 else ''} disputado{'s' if jogos != 1 else ''} dos 3 da fase de grupos; jogos extras no mata-mata so aumentam a confianca).

A nota geral combina os cinco componentes abaixo por media ponderada (pesos entre parenteses), calculados via z-score entre as selecoes do torneio — isso preserva a distancia real de desempenho, nao so o ranking ordinal.

{components}
{evolution_section}
## Resumo acumulado

{summary}

## Jogos

{match_table}

## Jogadores

{players_section}
"""


def _team_score_evolution(history: pd.DataFrame | None) -> str:
    """Mostra como a nota geral e os componentes mudaram a cada jogo disputado.
    So aparece quando ha pelo menos 2 pontos no historico — com 1 jogo nao ha
    'evolucao' para mostrar, e a secao ficaria so repetindo o que ja esta
    na tabela de componentes acima."""
    if history is None or history.empty or len(history) < 2:
        return ""
    rows = []
    prev_geral = None
    for _, row in history.iterrows():
        jogos = int(row.get("jogos", 0))
        geral = row.get("score_geral", 0)
        delta = "" if prev_geral is None else f"{geral - prev_geral:+.1f}"
        rows.append([jogos, geral, delta, row.get("score_resultado", 0), row.get("score_ataque", 0), row.get("score_defesa", 0)])
        prev_geral = geral
    table = _markdown_table(rows, ["jogos", "nota_geral", "variacao", "resultado", "ataque", "defesa"])
    return f"""
## Evolucao da nota por jogo

{table}
"""


def _team_matches_table(matches: pd.DataFrame, team_slug_by_name: dict[str, str]) -> str:
    if matches.empty:
        return "Nenhum jogo finalizado encontrado."
    display = matches[
        [
            "match_id",
            "date",
            "opponent",
            "result",
            "goals_for",
            "goals_against",
            "shots",
            "shots_on_target",
            "possession",
        ]
    ].copy()
    display["match_id"] = display["match_id"].apply(_match_link)
    display["opponent"] = display["opponent"].apply(lambda team: _team_link(team, team_slug_by_name.get(team)))
    display = display.rename(
        columns={
            "match_id": "jogo",
            "date": "data",
            "opponent": "adversario",
            "result": "resultado",
            "goals_for": "gols_pro",
            "goals_against": "gols_contra",
            "shots": "chutes",
            "shots_on_target": "no_alvo",
            "possession": "posse",
        }
    )
    return display.fillna("").to_markdown(index=False)


def _team_players_by_position(player_events: pd.DataFrame, team_slug: str) -> str:
    """Lista todos os jogadores do time agrupados por posição, com links e métricas
    relevantes para cada perfil — goleiros precisam de gols sofridos/defesas, meias e
    atacantes precisam de chutes fora do alvo para contextualizar o volume ofensivo."""
    if player_events.empty:
        return "Sem dados de escalação disponíveis."

    PROFILE_ORDER = ["goleiro", "defensor", "meio", "atacante"]
    SECTION_LABELS = {"goleiro": "Goleiros", "defensor": "Defensores", "meio": "Meias", "atacante": "Atacantes"}
    ALL_STAT_COLS = sorted({c for cols in PROFILE_STATS.values() for c in cols})

    # Agrega por jogador somando todas as partidas
    agg = {c: "sum" for c in ALL_STAT_COLS if c in player_events.columns}
    agg["perfil"] = "first"
    agg["player_slug"] = "first"
    agg["match_id"] = "nunique"
    available_agg = {c: f for c, f in agg.items() if c in player_events.columns or c == "match_id"}
    grouped = (
        player_events.groupby("player_name", dropna=False)
        .agg(available_agg)
        .reset_index()
        .rename(columns={"match_id": "jogos"})
    )

    stat_cols_available = [c for c in ALL_STAT_COLS if c in grouped.columns]
    for c in stat_cols_available:
        grouped[c] = pd.to_numeric(grouped[c], errors="coerce").fillna(0).astype(int)

    sections = []
    for profile in PROFILE_ORDER:
        pool = grouped[grouped["perfil"] == profile].copy()
        if pool.empty:
            continue

        # Ordena: titulares (mais jogos) primeiro, depois por gols/assists/saves
        sort_by = ["jogos"] + [c for c in ["goals", "assists", "saves", "shots_on_target"] if c in pool.columns]
        pool = pool.sort_values(sort_by, ascending=False)

        profile_cols = [c for c in PROFILE_STATS[profile] if c in stat_cols_available]
        rows = []
        for _, row in pool.iterrows():
            name = row["player_name"]
            slug = row.get("player_slug", "")
            # player_slug tem formato nome_time — extrai só o nome para o path
            name_slug = slug[: -(len(team_slug) + 1)] if slug and slug.endswith(f"_{team_slug}") else slugify(name)
            link = f"[[reports/players/{team_slug}/{name_slug}\\|{name}]]"
            stats = [str(int(row[c])) for c in profile_cols]
            rows.append([link] + stats)

        col_headers = ["jogador"] + [STAT_COL_LABELS.get(c, c) for c in profile_cols]
        table = pd.DataFrame(rows, columns=col_headers).to_markdown(index=False)
        sections.append(f"### {SECTION_LABELS[profile]}\n\n{table}")

    return "\n\n".join(sections) if sections else "Sem dados de escalação disponíveis."


def _markdown_table(rows: list[list[Any]], columns: list[str]) -> str:
    return pd.DataFrame(rows, columns=columns).to_markdown(index=False)


def _team_rankings_nav(active_slug: str) -> str:
    links = []
    for slug, _, title in TEAM_RANKINGS:
        label = title.title()
        if slug == active_slug:
            label = f"{label} (atual)"
        links.append(f"[[reports/rankings/selecoes/{slug}\\|{label}]]")
    return " · ".join(links)


def _team_ranking_labels(metric: str, title: str) -> dict[str, str]:
    labels = {
        "rank_metrica": "rank",
        "team": "selecao",
        "score_geral": "nota_geral",
        "score_resultado": "resultado",
        "score_ataque": "ataque",
        "score_defesa": "defesa",
        "score_eficiencia": "eficiencia",
        "score_controle": "controle",
        "forma_score": "forma",
        "nivel_evidencia": "evidencia",
        "points": "pontos",
    }
    labels[metric] = title.replace(" ", "_")
    return labels


def _team_score_explanation() -> str:
    return """## Como ler a nota

- **Nota geral**: nota de 0 a 100 = resultado (40%) + processo (60%). Componentes calculados via z-score, preservando distancia absoluta entre selecoes.
- **Resultado** (peso 40%): aproveitamento real de pontos. Quem vence mais jogos tem nota mais alta independente do estilo.
- **Ataque** (peso 20%): gols e chutes no alvo por jogo. Sem chutes totais — mede qualidade, nao volume bruto.
- **Defesa** (peso 25%): gols sofridos, chutes no alvo sofridos e jogos sem tomar gol.
- **Eficiencia** (peso 10%): conversao de chutes em gol e chutes no alvo por chute. Distinto de ataque: ataque mede producao, eficiencia mede aproveitamento.
- **Controle** (peso 5%): posse, passes e precisao. Peso baixo — estilo de jogo nao e determinante de qualidade.
- **Forma recente**: aproveitamento dos ultimos 5 jogos, independente da nota geral acumulada.
- **Evidencia**: estabilidade da nota (`baixa`, `media`, `alta`). Aumenta com o numero de jogos jogados."""


def _format_value(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_score(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.1f}"


def _obsidian_link(target: str, label: Any) -> str:
    return f"[[{target}\\|{label}]]"


def _team_link(team: Any, slug: Any = None) -> str:
    if pd.isna(team):
        return ""
    team_name = str(team)
    team_slug = str(slug) if slug and not pd.isna(slug) else slugify(team_name)
    return _obsidian_link(f"reports/teams/{team_slug}", team_name)


@lru_cache(maxsize=None)
def _match_report_relpath(match_id: str) -> str:
    """Resolve o caminho real do relatorio final via manifest — necessario pois
    os relatorios ficam em subdiretorios por rodada/fase, nao em reports/final/{id}."""
    manifest_path = MANIFESTS_DIR / f"{match_id}.yaml"
    if not manifest_path.exists():
        return f"reports/final/{match_id}"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    report_path = manifest.get("final_report_path")
    if not report_path:
        return f"reports/final/{match_id}"
    relative = Path(report_path).relative_to(REPORTS_DIR.parent)
    return str(relative.with_suffix(""))


def _match_link(match_id: Any) -> str:
    if pd.isna(match_id):
        return ""
    return _obsidian_link(_match_report_relpath(str(match_id)), match_id)


def _percent(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value) * 100:.1f}%"


def _consistency_label(std_value: Any) -> str:
    """Rotulo qualitativo do desvio padrao do aproveitamento por jogo — o numero
    bruto (ex: 0.42) nao e interpretavel sozinho com 3-7 jogos de amostra."""
    if pd.isna(std_value):
        return ""
    value = float(std_value)
    if value < 0.15:
        return "estavel (resultados parecidos jogo a jogo)"
    if value < 0.40:
        return "moderada (alguma variacao entre jogos)"
    return "inconsistente (alterna entre extremos)"


def _trend_label(trend_value: Any) -> str:
    """Rotulo qualitativo da tendencia (2a metade vs 1a metade dos jogos)."""
    if pd.isna(trend_value):
        return ""
    value = float(trend_value)
    if value > 0.15:
        return "subindo (melhor nos jogos mais recentes)"
    if value < -0.15:
        return "caindo (pior nos jogos mais recentes)"
    return "estavel (sem mudanca clara)"


def _read_optional(path: Path) -> pd.DataFrame:
    return read_dataframe(path) if path.exists() else pd.DataFrame()
