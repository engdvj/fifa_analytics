from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fifa_analytics.analytics.scores import (
    TEAM_SCORE_WEIGHTS,
    build_player_match_features,
    build_team_match_features,
    build_team_recent_form,
    build_team_scores,
)
from fifa_analytics.paths import GOLD_DIR, MANIFESTS_DIR, REPORTS_DIR
from fifa_analytics.transforms.standings import calculate_group_standings
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

CALIBRATION_DIR = ANALYTICS_DIR / "calibration_history"
CALIBRATION_INDEX_PATH = CALIBRATION_DIR / "index.md"
CALIBRATION_WEIGHTS_JSON_PATH = CALIBRATION_DIR / "latest_weight_calibration.json"
# Intervalo entre snapshots: só vale gerar um novo quando o total de jogos
# finalizados cresceu por pelo menos esse tanto desde o último snapshot —
# evita gerar snapshot repetido se rodar `scores` várias vezes no mesmo dia
# sem nenhum jogo novo.
CALIBRATION_INTERVAL_GAMES = 1


def _load_latest_calibrated_weights() -> dict[str, float]:
    """Lê o snapshot de calibração mais recente (se existir) e combina com
    TEAM_SCORE_WEIGHTS via apply_calibrated_weights — score_resultado e
    score_forca_relativa continuam fixos (decisão de design), só os 4
    componentes de processo são ajustados pela sugestão calibrada.

    Sem nenhum snapshot ainda (torneio recém-começado, calibrar-pesos nunca
    rodou), usa TEAM_SCORE_WEIGHTS sem alteração.
    """
    if not CALIBRATION_WEIGHTS_JSON_PATH.exists():
        return dict(TEAM_SCORE_WEIGHTS)

    import json
    from fifa_analytics.analytics.calibration import apply_calibrated_weights

    weight_calibration = json.loads(CALIBRATION_WEIGHTS_JSON_PATH.read_text(encoding="utf-8"))
    return apply_calibrated_weights(TEAM_SCORE_WEIGHTS, weight_calibration)

PROFILE_LABELS = {"goleiro": "Goleiro", "defensor": "Defensor", "meio": "Meia", "atacante": "Atacante"}
# Colunas relevantes por perfil — goleiro nao marca gol nem chuta a gol como
# metrica relevante, atacante nao defende. Cada perfil mostra so o que importa.
PROFILE_STATS: dict[str, list[str]] = {
    "goleiro": ["saves", "goals_conceded", "yellow_cards", "red_cards"],
    "defensor": ["goals", "assists", "shots_on_target", "shots_off_target", "fouls_committed", "fouls_drawn", "yellow_cards", "red_cards"],
    "meio": ["goals", "assists", "shots_on_target", "shots_off_target", "fouls_committed", "fouls_drawn", "yellow_cards", "red_cards"],
    "atacante": ["goals", "assists", "shots_on_target", "shots_off_target", "fouls_committed", "fouls_drawn", "yellow_cards", "red_cards"],
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
    ("forca-relativa", "score_forca_relativa", "forca relativa"),
    ("disciplina", "score_disciplina", "disciplina"),
]
# Estilo de jogo nao e um ranking ordenado (estilo nao e melhor/pior), entao
# tem pagina propria com tabela comparativa — listado separado de TEAM_RANKINGS
# mas presente na mesma navegacao.
TEAM_STYLE_PAGE = ("estilo", "estilo de jogo")


def run_scores_pipeline() -> dict[str, Any]:
    matches = _read_optional(GOLD_DIR / "dim_match" / "canonical_matches.parquet")
    if matches.empty:
        raise FileNotFoundError("Indice canonico ausente. Rode `python -m fifa_analytics indice-canonico` primeiro.")

    team_stats = _read_optional(GOLD_DIR / "fact_team_match_stats" / "canonical_team_stats.parquet")
    player_stats = _read_optional(GOLD_DIR / "fact_player_match_stats" / "canonical_player_stats.parquet")
    lineups = _read_optional(GOLD_DIR / "lineups" / "canonical_lineups.parquet")
    rosters = _read_optional(GOLD_DIR / "rosters" / "espn_rosters.parquet")
    stats_365 = _read_optional(GOLD_DIR / "fact_team_match_stats" / "365scores_enrichment.parquet")

    events = _read_optional(GOLD_DIR / "fact_events" / "canonical_events.parquet")
    team_match_features = build_team_match_features(matches, team_stats, events, lineups, stats_365)
    effective_weights = _load_latest_calibrated_weights()
    team_scores = build_team_scores(team_match_features, weights=effective_weights)
    team_recent_form = build_team_recent_form(team_match_features, n=3)
    player_match_features = build_player_match_features(player_stats, lineups, rosters)
    group_standings = calculate_group_standings(matches)

    team_match_features_path = write_dataframe(ANALYTICS_DIR / "team_match_features.parquet", team_match_features)
    team_scores_path = write_dataframe(ANALYTICS_DIR / "team_scores.parquet", team_scores)
    team_recent_form_path = write_dataframe(ANALYTICS_DIR / "team_recent_form.parquet", team_recent_form)
    player_match_features_path = write_dataframe(ANALYTICS_DIR / "player_match_features.parquet", player_match_features)
    team_score_history = _record_team_score_history(team_scores)

    team_report_paths = write_team_reports(team_scores, team_match_features, player_match_features, team_recent_form, team_score_history, group_standings, effective_weights)
    player_report_paths = write_player_reports(player_match_features)
    team_index_path = write_team_index(team_scores)
    rankings_index_path = write_rankings_index()
    team_scores_for_rankings = team_scores.copy()
    team_scores_for_rankings["tendencia_ranking"] = _ranking_trend(team_scores, team_score_history)
    team_ranking_paths = write_team_rankings(team_scores_for_rankings, effective_weights)

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


