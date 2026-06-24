"""Score próprio de JOGADOR — fonte única FIFA, por posição.

Score analítico construído a partir das métricas brutas que coletamos por jogador
(`fact_player_match_stats` → `player_match_wide`), em paralelo ao Power Ranking
oficial da FIFA (que vira `score_geral` em `player_snapshot._player_scores`). Os
dois convivem: a PR FIFA é a referência externa; este é o nosso, explicável e
decomposto em componentes.

Princípios (espelham `analytics/scores.py` do lado das seleções):
- **z-score DENTRO da posição.** Gol de atacante e defesa de goleiro não são
  comparáveis; cada componente é normalizado no grupo (atacante/meio/defensor/
  goleiro). Por isso o dashboard compara jogadores do mesmo perfil.
- **Pesos fixos por perfil** (`PROFILE_WEIGHTS`) — cada posição valoriza o que
  importa nela.
- **Referência fixa** (`ref_stats`): média/desvio de cada (perfil, métrica)
  calculados UMA vez sobre o estado final e reusados em cada snapshot, para que a
  nota de um jogador só mude quando ELE joga (igual ao lado das seleções).
- **Taxas por 90 minutos** + encolhimento por confiança: poucos minutos puxam a
  nota para a média da posição (50). Defensor e goleiro têm teto de confiança
  menor porque a FIFA não expõe pelo lado do jogador cortes, bloqueios, xGOT,
  xGP nem duelos aéreos — só temos proxies (turnovers, pressões).

Saída: colunas `score_proprio`, `prop_<componente>`, `confianca_score`,
`nivel_confianca` acrescentadas ao DataFrame de entrada.
"""
from __future__ import annotations

import pandas as pd

from fifa_analytics.analytics.scores import _safe_divide, _zscore_to_100

# Perfil → pesos dos componentes no score_proprio (somam 1.0).
PROFILE_WEIGHTS: dict[str, dict[str, float]] = {
    "atacante": {"finalizacao": 0.45, "criacao": 0.25, "eficiencia": 0.15, "progressao": 0.10, "defesa": 0.05},
    "meio":     {"criacao": 0.30, "progressao": 0.25, "defesa": 0.20, "finalizacao": 0.15, "eficiencia": 0.10},
    "defensor": {"defesa": 0.45, "progressao": 0.25, "criacao": 0.15, "finalizacao": 0.10, "eficiencia": 0.05},
    "goleiro":  {"goleiro": 0.80, "progressao": 0.20},
}

# Teto de confiança por perfil: dados mais pobres (só proxies) → nota encolhe mais
# para a média da posição. Atacante/meio têm métricas fartas; defensor/goleiro não.
DATA_RELIABILITY: dict[str, float] = {
    "atacante": 1.0, "meio": 1.0, "defensor": 0.8, "goleiro": 0.75,
}

# Minutos para confiança plena. Saturamos em ~2 jogos completos (180') para que
# diferenças pequenas de minutagem entre quem já jogou bastante NÃO desempatem o
# ranking (ex.: 188' vs 199' não deve decidir um top-2). Acima disso, quem manda
# é o desempenho bruto, não os minutos.
FULL_CONF_MINUTES = 180.0

# Colunas brutas (pt-BR, de player_match_wide) consumidas pelo score. Quem chama
# deve acumular (soma) estas + `minutos`, `jogos`, `perfil` por jogador.
RAW_INPUT_COLS = [
    "minutos", "gols", "xg", "chutes", "chutes_no_alvo", "assistencias",
    "sequencias_com_chute", "dribles_certos", "cruzamentos_certos", "progressoes",
    "passes", "passes_certos", "turnovers_forcados", "pressoes_defensivas",
    "pressoes_diretas", "defesas", "gols_sofridos", "jogos_sem_sofrer",
]

_COMPONENTS = ("finalizacao", "criacao", "eficiencia", "progressao", "defesa", "goleiro")


def _rate90(num: pd.Series, minutos: pd.Series) -> pd.Series:
    """Taxa por 90 minutos. Minutos<=0 → NaN (sem jogo, métrica indefinida)."""
    return num.where(minutos > 0, other=float("nan")) / minutos.where(minutos > 0, other=1) * 90.0


def _z_by_perfil(
    values: pd.Series,
    perfil: pd.Series,
    key: str,
    ref_stats: dict[tuple[str, str], tuple[float, float]] | None,
    lower_is_better: bool = False,
) -> pd.Series:
    """z-score 0-100 calculado SEPARADAMENTE dentro de cada perfil.

    Com `ref_stats`, usa média/desvio fixos por (perfil, key) — calculados e
    memorizados na primeira chamada (estado final), reusados nos snapshots.
    """
    out = pd.Series(50.0, index=values.index)
    for p in perfil.dropna().unique():
        mask = (perfil == p)
        sub = values[mask]
        ref = None
        if ref_stats is not None:
            rk = (p, key)
            if rk not in ref_stats:
                s = pd.to_numeric(sub, errors="coerce")
                ref_stats[rk] = (float(s.mean()), float(s.std(ddof=0)))
            ref = ref_stats[rk]
        out.loc[mask] = _zscore_to_100(sub, lower_is_better=lower_is_better, ref=ref)
    return out


