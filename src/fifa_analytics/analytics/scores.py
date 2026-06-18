from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from fifa_analytics.utils.text import slugify

# ---------------------------------------------------------------------------
# Pesos do score de seleções
# Defesa vale mais que ataque: um gol sofrido é mais difícil de recuperar
# do que um gol marcado. Eficiência mede qualidade do ataque, não volume.
# Controle é estilo de jogo — mantido com peso baixo, não é determinante.
# Força relativa: contextualiza resultado/ataque pela qualidade do adversário
# (vencer a Alemanha valoriza mais que vencer Curaçao) — sem isso, uma goleada
# contra um time fraco e contra um time forte pesam exatamente igual.
# ---------------------------------------------------------------------------
TEAM_SCORE_WEIGHTS = {
    "score_resultado": 0.35,
    "score_ataque": 0.15,
    "score_defesa": 0.20,
    "score_eficiencia": 0.10,
    "score_controle": 0.05,
    "score_forca_relativa": 0.15,
}

# Elo inicial neutro para todas as seleções — não há ranking FIFA oficial
# integrado ainda, então o ponto de partida é igual para todos e a diferenciação
# emerge só dos resultados do próprio torneio.
ELO_INITIAL_RATING = 1500.0
# K-factor base: mais alto que o usado em ligas longas (ex: xadrez usa K~20-32)
# porque o torneio tem só 3-7 jogos por time — cada resultado precisa pesar
# mais para o rating se diferenciar dentro de uma amostra tão pequena.
ELO_K_FACTOR = 40.0
# Teto do multiplicador de margem de gols. ln(perf_diff+1)+1 cresce sem limite
# e chega a ~4x numa goleada com domínio total — o teto evita que bater muito
# num adversário fraco renda Elo desproporcional. 2.5 mantém o realce de
# vitórias dominantes (≈ +150% sobre uma vitória mínima) sem explodir.
ELO_MARGIN_CAP = 2.5

# Maior número médio de jogos por time para o qual vale a pena pré-calcular
# o teto teórico de variância do Elo — a fase de grupos tem 3 jogos por
# time; números maiores (mata-mata) reusam o teto de 3 jogos como aproximação,
# já que o fator de maturidade essencialmente satura bem antes disso.
_ELO_MAX_VARIANCE_MAX_GAMES = 3

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

def build_team_match_features(
    matches: pd.DataFrame,
    team_stats: pd.DataFrame | None = None,
    events: pd.DataFrame | None = None,
    lineups: pd.DataFrame | None = None,
    stats_365: pd.DataFrame | None = None,
) -> pd.DataFrame:
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

    # Campos exclusivos da 365Scores (formação, expected_assists, key_passes etc.)
    # — não duplicam nada da ESPN, apenas enriquecem com métricas que ela não tem.
    # "formation" é tratado separado mais abaixo (fillna sobre o valor da ESPN).
    if stats_365 is not None and not stats_365.empty:
        enrich = stats_365.drop(columns=["opponent"], errors="ignore")
        formation_365 = enrich[["match_id", "team", "formation"]].rename(columns={"formation": "formation_365"})
        enrich = enrich.drop(columns=["formation"])
        features = features.merge(enrich, on=["match_id", "team"], how="left", suffixes=("", "_365"))
        features = features.merge(formation_365, on=["match_id", "team"], how="left")

    # Gols contra SOFRIDOS por time/jogo. No fact_events, o evento gol_contra é
    # atribuído ao time BENEFICIADO; quem sofreu o gol contra é o adversário
    # daquele jogo. Marcamos no time que se desorganizou a ponto de mandar contra
    # o próprio gol — pesa mais na defesa (ver score_defesa).
    features["own_goals_against"] = 0  # gol contra SOFRIDO (a marcação se desorganizou)
    features["own_goals_for"] = 0      # gol contra GANHO (não é mérito ofensivo)
    if events is not None and not events.empty and "event_type" in events.columns:
        og = events[events["event_type"] == "gol_contra"]
        if not og.empty:
            # no fact_events, team = BENEFICIÁRIO; quem sofreu é o adversário do jogo
            benef = og.groupby(["match_id", "team"]).size().rename("n").reset_index()
            opp_map = features[["match_id", "team", "opponent"]]
            benef = benef.merge(opp_map, on=["match_id", "team"], how="left")
            # gol contra a favor (beneficiário)
            afavor = benef.groupby(["match_id", "team"])["n"].sum().rename("_og_for").reset_index()
            features = features.merge(afavor, on=["match_id", "team"], how="left")
            features["own_goals_for"] = features["_og_for"].fillna(0)
            # gol contra sofrido (o adversário do beneficiário)
            sofridos = benef[["match_id", "opponent", "n"]].rename(columns={"opponent": "team"})
            sofridos = sofridos.groupby(["match_id", "team"])["n"].sum().rename("_og_against").reset_index()
            features = features.merge(sofridos, on=["match_id", "team"], how="left")
            features["own_goals_against"] = features["_og_against"].fillna(0)
            features = features.drop(columns=["_og_for", "_og_against"])

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

    # Estatísticas do adversário NESSA MESMA PARTIDA (não o score geral dele,
    # que ainda nem foi calculado e seria circular) — usado para contextualizar
    # ataque/defesa/eficiência/controle pela criação real do rival naquele
    # jogo: segurar 0 gols contra um time que criou muito vale mais do que
    # contra um time que praticamente não chegou ao ataque.
    opponent_stats = features[["match_id", "team", "shots", "shots_on_target", "possession", "passes"]].rename(columns={
        "team": "opponent",
        "shots": "shots_against",
        "shots_on_target": "shots_on_target_against",
        "possession": "possession_against",
        "passes": "passes_against",
    })
    features = features.merge(opponent_stats, on=["match_id", "opponent"], how="left")
    features["opponent_stats_available"] = features[["shots_against", "shots_on_target_against"]].notna().any(axis=1)

    # Fator de inferioridade numérica: quanto do jogo o time jogou com menos
    # jogadores em campo por expulsão. Calculado a partir dos eventos de
    # cartão vermelho com minuto — expulsão aos 49' pesa muito mais do que
    # aos 90+2'. O adversário recebe o fator inverso (jogar contra 9 é vantagem).
    disadvantage = _numerical_disadvantage_factor(events, features["match_id"].unique())
    features = features.merge(disadvantage, on=["match_id", "team"], how="left")
    features["disadvantage_factor"] = features["disadvantage_factor"].fillna(0.0)

    if lineups is not None and not lineups.empty and "formation" in lineups.columns:
        formation_by_match_team = (
            lineups[lineups["formation"].notna()][["match_id", "team", "formation"]]
            .drop_duplicates(["match_id", "team"])
        )
        features = features.merge(formation_by_match_team, on=["match_id", "team"], how="left")

    # A 365Scores cobre formação para jogos onde a ESPN não tem lineup completo.
    if "formation_365" in features.columns:
        if "formation" not in features.columns:
            features["formation"] = pd.NA
        features["formation"] = features["formation"].fillna(features["formation_365"])
        features = features.drop(columns=["formation_365"])

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


def _elo_maturity_factor(elo_rating: pd.Series, jogos: pd.Series) -> pd.Series:
    """Fator 0-1: o quanto o Elo já diferenciou os times na rodada atual.

    Compara a variância real do Elo observado com o teto teórico de
    variância para o número médio de jogos disputados (ver
    _simulate_max_elo_variance) — o teto vem de rodar a MESMA simulação de
    Elo do projeto (_run_elo_simulation, com o margin_multiplier real) sobre
    um cenário sintético de máxima divergência possível (metade do campo
    goleia a outra metade do placar mais largo já observado no torneio, em
    todos os jogos). Variância real próxima de 0 (rodada 1, todos em 1500)
    dá fator próximo de 0; variância se aproximando do teto teórico dá fator
    próximo de 1.
    """
    avg_games = int(round(jogos.mean())) if len(jogos) else 0
    if avg_games <= 0:
        return pd.Series(0.0, index=elo_rating.index)

    max_variance = _simulate_max_elo_variance(min(avg_games, _ELO_MAX_VARIANCE_MAX_GAMES))
    observed_variance = elo_rating.var(ddof=0)
    if pd.isna(observed_variance) or max_variance <= 0:
        return pd.Series(0.0, index=elo_rating.index)

    factor = min(observed_variance / max_variance, 1.0)
    return pd.Series(factor, index=elo_rating.index)


@lru_cache(maxsize=8)
def _simulate_max_elo_variance(n_games_per_team: int, n_teams: int = 32, goal_margin: int = 7) -> float:
    """Roda a simulação real de Elo (_run_elo_simulation) sobre um torneio
    sintético de máxima divergência possível: metade dos times goleia a
    outra metade pelo placar mais largo já visto no torneio (goal_margin a
    1) em todos os jogos, com domínio total de chutes/posse — o cenário que
    maximiza o delta de Elo a cada partida dado o margin_multiplier real.

    Cacheado porque o resultado só depende de N jogos (determinístico) — sem
    isso, recalcularia a mesma simulação a cada chamada de build_team_scores.
    """
    half = n_teams // 2
    rows = []
    match_id = 0
    for _ in range(n_games_per_team):
        for i in range(half):
            match_id += 1
            strong, weak = f"strong_{i}", f"weak_{i}"
            rows.append({
                "match_id": match_id, "date": match_id, "team": strong,
                "goals_for": goal_margin + 1, "shots_on_target": 25, "possession": 65,
            })
            rows.append({
                "match_id": match_id, "date": match_id, "team": weak,
                "goals_for": 1, "shots_on_target": 5, "possession": 35,
            })

    synthetic = pd.DataFrame(rows)
    ratings, _ = _run_elo_simulation(synthetic)
    return float(np.var(list(ratings.values())))