def run_calibration_report(force: bool = False) -> dict[str, Any]:
    """Calibra os pesos do score_geral e valida cada componente contra a
    métrica que ele tenta capturar, usando os jogos já finalizados.

    Não altera TEAM_SCORE_WEIGHTS automaticamente — apenas reporta o que os
    dados sugerem. Ajustar pesos com poucos jogos é arriscado (overfitting),
    então a decisão de aplicar a sugestão fica manual.

    Só gera um novo snapshot se o número de jogos cresceu por pelo menos
    CALIBRATION_INTERVAL_GAMES desde o último (ver ``force=True`` para pular
    essa checagem). Cada snapshot fica salvo em calibration_history/ com o
    número de jogos no nome, para comparar a evolução da sugestão conforme
    o torneio avança — pesos que oscilam muito entre snapshots indicam que
    ainda é cedo para fixar a calibração.
    """
    from fifa_analytics.analytics.calibration import (
        COMPONENT_VALIDATION_TARGETS,
        calibrate_full_weights_predictive,
        calibrate_team_score_weights,
        validate_component,
    )

    features_path = ANALYTICS_DIR / "team_match_features.parquet"
    features = _read_optional(features_path)
    if features.empty:
        raise FileNotFoundError("team_match_features ausente. Rode `fifa-analytics scores` primeiro.")

    n_jogos = features["match_id"].nunique()
    last_n = _last_calibration_game_count()
    if not force and last_n is not None and n_jogos - last_n < CALIBRATION_INTERVAL_GAMES:
        return {
            "status": "pulado",
            "motivo": f"apenas {n_jogos - last_n} jogo(s) novo(s) desde o último snapshot ({last_n} jogos); aguardando {CALIBRATION_INTERVAL_GAMES}",
            "n_jogos": n_jogos,
            "ultimo_snapshot_jogos": last_n,
        }

    component_results = {
        component: validate_component(features, component) for component in COMPONENT_VALIDATION_TARGETS
    }

    # Tenta calibração preditiva com 6 pesos (requer times com 2+ jogos e
    # histórico de scores). Se não houver dados suficientes, cai no modo
    # processo (4 pesos variáveis, resultado e força relativa fixos).
    score_history = _read_optional(TEAM_SCORE_HISTORY_PATH)
    weight_calibration = calibrate_full_weights_predictive(features, score_history if not score_history.empty else None)
    if weight_calibration.get("status") != "ok":
        weight_calibration = calibrate_team_score_weights(features)

    report_content = _render_calibration_report(n_jogos, component_results, weight_calibration)

    ensure_dir(CALIBRATION_DIR)
    snapshot_path = CALIBRATION_DIR / f"calibration_{n_jogos:03d}_jogos.md"
    snapshot_path.write_text(report_content, encoding="utf-8")

    current_path = ANALYTICS_DIR / "calibration_report.md"
    current_path.write_text(report_content, encoding="utf-8")

    import json
    CALIBRATION_WEIGHTS_JSON_PATH.write_text(json.dumps(weight_calibration, default=float), encoding="utf-8")

    _update_calibration_index(n_jogos, weight_calibration, snapshot_path)

    return {
        "status": "gerado",
        "calibration_report_path": current_path,
        "snapshot_path": snapshot_path,
        "n_jogos": n_jogos,
        "component_results": component_results,
        "weight_calibration": weight_calibration,
    }


def _last_calibration_game_count() -> int | None:
    if not CALIBRATION_DIR.exists():
        return None
    snapshots = sorted(CALIBRATION_DIR.glob("calibration_*_jogos.md"))
    if not snapshots:
        return None
    last = snapshots[-1].stem
    try:
        return int(last.split("_")[1])
    except (IndexError, ValueError):
        return None


def _render_calibration_report(
    n_jogos: int,
    component_results: dict[str, Any],
    weight_calibration: dict[str, Any],
) -> str:
    lines = ["# Calibração de pesos — score de seleções\n"]
    lines.append(f"Jogos disponíveis: {n_jogos}\n")
    lines.append(
        "Aviso: com poucos jogos, R² e pesos sugeridos têm alta variância — "
        "tratar como direção, não como substituição definitiva dos pesos manuais.\n"
    )

    lines.append("## Validação por componente\n")
    lines.append("| Componente | R² | N jogos | Maior peso |")
    lines.append("|---|---|---|---|")
    for component, result in component_results.items():
        if result.get("status") != "ok":
            lines.append(f"| {component} | - | {result.get('n_jogos', 0)} | dados insuficientes |")
            continue
        coefs = result["coeficientes_padronizados"]
        top_feature = max(coefs, key=lambda k: abs(coefs[k]))
        lines.append(f"| {component} | {result['r2']} | {result['n_jogos']} | {top_feature} ({coefs[top_feature]}) |")

    lines.append("\n## Pesos sugeridos para score_geral (vs. atuais)\n")
    if weight_calibration.get("status") == "ok":
        lines.append(f"R² do modelo: {weight_calibration['r2']} | N jogos: {weight_calibration['n_jogos']}\n")
        lines.append("| Componente | Peso atual | Peso sugerido |")
        lines.append("|---|---|---|")
        for component, current_weight in TEAM_SCORE_WEIGHTS.items():
            suggested = weight_calibration["pesos_sugeridos"].get(component)
            suggested_display = suggested if suggested is not None else "—"
            lines.append(f"| {component} | {current_weight} | {suggested_display} |")
    else:
        lines.append(f"Status: {weight_calibration.get('status')}\n")

    return "\n".join(lines)


