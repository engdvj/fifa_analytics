from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from fifa_analytics.utils.text import slugify

# ---------------------------------------------------------------------------
# Pesos do score de seleções
# Defesa vale mais que ataque: um gol sofrido é mais difícil de recuperar
# do que um gol marcado. Eficiência mede qualidade do ataque, não volume.
# Controle é estilo de jogo — mantido com peso baixo, não é determinante.
# ---------------------------------------------------------------------------
TEAM_SCORE_WEIGHTS = {
    "score_resultado": 0.40,
    "score_ataque": 0.20,
    "score_defesa": 0.25,
    "score_eficiencia": 0.10,
    "score_controle": 0.05,
}

# Posições ESPN → perfil interno
# Inclui tanto os códigos padrão (GK, CB...) quanto os que aparecem nos dados reais
# da ESPN Copa 2026 (G, CD-L, CD-R, DM, AM-L, CF-L, SUB...)
_POSITION_TO_PROFILE: dict[str, str] = {
    # Goleiro
    "GK": "goleiro", "G": "goleiro",
    # Defensor — zagueiros, laterais, volantes (sem produção ofensiva esperada)
    "CB": "defensor", "CD": "defensor", "CD-L": "defensor", "CD-R": "defensor",
    "SW": "defensor",
    "RB": "defensor", "LB": "defensor", "RWB": "defensor", "LWB": "defensor",
    "DM": "defensor", "D": "defensor",
    # Meia — centroavante criativo e meias de todos os tipos
    "CDM": "meio", "CM": "meio", "CM-L": "meio", "CM-R": "meio",
    "CAM": "meio", "AM": "meio", "AM-L": "meio", "AM-R": "meio",
    "RM": "meio", "LM": "meio", "M": "meio", "MF": "meio",
    # Atacante — pontas, centroavantes, segundos atacantes
    "RW": "atacante", "LW": "atacante",
    "CF": "atacante", "CF-L": "atacante", "CF-R": "atacante",
    "ST": "atacante", "SS": "atacante",
    "F": "atacante", "LF": "atacante", "RF": "atacante",
}


