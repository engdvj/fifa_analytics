from __future__ import annotations

from typing import Any

import pandas as pd

from fifa_analytics.utils.text import slugify


TEAM_SCORE_WEIGHTS = {
    "score_ataque": 0.30,
    "score_defesa": 0.25,
    "score_controle": 0.20,
    "score_eficiencia": 0.15,
    "score_disciplina": 0.10,
}


def build_team_match_features(matches: pd.DataFrame, team_stats: pd.DataFrame | None = None) -> pd.DataFrame:
    finished = matches[matches["status"] == "finalizado"].copy()
    rows = []
    for _, match in finished.iterrows():
        home_team = match.get("home_team")
        away_team = match.get("away_team")
        home_score = _number(match.get("home_score"))
        away_score = _number(match.get("away_score"))
        if not home_team or not away_team or pd.isna(home_score) or pd.isna(away_score):
            continue
        rows.extend(
            [
                _team_match_row(match, home_team, away_team, home_score, away_score, "home"),
                _team_match_row(match, away_team, home_team, away_score, home_score, "away"),
            ]
        )

    features = pd.DataFrame(rows)
    if features.empty:
        return features

    stats = team_stats.copy() if team_stats is not None and not team_stats.empty else pd.DataFrame()
    if not stats.empty:
        stats = stats.drop(columns=[column for column in ["source_match_id", "source", "collected_at", "dataset_source"] if column in stats.columns])
        features = features.merge(stats, on=["match_id", "team"], how="left", suffixes=("", "_fonte"))

    team_metric_columns = [column for column in ["shots", "shots_on_target", "passes", "possession", "fouls"] if column in features.columns]
    features["team_stats_available"] = features[team_metric_columns].notna().any(axis=1) if team_metric_columns else False

    for column in [
        "goals_for",
        "goals_against",
        "shots",
        "shots_on_target",
        "blocked_shots",
        "passes",
        "accurate_passes",
        "pass_accuracy",
        "possession",
        "corners",
        "fouls",
        "saves",
        "yellow_cards",
        "red_cards",
        "tackles",
        "interceptions",
    ]:
        if column not in features.columns:
            features[column] = 0
        features[column] = pd.to_numeric(features[column], errors="coerce")

    features["shot_accuracy"] = _safe_divide(features["shots_on_target"], features["shots"])
    features["goal_conversion"] = _safe_divide(features["goals_for"], features["shots"])
    features["points"] = features["result"].map({"vitoria": 3, "empate": 1, "derrota": 0}).fillna(0).astype(int)
    features["clean_sheet"] = (features["goals_against"].fillna(0) == 0).astype(int)
    opponent_stats = features[["match_id", "team", "shots", "shots_on_target"]].rename(
        columns={
            "team": "opponent",
            "shots": "shots_against",
            "shots_on_target": "shots_on_target_against",
        }
    )
    features = features.merge(opponent_stats, on=["match_id", "opponent"], how="left")
    features["opponent_stats_available"] = features[["shots_against", "shots_on_target_against"]].notna().any(axis=1)
    features["team_slug"] = features["team"].apply(slugify)
    return features.sort_values(["date", "match_id", "home_away"]).reset_index(drop=True)