def _update_calibration_index(n_jogos: int, weight_calibration: dict[str, Any], snapshot_path: Path) -> None:
    """Mantém um índice com uma linha por snapshot, para ver a evolução dos
    pesos sugeridos ao longo do torneio sem abrir cada relatório individual.

    Se já existir uma linha para esse mesmo n_jogos (ex: re-rodado com
    --forcar), substitui em vez de duplicar.
    """
    header = "| Jogos | R² | " + " | ".join(TEAM_SCORE_WEIGHTS.keys()) + " | Relatório |"
    separator = "|---" * (len(TEAM_SCORE_WEIGHTS) + 3) + "|"

    if CALIBRATION_INDEX_PATH.exists():
        existing_lines = CALIBRATION_INDEX_PATH.read_text(encoding="utf-8").splitlines()
    else:
        existing_lines = ["# Histórico de calibração de pesos", "", header, separator]

    row_prefix = f"| {n_jogos} |"
    existing_lines = [line for line in existing_lines if not line.startswith(row_prefix)]

    suggested = weight_calibration.get("pesos_sugeridos", {}) if weight_calibration.get("status") == "ok" else {}
    r2 = weight_calibration.get("r2", "-")
    row_values = [suggested.get(c, "—") for c in TEAM_SCORE_WEIGHTS]
    row = f"| {n_jogos} | {r2} | " + " | ".join(str(v) for v in row_values) + f" | [{snapshot_path.name}]({snapshot_path.name}) |"

    CALIBRATION_INDEX_PATH.write_text("\n".join(existing_lines + [row]) + "\n", encoding="utf-8")


def write_team_reports(
    team_scores: pd.DataFrame,
    team_match_features: pd.DataFrame,
    player_match_features: pd.DataFrame,
    team_recent_form: pd.DataFrame | None = None,
    team_score_history: pd.DataFrame | None = None,
    group_standings: pd.DataFrame | None = None,
    weights: dict[str, float] | None = None,
) -> list[Path]:
    effective_weights = weights if weights is not None else TEAM_SCORE_WEIGHTS
    ensure_dir(TEAM_REPORTS_DIR)
    paths = []
    total_teams = len(team_scores)
    team_slug_by_name = dict(zip(team_scores["team"], team_scores["team_slug"]))
    form_by_team: dict[str, pd.Series] = {}
    if team_recent_form is not None and not team_recent_form.empty:
        for _, row in team_recent_form.iterrows():
            form_by_team[str(row["team"])] = row
    group_by_team: dict[str, str] = {}
    if "group" in team_match_features.columns:
        group_by_team = team_match_features.dropna(subset=["group"]).drop_duplicates("team").set_index("team")["group"].to_dict()
    for _, team in team_scores.iterrows():
        matches = team_match_features[team_match_features["team"] == team["team"]].sort_values("date")
        player_events = player_match_features[player_match_features["team"] == team["team"]] if not player_match_features.empty else pd.DataFrame()
        recent = form_by_team.get(str(team["team"]))
        history = (
            team_score_history[team_score_history["team"] == team["team"]].sort_values("jogos")
            if team_score_history is not None and not team_score_history.empty
            else pd.DataFrame()
        )
        group = group_by_team.get(str(team["team"]))
        group_table = (
            group_standings[group_standings["group"] == group]
            if group is not None and group_standings is not None and not group_standings.empty
            else pd.DataFrame()
        )
        path = TEAM_REPORTS_DIR / f"{team['team_slug']}.md"
        path.write_text(
            _render_team_report(team, matches, player_events, total_teams, team_slug_by_name, recent, history, group_table, effective_weights),
            encoding="utf-8",
        )
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
    """Lista simples das selecoes por nome, com link para o relatorio de cada
    uma — o ranking completo (com notas e componentes) ja existe em
    reports/rankings/selecoes/geral.md, nao precisa ser duplicado aqui."""
    ensure_dir(TEAM_REPORTS_DIR)
    path = TEAM_REPORTS_DIR / "index.md"
    if team_scores.empty:
        path.write_text("# Selecoes\n\nNenhuma selecao disponivel ainda.\n", encoding="utf-8")
        return path
    ordered = team_scores.sort_values("team")
    links = "\n".join(f"- {_team_link(row['team'], row.get('team_slug'))}" for _, row in ordered.iterrows())
    content = f"""# Selecoes

[[reports/rankings/selecoes/index\\|Ver ranking completo]]

{links}
"""
    path.write_text(content, encoding="utf-8")
    return path


def write_rankings_index() -> Path:
    ensure_dir(RANKINGS_DIR)
    path = RANKINGS_DIR / "index.md"
    calibration_link = ""
    if CALIBRATION_INDEX_PATH.exists():
        _copy_calibration_index_to_reports()
        calibration_link = "\n- [[reports/rankings/calibracao_pesos\\|Historico de calibracao de pesos]]"
    content = f"""# Rankings

Atualizado em `{utc_now_iso()}`.

- [[reports/rankings/selecoes/index\\|Rankings de selecoes]]{calibration_link}
"""
    path.write_text(content, encoding="utf-8")
    return path


