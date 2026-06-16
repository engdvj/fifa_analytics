from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from fifa_analytics.analytics.scores import (
    build_player_match_features,
    build_player_scores,
    build_team_match_features,
    build_team_recent_form,
    build_team_scores,
)
from fifa_analytics.paths import GOLD_DIR, REPORTS_DIR
from fifa_analytics.utils.io import ensure_dir, read_dataframe, write_dataframe
from fifa_analytics.utils.text import slugify
from fifa_analytics.utils.time import utc_now_iso


ANALYTICS_DIR = GOLD_DIR / "analytics"
TEAM_REPORTS_DIR = REPORTS_DIR / "teams"
PLAYER_REPORTS_DIR = REPORTS_DIR / "players"
RANKINGS_DIR = REPORTS_DIR / "rankings"
TEAM_RANKINGS_DIR = RANKINGS_DIR / "selecoes"
PLAYER_RANKINGS_DIR = RANKINGS_DIR / "jogadores"
TEAM_RANKINGS = [
    ("geral", "score_geral", "nota geral"),
    ("resultado", "score_resultado", "resultado"),
    ("ataque", "score_ataque", "ataque"),
    ("defesa", "score_defesa", "defesa"),
    ("eficiencia", "score_eficiencia", "eficiencia"),
    ("controle", "score_controle", "controle"),
    ("forma", "forma_score", "forma recente"),
]
PLAYER_RANKINGS = [
    ("geral", "score_geral", "nota geral"),
    ("acumulado", "score_acumulado", "impacto acumulado"),
    ("goleiros", "score_geral", "goleiros"),
    ("defensores", "score_geral", "defensores"),
    ("meias", "score_geral", "meias"),
    ("atacantes", "score_geral", "atacantes"),
]


def run_scores_pipeline() -> dict[str, Any]:
    matches = _read_optional(GOLD_DIR / "dim_match" / "canonical_matches.parquet")
    if matches.empty:
        raise FileNotFoundError("Indice canonico ausente. Rode `python -m fifa_analytics indice-canonico` primeiro.")

    team_stats = _read_optional(GOLD_DIR / "fact_team_match_stats" / "canonical_team_stats.parquet")
    player_stats = _read_optional(GOLD_DIR / "fact_player_match_stats" / "canonical_player_stats.parquet")
    lineups = _read_optional(GOLD_DIR / "lineups" / "canonical_lineups.parquet")

    team_match_features = build_team_match_features(matches, team_stats)
    team_scores = build_team_scores(team_match_features)
    team_recent_form = build_team_recent_form(team_match_features, n=5)
    player_match_features = build_player_match_features(player_stats, lineups)
    player_scores = build_player_scores(player_match_features)

    team_match_features_path = write_dataframe(ANALYTICS_DIR / "team_match_features.parquet", team_match_features)
    team_scores_path = write_dataframe(ANALYTICS_DIR / "team_scores.parquet", team_scores)
    team_recent_form_path = write_dataframe(ANALYTICS_DIR / "team_recent_form.parquet", team_recent_form)
    player_match_features_path = write_dataframe(ANALYTICS_DIR / "player_match_features.parquet", player_match_features)
    player_scores_path = write_dataframe(ANALYTICS_DIR / "player_scores.parquet", player_scores)

    team_report_paths = write_team_reports(team_scores, team_match_features, player_scores, team_recent_form)
    player_report_paths = write_player_reports(player_scores, player_match_features)
    team_index_path = write_team_index(team_scores)
    player_index_path = write_player_index(player_scores)
    rankings_index_path = write_rankings_index()
    team_ranking_paths = write_team_rankings(team_scores)
    player_ranking_paths = write_player_rankings(player_scores)

    return {
        "team_match_features_path": team_match_features_path,
        "team_scores_path": team_scores_path,
        "team_recent_form_path": team_recent_form_path,
        "player_match_features_path": player_match_features_path,
        "player_scores_path": player_scores_path,
        "team_reports_dir": TEAM_REPORTS_DIR,
        "player_reports_dir": PLAYER_REPORTS_DIR,
        "team_index_path": team_index_path,
        "player_index_path": player_index_path,
        "rankings_index_path": rankings_index_path,
        "team_ranking_path": team_ranking_paths[0] if team_ranking_paths else None,
        "player_ranking_path": player_ranking_paths[0] if player_ranking_paths else None,
        "team_rankings": len(team_ranking_paths),
        "player_rankings": len(player_ranking_paths),
        "teams_ranked": len(team_scores),
        "players_ranked": len(player_scores),
        "team_reports": len(team_report_paths),
        "player_reports": len(player_report_paths),
    }