def build_team_scores(team_match_features: pd.DataFrame) -> pd.DataFrame:
    if team_match_features.empty:
        return pd.DataFrame()

    aggregations = {
        "match_id": "nunique",
        "points": "sum",
        "goals_for": "sum",
        "goals_against": "sum",
        "shots": "sum",
        "shots_on_target": "sum",
        "blocked_shots": "sum",
        "passes": "sum",
        "accurate_passes": "sum",
        "possession": "mean",
        "pass_accuracy": "mean",
        "corners": "sum",
        "fouls": "sum",
        "saves": "sum",
        "yellow_cards": "sum",
        "red_cards": "sum",
        "clean_sheet": "sum",
        "shots_against": "sum",
        "shots_on_target_against": "sum",
        "team_stats_available": "sum",
        "opponent_stats_available": "sum",
    }
    available = {column: aggregation for column, aggregation in aggregations.items() if column in team_match_features.columns}
    scores = team_match_features.groupby("team", dropna=False).agg(available).reset_index()
    scores = scores.rename(
        columns={
            "match_id": "jogos",
            "goals_for": "gols_pro",
            "goals_against": "gols_contra",
            "shots": "chutes",
            "shots_on_target": "chutes_no_alvo",
            "blocked_shots": "chutes_bloqueados",
            "passes": "passes",
            "accurate_passes": "passes_certos",
            "possession": "posse_media",
            "pass_accuracy": "precisao_passes_media",
            "corners": "escanteios",
            "fouls": "faltas",
            "saves": "defesas",
            "yellow_cards": "amarelos",
            "red_cards": "vermelhos",
            "clean_sheet": "jogos_sem_sofrer_gol",
            "shots_against": "chutes_sofridos",
            "shots_on_target_against": "chutes_no_alvo_sofridos",
            "team_stats_available": "jogos_com_estatisticas",
            "opponent_stats_available": "jogos_com_estatisticas_adversario",
        }
    )
    scores["saldo_gols"] = scores["gols_pro"] - scores["gols_contra"]
    scores["aproveitamento"] = _safe_divide(scores["points"], scores["jogos"] * 3)
    scores["gols_por_jogo"] = _safe_divide(scores["gols_pro"], scores["jogos"])
    scores["gols_contra_por_jogo"] = _safe_divide(scores["gols_contra"], scores["jogos"])
    scores["chutes_por_jogo"] = _safe_divide(scores["chutes"], scores["jogos"])
    scores["chutes_no_alvo_por_jogo"] = _safe_divide(scores["chutes_no_alvo"], scores["jogos"])
    scores["gols_por_chute"] = _safe_divide(scores["gols_pro"], scores["chutes"])
    scores["chutes_no_alvo_por_chute"] = _safe_divide(scores["chutes_no_alvo"], scores["chutes"])
    scores["passes_por_jogo"] = _safe_divide(scores["passes"], scores["jogos"])
    scores["faltas_por_jogo"] = _safe_divide(scores["faltas"], scores["jogos"])
    scores["amarelos_por_jogo"] = _safe_divide(scores["amarelos"], scores["jogos"])
    scores["vermelhos_por_jogo"] = _safe_divide(scores["vermelhos"], scores["jogos"])
    scores["clean_sheet_rate"] = _safe_divide(scores["jogos_sem_sofrer_gol"], scores["jogos"])
    scores["chutes_sofridos_por_jogo"] = _safe_divide(scores["chutes_sofridos"], scores["jogos"])
    scores["chutes_no_alvo_sofridos_por_jogo"] = _safe_divide(scores["chutes_no_alvo_sofridos"], scores["jogos"])

    scores["score_ataque_bruto"] = _mean_score(
        [
            _normalize(scores["gols_por_jogo"]),
            _normalize(scores["chutes_por_jogo"]),
            _normalize(scores["chutes_no_alvo_por_jogo"]),
        ]
    )
    scores["score_defesa_bruto"] = _mean_score(
        [
            _normalize(scores["gols_contra_por_jogo"], lower_is_better=True),
            _normalize(scores["chutes_sofridos_por_jogo"], lower_is_better=True),
            _normalize(scores["chutes_no_alvo_sofridos_por_jogo"], lower_is_better=True),
            _normalize(scores["clean_sheet_rate"]),
        ]
    )
    scores["score_controle_bruto"] = _mean_score(
        [
            _normalize(scores["posse_media"]),
            _normalize(scores["passes_por_jogo"]),
            _normalize(scores["precisao_passes_media"]),
        ]
    )
    scores["score_eficiencia_bruto"] = _mean_score(
        [
            _normalize(scores["gols_por_chute"]),
            _normalize(scores["chutes_no_alvo_por_chute"]),
        ]
    )
    scores["score_disciplina_bruto"] = _mean_score(
        [
            _normalize(scores["faltas_por_jogo"], lower_is_better=True),
            _normalize(scores["amarelos_por_jogo"], lower_is_better=True),
            _normalize(scores["vermelhos_por_jogo"], lower_is_better=True),
        ]
    )
    scores["confianca_amostra"] = _sample_confidence(scores["jogos"])
    scores["confianca_dados_time"] = _safe_divide(scores["jogos_com_estatisticas"], scores["jogos"]).clip(0, 1)
    scores["confianca_dados_defesa"] = _safe_divide(scores["jogos_com_estatisticas_adversario"], scores["jogos"]).clip(0, 1)
    scores["confianca_teste_defensivo"] = _defensive_workload_confidence(scores)
    scores["confianca_ataque"] = (scores["confianca_amostra"] * scores["confianca_dados_time"]).clip(0, 1)
    scores["confianca_defesa"] = (
        scores["confianca_amostra"] * scores["confianca_dados_defesa"] * (0.75 + 0.25 * scores["confianca_teste_defensivo"])
    ).clip(0, 1)
    scores["confianca_controle"] = (scores["confianca_amostra"] * scores["confianca_dados_time"]).clip(0, 1)
    scores["confianca_eficiencia"] = (scores["confianca_amostra"] * scores["confianca_dados_time"]).clip(0, 1)
    scores["confianca_disciplina"] = (scores["confianca_amostra"] * scores["confianca_dados_time"]).clip(0, 1)
    scores["score_ataque"] = _apply_confidence(scores["score_ataque_bruto"], scores["confianca_ataque"])
    scores["score_defesa"] = _apply_confidence(scores["score_defesa_bruto"], scores["confianca_defesa"])
    scores["score_controle"] = _apply_confidence(scores["score_controle_bruto"], scores["confianca_controle"])
    scores["score_eficiencia"] = _apply_confidence(scores["score_eficiencia_bruto"], scores["confianca_eficiencia"])
    scores["score_disciplina"] = _apply_confidence(scores["score_disciplina_bruto"], scores["confianca_disciplina"])
    scores["confianca_score"] = _weighted_score(
        scores,
        {
            "confianca_ataque": 0.30,
            "confianca_defesa": 0.25,
            "confianca_controle": 0.20,
            "confianca_eficiencia": 0.15,
            "confianca_disciplina": 0.10,
        },
    )
    scores["score_geral"] = _weighted_score(scores, TEAM_SCORE_WEIGHTS)
    scores["team_slug"] = scores["team"].apply(slugify)
    scores = _add_rank(scores, "score_geral", "ranking_score_geral")
    score_columns = [column for column in scores.columns if column.startswith("score_")]
    scores[score_columns] = scores[score_columns].round(1)
    confidence_columns = [column for column in scores.columns if column.startswith("confianca_")]
    scores[confidence_columns] = scores[confidence_columns].round(2)
    scores["nivel_evidencia"] = scores["confianca_score"].apply(_evidence_level)
    return scores.sort_values(["score_geral", "points", "saldo_gols"], ascending=[False, False, False]).reset_index(drop=True)