def _copy_calibration_index_to_reports() -> None:
    """O histórico de calibração vive em data/gold/analytics/ (camada de
    dados), mas precisa ser navegável a partir de reports/ como os outros
    relatórios — copia o índice (não os snapshots individuais, esses ficam
    só na camada de dados por serem material de auditoria, não de consumo).
    """
    content = CALIBRATION_INDEX_PATH.read_text(encoding="utf-8")
    note = (
        "\n\n_Cada linha representa um snapshot de calibração gerado a cada "
        "jogo novo finalizado — ver `fifa-analytics calibrar-pesos`. "
        "R² baixo ou pesos oscilando entre snapshots indicam que ainda é "
        "cedo para tratar a sugestão como definitiva; o ranking aplica "
        "automaticamente o snapshot mais recente disponível._\n"
    )
    (RANKINGS_DIR / "calibracao_pesos.md").write_text(content + note, encoding="utf-8")


def write_team_rankings(team_scores: pd.DataFrame, weights: dict[str, float] | None = None) -> list[Path]:
    effective_weights = weights if weights is not None else TEAM_SCORE_WEIGHTS
    ensure_dir(TEAM_RANKINGS_DIR)
    paths = []
    index_path = TEAM_RANKINGS_DIR / "index.md"
    index_path.write_text(_render_team_rankings_index(team_scores), encoding="utf-8")
    paths.append(index_path)
    for slug, metric, title in TEAM_RANKINGS:
        path = TEAM_RANKINGS_DIR / f"{slug}.md"
        path.write_text(_render_team_ranking(team_scores, slug, metric, title, effective_weights), encoding="utf-8")
        paths.append(path)
    style_path = TEAM_RANKINGS_DIR / f"{TEAM_STYLE_PAGE[0]}.md"
    style_path.write_text(_render_team_style_table(team_scores), encoding="utf-8")
    paths.append(style_path)
    return paths


def _render_team_rankings_index(team_scores: pd.DataFrame) -> str:
    """So navegacao — a tabela completa do ranking geral fica em
    reports/rankings/selecoes/geral.md, sem duplicar aqui."""
    entries = [(slug, title) for slug, _, title in TEAM_RANKINGS] + [TEAM_STYLE_PAGE]
    links = "\n".join(f"- [[reports/rankings/selecoes/{slug}\\|{title.title()}]]" for slug, title in entries)
    return f"# Rankings de selecoes\n\nAtualizado em `{utc_now_iso()}`.\n\n{links}\n"


def _render_team_ranking(
    team_scores: pd.DataFrame,
    ranking_slug: str,
    metric: str,
    title: str,
    weights: dict[str, float] | None = None,
) -> str:
    # Para forma recente, a coluna pode não existir se o pipeline não rodou ainda
    if metric not in team_scores.columns:
        return f"# Ranking de selecoes - {title.title()}\n\nDados de `{metric}` ainda nao disponiveis.\n"
    ranked = team_scores.sort_values([metric, "score_geral", "points", "saldo_gols"], ascending=[False, False, False, False]).reset_index(drop=True)
    ranked["rank_metrica"] = ranked.index + 1
    score_columns = ["score_geral", "score_resultado", "score_ataque", "score_defesa", "score_eficiencia", "score_controle", "score_forca_relativa"]
    if "score_disciplina" in ranked.columns:
        score_columns.append("score_disciplina")
    if "tendencia_ranking" in ranked.columns:
        score_columns.append("tendencia_ranking")
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
    effective_weights = weights if weights is not None else TEAM_SCORE_WEIGHTS
    # Média entre os times (todos compartilham a mesma maturidade do Elo
    # dentro de um mesmo snapshot — só varia se algum time tiver jogado mais
    # rodadas que outros) para uma explicação representativa do ranking inteiro.
    avg_resultado = ranked["peso_efetivo_resultado"].mean() if "peso_efetivo_resultado" in ranked.columns else None
    avg_forca_relativa = ranked["peso_efetivo_forca_relativa"].mean() if "peso_efetivo_forca_relativa" in ranked.columns else None
    explanation = _team_score_explanation(effective_weights, avg_resultado, avg_forca_relativa)
    return f"# Ranking de selecoes - {title.title()}\n\nAtualizado em `{utc_now_iso()}`.\n\n{nav}\n\n{explanation}\n\n{display.to_markdown(index=False)}\n"


def _render_team_style_table(team_scores: pd.DataFrame) -> str:
    """Pagina de estilo de jogo: tabela COMPARATIVA, nao ranking ordenado.
    Estilo nao e melhor/pior, entao a ordenacao default e por nome — o leitor
    compara assinaturas, nao busca um 'campeao de estilo'."""
    nav = _team_rankings_nav(TEAM_STYLE_PAGE[0])
    if "estilo_jogo" not in team_scores.columns:
        return f"# Estilo de jogo das selecoes\n\n{nav}\n\nDados de estilo ainda nao disponiveis.\n"
    ranked = team_scores.sort_values("team").reset_index(drop=True)
    rows = []
    for _, row in ranked.iterrows():
        rows.append([
            _team_link(row["team"], row.get("team_slug")),
            row.get("estilo_jogo", ""),
            f"{float(row.get('estilo_posse', 50)):.0f}",
            f"{float(row.get('estilo_pressao', 50)):.0f}",
            f"{float(row.get('estilo_verticalidade', 50)):.0f}",
            f"{float(row.get('estilo_largura', 50)):.0f}",
            row.get("nivel_evidencia", ""),
        ])
    table = _markdown_table(
        rows,
        ["selecao", "estilo", "construcao", "recuperacao", "chegada", "largura", "evidencia"],
    )
    return f"""# Estilo de jogo das selecoes

Atualizado em `{utc_now_iso()}`.

{nav}

Metrica DESCRITIVA (nao avaliativa): caracteriza COMO cada selecao joga, nao quao bem. Cada eixo e um z-score 0-100 relativo ao torneio (50 = na media):

- **Construcao** (alto): joga na posse, muito passe e precisao — vs. jogo direto/vertical (baixo).
- **Recuperacao** (alto): pressiona alto, recupera no campo do adversario — vs. bloco baixo/reativo (baixo).
- **Chegada ao ataque** (alto): vertical, chuta e progride rapido — vs. ataque paciente (baixo).
- **Largura** (alto): ataca pelas pontas (cruzamentos) — vs. jogo interior, por dribles e passes-chave (baixo).

A flag `estilo` e escolhida de uma lista fixa de arquetipos (Toque e Posse, Ofensivo, Drible e Individual, Defensivo, Contra-ataque, Jogo pelas Pontas, Pressao Alta) — cada time recebe a do arquetipo que mais COMBINA com as estatisticas dele. Os 4 eixos abaixo sao ingredientes da classificacao. So vira `Equilibrado` quando nenhum arquetipo combina de fato. A flag e provisoria com poucos jogos (reflete o que o time FEZ, nao a fama) e se firma conforme o torneio avanca. Ordenado por nome — estilo nao e ranking.

{table}
"""


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


