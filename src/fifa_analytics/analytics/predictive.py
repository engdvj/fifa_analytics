"""Analise Preditiva - proximos jogos com previsao explicavel.

O modelo segue simples e auditavel: usa o snapshot atual das selecoes para
estimar gols esperados, monta a matriz de placares via Poisson e aplica uma
calibracao leve no empate para nao transformar todo jogo parelho em 1-1.
"""
from __future__ import annotations

import hashlib
import json
from math import exp, factorial, floor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


OUTCOMES = ("home", "draw", "away")
FEATURE_KEYS = (
    "score",
    "ataque",
    "defesa",
    "resultado",
    "controle",
    "eficiencia",
    "elo",
    "xg_pj",
    "gols_pj",
    "xg_sofrido_pj",
    "gols_contra_pj",
    "aproveitamento",
    "saldo_gols",
    "reliability",
)
# Features ENXUTAS para o classificador logístico. Só as diferenças mais
# informativas (4) — com ~48 jogos de treino, usar as 40+ features completas faz
# o modelo overfitar e até INVERTER a previsão (ex: dava 87% pro azarão). Poucas
# features + regularização forte = contribuição estável, sem inversão.
LEAN_FEATURES = ("diff_score", "diff_elo", "diff_xg_pj", "diff_xg_sofrido_pj")
# Pesos do ensemble. Calibrados pelo backtest walk-forward sobre os jogos
# finalizados (ver build_backtest -> summary.models). A família Poisson e o
# Empirical Bayes carregam o sinal útil (todos usam score/Elo/ataque/controle/
# eficiência via _expected_goals); o Monte Carlo injeta over-dispersão (Negative
# Binomial). O RandomForest foi REMOVIDO e a logística virou enxuta+regularizada
# (LEAN_FEATURES) porque com ~48 jogos os classificadores genéricos overfitavam
# e invertiam a previsão — recebe peso pequeno, só de ajuste fino.
MODEL_WEIGHTS = {
    "poisson": 0.42,
    "empirical_bayes": 0.23,
    "poisson_regressor": 0.18,
    "monte_carlo": 0.11,
    "logistic_regression": 0.06,
}
MIN_PREDICTION_GAME = 25  # a partir daqui a previsão CONTA na métrica/aprendizado
MIN_DISPLAY_GAME = 2      # a partir daqui a previsão APARECE (jogo 1 não tem base)
# Dispersao do Negative Binomial usado no Monte Carlo. Quanto MENOR, mais
# over-dispersao (cauda mais gorda) em relacao ao Poisson puro.
NB_DISPERSION = 6.0

# Constantes de calibracao do gerador de gols esperados e do fator de empate.
# Ajustadas a partir do backtest walk-forward (build_backtest): a versao anterior
# previa empate em ~5% dos jogos contra ~21% reais, porque o `draw_factor` so
# sabia SUPRIMIR empate. A faixa foi elevada e o multiplicador de mando zerado
# (na Copa "home" e so a ordem do fixture, nao ha mando de verdade salvo anfitriao).
# `build_backtest(..., calibrate=True)` sugere novos valores a partir dos dados.
CALIBRATION = {
    "home_advantage": 1.0,   # multiplicador de xG do mandante (1.0 = sem mando)
    "global_scale": 1.02,    # ajuste fino global de volume de gols
    "strength_scale": 1.8,   # o quanto a superioridade vira favoritismo (>1 = favoritos mais claros)
    "draw_base": 1.18,       # fator de empate quando o jogo e parelho
    "draw_min": 0.85,        # piso do fator de empate (jogo desigual)
    "draw_slope": 0.10,      # quanto a desigualdade derruba o fator de empate
}

# Onde a calibracao/pesos APRENDIDOS sao gravados pelo pipeline. Quando o arquivo
# existe, build_predictive passa a usa-lo automaticamente em vez dos defaults acima.
_CALIBRATION_FILE = (
    Path(__file__).resolve().parents[3] / "data" / "gold" / "analytics" / "predictive_calibration.json"
)
_LEARNED_CACHE: dict[str, Any] | None = None