# ---------------------------------------------------------------------------
# Features por partida — seleções
# ---------------------------------------------------------------------------

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
        rows.extend([
            _team_match_row(match, home_team, away_team, home_score, away_score, "home"),
            _team_match_row(match, away_team, home_team, away_score, home_score, "away"),
        ])

    features = pd.DataFrame(rows)
    if features.empty:
        return features

    stats = team_stats.copy() if team_stats is not None and not team_stats.empty else pd.DataFrame()
    if not stats.empty:
        drop = [c for c in ["source_match_id", "source", "collected_at", "dataset_source"] if c in stats.columns]
        stats = stats.drop(columns=drop)
        features = features.merge(stats, on=["match_id", "team"], how="left", suffixes=("", "_fonte"))

    process_cols = ["shots", "shots_on_target", "passes", "possession", "fouls"]
    available_process = [c for c in process_cols if c in features.columns]
    features["team_stats_available"] = features[available_process].notna().any(axis=1) if available_process else False

    for column in [
        "goals_for", "goals_against", "shots", "shots_on_target", "blocked_shots",
        "passes", "accurate_passes", "pass_accuracy", "possession", "corners",
        "fouls", "saves", "yellow_cards", "red_cards", "tackles", "interceptions",
    ]:
        if column not in features.columns:
            features[column] = 0
        features[column] = pd.to_numeric(features[column], errors="coerce")

    features["shot_accuracy"] = _safe_divide(features["shots_on_target"], features["shots"])
    features["goal_conversion"] = _safe_divide(features["goals_for"], features["shots"])
    features["points"] = features["result"].map({"vitoria": 3, "empate": 1, "derrota": 0}).fillna(0).astype(int)
    features["clean_sheet"] = (features["goals_against"].fillna(0) == 0).astype(int)

    opponent_stats = features[["match_id", "team", "shots", "shots_on_target"]].rename(columns={
        "team": "opponent",
        "shots": "shots_against",
        "shots_on_target": "shots_on_target_against",
    })
    features = features.merge(opponent_stats, on=["match_id", "opponent"], how="left")
    features["opponent_stats_available"] = features[["shots_against", "shots_on_target_against"]].notna().any(axis=1)
    features["team_slug"] = features["team"].apply(slugify)
    return features.sort_values(["date", "match_id", "home_away"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Forma recente
# ---------------------------------------------------------------------------

def build_team_recent_form(team_match_features: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Retorna métricas dos últimos N jogos por seleção.

    Usa a coluna `date` para ordenar. Quando não há data disponível, mantém
    a ordem de inserção. Retorna uma linha por seleção com colunas prefixadas
    por `forma_` para não colidir com os acumulados de build_team_scores.
    """
    if team_match_features.empty:
        return pd.DataFrame()

    has_date = "date" in team_match_features.columns and team_match_features["date"].notna().any()
    sort_col = "date" if has_date else "match_id"

    rows = []
    for team, group in team_match_features.groupby("team", dropna=False):
        recent = group.sort_values(sort_col, ascending=True).tail(n)
        jogos = len(recent)
        pontos = int(recent["points"].sum()) if "points" in recent.columns else 0
        vitorias = int((recent["result"] == "vitoria").sum()) if "result" in recent.columns else 0
        empates = int((recent["result"] == "empate").sum()) if "result" in recent.columns else 0
        derrotas = int((recent["result"] == "derrota").sum()) if "result" in recent.columns else 0
        gols_pro = float(recent["goals_for"].sum()) if "goals_for" in recent.columns else 0.0
        gols_contra = float(recent["goals_against"].sum()) if "goals_against" in recent.columns else 0.0
        aproveitamento = pontos / (jogos * 3) if jogos > 0 else 0.0
        # Sequência textual: V/E/D dos últimos jogos (mais recente à direita)
        if "result" in recent.columns:
            seq = "".join(
                "V" if r == "vitoria" else ("E" if r == "empate" else "D")
                for r in recent["result"]
            )
        else:
            seq = ""
        rows.append({
            "team": team,
            "forma_jogos": jogos,
            "forma_pontos": pontos,
            "forma_vitorias": vitorias,
            "forma_empates": empates,
            "forma_derrotas": derrotas,
            "forma_gols_pro": gols_pro,
            "forma_gols_contra": gols_contra,
            "forma_saldo_gols": gols_pro - gols_contra,
            "forma_aproveitamento": round(aproveitamento, 3),
            "forma_score": round(_zscore_to_100(pd.Series([aproveitamento])).iloc[0], 1),
            "forma_sequencia": seq,
            "forma_n": n,
        })

    result = pd.DataFrame(rows)
    # forma_score normalizado entre todas as seleções (não por time isolado)
    if len(result) > 1:
        result["forma_score"] = _zscore_to_100(result["forma_aproveitamento"]).round(1)
    return result.sort_values("forma_aproveitamento", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Score de seleções
# ---------------------------------------------------------------------------

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
    available = {c: agg for c, agg in aggregations.items() if c in team_match_features.columns}
    scores = team_match_features.groupby("team", dropna=False).agg(available).reset_index()
    scores = scores.rename(columns={
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
    })

    # Métricas por jogo
    scores["saldo_gols"] = scores["gols_pro"] - scores["gols_contra"]
    scores["aproveitamento"] = _safe_divide(scores["points"], scores["jogos"] * 3)
    scores["gols_por_jogo"] = _safe_divide(scores["gols_pro"], scores["jogos"])
    scores["gols_contra_por_jogo"] = _safe_divide(scores["gols_contra"], scores["jogos"])
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

    # --- Componentes via z-score (preserva distância absoluta entre times) ---
    # score_resultado: resultado real — aproveitamento normalizado no torneio
    scores["score_resultado"] = _zscore_to_100(scores["aproveitamento"])

    # score_ataque: volume ofensivo de qualidade (chutes no alvo + gols, sem chutes totais)
    scores["score_ataque"] = _mean_score([
        _zscore_to_100(scores["gols_por_jogo"]),
        _zscore_to_100(scores["chutes_no_alvo_por_jogo"]),
    ])

    # score_defesa: solidez defensiva
    scores["score_defesa"] = _mean_score([
        _zscore_to_100(scores["gols_contra_por_jogo"], lower_is_better=True),
        _zscore_to_100(scores["chutes_no_alvo_sofridos_por_jogo"], lower_is_better=True),
        _zscore_to_100(scores["clean_sheet_rate"]),
    ])

    # score_eficiencia: qualidade do ataque (conversão, não volume)
    scores["score_eficiencia"] = _mean_score([
        _zscore_to_100(scores["gols_por_chute"]),
        _zscore_to_100(scores["chutes_no_alvo_por_chute"]),
    ])

    # score_controle: estilo de jogo — peso baixo, não determina qualidade
    scores["score_controle"] = _mean_score([
        _zscore_to_100(scores["posse_media"]),
        _zscore_to_100(scores["passes_por_jogo"]),
        _zscore_to_100(scores["precisao_passes_media"]),
    ])

    # score_geral composto
    scores["score_geral"] = _weighted_score(scores, TEAM_SCORE_WEIGHTS)

    # Confiança baseada em amostra — sem piso artificial de 0.55
    scores["confianca_amostra"] = _sample_confidence(scores["jogos"])
    scores["confianca_dados"] = _safe_divide(
        scores.get("jogos_com_estatisticas", pd.Series(0, index=scores.index)), scores["jogos"]
    ).clip(0, 1)
    scores["nivel_evidencia"] = scores["confianca_amostra"].apply(_evidence_level)

    scores["team_slug"] = scores["team"].apply(slugify)
    scores = _add_rank(scores, "score_geral", "ranking_score_geral")
    scores = _add_rank(scores, "score_ataque", "ranking_ataque")
    scores = _add_rank(scores, "score_defesa", "ranking_defesa")
    scores = _add_rank(scores, "score_eficiencia", "ranking_eficiencia")

    score_cols = [c for c in scores.columns if c.startswith("score_")]
    scores[score_cols] = scores[score_cols].round(1)
    scores["confianca_amostra"] = scores["confianca_amostra"].round(2)
    scores["confianca_dados"] = scores["confianca_dados"].round(2)

    return scores.sort_values(["score_geral", "points", "saldo_gols"], ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Features por partida — jogadores
# ---------------------------------------------------------------------------

def build_player_match_features(player_stats: pd.DataFrame, lineups: pd.DataFrame | None = None) -> pd.DataFrame:
    if player_stats.empty:
        return pd.DataFrame()

    features = player_stats.copy()
    for column in [
        "appearances", "goals", "assists", "shots", "shots_on_target",
        "saves", "goals_conceded", "shots_faced",
        "yellow_cards", "red_cards", "fouls_committed", "fouls_drawn",
        "offsides", "own_goals",
    ]:
        if column not in features.columns:
            features[column] = 0
        features[column] = pd.to_numeric(features[column], errors="coerce").fillna(0)

    if lineups is not None and not lineups.empty and {"match_id", "team", "player_name"}.issubset(lineups.columns):
        lineup_cols = [c for c in ["match_id", "team", "player_name", "position", "is_starter", "formation"] if c in lineups.columns]
        lineup_info = lineups[lineup_cols].drop_duplicates(["match_id", "team", "player_name"])
        features = features.merge(lineup_info, on=["match_id", "team", "player_name"], how="left")

    features["participacoes_gol"] = features["goals"] + features["assists"]
    features["shot_accuracy"] = _safe_divide(features["shots_on_target"], features["shots"])
    features["perfil"] = features.apply(_player_profile, axis=1)
    features["player_slug"] = features.apply(
        lambda row: slugify(f"{row.get('player_name')}_{row.get('team')}"), axis=1
    )
    return features.sort_values(["team", "player_name", "match_id"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Score de jogadores
# ---------------------------------------------------------------------------

def build_player_scores(player_match_features: pd.DataFrame) -> pd.DataFrame:
    if player_match_features.empty:
        return pd.DataFrame()

    group_columns = ["player_slug", "player_name", "team"]
    aggregations = {
        "match_id": "nunique",
        "goals": "sum",
        "assists": "sum",
        "shots": "sum",
        "shots_on_target": "sum",
        "saves": "sum",
        "goals_conceded": "sum",
        "fouls_committed": "sum",
        "fouls_drawn": "sum",
        "yellow_cards": "sum",
        "red_cards": "sum",
        "participacoes_gol": "sum",
        "perfil": _mode_or_first,
    }
    available = {c: agg for c, agg in aggregations.items() if c in player_match_features.columns}
    scores = player_match_features.groupby(group_columns, dropna=False).agg(available).reset_index()
    scores = scores.rename(columns={"match_id": "jogos"})

    scores["gols_por_jogo"] = _safe_divide(scores["goals"], scores["jogos"])
    scores["assistencias_por_jogo"] = _safe_divide(scores["assists"], scores["jogos"])
    scores["participacoes_por_jogo"] = _safe_divide(scores["participacoes_gol"], scores["jogos"])
    scores["chutes_no_alvo_por_jogo"] = _safe_divide(scores["shots_on_target"], scores["jogos"])
    scores["defesas_por_jogo"] = _safe_divide(scores["saves"], scores["jogos"])
    scores["faltas_sofridas_por_jogo"] = _safe_divide(scores.get("fouls_drawn", pd.Series(0, index=scores.index)), scores["jogos"])
    scores["faltas_cometidas_por_jogo"] = _safe_divide(scores.get("fouls_committed", pd.Series(0, index=scores.index)), scores["jogos"])

    # score_geral calculado dentro do pool de cada perfil via z-score
    # Goleiro não compete com atacante — cada um é ranqueado entre os seus
    scores["score_geral"] = _score_by_profile(scores)

    scores["confianca_amostra"] = _sample_confidence(scores["jogos"])
    scores["nivel_evidencia"] = scores["confianca_amostra"].apply(_evidence_level)

    score_cols = [c for c in scores.columns if c.startswith("score_")]
    scores[score_cols] = scores[score_cols].round(1)
    scores["confianca_amostra"] = scores["confianca_amostra"].round(2)

    scores = _add_rank(scores, "score_geral", "ranking_score_geral")
    return scores.sort_values(["score_geral", "goals"], ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

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
    num = pd.to_numeric(pd.Series(numerator), errors="coerce").astype(float)
    if isinstance(denominator, pd.Series):
        den = pd.to_numeric(denominator, errors="coerce").astype(float).reindex(num.index)
    else:
        den = pd.Series(float(denominator), index=num.index)
    return (num / den.replace(0, pd.NA)).fillna(0)


def _zscore_to_100(values: pd.Series, lower_is_better: bool = False) -> pd.Series:
    """Converte série em score 0–100 via z-score, preservando distância absoluta.

    Diferente de min-max, um time isoladamente ruim não puxa o mínimo para 0
    quando o grupo todo é bom — as distâncias relativas permanecem proporcionais.
    Com um único valor (desvio padrão zero), retorna 50 (neutro).
    """
    numeric = pd.to_numeric(values, errors="coerce").fillna(0).astype(float)
    std = float(numeric.std(ddof=0))
    if std == 0:
        return pd.Series(50.0, index=numeric.index)
    z = (numeric - float(numeric.mean())) / std
    if lower_is_better:
        z = -z
    # Clamp em ±3 desvios e mapeia para [0, 100]
    return ((z.clip(-3, 3) + 3) / 6 * 100).clip(0, 100)


def _normalize(values: pd.Series, lower_is_better: bool = False) -> pd.Series:
    """Min-max 0–100. Mantido para compatibilidade interna."""
    numeric = pd.to_numeric(values, errors="coerce").fillna(0).astype(float)
    mn, mx = float(numeric.min()), float(numeric.max())
    if mx == mn:
        if lower_is_better and mx == 0:
            return pd.Series(100.0, index=numeric.index)
        return pd.Series(100.0 if mx > 0 else 0.0, index=numeric.index)
    normalized = (numeric - mn) / (mx - mn) * 100
    if lower_is_better:
        normalized = 100 - normalized
    return normalized.clip(0, 100)


def _sample_confidence(games: pd.Series, full_confidence_games: int = 5) -> pd.Series:
    """Confiança cresce de 0 a 1 com mais jogos. Sem piso artificial."""
    numeric = pd.to_numeric(games, errors="coerce").fillna(0).clip(lower=0)
    return (numeric.clip(upper=full_confidence_games) / full_confidence_games).clip(0, 1)


def _apply_confidence(raw_score: pd.Series, confidence: pd.Series, neutral: float = 50.0) -> pd.Series:
    raw = pd.to_numeric(raw_score, errors="coerce").fillna(neutral)
    conf = pd.to_numeric(confidence, errors="coerce").fillna(0).clip(0, 1)
    return raw * conf + neutral * (1 - conf)


def _evidence_level(value: Any) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0).iloc[0]
    if numeric >= 0.80:
        return "alta"
    if numeric >= 0.50:
        return "media"
    return "baixa"


def _mean_score(series_list: list[pd.Series]) -> pd.Series:
    return pd.concat(series_list, axis=1).mean(axis=1).fillna(0)


def _weighted_score(frame: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    parts, used = [], []
    for col, w in weights.items():
        if col in frame.columns:
            parts.append(frame[col].fillna(0) * w)
            used.append(w)
    if not parts:
        return pd.Series(0.0, index=frame.index)
    return sum(parts) / sum(used)


def _add_rank(frame: pd.DataFrame, score_col: str, rank_col: str) -> pd.DataFrame:
    out = frame.copy()
    out[rank_col] = out[score_col].rank(method="min", ascending=False).astype(int)
    return out


def _player_profile(row: pd.Series) -> str:
    """Classifica jogador por perfil usando posição ESPN quando disponível.

    Fallback por estatísticas: tackles e interceptions não existem nos dados ESPN —
    o fallback usa apenas saves vs produção ofensiva. Sem posição e sem saves,
    o padrão é "meio" (perfil mais genérico).
    """
    position = str(row.get("position") or "").strip().upper()
    if position in _POSITION_TO_PROFILE:
        return _POSITION_TO_PROFILE[position]
    # SUB sem posição definida: tenta inferir pelas stats
    saves = float(row.get("saves", 0) or 0)
    goals = float(row.get("goals", 0) or 0)
    assists = float(row.get("assists", 0) or 0)
    # Goleiro: saves dominam claramente sobre produção ofensiva
    if saves > 0 and saves > (goals + assists):
        return "goleiro"
    # Com produção ofensiva: atacante
    if goals > 0 or assists > 0 or float(row.get("shots_on_target", 0) or 0) > 0:
        return "atacante"
    return "meio"


def _score_by_profile(scores: pd.DataFrame) -> pd.Series:
    """Calcula score_geral dentro do pool de cada perfil via média ponderada de z-scores.

    Métricas e pesos por perfil (só o que existe nos dados ESPN Copa 2026):

    Goleiro:  saves/jogo        peso 0.4
              save%             peso 0.4  (saves / saves+gols_sofridos)
              gols_sofridos/jogo peso 0.2 (lower_is_better)

    Defensor: fouls_drawn/jogo  peso 0.5  (duelos ganhos, pressão)
              shots_on_target/j peso 0.3  (chegada ao ataque)
              fouls_committed/j peso 0.2  (lower — disciplina)

    Meia:     goals+assists/jogo peso 0.5 (criação e finalização)
              shots_on_target/j  peso 0.3 (chutes perigosos)
              fouls_drawn/jogo   peso 0.2 (envolvimento — peso baixo)

    Atacante: goals/jogo         peso 0.5 (função principal)
              assists/jogo        peso 0.3 (criação)
              shots_on_target/j   peso 0.2 (pressão constante)
              — fouls_drawn excluído: ruidoso, não discrimina qualidade ofensiva
    """
    result = pd.Series(50.0, index=scores.index)

    def _per_game(col: str, pool: pd.DataFrame) -> pd.Series:
        if col not in pool.columns:
            return pd.Series(0.0, index=pool.index)
        return _safe_divide(pool[col].fillna(0), pool["jogos"])

    def _wavg(components_weights: list[tuple[pd.Series, float]]) -> pd.Series:
        total_w = sum(w for _, w in components_weights)
        return sum(s * w for s, w in components_weights) / total_w

    for profile in ["goleiro", "defensor", "meio", "atacante"]:
        mask = scores["perfil"] == profile
        if not mask.any():
            continue
        pool = scores[mask].copy()

        if profile == "goleiro":
            saves_col = pool["saves"].fillna(0) if "saves" in pool.columns else pd.Series(0.0, index=pool.index)
            conceded_col = pool["goals_conceded"].fillna(0) if "goals_conceded" in pool.columns else pd.Series(0.0, index=pool.index)
            save_rate = _safe_divide(saves_col, saves_col + conceded_col)
            raw = _wavg([
                (_zscore_to_100(_per_game("saves", pool)),                          0.4),
                (_zscore_to_100(save_rate),                                         0.4),
                (_zscore_to_100(_per_game("goals_conceded", pool), lower_is_better=True), 0.2),
            ])

        elif profile == "defensor":
            raw = _wavg([
                (_zscore_to_100(_per_game("fouls_drawn", pool)),                                    0.4),
                (_zscore_to_100(_per_game("shots_on_target", pool)),                                0.2),
                (_zscore_to_100(_per_game("goals_conceded", pool), lower_is_better=True),           0.3),
                (_zscore_to_100(_per_game("fouls_committed", pool), lower_is_better=True),          0.1),
            ])

        elif profile == "meio":
            participacoes = (
                pool["goals"].fillna(0) + pool["assists"].fillna(0)
                if "goals" in pool.columns and "assists" in pool.columns
                else pd.Series(0.0, index=pool.index)
            )
            raw = _wavg([
                (_zscore_to_100(_safe_divide(participacoes, pool["jogos"])), 0.5),
                (_zscore_to_100(_per_game("shots_on_target", pool)),         0.3),
                (_zscore_to_100(_per_game("fouls_drawn", pool)),             0.2),
            ])

        else:  # atacante — fouls_drawn excluído
            raw = _wavg([
                (_zscore_to_100(_per_game("goals", pool)),           0.5),
                (_zscore_to_100(_per_game("assists", pool)),          0.3),
                (_zscore_to_100(_per_game("shots_on_target", pool)), 0.2),
            ])

        conf = _sample_confidence(pool["jogos"])
        adjusted = _apply_confidence(raw.fillna(50.0), conf)
        result.loc[mask] = adjusted.values

    return result


def _score_acumulado(scores: pd.DataFrame) -> pd.Series:
    """Score de impacto acumulado no torneio — coluna auxiliar, não entra no score_geral."""
    parts = []
    if "goals" in scores.columns:
        parts.append(_zscore_to_100(scores["goals"]) * 0.5)
    if "assists" in scores.columns:
        parts.append(_zscore_to_100(scores["assists"]) * 0.3)
    if "saves" in scores.columns:
        parts.append(_zscore_to_100(scores["saves"]) * 0.2)
    if not parts:
        return pd.Series(0.0, index=scores.index)
    return sum(parts).clip(0, 100)


def _mode_or_first(values: pd.Series) -> Any:
    clean = values.dropna()
    if clean.empty:
        return None
    mode = clean.mode()
    return mode.iloc[0] if not mode.empty else clean.iloc[0]


def _number(value: Any) -> float | None:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(converted) else float(converted)