# Templates de explicacao por componente — o peso exibido entre parenteses
# e preenchido dinamicamente a partir dos pesos EFETIVOS daquele momento
# (calibrados pela regressao + ajustados pela maturidade do Elo), nao um
# numero fixo no texto, porque os pesos mudam a cada calibracao.
_COMPONENT_EXPLANATION_TEMPLATES = {
    "score_resultado": "aproveitamento de pontos ponderado pela forca do adversario no momento do jogo — empatar com um time forte vale mais que empatar com um fraco ({peso} da nota geral)",
    "score_ataque": "gols, chutes no alvo, key passes e expected assists por jogo (ESPN + 365Scores), ponderados por quao solida e a defesa historica do adversario ({peso})",
    "score_defesa": "gols sofridos, chutes no alvo sofridos e jogos sem tomar gol, ponderados por quanto volume o adversario criou — defesa pouco testada (dominio total do proprio time) e atraida para o neutro, ja que nao foi testada ({peso})",
    "score_eficiencia": "conversao de chutes em gol, chutes no alvo por chute e key passes por jogo (365Scores) — criar chances que nao terminam em gol tambem conta como eficiencia ofensiva, nao so a finalizacao ({peso})",
    "score_controle": "posse, passes, precisao e posse liquida (dribbles ganhos / posse perdida, via 365Scores) — estilo de jogo, peso baixo, mesmo ajuste de adversario ({peso})",
    "score_forca_relativa": "rating Elo ponderado por desempenho (gols, chutes no alvo, posse) — vencer um adversario forte vale mais que vencer um fraco. Peso escalado pela maturidade do Elo: no inicio do torneio, com todos os times no rating inicial, ainda nao ha forca relativa real para medir ({peso})",
}
_COMPONENT_DISCIPLINA_EXPLANATION = (
    "faltas, cartoes amarelos e vermelhos por jogo — nota alta = time disciplinado; vermelho pesa mais "
    "que amarelo por ter impacto imediato e irreversivel no jogo. Nao entra na nota geral — e informativo"
)
_COMPONENT_ESTILO_EXPLANATION = (
    "flag DESCRITIVA de como o time joga (nao quao bem): de uma lista de arquetipos "
    "(Toque e Posse, Ofensivo, Drible e Individual, Defensivo, Contra-ataque, Jogo pelas Pontas, "
    "Pressao Alta), o time recebe a que mais combina com as estatisticas dele. Os 4 eixos abaixo "
    "(posse, pressao, verticalidade, largura) sao os ingredientes. Reflete o que o time FEZ, nao a "
    "fama — provisorio com poucos jogos. Nao entra na nota geral"
)


def _format_weight_pct(weights: dict[str, float], key: str) -> str:
    value = weights.get(key)
    return f"{value * 100:.0f}%" if value is not None else "—"


def _component_explanations(
    weights: dict[str, float],
    effective_resultado: float | None = None,
    effective_forca_relativa: float | None = None,
) -> dict[str, str]:
    """``effective_resultado``/``effective_forca_relativa`` sobrescrevem o
    peso de design quando vêm da própria linha do time (colunas
    peso_efetivo_resultado/peso_efetivo_forca_relativa de build_team_scores)
    — esses dois variam conforme a maturidade do Elo, diferente dos 4
    componentes de processo, que usam o mesmo peso calibrado para todos.
    """
    resultado_pct = f"{effective_resultado * 100:.0f}%" if effective_resultado is not None else _format_weight_pct(weights, "score_resultado")
    forca_pct = f"{effective_forca_relativa * 100:.0f}%" if effective_forca_relativa is not None else _format_weight_pct(weights, "score_forca_relativa")
    return {
        "Resultado": _COMPONENT_EXPLANATION_TEMPLATES["score_resultado"].format(peso=resultado_pct),
        "Ataque": _COMPONENT_EXPLANATION_TEMPLATES["score_ataque"].format(peso=_format_weight_pct(weights, "score_ataque")),
        "Defesa": _COMPONENT_EXPLANATION_TEMPLATES["score_defesa"].format(peso=_format_weight_pct(weights, "score_defesa")),
        "Eficiencia": _COMPONENT_EXPLANATION_TEMPLATES["score_eficiencia"].format(peso=_format_weight_pct(weights, "score_eficiencia")),
        "Controle": _COMPONENT_EXPLANATION_TEMPLATES["score_controle"].format(peso=_format_weight_pct(weights, "score_controle")),
        "Forca Relativa": _COMPONENT_EXPLANATION_TEMPLATES["score_forca_relativa"].format(peso=forca_pct),
        "Disciplina": _COMPONENT_DISCIPLINA_EXPLANATION,
        "Estilo": _COMPONENT_ESTILO_EXPLANATION,
    }