def _load_learned() -> dict[str, Any]:
    """Le (com cache) a calibracao aprendida do disco; {} se nao existir."""
    global _LEARNED_CACHE
    if _LEARNED_CACHE is None:
        try:
            _LEARNED_CACHE = json.loads(_CALIBRATION_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _LEARNED_CACHE = {}
    return _LEARNED_CACHE


def reset_learned_cache() -> None:
    """Forca rele-leitura do arquivo (chamar apos regravar a calibracao)."""
    global _LEARNED_CACHE
    _LEARNED_CACHE = None


def load_learned_calibration() -> dict[str, float]:
    learned = _load_learned().get("calibration")
    return {**CALIBRATION, **learned} if isinstance(learned, dict) else dict(CALIBRATION)


def load_learned_weights() -> dict[str, float]:
    learned = _load_learned().get("weights")
    return {**MODEL_WEIGHTS, **learned} if isinstance(learned, dict) else dict(MODEL_WEIGHTS)


# Previsoes CONGELADAS: o primeiro palpite de cada jogo e salvo e nunca mais muda,
# mesmo que outros jogos aconteçam depois. É o "palpite oficial" que se compara com
# o resultado real — evita que a previsao se ajuste retroativamente.
_FROZEN_FILE = (
    Path(__file__).resolve().parents[3] / "data" / "gold" / "analytics" / "predictive_frozen.json"
)


def _load_frozen() -> dict[str, Any]:
    try:
        return json.loads(_FROZEN_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_frozen(store: dict[str, Any]) -> None:
    _FROZEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _FROZEN_FILE.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")


def _apply_freeze(prediction: dict[str, Any], already_final: bool = False) -> tuple[dict[str, Any], str | None]:
    """Devolve o palpite congelado (1ª vez salva, depois reusa). Retorna (palpite, quando).

    Se `already_final` (a 1ª visualização já é pós-jogo), não congela — não há
    previsão genuína a guardar; devolve o palpite atual sem persistir.
    """
    from datetime import datetime, timezone

    match_id = str(prediction.get("match_id"))
    store = _load_frozen()
    saved = store.get(match_id)
    if saved is not None:
        return saved["prediction"], saved.get("frozen_at")
    if already_final:
        return prediction, None

    frozen_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    store[match_id] = {"frozen_at": frozen_at, "prediction": prediction}
    _save_frozen(store)
    return prediction, frozen_at


def _num(v: Any, default: float | None = None) -> float | None:
    try:
        f = float(v)
        return default if np.isnan(f) else f
    except (TypeError, ValueError):
        return default


def _round(v: float | None, ndigits: int = 2) -> float | None:
    return None if v is None else round(float(v), ndigits)


def _clean_team(v: Any) -> str:
    """Nome de time saneado, ou string vazia se ausente/NaN."""
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return ""
    name = str(v).strip()
    return "" if name.lower() == "nan" else name


def _seed_for(match_id: Any, target: int) -> int:
    """Seed deterministica e estavel a partir do match_id (sem colisoes triviais).

    Usa blake2b em vez de hash() builtin, que e salgado por processo
    (PYTHONHASHSEED) e nao reproduziria a mesma simulacao entre execucoes.
    """
    digest = hashlib.blake2b(f"{match_id}|{int(target)}".encode(), digest_size=4).digest()
    return int.from_bytes(digest, "big")


def _clip(v: float, lo: float, hi: float) -> float:
    return float(np.clip(v, lo, hi))


def _blend(base: float, observed: float, weight: float) -> float:
    weight = _clip(weight, 0.0, 1.0)
    return (base * (1 - weight)) + (observed * weight)


def _reliability(games: float) -> float:
    """Peso da amostra: 1 jogo ainda e barulhento; 4+ ja fala mais alto."""
    return _clip(games / (games + 2.5), 0.0, 0.78)


def _pct(values: list[float]) -> list[int]:
    total = sum(values) or 1.0
    raw = [max(0.0, v) / total * 100 for v in values]
    ints = [floor(v) for v in raw]
    missing = max(0, 100 - sum(ints))
    order = sorted(range(len(raw)), key=lambda i: raw[i] - ints[i], reverse=True)
    for i in order[:missing]:
        ints[i] += 1
    return ints


def _poisson(k: int, lam: float) -> float:
    return exp(-lam) * (lam ** k) / factorial(k)


def _score_matrix(
    home_xg: float,
    away_xg: float,
    draw_factor: float = 1.0,
    max_goals: int = 8,
) -> dict[str, Any]:
    home_probs = [_poisson(i, home_xg) for i in range(max_goals + 1)]
    away_probs = [_poisson(i, away_xg) for i in range(max_goals + 1)]
    p_home = p_draw = p_away = 0.0
    scorelines: list[tuple[float, int, int, str]] = []
    best_by_result: dict[str, tuple[float, int, int]] = {
        "home": (0.0, 0, 0),
        "draw": (0.0, 0, 0),
        "away": (0.0, 0, 0),
    }

    for h, ph in enumerate(home_probs):
        for a, pa in enumerate(away_probs):
            p = ph * pa
            result = "draw"
            if h > a:
                p_home += p
                result = "home"
            elif h == a:
                p *= draw_factor
                p_draw += p
            else:
                p_away += p
                result = "away"

            scorelines.append((p, h, a, result))
            if p > best_by_result[result][0]:
                best_by_result[result] = (p, h, a)

    total = p_home + p_draw + p_away
    if total > 0:
        p_home, p_draw, p_away = p_home / total, p_draw / total, p_away / total
        scorelines = [(p / total, h, a, result) for p, h, a, result in scorelines]

    home_pct, draw_pct, away_pct = _pct([p_home, p_draw, p_away])
    scorelines = sorted(scorelines, reverse=True)[:5]
    most_likely = scorelines[0] if scorelines else (0.0, 0, 0, "draw")

    result_probs = {"home": home_pct, "draw": draw_pct, "away": away_pct}
    leading_result = max(result_probs, key=result_probs.get)
    lean = most_likely
    if leading_result != "draw" and result_probs[leading_result] >= draw_pct + 4:
        p, h, a = best_by_result[leading_result]
        lean = (p / total if total else p, h, a, leading_result)

    return {
        "home_win": home_pct,
        "draw": draw_pct,
        "away_win": away_pct,
        "score": {"home": lean[1], "away": lean[2]},
        "scoreline": {
            "recommended": {"home": lean[1], "away": lean[2], "probability": round(lean[0] * 100, 1)},
            "most_likely": {
                "home": most_likely[1],
                "away": most_likely[2],
                "probability": round(most_likely[0] * 100, 1),
            },
            "alternatives": [
                {"home": h, "away": a, "probability": round(p * 100, 1), "result": result}
                for p, h, a, result in scorelines
            ],
        },
    }


def _prob_dict(home: float, draw: float, away: float) -> dict[str, int]:
    home_pct, draw_pct, away_pct = _pct([home, draw, away])
    return {"home_win": home_pct, "draw": draw_pct, "away_win": away_pct}


def _prob_vector(probs: dict[str, Any]) -> np.ndarray:
    return np.array([probs["home_win"], probs["draw"], probs["away_win"]], dtype=float) / 100


def _expected_scoreline(home_xg: float, away_xg: float, leading: str) -> tuple[int, int]:
    """Placar a partir dos gols ESPERADOS (arredondados), coerente com o resultado.

    O placar modal do Poisson subestima (moda < média): para xG ~2 o pico fica em
    1 gol, então um favorito que deve fazer ~2x1 aparecia como "1-0 murcho". Usar
    round(xG) deixa o placar fiel ao volume esperado que o card mostra; depois
    ajustamos o mínimo para respeitar o resultado liderante.
    """
    h, a = int(round(home_xg)), int(round(away_xg))
    if leading == "home" and h <= a:
        h = a + 1
    elif leading == "away" and a <= h:
        a = h + 1
    elif leading == "draw" and h != a:
        h = a = round((home_xg + away_xg) / 2)
    return h, a


def _with_scoreline(probs: dict[str, int], home_xg: float, away_xg: float, draw_factor: float) -> dict[str, Any]:
    """Anexa o placar recomendado, coerente com o resultado liderante e com o xG.

    O placar recomendado vem dos gols esperados arredondados (fiel ao volume que o
    card exibe), forçado a respeitar o resultado liderante das probabilidades. A
    `probability` é a probabilidade real DAQUELE placar. O `most_likely` (placar
    modal) e as alternativas continuam disponíveis nos chips.
    """
    matrix = _score_matrix(home_xg, away_xg, draw_factor)
    leading = "home" if probs["home_win"] >= probs["draw"] and probs["home_win"] >= probs["away_win"] else (
        "away" if probs["away_win"] >= probs["home_win"] and probs["away_win"] >= probs["draw"] else "draw"
    )
    h, a = _expected_scoreline(home_xg, away_xg, leading)
    p = _poisson(h, home_xg) * _poisson(a, away_xg) * (draw_factor if h == a else 1.0)
    matrix["scoreline"]["recommended"] = {"home": h, "away": a, "probability": round(p * 100, 1)}
    matrix["score"] = {"home": h, "away": a}
    return {**probs, "score": matrix["score"], "scoreline": matrix["scoreline"]}


def _score_grid(home_xg: float, away_xg: float, draw_factor: float, max_goals: int = 8) -> list[tuple[float, int, int, str]]:
    rows: list[tuple[float, int, int, str]] = []
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = _poisson(h, home_xg) * _poisson(a, away_xg)
            if h > a:
                result = "home"
            elif h < a:
                result = "away"
            else:
                result = "draw"
                p *= draw_factor
            rows.append((p, h, a, result))
    total = sum(p for p, _, _, _ in rows) or 1.0
    return [(p / total, h, a, result) for p, h, a, result in rows]


def _monte_carlo_probs(
    home_xg: float,
    away_xg: float,
    draw_factor: float,
    seed: int,
    n: int = 20000,
    dispersion: float = NB_DISPERSION,
) -> dict[str, Any]:
    """Simula gols com Negative Binomial (Poisson com lambda Gamma-distribuido).

    Ao contrario do Poisson puro, isso modela over-dispersao: jogos com placares
    elevados (3-2, 4-1) ficam mais provaveis do que o Poisson admite, o que casa
    melhor com a realidade do futebol. Para `dispersion -> inf` recai no Poisson.
    """
    rng = np.random.default_rng(seed)

    def goals(lam: float) -> np.ndarray:
        # Mistura Gamma-Poisson => Negative Binomial com media `lam`.
        rate = rng.gamma(shape=dispersion, scale=lam / dispersion, size=n)
        return rng.poisson(rate)

    home = goals(home_xg)
    away = goals(away_xg)
    home_win = int(np.sum(home > away))
    away_win = int(np.sum(home < away))
    draw = int(round((n - home_win - away_win) * draw_factor))
    return _with_scoreline(
        _prob_dict(home_win / n, draw / n, away_win / n), home_xg, away_xg, draw_factor
    )


def _latest_snapshot(timeline: pd.DataFrame, snapshot: int | None) -> pd.DataFrame:
    if timeline.empty or "snapshot_jogo" not in timeline.columns:
        return pd.DataFrame()
    last = int(timeline["snapshot_jogo"].max())
    target = last if snapshot is None else min(int(snapshot), last)
    return timeline[timeline["snapshot_jogo"] == target].copy()


def _ordered_matches(dim_match: pd.DataFrame) -> pd.DataFrame:
    if dim_match.empty:
        return dim_match.copy()
    out = dim_match.copy()
    sort_cols = [c for c in ["date_utc", "match_number"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, na_position="last")
    out = out.reset_index(drop=True)
    out["prediction_index"] = np.arange(1, len(out) + 1)
    return out


def _baseline(snap: pd.DataFrame, col: str, fallback: float) -> float:
    if col not in snap.columns:
        return fallback
    vals = pd.to_numeric(snap[col], errors="coerce").dropna()
    return float(vals.mean()) if len(vals) else fallback


def _team_profile(row: pd.Series | dict | None, base_xg: float, base_goals: float) -> dict[str, float]:
    if row is None:
        return {
            "jogos": 0.0,
            "reliability": 0.0,
            "score": 50.0,
            "ataque": 50.0,
            "defesa": 50.0,
            "resultado": 50.0,
            "controle": 50.0,
            "eficiencia": 50.0,
            "elo": 1500.0,
            "xg_pj": base_xg,
            "gols_pj": base_goals,
            "xg_sofrido_pj": base_xg,
            "gols_contra_pj": base_goals,
            "aproveitamento": 0.5,
            "saldo_gols": 0.0,
        }

    games = _num(row.get("jogos"), 0.0) or 0.0
    return {
        "jogos": games,
        "reliability": _reliability(games),
        "score": _num(row.get("score_geral"), 50.0) or 50.0,
        "ataque": _num(row.get("score_ataque"), 50.0) or 50.0,
        "defesa": _num(row.get("score_defesa"), 50.0) or 50.0,
        "resultado": _num(row.get("score_resultado"), 50.0) or 50.0,
        "controle": _num(row.get("score_controle"), 50.0) or 50.0,
        "eficiencia": _num(row.get("score_eficiencia"), 50.0) or 50.0,
        "elo": _num(row.get("elo_rating"), 1500.0) or 1500.0,
        "xg_pj": _num(row.get("xg_pj"), base_xg) or base_xg,
        "gols_pj": _num(row.get("gols_pj"), base_goals) or base_goals,
        "xg_sofrido_pj": _num(row.get("xg_sofrido_pj"), base_xg) or base_xg,
        "gols_contra_pj": _num(row.get("gols_contra_pj"), base_goals) or base_goals,
        "aproveitamento": _num(row.get("aproveitamento"), 0.5) or 0.5,
        "saldo_gols": _num(row.get("saldo_gols"), 0.0) or 0.0,
    }


def _features(home: dict[str, float], away: dict[str, float]) -> dict[str, float]:
    feat: dict[str, float] = {
        "home_jogos": home["jogos"],
        "away_jogos": away["jogos"],
        "min_jogos": min(home["jogos"], away["jogos"]),
    }
    for key in FEATURE_KEYS:
        feat[f"home_{key}"] = home[key]
        feat[f"away_{key}"] = away[key]
        feat[f"diff_{key}"] = home[key] - away[key]
    return feat


def _feature_columns() -> list[str]:
    cols = ["home_jogos", "away_jogos", "min_jogos"]
    for key in FEATURE_KEYS:
        cols.extend([f"home_{key}", f"away_{key}", f"diff_{key}"])
    return cols


def _snapshot_records(timeline: pd.DataFrame) -> dict[int, dict[str, dict]]:
    if timeline.empty or "snapshot_jogo" not in timeline.columns:
        return {}
    out: dict[int, dict[str, dict]] = {}
    for row in timeline.to_dict("records"):
        snap = int(row.get("snapshot_jogo"))
        out.setdefault(snap, {})[str(row.get("team"))] = row
    return out


def _profile_at(
    snapshots: dict[int, dict[str, dict]],
    snapshot: int,
    team: str,
    base_xg: float,
    base_goals: float,
) -> dict[str, float]:
    row = snapshots.get(int(snapshot), {}).get(team)
    return _team_profile(row, base_xg, base_goals)


def _outcome_from_scores(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if away_goals > home_goals:
        return "away"
    return "draw"


def _training_table(
    ordered_matches: pd.DataFrame,
    timeline: pd.DataFrame,
    target_game: int,
    base_xg: float,
    base_goals: float,
) -> pd.DataFrame:
    snapshots = _snapshot_records(timeline)
    rows: list[dict[str, Any]] = []
    if not snapshots or ordered_matches.empty or "prediction_index" not in ordered_matches.columns:
        return pd.DataFrame()

    for match in ordered_matches.to_dict("records"):
        match_number = _num(match.get("prediction_index"))
        if match_number is None or match_number <= 1 or match_number >= target_game:
            continue
        actual = _actual_result(match)
        if not actual:
            continue
        home_team, away_team = _clean_team(match.get("home_team")), _clean_team(match.get("away_team"))
        if not home_team or not away_team:
            continue

        asof = int(match_number) - 1
        home = _profile_at(snapshots, asof, home_team, base_xg, base_goals)
        away = _profile_at(snapshots, asof, away_team, base_xg, base_goals)
        row = {
            "match_id": match.get("match_id"),
            "match_number": int(match_number),
            "home_team": home_team,
            "away_team": away_team,
            "target_result": actual["outcome"],
            "target_home_goals": actual["home"],
            "target_away_goals": actual["away"],
            **_features(home, away),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def _expected_goals(
    team: dict[str, float],
    opp: dict[str, float],
    base_xg: float,
    is_home: bool = False,
    calibration: dict[str, float] | None = None,
) -> float:
    cal = calibration or CALIBRATION
    rel = team.get("reliability", _reliability(team["jogos"]))
    opp_rel = opp.get("reliability", _reliability(opp["jogos"]))
    attack_xg = _blend(base_xg, team["xg_pj"], rel)
    attack_goals = _blend(base_xg, team["gols_pj"], rel * 0.65)
    conceded_xg = _blend(base_xg, opp["xg_sofrido_pj"], opp_rel)
    conceded_goals = _blend(base_xg, opp["gols_contra_pj"], opp_rel * 0.65)

    attack = 0.62 * attack_xg + 0.20 * attack_goals + 0.18 * base_xg * (team["ataque"] / 50)
    opp_def = 0.64 * conceded_xg + 0.18 * conceded_goals + 0.18 * base_xg * ((100 - opp["defesa"]) / 50)
    raw = 0.60 * attack + 0.40 * opp_def
    # Termo de força: combina TODOS os sinais ricos do snapshot (não só gols).
    # score=força geral, ataque vs defesa do rival, Elo, controle territorial e
    # eficiência (qualidade de finalização — converte chance em gol). Tudo entra
    # como diferença relativa ao adversário. `strength_scale` (calibrável) controla
    # o quanto a superioridade vira favoritismo: valor alto = favoritos mais
    # claros. A versão anterior diluía demais (Brasil dominante saía só 39%).
    strength_exponent = (
        ((team["score"] - opp["score"]) / 240)
        + ((team["ataque"] - opp["defesa"]) / 260)
        + ((team["elo"] - opp["elo"]) / 2200)
        + ((team["controle"] - opp["controle"]) / 520)
        + ((team["eficiencia"] - opp["eficiencia"]) / 600)
    )
    strength = exp(strength_exponent * cal.get("strength_scale", 1.0))
    mando = cal["home_advantage"] if is_home else 1.0
    return _clip(raw * strength * cal["global_scale"] * mando, 0.38, 3.8)


def _draw_factor(
    home: dict[str, float],
    away: dict[str, float],
    home_xg: float,
    away_xg: float,
    calibration: dict[str, float] | None = None,
) -> float:
    cal = calibration or CALIBRATION
    xg_gap = abs(home_xg - away_xg)
    score_gap = abs(home["score"] - away["score"]) / 55
    elo_gap = abs(home["elo"] - away["elo"]) / 190
    gap = (xg_gap / 1.25) + score_gap + elo_gap
    return _clip(cal["draw_base"] - (cal["draw_slope"] * gap), cal["draw_min"], cal["draw_base"])


def _confidence(home: dict[str, float], away: dict[str, float], probs: dict[str, Any]) -> dict[str, str]:
    games = min(home["jogos"], away["jogos"])
    top = max(probs["home_win"], probs["draw"], probs["away_win"])
    if games >= 3 and top >= 52:
        return {"nivel": "alta", "label": "boa amostra e favorito claro"}
    if games >= 2:
        return {"nivel": "media", "label": "amostra razoavel"}
    return {"nivel": "baixa", "label": "poucos jogos no recorte"}


def _factor(
    label: str,
    home_val: float,
    away_val: float,
    unit: str = "",
    lower_is_better: bool = False,
) -> dict[str, Any]:
    diff = home_val - away_val
    if abs(diff) < 0.01:
        edge = "even"
    elif lower_is_better:
        edge = "home" if diff < 0 else "away"
    else:
        edge = "home" if diff > 0 else "away"
    return {
        "label": label,
        "home": _round(home_val, 2),
        "away": _round(away_val, 2),
        "diff": _round(abs(diff), 2),
        "unit": unit,
        "edge": edge,
    }


def _favorite(probs: dict[str, Any], home_team: str, away_team: str) -> tuple[str, str]:
    home_win = probs["home_win"]
    draw = probs["draw"]
    away_win = probs["away_win"]
    if draw >= max(home_win, away_win) + 3:
        return "Empate", "draw"
    if home_win >= away_win:
        return home_team, "home"
    return away_team, "away"


def _field(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _actual_result(match: Any) -> dict[str, Any] | None:
    status = _field(match, "status")
    home_score = _num(_field(match, "home_score"))
    away_score = _num(_field(match, "away_score"))
    if status != "finalizado" or home_score is None or away_score is None:
        return None
    home_goals = int(home_score)
    away_goals = int(away_score)
    if home_goals > away_goals:
        outcome = "home"
    elif away_goals > home_goals:
        outcome = "away"
    else:
        outcome = "draw"
    return {"home": home_goals, "away": away_goals, "outcome": outcome}


def _prediction_evaluation(probs: dict[str, Any], actual: dict[str, Any] | None) -> dict[str, Any] | None:
    if actual is None:
        return None
    predicted = _predicted_outcome(probs)
    score = probs.get("score") or probs.get("scoreline", {}).get("recommended") or {"home": 0, "away": 0}
    score_home = int(score["home"])
    score_away = int(score["away"])
    goal_error_home = abs(score_home - int(actual["home"]))
    goal_error_away = abs(score_away - int(actual["away"]))
    return {
        "predicted_outcome": predicted,
        "actual_outcome": actual["outcome"],
        "winner_hit": predicted == actual["outcome"],
        "exact_score": score_home == actual["home"] and score_away == actual["away"],
        "goal_error_home": goal_error_home,
        "goal_error_away": goal_error_away,
        "goal_error_total": goal_error_home + goal_error_away,
        "goal_mae": _round((goal_error_home + goal_error_away) / 2, 2),
        "actual_probability": _round(_actual_probability(probs, actual["outcome"]) * 100, 1),
    }


def _class_probs(classes: np.ndarray, values: np.ndarray, floor: float = 0.03) -> dict[str, float]:
    """Probabilidades por classe, com piso para nao zerar nenhum resultado.

    Sem piso, um modelo (tipicamente a LogReg) atribui ~0% a um resultado que
    acaba acontecendo e o log-loss explode. O piso de 3% reflete que nenhum dos
    tres resultados de um jogo de futebol e realmente impossivel.
    """
    mapped = {name: 0.0 for name in OUTCOMES}
    for cls, prob in zip(classes, values):
        mapped[str(cls)] = max(float(prob), floor)
    total = sum(mapped.values()) or 1.0
    return {k: v / total for k, v in mapped.items()}


def _probs_from_float(mapped: dict[str, float]) -> dict[str, int]:
    return _prob_dict(mapped["home"], mapped["draw"], mapped["away"])


def _fit_logistic(train: pd.DataFrame, row: dict[str, float]) -> dict[str, Any] | None:
    """Classificador logístico ENXUTO: poucas features + regularização forte.

    Substitui o par LogReg(40 features) + RandomForest, que com ~48 jogos
    overfitavam e chegavam a inverter a previsão (87% pro azarão). Aqui o modelo
    usa só 4 diffs essenciais e C baixo, então no máximo concorda fraco — nunca
    contradiz violentamente o consenso de gols.
    """
    if len(train) < 18 or train["target_result"].nunique() < 2:
        return None
    cols = [c for c in LEAN_FEATURES if c in train.columns]
    if len(cols) < 2:
        return None
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=0.18, class_weight="balanced", max_iter=1000, random_state=42),
    )
    x_train = train[cols].astype(float).fillna(0.0)
    y_train = train["target_result"].astype(str)
    model.fit(x_train, y_train)
    x = pd.DataFrame([{c: row.get(c, 0.0) for c in cols}])
    probs = _class_probs(model.classes_, model.predict_proba(x)[0])
    return {"probabilities": _probs_from_float(probs), "sample_size": int(len(train))}


def _fit_poisson_regressor(
    train: pd.DataFrame,
    feature_cols: list[str],
    row: dict[str, float],
    draw_factor: float,
) -> dict[str, Any] | None:
    if len(train) < 18:
        return None
    x_train = train[feature_cols].astype(float).fillna(0.0)
    x = pd.DataFrame([{c: row.get(c, 0.0) for c in feature_cols}])
    home_model = make_pipeline(StandardScaler(), PoissonRegressor(alpha=1.2, max_iter=1000))
    away_model = make_pipeline(StandardScaler(), PoissonRegressor(alpha=1.2, max_iter=1000))
    home_model.fit(x_train, train["target_home_goals"].astype(float))
    away_model.fit(x_train, train["target_away_goals"].astype(float))
    home_xg = _clip(float(home_model.predict(x)[0]), 0.25, 3.8)
    away_xg = _clip(float(away_model.predict(x)[0]), 0.25, 3.8)
    return {
        "probabilities": _score_matrix(home_xg, away_xg, draw_factor),
        "expected_goals": {"home": _round(home_xg), "away": _round(away_xg)},
        "sample_size": int(len(train)),
    }


def _empirical_bayes(
    train: pd.DataFrame,
    home_team: str,
    away_team: str,
    base_goals: float,
    draw_factor: float,
) -> dict[str, Any] | None:
    if len(train) < 8:
        return None
    team_stats: dict[str, dict[str, float]] = {}
    for row in train.to_dict("records"):
        h_team = str(row.get("home_team", ""))
        a_team = str(row.get("away_team", ""))
        hg = float(row["target_home_goals"])
        ag = float(row["target_away_goals"])
        team_stats.setdefault(h_team, {"gf": 0.0, "ga": 0.0, "n": 0.0})
        team_stats.setdefault(a_team, {"gf": 0.0, "ga": 0.0, "n": 0.0})
        team_stats[h_team]["gf"] += hg
        team_stats[h_team]["ga"] += ag
        team_stats[h_team]["n"] += 1
        team_stats[a_team]["gf"] += ag
        team_stats[a_team]["ga"] += hg
        team_stats[a_team]["n"] += 1

    def rates(team: str) -> tuple[float, float]:
        stat = team_stats.get(team)
        if not stat or stat["n"] <= 0:
            return base_goals, base_goals
        weight = _clip(stat["n"] / (stat["n"] + 3.0), 0.0, 0.75)
        gf = _blend(base_goals, stat["gf"] / stat["n"], weight)
        ga = _blend(base_goals, stat["ga"] / stat["n"], weight)
        return gf, ga

    home_for, home_against = rates(home_team)
    away_for, away_against = rates(away_team)
    home_xg = _clip(0.56 * home_for + 0.44 * away_against, 0.25, 3.8)
    away_xg = _clip(0.56 * away_for + 0.44 * home_against, 0.25, 3.8)
    return {
        "probabilities": _score_matrix(home_xg, away_xg, draw_factor),
        "expected_goals": {"home": _round(home_xg), "away": _round(away_xg)},
        "sample_size": int(len(train)),
    }


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _model_pack(
    train: pd.DataFrame,
    feature_cols: list[str],
    feature_row: dict[str, float],
    home_team: str,
    away_team: str,
    home_xg: float,
    away_xg: float,
    draw_factor: float,
    base_goals: float,
    seed: int,
) -> dict[str, Any]:
    poisson = {
        "available": True,
        "probabilities": _score_matrix(home_xg, away_xg, draw_factor),
        "expected_goals": {"home": _round(home_xg), "away": _round(away_xg)},
        "sample_size": int(len(train)),
    }
    monte_carlo = {
        "available": True,
        "probabilities": _monte_carlo_probs(home_xg, away_xg, draw_factor, seed),
        "expected_goals": {"home": _round(home_xg), "away": _round(away_xg)},
        "sample_size": int(len(train)),
    }

    models: dict[str, dict[str, Any]] = {
        "poisson": poisson,
        "monte_carlo": monte_carlo,
        "logistic_regression": _unavailable("amostra insuficiente"),
        "poisson_regressor": _unavailable("amostra insuficiente"),
        "empirical_bayes": _unavailable("amostra insuficiente"),
    }

    logistic = _fit_logistic(train, feature_row)
    if logistic:
        models["logistic_regression"] = {"available": True, **logistic}

    poisson_reg = _fit_poisson_regressor(train, feature_cols, feature_row, draw_factor)
    if poisson_reg:
        models["poisson_regressor"] = {"available": True, **poisson_reg}

    bayes = _empirical_bayes(train, home_team, away_team, base_goals, draw_factor)
    if bayes:
        models["empirical_bayes"] = {"available": True, **bayes}

    return models


def _ensemble(
    models: dict[str, dict[str, Any]],
    fallback_xg: tuple[float, float] = (1.2, 1.2),
    weights: dict[str, float] | None = None,
) -> tuple[dict[str, int], dict[str, Any], tuple[float, float]]:
    w = weights or MODEL_WEIGHTS
    weighted = np.zeros(3, dtype=float)
    total_weight = 0.0
    xg_home = xg_away = xg_weight = 0.0
    available = []
    for name, model in models.items():
        if not model.get("available"):
            continue
        weight = w.get(name, 0.0)
        weighted += _prob_vector(model["probabilities"]) * weight
        total_weight += weight
        eg = model.get("expected_goals")
        if eg and eg.get("home") is not None and eg.get("away") is not None:
            xg_home += float(eg["home"]) * weight
            xg_away += float(eg["away"]) * weight
            xg_weight += weight
        available.append(name)
    if total_weight <= 0:
        return (
            {"home_win": 34, "draw": 32, "away_win": 34},
            {"level": "baixa", "divergence": "alta", "models": []},
            fallback_xg,
        )

    consensus_xg = (
        (xg_home / xg_weight, xg_away / xg_weight) if xg_weight > 0 else fallback_xg
    )
    vec = weighted / total_weight
    probs = _prob_dict(float(vec[0]), float(vec[1]), float(vec[2]))
    winners = []
    distances = []
    for name in available:
        mv = _prob_vector(models[name]["probabilities"])
        winners.append(OUTCOMES[int(np.argmax(mv))])
        distances.append(float(np.abs(mv - vec).mean() * 100))
    majority = max(winners.count(outcome) for outcome in set(winners)) / len(winners)
    avg_distance = float(np.mean(distances)) if distances else 0.0
    consensus = "forte" if majority >= 0.75 and avg_distance < 8 else "media" if majority >= 0.55 else "baixa"
    divergence = "baixa" if avg_distance < 6 else "media" if avg_distance < 12 else "alta"
    return probs, {
        "level": consensus,
        "divergence": divergence,
        "avg_probability_gap": _round(avg_distance, 1),
        "models": available,
    }, consensus_xg


def _summary(
    home_team: str,
    away_team: str,
    favorite_side: str,
    probs: dict[str, Any],
    home_xg: float,
    away_xg: float,
    draw_factor: float,
) -> dict[str, Any]:
    total_xg = home_xg + away_xg
    gap = abs(probs["home_win"] - probs["away_win"])
    if favorite_side == "draw":
        title = "Jogo realmente parelho"
        detail = "Empate lidera a distribuicao, mas a leitura fica aberta para os dois lados."
    else:
        side_name = home_team if favorite_side == "home" else away_team
        other = away_team if favorite_side == "home" else home_team
        if gap >= 24:
            title = f"{side_name} com favoritismo claro"
        elif gap >= 10:
            title = f"{side_name} com vantagem moderada"
        else:
            title = f"{side_name} por margem curta"
        detail = (
            f"{side_name} combina melhor volume esperado e forca recente, "
            f"mas {other} ainda fica competitivo se baixar o ritmo do jogo."
        )

    risk = "baixo"
    if probs["draw"] >= 30 or total_xg < 2.35:
        risk = "alto"
    elif probs["draw"] >= 25 or gap < 12:
        risk = "medio"

    return {
        "title": title,
        "detail": detail,
        "draw_risk": risk,
        "total_xg": _round(total_xg),
        "xg_gap": _round(abs(home_xg - away_xg)),
        "draw_calibration": _round(draw_factor, 2),
    }


def build_predictive(
    dim_match: pd.DataFrame,
    timeline: pd.DataFrame,
    snapshot: int | None = None,
    min_prediction_game: int = MIN_PREDICTION_GAME,
    calibration: dict[str, float] | None = None,
    weights: dict[str, float] | None = None,
    freeze: bool = False,
    min_display_game: int = MIN_DISPLAY_GAME,
) -> dict[str, Any]:
    """Prevê o jogo do snapshot-alvo usando só dados até o snapshot anterior.

    `calibration`/`weights` permitem injetar parâmetros aprendidos (auto-calibração
    e pesos adaptativos). Se None, usa os defaults ou o que foi carregado do disco.

    `freeze=True` (caminho de produção): o primeiro palpite de cada jogo é salvo e
    reusado nas próximas chamadas — o "palpite oficial". A realidade (resultado e
    avaliação) é sempre recalculada por cima do palpite congelado.

    Dois limiares distintos: a previsão APARECE a partir de `min_display_game` (a
    partir do jogo 2 há ao menos 1 jogo de base), mas só CONTA na métrica/backtest
    a partir de `min_prediction_game`. Entre os dois, a previsão sai marcada como
    `low_confidence` (pouca base — ruído alto), sem sujar a avaliação de qualidade.
    """
    calibration = calibration or load_learned_calibration()
    weights = weights or load_learned_weights()
    if dim_match.empty:
        return {"snapshot": snapshot, "matches": []}

    ordered = _ordered_matches(dim_match)
    if ordered.empty:
        return {"snapshot": snapshot, "matches": []}

    max_game = int(ordered["prediction_index"].max())
    if timeline.empty or "snapshot_jogo" not in timeline.columns:
        return {"snapshot": snapshot, "matches": []}
    latest_data_snapshot = int(timeline["snapshot_jogo"].max())
    latest_finalized = min(latest_data_snapshot + 1, max_game)
    target_game = int(snapshot) if snapshot is not None else latest_finalized
    target_game = int(_clip(float(target_game), 1, max_game))
    if target_game < min_display_game:
        return {
            "snapshot": target_game,
            "as_of_snapshot": None,
            "base": {
                "modo": "jogo_unico",
                "min_prediction_game": min_prediction_game,
                "min_display_game": min_display_game,
                "status": "indisponivel_sem_base",
            },
            "matches": [],
        }
    low_confidence = target_game < min_prediction_game
    as_of_snapshot = max(1, min(target_game - 1, latest_data_snapshot))

    snap = _latest_snapshot(timeline, as_of_snapshot)
    if snap.empty:
        return {"snapshot": snapshot, "matches": []}
    target = target_game

    base_xg = _baseline(snap, "xg_pj", 1.25)
    base_goals = _baseline(snap, "gols_pj", 1.20)
    by_team = {str(r["team"]): r for r in snap.to_dict("records")}
    train = _training_table(ordered, timeline, target_game, base_xg, base_goals)
    feature_cols = _feature_columns()

    games = ordered[ordered["prediction_index"] == target_game].copy()

    if games.empty:
        return {"snapshot": target_game, "as_of_snapshot": as_of_snapshot, "matches": []}

    out: list[dict[str, Any]] = []
    for m in games.head(1).to_dict("records"):
        home_team, away_team = _clean_team(m.get("home_team")), _clean_team(m.get("away_team"))
        if not home_team or not away_team:
            continue
        home = _team_profile(by_team.get(home_team), base_xg, base_goals)
        away = _team_profile(by_team.get(away_team), base_xg, base_goals)
        home_xg = _expected_goals(home, away, base_xg, is_home=True, calibration=calibration)
        away_xg = _expected_goals(away, home, base_xg, is_home=False, calibration=calibration)
        draw_factor = _draw_factor(home, away, home_xg, away_xg, calibration=calibration)
        feature_row = _features(home, away)
        seed = _seed_for(m.get("match_id"), target)
        models = _model_pack(
            train,
            feature_cols,
            feature_row,
            home_team,
            away_team,
            home_xg,
            away_xg,
            draw_factor,
            base_goals,
            seed,
        )
        ensemble_probs, ensemble_info, consensus_xg = _ensemble(models, fallback_xg=(home_xg, away_xg), weights=weights)
        # Tudo o que o card mostra (placar, xG, resumo) sai do MESMO par de xG de
        # consenso do ensemble — nunca mais "2-1 recomendado" com xG 1,2 x 1,8.
        home_xg, away_xg = consensus_xg
        draw_factor = _draw_factor(home, away, home_xg, away_xg, calibration=calibration)
        probs = _with_scoreline(ensemble_probs, home_xg, away_xg, draw_factor)
        favorite, favorite_side = _favorite(probs, home_team, away_team)
        actual_result = _actual_result(m)

        # Campos do PALPITE (congeláveis) e campos da REALIDADE (sempre frescos).
        prediction = {
            "match_id": m.get("match_id"),
            "match_number": _num(m.get("prediction_index")),
            "official_match_number": _num(m.get("match_number")),
            "home_team": home_team,
            "away_team": away_team,
            "stage": m.get("stage"),
            "group": m.get("group"),
            "date_utc": m.get("date_utc"),
            "expected_goals": {"home": _round(home_xg), "away": _round(away_xg)},
            "probabilities": probs,
            "favorite": favorite,
            "favorite_side": favorite_side,
            "low_confidence": low_confidence,
            "models": models,
            "ensemble": ensemble_info,
            "consensus": ensemble_info["level"],
            "divergence": ensemble_info["divergence"],
            "confidence": _confidence(home, away, probs),
            "summary": _summary(home_team, away_team, favorite_side, probs, home_xg, away_xg, draw_factor),
            "factors": [
                _factor("Score geral", home["score"], away["score"]),
                _factor("Elo", home["elo"], away["elo"]),
                _factor("xG criado/jogo", home["xg_pj"], away["xg_pj"]),
                _factor("xG sofrido/jogo", home["xg_sofrido_pj"], away["xg_sofrido_pj"], lower_is_better=True),
                _factor("Controle", home["controle"], away["controle"]),
                _factor("Eficiencia", home["eficiencia"], away["eficiencia"]),
            ],
        }

        # Congelamento: o 1º palpite vira o oficial e não muda mais. Só congela
        # palpites GENUÍNOS (feitos antes do jogo acabar); se a 1ª visualização já
        # for pós-jogo, não há previsão real a congelar.
        frozen_at = None
        if freeze:
            prediction, frozen_at = _apply_freeze(prediction, already_final=actual_result is not None)

        # Realidade é sempre recalculada por cima do palpite (congelado ou não).
        prediction["frozen_at"] = frozen_at
        prediction["actual_result"] = actual_result
        prediction["evaluation"] = _prediction_evaluation(prediction["probabilities"], actual_result)
        out.append(prediction)

    return {
        "snapshot": target_game,
        "as_of_snapshot": as_of_snapshot,
        "base": {
            "xg_medio_time": _round(base_xg),
            "gols_medio_time": _round(base_goals),
            "modelo": "Ensemble as-of (calibrado): Poisson, Negative Binomial, Poisson Regressor, Empirical Bayes e logística enxuta",
            "treino_jogos": int(len(train)),
            "modelos": list(MODEL_WEIGHTS.keys()),
            "modo": "jogo_unico",
            "min_prediction_game": min_prediction_game,
            "min_display_game": min_display_game,
            "low_confidence": low_confidence,
        },
        "matches": out,
    }


def _actual_probability(probs: dict[str, Any], outcome: str) -> float:
    key = {"home": "home_win", "draw": "draw", "away": "away_win"}[outcome]
    return max(float(probs[key]) / 100, 1e-9)


def _brier(probs: dict[str, Any], outcome: str) -> float:
    vec = _prob_vector(probs)
    target = np.array([1.0 if o == outcome else 0.0 for o in OUTCOMES])
    return float(np.mean((vec - target) ** 2))


def _predicted_outcome(probs: dict[str, Any]) -> str:
    vec = _prob_vector(probs)
    return OUTCOMES[int(np.argmax(vec))]


def _metric_row(probs: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    outcome = actual["outcome"]
    predicted = _predicted_outcome(probs)
    score = probs.get("score") or probs.get("scoreline", {}).get("recommended") or {"home": 0, "away": 0}
    sh, sa = int(score["home"]), int(score["away"])
    ah, aa = int(actual["home"]), int(actual["away"])
    hit = predicted == outcome
    exact = sh == ah and sa == aa
    # "parcial": errou o vencedor mas acertou o SALDO de gols (chegou perto).
    diff_hit = (sh - sa) == (ah - aa)
    return {
        "predicted_outcome": predicted,
        "hit": hit,
        "exact_score": exact,
        "diff_hit": diff_hit,
        "partial_hit": (not hit) and diff_hit,
        "log_loss": -float(np.log(_actual_probability(probs, outcome))),
        "brier": _brier(probs, outcome),
        "goal_mae": (abs(sh - ah) + abs(sa - aa)) / 2,
    }


def _frame_fingerprint(df: pd.DataFrame) -> str:
    """Hash estavel do conteudo de um DataFrame para chave de cache."""
    if df.empty:
        return "empty"
    try:
        return hashlib.blake2b(
            pd.util.hash_pandas_object(df, index=True).values.tobytes(), digest_size=8
        ).hexdigest()
    except Exception:  # fallback defensivo
        return f"shape:{df.shape}"


# Cache em processo do backtest. O frontend re-dispara o backtest a cada troca de
# snapshot; recomputar ~40 jogos (cada um refit de varios modelos) leva segundos.
# Como o resultado so depende do CONTEUDO dos dados + parametros, memoizamos por
# fingerprint. Invalida sozinho quando o gold muda (novo jogo coletado).
_BACKTEST_CACHE: dict[tuple, dict[str, Any]] = {}
_BACKTEST_CACHE_MAX = 16


def build_backtest(
    dim_match: pd.DataFrame,
    timeline: pd.DataFrame,
    start: int = MIN_PREDICTION_GAME,
    end: int | None = None,
    min_prediction_game: int = MIN_PREDICTION_GAME,
    calibration: dict[str, float] | None = None,
    weights: dict[str, float] | None = None,
    display_start: int | None = None,
) -> dict[str, Any]:
    cache_key = (
        _frame_fingerprint(dim_match),
        _frame_fingerprint(timeline),
        int(start),
        -1 if end is None else int(end),
        int(min_prediction_game),
        None if calibration is None else tuple(sorted(calibration.items())),
        None if weights is None else tuple(sorted(weights.items())),
        -1 if display_start is None else int(display_start),
    )
    cached = _BACKTEST_CACHE.get(cache_key)
    if cached is not None:
        return cached
    result = _build_backtest_uncached(dim_match, timeline, start, end, min_prediction_game, calibration, weights, display_start)
    if len(_BACKTEST_CACHE) >= _BACKTEST_CACHE_MAX:
        _BACKTEST_CACHE.pop(next(iter(_BACKTEST_CACHE)))
    _BACKTEST_CACHE[cache_key] = result
    return result


def _build_backtest_uncached(
    dim_match: pd.DataFrame,
    timeline: pd.DataFrame,
    start: int = MIN_PREDICTION_GAME,
    end: int | None = None,
    min_prediction_game: int = MIN_PREDICTION_GAME,
    calibration: dict[str, float] | None = None,
    weights: dict[str, float] | None = None,
    display_start: int | None = None,
) -> dict[str, Any]:
    ordered = _ordered_matches(dim_match)
    if ordered.empty or timeline.empty:
        return {"rows": [], "summary": {}}
    latest_data_snapshot = int(timeline["snapshot_jogo"].max())
    max_game = int(ordered["prediction_index"].max())
    end_game = min(end if end is not None else latest_data_snapshot, max_game)
    rows: list[dict[str, Any]] = []
    by_model: dict[str, list[dict[str, Any]]] = {}

    # `display_start` permite avaliar (gerar linhas) desde os jogos iniciais para
    # COLORIR as bolinhas, mas o summary abaixo só conta a partir de
    # `min_prediction_game` para não sujar a métrica de qualidade.
    loop_start = display_start if display_start is not None else max(min_prediction_game, int(start))
    for game in range(int(loop_start), end_game + 1):
        pred = build_predictive(
            dim_match,
            timeline,
            snapshot=game,
            min_prediction_game=min_prediction_game,
            calibration=calibration,
            weights=weights,
        )
        if not pred.get("matches"):
            continue
        match = pred["matches"][0]
        actual = match.get("actual_result")
        if not actual:
            continue

        main_metrics = _metric_row(match["probabilities"], actual)
        in_metric = int(pred["snapshot"]) >= min_prediction_game
        row = {
            "snapshot": pred["snapshot"],
            "as_of_snapshot": pred.get("as_of_snapshot"),
            "match_id": match["match_id"],
            "match_number": match["match_number"],
            "home_team": match["home_team"],
            "away_team": match["away_team"],
            "actual": actual,
            "low_confidence": bool(match.get("low_confidence")),
            "probabilities": {
                "home_win": match["probabilities"]["home_win"],
                "draw": match["probabilities"]["draw"],
                "away_win": match["probabilities"]["away_win"],
            },
            **main_metrics,
            "consensus": match.get("consensus"),
            "divergence": match.get("divergence"),
        }
        rows.append(row)

        if in_metric:  # modelos individuais só contam na janela da métrica
            for name, model in (match.get("models") or {}).items():
                if not model.get("available") or "probabilities" not in model:
                    continue
                metric = _metric_row(model["probabilities"], actual)
                by_model.setdefault(name, []).append(metric)

    # O SUMMARY (qualidade do modelo) conta apenas a janela da métrica; as linhas
    # de baixa confiança existem só para colorir as bolinhas.
    metric_rows = [r for r in rows if not r.get("low_confidence")]

    def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
        if not items:
            return {}
        return {
            "n": len(items),
            "accuracy": _round(sum(1 for r in items if r["hit"]) / len(items), 3),
            "log_loss": _round(float(np.mean([r["log_loss"] for r in items])), 3),
            "brier": _round(float(np.mean([r["brier"] for r in items])), 3),
            "goal_mae": _round(float(np.mean([r["goal_mae"] for r in items])), 3),
        }

    summary = summarize(metric_rows)
    summary["models"] = {name: summarize(items) for name, items in by_model.items()}
    summary["draw_rate"] = {
        "predicted": _round(sum(1 for r in metric_rows if r["predicted_outcome"] == "draw") / len(metric_rows), 3) if metric_rows else None,
        "actual": _round(sum(1 for r in metric_rows if r["actual"]["outcome"] == "draw") / len(metric_rows), 3) if metric_rows else None,
    }
    if metric_rows:
        mid = max(1, len(metric_rows) // 2)
        early = summarize(metric_rows[:mid])
        recent = summarize(metric_rows[-min(10, len(metric_rows)):])
        summary["evolution"] = {
            "early": early,
            "recent": recent,
            "accuracy_delta": _round((recent.get("accuracy", 0) or 0) - (early.get("accuracy", 0) or 0), 3),
            "log_loss_delta": _round((recent.get("log_loss", 0) or 0) - (early.get("log_loss", 0) or 0), 3),
        }
    return {"summary": summary, "rows": rows}


# ──────────────────────────────────────────────────────────────────────────────
# AUTO-APRENDIZADO: o modelo se ajusta aos resultados reais
#
# Dois mecanismos, ambos guiados pelo MESMO backtest walk-forward (cada jogo so
# usa dados anteriores a ele — sem vazamento de futuro):
#
#   #1 learn_calibration: busca por coordenada nos parametros de CALIBRATION
#      (fator de empate, escala de gols, mando), escolhendo o conjunto que
#      MINIMIZA o log-loss agregado. É "aprender com os erros" de forma honesta:
#      a metrica de erro do passado define os parametros do futuro.
#
#   #2 learn_weights: da mais peso aos modelos do ensemble que vem ACERTANDO
#      mais (menor log-loss) no backtest, via softmax sobre -log_loss. Modelos
#      ruins encolhem; bons crescem.
#
# learn_and_save roda os dois, grava em predictive_calibration.json e devolve um
# relatorio antes/depois. O pipeline chama isso a cada coleta.
# ──────────────────────────────────────────────────────────────────────────────

# Grade de candidatos por knob (busca por coordenada). Enxuta de proposito: cada
# candidato custa um backtest walk-forward completo, entao limitamos aos knobs e
# valores que de fato movem o log-loss (medido empiricamente). Uma so passada.
_CALIBRATION_GRID = {
    "strength_scale": [1.0, 1.4, 1.8, 2.2, 2.6],
    "global_scale": [0.98, 1.02, 1.06, 1.10],
    "draw_min": [0.78, 0.85, 0.92],
    "draw_slope": [0.10, 0.14, 0.18],
}


def _backtest_loss(
    dim_match: pd.DataFrame,
    timeline: pd.DataFrame,
    calibration: dict[str, float],
    weights: dict[str, float] | None,
    start: int,
    end: int | None,
) -> float:
    bt = build_backtest(
        dim_match, timeline, start=start, end=end,
        min_prediction_game=start, calibration=calibration, weights=weights,
    )
    ll = bt.get("summary", {}).get("log_loss")
    return float(ll) if ll is not None else float("inf")


def learn_calibration(
    dim_match: pd.DataFrame,
    timeline: pd.DataFrame,
    start: int = MIN_PREDICTION_GAME,
    end: int | None = None,
    weights: dict[str, float] | None = None,
    passes: int = 1,
) -> tuple[dict[str, float], float]:
    """Busca por coordenada nos knobs de calibracao minimizando o log-loss."""
    best = dict(CALIBRATION)
    best_loss = _backtest_loss(dim_match, timeline, best, weights, start, end)
    for _ in range(max(1, passes)):
        improved = False
        for knob, candidates in _CALIBRATION_GRID.items():
            for value in candidates:
                if value == best[knob]:
                    continue
                trial = {**best, knob: value}
                loss = _backtest_loss(dim_match, timeline, trial, weights, start, end)
                if loss < best_loss - 1e-6:
                    best, best_loss = trial, loss
                    improved = True
        if not improved:
            break
    return best, best_loss


def learn_weights(
    dim_match: pd.DataFrame,
    timeline: pd.DataFrame,
    calibration: dict[str, float] | None = None,
    start: int = MIN_PREDICTION_GAME,
    end: int | None = None,
    temperature: float = 0.15,
    floor: float = 0.02,
) -> dict[str, float]:
    """Pesos ∝ softmax(-log_loss/T) por modelo, a partir do backtest.

    Modelos que acertam mais (log-loss menor) ganham mais peso. `floor` garante
    que nenhum modelo disponivel seja zerado de vez. So redistribui entre os
    modelos que efetivamente rodaram em quantidade suficiente de jogos.
    """
    bt = build_backtest(
        dim_match, timeline, start=start, end=end,
        min_prediction_game=start, calibration=calibration,
    )
    per_model = bt.get("summary", {}).get("models", {})
    n_total = bt.get("summary", {}).get("n", 0) or 0
    losses: dict[str, float] = {}
    for name in MODEL_WEIGHTS:
        m = per_model.get(name) or {}
        # só considera modelos que rodaram em pelo menos metade dos jogos
        if m.get("log_loss") is not None and (m.get("n", 0) or 0) >= max(1, n_total // 2):
            losses[name] = float(m["log_loss"])
    if len(losses) < 2:
        return dict(MODEL_WEIGHTS)  # dados insuficientes: mantem defaults

    names = list(losses)
    arr = np.array([losses[n] for n in names], dtype=float)
    logits = -(arr - arr.min()) / max(temperature, 1e-6)
    soft = np.exp(logits)
    soft = soft / soft.sum()
    soft = soft * (1 - floor * len(names)) + floor  # piso por modelo
    soft = soft / soft.sum()
    return {n: round(float(w), 4) for n, w in zip(names, soft)}


def learn_and_save(
    dim_match: pd.DataFrame,
    timeline: pd.DataFrame,
    start: int = MIN_PREDICTION_GAME,
    end: int | None = None,
) -> dict[str, Any]:
    """Aprende calibracao + pesos dos resultados reais, grava e devolve relatorio."""
    base = build_backtest(dim_match, timeline, start=start, end=end, min_prediction_game=start)
    before = base.get("summary", {})

    # 1) pesos adaptativos primeiro (usando calibracao default)…
    weights = learn_weights(dim_match, timeline, calibration=dict(CALIBRATION), start=start, end=end)
    # 2) …depois calibra com esses pesos
    calibration, _ = learn_calibration(dim_match, timeline, start=start, end=end, weights=weights)

    after = build_backtest(
        dim_match, timeline, start=start, end=end,
        min_prediction_game=start, calibration=calibration, weights=weights,
    ).get("summary", {})

    payload = {
        "calibration": calibration,
        "weights": weights,
        "metrics": {"before": _learn_metrics(before), "after": _learn_metrics(after)},
        "evaluated_games": after.get("n"),
        "start": start,
    }
    _CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CALIBRATION_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    reset_learned_cache()
    _BACKTEST_CACHE.clear()
    return payload


def _learn_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    return {k: summary.get(k) for k in ("n", "accuracy", "log_loss", "brier", "goal_mae")}
