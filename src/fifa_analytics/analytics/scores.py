"""Scores de seleções — fonte única FIFA (fdh).

Entrada: team_match_wide (uma linha por match_id+team, colunas do pivot.py)
         dim_match (resultado/status dos jogos)

Saída: DataFrame com uma linha por seleção contendo todos os scores,
       métricas acumuladas e métricas por jogo.

Pesos fixos (TEAM_SCORE_WEIGHTS):
  Não usamos calibração automática (RidgeCV) porque o torneio tem no máximo
  7 jogos por seleção — amostra insuficiente para regressão estável. Os pesos
  refletem julgamento de design: resultado domina (o placar é a verdade),
  defesa vale ligeiramente mais que ataque, controle e eficiência são
  complementares. score_forca_relativa escala via _elo_maturity_factor para
  não contar na rodada 1 quando todos os Elos são iguais.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from fifa_analytics.utils.text import slugify

# ---------------------------------------------------------------------------
# Pesos fixos
# ---------------------------------------------------------------------------
TEAM_SCORE_WEIGHTS: dict[str, float] = {
    "score_resultado":       0.30,
    "score_ataque":          0.20,
    "score_defesa":          0.20,
    "score_eficiencia":      0.10,
    "score_controle":        0.10,
    "score_forca_relativa":  0.10,
}

ELO_INITIAL_RATING = 1500.0
ELO_K_FACTOR = 40.0
ELO_MARGIN_CAP = 3.0
_ELO_MAX_VARIANCE_MAX_GAMES = 3


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def _safe_divide(num: pd.Series, den: pd.Series) -> pd.Series:
    return num.where(den.fillna(0) > 0, other=float("nan")) / den.where(den.fillna(0) > 0, other=1)


def _num(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return default if np.isnan(v) else v
    except (TypeError, ValueError):
        return default


def _zscore_to_100(
    series: pd.Series,
    lower_is_better: bool = False,
    ref: tuple[float, float] | None = None,
) -> pd.Series:
    """Normaliza via z-score para escala 0-100 (média ≈ 50).

    Se `ref=(mean, std)` for dado, usa essa referência FIXA em vez da média/desvio
    do próprio `series`. Isso torna o score estável entre snapshots: o valor de um
    time só muda quando o próprio time joga, não quando o campo muda. Sem `ref`,
    mantém o comportamento relativo antigo (normaliza contra o próprio series).
    """
    s = pd.to_numeric(series, errors="coerce")
    if ref is not None:
        mean, std = ref
    else:
        mean, std = s.mean(), s.std(ddof=0)
    if s.isna().all() or std == 0 or pd.isna(std):
        return pd.Series(50.0, index=series.index)
    # Linha sem a métrica (ex.: métrica fdh ausente naquele jogo, como
    # FinalThirdEntries) vira NEUTRA (z=0 → 50) em vez de virar NaN e zerar o
    # score inteiro — os demais sub-componentes seguem contando normalmente.
    z = (s.fillna(mean) - mean) / std
    if lower_is_better:
        z = -z
    # 1 desvio-padrão = 25 pontos: abre bem a escala (top ~85, fundo ~15),
    # em vez de espremer tudo em 30-70.
    return (50 + z * 25).clip(0, 100)


def _mean_score(components: list[pd.Series]) -> pd.Series:
    valid = [c for c in components if not c.isna().all()]
    if not valid:
        return pd.Series(50.0)
    return pd.concat(valid, axis=1).mean(axis=1)


def _sample_confidence(jogos: pd.Series) -> pd.Series:
    """REMOVIDA: confiança por amostra desativada (sempre 1.0). Cada jogo já traz
    ~150 métricas da FIFA — muita informação por partida —, então não faz sentido
    encolher a nota pro meio só pela contagem de jogos. As notas valem integralmente
    desde o 1º jogo (coerente com o Resultado, que já rodava a 100%)."""
    j = pd.to_numeric(jogos, errors="coerce").fillna(0)
    return pd.Series(1.0, index=j.index).where(j > 0, 0.0)


def _apply_confidence(score: pd.Series, conf: pd.Series) -> pd.Series:
    return (50.0 * (1 - conf) + score * conf).round(1)


def _add_rank(df: pd.DataFrame, col: str, rank_col: str) -> pd.DataFrame:
    if col in df.columns:
        df[rank_col] = (
            df[col]
            .rank(ascending=False, method="min", na_option="bottom")
            .fillna(len(df))
            .astype(int)
        )
    return df


def _evidence_level(conf: float) -> str:
    if conf < 0.5:
        return "baixa"
    if conf < 0.75:
        return "media"
    return "alta"


# ---------------------------------------------------------------------------
# Elo
# ---------------------------------------------------------------------------

def _performance_index(gols: float, xg: float, chutes_no_alvo: float, posse_pct: float,
                       threat: float = 0.0) -> float:
    """Índice de desempenho (quão convincente foi a atuação, dentro da faixa do
    resultado). Blend de perigo + resultado; posse é coadjuvante (antes dominava
    96% por estar em escala 0-100 × 5). threat = ameaça holística."""
    return gols * 3.0 + xg * 2.0 + chutes_no_alvo * 0.5 + posse_pct * 0.05 + threat * 0.05


def _run_elo_simulation(
    games: pd.DataFrame,
    initial_ratings: dict[str, float] | None = None,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """Passada cronológica de Elo. Retorna ratings finais + log pré-jogo.

    `games` deve ter uma linha por time por jogo com colunas:
    match_id, team, date_utc (ou match_id para ordem), gols, xg,
    chutes_no_alvo, posse (decimal 0-1).
    """
    seed = dict(initial_ratings) if initial_ratings else {}
    ratings: dict[str, float] = {}
    pre_match_log: list[dict[str, Any]] = []

    sort_col = "date_utc" if "date_utc" in games.columns else "match_id"
    for match_id, game in games.sort_values(sort_col).groupby("match_id", sort=False):
        if len(game) != 2:
            continue
        a, b = game.iloc[0], game.iloc[1]
        ta, tb = str(a["team"]), str(b["team"])
        ra = ratings.setdefault(ta, seed.get(ta, ELO_INITIAL_RATING))
        rb = ratings.setdefault(tb, seed.get(tb, ELO_INITIAL_RATING))

        pre_match_log += [
            {"match_id": match_id, "team": ta, "opponent_elo_pre": rb},
            {"match_id": match_id, "team": tb, "opponent_elo_pre": ra},
        ]

        ga = _num(a.get("gols")); gb = _num(b.get("gols"))
        xga = _num(a.get("xg")); xgb = _num(b.get("xg"))
        sna = _num(a.get("chutes_no_alvo")); snb = _num(b.get("chutes_no_alvo"))
        pa = _num(a.get("posse")) * 100; pb = _num(b.get("posse")) * 100
        tha = _num(a.get("threat")); thb = _num(b.get("threat"))

        perf_a = _performance_index(ga, xga, sna, pa, tha)
        perf_b = _performance_index(gb, xgb, snb, pb, thb)
        share_a = perf_a / (perf_a + perf_b) if (perf_a + perf_b) > 0 else 0.5

        if ga > gb:
            lo, hi = 2 / 3, 1.0
        elif ga < gb:
            lo, hi = 0.0, 1 / 3
        else:
            lo, hi = 1 / 3, 2 / 3
        score_a = lo + (hi - lo) * share_a

        expected_a = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
        if ga > gb:
            score_a = max(score_a, expected_a)
        elif ga < gb:
            score_a = min(score_a, expected_a)

        saldo_efetivo = abs(0.5 * (ga - gb) + 0.5 * (xga - xgb))
        margin = min(1.0 + 0.6 * np.sqrt(saldo_efetivo), ELO_MARGIN_CAP)
        delta = ELO_K_FACTOR * margin * (score_a - expected_a)

        ratings[ta] = ra + delta
        ratings[tb] = rb - delta

    return ratings, pre_match_log


def calculate_elo_ratings(team_game_df: pd.DataFrame) -> pd.DataFrame:
    ratings, _ = _run_elo_simulation(team_game_df)
    return pd.DataFrame({"team": list(ratings), "elo_rating": list(ratings.values())})


def calculate_post_match_opponent_elo(team_game_df: pd.DataFrame) -> pd.DataFrame:
    final_ratings, _ = _run_elo_simulation(team_game_df)
    rows: list[dict[str, Any]] = []
    for match_id, game in team_game_df.groupby("match_id"):
        if len(game) != 2:
            continue
        ta, tb = str(game.iloc[0]["team"]), str(game.iloc[1]["team"])
        rows += [
            {"match_id": match_id, "team": ta, "opponent_elo": final_ratings.get(tb, ELO_INITIAL_RATING)},
            {"match_id": match_id, "team": tb, "opponent_elo": final_ratings.get(ta, ELO_INITIAL_RATING)},
        ]
    return pd.DataFrame(rows)


def calculate_pre_match_opponent_elo(team_game_df: pd.DataFrame) -> pd.DataFrame:
    """Elo do adversário NO MOMENTO do confronto (pré-jogo).

    Diferente do pós-jogo, este valor é estável: depende só dos jogos até aquele
    confronto, não evolui quando o adversário joga de novo depois. Isso mantém o
    aproveitamento ponderado de um time inalterado entre snapshots enquanto o
    próprio time não joga.
    """
    _, pre_log = _run_elo_simulation(team_game_df)
    if not pre_log:
        return pd.DataFrame(columns=["match_id", "team", "opponent_elo"])
    return pd.DataFrame(pre_log).rename(columns={"opponent_elo_pre": "opponent_elo"})


@lru_cache(maxsize=8)
def _simulate_max_elo_variance(n_games: int, n_teams: int = 32, goal_margin: int = 7) -> float:
    half = n_teams // 2
    rows = []
    mid = 0
    for _ in range(n_games):
        for i in range(half):
            mid += 1
            for team, g, x, sn, p in [
                (f"s{i}", goal_margin + 1, goal_margin * 0.6, 10, 0.65),
                (f"w{i}", 1, 0.3, 2, 0.35),
            ]:
                rows.append({"match_id": mid, "team": team,
                             "gols": g, "xg": x, "chutes_no_alvo": sn, "posse": p})
    synthetic = pd.DataFrame(rows)
    rts, _ = _run_elo_simulation(synthetic)
    return float(np.var(list(rts.values())))


def _elo_maturity_factor(elo_rating: pd.Series, jogos: pd.Series) -> pd.Series:
    avg = int(round(jogos.mean())) if len(jogos) else 0
    if avg <= 0:
        return pd.Series(0.0, index=elo_rating.index)
    max_var = _simulate_max_elo_variance(min(avg, _ELO_MAX_VARIANCE_MAX_GAMES))
    obs_var = elo_rating.var(ddof=0)
    if pd.isna(obs_var) or max_var <= 0:
        return pd.Series(0.0, index=elo_rating.index)
    return pd.Series(min(obs_var / max_var, 1.0), index=elo_rating.index)


# ---------------------------------------------------------------------------
# Aproveitamento ponderado pelo Elo do adversário
# ---------------------------------------------------------------------------

def _weighted_aproveitamento(
    game_results: pd.DataFrame,
    opp_elo: pd.DataFrame,
) -> pd.DataFrame:
    """game_results: match_id, team, points. opp_elo: match_id, team, opponent_elo.

    O peso do adversário usa âncora FIXA (1500 = Elo inicial), não a média do
    campo: assim o aproveitamento ponderado não muda quando OUTROS times jogam.

    Crédito ABSOLUTO pelo adversário (média de pontos ponderados por jogo).
    A versão antiga era a razão Σ(p·w)/Σ(3·w), em que o peso se CANCELA por
    jogo — empatar com a Espanha valia o MESMO que empatar com a Jordânia. Agora
    segurar/bater um time forte (peso>1) rende mais que o mesmo resultado contra
    um fraco (peso<1). Divide por 3 só para manter a escala ~0-1 da versão sem
    Elo; o z-score downstream reescala de qualquer forma.
    """
    if opp_elo.empty:
        agg = game_results.groupby("team")["points"].mean().rename("aproveitamento_ponderado") / 3
        return agg.reset_index()

    df = game_results.merge(opp_elo, on=["match_id", "team"], how="left")
    df["opp_elo"] = df["opponent_elo"].fillna(ELO_INITIAL_RATING)
    # Sensibilidade /250 (antes /400): a mesma diferença de Elo gera um peso ~1,6×
    # maior, então enfrentar um time que JÁ se provou forte pesa mais cedo — sem
    # prior de reputação (Elo ainda parte de 1500). Clip alargado p/ caber a
    # divergência maior conforme o torneio avança.
    df["opp_weight"] = (1.0 + (df["opp_elo"] - ELO_INITIAL_RATING) / 250.0).clip(0.4, 2.2)
    df["w_pts"] = df["points"] * df["opp_weight"]
    agg = (df.groupby("team")["w_pts"].mean() / 3.0).rename("aproveitamento_ponderado")
    return agg.reset_index()


# ---------------------------------------------------------------------------
# Estilo de jogo (Phase* metrics)
# ---------------------------------------------------------------------------
_PHASE_COLS = [
    "fase_transicao_ofensiva", "fase_construcao_pressionada", "fase_construcao_livre",
    "fase_contra_ataque", "fase_contra_pressao", "fase_transicao_defensiva",
    "fase_terceiro_final", "fase_bloco_alto", "fase_pressao_alta",
    "fase_bola_longa", "fase_bloco_baixo", "fase_pressao_baixa",
    "fase_bloco_medio", "fase_pressao_media", "fase_progressao",
    "fase_recuperacao", "fase_bola_parada",
]


def _add_team_style(
    scores: pd.DataFrame,
    game_df: pd.DataFrame,
    ref_stats: dict[str, tuple[float, float]] | None = None,
) -> pd.DataFrame:
    """Calcula estilo de jogo a partir das métricas Phase* do fdh.

    Mantém 4 eixos numéricos bipolares (radar do dashboard) e deriva o RÓTULO
    `estilo_jogo` de 6 arquétipos bem definidos, com fases exclusivas:
    - Posse:         construção livre + pressionada + progressão + terço final
    - Pressão Alta:  pressão alta + bloco alto + contra-pressão + recuperação
    - Contra-ataque: contra-ataque + transição ofensiva
    - Retranca:      bloco baixo + pressão baixa + transição defensiva
    - Jogo Direto:   bola longa
    - Bola Parada:   bola parada
    (bloco/pressão médios ficam de fora — setups equilibrados, não um estilo.)
    """
    present = [c for c in _PHASE_COLS if c in game_df.columns]
    if not present:
        for col in ["estilo_posse", "estilo_pressao", "estilo_verticalidade", "estilo_bola_parada"]:
            scores[col] = None
        scores["estilo_jogo"] = None
        return scores

    phase = game_df.groupby("team")[present].mean()

    def _zt(col: str) -> pd.Series:
        s = phase.get(col, pd.Series(0.0, index=phase.index))
        key = f"style_{col}"
        if ref_stats is not None and key in ref_stats:
            mean, std = ref_stats[key]
        else:
            mean, std = s.mean(), s.std(ddof=0)
            if ref_stats is not None:
                ref_stats[key] = (mean, std)
        if std == 0 or pd.isna(std):
            return pd.Series(50.0, index=phase.index)
        return ((s - mean) / std * 25 + 50).clip(0, 100)

    style = pd.DataFrame(index=phase.index)
    # Eixos numéricos bipolares (radar do dashboard) — mantidos p/ compat.
    style["estilo_posse"] = _mean_score([
        _zt("fase_construcao_livre"), _zt("fase_construcao_pressionada"), _zt("fase_progressao")
    ])
    style["estilo_pressao"] = _mean_score([
        _zt("fase_pressao_alta"), _zt("fase_contra_pressao"), _zt("fase_transicao_ofensiva")
    ])
    style["estilo_verticalidade"] = _mean_score([
        _zt("fase_bola_longa"), _zt("fase_contra_ataque"), _zt("fase_transicao_ofensiva")
    ])
    style["estilo_bola_parada"] = _zt("fase_bola_parada")

    # Eixos do MAPA de estilos — desenhados para SEPARAR os 6 arquétipos em
    # quadrantes nomeados (os eixos posse×verticalidade não conseguiam: pressão,
    # retranca e bola parada caíam todos no centro).
    #   X = Reativo (−) ↔ Proativo (+): quem toma a iniciativa do jogo.
    #   Y = Direto (−)  ↔ Elaborado (+): como chega ao gol (vertical vs construído).
    proativo = _mean_score([
        _zt("fase_construcao_livre"), _zt("fase_construcao_pressionada"),
        _zt("fase_progressao"), _zt("fase_pressao_alta"), _zt("fase_bloco_alto")])
    reativo = _mean_score([
        _zt("fase_bloco_baixo"), _zt("fase_pressao_baixa"),
        _zt("fase_transicao_defensiva"), _zt("fase_contra_ataque")])
    elaborado = _mean_score([
        _zt("fase_construcao_livre"), _zt("fase_construcao_pressionada"),
        _zt("fase_progressao"), _zt("fase_terceiro_final")])
    direto = _mean_score([
        _zt("fase_bola_longa"), _zt("fase_contra_ataque"), _zt("fase_bola_parada")])
    # Centrado em 50 (0-100): >50 = proativo/elaborado, <50 = reativo/direto.
    style["estilo_proatividade"] = (50 + (proativo - reativo) / 2).clip(0, 100)
    style["estilo_diretude"] = (50 + (elaborado - direto) / 2).clip(0, 100)

    # Rótulo descritivo — 6 arquétipos bem definidos (fases exclusivas).
    arquetipos = pd.DataFrame({
        "Posse": _mean_score([
            _zt("fase_construcao_livre"), _zt("fase_construcao_pressionada"),
            _zt("fase_progressao"), _zt("fase_terceiro_final")]),
        "Pressão Alta": _mean_score([
            _zt("fase_pressao_alta"), _zt("fase_bloco_alto"),
            _zt("fase_contra_pressao"), _zt("fase_recuperacao")]),
        "Contra-ataque": _mean_score([
            _zt("fase_contra_ataque"), _zt("fase_transicao_ofensiva")]),
        "Retranca": _mean_score([
            _zt("fase_bloco_baixo"), _zt("fase_pressao_baixa"),
            _zt("fase_transicao_defensiva")]),
        "Jogo Direto": _zt("fase_bola_longa"),
        "Bola Parada": _zt("fase_bola_parada"),
    }, index=phase.index)
    style["estilo_jogo"] = arquetipos.idxmax(axis=1)
    style = style.reset_index()
    return scores.merge(style, on="team", how="left")


# ---------------------------------------------------------------------------
# Score principal
# ---------------------------------------------------------------------------

def build_team_scores(
    wide: pd.DataFrame,
    dim_match: pd.DataFrame,
    weights: dict[str, float] | None = None,
    ref_stats: dict[str, tuple[float, float]] | None = None,
) -> pd.DataFrame:
    """Calcula scores de seleção a partir do wide (uma linha por match+team).

    `wide` vem de `fifa.pivot.build_team_match_wide()`.
    `dim_match` é o calendário completo (para resultado/status).

    `ref_stats` (referência fixa de normalização): se for um dict, cada z-score
    usa a média/desvio guardados ali sob uma chave estável; chaves ausentes são
    calculadas do campo atual e GRAVADAS no dict. O padrão de uso é:
      1. uma passada sobre TODOS os jogos com um dict vazio → popula a referência;
      2. cada snapshot reusa o MESMO dict → scores estáveis entre snapshots
         (o valor de um time só muda quando o próprio time joga).
    Sem `ref_stats` (None), o comportamento é o relativo antigo (normaliza contra
    o campo do snapshot).
    """
    if wide.empty:
        return pd.DataFrame()

    w = weights or TEAM_SCORE_WEIGHTS

    def zt(series: pd.Series, key: str, lower_is_better: bool = False) -> pd.Series:
        """z-score 0-100 usando referência fixa de `ref_stats[key]` quando houver."""
        ref = None
        if ref_stats is not None:
            if key not in ref_stats:
                s = pd.to_numeric(series, errors="coerce")
                ref_stats[key] = (float(s.mean()), float(s.std(ddof=0)))
            ref = ref_stats[key]
        return _zscore_to_100(series, lower_is_better=lower_is_better, ref=ref)

    # --- Resultado por jogo (fonte de verdade: dim_match) ---
    finished = dim_match[dim_match["status"] == "finalizado"].copy()
    game_rows: list[dict[str, Any]] = []
    for _, m in finished.iterrows():
        hs = _num(m.get("home_score"))
        as_ = _num(m.get("away_score"))
        for team, gf, ga in [(m["home_team"], hs, as_), (m["away_team"], as_, hs)]:
            result = "vitoria" if gf > ga else ("empate" if gf == ga else "derrota")
            game_rows.append({
                "match_id": m["match_id"], "team": team,
                "date_utc": m.get("date_utc"),
                "gols": gf, "gols_contra": ga,
                "result": result,
                "points": 3 if result == "vitoria" else (1 if result == "empate" else 0),
                "clean_sheet": int(ga == 0),
            })
    game_df = pd.DataFrame(game_rows)
    if game_df.empty:
        return pd.DataFrame()

    # Enriquecer com métricas fdh do wide — exclui colunas que já vêm de game_rows
    # para evitar sufixos _x/_y no merge.
    _game_cols = {"match_id", "id_team", "team", "date_utc", "stage", "group",
                  "gols", "gols_contra", "result", "points", "clean_sheet"}
    fdh_cols = [c for c in wide.columns if c not in _game_cols]
    game_df = game_df.merge(wide[["match_id", "team"] + fdh_cols], on=["match_id", "team"], how="left")

    # xG sofrido = xG de ataque do adversário no MESMO jogo (derivado do confronto).
    if "xg" in game_df.columns:
        _gm = game_df.groupby("match_id")
        game_df["xg_sofrido"] = (_gm["xg"].transform("sum") - game_df["xg"]).where(
            _gm["team"].transform("size") == 2
        )

    # --- Agregações por seleção ---
    SUM_COLS = [
        "points", "clean_sheet",
        "chutes", "chutes_no_alvo", "chutes_bloqueados", "chutes_dentro_area",
        "entradas_3o_central", "entradas_3o_esq", "entradas_3o_dir",
        "chutes_sofridos", "chutes_sofridos_no_alvo",
        "xg", "xg_sofrido", "threat",
        "passes", "passes_certos",
        "progressoes_bola", "progressoes_tentadas",
        "distribuicoes_certas_sob_pressao", "distribuicoes_sob_pressao",
        "linebreaks", "linebreaks_tentados",
        "defesas_goleiro", "defesas_goleiro_no_alvo",
        "turnovers_forcados", "pressoes_defensivas",
        "faltas_cometidas", "faltas_sofridas",
        "amarelos", "vermelhos",
        "impedimentos", "escanteios",
        "sprints", "corridas_alta_vel",
        "dribles_certos", "trocas_lado_certas",
    ]
    MEAN_COLS = [
        "posse", "pitch_control", "final_third_control",
        "save_pct_goleiro",
        "distancia_total", "velocidade_media", "velocidade_maxima",
    ] + [c for c in game_df.columns if c.startswith("fase_")]

    agg_dict: dict[str, Any] = {"match_id": "nunique", "gols": "sum", "gols_contra": "sum"}
    for c in SUM_COLS:
        if c in game_df.columns:
            agg_dict[c] = "sum"
    for c in MEAN_COLS:
        if c in game_df.columns:
            agg_dict[c] = "mean"

    metric_counts = {
        c: game_df.groupby("team")[c].count()
        for c in SUM_COLS
        if c in game_df.columns
    }
    sc = game_df.groupby("team").agg(agg_dict).reset_index()
    sc = sc.rename(columns={"match_id": "jogos"})
    for col, counts in metric_counts.items():
        count_col = f"_{col}_valid_games"
        sc[count_col] = sc["team"].map(counts).fillna(0).astype(int)
        sc.loc[sc[count_col] == 0, col] = np.nan

    # Métricas acumuladas adicionais
    sc["saldo_gols"] = sc["gols"] - sc["gols_contra"]
    sc["aproveitamento"] = _safe_divide(sc["points"], sc["jogos"] * 3)
    sc["precisao_passes"] = _safe_divide(
        sc.get("passes_certos", pd.Series(dtype=float)), sc.get("passes", pd.Series(dtype=float))
    )
    sc["conversao_chutes"] = _safe_divide(
        sc.get("gols", pd.Series(dtype=float)), sc.get("chutes", pd.Series(dtype=float))
    )
    sc["precisao_chutes"] = _safe_divide(
        sc.get("chutes_no_alvo", pd.Series(dtype=float)), sc.get("chutes", pd.Series(dtype=float))
    )
    sc["gols_por_xg"] = _safe_divide(
        sc.get("gols", pd.Series(dtype=float)), sc.get("xg", pd.Series(dtype=float))
    )
    # Razões de eficiência (certo/tentado) — entram na score_eficiencia
    sc["pct_progressoes_certas"] = _safe_divide(
        sc.get("progressoes_bola", pd.Series(dtype=float)),
        sc.get("progressoes_tentadas", pd.Series(dtype=float)),
    ) * 100
    sc["pct_distribuicao_sob_pressao"] = _safe_divide(
        sc.get("distribuicoes_certas_sob_pressao", pd.Series(dtype=float)),
        sc.get("distribuicoes_sob_pressao", pd.Series(dtype=float)),
    ) * 100
    if "distancia_total" in sc.columns:
        sc["distancia_total_km_pj"] = (sc["distancia_total"] / 1000).round(2)

    # Entradas no terço final = soma dos três corredores (penetração total).
    _entr = [c for c in ("entradas_3o_central", "entradas_3o_esq", "entradas_3o_dir") if c in sc.columns]
    if _entr:
        sc["entradas_terco_final"] = sc[_entr].sum(axis=1, min_count=1)

    # Métricas por jogo (_pj)
    PJ_COLS = [
        "gols", "gols_contra", "chutes", "chutes_no_alvo", "chutes_dentro_area",
        "entradas_terco_final", "chutes_sofridos",
        "chutes_sofridos_no_alvo", "xg", "xg_sofrido", "threat",
        "passes", "progressoes_bola", "linebreaks",
        "defesas_goleiro", "turnovers_forcados", "pressoes_defensivas",
        "faltas_cometidas", "amarelos", "vermelhos", "impedimentos",
        "escanteios", "sprints", "corridas_alta_vel", "dribles_certos",
        "trocas_lado_certas",
    ]
    for col in PJ_COLS:
        if col in sc.columns:
            den = sc.get(f"_{col}_valid_games", sc["jogos"])
            sc[f"{col}_pj"] = _safe_divide(sc[col], den)

    # --- Elo ---
    _elo_cols = ["match_id", "team", "date_utc", "gols", "xg", "chutes_no_alvo", "posse"]
    if "threat" in game_df.columns:
        _elo_cols.append("threat")
    elo_input = game_df[_elo_cols].drop_duplicates(subset=["match_id", "team"])
    elo_df = calculate_elo_ratings(elo_input)
    sc = sc.merge(elo_df, on="team", how="left")
    sc["elo_rating"] = sc["elo_rating"].fillna(ELO_INITIAL_RATING)
    # elo_maturity REMOVIDO: os pesos definidos valem integralmente (10% = 10%).
    # Antes ele cortava a Força Relativa a ~24% e inflava o Resultado.
    elo_maturity = pd.Series(1.0, index=sc.index)

    # Aproveitamento ponderado pelo adversário (Elo PRÉ-jogo = estável)
    opp_elo = calculate_pre_match_opponent_elo(elo_input)
    wa = _weighted_aproveitamento(
        game_df[["match_id", "team", "points"]].drop_duplicates(), opp_elo
    )
    sc = sc.merge(wa, on="team", how="left")
    sc["aproveitamento_ponderado"] = sc["aproveitamento_ponderado"].fillna(sc["aproveitamento"])

    # --- Stats por jogo PONDERADAS pelo adversário (alimentam ataque/defesa) ---
    # Mesma lógica do Resultado: criar/conceder contra quem JÁ se provou forte
    # vale mais que contra um fraco. Média ponderada por jogo sum(stat·w)/sum(w),
    # com o peso pré-jogo (estável) /250, clip 0.4-2.2. Só volume ofensivo/
    # defensivo — rates (save%) e métricas já-médias ficam fora.
    _gw = game_df.copy()
    _e3 = [c for c in ("entradas_3o_central", "entradas_3o_esq", "entradas_3o_dir") if c in _gw.columns]
    if _e3:
        _gw["entradas_terco_final"] = _gw[_e3].sum(axis=1, min_count=1)
    _gw = _gw.merge(opp_elo, on=["match_id", "team"], how="left")
    _gw["_w"] = (1.0 + (_gw["opponent_elo"].fillna(ELO_INITIAL_RATING) - ELO_INITIAL_RATING) / 250.0).clip(0.4, 2.2)
    _WPJ_COLS = [
        "xg", "gols", "chutes_dentro_area", "chutes_no_alvo", "threat", "entradas_terco_final",
        "gols_contra", "xg_sofrido", "chutes_sofridos_no_alvo", "turnovers_forcados",
    ]
    for _wc in _WPJ_COLS:
        if _wc not in _gw.columns:
            continue
        _wnum = (_gw[_wc] * _gw["_w"]).groupby(_gw["team"]).sum()
        _wden = (_gw["_w"] * _gw[_wc].notna()).groupby(_gw["team"]).sum()
        sc[f"{_wc}_wpj"] = sc["team"].map(_safe_divide(_wnum, _wden))

    def wpj(stat: str, fallback: pd.Series) -> pd.Series:
        """Coluna por-jogo ponderada pelo adversário, com fallback p/ a simples."""
        return sc[f"{stat}_wpj"] if f"{stat}_wpj" in sc.columns else fallback

    conf = _sample_confidence(sc["jogos"])

    # --- score_resultado ---
    _aprov = zt(sc["aproveitamento_ponderado"], "res_aprov")
    _saldo = zt(sc["saldo_gols"] / sc["jogos"].clip(lower=1), "res_saldo")
    sc["score_resultado"] = (_aprov * 0.70 + _saldo * 0.30).clip(0, 100).round(1)

    # --- score_ataque ---
    # xG (qualidade) e gols (resultado) dominam; chutes dentro da área = volume
    # de chance perigosa; chutes no alvo = finalização; threat = ameaça;
    # entradas no terço final = penetração.
    _at_xg   = zt(wpj("xg", sc.get("xg_pj", _safe_divide(sc["xg"], sc["jogos"]))), "at_xg")
    _at_gols = zt(wpj("gols", sc.get("gols_pj", _safe_divide(sc["gols"], sc["jogos"]))), "at_gols")
    _at_box  = zt(wpj("chutes_dentro_area", sc.get("chutes_dentro_area_pj", pd.Series(0.0, index=sc.index))), "at_box")
    _at_sno  = zt(wpj("chutes_no_alvo", sc.get("chutes_no_alvo_pj", _safe_divide(sc["chutes_no_alvo"], sc["jogos"]))), "at_sno")
    _at_thr  = zt(wpj("threat", sc.get("threat_pj", _safe_divide(
        sc.get("threat", pd.Series(0.0, index=sc.index)), sc["jogos"]
    ))), "at_thr")
    _at_entr = zt(wpj("entradas_terco_final", sc.get("entradas_terco_final_pj", pd.Series(0.0, index=sc.index))), "at_entr")
    _ataque_raw = (_at_xg * 0.30 + _at_gols * 0.30 + _at_box * 0.10
                   + _at_sno * 0.10 + _at_thr * 0.10 + _at_entr * 0.10)
    sc["score_ataque"] = _apply_confidence(_ataque_raw, conf)

    # --- score_defesa (blend: resultado + perigo permitido + qualidade) ---
    # Gols sofridos manda (resultado); xG sofrido = perigo real permitido
    # (espelho do xG no ataque, derivado do adversário); chutes sofridos no alvo
    # = chances no gol cedidas; save%/turnovers forçados = goleiro e recuperação.
    _de_gc   = zt(wpj("gols_contra", sc.get("gols_contra_pj", _safe_divide(sc["gols_contra"], sc["jogos"]))),
                  "de_gc", lower_is_better=True)
    _de_xgs  = zt(wpj("xg_sofrido", sc.get("xg_sofrido_pj", pd.Series(0.0, index=sc.index))),
                  "de_xgs", lower_is_better=True)
    _de_sot  = zt(wpj("chutes_sofridos_no_alvo", sc.get("chutes_sofridos_no_alvo_pj",
                         _safe_divide(sc.get("chutes_sofridos_no_alvo", pd.Series(0.0, index=sc.index)), sc["jogos"]))),
                  "de_sot", lower_is_better=True)
    _de_save = zt(sc.get("save_pct_goleiro", pd.Series(0.5, index=sc.index)).fillna(0.5), "de_save")
    _de_forced = zt(wpj("turnovers_forcados", sc.get("turnovers_forcados_pj",
                           _safe_divide(sc.get("turnovers_forcados", pd.Series(0.0, index=sc.index)), sc["jogos"]))),
                    "de_forced")
    _defesa_raw = (_de_gc * 0.30 + _de_xgs * 0.30 + _de_sot * 0.10
                   + _de_save * 0.15 + _de_forced * 0.15)
    sc["score_defesa"] = _apply_confidence(_defesa_raw, conf)

    # --- score_eficiencia ---
    # Finishing clínico domina (gols/xG + conversão); progressão certa e
    # distribuição sob pressão = uso eficiente da bola (razões, não contagem).
    _ef_gxg  = zt(sc["gols_por_xg"].fillna(1.0), "ef_gxg")
    _ef_conv = zt(sc["conversao_chutes"], "ef_conv")
    _ef_prog = zt(sc.get("pct_progressoes_certas", pd.Series(50.0, index=sc.index)).fillna(50.0), "ef_prog")
    _ef_pres = zt(sc.get("pct_distribuicao_sob_pressao", pd.Series(50.0, index=sc.index)).fillna(50.0), "ef_pres")
    _eficiencia_raw = _ef_gxg * 0.45 + _ef_conv * 0.30 + _ef_prog * 0.10 + _ef_pres * 0.15
    _saldo_jogo = _safe_divide(sc["saldo_gols"], sc["jogos"])
    _damp = (1.0 + _saldo_jogo.clip(upper=0) / 4.0).clip(lower=0.1)
    sc["score_eficiencia"] = _apply_confidence(50.0 + (_eficiencia_raw - 50.0) * _damp, conf)

    # --- score_controle ---
    # Controle no terço final manda (domínio que vira perigo > domínio do próprio
    # campo). Pitch control saiu (redundante, corr 0.94 com posse/terço final).
    # Trocas de lado certas = circulação/espalhar o jogo (eixo menos correlato).
    _ct_f3rd  = zt(sc.get("final_third_control", pd.Series(50.0, index=sc.index)), "ct_f3rd")
    _ct_posse = zt(sc.get("posse", pd.Series(0.5, index=sc.index)) * 100, "ct_posse")
    _ct_prec  = zt(sc["precisao_passes"], "ct_prec")
    _ct_troca = zt(sc.get("trocas_lado_certas_pj", pd.Series(0.0, index=sc.index)), "ct_troca")
    _controle_raw = _ct_f3rd * 0.40 + _ct_posse * 0.20 + _ct_prec * 0.20 + _ct_troca * 0.20
    sc["score_controle"] = _apply_confidence(_controle_raw, conf)

    # --- score_forca_relativa ---
    _elo_dev = _safe_divide(sc["elo_rating"] - ELO_INITIAL_RATING, sc["jogos"])
    sc["score_forca_relativa"] = _apply_confidence(zt(_elo_dev, "fr_elo"), conf).round(1)

    # --- score_disciplina (descritivo, fora do score_geral) ---
    _disc_f = zt(sc.get("faltas_cometidas_pj", pd.Series(0.0, index=sc.index)), "disc_f", lower_is_better=True)
    _disc_a = zt(sc.get("amarelos_pj", pd.Series(0.0, index=sc.index)), "disc_a", lower_is_better=True)
    _disc_v = zt(sc.get("vermelhos_pj", pd.Series(0.0, index=sc.index)), "disc_v", lower_is_better=True)
    # cartões mandam (vermelho dói de verdade); falta tática conta pouco. Soma 1.0.
    sc["score_disciplina"] = (_disc_f * 0.20 + _disc_a * 0.30 + _disc_v * 0.50).clip(0, 100).round(1)

    # --- score_geral ---
    base_fr = w.get("score_forca_relativa", 0.0)
    eff_fr = base_fr * elo_maturity
    eff_res = w.get("score_resultado", 0.0) + (base_fr - eff_fr)

    def _weighted_score(row: pd.Series) -> float:
        total = 0.0
        for key, wt in w.items():
            if key == "score_forca_relativa":
                wt = float(eff_fr.loc[row.name]) if isinstance(eff_fr, pd.Series) else float(eff_fr)
            elif key == "score_resultado":
                wt = float(eff_res.loc[row.name]) if isinstance(eff_res, pd.Series) else float(eff_res)
            total += _num(row.get(key), 50.0) * wt
        return round(total, 1)

    sc["score_geral"] = sc.apply(_weighted_score, axis=1)
    sc["elo_maturity"] = (elo_maturity.round(4) if isinstance(elo_maturity, pd.Series)
                          else round(elo_maturity, 4))
    sc["confianca_amostra"] = conf.round(2)
    sc["nivel_evidencia"] = conf.apply(_evidence_level)

    sc = _add_team_style(sc, game_df, ref_stats)
    sc["team_slug"] = sc["team"].apply(slugify)
    sc = _add_rank(sc, "score_geral", "ranking_score_geral")
    sc = _add_rank(sc, "score_ataque", "ranking_ataque")
    sc = _add_rank(sc, "score_defesa", "ranking_defesa")
    sc = _add_rank(sc, "score_eficiencia", "ranking_eficiencia")
    sc = _add_rank(sc, "score_disciplina", "ranking_disciplina")

    score_cols = [c for c in sc.columns if c.startswith("score_")]
    sc[score_cols] = sc[score_cols].round(1)

    return sc.sort_values(["score_geral", "points", "saldo_gols"], ascending=False).reset_index(drop=True)
