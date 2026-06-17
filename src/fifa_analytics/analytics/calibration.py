from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler

# Componente do score_geral -> features brutas de processo (por jogo) que ele
# tenta capturar, e a métrica de resultado que valida se o componente faz
# sentido. Cada componente é avaliado isoladamente contra seu alvo natural —
# squad_ataque tenta prever gols, não posse de bola, por exemplo.
COMPONENT_VALIDATION_TARGETS: dict[str, dict[str, list[str] | str]] = {
    "score_ataque": {
        "features": ["shots", "shots_on_target", "key_passes", "expected_assists"],
        "target": "goals_for",
    },
    "score_defesa": {
        # solidez = sofrer pouco; tackles/interceptions/clearances medem volume
        # de ações (time pressionado), não solidez — fora (ver PROCESS_FEATURES).
        "features": ["shots_against", "shots_on_target_against"],
        "target": "goals_against",
        "lower_is_better_target": True,
    },
    "score_eficiencia": {
        "features": ["shot_accuracy", "goal_conversion", "key_passes"],
        "target": "goals_for",
    },
    "score_controle": {
        "features": ["possession", "passes", "pass_accuracy", "touches", "dribbles_won"],
        "target": "points",
    },
}

# Features de processo (por jogo) usadas para calibrar os pesos finais do
# score_geral — tudo que não seja score_resultado, que já É o resultado
# observado (aproveitamento/saldo), não uma previsão dele. Incluí-lo aqui
# seria circular: o modelo aprenderia que "o resultado prevê o resultado".
#
# IMPORTANTE: cada bloco deve refletir o que o COMPONENTE correspondente em
# analytics/scores.py de fato mede — senão a calibração pesa o componente por um
# proxy diferente do que ele representa. A defesa em scores.py é solidez =
# *sofrer pouco* (chutes/chutes no alvo sofridos), NÃO volume de ações
# defensivas. tackles/interceptions/clearances foram removidos daqui porque
# medem o oposto: um time que desarma/corta muito é um time PRESSIONADO (está
# apanhando), o que polui o sinal e derrubava o peso da defesa artificialmente.
PROCESS_FEATURES: dict[str, list[str]] = {
    "ataque": ["shots", "shots_on_target", "key_passes", "expected_assists"],
    "defesa": ["shots_against", "shots_on_target_against"],
    "eficiencia": ["shot_accuracy", "goal_conversion"],
    "controle": ["possession", "passes", "pass_accuracy", "touches", "dribbles_won"],
}


def validate_component(
    team_match_features: pd.DataFrame,
    component: str,
) -> dict[str, float | int | str]:
    """Mede o quanto as features de um componente explicam sua métrica-alvo
    natural, jogo a jogo. Retorna R² (ajuste do modelo) e os coeficientes
    padronizados (qual feature pesa mais), não para substituir o componente,
    mas para apontar se ele está capturando o que deveria.
    """
    spec = COMPONENT_VALIDATION_TARGETS.get(component)
    if spec is None:
        raise ValueError(f"Componente desconhecido para validação: {component}")

    features_cols = [c for c in spec["features"] if c in team_match_features.columns]
    target_col = spec["target"]
    if not features_cols or target_col not in team_match_features.columns:
        return {"component": component, "status": "dados_insuficientes", "n_jogos": 0}

    data = team_match_features[features_cols + [target_col]].apply(pd.to_numeric, errors="coerce").dropna()
    n = len(data)
    if n < 5:
        return {"component": component, "status": "amostra_pequena", "n_jogos": n}

    X = data[features_cols].to_numpy()
    y = data[target_col].to_numpy()
    if spec.get("lower_is_better_target"):
        y = -y

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = RidgeCV(alphas=np.logspace(-2, 2, 20))
    model.fit(X_scaled, y)
    r2 = model.score(X_scaled, y)

    coefficients = dict(zip(features_cols, model.coef_.round(3)))

    return {
        "component": component,
        "status": "ok",
        "n_jogos": n,
        "r2": round(float(r2), 3),
        "alpha": round(float(model.alpha_), 3),
        "coeficientes_padronizados": coefficients,
    }