def _render_team_report(
    team: pd.Series,
    matches: pd.DataFrame,
    player_events: pd.DataFrame,
    total_teams: int,
    team_slug_by_name: dict[str, str],
    recent: pd.Series | None = None,
    history: pd.DataFrame | None = None,
    group_table: pd.DataFrame | None = None,
    weights: dict[str, float] | None = None,
) -> str:
    generated_at = utc_now_iso()
    jogos = int(team.get("jogos", 0) or 0)
    effective_weights = weights if weights is not None else TEAM_SCORE_WEIGHTS
    explanations = _component_explanations(
        effective_weights,
        effective_resultado=team.get("peso_efetivo_resultado"),
        effective_forca_relativa=team.get("peso_efetivo_forca_relativa"),
    )

    # Cada componente aparece com nota + explicacao do calculo juntos — sem
    # repetir a mesma explicacao numa secao "Como ler" e numa "Auditoria"
    # separadas (eram redundantes e o usuario apontou a confusao).
    components = _markdown_table(
        [
            ["Resultado", team.get("score_resultado", 0), explanations["Resultado"]],
            ["Ataque", team.get("score_ataque", 0), explanations["Ataque"]],
            ["Defesa", team.get("score_defesa", 0), explanations["Defesa"]],
            ["Eficiencia", team.get("score_eficiencia", 0), explanations["Eficiencia"]],
            ["Controle", team.get("score_controle", 0), explanations["Controle"]],
            ["Forca Relativa", team.get("score_forca_relativa", 0), explanations["Forca Relativa"]],
            ["Disciplina", team.get("score_disciplina", 0), explanations["Disciplina"]],
        ],
        ["componente", "nota", "como e calculado"],
    )

    evolution_section = _team_score_evolution(history)
    style_section = _team_style_section(team, explanations["Estilo"])

    gols_label = "gols marcados"
    gols_value: Any = _format_value(team.get("gols_pro", 0))
    if jogos > 1:
        # mediana so agrega informacao a partir de 2+ jogos — com 1 jogo
        # ela e identica ao total e mostrar os dois e redundante.
        gols_label = "gols marcados (mediana por jogo)"
        gols_value = f"{_format_value(team.get('gols_pro', 0))} ({_format_value(team.get('mediana_gols_pro'))})"
    amarelos = int(team.get("amarelos", 0) or 0)
    vermelhos = int(team.get("vermelhos", 0) or 0)
    faltas = int(team.get("faltas", 0) or 0)
    cartoes_str = f"{amarelos} amarelo{'s' if amarelos != 1 else ''}"
    if vermelhos:
        cartoes_str += f", {vermelhos} vermelho{'s' if vermelhos != 1 else ''}"
    summary_rows = [
        ["jogos disputados", jogos],
        ["pontos", _format_value(team.get("points", 0))],
        ["saldo de gols", _format_value(team.get("saldo_gols", 0))],
        [gols_label, gols_value],
        ["gols sofridos", _format_value(team.get("gols_contra", 0))],
        ["aproveitamento de pontos", _percent(team.get("aproveitamento"))],
        ["faltas cometidas", faltas],
        ["cartoes", cartoes_str],
        ["disciplina (ranking)", f"{_format_value(team.get('ranking_disciplina'))} de {total_teams}"],
        ["rating Elo", f"{team.get('elo_rating', 1500):.0f} (1500 = neutro)"],
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
    group_section = _format_group_standings(group_table, str(team.get("team", "")), team_slug_by_name)
    tactics_section = _format_tactics(matches)
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

A nota geral combina os seis componentes abaixo por media ponderada (pesos entre parenteses), calculados via z-score entre as selecoes do torneio — isso preserva a distancia real de desempenho, nao so o ranking ordinal. Resultado e Forca Relativa tem peso de design fixo (35% e 15%, este ultimo escalado pela maturidade do Elo — ver nota abaixo); Ataque, Defesa, Eficiencia e Controle sao recalibrados a cada jogo novo via regressao (RidgeCV) contra saldo de gols real, usando estatisticas brutas de processo (chutes, posse, key passes etc.) — ver [[reports/rankings/calibracao_pesos\\|historico de calibracao]] para a evolucao dos pesos sugeridos.

Maturidade do Elo: no inicio do torneio todos os times comecam no mesmo rating (1500) — vencer ainda nao prova forca relativa de fato, e o mesmo sinal que Resultado ja capta. O peso de Forca Relativa cresce organicamente conforme os ratings se diferenciam de verdade (medido pela variancia real do Elo vs. o teto teorico para o numero de jogos disputados); a fracao "nao ganha" e transferida para Resultado.

{components}
{style_section}{evolution_section}
## Resumo acumulado

{summary}

## Jogos

{match_table}
{tactics_section}{group_section}
## Jogadores

{players_section}
"""


def _format_tactics(matches: pd.DataFrame) -> str:
    if matches.empty or "formation" not in matches.columns:
        return ""
    has_formation = matches["formation"].notna()
    if not has_formation.any():
        return ""
    rows = []
    for formation, group in matches[has_formation].groupby("formation"):
        vitorias = int((group["result"] == "vitoria").sum())
        empates = int((group["result"] == "empate").sum())
        derrotas = int((group["result"] == "derrota").sum())
        jogos = len(group)
        rows.append([formation, jogos, vitorias, empates, derrotas])
    table = _markdown_table(rows, ["formacao", "jogos", "V", "E", "D"])
    return f"\n## Esquema Tatico\n\n{table}\n"


def _format_group_standings(group_table: pd.DataFrame | None, team: str, team_slug_by_name: dict[str, str]) -> str:
    """Classificacao do grupo na fase de grupos — contextualiza se o time esta
    avancando ou nao, algo que faltava no relatorio (so mostrava os jogos do
    proprio time, sem comparar com os rivais de grupo)."""
    if group_table is None or group_table.empty:
        return ""
    ordered = group_table.sort_values(["points", "goal_difference", "goals_for"], ascending=False).reset_index(drop=True)
    rows = []
    for position, (_, row) in enumerate(ordered.iterrows(), start=1):
        team_name = str(row["team"])
        label = f"**{_team_link(team_name, team_slug_by_name.get(team_name))}**" if team_name == team else _team_link(team_name, team_slug_by_name.get(team_name))
        rows.append([
            position, label, int(row["played"]), int(row["wins"]), int(row["draws"]), int(row["losses"]),
            int(row["goals_for"]), int(row["goals_against"]), int(row["goal_difference"]), int(row["points"]),
        ])
    table = _markdown_table(rows, ["pos", "selecao", "jogos", "vit", "emp", "der", "gp", "gc", "sg", "pts"])
    group_name = ordered.iloc[0].get("group", "") if not ordered.empty else ""
    return f"""
## Classificacao do Grupo {group_name}

{table}
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


# Eixos de estilo: (coluna, polo alto, polo baixo). Espelha _STYLE_AXIS_LABELS
# em analytics/scores.py, mas com texto mais longo para a tabela do relatorio.
_STYLE_AXES_DISPLAY = [
    ("estilo_posse", "posse", "jogo direto"),
    ("estilo_pressao", "pressao alta", "bloco baixo"),
    ("estilo_verticalidade", "ataque vertical", "ataque paciente"),
    ("estilo_largura", "jogo pelas pontas", "jogo interior"),
]
_STYLE_AXIS_NAMES = {
    "estilo_posse": "Construcao",
    "estilo_pressao": "Recuperacao",
    "estilo_verticalidade": "Chegada ao ataque",
    "estilo_largura": "Largura",
}


def _style_axis_tendency(value: float, high_label: str, low_label: str) -> str:
    """Traduz o eixo (0-100, 50=neutro) em texto: polo + intensidade. Perto de
    50 = sem tendencia clara naquele eixo."""
    distance = abs(value - 50.0)
    if distance < 6:
        return "equilibrado"
    intensity = "forte" if distance >= 18 else "moderado"
    pole = high_label if value >= 50 else low_label
    return f"{pole} ({intensity})"


def _team_style_section(team: pd.Series, explanation: str) -> str:
    """Secao 'Estilo de jogo': o rotulo em destaque + a tabela dos 4 eixos com
    a tendencia de cada um. So aparece se os eixos foram calculados."""
    if "estilo_jogo" not in team.index or pd.isna(team.get("estilo_jogo")):
        return ""
    rows = []
    for col, high_label, low_label in _STYLE_AXES_DISPLAY:
        value = float(team.get(col, 50.0) or 50.0)
        rows.append([
            _STYLE_AXIS_NAMES[col],
            f"{high_label} ↔ {low_label}",
            f"{value:.0f}/100",
            _style_axis_tendency(value, high_label, low_label),
        ])
    table = _markdown_table(rows, ["eixo", "polos", "nota", "tendencia"])
    return f"""
## Estilo de jogo: {team.get('estilo_jogo')}

{explanation}.

{table}

> Eixos relativos ao torneio (50 = na media das selecoes), usados como ingredientes da classificacao. Nao medem qualidade — um time pode jogar muito na posse e ainda assim ir mal. A flag de estilo vem do arquetipo mais proximo; e provisoria com poucos jogos e se firma conforme o torneio avanca.

"""


_RESULT_LABELS = {"vitoria": "vitoria", "empate": "empate", "derrota": "derrota"}


def _team_matches_table(matches: pd.DataFrame, team_slug_by_name: dict[str, str]) -> str:
    """Tabela enxuta: jogo, data, adversario e resultado com placar embutido.
    Estatisticas detalhadas (chutes, posse, etc) ficam no relatorio do jogo —
    quem quiser o detalhe clica no link em vez de ver tudo repetido aqui."""
    if matches.empty:
        return "Nenhum jogo finalizado encontrado."
    display = matches[["match_id", "date", "opponent", "result", "goals_for", "goals_against"]].copy()
    display["match_id"] = display["match_id"].apply(_match_link)
    display["opponent"] = display["opponent"].apply(lambda team: _team_link(team, team_slug_by_name.get(team)))
    display["result"] = display.apply(
        lambda row: f"{_RESULT_LABELS.get(row['result'], row['result'])} {_format_value(row['goals_for'])}x{_format_value(row['goals_against'])}",
        axis=1,
    )
    display = display.drop(columns=["goals_for", "goals_against"]).rename(
        columns={"match_id": "jogo", "date": "data", "opponent": "adversario", "result": "resultado"}
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


def _ranking_trend(team_scores: pd.DataFrame, history: pd.DataFrame) -> pd.Series:
    """Delta de posição no ranking geral entre o snapshot anterior e o atual.

    Retorna série indexada como team_scores com strings tipo '↑3', '↓2' ou '→'.
    No primeiro jogo (sem snapshot anterior) retorna '→' para todos.
    """
    result = pd.Series("→", index=team_scores.index)
    if history is None or history.empty:
        return result

    current_jogos = int(team_scores["jogos"].max()) if "jogos" in team_scores.columns else 0
    if current_jogos < 2:
        return result

    prev = history[history["jogos"] == current_jogos - 1][["team", "score_geral"]].copy()
    if prev.empty:
        return result

    prev["ranking_anterior"] = prev["score_geral"].rank(method="min", ascending=False).astype(int)
    merged = team_scores[["team", "ranking_score_geral"]].merge(prev[["team", "ranking_anterior"]], on="team", how="left")

    def _delta(row: pd.Series) -> str:
        if pd.isna(row.get("ranking_anterior")):
            return "→"
        delta = int(row["ranking_anterior"]) - int(row["ranking_score_geral"])
        if delta > 0:
            return f"↑{delta}"
        if delta < 0:
            return f"↓{abs(delta)}"
        return "→"

    trend = merged.apply(_delta, axis=1)
    trend.index = team_scores.index
    return trend


def _markdown_table(rows: list[list[Any]], columns: list[str]) -> str:
    return pd.DataFrame(rows, columns=columns).to_markdown(index=False)


def _team_rankings_nav(active_slug: str) -> str:
    links = []
    for slug, title in [(s, t) for s, _, t in TEAM_RANKINGS] + [TEAM_STYLE_PAGE]:
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
        "score_forca_relativa": "forca_relativa",
        "score_disciplina": "disciplina",
        "tendencia_ranking": "tendencia",
        "nivel_evidencia": "evidencia",
        "points": "pontos",
    }
    labels[metric] = title.replace(" ", "_")
    return labels


def _team_score_explanation(
    weights: dict[str, float] | None = None,
    effective_resultado: float | None = None,
    effective_forca_relativa: float | None = None,
) -> str:
    w = weights if weights is not None else TEAM_SCORE_WEIGHTS
    p = lambda key: _format_weight_pct(w, key)
    resultado_pct = f"{effective_resultado * 100:.0f}%" if effective_resultado is not None else p("score_resultado")
    forca_pct = f"{effective_forca_relativa * 100:.0f}%" if effective_forca_relativa is not None else p("score_forca_relativa")
    return f"""## Como ler a nota

- **Nota geral**: nota de 0 a 100, media ponderada de seis componentes. Calculados via z-score, preservando distancia absoluta entre selecoes.
- **Resultado** (peso {resultado_pct}): aproveitamento real de pontos. Quem vence mais jogos tem nota mais alta independente do estilo. Peso fixo de design — absorve a fracao de Forca Relativa ainda nao "ganha" pela maturidade do Elo (ver abaixo).
- **Ataque** (peso {p('score_ataque')}): gols, chutes no alvo, key passes e expected assists por jogo (ESPN + 365Scores). Sem chutes totais isolados — mede qualidade, nao volume bruto.
- **Defesa** (peso {p('score_defesa')}): gols sofridos, chutes no alvo sofridos e jogos sem tomar gol.
- **Eficiencia** (peso {p('score_eficiencia')}): conversao de chutes em gol, chutes no alvo por chute e key passes por jogo. Distinto de ataque: ataque mede producao, eficiencia mede aproveitamento — criar chance sem converter tambem conta.
- **Controle** (peso {p('score_controle')}): posse, passes, precisao e posse liquida (dribbles ganhos / posse perdida, via 365Scores). Peso baixo — estilo de jogo nao e determinante de qualidade.
- **Forca relativa** (peso {forca_pct}): rating Elo. O placar real decide a faixa do ajuste — vitoria sempre acima de empate, empate sempre acima de derrota, a hierarquia nunca se inverte. Mas a posicao exata dentro de cada faixa vem do indice de desempenho (gols, chutes no alvo, posse): uma vitoria sofrida (ganhou jogando pior que o adversario) ganha menos rating que uma vitoria dominante com a mesma margem de gols, e o mesmo vale para empates (dominado vs. equilibrado) e derrotas. Contextualiza tambem pelo adversario enfrentado — vencer um time forte vale mais que vencer um fraco, efeito que so aparece a partir do 2o jogo de cada selecao, quando os ratings ja deixaram de ser todos iguais. **O peso exibido aqui ja reflete a maturidade atual do Elo** (cresce conforme os ratings se diferenciam de verdade); o peso de design pleno e {p('score_forca_relativa')}.
- **Disciplina**: faltas, cartoes amarelos e vermelhos por jogo. Nota alta = time disciplinado. Nao entra na nota geral — e informativo.
- **Estilo de jogo**: flag DESCRITIVA (nao avaliativa) de como o time joga, escolhida de uma lista de arquetipos (Toque e Posse, Ofensivo, Drible e Individual, Defensivo, Contra-ataque, Jogo pelas Pontas, Pressao Alta) pelo que mais combina com as estatisticas. Os 4 eixos sao ingredientes. Nao entra na nota geral — estilo nao e melhor/pior.
- **Tendencia**: variacao de posicao no ranking geral em relacao ao jogo anterior (`↑3` subiu 3, `↓2` caiu 2, `→` estavel ou primeiro jogo).
- **Evidencia**: estabilidade da nota (`baixa`, `media`, `alta`). Atinge confianca plena com 3 jogos — os 3 da fase de grupos.

Ataque, Defesa, Eficiencia e Controle sao recalibrados a cada jogo novo finalizado via regressao (RidgeCV) contra saldo de gols real — ver [[reports/rankings/calibracao_pesos\\|historico de calibracao]]. Fontes de dados: ESPN (estatisticas de equipe e jogador desde o inicio do torneio) e 365Scores (enriquecimento com formacao tatica, expected assists, key passes e dribbles ganhos, cobrindo os jogos ja finalizados)."""


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