def build_player_match_features(player_stats: pd.DataFrame, lineups: pd.DataFrame | None = None) -> pd.DataFrame:
    if player_stats.empty:
        return pd.DataFrame()
    features = player_stats.copy()
    for column in [
        "minutes_played",
        "goals",
        "assists",
        "shots",
        "shots_on_target",
        "passes",
        "tackles",
        "interceptions",
        "saves",
        "yellow_cards",
        "red_cards",
        "fouls_committed",
        "fouls_drawn",
    ]:
        if column not in features.columns:
            features[column] = 0
        features[column] = pd.to_numeric(features[column], errors="coerce").fillna(0)

    if lineups is not None and not lineups.empty and {"match_id", "team", "player_name"}.issubset(lineups.columns):
        lineup_columns = [column for column in ["match_id", "team", "player_name", "position", "is_starter", "formation"] if column in lineups.columns]
        lineup_info = lineups[lineup_columns].drop_duplicates(["match_id", "team", "player_name"])
        features = features.merge(lineup_info, on=["match_id", "team", "player_name"], how="left")

    features["participacoes_gol"] = features["goals"] + features["assists"]
    features["shot_accuracy"] = _safe_divide(features["shots_on_target"], features["shots"])
    features["impacto_partida"] = (
        features["goals"] * 5
        + features["assists"] * 3
        + features["shots_on_target"] * 1.5
        + features["shots"]
        + features["saves"] * 1.2
        + features["tackles"] * 0.4
        + features["interceptions"] * 0.4
        + features["fouls_drawn"] * 0.2
        - features["yellow_cards"] * 0.5
        - features["red_cards"] * 2
    ).clip(lower=0)
    features["perfil"] = features.apply(_player_profile, axis=1)
    features["player_slug"] = features.apply(lambda row: slugify(f"{row.get('player_name')}_{row.get('team')}"), axis=1)
    return features.sort_values(["team", "player_name", "match_id"]).reset_index(drop=True)