def build_player_scores(
    acc: pd.DataFrame,
    ref_stats: dict[tuple[str, str], tuple[float, float]] | None = None,
) -> pd.DataFrame:
    """Calcula o score_proprio por jogador.

    `acc`: uma linha por jogador com as colunas de `RAW_INPUT_COLS` ACUMULADAS
    (soma até o snapshot) + `perfil` + `jogos`. Devolve `acc` com:
      - `prop_<componente>` (0-100, neutro=50) para cada componente,
      - `score_proprio` (0-100) já encolhido pela confiança,
      - `confianca_score` (0-1) e `nivel_confianca` ("alta"/"media"/"baixa").

    `ref_stats` é preenchido na primeira chamada e deve ser reusado entre
    snapshots para estabilidade (ver módulo).
    """
    df = acc.copy()
    if df.empty:
        for c in _COMPONENTS:
            df[f"prop_{c}"] = pd.Series(dtype=float)
        df["score_proprio"] = pd.Series(dtype=float)
        df["confianca_score"] = pd.Series(dtype=float)
        df["nivel_confianca"] = pd.Series(dtype=object)
        return df

    perfil = df["perfil"].where(df["perfil"].isin(PROFILE_WEIGHTS), other="meio")
    jogos = pd.to_numeric(df.get("jogos", 0), errors="coerce").fillna(0)

    zero = pd.Series(0.0, index=df.index)

    def col(name: str) -> pd.Series:
        if name not in df.columns:
            return zero
        return pd.to_numeric(df[name], errors="coerce").fillna(0)

    minutos = col("minutos")
    # Sem TimePlayed (ou só banco) → aproxima por jogos×90, para o per-90 não zerar.
    eff_min = minutos.where(minutos > 0, other=jogos.clip(lower=0) * 90.0)

    # taxas por 90
    g90 = _rate90(col("gols"), eff_min)
    xg90 = _rate90(col("xg"), eff_min)
    sot90 = _rate90(col("chutes_no_alvo"), eff_min)
    a90 = _rate90(col("assistencias"), eff_min)
    kp90 = _rate90(col("sequencias_com_chute"), eff_min)
    drib90 = _rate90(col("dribles_certos"), eff_min)
    cross90 = _rate90(col("cruzamentos_certos"), eff_min)
    prog90 = _rate90(col("progressoes"), eff_min)
    pc90 = _rate90(col("passes_certos"), eff_min)
    tkl90 = _rate90(col("turnovers_forcados"), eff_min)
    rec90 = _rate90(col("pressoes_defensivas"), eff_min)
    int90 = _rate90(col("pressoes_diretas"), eff_min)
    def90 = _rate90(col("defesas"), eff_min)
    gc90 = _rate90(col("gols_sofridos"), eff_min)

    # razões (não dependem de minutos)
    prec_passes = _safe_divide(col("passes_certos"), col("passes"))
    conversao = _safe_divide(col("gols"), col("chutes"))
    gols_xg = _safe_divide(col("gols"), col("xg"))
    save_pct = _safe_divide(col("defesas"), col("defesas") + col("gols_sofridos"))
    cs_rate = _safe_divide(col("jogos_sem_sofrer"), jogos.clip(lower=1))

    def z(values: pd.Series, key: str, lower: bool = False) -> pd.Series:
        return _z_by_perfil(values, perfil, key, ref_stats, lower)

    comps = {
        "finalizacao": z(g90, "fin_g") * 0.45 + z(xg90, "fin_xg") * 0.35 + z(sot90, "fin_sot") * 0.20,
        "criacao": z(a90, "cri_a") * 0.40 + z(kp90, "cri_kp") * 0.30 + z(drib90, "cri_drib") * 0.15 + z(cross90, "cri_cross") * 0.15,
        "eficiencia": z(gols_xg, "efi_gxg") * 0.55 + z(conversao, "efi_conv") * 0.45,
        "progressao": z(prog90, "pro_prog") * 0.55 + z(prec_passes, "pro_prec") * 0.25 + z(pc90, "pro_pc") * 0.20,
        "defesa": z(tkl90, "def_tkl") * 0.40 + z(rec90, "def_rec") * 0.35 + z(int90, "def_int") * 0.25,
        "goleiro": z(save_pct, "gk_save") * 0.40 + z(def90, "gk_def") * 0.25 + z(gc90, "gk_gc", lower=True) * 0.20 + z(cs_rate, "gk_cs") * 0.15,
    }
    for name, series in comps.items():
        df[f"prop_{name}"] = series.round(1)

    # combina componentes pelo perfil
    raw = pd.Series(50.0, index=df.index)
    for p, weights in PROFILE_WEIGHTS.items():
        mask = (perfil == p)
        if not mask.any():
            continue
        blended = pd.Series(0.0, index=df.index)
        for comp, w in weights.items():
            blended = blended + comps[comp].fillna(50.0) * w
        raw = raw.where(~mask, blended)

    # confiança = minutos jogados × confiabilidade dos dados da posição
    minute_conf = (eff_min / FULL_CONF_MINUTES).clip(0, 1)
    reliability = perfil.map(DATA_RELIABILITY).fillna(0.8)
    conf = (minute_conf * reliability).clip(0, 1)

    df["score_proprio"] = (50.0 * (1 - conf) + raw * conf).round(1)
    df["confianca_score"] = conf.round(2)
    df["nivel_confianca"] = conf.apply(
        lambda c: "alta" if c >= 0.75 else ("media" if c >= 0.5 else "baixa")
    )

    # quem nunca entrou em campo não recebe nota (mantém NaN, não 50).
    sem_jogo = jogos <= 0
    df.loc[sem_jogo, ["score_proprio", "confianca_score"]] = float("nan")
    df.loc[sem_jogo, "nivel_confianca"] = None
    return df