def calculate_elo_ratings(team_match_features: pd.DataFrame) -> pd.DataFrame:
    """Rating Elo por seleção, com multiplicador de margem de gols.

    Cada jogo do torneio é processado em ordem cronológica (cada partida afeta
    os dois times ao mesmo tempo, por isso não dá para calcular por time
    isolado). Vencer um adversário forte vale mais que vencer um fraco —
    o termo `expected` da fórmula reflete a diferença de rating ANTES do jogo,
    então uma goleada contra um time de rating baixo move pouco o rating de
    quem já era favorito, e vencer um favorito move muito o rating do azarão.

    Margem de gols: K efetivo cresce com ln(saldo_gols + 1) — o mesmo
    princípio usado em ratings públicos de futebol (ex: FiveThirtyEight SPI).
    Sem isso, 7x1 e 1x0 contra o mesmo adversário ajustariam o rating igual,
    o que não capturaria "essa goleada justifica-se".

    O resultado real (V/E/D pelo placar) decide qual FAIXA de `score_a` se
    aplica — vitória sempre acima de empate, empate sempre acima de derrota,
    a hierarquia nunca se inverte. Mas dentro de cada faixa, a posição exata
    vem do índice de desempenho (gols + chutes no alvo + posse): uma vitória
    sofrida (ganhou jogando pior que o adversário) fica perto do piso da
    faixa de vitória, uma vitória dominante fica perto do teto — o mesmo
    valendo para empates (dominado vs. equilibrado) e derrotas. Antes, só
    o empate usava o desempenho para definir direção; vitória e derrota só
    usavam `abs(diferença)` como magnitude simétrica, então uma vitória
    sofrida e uma vitória dominante com a mesma margem de gols geravam o
    mesmo ajuste — o que contradizia o princípio de que estatística sempre
    deve contar, não só quando o resultado é ambíguo.

    As três faixas (derrota=[0, 1/3], empate=[1/3, 2/3], vitória=[2/3, 1])
    têm a mesma largura e nunca se tocam, preservando a hierarquia estrita.
    Dentro da faixa, `performance_share_a` (participação de A no desempenho
    total do jogo) interpola a posição exata — não há peso arbitrário
    separando "resultado" de "desempenho": o desempenho nunca decide quem
    ganhou (isso é sempre o placar real), só onde dentro da faixa correta
    o ajuste cai.
    """
    if team_match_features.empty or "match_id" not in team_match_features.columns:
        return pd.DataFrame(columns=["team", "elo_rating"])

    ratings, _ = _run_elo_simulation(team_match_features)
    return pd.DataFrame({"team": list(ratings.keys()), "elo_rating": list(ratings.values())})


def calculate_pre_match_opponent_elo(team_match_features: pd.DataFrame) -> pd.DataFrame:
    """Rating Elo do ADVERSÁRIO no momento de cada jogo (antes do próprio jogo
    rodar) — usado para ponderar o aproveitamento de pontos em `score_resultado`.
    Empatar com um time que já provou ser forte (rating alto na hora do jogo)
    deveria valer mais que empatar com um time fraco; hoje o aproveitamento
    trata os dois empates como idênticos (33.3%), o que gera o "salto
    drástico" entre vitória/empate/derrota que ignora quem era o rival.
    """
    if team_match_features.empty or "match_id" not in team_match_features.columns:
        return pd.DataFrame(columns=["match_id", "team", "opponent_elo_pre_match"])
    _, pre_match_log = _run_elo_simulation(team_match_features)
    return pd.DataFrame(pre_match_log)


def calculate_post_match_opponent_elo(team_match_features: pd.DataFrame) -> pd.DataFrame:
    """Rating Elo FINAL do adversário de cada jogo (após todo o torneio rodado).

    Diferente do pré-jogo: na rodada 1 todos os adversários valiam 1500 (ninguém
    tinha jogado), então o pré-jogo não diferencia "ganhou de quem". O Elo final
    já incorpora o que cada adversário provou ser ao longo do torneio — ganhar de
    um time que se confirmou forte vale mais que ganhar de um que afundou. O
    efeito é pequeno na rodada 1 (os Elos mal se diferenciaram) e cresce conforme
    mais jogos acontecem. Trade-off aceito: usa informação "do futuro" relativo
    ao jogo, mas é o sinal mais justo de força real do adversário disponível.
    """
    if team_match_features.empty or "match_id" not in team_match_features.columns:
        return pd.DataFrame(columns=["match_id", "team", "opponent_elo_pre_match"])

    final_ratings, _ = _run_elo_simulation(team_match_features)
    rows: list[dict[str, Any]] = []
    for match_id, game in team_match_features.groupby("match_id"):
        if len(game) != 2:
            continue
        team_a, team_b = str(game.iloc[0]["team"]), str(game.iloc[1]["team"])
        # opponent_elo_pre_match: mantém o nome da coluna p/ reaproveitar a função
        # de ponderação, mas o valor é o Elo FINAL do adversário.
        rows.append({"match_id": match_id, "team": team_a,
                     "opponent_elo_pre_match": final_ratings.get(team_b, ELO_INITIAL_RATING)})
        rows.append({"match_id": match_id, "team": team_b,
                     "opponent_elo_pre_match": final_ratings.get(team_a, ELO_INITIAL_RATING)})
    return pd.DataFrame(rows)