def build_player_scores(player_match_features: pd.DataFrame) -> pd.DataFrame:
    if player_match_features.empty:
        return pd.DataFrame()

    group_columns = ["player_slug", "player_name", "team"]
    aggregations = {
        "match_id": "nunique",
        "minutes_played": "sum",
        "goals": "sum",
        "assists": "sum",
        "shots": "sum",
        "shots_on_target": "sum",
        "passes": "sum",
        "tackles": "sum",
        "interceptions": "sum",
        "saves": "sum",
        "yellow_cards": "sum",
        "red_cards": "sum",
        "participacoes_gol": "sum",
        "impacto_partida": "sum",
        "perfil": _mode_or_first,
    }
    available = {column: aggregation for column, aggregation in aggregations.items() if column in player_match_features.columns}
    scores = player_match_features.groupby(group_columns, dropna=False).agg(available).reset_index()
    scores = scores.rename(columns={"match_id": "jogos", "impacto_partida": "impacto_total"})
    scores["impacto_por_jogo"] = _safe_divide(scores["impacto_total"], scores["jogos"])
    scores["gols_por_jogo"] = _safe_divide(scores["goals"], scores["jogos"])
    scores["assistencias_por_jogo"] = _safe_divide(scores["assists"], scores["jogos"])
    scores["chutes_no_alvo_por_chute"] = _safe_divide(scores["shots_on_target"], scores["shots"])
    scores["score_acumulado_bruto"] = _normalize(scores["impacto_total"])
    scores["score_medio_bruto"] = _normalize(scores["impacto_por_jogo"])
    scores["score_ofensivo_bruto"] = _normalize(scores["goals"] * 5 + scores["assists"] * 3 + scores["shots_on_target"] * 1.5 + scores["shots"])
    scores["score_goleiro_bruto"] = _normalize(scores["saves"])
    scores["score_disciplina_bruto"] = _mean_score(
        [
            _normalize(_safe_divide(scores["yellow_cards"], scores["jogos"]), lower_is_better=True),
            _normalize(_safe_divide(scores["red_cards"], scores["jogos"]), lower_is_better=True),
        ]
    )
    scores["confianca_amostra"] = _sample_confidence(scores["jogos"])
    scores["score_acumulado"] = _apply_confidence(scores["score_acumulado_bruto"], scores["confianca_amostra"])
    scores["score_medio"] = _apply_confidence(scores["score_medio_bruto"], scores["confianca_amostra"])
    scores["score_ofensivo"] = _apply_confidence(scores["score_ofensivo_bruto"], scores["confianca_amostra"])
    scores["score_goleiro"] = _apply_confidence(scores["score_goleiro_bruto"], scores["confianca_amostra"])
    scores["score_disciplina"] = _apply_confidence(scores["score_disciplina_bruto"], scores["confianca_amostra"])
    scores["score_geral"] = scores["score_medio"].fillna(0) * 0.6 + scores["score_acumulado"].fillna(0) * 0.4
    score_columns = [column for column in scores.columns if column.startswith("score_")]
    scores[score_columns] = scores[score_columns].round(1)
    scores["confianca_amostra"] = scores["confianca_amostra"].round(2)
    scores["nivel_evidencia"] = scores["confianca_amostra"].apply(_evidence_level)
    scores = _add_rank(scores, "score_geral", "ranking_score_geral")
    return scores.sort_values(["score_geral", "impacto_total"], ascending=[False, False]).reset_index(drop=True)


def _team_match_row(match: pd.Series, team: str, opponent: str, goals_for: float, goals_against: float, home_away: str) -> dict[str, Any]:
    if goals_for > goals_against:
        result = "vitoria"
    elif goals_for < goals_against:
        result = "derrota"
    else:
        result = "empate"
    return {
        "match_id": match.get("canonical_match_id") or match.get("match_id"),
        "date": match.get("date"),
        "group": match.get("group"),
        "stage": match.get("stage"),
        "round": match.get("round"),
        "team": team,
        "opponent": opponent,
        "home_away": home_away,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "result": result,
    }