def write_team_reports(
    team_scores: pd.DataFrame,
    team_match_features: pd.DataFrame,
    player_scores: pd.DataFrame,
    team_recent_form: pd.DataFrame | None = None,
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
        players = player_scores[player_scores["team"] == team["team"]].sort_values("score_geral", ascending=False)
        recent = form_by_team.get(str(team["team"]))
        path = TEAM_REPORTS_DIR / f"{team['team_slug']}.md"
        path.write_text(_render_team_report(team, matches, players, total_teams, team_slug_by_name, recent), encoding="utf-8")
        paths.append(path)
    return paths


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
- [[reports/rankings/jogadores/index\\|Rankings de jogadores]]
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


def write_player_reports(player_scores: pd.DataFrame, player_match_features: pd.DataFrame) -> list[Path]:
    ensure_dir(PLAYER_REPORTS_DIR)
    paths = []
    total_players = len(player_scores)
    for _, player in player_scores.iterrows():
        matches = player_match_features[player_match_features["player_slug"] == player["player_slug"]].sort_values("match_id")
        path = PLAYER_REPORTS_DIR / f"{player['player_slug']}.md"
        path.write_text(_render_player_report(player, matches, total_players), encoding="utf-8")
        paths.append(path)
    return paths


def write_player_index(player_scores: pd.DataFrame) -> Path:
    ensure_dir(PLAYER_REPORTS_DIR)
    path = PLAYER_REPORTS_DIR / "index.md"
    path.write_text(_render_player_ranking(player_scores, "geral", "score_geral", "nota geral"), encoding="utf-8")
    return path


_PROFILE_SLUGS = {"goleiros": "goleiro", "defensores": "defensor", "meias": "meio", "atacantes": "atacante"}


def write_player_rankings(player_scores: pd.DataFrame) -> list[Path]:
    ensure_dir(PLAYER_RANKINGS_DIR)
    paths = []
    index_path = PLAYER_RANKINGS_DIR / "index.md"
    index_path.write_text(_render_player_rankings_index(player_scores), encoding="utf-8")
    paths.append(index_path)
    for slug, metric, title in PLAYER_RANKINGS:
        profile_filter = _PROFILE_SLUGS.get(slug)
        pool = player_scores[player_scores["perfil"] == profile_filter] if profile_filter else player_scores
        path = PLAYER_RANKINGS_DIR / f"{slug}.md"
        path.write_text(_render_player_ranking(pool, slug, metric, title), encoding="utf-8")
        paths.append(path)
    return paths


def _render_player_rankings_index(player_scores: pd.DataFrame) -> str:
    links = "\n".join(f"- [[reports/rankings/jogadores/{slug}\\|{title.title()}]]" for slug, _, title in PLAYER_RANKINGS)
    return f"# Rankings de jogadores\n\nAtualizado em `{utc_now_iso()}`.\n\n{links}\n\n{_render_player_ranking(player_scores, 'geral', 'score_geral', 'nota geral')}"


def _render_player_ranking(player_scores: pd.DataFrame, ranking_slug: str, metric: str, title: str) -> str:
    if player_scores.empty:
        return f"# Ranking de jogadores - {title.title()}\n\nNenhum jogador encontrado para este perfil.\n"
    sort_cols = [c for c in [metric, "score_geral", "goals"] if c in player_scores.columns]
    ranked = player_scores.sort_values(sort_cols, ascending=[False] * len(sort_cols)).reset_index(drop=True)
    ranked["rank_metrica"] = ranked.index + 1
    score_columns = ["score_geral", "score_acumulado"]
    want_columns = [
        "rank_metrica", "player_slug", "player_name", "team", "perfil",
        metric,
        *[c for c in score_columns if c != metric and c in ranked.columns],
        "nivel_evidencia", "jogos", "goals", "assists", "shots_on_target", "saves",
    ]
    available = [c for c in want_columns if c in ranked.columns]
    display = ranked.head(100)[available].copy()
    if "player_name" in display.columns and "player_slug" in display.columns:
        display["player_name"] = display.apply(lambda row: _player_link(row["player_name"], row["player_slug"]), axis=1)
    if "team" in display.columns:
        display["team"] = display["team"].apply(lambda t: _team_link(t, slugify(t)))
    if "player_slug" in display.columns:
        display = display.drop(columns=["player_slug"])
    display = display.rename(columns=_player_ranking_labels(metric, title))
    nav = _player_rankings_nav(ranking_slug)
    return f"# Ranking de jogadores - {title.title()}\n\nAtualizado em `{utc_now_iso()}`.\n\n{nav}\n\n{_player_score_explanation()}\n\nTop 100 por {title}.\n\n{display.to_markdown(index=False)}\n"


def _render_team_report(
    team: pd.Series,
    matches: pd.DataFrame,
    players: pd.DataFrame,
    total_teams: int,
    team_slug_by_name: dict[str, str],
    recent: pd.Series | None = None,
) -> str:
    generated_at = utc_now_iso()
    components = _markdown_table(
        [
            ["Resultado", team.get("score_resultado", 0)],
            ["Ataque", team.get("score_ataque", 0)],
            ["Defesa", team.get("score_defesa", 0)],
            ["Eficiencia", team.get("score_eficiencia", 0)],
            ["Controle", team.get("score_controle", 0)],
        ],
        ["componente", "nota"],
    )
    audit = _markdown_table(
        [
            ["Resultado", team.get("score_resultado", 0), team.get("confianca_amostra", ""), team.get("nivel_evidencia", "")],
            ["Ataque",    team.get("score_ataque", 0),    team.get("confianca_dados", ""),   _evidence_level(team.get("confianca_dados"))],
            ["Defesa",    team.get("score_defesa", 0),    team.get("confianca_dados", ""),   _evidence_level(team.get("confianca_dados"))],
            ["Eficiencia",team.get("score_eficiencia", 0),team.get("confianca_dados", ""),   _evidence_level(team.get("confianca_dados"))],
            ["Controle",  team.get("score_controle", 0),  team.get("confianca_dados", ""),   _evidence_level(team.get("confianca_dados"))],
        ],
        ["componente", "nota_usada", "peso_evidencia", "evidencia"],
    )
    summary = _markdown_table(
        [
            ["jogos", team.get("jogos", 0)],
            ["pontos", team.get("points", 0)],
            ["saldo_gols", team.get("saldo_gols", 0)],
            ["gols_pro", team.get("gols_pro", 0)],
            ["gols_contra", team.get("gols_contra", 0)],
            ["chutes_no_alvo", team.get("chutes_no_alvo", 0)],
            ["chutes_no_alvo_sofridos", team.get("chutes_no_alvo_sofridos", 0)],
            ["jogos_com_estatisticas", team.get("jogos_com_estatisticas", "")],
            ["aproveitamento", _percent(team.get("aproveitamento"))],
        ],
        ["metrica", "valor"],
    )

    forma_section = ""
    if recent is not None:
        forma_section = f"""
## Forma recente (ultimos {int(recent.get('forma_n', 5))} jogos)

Sequencia: **{recent.get('forma_sequencia', '')}** (V=vitoria, E=empate, D=derrota, mais recente a direita)

{_markdown_table(
    [
        ["jogos", recent.get('forma_jogos', 0)],
        ["pontos", recent.get('forma_pontos', 0)],
        ["aproveitamento", _percent(recent.get('forma_aproveitamento'))],
        ["vitorias", recent.get('forma_vitorias', 0)],
        ["empates", recent.get('forma_empates', 0)],
        ["derrotas", recent.get('forma_derrotas', 0)],
        ["gols_pro", recent.get('forma_gols_pro', 0)],
        ["gols_contra", recent.get('forma_gols_contra', 0)],
    ],
    ["metrica", "valor"],
)}
"""

    match_table = _team_matches_table(matches, team_slug_by_name)
    player_table = _team_players_table_by_profile(players)
    return f"""<!--
team: {team.get('team')}
generated_at: {generated_at}
-->

# {team.get('team')}

[[reports/rankings/selecoes/index|Ranking de selecoes]]

## Score

Nota geral: **{_format_score(team.get('score_geral'))}/100**

Ranking geral: **{_format_value(team.get('ranking_score_geral'))} de {total_teams}**

Nivel de evidencia: **{team.get('nivel_evidencia', '')}**

{_team_score_explanation()}

## Componentes da nota

{components}

## Resumo acumulado

{summary}
{forma_section}
## Jogos

{match_table}

## Jogadores

{player_table}

## Auditoria da nota

{audit}
"""


def _render_player_report(player: pd.Series, matches: pd.DataFrame, total_players: int) -> str:
    generated_at = utc_now_iso()
    profile = player.get("perfil", "")
    profile_label = {"goleiro": "Goleiro", "defensor": "Defensor", "meio": "Meia", "atacante": "Atacante"}.get(profile, profile)
    profile_ranking_slug = {"goleiro": "goleiros", "defensor": "defensores", "meio": "meias", "atacante": "atacantes"}.get(profile, "geral")
    summary = _markdown_table(
        [
            ["selecao", player.get("team", "")],
            ["perfil", profile_label],
            ["jogos", player.get("jogos", 0)],
            ["gols", player.get("goals", 0)],
            ["assistencias", player.get("assists", 0)],
            ["participacoes_gol", player.get("participacoes_gol", 0)],
            ["chutes_no_alvo", player.get("shots_on_target", 0)],
            ["defesas", player.get("saves", 0)],
            ["tackles", player.get("tackles", 0)],
            ["intercepcoes", player.get("interceptions", 0)],
            ["score_acumulado", player.get("score_acumulado", 0)],
        ],
        ["metrica", "valor"],
    )
    match_table = _player_matches_table(matches)
    team_name = player.get("team") or ""
    return f"""<!--
player: {player.get('player_name')}
team: {team_name}
perfil: {profile}
generated_at: {generated_at}
-->

# {player.get('player_name')}

[[reports/rankings/jogadores/index|Ranking geral]] · [[reports/rankings/jogadores/{profile_ranking_slug}|Ranking {profile_label}]] · {_team_link(team_name, slugify(team_name))}

## Score

Nota geral ({profile_label}): **{_format_score(player.get('score_geral'))}/100**

Ranking geral: **{_format_value(player.get('ranking_score_geral'))} de {total_players}**

Nivel de evidencia: **{player.get('nivel_evidencia', '')}**

{_player_score_explanation()}

## Resumo acumulado

{summary}

## Jogos

{match_table}
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


def _team_players_table(players: pd.DataFrame) -> str:
    if players.empty:
        return "Nenhum jogador com estatistica individual encontrado."
    want = ["ranking_score_geral", "player_name", "perfil", "score_geral",
            "jogos", "goals", "assists", "shots_on_target", "saves"]
    avail = [c for c in want if c in players.columns]
    display = players.head(20)[avail].copy()
    display["player_name"] = players.head(20).apply(
        lambda row: _player_link(row["player_name"], row["player_slug"]), axis=1
    )
    display = display.rename(columns={
        "ranking_score_geral": "rank", "player_name": "jogador",
        "score_geral": "nota", "goals": "gols",
        "assists": "assist", "shots_on_target": "no_alvo", "saves": "defesas",
    })
    return display.fillna("").to_markdown(index=False)


def _team_players_table_by_profile(players: pd.DataFrame) -> str:
    """Tabela de jogadores agrupada por perfil com ranking dentro do perfil."""
    if players.empty:
        return "Nenhum jogador com estatistica individual encontrado."
    profile_order = ["goleiro", "defensor", "meio", "atacante"]
    profile_labels = {"goleiro": "Goleiros", "defensor": "Defensores", "meio": "Meias", "atacante": "Atacantes"}
    sections = []
    for profile in profile_order:
        pool = players[players["perfil"] == profile] if "perfil" in players.columns else pd.DataFrame()
        if pool.empty:
            continue
        want = ["player_name", "score_geral", "jogos", "goals", "assists", "shots_on_target", "saves", "tackles", "interceptions"]
        avail = [c for c in want if c in pool.columns]
        display = pool[avail].copy()
        display["player_name"] = pool.apply(
            lambda row: _player_link(row["player_name"], row["player_slug"]), axis=1
        )
        display = display.rename(columns={
            "player_name": "jogador", "score_geral": "nota",
            "goals": "gols", "assists": "assist",
            "shots_on_target": "no_alvo", "saves": "defesas",
        })
        sections.append(f"### {profile_labels[profile]}\n\n{display.fillna('').to_markdown(index=False)}")
    return "\n\n".join(sections) if sections else "Nenhum jogador com estatistica individual encontrado."


def _player_matches_table(matches: pd.DataFrame) -> str:
    if matches.empty:
        return "Nenhum jogo com estatistica individual encontrado."
    columns = [
        "match_id", "goals", "assists", "shots_on_target",
        "saves", "tackles", "interceptions", "yellow_cards", "red_cards",
    ]
    available = [c for c in columns if c in matches.columns]
    display = matches[available].copy()
    if "match_id" in display.columns:
        display["match_id"] = display["match_id"].apply(_match_link)
    display = display.rename(columns={
        "match_id": "jogo", "goals": "gols", "assists": "assist",
        "shots_on_target": "no_alvo", "saves": "defesas",
        "yellow_cards": "amarelos", "red_cards": "vermelhos",
    })
    return display.fillna(0).to_markdown(index=False)


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


def _player_rankings_nav(active_slug: str) -> str:
    links = []
    for slug, _, title in PLAYER_RANKINGS:
        label = title.title()
        if slug == active_slug:
            label = f"{label} (atual)"
        links.append(f"[[reports/rankings/jogadores/{slug}\\|{label}]]")
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


def _player_ranking_labels(metric: str, title: str) -> dict[str, str]:
    labels = {
        "rank_metrica": "rank",
        "player_name": "jogador",
        "team": "selecao",
        "score_geral": "nota_geral",
        "score_acumulado": "acumulado",
        "nivel_evidencia": "evidencia",
        "goals": "gols",
        "assists": "assist",
        "shots_on_target": "no_alvo",
        "saves": "defesas",
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


def _player_score_explanation() -> str:
    return """## Como ler a nota

- **Nota geral**: nota de 0 a 100 calculada dentro do pool de cada perfil (goleiro, defensor, meia, atacante). Goleiro nao compete com atacante na mesma formula.
- **Acumulado**: contribuicao total no torneio (gols, assistencias, defesas) — coluna auxiliar, nao entra na nota geral.
- **Evidencia**: estabilidade da nota (`baixa`, `media`, `alta`). Com poucos jogos a nota tende a oscilar mais.
- Rankings por posicao: `goleiros`, `defensores`, `meias`, `atacantes` — cada um usa metricas do proprio perfil."""


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


def _player_link(player_name: Any, player_slug: Any) -> str:
    if pd.isna(player_name):
        return ""
    return _obsidian_link(f"reports/players/{player_slug}", player_name)


def _match_link(match_id: Any) -> str:
    if pd.isna(match_id):
        return ""
    return _obsidian_link(f"reports/final/{match_id}", match_id)


def _evidence_level(value: Any) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0).iloc[0]
    if numeric >= 0.90:
        return "alta"
    if numeric >= 0.75:
        return "media"
    return "baixa"


def _percent(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value) * 100:.1f}%"


def _read_optional(path: Path) -> pd.DataFrame:
    return read_dataframe(path) if path.exists() else pd.DataFrame()