def _run_elo_simulation(
    team_match_features: pd.DataFrame,
    initial_ratings: dict[str, float] | None = None,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """Roda UMA passada cronológica da simulação de Elo, retornando o rating
    final por time E o log de rating do adversário pré-jogo em cada partida.

    `initial_ratings` semeia o rating inicial de cada time. Na 1ª passada é None
    (todos em ELO_INITIAL_RATING). Nas passadas seguintes (Elo iterativo), recebe
    os ratings finais da passada anterior — assim, ao reprocessar o jogo da
    rodada 1, o adversário já entra com o rating que ele provou ter ao longo do
    torneio, e vencer um fraco deixa de valer Elo cheio (corrige o viés de "na
    rodada 1 todo mundo era 1500")."""
    seed = dict(initial_ratings) if initial_ratings else {}
    ratings: dict[str, float] = {}
    pre_match_log: list[dict[str, Any]] = []
    sort_col = "date" if "date" in team_match_features.columns else "match_id"
    games_by_match = team_match_features.sort_values(sort_col).groupby("match_id", sort=False)

    for match_id, game in games_by_match:
        if len(game) != 2:
            continue
        a, b = game.iloc[0], game.iloc[1]
        team_a, team_b = str(a["team"]), str(b["team"])
        rating_a = ratings.setdefault(team_a, seed.get(team_a, ELO_INITIAL_RATING))
        rating_b = ratings.setdefault(team_b, seed.get(team_b, ELO_INITIAL_RATING))

        pre_match_log.append({"match_id": match_id, "team": team_a, "opponent_elo_pre_match": rating_b})
        pre_match_log.append({"match_id": match_id, "team": team_b, "opponent_elo_pre_match": rating_a})

        goals_a = float(a.get("goals_for", 0) or 0)
        goals_b = float(b.get("goals_for", 0) or 0)
        perf_a, perf_b = _performance_index(a), _performance_index(b)
        # participação de A no desempenho total do jogo — 0.5 quando os dois
        # times tiveram desempenho idêntico, desvia para os lados conforme
        # o domínio real (chutes, posse, gols) de cada um.
        performance_share_a = perf_a / (perf_a + perf_b) if (perf_a + perf_b) > 0 else 0.5

        if goals_a > goals_b:
            band_low, band_high = 2 / 3, 1.0
        elif goals_a < goals_b:
            band_low, band_high = 0.0, 1 / 3
        else:
            band_low, band_high = 1 / 3, 2 / 3
        score_a = band_low + (band_high - band_low) * performance_share_a

        performance_diff = abs(perf_a - perf_b)
        expected_a = 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

        # Multiplicador de margem (goleada conta mais), com TETO. Sem teto,
        # ln(perf_diff+1) chega a ~4x numa goleada com domínio total (ex.:
        # Alemanha 7×1, perf_diff ~24), inflando o Elo de forma desproporcional —
        # bater muito num fraco não deve render quase o quádruplo de uma vitória
        # simples. O teto em ELO_MARGIN_CAP limita esse ganho: a margem ainda
        # importa (vitória dominante > sofrida), mas satura num ponto razoável.
        margin_multiplier = min(np.log(performance_diff + 1) + 1, ELO_MARGIN_CAP)
        delta = ELO_K_FACTOR * margin_multiplier * (score_a - expected_a)

        ratings[team_a] = rating_a + delta
        ratings[team_b] = rating_b - delta

    return ratings, pre_match_log




def _performance_index(game: pd.Series) -> float:
    """Índice de desempenho de um time numa partida — combina gols (peso
    maior, é o que decide o jogo), chutes no alvo (volume de chances criadas)
    e posse (controle de jogo). Usado só para calibrar a MARGEM do ajuste de
    Elo, nunca para decidir quem ganhou — isso é sempre o placar real."""
    goals = float(game.get("goals_for", 0) or 0)
    shots_on_target = float(game.get("shots_on_target", 0) or 0)
    possession = float(game.get("possession", 0) or 0)
    return goals * 3.0 + shots_on_target * 0.5 + possession * 0.05


# ---------------------------------------------------------------------------
# Score de seleções
# ---------------------------------------------------------------------------

def build_team_scores(
    team_match_features: pd.DataFrame,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """``weights`` permite injetar pesos calibrados (ver analytics/calibration.py)
    sem acoplar esta função a leitura de arquivo — por padrão usa
    TEAM_SCORE_WEIGHTS, os pesos de design fixados manualmente."""
    if team_match_features.empty:
        return pd.DataFrame()

    score_weights = weights if weights is not None else TEAM_SCORE_WEIGHTS

    aggregations = {
        "match_id": "nunique",
        "points": "sum",
        "goals_for": "sum",
        "goals_against": "sum",
        "own_goals_against": "sum",
        "own_goals_for": "sum",
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
        "disadvantage_factor": "mean",
        "clean_sheet": "sum",
        "shots_against": "sum",
        "shots_on_target_against": "sum",
        "team_stats_available": "sum",
        "opponent_stats_available": "sum",
        "key_passes": "sum",
        "expected_assists": "sum",
        "dribbles_won": "sum",
        "touches": "sum",
        "possession_lost": "sum",
        # Campos de estilo de jogo (informacional, não entra no score_geral) —
        # caracterizam COMO o time joga, não quão bem. Ver build_team_style.
        "crosses": "sum",
        "accurate_crosses": "sum",
        "passes_into_final_third": "sum",
        "tackles": "sum",
        "interceptions": "sum",
        "clearances": "sum",
        "final_third_possession_won": "sum",
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
        "key_passes": "key_passes",
        "expected_assists": "expected_assists",
        "dribbles_won": "dribbles_won",
        "touches": "touches",
        "possession_lost": "posse_perdida",
    })

    # Métricas por jogo
    scores["saldo_gols"] = scores["gols_pro"] - scores["gols_contra"]
    scores["aproveitamento"] = _safe_divide(scores["points"], scores["jogos"] * 3)
    scores["gols_por_jogo"] = _safe_divide(scores["gols_pro"], scores["jogos"])
    scores["gols_contra_por_jogo"] = _safe_divide(scores["gols_contra"], scores["jogos"])
    scores["chutes_no_alvo_por_jogo"] = _safe_divide(scores["chutes_no_alvo"], scores["jogos"])
    scores["gols_por_chute"] = _safe_divide(scores["gols_pro"], scores["chutes"])
    scores["chutes_no_alvo_por_chute"] = _safe_divide(scores["chutes_no_alvo"], scores["chutes"])
    # conversão da finalização CERTA em gol: dos chutes que acertaram o alvo,
    # quantos viraram gol. Mede eficiência de finalização (não pontaria).
    scores["gols_por_chute_no_alvo"] = _safe_divide(scores["gols_pro"], scores["chutes_no_alvo"])
    scores["passes_por_jogo"] = _safe_divide(scores["passes"], scores["jogos"])
    # Precisão de passes REAL = passes certos / passes totais. O pass_accuracy da
    # ESPN vem arredondado a 1 casa (só 0.6/0.7/0.8/0.9), colapsando times
    # distintos no mesmo valor (México 89.8%, EUA 85.1% e Coreia 86.7% viravam
    # todos "0.9"). Recalcular da razão dos totais recupera a granularidade real.
    # Só sobrescreve quando há passes totais registrados; senão mantém o que veio.
    _prec_real = _safe_divide(scores["passes_certos"], scores["passes"])
    scores["precisao_passes_media"] = _prec_real.where(scores["passes"] > 0,
                                                       scores["precisao_passes_media"])
    scores["faltas_por_jogo"] = _safe_divide(scores["faltas"], scores["jogos"])
    scores["amarelos_por_jogo"] = _safe_divide(scores["amarelos"], scores["jogos"])
    scores["vermelhos_por_jogo"] = _safe_divide(scores["vermelhos"], scores["jogos"])
    scores["clean_sheet_rate"] = _safe_divide(scores["jogos_sem_sofrer_gol"], scores["jogos"])
    scores["chutes_sofridos_por_jogo"] = _safe_divide(scores["chutes_sofridos"], scores["jogos"])
    scores["chutes_no_alvo_sofridos_por_jogo"] = _safe_divide(scores["chutes_no_alvo_sofridos"], scores["jogos"])
    # key_passes/expected_assists/dribbles_won/touches/posse_perdida só
    # existem para jogos com dados da 365Scores (hoje os finalizados); para
    # o resto ficam 0 — não inflar nem penalizar times sem essa fonte ainda,
    # por isso entram em score_eficiencia/score_controle só quando há
    # cobertura real (ver checagem `.gt(0).any()` mais abaixo).
    for _col_365 in ["key_passes", "expected_assists", "dribbles_won", "touches", "posse_perdida"]:
        if _col_365 not in scores.columns:
            scores[_col_365] = 0.0
    scores["key_passes_por_jogo"] = _safe_divide(scores["key_passes"], scores["jogos"])
    scores["expected_assists_por_jogo"] = _safe_divide(scores["expected_assists"], scores["jogos"])
    scores["dribbles_won_por_jogo"] = _safe_divide(scores["dribbles_won"], scores["jogos"])
    # posse_liquida: dribbles ganhos relativos à posse perdida — controle de
    # qualidade não é só ter a bola, é manter o domínio em duelos (driblar
    # com sucesso) sem entregá-la com frequência (possession_lost).
    scores["posse_liquida"] = _safe_divide(scores["dribbles_won"], scores["posse_perdida"].clip(lower=1))

    # --- Contexto do adversário por jogo (sem circularidade) ---
    # Segurar 0 gols contra um time que criou muito (chutes, posse, passes)
    # naquela partida especifica vale mais do que contra um time que quase
    # nao chegou ao ataque — e furar uma defesa que praticamente nao sofreu
    # chutes em nenhum outro jogo (do adversario) vale mais do que furar uma
    # que sofre sempre. Usa as estatisticas REAIS do adversario NESSE jogo
    # (shots_against, possession_against, etc, já calculadas em
    # build_team_match_features), não o score geral dele — isso evitaria a
    # circularidade de precisar do score do adversário antes dele existir.
    context_features = _opponent_context_multiplier(team_match_features)
    scores = scores.merge(context_features, on="team", how="left")
    for col in ["ataque_ctx", "defesa_ctx", "eficiencia_ctx", "controle_ctx"]:
        scores[col] = scores[col].fillna(1.0)

    # --- Estatísticas robustas por jogo (mediana, consistência, tendência) ---
    # Médias/somas acumuladas escondem outliers (uma goleada de 7x1 infla a
    # média de gols tanto quanto 7 jogos de 1x0 cada) e não dizem nada sobre
    # se o desempenho é estável ou alterna entre ótimo e péssimo — daí
    # mediana (robusta a outliers) e consistência (desvio padrão do
    # aproveitamento por jogo) como camada extra de leitura, não substituição.
    per_game_stats = _team_per_game_distribution(team_match_features)
    scores = scores.merge(per_game_stats, on="team", how="left")

    # --- Forca relativa (Elo com margem de gols) ---
    elo_ratings = calculate_elo_ratings(team_match_features)
    scores = scores.merge(elo_ratings, on="team", how="left")
    scores["elo_rating"] = scores["elo_rating"].fillna(ELO_INITIAL_RATING)

    # Maturidade do Elo: na rodada 1, todo mundo começa em 1500 — vencer não
    # significa "ser mais forte", só significa "ganhou esse jogo" (que
    # score_resultado já mede). O Elo só carrega informação de força relativa
    # de fato quando os ratings já se diferenciaram. Esse fator (0 a 1) mede
    # isso e é usado para escalar o peso de score_forca_relativa dinamicamente.
    elo_maturity = _elo_maturity_factor(scores["elo_rating"], scores["jogos"])

    # --- Aproveitamento ponderado pela força do adversário no momento do jogo ---
    # Sem isso, empatar com a Alemanha e empatar com Curaçao valem exatamente
    # os mesmos 33,3% de aproveitamento — o "salto drástico" entre vitória/
    # empate/derrota ignora completamente quem era o rival. Usa o Elo FINAL do
    # adversário (não o pré-jogo): na rodada 1 todos valiam 1500, então o
    # pré-jogo não diferencia "ganhou de quem"; o Elo final já reflete o que cada
    # adversário provou ser ao longo do torneio. Efeito pequeno agora, cresce com
    # mais rodadas.
    opponent_elo = calculate_post_match_opponent_elo(team_match_features)
    weighted_aproveitamento = _weighted_aproveitamento_by_opponent(team_match_features, opponent_elo)
    scores = scores.merge(weighted_aproveitamento, on="team", how="left")
    scores["aproveitamento_ponderado"] = scores["aproveitamento_ponderado"].fillna(scores["aproveitamento"])

    # --- Componentes via z-score (preserva distância absoluta entre times) ---
    # score_resultado: aproveitamento PONDERADO pelo adversário domina; saldo
    # de gols por jogo quebra empates dentro da mesma faixa sem inverter a
    # hierarquia vitória > empate > derrota (o ajuste de adversário também
    # nunca inverte essa hierarquia — só reposiciona dentro do que o placar
    # real já estabeleceu, mesmo princípio do Elo com faixas).
    _aprov_norm = _zscore_to_100(scores["aproveitamento_ponderado"])
    _saldo_norm = _zscore_to_100(scores["saldo_gols"] / scores["jogos"].clip(lower=1))
    scores["score_resultado"] = (_aprov_norm * 0.85 + _saldo_norm * 0.15).clip(0, 100).round(1)

    # Confiança da amostra (cresce de 0 a 1 com mais jogos; 3 = fase de grupos
    # completa). Aplicada a TODOS os componentes de processo — não só à defesa —
    # para que um único jogo excepcional (ex.: Alemanha 7×1 num jogo) não produza
    # um score de quase-100 com falsa precisão: o score é puxado para o neutro
    # proporcionalmente à pouca evidência, e converge para o valor cheio conforme
    # os jogos acumulam, se o desempenho se sustentar.
    _amostra_conf = _sample_confidence(scores["jogos"])

    # score_ataque: poder ofensivo. GOL domina (70%) — é o produto final do
    # ataque; o VOLUME de chutes no alvo (30%) ainda conta como criação de
    # chances, mas não infla quem chuta muito e não converte (ex.: Uruguai 1 gol
    # em 10 chutes no alvo não deve ter ataque ~ EUA que fez 4 gols). A conversão
    # em si é avaliada à parte em score_eficiencia. Multiplicado pelo contexto do
    # adversário ANTES do z-score: marcar contra quem criou muito volume de jogo
    # conta mais do que contra quem praticamente não jogou.
    # gol contra GANHO não é mérito do ataque — desconta do gols/jogo só p/ o
    # score_ataque (o placar/resultado segue contando o gol normalmente).
    _og_for = scores.get("own_goals_for", pd.Series(0, index=scores.index)).fillna(0)
    _gols_ataque_por_jogo = _safe_divide((scores["gols_pro"] - _og_for).clip(lower=0), scores["jogos"])
    _ataque_gol = _zscore_to_100(_gols_ataque_por_jogo * scores["ataque_ctx"])
    _ataque_vol = _zscore_to_100(scores["chutes_no_alvo_por_jogo"] * scores["ataque_ctx"])
    _ataque_raw = _ataque_gol * 0.70 + _ataque_vol * 0.30
    scores["score_ataque"] = _apply_confidence(_ataque_raw, _amostra_conf)

    # score_defesa: o GOLS SOFRIDOS/jogo é o eixo dominante e MONOTÔNICO — um time
    # que sofreu mais gols nunca pode ter defesa melhor que um que sofreu menos
    # (era o bug: Argélia 3 gols > EUA 1 gol porque os termos de "mérito sob
    # pressão" invertiam o placar). O contexto (volume segurado + força do
    # adversário) só AJUSTA dentro da faixa de cada nível de gols, sem cruzá-la.
    #
    # Estrutura em bandas: gols sofridos define a banda-base (0 gol = banda alta,
    # 1 gol = média, etc.); dentro da banda, um ajuste contextual de ±meia-banda
    # premia quem segurou mais volume contra adversário mais forte. Como o ajuste
    # é menor que o espaçamento entre bandas, a ordem por gols é preservada.

    # força do adversário (Elo médio dos rivais, não-circular) — segurar pressão
    # de um time forte vale mais que de um fraco (Cabo Verde/Espanha vs Austrália/Turquia)
    _opp_elo_avg = (
        opponent_elo.groupby("team")["opponent_elo_pre_match"].mean()
        if not opponent_elo.empty else pd.Series(dtype=float)
    )
    _elo_strength = scores["team"].map(_opp_elo_avg).fillna(ELO_INITIAL_RATING)
    _elo_mean = _elo_strength.mean() or ELO_INITIAL_RATING
    _opp_strength_mult = (1.0 + (_elo_strength - _elo_mean) / 200.0).clip(0.7, 1.3)
    _defesa_ctx_q = (scores["defesa_ctx"] * _opp_strength_mult).clip(0.5, 1.6)

    _alvo_sofridos = scores["chutes_no_alvo_sofridos_por_jogo"].clip(lower=0)
    _neutralizados = (_alvo_sofridos - scores["gols_contra_por_jogo"]).clip(lower=0)

    # banda-base por gols sofridos/jogo: decai com cada gol (assintótico).
    # 0 gol→85, 1→54.8, 2→40.5, 3→32.1, ... — os gaps encolhem conforme sobe o nº
    # de gols, então o ajuste contextual precisa ser proporcional ao gap LOCAL.
    def _band(gc):
        return 85.0 / (1.0 + gc * 0.55)
    # gol contra pesa MAIS na defesa: a marcação se desorganizou a ponto do próprio
    # jogador mandar contra. Cada gol contra conta como 1.5 gol sofrido (penalidade
    # de +0.5) no eixo da banda — empurra o time pra uma banda defensiva pior.
    _og_against = scores.get("own_goals_against", pd.Series(0, index=scores.index)).fillna(0)
    _gc_efetivo = scores["gols_contra"] + _og_against * 0.5
    _gc = _safe_divide(_gc_efetivo, scores["jogos"]).clip(lower=0)
    _banda_base = _band(_gc)

    # gap adjacente à banda do time — limita o ajuste pra NUNCA cruzar de banda
    # (garante monotonicidade: + gols ⇒ nunca + defesa). No nível 0 não há banda
    # "acima", então usa só o gap abaixo (não o min, que seria 0 e zeraria o
    # ajuste, reamontoando os clean sheets).
    _gap_abaixo = (_banda_base - _band(_gc + 1.0)).clip(lower=0)
    _gap_acima = (_band((_gc - 1.0).clip(lower=0)) - _banda_base)
    # onde há banda acima (gc>=1), usa o menor dos dois; senão só o de baixo.
    _gap_local = pd.concat([_gap_abaixo, _gap_acima.where(_gc >= 1.0, _gap_abaixo)], axis=1).min(axis=1)

    # mérito contextual ∈ [-1,+1]: segurar volume sob pressão de adversário forte.
    # Escalado a ±40% do gap local — o ajuste fica sempre menor que meia-banda.
    _merito = _zscore_to_100(_neutralizados * _defesa_ctx_q)  # 0..100, média ~50
    _ajuste = ((_merito - 50.0) / 50.0).clip(-1, 1) * _gap_local * 0.40

    _defesa_raw = (_banda_base + _ajuste).clip(0, 100)
    # Defesa pouco testada (adversário criou pouco volume — defesa_ctx baixo)
    # não é o mesmo que defesa sólida sob pressão: sem ser testada, não há
    # evidência suficiente do mérito defensivo, então o score é atraído para
    # o neutro (50) proporcionalmente a quão pouco foi testada — mesmo
    # princípio do _apply_confidence já usado para jogadores com poucos jogos,
    # aqui aplicado a "poucos chutes sofridos por dominar o jogo", não a
    # poucos jogos disputados.
    # Dois amortecimentos: (1) quão testada foi a defesa (defesa_ctx) e (2) a
    # confiança da amostra (poucos jogos). O menor dos dois governa — sem
    # evidência (poucos jogos OU defesa pouco testada) o score fica perto do neutro.
    _defesa_conf = pd.concat([scores["defesa_ctx"].clip(upper=1.0), _amostra_conf], axis=1).min(axis=1)
    scores["score_defesa"] = _apply_confidence(_defesa_raw, _defesa_conf)

    # score_eficiencia: CONVERSÃO de chances em gol, não pontaria nem volume.
    # eficiencia_resultado: gols/chute ponderado pelo aproveitamento — converter
    # bem e perder não é eficiência real; o resultado contextualiza se a
    # conversão técnica se traduziu em vantagem concreta.
    # Antes havia um componente de "acertar o alvo" (chutes_no_alvo/chutes), que é
    # PONTARIA, não eficiência: inflava quem chutava no gol sem marcar (ex.:
    # Uruguai 10 no alvo, 1 gol = 10% de conversão, mas eficiência ~ Japão com
    # 67%). Trocado por gols/chute_no_alvo: dos chutes certos, quantos viraram
    # gol — eficiência de finalização de verdade.
    scores["eficiencia_resultado"] = scores["gols_por_chute"] * scores["aproveitamento"].clip(lower=0.1)
    _eficiencia_components = [
        _zscore_to_100(scores["gols_por_chute"] * scores["eficiencia_ctx"]),
        _zscore_to_100(scores["gols_por_chute_no_alvo"] * scores["eficiencia_ctx"]),
        _zscore_to_100(scores["eficiencia_resultado"]),
    ]
    # key_passes_por_jogo: criação de chances que não resultou em gol também é
    # eficiência ofensiva — um time pode estar errando finalizações mas
    # achando os espaços certos. Só entra quando há cobertura da 365Scores
    # (fonte ainda não tem todos os jogos); senão o z-score ficaria comparando
    # times com dado real contra times com 0 artificial.
    if scores["key_passes_por_jogo"].gt(0).any():
        _eficiencia_components.append(_zscore_to_100(scores["key_passes_por_jogo"] * scores["eficiencia_ctx"]))
    scores["score_eficiencia"] = _apply_confidence(_mean_score(_eficiencia_components), _amostra_conf)

    # score_controle: domínio de bola/jogo — peso baixo, não determina qualidade.
    # Dois grupos com pesos diferentes (CORE 70% / COMPLEMENTOS 30%):
    #  • CORE = controle de bola no sentido clássico: posse, volume de passes e
    #    precisão. É o que define "ter o jogo nos pés" (ex.: a Espanha com 74%
    #    posse e 90% precisão deve liderar o controle).
    #  • COMPLEMENTOS = nuances que refinam, mas não definem o controle:
    #    posse_produtiva (a posse virou finalização? penaliza posse estéril) e
    #    posse_liquida (domínio nos duelos via dribles). Antes os 5 pesavam
    #    igual (1/5), e um pico num complemento (ex.: EUA com 22 dribles)
    #    superava a posse dominante da Espanha — invertendo o que "controle"
    #    deveria capturar.
    scores["posse_produtiva"] = _safe_divide(scores["chutes_no_alvo_por_jogo"], scores["posse_media"])
    _controle_core = _mean_score([
        _zscore_to_100(scores["posse_media"] * scores["controle_ctx"]),
        _zscore_to_100(scores["passes_por_jogo"] * scores["controle_ctx"]),
        _zscore_to_100(scores["precisao_passes_media"] * scores["controle_ctx"]),
    ])
    _controle_complementos = [_zscore_to_100(scores["posse_produtiva"])]
    # posse_liquida (dribbles ganhos / posse perdida): controle em duelos
    # individuais. Só entra quando há cobertura da 365Scores (mesma lógica de
    # key_passes em eficiência).
    if scores["dribbles_won_por_jogo"].gt(0).any():
        _controle_complementos.append(_zscore_to_100(scores["posse_liquida"] * scores["controle_ctx"]))
    _controle_raw = _controle_core * 0.70 + _mean_score(_controle_complementos) * 0.30
    scores["score_controle"] = _apply_confidence(_controle_raw, _amostra_conf)

    # score_forca_relativa: contextualiza o resultado pela qualidade do
    # adversário enfrentado — vencer a Alemanha vale mais que vencer Curaçao.
    # Único componente que não é "por jogo" isolado: o Elo acumula o efeito
    # de toda a sequência de jogos do time (quem jogou, em que ordem, com
    # que margem), por isso o z-score aqui mede força relativa acumulada,
    # não uma média simples como os outros componentes.
    scores["score_forca_relativa"] = _zscore_to_100(scores["elo_rating"]).round(1)

    # score_disciplina: índice de violência — faltas e cartões por jogo.
    # Nota alta = time disciplinado. Vermelho vale mais que amarelo (impacto
    # imediato e irreversível no jogo). Não entra no score_geral — é informativo,
    # não determinante de qualidade de jogo.
    scores["vermelhos_por_jogo"] = _safe_divide(scores["vermelhos"], scores["jogos"])
    _disc_faltas = _zscore_to_100(scores["faltas_por_jogo"], lower_is_better=True)
    _disc_amarelos = _zscore_to_100(scores["amarelos_por_jogo"], lower_is_better=True)
    _disc_vermelhos = _zscore_to_100(scores["vermelhos_por_jogo"], lower_is_better=True)
    scores["score_disciplina"] = _mean_score([
        _disc_faltas * 0.3,
        _disc_amarelos * 0.3,
        _disc_vermelhos * 0.4,
    ]) / 0.3  # reescala para manter 0-100 após ponderação

    # Estilo de jogo: métrica DESCRITIVA (não avaliativa) — caracteriza COMO o
    # time joga em 4 eixos e deriva um rótulo legível. Não entra no score_geral:
    # estilo não é melhor/pior, é uma assinatura. Ver build_team_style.
    scores = _add_team_style(scores)

    # score_geral composto. O peso de score_forca_relativa é escalado pela
    # maturidade do Elo (elo_maturity, 0-1): na rodada 1, todos os times têm
    # Elo igual (1500) e "vencer" não mede força relativa de fato, é o mesmo
    # sinal que score_resultado já captura — então a fração de peso "não
    # ganha" pela força relativa imatura é transferida para score_resultado,
    # que é o componente que sabidamente mede o que aconteceu naquele jogo
    # com informação real (saldo de gols, aproveitamento) desde o primeiro
    # jogo, sem depender de histórico acumulado.
    base_forca_relativa = score_weights.get("score_forca_relativa", 0.0)
    effective_forca_relativa = base_forca_relativa * elo_maturity
    forca_relativa_gap = base_forca_relativa - effective_forca_relativa
    effective_resultado = score_weights.get("score_resultado", 0.0) + forca_relativa_gap

    scores["score_geral"] = _weighted_score_per_row(
        scores,
        score_weights,
        overrides={
            "score_forca_relativa": effective_forca_relativa,
            "score_resultado": effective_resultado,
        },
    )
    # Pesos efetivos expostos para que relatórios mostrem o peso REAL usado
    # naquele cálculo, não o peso de design — útil porque score_forca_relativa
    # varia conforme a maturidade do Elo (ver _elo_maturity_factor).
    scores["peso_efetivo_forca_relativa"] = effective_forca_relativa.round(4) if isinstance(effective_forca_relativa, pd.Series) else round(effective_forca_relativa, 4)
    scores["peso_efetivo_resultado"] = effective_resultado.round(4) if isinstance(effective_resultado, pd.Series) else round(effective_resultado, 4)
    scores["elo_maturity"] = elo_maturity.round(4) if isinstance(elo_maturity, pd.Series) else round(elo_maturity, 4)

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
    scores = _add_rank(scores, "score_disciplina", "ranking_disciplina")

    score_cols = [c for c in scores.columns if c.startswith("score_")]
    scores[score_cols] = scores[score_cols].round(1)
    scores["confianca_amostra"] = scores["confianca_amostra"].round(2)
    scores["confianca_dados"] = scores["confianca_dados"].round(2)

    return scores.sort_values(["score_geral", "points", "saldo_gols"], ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Features por partida — jogadores
# ---------------------------------------------------------------------------

def _player_name_key(value: Any) -> str:
    text = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()
    if text.lower().endswith(" null"):
        text = text[:-5].strip()
    return slugify(text)


def build_player_match_features(
    player_stats: pd.DataFrame, lineups: pd.DataFrame | None = None, rosters: pd.DataFrame | None = None
) -> pd.DataFrame:
    if player_stats.empty and (rosters is None or rosters.empty):
        return pd.DataFrame()

    metric_columns = [
        "appearances", "goals", "assists", "shots", "shots_on_target",
        "shots_off_target", "shots_blocked_att", "shots_woodwork",
        "saves", "goals_conceded", "shots_faced",
        "yellow_cards", "red_cards", "fouls_committed", "fouls_drawn",
        "offsides_player", "own_goals_player", "corners_won",
    ]
    features = player_stats.copy() if not player_stats.empty else pd.DataFrame(columns=["match_id", "team", "player_name", "position", *metric_columns])
    # appearances ausente: deriva de minutes_played (jogou = 1, não entrou = 0).
    # Sem minutes nem appearances, assume 1 (linha de stats = participou).
    if "appearances" not in features.columns and not features.empty:
        if "minutes_played" in features.columns:
            mins = pd.to_numeric(features["minutes_played"], errors="coerce").fillna(0)
            features["appearances"] = (mins > 0).astype(int)
        else:
            features["appearances"] = 1
    for column in metric_columns:
        if column not in features.columns:
            features[column] = 0
        features[column] = pd.to_numeric(features[column], errors="coerce").fillna(0)

    if lineups is not None and not lineups.empty and {"match_id", "team", "player_name"}.issubset(lineups.columns):
        lineup_cols = [c for c in ["match_id", "team", "player_name", "position", "is_starter", "formation"] if c in lineups.columns]
        lineup_info = lineups[lineup_cols].drop_duplicates(["match_id", "team", "player_name"])
        features = features.merge(lineup_info, on=["match_id", "team", "player_name"], how="left")

    # "position" (do lineup) é a posição TÁTICA daquele jogo especifico — varia
    # jogo a jogo (ex: Vinícius Júnior às vezes joga aberto como "AM-L") e fica
    # como está para exibir a escalação real da partida. Para classificar o
    # PERFIL do jogador (usado em scores e agrupamento de relatórios), usa-se
    # "roster_position" — a função de elenco/convocação da ESPN, estável e
    # correta independente de onde o jogador atuou num jogo específico.
    if "position" not in features.columns:
        features["position"] = pd.NA
    features["roster_position"] = features.get("position")
    if rosters is not None and not rosters.empty:
        roster_position = rosters[["team", "player_name", "squad_position"]].dropna(subset=["team", "player_name"]).copy()
        roster_position["_player_key"] = roster_position["player_name"].map(_player_name_key)
        roster_position = roster_position.drop_duplicates(["team", "_player_key"])
        features["_player_key"] = features["player_name"].map(_player_name_key)
        features = features.merge(
            roster_position[["team", "_player_key", "squad_position"]],
            on=["team", "_player_key"],
            how="left",
        )
        has_roster = features["squad_position"].notna()
        features.loc[has_roster, "roster_position"] = features.loc[has_roster, "squad_position"]
        features = features.drop(columns=["squad_position"])

        existing = set(zip(features["team"], features["_player_key"]))
        missing_roster = roster_position[
            ~roster_position.apply(lambda row: (row["team"], row["_player_key"]) in existing, axis=1)
        ]
        if not missing_roster.empty:
            roster_only = missing_roster[["team", "player_name", "squad_position", "_player_key"]].rename(
                columns={"squad_position": "roster_position"}
            )
            roster_only["position"] = pd.NA
            roster_only["match_id"] = pd.NA
            for column in metric_columns:
                roster_only[column] = 0
            features = pd.concat([features, roster_only], ignore_index=True, sort=False)
        features = features.drop(columns=["_player_key"], errors="ignore")

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
        "appearances": "sum",  # jogos REALMENTE disputados (0 p/ reserva que não entrou)
        "goals": "sum",
        "assists": "sum",
        "shots": "sum",
        "shots_on_target": "sum",
        "shots_off_target": "sum",
        "shots_blocked_att": "sum",
        "shots_woodwork": "sum",
        "saves": "sum",
        "goals_conceded": "sum",
        "fouls_committed": "sum",
        "fouls_drawn": "sum",
        "corners_won": "sum",
        "yellow_cards": "sum",
        "red_cards": "sum",
        "participacoes_gol": "sum",
        "perfil": _mode_or_first,
    }
    available = {c: agg for c, agg in aggregations.items() if c in player_match_features.columns}
    scores = player_match_features.groupby(group_columns, dropna=False).agg(available).reset_index()
    # jogos = partidas REALMENTE disputadas (soma de appearances). Cair pro nº de
    # partidas listadas só se appearances não existir/for tudo nulo — senão reserva
    # que nunca entrou contaria como 1 jogo (e recebia score sem ter jogado).
    _match_count = pd.to_numeric(scores["match_id"], errors="coerce").fillna(0)
    if "appearances" in scores.columns and pd.to_numeric(scores["appearances"], errors="coerce").notna().any():
        _apps = pd.to_numeric(scores["appearances"], errors="coerce")
        # se appearances for nulo numa linha, usa o nº de partidas como fallback
        scores["jogos"] = _apps.fillna(_match_count).fillna(0).round().astype(int)
        scores = scores.drop(columns=["match_id"])
    else:
        scores["jogos"] = _match_count.round().astype(int)
        scores = scores.drop(columns=["match_id"])

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
    # quem não disputou nenhum jogo não recebe score (não faz sentido pontuar
    # reserva que não entrou) — fica sem nota e some do filtro "só com jogos".
    scores.loc[scores["jogos"] <= 0, "score_geral"] = pd.NA

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


def _team_per_game_distribution(team_match_features: pd.DataFrame) -> pd.DataFrame:
    """Mediana, consistência e tendência por time, calculadas jogo a jogo
    (não a partir dos agregados já somados — precisa da distribuição real).

    - mediana_gols_pro / mediana_chutes_no_alvo: robustas a goleadas/outliers,
      ao contrário da média que uma goleada isolada distorce.
    - consistencia_resultado: desvio padrão do aproveitamento por jogo
      (pontos/3 em cada jogo individual). 0 = sempre o mesmo resultado tipo
      (ex: 3 vitórias), valores altos = alterna entre extremos. Vira rótulo
      qualitativo na exibição porque o número bruto não é interpretável
      sozinho com 3-7 jogos de amostra.
    - tendencia_resultado: compara o aproveitamento da segunda metade dos
      jogos com a primeira. Precisa de pelo menos 2 jogos; com 1 jogo não há
      tendência a calcular.
    """
    if team_match_features.empty:
        return pd.DataFrame(columns=["team", "mediana_gols_pro", "mediana_chutes_no_alvo", "consistencia_resultado", "tendencia_resultado"])

    rows = []
    for team, group in team_match_features.groupby("team", dropna=False):
        ordered = group.sort_values("date") if "date" in group.columns else group
        game_points = ordered["points"] if "points" in ordered.columns else pd.Series(dtype=float)
        per_game_aproveitamento = (game_points / 3).reset_index(drop=True)

        tendencia = None
        if len(per_game_aproveitamento) >= 2:
            mid = len(per_game_aproveitamento) // 2
            first_half = per_game_aproveitamento.iloc[:mid] if mid > 0 else per_game_aproveitamento.iloc[:1]
            second_half = per_game_aproveitamento.iloc[mid:] if mid > 0 else per_game_aproveitamento.iloc[1:]
            tendencia = float(second_half.mean() - first_half.mean())

        rows.append({
            "team": team,
            "mediana_gols_pro": float(ordered["goals_for"].median()) if "goals_for" in ordered.columns else None,
            "mediana_chutes_no_alvo": float(ordered["shots_on_target"].median()) if "shots_on_target" in ordered.columns else None,
            "consistencia_resultado": float(per_game_aproveitamento.std(ddof=0)) if len(per_game_aproveitamento) >= 2 else None,
            "tendencia_resultado": tendencia,
        })
    return pd.DataFrame(rows)


def _weighted_aproveitamento_by_opponent(team_match_features: pd.DataFrame, pre_match_elo: pd.DataFrame) -> pd.DataFrame:
    """Aproveitamento de pontos por jogo, ponderado pelo rating Elo do
    adversário NO MOMENTO daquele jogo (antes do resultado dele mesmo
    influenciar o rating). Pontos contra adversário acima da média do
    rating valem mais que pontos contra adversário abaixo da média —
    empatar com a Alemanha não fica mais idêntico a empatar com Curaçao.

    O ajuste só reposiciona o valor DENTRO do que o resultado real (V/E/D)
    já decidiu, nunca inverte a hierarquia entre jogos com placares
    diferentes — mesmo princípio do Elo com faixas: o placar decide o que
    aconteceu, o contexto só pesa o quanto isso vale.
    """
    if team_match_features.empty or pre_match_elo.empty:
        return pd.DataFrame(columns=["team", "aproveitamento_ponderado"])

    games = team_match_features.merge(pre_match_elo, on=["match_id", "team"], how="left")
    games["opponent_elo_pre_match"] = games["opponent_elo_pre_match"].fillna(ELO_INITIAL_RATING)
    games["points"] = pd.to_numeric(games.get("points", 0), errors="coerce").fillna(0)

    league_avg_elo = games["opponent_elo_pre_match"].mean() or ELO_INITIAL_RATING
    # peso relativo do adversário: >1 se mais forte que a média do torneio
    # na hora do jogo, <1 se mais fraco. Clip evita que um Elo muito
    # destoante (extremos do torneio) gere peso desproporcional.
    games["_opponent_weight"] = (games["opponent_elo_pre_match"] / league_avg_elo).clip(0.7, 1.3)
    games["_weighted_points"] = (games["points"] / 3.0) * games["_opponent_weight"]

    by_team = games.groupby("team", dropna=False)["_weighted_points"].mean().reset_index()
    return by_team.rename(columns={"_weighted_points": "aproveitamento_ponderado"})


def _opponent_context_multiplier(team_match_features: pd.DataFrame) -> pd.DataFrame:
    """Multiplicador de contexto por time (média entre os jogos disputados),
    baseado em estatísticas REAIS do adversário em cada partida — não o
    score geral dele, que seria circular (precisaria do score do adversário
    antes de existir o do time, e vice-versa).

    Dois multiplicadores distintos, não um único reaproveitado:

    - `defesa_ctx`: volume ofensivo que o adversário teve NESSE jogo (chutes,
      posse). Segurar um adversário que pressionou muito vale mais do que
      segurar quem quase não chegou ao ataque — não depende de o adversário
      ter convertido ou não, só de ter criado volume.

    - `ataque_ctx` (e eficiência/controle): quão bem o adversário defendeu
      EM MÉDIA NOS OUTROS JOGOS DELE (gols/chutes no alvo sofridos por jogo,
      olhando só partidas anteriores à atual). Marcar contra um adversário
      historicamente sólido vale mais do que contra um que sofre sempre.
      Por isso fica neutro (1.0) no 1º jogo de cada adversário — ainda não
      há "outros jogos dele" para medir solidez defensiva real, e usar
      volume bruto dele nesse mesmo jogo seria o erro identificado: um
      adversário que domina posse mas não converte (ex: Turquia 71% posse,
      perdeu 0x2) não torna o ATAQUE do rival mais impressionante, só
      mostra que a DEFESA do rival aguentou pressão.
    """
    empty_cols = ["team", "ataque_ctx", "defesa_ctx", "eficiencia_ctx", "controle_ctx"]
    if team_match_features.empty:
        return pd.DataFrame(columns=empty_cols)

    games = team_match_features.copy()
    for col in ["shots_against", "shots_on_target_against", "possession_against", "goals_against", "shots_on_target"]:
        if col not in games.columns:
            games[col] = 0
        games[col] = pd.to_numeric(games[col], errors="coerce").fillna(0)

    # --- defesa_ctx: volume ofensivo do adversário NESSE jogo (sem olhar histórico) ---
    games["_opponent_volume"] = games["shots_on_target_against"] * 0.5 + games["possession_against"] * 0.05 + games["shots_against"] * 0.1
    volume_mean = games["_opponent_volume"].mean()
    if not volume_mean or pd.isna(volume_mean):
        games["defesa_ctx"] = 1.0
    else:
        games["defesa_ctx"] = (games["_opponent_volume"] / volume_mean).clip(0.5, 1.5)

    # --- ataque_ctx: solidez defensiva HISTÓRICA do adversário (jogos
    # anteriores dele, não esse jogo) — evita confundir "dominou sem
    # converter" com "defesa fraca que torna o gol mais fácil". Processa por
    # PARTIDA (não por linha) para nunca deixar o gol sofrido de um time
    # nessa mesma partida contaminar o histórico consultado pelo adversário
    # dentro do próprio jogo — mesma armadilha que o Elo evita processando
    # match_id por vez antes de atualizar os ratings dos dois lados.
    sort_col = "date" if "date" in games.columns else "match_id"
    league_avg_conceded = pd.to_numeric(games["goals_against"], errors="coerce").fillna(0).mean() or 1.0
    defensive_history: dict[str, list[float]] = {}
    attack_ctx_by_index: dict[int, float] = {}
    games_by_match = games.sort_values(sort_col).groupby("match_id", sort=False)
    for _, match_rows in games_by_match:
        for idx, row in match_rows.iterrows():
            opponent = str(row.get("opponent"))
            history = defensive_history.get(opponent, [])
            if history:
                opponent_avg_conceded = sum(history) / len(history)
                attack_ctx_by_index[idx] = float((league_avg_conceded / opponent_avg_conceded) if opponent_avg_conceded > 0 else 1.5)
            else:
                attack_ctx_by_index[idx] = 1.0  # sem histórico do adversário ainda — neutro
        # só depois de calcular o contexto dos DOIS lados dessa partida,
        # atualiza o histórico defensivo de cada time com o que sofreu aqui.
        for _, row in match_rows.iterrows():
            team = str(row.get("team"))
            team_history = defensive_history.setdefault(team, [])
            team_history.append(float(row.get("goals_against", 0) or 0))
    games["ataque_ctx"] = pd.Series(attack_ctx_by_index).reindex(games.index).clip(0.5, 1.5)
    games["eficiencia_ctx"] = games["ataque_ctx"]
    games["controle_ctx"] = games["ataque_ctx"]

    # Ajuste de inferioridade/superioridade numérica — condicional ao resultado:
    # - perdeu em inferioridade (ex: África do Sul 0x2 com 9) → reduz peso
    #   (resultado esperado, pouca evidência sobre a qualidade real do time)
    # - ganhou em inferioridade (ex: 10 contra 11 e venceu) → aumenta peso
    #   (resultado improvável, forte evidência de qualidade tática)
    # - ganhou em superioridade (ex: México 2x0 contra 9) → reduz peso
    #   (resultado esperado, pouca evidência — vencer com 11 contra 9 é o mínimo)
    # - perdeu/empatou em superioridade → sem ajuste (já é penalizado pelo resultado)
    if "disadvantage_factor" in games.columns and "result" in games.columns:
        disadv = pd.to_numeric(games["disadvantage_factor"], errors="coerce").fillna(0)
        # fator do adversário: o quanto O OUTRO TIME jogou em inferioridade nesse jogo
        opponent_disadv = (
            games[["match_id", "team", "disadvantage_factor"]]
            .rename(columns={"team": "opponent", "disadvantage_factor": "opponent_disadvantage_factor"})
        )
        games = games.merge(opponent_disadv, on=["match_id", "opponent"], how="left")
        opp_disadv = pd.to_numeric(games["opponent_disadvantage_factor"], errors="coerce").fillna(0)

        won = games["result"] == "vitoria"
        lost = games["result"] == "derrota"
        # própria inferioridade: bônus se ganhou, penalidade se perdeu
        own_bonus = 1.0 + disadv * 0.4 * won.astype(float)
        own_penalty = 1.0 - disadv * 0.4 * lost.astype(float)
        # superioridade sobre o adversário: penaliza quem ganhou jogando com 11 contra menos
        superiority_penalty = 1.0 - opp_disadv * 0.3 * won.astype(float)
        adjustment = own_bonus * own_penalty * superiority_penalty
        for col in ["ataque_ctx", "defesa_ctx", "eficiencia_ctx", "controle_ctx"]:
            games[col] = (games[col] * adjustment).clip(0.3, 2.0)

    by_team = games.groupby("team", dropna=False)[["ataque_ctx", "defesa_ctx", "eficiencia_ctx", "controle_ctx"]].mean().reset_index()
    return by_team


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


def _sample_confidence(games: pd.Series, full_confidence_games: int = 3) -> pd.Series:
    """Confiança da amostra (0 a 1) cresce com mais jogos, em curva CÔNCAVA:

        0 jogos → 0.0    1 jogo → 0.50    2 jogos → 0.80    3+ jogos → 1.0

    Côncava (e não linear 1/3, 2/3, 1) porque cada jogo adicional traz menos
    informação nova que o anterior — rendimentos decrescentes. O 1º jogo é o
    maior salto (de "nada" para "indício forte"), por isso já vale 50%; o 2º
    confirma (+30%); o 3º refina (+20%). Sem isso, os scores de processo
    (ataque/defesa/eficiência/controle) ficavam espremidos perto de 50 na
    rodada 1 (1 jogo valia só 1/3). Interpola linearmente entre os marcos para
    contagens fracionárias e satura em 1.0 (mata-mata só aumenta jogos, não muda
    a referência da fase de grupos = full_confidence_games).
    """
    import numpy as np
    numeric = pd.to_numeric(games, errors="coerce").fillna(0).clip(lower=0)
    # marcos da curva côncava ancorados em full_confidence_games (=3): 50/80/100%
    xp = [0.0, 1.0, 2.0, float(full_confidence_games)]
    fp = [0.0, 0.50, 0.80, 1.0]
    interpolated = np.interp(numeric.clip(upper=full_confidence_games), xp, fp)
    return pd.Series(interpolated, index=numeric.index).clip(0, 1)


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


def _weighted_score_per_row(
    frame: pd.DataFrame,
    weights: dict[str, float],
    overrides: dict[str, pd.Series | float],
) -> pd.Series:
    """Como ``_weighted_score``, mas permite que alguns pesos variem por
    linha (ex: peso de força relativa escalado pela maturidade do Elo,
    que pode diferir entre snapshots). ``overrides`` substitui o peso fixo
    de ``weights`` por uma Series/escalar para as colunas informadas.
    """
    parts, used = [], []
    for col, w in weights.items():
        if col not in frame.columns:
            continue
        effective_w = overrides.get(col, w)
        parts.append(frame[col].fillna(0) * effective_w)
        used.append(effective_w)
    if not parts:
        return pd.Series(0.0, index=frame.index)
    total_used = sum(used)
    total_used = total_used if isinstance(total_used, pd.Series) else pd.Series(total_used, index=frame.index)
    return sum(parts) / total_used.replace(0, 1)


def _add_rank(frame: pd.DataFrame, score_col: str, rank_col: str) -> pd.DataFrame:
    out = frame.copy()
    # quem tem score nulo (ex.: jogador sem jogos) não recebe rank — Int64 nullable
    # evita o crash de astype(int) sobre NaN e mantém o ranking só dos pontuados.
    out[rank_col] = out[score_col].rank(method="min", ascending=False).astype("Int64")
    return out


def _player_profile(row: pd.Series) -> str:
    """Classifica jogador por perfil usando a posição de elenco/convocação
    (roster_position) quando disponível — estável e correta independente de
    onde o jogador atuou tatica numa partida especifica. Cai para a posição
    de lineup (tática, pode variar jogo a jogo) só quando o roster não tem
    o jogador, e por último para o fallback estatístico.

    Fallback por estatísticas: tackles e interceptions não existem nos dados ESPN —
    o fallback usa apenas saves vs produção ofensiva. Sem posição e sem saves,
    o padrão é "meio" (perfil mais genérico).
    """
    position = str(row.get("roster_position") or row.get("position") or "").strip().upper()
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

    Goleiro:  saves/jogo         peso 0.4
              save%              peso 0.4  (saves / saves+gols_sofridos)
              gols_sofridos/jogo peso 0.2  (lower_is_better)

    Defensor: fouls_drawn/jogo   peso 0.4  (duelos ganhos, pressão)
              goals_conceded/j   peso 0.3  (lower — solidez defensiva)
              shots_on_target/j  peso 0.2  (chegada ao ataque)
              fouls_committed/j  peso 0.1  (lower — disciplina)

    Meia:     goals+assists/jogo peso 0.5  (criação e finalização)
              shots_on_target/j  peso 0.2  (chutes perigosos)
              total_shots/jogo   peso 0.1  (volume ofensivo)
              fouls_drawn/jogo   peso 0.2  (envolvimento — peso baixo)

    Atacante: goals/jogo         peso 0.5  (função principal)
              assists/jogo       peso 0.2  (criação)
              shots_on_target/j  peso 0.2  (pressão constante)
              total_shots/jogo   peso 0.1  (volume ofensivo)
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
            # total de chutes tentados = on_target + off_target + bloqueados + trave
            total_shots = sum(
                pool[c].fillna(0) for c in ["shots_on_target", "shots_off_target", "shots_blocked_att", "shots_woodwork"]
                if c in pool.columns
            )
            if isinstance(total_shots, int):
                total_shots = pd.Series(0.0, index=pool.index)
            raw = _wavg([
                (_zscore_to_100(_safe_divide(participacoes, pool["jogos"])),      0.5),
                (_zscore_to_100(_per_game("shots_on_target", pool)),              0.2),
                (_zscore_to_100(_safe_divide(total_shots, pool["jogos"])),        0.1),
                (_zscore_to_100(_per_game("fouls_drawn", pool)),                  0.2),
            ])

        else:  # atacante — sem fouls_drawn; usa todos os chutes tentados
            total_shots = sum(
                pool[c].fillna(0) for c in ["shots_on_target", "shots_off_target", "shots_blocked_att", "shots_woodwork"]
                if c in pool.columns
            )
            if isinstance(total_shots, int):
                total_shots = pd.Series(0.0, index=pool.index)
            raw = _wavg([
                (_zscore_to_100(_per_game("goals", pool)),                        0.5),
                (_zscore_to_100(_per_game("assists", pool)),                      0.2),
                (_zscore_to_100(_per_game("shots_on_target", pool)),              0.2),
                (_zscore_to_100(_safe_divide(total_shots, pool["jogos"])),        0.1),
            ])

        conf = _sample_confidence(pool["jogos"])
        adjusted = _apply_confidence(raw.fillna(50.0), conf)
        result.loc[mask] = adjusted.values

    return result


def _numerical_disadvantage_factor(
    events: pd.DataFrame | None, match_ids: "np.ndarray"
) -> pd.DataFrame:
    """Fração do jogo que cada time jogou em inferioridade numérica por expulsão.

    Retorna DataFrame com colunas [match_id, team, disadvantage_factor] onde
    disadvantage_factor é a proporção de minutos jogados com menos jogadores
    (0.0 = jogo completo com 11, 1.0 = expulsão no 1º minuto).

    Expulsão no minuto M → time jogou (90 - M) / 90 minutos em inferioridade.
    Múltiplas expulsões acumulam (ficou com 9: soma os dois intervalos).
    O adversário recebe o fator invertido como bônus (jogar contra 9 é vantagem),
    mas apenas nos scores de ataque/defesa via _opponent_context_multiplier.
    """
    empty = pd.DataFrame(columns=["match_id", "team", "disadvantage_factor"])
    if events is None or events.empty:
        return empty
    reds = events[events["event_type"] == "cartao_vermelho"].copy()
    if reds.empty:
        return empty

    reds["minute_num"] = pd.to_numeric(reds["minute"], errors="coerce").fillna(90)
    reds["minute_num"] = reds["minute_num"].clip(1, 90)

    rows = []
    for (match_id, team), group in reds.groupby(["match_id", "team"]):
        # cada expulsão contribui com (90 - minuto) / 90 de inferioridade
        factor = float((90 - group["minute_num"]).clip(lower=0).sum() / 90)
        rows.append({"match_id": match_id, "team": team, "disadvantage_factor": min(factor, 1.0)})
    return pd.DataFrame(rows) if rows else empty


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


# ---------------------------------------------------------------------------
# Estilo de jogo (métrica descritiva, informacional)
# ---------------------------------------------------------------------------
# Os 4 eixos são z-scores 0–100 RELATIVOS ao torneio (50 = na média): não medem
# qualidade, medem posição numa dimensão de estilo. Um time pode ter eixo alto
# de "jogo direto" e ainda ser ruim — estilo e qualidade são ortogonais.
#
#   estilo_posse:        construir tocando (posse + volume/precisão de passes)
#                        ↔ jogo direto/vertical. Alto = posse; baixo = direto.
#   estilo_pressao:      recuperar a bola alto e no campo do adversário
#                        (posse ganha no terço final, desarmes + interceptações)
#                        ↔ bloco baixo/reativo (mais cortes/clearances).
#   estilo_largura:      atacar pelos lados (cruzamentos certos)
#                        ↔ jogo interior (dribles, passes em profundidade).
#   estilo_verticalidade: ataque de volume/rápido (chutes por posse, passes pro
#                        terço final) ↔ ataque paciente.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Classificação por ARQUÉTIPO de estilo (perfis IDEAIS absolutos)
# ---------------------------------------------------------------------------
# Cada arquétipo é um PERFIL IDEAL definido em VALORES REAIS por jogo (não em
# z-score relativo ao torneio). A afinidade do time a um arquétipo mede quão
# perto os dados dele estão desse molde ideal — INDEPENDENTE dos outros times.
# Não é ranking: um time não fica "100% Ofensivo" por ser o melhor do torneio,
# e sim por bater o perfil ideal de um time ofensivo. A flag é o arquétipo de
# MAIOR afinidade (≥ _STYLE_MIN_AFFINITY, senão "Equilibrado").
#
# Cada métrica é (percentil, peso, direção):
#   - percentil: qual ponto da distribuição REAL do torneio define a meta.
#     Ex: gols do "Ofensivo" = p80 → a meta é o valor de gols/jogo que separa
#     os 20% mais ofensivos. O percentil é FIXO (define o arquétipo); o valor
#     concreto que ele representa RECALCULA a cada jogo (dinâmico, ver
#     _resolve_style_targets).
#   - direção +1 → "quanto MAIS, melhor": score da métrica = min(valor/meta, 1)
#     — satura em 100% ao atingir a meta (passar dela não dá mais que 100%: uma
#     goleada de 7×0 e um ataque sólido cravam igual o traço "ofensivo").
#     A meta vem de um percentil ALTO (p70-p85).
#   - direção -1 → "quanto MENOS, melhor": score = min(meta/valor, 1) — satura
#     em 100% ao ficar ABAIXO da meta. A meta vem de um percentil BAIXO (p15-p35).
# Afinidade do arquétipo = média ponderada dos scores das métricas (0-100).
# Flag = arquétipo de maior afinidade (≥ _STYLE_MIN_AFFINITY, senão Equilibrado).
# Cada arquétipo tem EXATAMENTE 4 métricas (exibição uniforme no dashboard). As
# 2-3 primeiras são o traço dominante (peso alto); a(s) última(s), com peso
# menor, são refinamentos que reforçam a identidade sem distorcer a classificação.
_STYLE_PROFILES: dict[str, dict[str, tuple[float, float, int]]] = {
    # nome : { métrica_por_jogo: (percentil, peso, direção) }
    "Toque e Posse": {
        # posse com PESO DOMINANTE: o traço que define o estilo é ter MUITO a
        # bola. Um time de posse mediana (p50) não é Toque e Posse por acaso só
        # porque passa com precisão — por isso posse pesa bem mais que as outras.
        "posse": (82, 2.0, +1), "passes": (82, 1.2, +1), "precisao": (78, 0.8, +1),
        "pressao": (55, 0.3, +1),        # quem domina a bola pressiona p/ recuperá-la
    },
    "Ofensivo": {
        "gols": (80, 1.2, +1), "no_alvo": (80, 1.0, +1), "chutes": (75, 0.8, +1),
        "verticalidade": (60, 0.4, +1),  # volume ofensivo costuma ser vertical
    },
    "Drible e Individual": {
        "dribles": (80, 1.2, +1), "key_passes": (75, 0.8, +1),
        "cruzamentos": (35, 0.5, -1),  # cria por dentro, não por cruzamento
        "posse": (60, 0.4, +1),         # precisa da bola para o talento aparecer
    },
    "Defensivo": {
        "clearances": (75, 1.0, +1), "posse": (25, 1.0, -1), "chutes": (30, 0.7, -1),
        "passes": (30, 0.5, -1),         # bloco baixo troca poucos passes
    },
    "Contra-ataque": {
        "verticalidade": (75, 1.0, +1), "posse": (30, 0.9, -1),
        "no_alvo": (60, 0.6, +1),        # pouca posse mas finaliza com perigo
        "passes": (35, 0.4, -1),         # sai jogando direto, troca pouco passe
    },
    "Jogo pelas Pontas": {
        "cruzamentos": (80, 1.2, +1), "dribles": (35, 0.4, -1),
        "key_passes": (60, 0.6, +1),     # cruzamento é criação de chance pelo lado
        "posse": (55, 0.4, +1),          # joga aberto, precisa ter a bola
    },
    "Pressão Alta": {
        # pressão é o traço dominante; posse penalizada com PESO ALTO (1.0) e
        # alvo BAIXO (p45) — um time que domina a bola (posse alta) é Toque e
        # Posse, não Pressão Alta. Sem isso, times de posse que pressionam
        # roubavam a flag. Métricas extras com peso baixo só refinam.
        "pressao": (82, 2.0, +1), "posse": (45, 0.9, -1),
        "chutes": (60, 0.3, +1),         # recupera alto → finaliza mais
        "verticalidade": (60, 0.3, +1),  # recupera e ataca rápido
    },
}

# Sementes: valor-âncora de cada métrica (em valores/jogo) usado quando ainda há
# poucos jogos no torneio — futebol de seleção "típico", de conhecimento de
# domínio. A meta real é uma mistura semente↔percentil cujo peso migra para o
# percentil conforme os jogos acumulam (ver _resolve_style_targets). Cada
# métrica tem (semente_para_percentil_ALTO, semente_para_percentil_BAIXO): um
# percentil p≥50 usa a 1ª (nível "destaca-se nisso"), p<50 usa a 2ª (nível
# "evita isso"). Ancoradas nos ranges reais observados no torneio.
_STYLE_METRIC_SEEDS: dict[str, tuple[float, float]] = {
    # métrica : (semente p/ meta ALTA, semente p/ meta BAIXA)
    "posse":         (60.0, 40.0),
    "passes":        (560.0, 330.0),
    "precisao":      (87.0, 78.0),
    "gols":          (2.6, 0.7),
    "no_alvo":       (6.5, 2.5),
    "chutes":        (17.0, 8.0),
    "dribles":       (11.0, 4.0),
    "key_passes":    (15.0, 6.0),
    "cruzamentos":   (7.0, 2.0),
    "clearances":    (32.0, 16.0),
    "verticalidade": (62.0, 40.0),
    "pressao":       (60.0, 42.0),
}

# Afinidade mínima (0-100) para o time receber a flag do melhor arquétipo. Se
# nem o melhor encaixe atinge isso, o time não tem perfil claro → "Equilibrado".
_STYLE_MIN_AFFINITY = 55.0

# Mantido para compat com a tabela de eixos exibida (4 eixos numéricos seguem
# existindo como ingredientes visíveis; a flag agora vem do arquétipo).
_STYLE_AXIS_LABELS: list[tuple[str, str, str]] = [
    ("estilo_posse", "posse", "jogo direto"),
    ("estilo_pressao", "pressão alta", "bloco baixo"),
    ("estilo_verticalidade", "ataque vertical", "ataque paciente"),
    ("estilo_largura", "jogo pelas pontas", "jogo interior"),
]


def _add_team_style(scores: pd.DataFrame) -> pd.DataFrame:
    """Calcula os 4 eixos de estilo (0–100, z-score entre os times) e o rótulo
    textual. Cada coluna de origem é por jogo (divide pelos jogos) para não
    favorecer quem disputou mais partidas. Campos ausentes viram 0 — o time
    fica na média (50) naquele eixo, sem distorcer os outros.

    Os eixos guardam a posição CHEIA (sem achatamento pela amostra): estilo é
    descritivo, não avaliativo, então todo time recebe uma assinatura já no 1º
    jogo (ver _style_label). A assinatura é provisória e se firma conforme os
    jogos acumulam, mas nunca é escondida atrás do neutro.
    """
    jogos = scores["jogos"].clip(lower=1)

    def _per_game(col: str) -> pd.Series:
        if col not in scores.columns:
            return pd.Series(0.0, index=scores.index)
        return _safe_divide(scores[col], jogos)

    posse_media = scores.get("posse_media", pd.Series(0.0, index=scores.index))
    passes_pj = _per_game("passes")
    precisao = scores.get("precisao_passes_media", pd.Series(0.0, index=scores.index))
    # posse + volume de passes + precisão: as três faces de "ter o jogo nos pés".
    estilo_posse = _mean_score([
        _zscore_to_100(posse_media),
        _zscore_to_100(passes_pj),
        _zscore_to_100(precisao),
    ])

    # pressão: recuperações altas (posse ganha no terço final) e duelos
    # defensivos no campo de frente (desarmes + interceptações). O polo baixo
    # — muitos cortes/clearances — indica defender recuado, sem disputar alto.
    recuperacao_alta = _per_game("final_third_possession_won")
    duelos = _per_game("tackles") + _per_game("interceptions")
    bloco_baixo = _per_game("clearances")
    estilo_pressao = _mean_score([
        _zscore_to_100(recuperacao_alta),
        _zscore_to_100(duelos),
        _zscore_to_100(bloco_baixo, lower_is_better=True),
    ])

    # largura: cruzamentos CERTOS por jogo (não tentados — chuveirinho perdido
    # não é estilo de ataque pelos lados). Polo baixo = jogo interior, medido
    # por dribles e passes-chave que furam por dentro.
    cruzamentos = _per_game("accurate_crosses")
    interior = _per_game("dribbles_won") + _per_game("key_passes")
    estilo_largura = _mean_score([
        _zscore_to_100(cruzamentos),
        _zscore_to_100(interior, lower_is_better=True),
    ])

    # verticalidade: quão rápido/direto o time chega ao ataque — chutes por
    # unidade de posse (converte posse em finalização em vez de só circular) e
    # volume de passes no terço final. Alto = vertical; baixo = paciente.
    chutes_por_posse = _safe_divide(_per_game("chutes"), posse_media.clip(lower=1))
    final_third = _per_game("passes_into_final_third")
    estilo_verticalidade = _mean_score([
        _zscore_to_100(chutes_por_posse),
        _zscore_to_100(final_third),
    ])

    # Os 4 eixos (0-100) seguem expostos como ingredientes visíveis no painel.
    scores["estilo_posse"] = estilo_posse.round(1)
    scores["estilo_pressao"] = estilo_pressao.round(1)
    scores["estilo_largura"] = estilo_largura.round(1)
    scores["estilo_verticalidade"] = estilo_verticalidade.round(1)

    # --- Classificação por arquétipo (perfis ideais, metas dinâmicas) ---
    # Métricas em VALORES REAIS por jogo (não z-score) — comparadas a metas
    # absolutas que evoluem com o torneio (ver _resolve_style_targets).
    # `verticalidade`/`pressao` reusam os eixos 0-100 (já são escalas próprias).
    metrics = pd.DataFrame({
        "posse": posse_media,
        "passes": passes_pj,
        "precisao": precisao * (100.0 if precisao.max() <= 1.5 else 1.0),  # frac→%
        "dribles": _per_game("dribbles_won"),
        "key_passes": _per_game("key_passes"),
        "chutes": _per_game("chutes"),
        "gols": _per_game("gols_pro") if "gols_pro" in scores.columns else _per_game("goals_for"),
        "no_alvo": _per_game("chutes_no_alvo"),
        "cruzamentos": _per_game("accurate_crosses"),
        "clearances": _per_game("clearances"),
        "verticalidade": estilo_verticalidade,
        "pressao": estilo_pressao,
    }, index=scores.index)

    # nº de jogos do TORNEIO (não por time) = soma das aparições / 2 — é o
    # tamanho da amostra que estabiliza as metas dinâmicas.
    total_games = int(round(float(scores["jogos"].sum()) / 2.0))
    targets = _resolve_style_targets(metrics, n_jogos=total_games)
    affinities = _style_affinities(metrics, targets)
    scores["estilo_jogo"] = [_classify_style(a) for a in affinities]
    # Afinidade (0-100) a CADA arquétipo, serializada como JSON por time — o
    # dashboard usa no dropdown "ver o time como estilo X". String para
    # sobreviver ao parquet sem virar uma coluna por arquétipo.
    import json as _json
    scores["estilo_afinidades"] = [_json.dumps(row) for row in affinities]
    # Detalhamento valor-vs-meta por arquétipo/métrica — o dashboard mostra
    # "26/18 ✅" com barra, deixando claro POR QUE um arquétipo encaixa.
    breakdown = _style_breakdown(metrics, targets)
    scores["estilo_detalhe"] = [_json.dumps(row) for row in breakdown]
    return scores


def _style_breakdown(metrics: pd.DataFrame, targets: dict[str, float]) -> list[dict[str, list[dict[str, Any]]]]:
    """Para cada time, detalha o encaixe em cada arquétipo métrica a métrica:
    {arquétipo: [{metrica, valor, meta, score, direcao}, ...]}. `score` é o
    0-1 daquela métrica (mesma saturação suave de _style_affinities); `direcao`
    é "mais" (+1, mais é melhor) ou "menos" (-1). Usado só p/ exibição."""
    out: list[dict[str, list[dict[str, Any]]]] = []
    for idx in metrics.index:
        row = metrics.loc[idx]
        team_detail: dict[str, list[dict[str, Any]]] = {}
        for name, profile in _STYLE_PROFILES.items():
            items: list[dict[str, Any]] = []
            for metric, (pct, _w, direction) in profile.items():
                meta = targets.get(f"{metric}@{pct}")
                val = row.get(metric)
                if meta is None or val is None or pd.isna(val):
                    continue
                val = float(val)
                if direction > 0:
                    ratio = val / meta if meta > 0 else 0.0
                else:
                    ratio = meta / val if val > 0 else 2.0
                items.append({
                    "metrica": metric,
                    "valor": round(val, 1),
                    "meta": round(float(meta), 1),
                    "score": round(_style_metric_score(ratio), 3),
                    "direcao": "mais" if direction > 0 else "menos",
                })
            team_detail[name] = items
        out.append(team_detail)
    return out


def _style_target_blend_weight(n_jogos: int) -> float:
    """Peso (0-1) do percentil do torneio na meta, vs. a semente fixa. Cresce
    com o nº de jogos disputados — cedo confia na semente (futebol típico),
    tarde confia nos dados reais. Curva côncava saturando perto de ~60 jogos
    (metade do torneio): poucos jogos → percentis instáveis, então a semente
    domina e segura a assinatura; conforme acumula, a meta migra para os dados
    e se estabiliza."""
    import numpy as np
    # marcos: 0 jogos→0.0 | 10→0.30 | 30→0.65 | 60+→0.95
    return float(np.interp(max(n_jogos, 0), [0, 10, 30, 60], [0.0, 0.30, 0.65, 0.95]))


def _resolve_style_targets(metrics: pd.DataFrame, n_jogos: int) -> dict[str, float]:
    """Resolve a meta CONCRETA de cada métrica usada pelos arquétipos, de forma
    DINÂMICA: mistura a semente fixa com o percentil real do torneio, com peso
    migrando para o percentil conforme os jogos acumulam. Retorna {métrica: meta}.

    Cada métrica pode aparecer em vários arquétipos com o MESMO percentil-alvo
    (alto p/ direção +1, baixo p/ -1) — resolvemos uma meta por (métrica), pelo
    percentil declarado nos perfis. Se a mesma métrica usa percentis diferentes
    entre arquétipos (ex: posse p80 no Posse, p25 no Defensivo), guardamos uma
    meta por (métrica, percentil)."""
    k = _style_target_blend_weight(n_jogos)
    targets: dict[str, float] = {}
    for profile in _STYLE_PROFILES.values():
        for metric, (pct, _w, _d) in profile.items():
            key = f"{metric}@{pct}"
            if key in targets:
                continue
            col = metrics.get(metric)
            seed_hi, seed_lo = _STYLE_METRIC_SEEDS.get(metric, (1.0, 1.0))
            seed = seed_hi if pct >= 50 else seed_lo
            if col is None or col.dropna().empty:
                targets[key] = seed
                continue
            observed = float(np.percentile(col.dropna().astype(float), pct))
            targets[key] = seed * (1.0 - k) + observed * k
    return targets


def _style_affinities(metrics: pd.DataFrame, targets: dict[str, float]) -> list[dict[str, float]]:
    """Afinidade 0-100 de cada time a cada arquétipo, medida contra o PERFIL
    IDEAL absoluto (não contra os outros times). Para cada métrica do arquétipo:
      direção +1: score = min(valor/meta, 1)  (satura ao ATINGIR a meta alta)
      direção -1: score = min(meta/valor, 1)  (satura ao ficar ABAIXO da meta baixa)
    Afinidade do arquétipo = média ponderada (0-100). Independente do torneio:
    bater o molde dá 100% mesmo sem ser o melhor, e superá-lo não passa de 100%."""
    out: list[dict[str, float]] = []
    for idx in metrics.index:
        row = metrics.loc[idx]
        affin: dict[str, float] = {}
        for name, profile in _STYLE_PROFILES.items():
            total_w, acc = 0.0, 0.0
            for metric, (pct, w, direction) in profile.items():
                meta = targets.get(f"{metric}@{pct}")
                val = row.get(metric)
                if meta is None or val is None or pd.isna(val):
                    continue
                val = float(val)
                # ratio = quão perto do alvo (1.0 = atingiu; >1 = superou).
                if direction > 0:
                    ratio = val / meta if meta > 0 else 0.0
                else:
                    ratio = meta / val if val > 0 else 2.0
                acc += _style_metric_score(ratio) * w
                total_w += w
            affin[name] = round(100.0 * acc / total_w, 1) if total_w > 0 else 0.0
        out.append(affin)
    return out


def _style_metric_score(ratio: float) -> float:
    """Score 0-1 de uma métrica dado o ratio valor/meta. Saturação SUAVE: atingir
    a meta (ratio=1) dá ~0.85, não 1.0 — só superá-la com folga (ratio≥1.4) chega
    a 1.0. Assim um time que apenas alcança o limiar de vários arquétipos não
    crava 100% em todos ao mesmo tempo; o arquétipo em que ele MAIS se destaca
    (maior ratio) sobressai. Abaixo da meta, cai proporcionalmente."""
    if ratio <= 0:
        return 0.0
    if ratio >= 1.0:
        # 1.0→0.85 ... 1.4+→1.0 (recompensa folga, mas com teto rápido)
        return min(1.0, 0.85 + 0.15 * (ratio - 1.0) / 0.4)
    # abaixo do alvo: 0.85 no alvo decaindo a 0 — penaliza não atingir
    return 0.85 * ratio


def _classify_style(affinities: dict[str, float]) -> str:
    """Flag = arquétipo de MAIOR afinidade ao perfil ideal. Se nem o melhor
    atinge _STYLE_MIN_AFFINITY, o time não encaixa claramente em nenhum molde
    → "Equilibrado"."""
    if not affinities:
        return "Equilibrado"
    best_name = max(affinities, key=lambda k: affinities[k])
    if affinities[best_name] < _STYLE_MIN_AFFINITY:
        return "Equilibrado"
    return best_name


def _mode_or_first(values: pd.Series) -> Any:
    clean = values.dropna()
    if clean.empty:
        return None
    mode = clean.mode()
    return mode.iloc[0] if not mode.empty else clean.iloc[0]


def _number(value: Any) -> float | None:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(converted) else float(converted)