def _safe_divide(numerator: Any, denominator: Any) -> pd.Series:
    numerator_series = pd.to_numeric(pd.Series(numerator), errors="coerce").astype(float)
    if isinstance(denominator, pd.Series):
        denominator_series = pd.to_numeric(denominator, errors="coerce").astype(float)
        denominator_series = denominator_series.reindex(numerator_series.index)
    else:
        denominator_series = pd.Series(float(denominator), index=numerator_series.index)
    denominator_series = denominator_series.replace(0, pd.NA)
    return (numerator_series / denominator_series).fillna(0)


def _normalize(values: pd.Series, lower_is_better: bool = False) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").fillna(0).astype(float)
    minimum = numeric.min()
    maximum = numeric.max()
    if maximum == minimum:
        if lower_is_better and maximum == 0:
            return pd.Series(100.0, index=numeric.index)
        return pd.Series(100.0 if maximum > 0 else 0.0, index=numeric.index)
    normalized = (numeric - minimum) / (maximum - minimum) * 100
    if lower_is_better:
        normalized = 100 - normalized
    return normalized.clip(lower=0, upper=100)


def _sample_confidence(games: pd.Series, full_confidence_games: int = 3) -> pd.Series:
    numeric = pd.to_numeric(games, errors="coerce").fillna(0).clip(lower=0)
    return (0.55 + (numeric.clip(upper=full_confidence_games) / full_confidence_games) * 0.45).clip(0, 1)


def _defensive_workload_confidence(scores: pd.DataFrame) -> pd.Series:
    shots_reference = _positive_mean(scores["chutes_sofridos_por_jogo"])
    target_reference = _positive_mean(scores["chutes_no_alvo_sofridos_por_jogo"])
    shots_ratio = (scores["chutes_sofridos_por_jogo"] / shots_reference).clip(lower=0, upper=1) if shots_reference else 0
    target_ratio = (
        (scores["chutes_no_alvo_sofridos_por_jogo"] / target_reference).clip(lower=0, upper=1) if target_reference else 0
    )
    return _mean_score([pd.Series(shots_ratio, index=scores.index), pd.Series(target_ratio, index=scores.index)]).clip(0, 1)


def _positive_mean(values: pd.Series) -> float:
    positive = pd.to_numeric(values, errors="coerce")
    positive = positive[positive > 0]
    return float(positive.mean()) if not positive.empty else 0.0


def _apply_confidence(raw_score: pd.Series, confidence: pd.Series, neutral: float | None = None) -> pd.Series:
    raw = pd.to_numeric(raw_score, errors="coerce").fillna(0)
    confidence = pd.to_numeric(confidence, errors="coerce").fillna(0).clip(0, 1)
    neutral_value = float(raw.median()) if neutral is None else neutral
    return raw * confidence + neutral_value * (1 - confidence)


def _evidence_level(value: Any) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0).iloc[0]
    if numeric >= 0.90:
        return "alta"
    if numeric >= 0.75:
        return "media"
    return "baixa"


def _mean_score(scores: list[pd.Series]) -> pd.Series:
    frame = pd.concat(scores, axis=1)
    return frame.mean(axis=1).fillna(0)


def _weighted_score(frame: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    weighted_parts = []
    used_weights = []
    for column, weight in weights.items():
        if column in frame.columns:
            weighted_parts.append(frame[column].fillna(0) * weight)
            used_weights.append(weight)
    if not weighted_parts:
        return pd.Series(0.0, index=frame.index)
    return sum(weighted_parts) / sum(used_weights)


def _add_rank(frame: pd.DataFrame, score_column: str, rank_column: str) -> pd.DataFrame:
    ranked = frame.copy()
    ranked[rank_column] = ranked[score_column].rank(method="min", ascending=False).astype(int)
    return ranked


def _player_profile(row: pd.Series) -> str:
    position = str(row.get("position") or "").upper()
    if position in {"G", "GK"} or row.get("saves", 0) > 0:
        return "goleiro"
    if row.get("goals", 0) > 0 or row.get("assists", 0) > 0 or row.get("shots", 0) > 0:
        return "linha_ofensivo"
    if row.get("tackles", 0) > 0 or row.get("interceptions", 0) > 0:
        return "linha_defensivo"
    return "linha"


def _mode_or_first(values: pd.Series) -> Any:
    clean = values.dropna()
    if clean.empty:
        return None
    mode = clean.mode()
    return mode.iloc[0] if not mode.empty else clean.iloc[0]


def _number(value: Any) -> float | None:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(converted) else float(converted)