def _collinearity_score(features: pd.DataFrame) -> float:
    """Grau de colinearidade do conjunto de componentes (0 a 1).

    Para cada componente, mede o R² ao regredi-lo nos OUTROS (quanto ele é
    "explicável" pelos demais). A média é o grau de redundância do conjunto:
    0 = componentes independentes, 1 = totalmente redundantes. Usado como peso
    da relevância univariada no híbrido — quanto mais colineares os dados, menos
    confiável a regressão múltipla (que vira ruído), mais peso ao mérito isolado.
    """
    cols = list(features.columns)
    if len(cols) < 2:
        return 0.0
    r2s = []
    for target_col in cols:
        others = [c for c in cols if c != target_col]
        X = features[others].to_numpy()
        y = features[target_col].to_numpy()
        if y.std() == 0:
            continue
        Xb = np.c_[X, np.ones(len(X))]
        beta, _, _, _ = np.linalg.lstsq(Xb, y, rcond=None)
        pred = Xb @ beta
        ss_res = float(((y - pred) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        if ss_tot > 0:
            r2s.append(max(0.0, 1.0 - ss_res / ss_tot))
    return float(np.mean(r2s)) if r2s else 0.0


def calibrate_team_score_weights(
    team_match_features: pd.DataFrame,
    target: str = "hibrido",
    alpha_hibrido: float = 0.6,
) -> dict[str, float | int | str | dict]:
    """Calibra os pesos relativos dos componentes de processo do score_geral.

    Por padrão usa um alvo híbrido: combinação ponderada de pontos (3/1/0) e
    saldo de gols, ambos normalizados por z-score antes de combinar.
    ``alpha_hibrido`` controla o peso de pontos (0.6) vs. saldo de gols (0.4):
    pontos capturam se o time ganhou, saldo captura por quanto dominou — os
    dois se complementam sem precisar de um modelo multivariado.

    Usa RidgeCV (regularização L2) para lidar com amostras pequenas sem
    superajustar — o alpha é escolhido por validação cruzada interna.

    score_resultado e score_forca_relativa ficam fora: o primeiro é derivado
    do próprio resultado (circular), o segundo é Elo acumulado de toda a
    campanha (não uma feature daquele jogo). Ambos entram no modo preditivo
    (calibrate_full_weights_predictive), não aqui.
    """
    data = team_match_features.copy()

    if target == "hibrido":
        goals_for = pd.to_numeric(data["goals_for"], errors="coerce")
        goals_against = pd.to_numeric(data["goals_against"], errors="coerce")
        points = pd.to_numeric(data["points"], errors="coerce")
        goal_diff = goals_for - goals_against

        # Normaliza cada alvo individualmente antes de combinar — sem isso,
        # saldo de gols (~-3 a +5) dominaria pontos (0/1/3) só pela escala.
        def _znorm(s: pd.Series) -> pd.Series:
            std = s.std(ddof=0)
            return (s - s.mean()) / std if std > 0 else s - s.mean()

        data["_target"] = alpha_hibrido * _znorm(points) + (1 - alpha_hibrido) * _znorm(goal_diff)
        target_col = "_target"
    elif target == "goal_diff":
        data["goal_diff"] = pd.to_numeric(data["goals_for"], errors="coerce") - pd.to_numeric(
            data["goals_against"], errors="coerce"
        )
        target_col = "goal_diff"
    else:
        target_col = target

    component_features: dict[str, pd.Series] = {}
    for component, cols in PROCESS_FEATURES.items():
        available = [c for c in cols if c in data.columns]
        if not available:
            continue
        numeric = data[available].apply(pd.to_numeric, errors="coerce")
        # Padroniza cada feature antes de agregar — sem isso, "passes" (~500)
        # dominaria "shot_accuracy" (~0-1) só pela escala, não pela relevância real.
        standardized = (numeric - numeric.mean()) / numeric.std(ddof=0).replace(0, 1)
        component_features[component] = standardized.mean(axis=1)

    if not component_features:
        return {"status": "dados_insuficientes"}

    features_df = pd.DataFrame(component_features)
    combined = pd.concat([features_df, data[target_col]], axis=1).dropna()
    n = len(combined)
    if n < 5:
        return {"status": "amostra_pequena", "n_jogos": n}

    comp_names = list(component_features.keys())
    y_series = pd.to_numeric(combined[target_col], errors="coerce")
    y_np = y_series.to_numpy()
    X = combined[comp_names].to_numpy()

    # Peso HÍBRIDO: média entre a relevância UNIVARIADA e a MULTIVARIADA de cada
    # componente. Os dois métodos capturam coisas diferentes e complementares:
    #
    #  • UNIVARIADA (correlação isolada): o mérito PRÓPRIO do componente — quanto
    #    ele sozinho prevê o resultado. Mas ignora que parte desse mérito é
    #    COMPARTILHADO com outros (controle e ataque têm ~0.75 de correlação:
    #    quem controla também ataca), então tende a superestimar redundantes.
    #
    #  • MULTIVARIADA (regressão Ridge): a contribuição ÚNICA — o que o componente
    #    adiciona ALÉM dos outros. Mas com colinearidade fica instável e gera
    #    ruído (o controle chegava a coeficiente NEGATIVO porque o ataque
    #    "roubava" o crédito da variação compartilhada), subestimando-o.
    #
    # O peso entre os dois métodos NÃO é fixo (50/50 seria arbitrário) — ele é
    # derivado da COLINEARIDADE real dos dados. Mede-se quanto cada componente é
    # explicável pelos outros (R² do componente regredido nos demais); a média
    # disso é o "grau de redundância" do conjunto. Quanto mais colineares:
    #   • menos confiável a multivariada (instável, gera ruído) → mais peso na univariada
    #   • dados independentes → o híbrido tende a 100% multivariada (o ideal sem colinearidade)
    # Assim o alpha se adapta: hoje ~0.46 (dados moderadamente colineares), e muda
    # sozinho conforme as features evoluem ao longo do torneio.
    def _safe_corr(col: pd.Series) -> float:
        return abs(float(col.corr(y_series))) if col.std(ddof=0) > 0 else 0.0

    def _normalize(d: dict) -> dict:
        t = sum(d.values()) or 1.0
        return {k: v / t for k, v in d.items()}

    uni = _normalize({name: _safe_corr(combined[name]) for name in comp_names})

    model = RidgeCV(alphas=np.logspace(-2, 2, 20))
    model.fit(X, y_np)
    r2 = model.score(X, y_np)
    multi = _normalize({name: abs(float(c)) for name, c in zip(comp_names, model.coef_)})

    # grau de colinearidade do conjunto = R² médio de cada componente explicado
    # pelos outros. É também o peso da univariada no híbrido.
    alpha_uni = _collinearity_score(combined[comp_names])
    hybrid = _normalize({
        name: alpha_uni * uni[name] + (1.0 - alpha_uni) * multi[name]
        for name in comp_names
    })
    normalized_weights = {f"score_{k}": round(v, 3) for k, v in hybrid.items()}

    # correlação COM SINAL, para diagnóstico (sinal inesperado = feature suspeita)
    signed_corr = {
        f"score_{name}": round(float(combined[name].corr(y_series)), 4)
        if combined[name].std(ddof=0) > 0 else 0.0
        for name in comp_names
    }

    return {
        "status": "ok",
        "n_jogos": n,
        "target": target,
        "alpha_hibrido": alpha_hibrido if target == "hibrido" else None,
        "r2": round(float(r2), 3),
        "metodo": "hibrido_univariada_multivariada",
        "alpha_univariada": round(float(alpha_uni), 3),  # peso da univariada (= colinearidade)
        "pesos_sugeridos": normalized_weights,
        "pesos_univariada": {f"score_{k}": round(v, 3) for k, v in uni.items()},
        "pesos_multivariada": {f"score_{k}": round(v, 3) for k, v in multi.items()},
        "correlacoes_com_sinal": signed_corr,
    }


def apply_calibrated_weights(
    base_weights: dict[str, float],
    weight_calibration: dict[str, Any],
    fixed_components: tuple[str, ...] = ("score_resultado", "score_forca_relativa"),
) -> dict[str, float]:
    """Aplica os pesos sugeridos pela calibração.

    Modo preditivo (modo="preditivo_6_pesos"): todos os 6 componentes foram
    calibrados juntos — usa os pesos sugeridos diretamente, redistribuídos
    para somar 1.0, sem fixar nenhum componente.

    Modo processo (padrão): resultado e força relativa ficam fixos em
    base_weights; os 4 componentes de processo são redistribuídos na proporção
    sugerida pela regressão, preenchendo o espaço restante (1.0 - fixos).
    """
    if weight_calibration.get("status") != "ok":
        return dict(base_weights)

    suggested = weight_calibration.get("pesos_sugeridos", {})

    if weight_calibration.get("modo") == "preditivo_6_pesos":
        # Todos os 6 pesos vêm da regressão — normaliza para somar 1.0
        total = sum(suggested.get(c, 0.0) for c in base_weights) or 1.0
        return {c: round(suggested.get(c, 0.0) / total, 4) for c in base_weights}

    # Modo processo: fixos preservados, variáveis redistribuídos
    fixed_total = sum(base_weights.get(c, 0.0) for c in fixed_components)
    remaining = max(1.0 - fixed_total, 0.0)

    calibrated_components = [c for c in base_weights if c not in fixed_components and c in suggested]
    if not calibrated_components:
        return dict(base_weights)

    suggested_total = sum(suggested[c] for c in calibrated_components) or 1.0

    result = dict(base_weights)
    for component in calibrated_components:
        result[component] = round(remaining * suggested[component] / suggested_total, 4)
    return result


def calibrate_full_weights_predictive(
    team_match_features: pd.DataFrame,
    score_history: pd.DataFrame | None = None,
    alpha_hibrido: float = 0.6,
) -> dict[str, float | int | str | dict]:
    """Calibra os 6 pesos do score_geral (incluindo resultado e força
    relativa) contra o desempenho do PRÓXIMO jogo de cada time.

    Usa os scores acumulados até o jogo N como features preditoras do
    desempenho no jogo N+1 (alvo híbrido: pontos + saldo de gols normalizados)
    — isso evita a circularidade de usar score_resultado no mesmo jogo.

    Requer score_history (score acumulado por time após cada jogo) e pelo
    menos 5 times com 2+ jogos disputados.
    """
    if "team" not in team_match_features.columns or "date" not in team_match_features.columns:
        return {"status": "dados_insuficientes"}

    if score_history is None or score_history.empty:
        return {"status": "dados_insuficientes", "motivo": "score_history ausente"}

    games_per_team = team_match_features.groupby("team")["match_id"].nunique()
    eligible_teams = games_per_team[games_per_team >= 2].index
    if len(eligible_teams) < 5:
        return {
            "status": "amostra_insuficiente",
            "motivo": "menos de 5 times com 2+ jogos disputados — aguardando mais rodadas",
            "times_elegiveis": int(len(eligible_teams)),
        }

    # Para cada time com 2+ jogos: scores acumulados após o jogo N-1 → alvo
    # é o saldo de gols no jogo N. Usa todos os pares (N-1, N) disponíveis,
    # não só o primeiro par — mais pares = mais sinal para a regressão.
    ordered = team_match_features.sort_values(["team", "date"])
    score_cols = ["score_resultado", "score_ataque", "score_defesa",
                  "score_eficiencia", "score_controle", "score_forca_relativa"]
    available_score_cols = [c for c in score_cols if c in score_history.columns]
    if not available_score_cols:
        return {"status": "dados_insuficientes", "motivo": "score_history sem colunas de score"}

    rows = []
    for team in eligible_teams:
        team_games = ordered[ordered["team"] == team].reset_index(drop=True)
        team_hist = score_history[score_history["team"] == team].sort_values("jogos").reset_index(drop=True)
        for i in range(1, len(team_games)):
            # Scores acumulados até o jogo anterior (i-1 jogos disputados)
            hist_row = team_hist[team_hist["jogos"] == i]
            if hist_row.empty:
                continue
            next_game = team_games.iloc[i]
            goals_for = pd.to_numeric(next_game.get("goals_for"), errors="coerce")
            goals_against = pd.to_numeric(next_game.get("goals_against"), errors="coerce")
            points = pd.to_numeric(next_game.get("points"), errors="coerce")
            if pd.isna(goals_for) or pd.isna(goals_against):
                continue
            row = {col: hist_row.iloc[0].get(col, np.nan) for col in available_score_cols}
            row["goal_diff_next"] = goals_for - goals_against
            row["points_next"] = points if not pd.isna(points) else np.nan
            rows.append(row)

    if len(rows) < 5:
        return {
            "status": "amostra_insuficiente",
            "motivo": f"apenas {len(rows)} pares (jogo_n → jogo_n+1) disponíveis — aguardando mais rodadas",
            "pares_disponiveis": len(rows),
        }

    df = pd.DataFrame(rows).dropna(subset=available_score_cols + ["goal_diff_next"])
    if len(df) < 5:
        return {"status": "amostra_insuficiente", "motivo": "dados insuficientes após dropna", "pares_disponiveis": len(df)}

    # Alvo híbrido: pontos e saldo de gols normalizados, combinados por alpha_hibrido.
    # Pontos com NaN (ex: jogo ainda sem resultado) caem para saldo puro.
    def _znorm(s: pd.Series) -> pd.Series:
        std = s.std(ddof=0)
        return (s - s.mean()) / std if std > 0 else s - s.mean()

    goal_diff = pd.to_numeric(df["goal_diff_next"], errors="coerce")
    if "points_next" in df.columns and df["points_next"].notna().sum() >= 5:
        points = pd.to_numeric(df["points_next"], errors="coerce")
        y = (alpha_hibrido * _znorm(points) + (1 - alpha_hibrido) * _znorm(goal_diff)).to_numpy()
        target_label = f"hibrido(pontos={alpha_hibrido:.0%}, saldo={1-alpha_hibrido:.0%})_next"
    else:
        y = goal_diff.to_numpy()
        target_label = "goal_diff_next"

    X = df[available_score_cols].to_numpy()
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = RidgeCV(alphas=np.logspace(-2, 2, 20))
    model.fit(X_scaled, y)
    r2 = model.score(X_scaled, y)

    raw_weights = dict(zip(available_score_cols, np.abs(model.coef_)))
    total = sum(raw_weights.values()) or 1.0
    normalized_weights = {k: round(v / total, 3) for k, v in raw_weights.items()}

    return {
        "status": "ok",
        "modo": "preditivo_6_pesos",
        "n_pares": len(df),
        "target": target_label,
        "alpha_hibrido": alpha_hibrido,
        "r2": round(float(r2), 3),
        "alpha": round(float(model.alpha_), 3),
        "pesos_sugeridos": normalized_weights,
        "coeficientes_brutos": {k: round(float(v), 4) for k, v in zip(available_score_cols, model.coef_)},
    }
