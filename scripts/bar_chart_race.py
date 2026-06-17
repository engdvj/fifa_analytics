"""
Bar chart race — ranking de seleções jogo a jogo (Copa 2026)
Gera reports/tournament/ranking_race.html
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

SNAPSHOTS_DIR = Path("data/gold/analytics/snapshots")
OUTPUT = Path("reports/tournament/ranking_race.html")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Bandeiras dos 48 times — fonte única em watcher/flags.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "watcher"))
from flags import FLAGS  # noqa: E402

# Campos exportados por time por snapshot — o JS rankeia/ordena por qualquer um
METRIC_COLS = {
    # scores
    "score_geral": "score_geral",
    "score_resultado": "score_resultado",
    "score_ataque": "score_ataque",
    "score_defesa": "score_defesa",
    "score_eficiencia": "score_eficiencia",
    "score_controle": "score_controle",
    "score_forca_relativa": "score_forca_relativa",
    "score_disciplina": "score_disciplina",
    # resultado acumulado
    "saldo_gols": "saldo_gols",
    "gols_pro": "gols_pro",
    "gols_contra": "gols_contra",
    "aproveitamento": "aproveitamento",
    "pontos": "points",
    "elo_rating": "elo_rating",
    # médias ofensivas por jogo
    "gols_por_jogo": "gols_por_jogo",
    "chutes_por_jogo": "_chutes_por_jogo",       # calculado abaixo
    "chutes_no_alvo_por_jogo": "chutes_no_alvo_por_jogo",
    "precisao_chute": "chutes_no_alvo_por_chute", # % chutes no alvo
    "escanteios_por_jogo": "_escanteios_por_jogo", # calculado abaixo
    "key_passes_por_jogo": "key_passes_por_jogo",
    "dribbles_won_por_jogo": "dribbles_won_por_jogo",
    # médias defensivas por jogo
    "gols_contra_por_jogo": "gols_contra_por_jogo",
    "chutes_sofridos_por_jogo": "chutes_sofridos_por_jogo",
    "defesas_por_jogo": "_defesas_por_jogo",
    "jogos_sem_sofrer_gol": "jogos_sem_sofrer_gol",
    # controle por jogo
    "posse_media": "posse_media",
    "passes_por_jogo": "passes_por_jogo",
    "precisao_passes": "precisao_passes_media",   # % passes certos
    # disciplina por jogo
    "faltas_por_jogo": "faltas_por_jogo",
    "amarelos_por_jogo": "amarelos_por_jogo",
    "vermelhos_por_jogo": "vermelhos_por_jogo",
}

tl = pd.read_parquet(SNAPSHOTS_DIR / "snapshot_timeline.parquet")
jogos = sorted(tl["snapshot_jogo"].unique())

matches_df = pd.read_parquet(Path("data/gold/dim_match/canonical_matches.parquet"))
match_info = matches_df.set_index("match_id")[["home_team", "away_team", "home_score", "away_score"]].to_dict("index")

# Nota: o placar AO VIVO não fica no HTML (estático demais para tempo real) —
# vive na janela do watcher (watcher/fifa_progress.py), que é leve e atualiza
# sozinha. O HTML foca no ranking dos jogos já processados.

data: dict = {}
for n in jogos:
    snap = tl[tl["snapshot_jogo"] == n].copy()
    wp = SNAPSHOTS_DIR / f"weights_jogo_{n:03d}.json"
    pesos = json.loads(wp.read_text())["pesos"] if wp.exists() else {}
    match_id = snap["match_id_referencia"].iloc[0]

    mi = match_info.get(match_id, {})
    home = mi.get("home_team", "?")
    away = mi.get("away_team", "?")
    hs = mi.get("home_score")
    as_ = mi.get("away_score")
    score_str = f"{int(hs)}–{int(as_)}" if hs is not None and not pd.isna(hs) else "?"
    match_label = f"Jogo {n} · {home} {score_str} {away}"
    home_flag = FLAGS.get(home, "🏳️")
    away_flag = FLAGS.get(away, "🏳️")

    if n > 1:
        prev = tl[tl["snapshot_jogo"] == n - 1].set_index("team")["jogos"]
        curr = snap.set_index("team")["jogos"]
        playing = curr[curr > prev.reindex(curr.index).fillna(0)].index.tolist()
    else:
        playing = snap["team"].tolist()

    # Calcula médias por jogo para métricas sem coluna própria
    snap = snap.copy()
    snap["_chutes_por_jogo"] = snap.apply(
        lambda r: round(r["chutes"] / r["jogos"], 2) if r.get("jogos", 0) > 0 else None, axis=1
    )
    snap["_escanteios_por_jogo"] = snap.apply(
        lambda r: round(r["escanteios"] / r["jogos"], 2) if r.get("jogos", 0) > 0 else None, axis=1
    )
    snap["_defesas_por_jogo"] = snap.apply(
        lambda r: round(r["defesas"] / r["jogos"], 2) if r.get("jogos", 0) > 0 else None, axis=1
    )

    teams = []
    for _, row in snap.sort_values("score_geral", ascending=False).iterrows():
        entry: dict = {
            "team": row["team"],
            "flag": FLAGS.get(row["team"], "🏳️"),
            "jogos": int(row.get("jogos", 0)),
            "playing": row["team"] in playing,
        }
        for key, col in METRIC_COLS.items():
            val = row.get(col, None)
            try:
                entry[key] = round(float(val), 2) if val is not None and not pd.isna(val) else None
            except (TypeError, ValueError):
                entry[key] = None
        teams.append(entry)

    data[str(n)] = {
        "match_id": match_id,
        "match_label": match_label,
        "match_n": int(n),
        "home": home, "away": away, "score": score_str,
        "home_flag": home_flag, "away_flag": away_flag,
        "pesos": {k: round(v * 100) for k, v in pesos.items()},
        "teams": teams,
    }

data_json = json.dumps(data, ensure_ascii=False)


def _sort_key_ptbr(s: str) -> str:
    """Chave de ordenação alfabética pt-BR: trata acentos como a letra base
    (Á→A, É→E, Ç→C) — senão 'África do Sul' iria para o fim e 'Argélia'
    antes de 'Arábia' pela ordem de código Unicode."""
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode().casefold()


all_teams_json = json.dumps(
    sorted(tl["team"].unique().tolist(), key=_sort_key_ptbr), ensure_ascii=False
)
team_flags_json = json.dumps(FLAGS, ensure_ascii=False)


# ── Detalhes por seleção (aba "Seleções" + modal) ──────────────────────────────
# Monta, para cada seleção que já entrou no ranking, um bloco com: jogos
# disputados, escalações por jogo (formação + onze inicial + reservas), elenco
# agregado (stats somadas) e o resumo de scores do snapshot mais recente.

def _read_optional(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


_lineups = _read_optional(Path("data/gold/lineups/canonical_lineups.parquet"))
_pstats = _read_optional(Path("data/gold/fact_player_match_stats/canonical_player_stats.parquet"))

# Confederação de cada seleção da Copa 2026 (não existe nos dados — mapa fixo).
CONFEDERATION = {
    # UEFA
    "Alemanha": "UEFA", "Áustria": "UEFA", "Bélgica": "UEFA", "Bósnia e Herzegovina": "UEFA",
    "Croácia": "UEFA", "Escócia": "UEFA", "Espanha": "UEFA", "França": "UEFA",
    "Inglaterra": "UEFA", "Noruega": "UEFA", "Países Baixos": "UEFA", "Portugal": "UEFA",
    "Suécia": "UEFA", "Suíça": "UEFA", "Tchéquia": "UEFA", "Turquia": "UEFA",
    # CONMEBOL
    "Argentina": "CONMEBOL", "Brasil": "CONMEBOL", "Colômbia": "CONMEBOL",
    "Equador": "CONMEBOL", "Paraguai": "CONMEBOL", "Uruguai": "CONMEBOL",
    # CAF
    "Argélia": "CAF", "Cabo Verde": "CAF", "Costa do Marfim": "CAF", "Egito": "CAF",
    "Gana": "CAF", "Marrocos": "CAF", "RD Congo": "CAF", "Senegal": "CAF",
    "Tunísia": "CAF", "África do Sul": "CAF",
    # AFC
    "Arábia Saudita": "AFC", "Austrália": "AFC", "Catar": "AFC", "Coreia do Sul": "AFC",
    "Irã": "AFC", "Iraque": "AFC", "Japão": "AFC", "Jordânia": "AFC", "Uzbequistão": "AFC",
    # CONCACAF
    "Canadá": "CONCACAF", "Curaçao": "CONCACAF", "Estados Unidos": "CONCACAF",
    "Haiti": "CONCACAF", "México": "CONCACAF", "Panamá": "CONCACAF",
    # OFC
    "Nova Zelândia": "OFC",
}

# Grupo (A–L) de cada seleção, derivado dos jogos da fase de grupos.
_grupos_fg = matches_df[matches_df["group"].isin(list("ABCDEFGHIJKL"))]
TEAM_GROUP = {}
for _, _r in _grupos_fg.iterrows():
    for _t in (_r.get("home_team"), _r.get("away_team")):
        if _t and not pd.isna(_t):
            TEAM_GROUP[_t] = _r["group"]

# Stage/round legíveis reaproveitando os rótulos definidos mais abaixo seria
# circular (ainda não existem aqui); usamos um mapa local enxuto.
_STAGE_LABEL = {
    "fase_de_grupos": "Fase de Grupos", "r32": "Oitavas", "r16": "Quartas",
    "qf": "Semifinais", "sf": "Semifinais", "third": "Disputa 3º Lugar", "final": "Final",
}

# Snapshot mais recente por time (último jogo processado) — para o resumo de scores
_latest_n = max(jogos) if jogos else None
_latest_snap = tl[tl["snapshot_jogo"] == _latest_n] if _latest_n else pd.DataFrame()
_latest_by_team = _latest_snap.set_index("team") if not _latest_snap.empty else pd.DataFrame()

_SCORE_KEYS = [
    ("score_geral", "Geral"), ("score_resultado", "Resultado"), ("score_ataque", "Ataque"),
    ("score_defesa", "Defesa"), ("score_eficiencia", "Eficiência"), ("score_controle", "Controle"),
    ("score_forca_relativa", "Força Relativa"), ("score_disciplina", "Disciplina"),
]


def _num(v, nd=0):
    try:
        if v is None or pd.isna(v):
            return None
        return round(float(v), nd) if nd else int(v)
    except (TypeError, ValueError):
        return None


_finalizados = matches_df[matches_df["status"] == "finalizado"]
# Todas as seleções da Copa (não só as que já jogaram) — para a grade da aba.
_all_cup_teams = sorted(
    {t for t in matches_df["home_team"].dropna()} | {t for t in matches_df["away_team"].dropna()},
    key=_sort_key_ptbr,
)
teams_detail: dict[str, dict] = {}
for _team in _all_cup_teams:
    mine = _finalizados[
        (_finalizados["home_team"] == _team) | (_finalizados["away_team"] == _team)
    ].sort_values(["temporal_order", "date", "kickoff_time"])

    # — jogos + escalações
    jogos_list = []
    for _, m in mine.iterrows():
        mid = m["match_id"]
        is_home = m["home_team"] == _team
        opp = m["away_team"] if is_home else m["home_team"]
        gf = m["home_score"] if is_home else m["away_score"]
        ga = m["away_score"] if is_home else m["home_score"]
        gf_i, ga_i = _num(gf), _num(ga)
        if gf_i is None or ga_i is None:
            res = "—"
        elif gf_i > ga_i:
            res = "V"
        elif gf_i < ga_i:
            res = "D"
        else:
            res = "E"

        lu = _lineups[(_lineups["match_id"] == mid) & (_lineups["team"] == _team)]
        formation = None
        starters, subs = [], []
        if not lu.empty:
            fvals = lu["formation"].dropna().unique()
            formation = str(fvals[0]) if len(fvals) else None
            for _, p in lu.sort_values("shirt_number", na_position="last").iterrows():
                item = {
                    "name": p.get("player_name"),
                    "num": _num(p.get("shirt_number")),
                    "pos": p.get("position") if not pd.isna(p.get("position")) else None,
                }
                if bool(p.get("is_starter")):
                    starters.append(item)
                else:
                    subs.append(item)

        jogos_list.append({
            "match_id": mid,
            "opp": opp, "opp_flag": FLAGS.get(opp, "🏳️"),
            "home": bool(is_home),
            "gf": gf_i, "ga": ga_i, "res": res,
            "date": str(m.get("date", ""))[:10],
            "stage": _STAGE_LABEL.get(m.get("stage"), m.get("stage") or ""),
            "formation": formation,
            "starters": starters, "subs": subs,
        })

    # — elenco agregado (stats somadas em todos os jogos)
    ps = _pstats[_pstats["team"] == _team]
    players = []
    if not ps.empty:
        agg = ps.groupby("player_name", dropna=True).agg(
            jogos=("appearances", "sum"), gols=("goals", "sum"), assist=("assists", "sum"),
            chutes=("shots", "sum"), no_alvo=("shots_on_target", "sum"),
            amarelos=("yellow_cards", "sum"), vermelhos=("red_cards", "sum"),
            defesas=("saves", "sum"),
        ).reset_index()
        # ordena: gols, assistências, jogos
        agg = agg.sort_values(["gols", "assist", "jogos"], ascending=False)
        for _, p in agg.iterrows():
            players.append({
                "name": p["player_name"],
                "jogos": _num(p["jogos"]), "gols": _num(p["gols"]), "assist": _num(p["assist"]),
                "chutes": _num(p["chutes"]), "no_alvo": _num(p["no_alvo"]),
                "amarelos": _num(p["amarelos"]), "vermelhos": _num(p["vermelhos"]),
                "defesas": _num(p["defesas"]),
            })

    # — resumo de scores + campanha (snapshot mais recente)
    scores = {}
    rank = None
    campanha = {}
    if _team in _latest_by_team.index:
        srow = _latest_by_team.loc[_team]
        for key, _lbl in _SCORE_KEYS:
            scores[key] = _num(srow.get(key), 1)
        rank = _num(srow.get("ranking_snapshot"))
        campanha = {
            "gols_pro": _num(srow.get("gols_pro")),
            "gols_contra": _num(srow.get("gols_contra")),
            "saldo_gols": _num(srow.get("saldo_gols")),
            "pontos": _num(srow.get("points")),
            "aproveitamento": _num(srow.get("aproveitamento"), 2),
            "elo_rating": _num(srow.get("elo_rating")),
        }

    # — fase atual (do último jogo) e flag de eliminada
    stage_now = jogos_list[-1]["stage"] if jogos_list else None

    teams_detail[_team] = {
        "team": _team,
        "flag": FLAGS.get(_team, "🏳️"),
        "rank": rank,
        "n_jogos": len(jogos_list),
        "group": TEAM_GROUP.get(_team),
        "confed": CONFEDERATION.get(_team),
        "stage_now": stage_now,
        "scores": scores,
        "campanha": campanha,
        "score_labels": {k: v for k, v in _SCORE_KEYS},
        "jogos": jogos_list,
        "players": players,
    }

teams_detail_json = json.dumps(teams_detail, ensure_ascii=False)

# Metadados de fase por snapshot — para colorir e agrupar os dots
matches = matches_df
match_order = json.loads(Path("data/gold/analytics/snapshots/match_order.json").read_text())

STAGE_META = {
    "fase_de_grupos": {"label": "Fase de Grupos", "color": "#3b82f6"},
    "r32":            {"label": "Oitavas de Final", "color": "#8b5cf6"},
    "r16":            {"label": "Quartas de Final", "color": "#f59e0b"},
    "qf":             {"label": "Semifinais",       "color": "#ef4444"},
    "sf":             {"label": "Semifinais",       "color": "#ef4444"},
    "third":          {"label": "Disputa 3º Lugar", "color": "#6b7280"},
    "final":          {"label": "Final",            "color": "#f5c542"},
}

ROUND_LABELS = {
    ("fase_de_grupos", 1): "Grupos · Rodada 1",
    ("fase_de_grupos", 2): "Grupos · Rodada 2",
    ("fase_de_grupos", 3): "Grupos · Rodada 3",
    ("r32",  4): "Oitavas de Final",
    ("r16",  5): "Quartas de Final",
    ("qf",   6): "Semifinais",
    ("sf",   7): "Semifinais",
    ("third",8): "Disputa 3º Lugar",
    ("final",9): "Final",
}

# match_id → número do snapshot (posição em match_order), se já processado
snapshot_n_by_mid = {mid: n for n, mid in enumerate(match_order, 1)
                     if str(n) in data}

# Dots de TODOS os 104 jogos, em ordem cronológica (temporal_order).
# Cada um carrega o status (done/live/pending) para colorir.
matches_sorted = matches.sort_values(["temporal_order", "date", "kickoff_time"])
snapshot_meta = []
for _ord, (_, mrow) in enumerate(matches_sorted.iterrows()):
    mid = mrow["match_id"]
    stage = mrow.get("stage") or "fase_de_grupos"
    try:
        rnd = int(mrow.get("round") or 1)
    except (TypeError, ValueError):
        rnd = 1
    sm    = STAGE_META.get(stage, {"label": stage, "color": "#6b7280"})
    label = ROUND_LABELS.get((stage, rnd), sm["label"])
    status = mrow.get("status", "agendado")
    if status == "ao_vivo":
        dot_status = "live"
    elif mid in snapshot_n_by_mid:
        dot_status = "done"
    else:
        dot_status = "pending"
    mi = match_info.get(mid, {})
    # times que jogaram — None quando o confronto ainda não foi definido (mata-mata)
    _home, _away = mi.get("home_team"), mi.get("away_team")
    _teams = [
        None if (_home is None or pd.isna(_home)) else _home,
        None if (_away is None or pd.isna(_away)) else _away,
    ]
    snapshot_meta.append({
        "n": snapshot_n_by_mid.get(mid),   # número do snapshot p/ navegar (ou null)
        "order": _ord,                     # posição cronológica (0-based)
        "match_id": mid,
        "stage": stage, "round": rnd,
        "label": label, "color": sm["color"],
        "status": dot_status,
        "teams": _teams,
    })

snapshot_meta_json = json.dumps(snapshot_meta, ensure_ascii=False)

# Grupos de métricas para o seletor agrupado no HTML (4 colunas no card)
METRIC_GROUPS = [
    ("Scores", "tt-col-scores", [
        ("score_geral", "Geral"),
        ("score_resultado", "Resultado"),
        ("score_ataque", "Ataque"),
        ("score_defesa", "Defesa"),
        ("score_eficiencia", "Eficiência"),
        ("score_controle", "Controle"),
        ("score_forca_relativa", "Força Relativa"),
        ("score_disciplina", "Disciplina"),
    ]),
    ("Campanha · Totais", "tt-col-campanha", [
        ("pontos", "Pontos"),
        ("aproveitamento", "Aproveitamento %"),
        ("saldo_gols", "Saldo de Gols"),
        ("gols_pro", "Gols Marcados"),
        ("gols_contra", "Gols Sofridos"),
        ("elo_rating", "Rating Elo"),
    ]),
    ("Ataque · Média/jogo", "tt-col-ataque", [
        ("gols_por_jogo", "Gols"),
        ("chutes_por_jogo", "Chutes"),
        ("chutes_no_alvo_por_jogo", "No Alvo"),
        ("precisao_chute", "Precisão de Chute %"),
        ("escanteios_por_jogo", "Escanteios"),
    ]),
    ("Defesa · Média/jogo", "tt-col-defesa", [
        ("gols_contra_por_jogo", "Gols Sofridos"),
        ("chutes_sofridos_por_jogo", "Chutes Sofridos"),
        ("defesas_por_jogo", "Defesas do Goleiro"),
        ("jogos_sem_sofrer_gol", "Jogos Sem Sofrer Gol"),
    ]),
    ("Controle · Média/jogo", "tt-col-controle", [
        ("posse_media", "Posse Média %"),
        ("passes_por_jogo", "Passes"),
        ("precisao_passes", "Precisão de Passes %"),
        ("key_passes_por_jogo", "Passes-Chave"),
        ("dribbles_won_por_jogo", "Dribles"),
    ]),
    ("Disciplina · Média/jogo", "tt-col-disciplina", [
        ("faltas_por_jogo", "Faltas"),
        ("amarelos_por_jogo", "Amarelos"),
        ("vermelhos_por_jogo", "Vermelhos"),
    ]),
]

# Métricas onde menor = melhor (barra mais comprida = mais destaque negativo)
LOWER_IS_BETTER = {
    "gols_contra", "gols_contra_por_jogo", "chutes_sofridos_por_jogo",
    "faltas_por_jogo", "amarelos_por_jogo", "vermelhos_por_jogo",
}

metric_groups_json = json.dumps(METRIC_GROUPS, ensure_ascii=False)
lower_is_better_json = json.dumps(list(LOWER_IS_BETTER), ensure_ascii=False)
snapshot_meta_json_var = snapshot_meta_json  # alias para usar no f-string

# Métricas relacionadas: ao selecionar uma, as outras ficam destacadas no card
METRIC_RELATIONS: dict[str, list[str]] = {
    # ── score_resultado ← aproveitamento_ponderado + saldo_gols/jogo
    "score_resultado":         ["aproveitamento", "pontos", "saldo_gols", "gols_pro", "gols_contra", "score_geral"],
    "aproveitamento":          ["pontos", "saldo_gols", "score_resultado"],
    "pontos":                  ["aproveitamento", "saldo_gols", "score_resultado"],
    "saldo_gols":              ["gols_pro", "gols_contra", "aproveitamento", "score_resultado"],
    "gols_pro":                ["saldo_gols", "gols_por_jogo", "score_resultado", "score_ataque"],
    "gols_contra":             ["saldo_gols", "gols_contra_por_jogo", "jogos_sem_sofrer_gol", "score_resultado", "score_defesa"],

    # ── score_ataque ← gols/jogo + chutes_no_alvo/jogo (× contexto adversário)
    "score_ataque":            ["gols_por_jogo", "chutes_no_alvo_por_jogo", "score_eficiencia"],
    "gols_por_jogo":           ["gols_pro", "chutes_no_alvo_por_jogo", "precisao_chute", "score_ataque", "score_eficiencia"],
    "chutes_no_alvo_por_jogo": ["chutes_por_jogo", "precisao_chute", "gols_por_jogo", "score_ataque", "score_eficiencia"],
    "chutes_por_jogo":         ["chutes_no_alvo_por_jogo", "precisao_chute", "escanteios_por_jogo"],
    "escanteios_por_jogo":     ["chutes_por_jogo", "key_passes_por_jogo"],

    # ── score_eficiencia ← gols/chute (precisao_chute) + chutes_no_alvo/chute + key_passes/jogo
    "score_eficiencia":        ["precisao_chute", "chutes_no_alvo_por_jogo", "gols_por_jogo", "key_passes_por_jogo", "score_ataque"],
    "precisao_chute":          ["chutes_por_jogo", "chutes_no_alvo_por_jogo", "gols_por_jogo", "score_eficiencia"],
    "key_passes_por_jogo":     ["gols_por_jogo", "escanteios_por_jogo", "score_eficiencia", "score_controle"],

    # ── score_defesa ← gols_contra/jogo + chutes_no_alvo_sofridos/jogo + clean_sheet_rate
    "score_defesa":            ["gols_contra_por_jogo", "chutes_sofridos_por_jogo", "jogos_sem_sofrer_gol", "defesas_por_jogo", "gols_contra"],
    "gols_contra_por_jogo":    ["gols_contra", "chutes_sofridos_por_jogo", "jogos_sem_sofrer_gol", "defesas_por_jogo", "score_defesa"],
    "chutes_sofridos_por_jogo":["gols_contra_por_jogo", "defesas_por_jogo", "jogos_sem_sofrer_gol", "score_defesa"],
    "defesas_por_jogo":        ["chutes_sofridos_por_jogo", "gols_contra_por_jogo", "jogos_sem_sofrer_gol", "score_defesa"],
    "jogos_sem_sofrer_gol":    ["gols_contra_por_jogo", "gols_contra", "defesas_por_jogo", "score_defesa"],

    # ── score_controle ← posse + passes + precisao_passes + posse_produtiva (chutes_no_alvo/posse) + dribbles
    "score_controle":          ["posse_media", "passes_por_jogo", "precisao_passes", "dribbles_won_por_jogo", "chutes_no_alvo_por_jogo"],
    "posse_media":             ["passes_por_jogo", "precisao_passes", "chutes_no_alvo_por_jogo", "score_controle"],
    "passes_por_jogo":         ["posse_media", "precisao_passes", "key_passes_por_jogo", "score_controle"],
    "precisao_passes":         ["passes_por_jogo", "posse_media", "score_controle"],
    "dribbles_won_por_jogo":   ["posse_media", "key_passes_por_jogo", "score_controle"],

    # ── score_disciplina ← faltas + amarelos + vermelhos por jogo
    "score_disciplina":        ["faltas_por_jogo", "amarelos_por_jogo", "vermelhos_por_jogo"],
    "faltas_por_jogo":         ["amarelos_por_jogo", "vermelhos_por_jogo", "score_disciplina"],
    "amarelos_por_jogo":       ["faltas_por_jogo", "vermelhos_por_jogo", "score_disciplina"],
    "vermelhos_por_jogo":      ["amarelos_por_jogo", "faltas_por_jogo", "score_disciplina"],

    # ── score_forca_relativa ← elo_rating puro (acumulado da campanha)
    "score_forca_relativa":    ["elo_rating", "aproveitamento", "pontos"],
    "elo_rating":              ["score_forca_relativa", "aproveitamento", "pontos"],

    # ── score_geral ← todos os 6 componentes
    "score_geral":             ["score_resultado", "score_ataque", "score_defesa",
                                "score_eficiencia", "score_controle", "score_forca_relativa", "score_disciplina"],
}

# Relações indiretas: correlações naturais que NÃO entram diretamente no cálculo do score,
# mas são contextualmente relevantes (ex: mais chutes totais → mais no alvo → influencia ataque)
METRIC_RELATIONS_INDIRECT: dict[str, list[str]] = {
    # chutes totais são contexto de volume, não insumo direto
    "score_ataque":            ["chutes_por_jogo", "escanteios_por_jogo", "key_passes_por_jogo"],
    "chutes_no_alvo_por_jogo": ["escanteios_por_jogo", "key_passes_por_jogo"],
    "gols_por_jogo":           ["chutes_por_jogo", "escanteios_por_jogo"],
    "gols_pro":                ["chutes_no_alvo_por_jogo", "precisao_chute"],

    # eficiência: key_passes é insumo quando 365scores disponível (nem sempre)
    "score_eficiencia":        ["chutes_por_jogo", "escanteios_por_jogo"],
    "precisao_chute":          ["escanteios_por_jogo"],

    # defesa: chutes sofridos é proxy de chutes no alvo sofridos (insumo real)
    "score_defesa":            ["faltas_por_jogo"],
    "gols_contra_por_jogo":    ["faltas_por_jogo"],
    "gols_contra":             ["chutes_sofridos_por_jogo", "faltas_por_jogo"],

    # controle: passes-chave e dribles são efeito do controle, não insumo direto
    "score_controle":          ["key_passes_por_jogo", "escanteios_por_jogo"],
    "posse_media":             ["key_passes_por_jogo", "dribbles_won_por_jogo"],
    "passes_por_jogo":         ["escanteios_por_jogo", "dribbles_won_por_jogo"],

    # resultado: força relativa do adversário influencia indiretamente via ponderação
    "score_resultado":         ["elo_rating", "score_forca_relativa"],
    "aproveitamento":          ["elo_rating"],
    "saldo_gols":              ["gols_por_jogo", "gols_contra_por_jogo"],

    # força relativa: resultado e aproveitamento são consequência, não insumo
    "score_forca_relativa":    ["score_resultado", "aproveitamento"],
    "elo_rating":              ["score_resultado", "saldo_gols"],

    # disciplina: faltas geram escanteios/cartões
    "faltas_por_jogo":         ["escanteios_por_jogo"],
    "amarelos_por_jogo":       ["escanteios_por_jogo"],

    # escanteios: resultado de pressão ofensiva
    "escanteios_por_jogo":     ["score_ataque", "gols_por_jogo", "chutes_por_jogo"],
    "chutes_por_jogo":         ["score_ataque", "gols_por_jogo"],
    "key_passes_por_jogo":     ["chutes_por_jogo", "escanteios_por_jogo", "score_ataque"],
}
metric_relations_json = json.dumps(METRIC_RELATIONS, ensure_ascii=False)
metric_relations_indirect_json = json.dumps(METRIC_RELATIONS_INDIRECT, ensure_ascii=False)

SCORE_INFO: dict[str, dict] = {
    "score_resultado": {
        "desc": "Aproveitamento de pontos na campanha, ponderado por dificuldade dos adversários.",
        "metricas": ["Pontos", "Aproveitamento %", "Saldo de Gols"],
    },
    "score_ataque": {
        "desc": "Poder ofensivo: volume e qualidade das finalizações criadas.",
        "metricas": ["Chutes", "Chutes no Alvo", "Passes-Chave", "Expected Assists"],
    },
    "score_defesa": {
        "desc": "Solidez defensiva: sofrer poucas finalizações e poucos gols. Mede o resultado defensivo (chutes/gols sofridos), não o volume de desarmes — defender muito costuma indicar um time pressionado.",
        "metricas": ["Chutes Sofridos", "Chutes no Alvo Sofridos", "Gols Sofridos", "Jogos sem sofrer gol"],
    },
    "score_eficiencia": {
        "desc": "Conversão de oportunidades em gols: qualidade das finalizações.",
        "metricas": ["Precisão de Chute %", "Conversão de Gols %", "Passes-Chave"],
    },
    "score_controle": {
        "desc": "Domínio do jogo: posse, passes e criação de jogadas.",
        "metricas": ["Posse de Bola %", "Passes", "Precisão de Passes %", "Dribles"],
    },
    "score_forca_relativa": {
        "desc": "Força histórica via Rating Elo — cresce conforme os ratings se diferenciam ao longo do torneio.",
        "metricas": ["Rating Elo", "Qualidade dos adversários vencidos"],
    },
    "score_disciplina": {
        "desc": "Comportamento disciplinar: penaliza faltas, cartões amarelos e vermelhos.",
        "metricas": ["Faltas / jogo", "Amarelos / jogo", "Vermelhos / jogo"],
    },
}
score_info_json = json.dumps(SCORE_INFO, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Copa 2026 — Ranking Race</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  background: #060910;
  color: #e6edf3;
  font-family: 'Segoe UI', system-ui, sans-serif;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}}

/* ── HEADER ── */
header {{
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  padding: 0 20px;
  height: 44px;
  background: #0d1117;
  border-bottom: 1px solid #21262d;
  flex-shrink: 0;
  gap: 20px;
}}
.header-title {{
  font-size: 0.88rem;
  font-weight: 700;
  color: #58a6ff;
  white-space: nowrap;
  letter-spacing: 0.3px;
}}
.header-title span {{ color: #8b949e; font-weight: 400; font-size: 0.78rem; margin-left: 8px; }}

/* pesos centralizados */
.weights-row {{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}}
.w-pill {{
  position: relative;
  display: flex;
  align-items: center;
  gap: 5px;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 3px 9px;
  font-size: 0.7rem;
  color: #8b949e;
  white-space: nowrap;
  cursor: help;
}}
.w-pill:hover {{ border-color: #58a6ff; background: #1a2233; }}
.w-pill .w-name {{ color: #c8d3e0; font-weight: 600; }}
.w-pill .w-val  {{ color: #58a6ff; font-weight: 700; }}
/* tooltip do peso — abre PARA BAIXO (os pills ficam no topo da tela) */
.w-pill .w-tip {{
  display: none;
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 9px 12px;
  min-width: 200px;
  max-width: 280px;
  white-space: normal;
  z-index: 2000;
  box-shadow: 0 8px 24px rgba(0,0,0,0.8);
  pointer-events: none;
}}
.w-pill:hover .w-tip {{ display: block; }}
.w-tip-title {{ font-size: 0.68rem; font-weight: 700; color: #58a6ff; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 6px; }}
.w-tip-desc  {{ font-size: 0.72rem; color: #8b949e; line-height: 1.5; margin-bottom: 6px; }}
.w-tip-metrics {{ font-size: 0.7rem; color: #4ade80; }}
.w-tip-metrics span {{ display: inline-block; background: #1a2a1a; border-radius: 3px; padding: 1px 5px; margin: 1px 2px; }}

/* header direita: play + slider */
.header-player {{
  display: flex;
  align-items: center;
  gap: 8px;
}}

/* ── CONTROLS ── */
.controls {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 20px;
  background: #0d1117;
  border-bottom: 1px solid #21262d;
  flex-shrink: 0;
  flex-wrap: wrap;
}}
.btn {{
  background: #21262d;
  border: 1px solid #30363d;
  color: #e6edf3;
  padding: 5px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.82rem;
  transition: all 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
}}
.btn:hover {{ background: #30363d; border-color: #58a6ff; color: #58a6ff; }}
.btn.playing {{ background: #1f6feb; border-color: #58a6ff; }}

select {{
  background: #21262d;
  border: 1px solid #30363d;
  color: #e6edf3;
  padding: 5px 8px;
  border-radius: 6px;
  font-size: 0.82rem;
  cursor: pointer;
  flex-shrink: 0;
}}
select:focus {{ outline: none; border-color: #58a6ff; }}

/* metric select destaque */
#metricSelect {{
  border-color: #58a6ff44;
  color: #58a6ff;
  font-weight: 600;
}}
#metricSelect:focus {{ border-color: #58a6ff; }}

.slider-wrap {{
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 160px;
}}
.slider-label {{ font-size: 0.78rem; color: #8b949e; white-space: nowrap; }}
input[type=range] {{
  flex: 1;
  accent-color: #58a6ff;
  cursor: pointer;
  height: 4px;
}}

/* ── DOTS agrupados por fase ──
   Tamanho/espaçamento responsivos: escalam com a largura da tela via clamp().
   --dot e --dot-gap são as variáveis que controlam tudo. */
:root {{
  --dot: clamp(7px, 0.5vw, 12px);
  --dot-gap: clamp(3px, 0.28vw, 7px);
  --phase-gap: clamp(8px, 0.8vw, 20px);
}}
.dots-wrap {{
  display: flex;
  align-items: center;
  gap: 0;
  padding: 4px clamp(16px, 1.5vw, 28px) 2px;
  background: #0d1117;
  border-bottom: 1px solid #21262d;
  flex-shrink: 0;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: #30363d #0d1117;
}}
.dots-wrap::-webkit-scrollbar {{ height: 6px; }}
.dots-wrap::-webkit-scrollbar-thumb {{ background: #30363d; border-radius: 3px; }}
.dots-wrap::-webkit-scrollbar-thumb:hover {{ background: #484f58; }}

/* réguas por time (quando há 2+ cards abertos) */
#teamDotRows {{ display: flex; flex-direction: column; }}
.team-dot-row {{
  border-bottom: 1px solid #161b22;
  align-items: center;
}}
.team-dot-flag {{
  display: flex; align-items: center; gap: 5px;
  font-size: clamp(0.62rem, 0.7vw, 0.8rem); font-weight: 700;
  color: #c8d3e0; white-space: nowrap;
  padding-right: 10px; margin-right: 6px;
  border-right: 1px solid #21262d;
  position: sticky; left: 0; background: #0d1117;
  flex-shrink: 0; min-width: 120px;
}}
.team-label-row {{ border-bottom: 1px solid #21262d; padding-top: 2px; padding-bottom: 0; }}
.team-label-row .phase-group {{ padding-top: 2px; padding-bottom: 0; }}
.team-label-row .dot {{ height: 0 !important; border: 0 !important; }}

.phase-group {{
  display: flex;
  flex-direction: column;
  align-items: stretch;       /* label e dots ocupam a MESMA largura (a do mais largo) */
  padding: 5px var(--phase-gap) 5px var(--phase-gap);
  gap: 6px;
  flex-shrink: 0;
  border-right: 1px solid #21262d;   /* tracinho entre fases (inclui após a Final) */
}}

.phase-label {{
  font-size: clamp(0.6rem, 0.7vw, 0.78rem);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  white-space: nowrap;
  opacity: 0.8;
  text-align: center;         /* texto centralizado no container da fase */
}}
.phase-dots {{
  display: flex;
  gap: var(--dot-gap);
  flex-wrap: nowrap;          /* cada fase numa linha só */
  justify-content: center;    /* bolinhas centralizadas no container (largura = do texto) */
}}
.dot {{
  width: var(--dot); height: var(--dot);
  border-radius: 50%;
  transition: transform 0.2s, opacity 0.2s, box-shadow 0.2s;
  flex-shrink: 0;
  border: 2px solid transparent;
}}
/* já disputado/processado: pintado, clicável */
.dot-done {{ opacity: 0.85; cursor: pointer; }}
.dot-done:hover {{ opacity: 1; transform: scale(1.4); }}
/* ainda não disputado: vazio (só contorno) */
.dot-pending {{ opacity: 0.45; cursor: default; }}
/* dot "apagado" por filtro de seleção (jogo sem o time em foco):
   continua visível (contorno perceptível), só não se destaca */
.dot-faded {{ opacity: 0.4; }}
/* realce do PRIMEIRO (verde) e ÚLTIMO (dourado) jogo do time —
   sem scale (não desloca o layout); só cor + brilho */
.dot-first, .dot-last {{ opacity: 1; }}
.dot-first {{ box-shadow: 0 0 7px 1px #35c46fcc; }}
.dot-last  {{ box-shadow: 0 0 7px 1px #f5c542cc; }}
/* acontecendo agora: vermelho pulsante */
.dot-live {{
  opacity: 1; cursor: default;
  box-shadow: 0 0 0 0 #f8514999;
  animation: dotLivePulse 1.3s infinite;
}}
@keyframes dotLivePulse {{
  0%   {{ box-shadow: 0 0 0 0 #f8514999; }}
  70%  {{ box-shadow: 0 0 0 6px #f8514900; }}
  100% {{ box-shadow: 0 0 0 0 #f8514900; }}
}}
/* o jogo atualmente em tela: anel branco e maior */
/* jogo selecionado (em tela): cor própria (ciano) + maior + anel branco */
.dot.current {{
  opacity: 1;
  transform: scale(1.35);
  background: #2dd4ff !important;
  border-color: #fff !important;
  box-shadow: 0 0 9px 2px #2dd4ffcc;
  z-index: 2;
}}

/* ── MAIN LAYOUT ── */
.main {{
  display: flex;
  flex: 1;
  overflow: hidden;
}}

/* ── CHART ── */
.chart-area {{
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 12px 20px 10px;
  overflow: hidden;
  min-width: 0;
}}
.chart-header {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
  gap: 12px;
  flex-wrap: wrap;
  flex-shrink: 0;
}}
.frame-title {{
  font-size: 0.95rem;
  font-weight: 700;
  color: #e6edf3;
}}
.frame-sub {{
  font-size: 0.7rem;
  color: #8b949e;
  margin-top: 2px;
}}

.bars-viewport {{
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: #30363d #060910;
}}
#barsContainer {{
  position: relative;
  width: 100%;
}}

/* ── BAR ROW ── */
.bar-row {{
  position: absolute;
  left: 0; right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: top 0.55s cubic-bezier(0.4,0,0.2,1),
              opacity 0.35s ease;
  cursor: default;
}}
.bar-row.dimmed {{ opacity: 0.12; }}
.bar-row.selected .bar-track {{
  outline: 2px solid #58a6ff;
  outline-offset: 2px;
  border-radius: 5px;
}}
.bar-row.selected .bar-name {{
  color: #58a6ff;
  font-weight: 700;
}}

.bar-rank {{
  width: 26px;
  text-align: right;
  font-size: 0.78rem;
  color: #6b7280;
  font-weight: 700;
  flex-shrink: 0;
}}
.bar-rank.r1 {{ color: #f5c542; font-size: 0.92rem; }}
.bar-rank.r2 {{ color: #c0c0c0; }}
.bar-rank.r3 {{ color: #cd7f32; }}

.bar-flag {{
  font-size: 1.2rem;
  flex-shrink: 0;
  line-height: 1;
  width: 26px;
  text-align: center;
}}

.bar-name {{
  width: 148px;
  font-size: 0.83rem;
  color: #e6edf3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-shrink: 0;
  cursor: pointer;
  transition: color 0.2s;
  user-select: none;
}}
.bar-name:hover {{ color: #58a6ff; }}

/* bola de futebol ao lado do time que jogou neste jogo */
.match-badge {{
  display: inline-block;
  font-size: 0.78rem;
  margin-left: 6px;
  vertical-align: middle;
  line-height: 1;
}}

.bar-track {{
  flex: 1;
  background: #1e2433;
  border-radius: 5px;
  height: 30px;
  position: relative;
  overflow: visible;
  min-width: 0;
}}
.bar-fill {{
  height: 100%;
  border-radius: 5px;
  transition: width 0.55s cubic-bezier(0.4,0,0.2,1),
              background 0.45s ease;
  min-width: 3px;
}}

.bar-value {{
  position: absolute;
  right: -50px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 0.8rem;
  font-weight: 700;
  color: #e6edf3;
  white-space: nowrap;
  width: 46px;
  text-align: left;
}}

/* ── CARD (hover) — grid 2×2 ── */
.bar-tooltip {{
  display: none;
  position: fixed;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 12px;
  padding: 0;
  z-index: 500;
  box-shadow: 0 16px 48px rgba(0,0,0,0.9);
  pointer-events: auto;
  flex-direction: column;
  min-width: 700px;
  max-width: 800px;
}}
.tt-header {{
  padding: 11px 16px 9px;
  border-bottom: 1px solid #21262d;
  flex-shrink: 0;
}}
.tt-title {{
  color: #e6edf3;
  font-weight: 700;
  font-size: 0.96rem;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.tt-subtitle {{ color: #6b7280; font-size: 0.7rem; margin-top: 2px; }}
.tt-grid {{
  display: grid;
  grid-template-columns: 168px 210px repeat(4, 1fr);
}}
.tt-col {{
  border-right: 1px solid #21262d;
  border-bottom: 1px solid #21262d;
}}
.tt-col-scores    {{ grid-column: span 1; grid-row: span 2; border-bottom: none; }}
.tt-col-campanha  {{ grid-column: span 1; grid-row: span 2; border-bottom: none; border-right: 2px solid #30363d; }}
.tt-col-ataque    {{ grid-column: span 2; }}
.tt-col-defesa    {{ grid-column: span 2; border-right: none; }}
.tt-col-controle  {{ grid-column: span 2; border-bottom: none; }}
.tt-col-disciplina {{ grid-column: span 2; border-right: none; border-bottom: none; }}
.tt-col-title {{
  font-size: 0.63rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: #58a6ff;
  padding: 7px 12px 5px;
  border-bottom: 1px solid #21262d;
  white-space: nowrap;
}}
.tt-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 12px;
  gap: 8px;
  cursor: pointer;
  transition: background 0.1s;
}}
.tt-row:hover {{ background: #161b22; }}
.tt-row.active {{ background: #1a2d50; }}
.tt-row.active .tt-label {{ color: #c8d3e0; }}
.tt-row.active .tt-val {{ color: #58a6ff; }}
.tt-row.related {{ background: #1f2d1a; }}
.tt-row.related .tt-label {{ color: #86c98a; }}
.tt-row.related .tt-val {{ color: #4ade80; font-weight: 600; }}
.tt-row.related-indirect {{ background: #2a2510; }}
.tt-row.related-indirect .tt-label {{ color: #c9a84c; }}
.tt-row.related-indirect .tt-val {{ color: #f0c040; }}
.tt-legend {{
  display: flex; gap: 14px; padding: 6px 10px 5px;
  border-top: 1px solid #21262d; margin-top: 2px;
  font-size: 10px; color: #8b949e;
}}
.tt-legend-dot {{
  width: 8px; height: 8px; border-radius: 2px;
  display: inline-block; margin-right: 5px; flex-shrink: 0;
  position: relative; top: 1px;
}}
.tt-legend-item {{ display: flex; align-items: center; }}
.tt-label {{ color: #8b949e; font-size: 0.75rem; user-select: none; flex: 1; white-space: nowrap; }}
.tt-val {{ color: #e6edf3; font-weight: 700; font-size: 0.78rem; white-space: nowrap; }}
.tt-val.negative {{ color: #f85149; }}

/* valor + badge de posição no ranking daquele item */
.tt-valwrap {{ display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }}
.tt-rank {{
  font-size: 0.62rem; font-weight: 800; color: #8b949e;
  background: #21262d; border: 1px solid #30363d;
  border-radius: 4px; padding: 0 4px; min-width: 22px; text-align: center;
}}
.tt-rank.rk1 {{ color: #1b1b1b; background: #f5c542; border-color: #f5c542; }}
.tt-rank.rk2 {{ color: #1b1b1b; background: #c0c0c0; border-color: #c0c0c0; }}
.tt-rank.rk3 {{ color: #1b1b1b; background: #cd7f32; border-color: #cd7f32; }}

/* ── MODAL FIXO ── */
.modal-card {{
  position: fixed;
  z-index: 900;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 14px;
  box-shadow: 0 24px 64px rgba(0,0,0,0.95);
  width: 880px;
  max-width: 95vw;
  max-height: 88vh;
  overflow-y: auto;
  flex-direction: column;
  display: none;
}}
.modal-card.open {{ display: flex; }}
.modal-drag-bar {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 12px 9px 16px;
  border-bottom: 1px solid #21262d;
  cursor: grab;
  flex-shrink: 0;
  border-radius: 14px 14px 0 0;
  background: #111720;
}}
.modal-drag-bar:active {{ cursor: grabbing; }}
.modal-drag-label {{ font-size: 0.68rem; color: #6b7280; user-select: none; }}
/* cabeçalho (bandeira + nome + ranking) dentro da barra de arrastar */
.drag-header {{ display: flex; align-items: baseline; gap: 8px; min-width: 0; overflow: hidden; }}
.drag-flag {{ font-size: 1.1rem; flex-shrink: 0; }}
.drag-name {{ color: #e6edf3; font-weight: 700; font-size: 0.95rem; white-space: nowrap; }}
.drag-sub {{ color: #6b7280; font-size: 0.7rem; white-space: nowrap; }}
.modal-card-close {{
  background: none;
  border: none;
  color: #6b7280;
  font-size: 1.1rem;
  cursor: pointer;
  line-height: 1;
  padding: 2px 6px;
  border-radius: 4px;
}}
.modal-card-close:hover {{ color: #e6edf3; background: #21262d; }}

/* ── SIDEBAR ── */
.sidebar {{
  width: 190px;
  background: #0d1117;
  border-left: 1px solid #21262d;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}}
.sidebar-header {{
  padding: 12px 12px 8px;
  border-bottom: 1px solid #21262d;
  flex-shrink: 0;
}}
.sidebar-header h3 {{
  font-size: 0.68rem;
  color: #8b949e;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 5px;
}}
.sidebar-team {{
  font-size: 0.85rem;
  font-weight: 700;
  color: #58a6ff;
  min-height: 18px;
}}
.sidebar-body {{
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  scrollbar-width: thin;
  scrollbar-color: #30363d #0d1117;
}}
.history-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 7px;
  border-radius: 6px;
  margin-bottom: 3px;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
  font-size: 0.75rem;
  gap: 4px;
}}
.history-row:hover {{ background: #161b22; border-color: #30363d; }}
.history-row.current {{ background: #1f2937; border-color: #58a6ff; }}
.h-jogo {{ color: #6b7280; width: 24px; flex-shrink: 0; }}
.h-val {{ font-weight: 700; color: #e6edf3; width: 38px; text-align: right; flex-shrink: 0; }}
.h-rank {{ color: #e8c84a; font-size: 0.68rem; width: 28px; text-align: right; flex-shrink: 0; }}
.no-team {{ color: #6b7280; font-size: 0.78rem; font-style: italic; padding: 10px 12px; }}

/* ── METRIC LABEL ── */
.metric-label-bar {{
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 20px;
  background: #0a0e17;
  border-bottom: 1px solid #1a2030;
  flex-shrink: 0;
  font-size: 0.72rem;
  color: #8b949e;
}}
.metric-label-bar strong {{ color: #58a6ff; }}
.lb-tag {{
  background: #1a2a44;
  border: 1px solid #1f6feb44;
  border-radius: 4px;
  padding: 1px 7px;
  color: #58a6ff;
  font-weight: 600;
  font-size: 0.7rem;
}}
.lb-inv {{
  background: #2a1a1a;
  border: 1px solid #ef444444;
  border-radius: 4px;
  padding: 1px 7px;
  color: #ef4444;
  font-size: 0.68rem;
}}

/* ── TABS no header ── */
.header-left {{ display: flex; align-items: center; gap: 16px; min-width: 0; }}
.tabs {{ display: flex; gap: 2px; }}
.tab {{
  background: transparent; border: none; cursor: pointer;
  color: #8b949e; font-size: 0.8rem; font-weight: 600;
  padding: 4px 12px; border-radius: 6px; white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}}
.tab:hover {{ background: #161b22; color: #c9d1d9; }}
.tab.active {{ background: #1f6feb22; color: #58a6ff; }}

/* ── VIEW Seleções ── */
#viewTeams {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
.teams-toolbar {{
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 12px 20px; border-bottom: 1px solid #21262d; flex-shrink: 0;
}}
.teams-search {{
  background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
  color: #e6edf3; padding: 6px 12px; font-size: 0.82rem; width: 220px;
}}
.teams-search:focus {{ outline: none; border-color: #1f6feb; }}
.tb-field {{ display: flex; align-items: center; gap: 6px; font-size: 0.72rem; color: #6b7280; white-space: nowrap; }}
.tb-field select {{
  background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
  color: #e6edf3; padding: 5px 8px; font-size: 0.78rem;
}}
.tb-field select:focus {{ outline: none; border-color: #1f6feb; }}
.tb-dir {{ padding: 5px 9px; font-size: 0.85rem; }}
.tb-check {{ display: flex; align-items: center; gap: 5px; font-size: 0.74rem; color: #8b949e; cursor: pointer; }}
.tb-check input {{ accent-color: #1f6feb; cursor: pointer; }}
.teams-count {{ color: #6b7280; font-size: 0.74rem; }}
.teams-grid {{
  flex: 1; overflow-y: auto; padding: 18px 20px;
  display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px; align-content: start;
}}
.team-card {{
  background: #0d1117; border: 1px solid #21262d; border-radius: 14px;
  padding: 18px 20px; cursor: pointer;
  transition: border-color 0.15s, transform 0.1s, background 0.15s, box-shadow 0.15s;
}}
.team-card:hover {{
  border-color: #1f6feb; background: #11161f; transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(31,111,235,0.12);
}}
.tc-head {{ display: flex; align-items: center; gap: 14px; }}
.team-card .tc-flag {{ font-size: 2.9rem; line-height: 1; flex-shrink: 0; }}
.team-card .tc-info {{ min-width: 0; flex: 1; }}
.team-card .tc-name {{ font-weight: 800; font-size: 1.12rem; color: #e6edf3; line-height: 1.15; }}
.team-card .tc-sub {{ font-size: 0.74rem; color: #8b949e; margin-top: 3px; }}
.team-card .tc-rank {{
  font-size: 1.15rem; font-weight: 900; color: #58a6ff;
  background: #1f6feb18; border-radius: 8px; padding: 6px 11px; flex-shrink: 0;
}}
/* mini-stats no card */
.tc-stats {{
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;
  margin-top: 14px; padding-top: 14px; border-top: 1px solid #161b22;
}}
.tc-stat {{ text-align: center; }}
.tc-stat .v {{ font-size: 1.05rem; font-weight: 800; color: #e6edf3; font-variant-numeric: tabular-nums; }}
.tc-stat .v.geral {{ color: #58a6ff; }}
.tc-stat .l {{ font-size: 0.62rem; color: #6b7280; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.3px; }}
.tc-badges {{ display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap; }}
.tc-badge {{
  font-size: 0.64rem; font-weight: 600; color: #9ca3af;
  background: #161b22; border: 1px solid #21262d; border-radius: 5px; padding: 2px 7px;
}}
.team-card.tc-empty {{ opacity: 0.45; cursor: default; }}
.team-card.tc-empty:hover {{ border-color: #21262d; transform: none; background: #0d1117; box-shadow: none; }}

/* ── MODAL ── */
.modal-overlay {{
  position: fixed; inset: 0; background: rgba(1,4,9,0.78);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; padding: 24px; backdrop-filter: blur(2px);
}}
.modal {{
  background: #0d1117; border: 1px solid #30363d; border-radius: 14px;
  width: min(860px, 100%); max-height: 88vh; display: flex; flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.6);
}}
.modal-head {{
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid #21262d; flex-shrink: 0;
}}
.modal-title {{ display: flex; align-items: center; gap: 12px; font-size: 1.15rem; font-weight: 800; }}
.modal-flag {{ font-size: 1.9rem; line-height: 1; }}
.modal-rank {{
  font-size: 0.78rem; font-weight: 700; color: #58a6ff;
  background: #1f6feb18; border-radius: 6px; padding: 3px 9px;
}}
.modal-close {{
  background: transparent; border: none; color: #8b949e; cursor: pointer;
  font-size: 1.1rem; padding: 4px 8px; border-radius: 6px;
}}
.modal-close:hover {{ background: #21262d; color: #e6edf3; }}
.modal-tabs {{
  display: flex; gap: 2px; padding: 8px 20px 0; border-bottom: 1px solid #21262d; flex-shrink: 0;
}}
.modal-tab {{
  background: transparent; border: none; border-bottom: 2px solid transparent; cursor: pointer;
  color: #8b949e; font-size: 0.8rem; font-weight: 600; padding: 8px 12px; transition: color 0.15s;
}}
.modal-tab:hover {{ color: #c9d1d9; }}
.modal-tab.active {{ color: #58a6ff; border-bottom-color: #58a6ff; }}
.modal-body {{ overflow-y: auto; padding: 18px 20px; }}

/* blocos do modal */
.md-scores {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(130px,1fr)); gap: 10px; }}
.md-score {{ background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 10px 12px; }}
.md-score .ms-val {{ font-size: 1.35rem; font-weight: 800; color: #e6edf3; }}
.md-score .ms-lbl {{ font-size: 0.7rem; color: #8b949e; margin-top: 2px; }}
.md-score.ms-geral {{ border-color: #1f6feb55; background: #1f6feb12; }}

table.md-table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
table.md-table th {{
  text-align: left; color: #8b949e; font-weight: 600; font-size: 0.7rem;
  text-transform: uppercase; letter-spacing: 0.4px; padding: 6px 8px; border-bottom: 1px solid #21262d;
}}
table.md-table td {{ padding: 7px 8px; border-bottom: 1px solid #161b22; }}
table.md-table tr:hover td {{ background: #11161f; }}
table.md-table td.num {{ text-align: center; font-variant-numeric: tabular-nums; }}
.md-pname {{ font-weight: 600; color: #e6edf3; }}

.md-game {{
  background: #161b22; border: 1px solid #21262d; border-radius: 8px;
  padding: 10px 14px; margin-bottom: 8px;
}}
.md-game-top {{ display: flex; align-items: center; gap: 10px; }}
.md-res {{
  font-weight: 800; width: 22px; height: 22px; border-radius: 5px;
  display: inline-flex; align-items: center; justify-content: center; font-size: 0.74rem; flex-shrink: 0;
}}
.md-res.V {{ background: #22c55e22; color: #22c55e; }}
.md-res.E {{ background: #6b728022; color: #9ca3af; }}
.md-res.D {{ background: #ef444422; color: #ef4444; }}
.md-game-score {{ font-weight: 800; font-size: 0.95rem; }}
.md-game-opp {{ flex: 1; }}
.md-game-meta {{ color: #6b7280; font-size: 0.72rem; }}
.md-formation {{ font-size: 0.72rem; color: #58a6ff; margin: 8px 0 4px; font-weight: 600; }}
.md-xi {{ display: flex; flex-wrap: wrap; gap: 5px; }}
.md-xi .pl {{ background: #0d1117; border: 1px solid #21262d; border-radius: 5px; padding: 2px 7px; font-size: 0.72rem; }}
.md-xi .pl .pn {{ color: #6b7280; margin-right: 4px; }}
.md-xi.subs .pl {{ opacity: 0.7; }}
.md-sub-label {{ font-size: 0.68rem; color: #6b7280; margin: 8px 0 4px; text-transform: uppercase; letter-spacing: 0.4px; }}
.md-empty {{ color: #6b7280; font-size: 0.82rem; padding: 12px 0; }}
</style>
</head>
<body>

<header>
  <div class="header-left">
    <div class="header-title">Copa 2026</div>
    <nav class="tabs">
      <button class="tab active" data-tab="race" onclick="switchTab('race')">Ranking Race</button>
      <button class="tab" data-tab="teams" onclick="switchTab('teams')">Seleções</button>
    </nav>
  </div>
  <div class="weights-row" id="weightsPills"></div>
  <div class="header-player">
    <button class="btn" id="btnPlay" onclick="togglePlay()">▶ Play</button>
    <span class="slider-label" id="sliderLabel" style="font-size:0.75rem;color:#8b949e;white-space:nowrap">Jogo 1</span>
    <input type="range" id="jogoSlider" min="1" value="1" style="width:160px" oninput="goToJogo(+this.value)">
    <select id="speedSelect" onchange="updateSpeed()" style="font-size:0.75rem;padding:3px 6px">
      <option value="1400">Lenta</option>
      <option value="900" selected>Normal</option>
      <option value="450">Rápida</option>
    </select>
  </div>
</header>

<!-- ══ VIEW: Ranking Race (original) ══ -->
<div id="viewRace">

<div class="controls">
  <span style="font-size:0.72rem;color:#6b7280;white-space:nowrap">Métrica:</span>
  <select id="metricSelect" onchange="changeMetric(this.value)"></select>
  <button class="btn" id="btnDir" onclick="toggleDir()">↓ Maior primeiro</button>
  <div style="width:1px;height:18px;background:#30363d;margin:0 4px"></div>
  <span style="font-size:0.72rem;color:#6b7280;white-space:nowrap">Destacar:</span>
  <select id="teamSelect" onchange="selectTeam(this.value)">
    <option value="">— time —</option>
  </select>
  <button class="btn" onclick="selectTeam('')" title="Limpar">✕</button>
  <div style="flex:1"></div>
  <span class="lb-tag" id="metricLabelTag" style="font-size:0.72rem">Geral</span>
  <span id="metricDirTag" style="color:#6b7280;font-size:0.7rem"></span>
</div>

<div class="dots-wrap" id="progressDots"></div>
<div id="teamDotRows"></div>

<div class="main">
  <div class="chart-area">
    <div class="chart-header">
      <div>
        <div class="frame-title" id="frameTitle">—</div>
        <div class="frame-sub" id="frameSub" style="display:none"></div>
      </div>
    </div>
    <div class="bars-viewport">
      <div id="barsContainer"></div>
    </div>
  </div>

  <div class="sidebar">
    <div class="sidebar-header">
      <h3>Trajetória</h3>
      <div class="sidebar-team" id="sidebarTeam">—</div>
    </div>
    <div class="sidebar-body" id="sidebarBody">
      <div class="no-team">Clique em um time para ver sua trajetória</div>
    </div>
  </div>
</div>

</div><!-- /viewRace -->

<!-- ══ VIEW: Seleções (grade de países) ══ -->
<div id="viewTeams" style="display:none">
  <div class="teams-toolbar">
    <input type="text" id="teamSearch" class="teams-search" placeholder="Buscar seleção…" oninput="renderTeamsGrid()">

    <label class="tb-field">Ordenar
      <select id="teamSort" onchange="renderTeamsGrid()"></select>
    </label>
    <button class="btn tb-dir" id="teamSortDir" onclick="toggleTeamSortDir()" title="Inverter ordem">↓</button>

    <label class="tb-field">Grupo
      <select id="filterGroup" onchange="renderTeamsGrid()"><option value="">Todos</option></select>
    </label>
    <label class="tb-field">Confederação
      <select id="filterConfed" onchange="renderTeamsGrid()"><option value="">Todas</option></select>
    </label>
    <label class="tb-field">Fase
      <select id="filterStage" onchange="renderTeamsGrid()"><option value="">Todas</option></select>
    </label>
    <label class="tb-check"><input type="checkbox" id="filterPlayed" onchange="renderTeamsGrid()"> Só com jogos</label>

    <div style="flex:1"></div>
    <button class="btn" onclick="resetTeamFilters()" title="Limpar filtros">✕ Limpar</button>
    <span class="teams-count" id="teamsCount"></span>
  </div>
  <div class="teams-grid" id="teamsGrid"></div>
</div>

<!-- ══ MODAL: detalhe da seleção ══ -->
<div id="teamModal" class="modal-overlay" style="display:none" onclick="if(event.target===this)closeTeamModal()">
  <div class="modal" role="dialog" aria-modal="true">
    <div class="modal-head">
      <div class="modal-title">
        <span class="modal-flag" id="modalFlag"></span>
        <span id="modalTeam">—</span>
        <span class="modal-rank" id="modalRank"></span>
      </div>
      <button class="modal-close" onclick="closeTeamModal()" title="Fechar (Esc)">✕</button>
    </div>
    <nav class="modal-tabs" id="modalTabs"></nav>
    <div class="modal-body" id="modalBody"></div>
  </div>
</div>

<!-- Cards flutuantes gerados dinamicamente pelo JS -->

<script>
const DATA = {data_json};
const ALL_TEAMS = {all_teams_json};
const TEAM_FLAGS = {team_flags_json};
const TEAMS_DETAIL = {teams_detail_json};
const TEAMS_GRID = Object.keys(TEAMS_DETAIL);
const METRIC_GROUPS = {metric_groups_json};
const LOWER_IS_BETTER = new Set({lower_is_better_json});

const jogos = Object.keys(DATA).map(Number).sort((a,b)=>a-b);
const N = jogos.length;
const ROW_H = 44;

let currentJogo = jogos[jogos.length - 1];
let selectedTeam = '';
let currentMetric = 'score_geral';
let sortDir = 'desc';   // 'desc' = maior primeiro, 'asc' = menor primeiro
let playing = false;
let timer = null;
let speed = 900;

// ── colour scale: rank 1 = green→red dependendo de sortDir
// asc (menor primeiro) = rank 1 é o pior → vermelho no topo
function rankColor(rank, total) {{
  const t = (rank - 1) / Math.max(total - 1, 1);
  // se asc: inverte — rank 1 fica vermelho (menor não é necessariamente melhor)
  const tt = sortDir === 'asc' ? 1 - t : t;
  let r, g, b;
  if (tt < 0.5) {{
    const s = tt * 2;
    r = Math.round(0x22 + s * (0xea - 0x22));
    g = Math.round(0xc5 + s * (0xb3 - 0xc5));
    b = Math.round(0x5e + s * (0x08 - 0x5e));
  }} else {{
    const s = (tt - 0.5) * 2;
    r = Math.round(0xea + s * (0xef - 0xea));
    g = Math.round(0xb3 + s * (0x44 - 0xb3));
    b = Math.round(0x08 + s * (0x44 - 0x08));
  }}
  return `rgb(${{r}},${{g}},${{b}})`;
}}

function rankGlow(rank, total) {{
  return `0 0 14px 2px ${{rankColor(rank, total)}}55`;
}}

// ── init metric select (grouped)
const metricSel = document.getElementById('metricSelect');
METRIC_GROUPS.forEach(([groupLabel, , options]) => {{
  const og = document.createElement('optgroup');
  og.label = groupLabel;
  options.forEach(([value, label]) => {{
    const o = document.createElement('option');
    o.value = value; o.textContent = label;
    if (value === 'score_geral') o.selected = true;
    og.appendChild(o);
  }});
  metricSel.appendChild(og);
}});

// ── flat map: metric key → label
const METRIC_LABELS = {{}};
METRIC_GROUPS.forEach(([, , opts]) => opts.forEach(([k, l]) => METRIC_LABELS[k] = l));

const METRIC_RELATIONS = {metric_relations_json};
const METRIC_RELATIONS_INDIRECT = {metric_relations_indirect_json};

// ── init slider
const slider = document.getElementById('jogoSlider');
slider.max = N;

// ── dots agrupados por fase
const SNAPSHOT_META = {snapshot_meta_json_var};
const dotRefs = {{}};  // n → dot element (só jogos processados/navegáveis)
const allDots = [];   // todos os dots: {{ el, meta }} — p/ filtrar por seleção

const dotsEl = document.getElementById('progressDots');

// Ordens cronológicas dos jogos de um time (0-based): todas, 1ª e última.
function teamGameOrders(team) {{
  return SNAPSHOT_META
    .filter(m => m.teams && m.teams.indexOf(team) !== -1)
    .map(m => m.order);
}}
function teamDebutOrder(team) {{
  const o = teamGameOrders(team);
  return o.length ? o[0] : Infinity;
}}

// Pinta um dot. Com foco (debutOrder), os jogos ANTES da estreia ficam apagados.
// marker='first'|'last' dá um anel colorido no 1º/último jogo do time.
function paintDot(el, m, color, debutOrder, marker) {{
  el.classList.remove('dot-done', 'dot-pending', 'dot-live', 'dot-faded',
                      'dot-first', 'dot-last');

  if (debutOrder != null && m.order < debutOrder) {{
    el.classList.add('dot-pending', 'dot-faded');
    el.style.background = 'transparent';
    el.style.borderColor = color + '66';
    return;
  }}
  el.classList.add('dot-' + m.status);
  if (m.status === 'done') {{
    el.style.background = color;
    el.style.borderColor = 'transparent';
  }} else if (m.status === 'live') {{
    el.style.background = '#f85149';
    el.style.borderColor = 'transparent';
  }} else {{
    el.style.background = 'transparent';
    el.style.borderColor = color + '66';
  }}
  // realce do primeiro / último jogo do time
  if (marker === 'first') {{ el.classList.add('dot-first'); el.style.background = '#35c46f'; el.style.borderColor = '#fff'; }}
  if (marker === 'last')  {{ el.classList.add('dot-last');  el.style.background = '#f5c542'; el.style.borderColor = '#fff'; }}
}}

// Aplica/limpa o filtro de time na régua PRINCIPAL. focusTeam=null → limpa.
function applyDotTeamFilter(focusTeam) {{
  if (!focusTeam) {{
    allDots.forEach(({{ el, color, meta }}) => paintDot(el, meta, color, null, null));
    return;
  }}
  const debut = teamDebutOrder(focusTeam);
  const played = SNAPSHOT_META
    .filter(m => m.teams && m.teams.indexOf(focusTeam) !== -1 && m.status !== 'pending')
    .map(m => m.order);
  const firstO = played.length ? played[0] : null;
  const lastO  = played.length ? played[played.length - 1] : null;
  allDots.forEach(({{ el, color, meta }}) => {{
    let marker = null;
    if (meta.order === firstO && firstO !== lastO) marker = 'first';
    else if (meta.order === lastO) marker = 'last';
    paintDot(el, meta, color, debut, marker);
  }});
}}

// Constrói uma régua de dots para um time, com bandeira no início.
// Reaproveita o agrupamento por fase (phaseGroups) e o paintDot.
function buildTeamDotRow(team) {{
  const wrap = document.createElement('div');
  wrap.className = 'dots-wrap team-dot-row';

  const flag = document.createElement('div');
  flag.className = 'team-dot-flag';
  flag.textContent = (TEAM_FLAGS[team] || '🏳️') + ' ' + team;
  wrap.appendChild(flag);

  const orders = teamGameOrders(team);
  const debut = orders.length ? orders[0] : Infinity;
  // 1º e último jogo JÁ DISPUTADOS do time (done/live), p/ realce
  const playedOrders = SNAPSHOT_META
    .filter(m => m.teams && m.teams.indexOf(team) !== -1 && m.status !== 'pending')
    .map(m => m.order);
  const firstO = playedOrders.length ? playedOrders[0] : null;
  const lastO  = playedOrders.length ? playedOrders[playedOrders.length - 1] : null;

  phaseGroups.forEach(pg => {{
    const grp = document.createElement('div');
    grp.className = 'phase-group';
    const dotsRow = document.createElement('div');
    dotsRow.className = 'phase-dots';
    pg.items.forEach(m => {{
      const d = document.createElement('div');
      d.className = 'dot';
      let marker = null;
      if (m.order === firstO && firstO !== lastO) marker = 'first';
      else if (m.order === lastO && lastO !== firstO) marker = 'last';
      else if (m.order === firstO && firstO === lastO) marker = 'last'; // único jogo
      paintDot(d, m, pg.color, debut, marker);
      if (m.n != null) {{
        d.onclick = () => goToJogo(m.n);
        d.dataset.n = m.n;
        if (m.n === currentJogo) d.classList.add('current');
      }}
      dotsRow.appendChild(d);
    }});
    grp.appendChild(dotsRow);
    wrap.appendChild(grp);
  }});
  return wrap;
}}

// Cabeçalho com os rótulos das fases (alinhado às réguas por time).
function buildPhaseLabelRow() {{
  const wrap = document.createElement('div');
  wrap.className = 'dots-wrap team-dot-row team-label-row';

  const spacer = document.createElement('div');
  spacer.className = 'team-dot-flag';   // mesma largura da coluna da bandeira
  spacer.textContent = '';
  wrap.appendChild(spacer);

  phaseGroups.forEach(pg => {{
    const grp = document.createElement('div');
    grp.className = 'phase-group';
    const lbl = document.createElement('div');
    lbl.className = 'phase-label';
    lbl.textContent = pg.label;
    lbl.style.color = pg.color;
    grp.appendChild(lbl);
    // espaçador invisível com a mesma largura dos dots, p/ alinhar
    const dotsRow = document.createElement('div');
    dotsRow.className = 'phase-dots';
    pg.items.forEach(() => {{
      const d = document.createElement('div');
      d.className = 'dot';
      d.style.visibility = 'hidden';
      dotsRow.appendChild(d);
    }});
    grp.appendChild(dotsRow);
    wrap.appendChild(grp);
  }});
  return wrap;
}}

// Sincroniza as réguas conforme os cards/seleção:
//  • 0-1 time em foco → só a régua principal (filtrada)
//  • 2+ cards abertos → ESCONDE a principal; cabeçalho de fases + 1 régua por time
function syncDotRows() {{
  const mainRow = document.getElementById('progressDots');
  const teamRows = document.getElementById('teamDotRows');
  teamRows.innerHTML = '';
  const cards = [...openCards.keys()];

  if (cards.length >= 2) {{
    mainRow.style.display = 'none';           // esconde a régua principal
    teamRows.appendChild(buildPhaseLabelRow());
    cards.forEach(t => teamRows.appendChild(buildTeamDotRow(t)));
  }} else {{
    mainRow.style.display = '';               // mostra a principal
    const focus = cards.length === 1 ? cards[0] : (selectedTeam || null);
    applyDotTeamFilter(focus);
  }}
}}

// agrupa snapshots por label de fase
const phaseGroups = [];
SNAPSHOT_META.forEach(m => {{
  const last = phaseGroups[phaseGroups.length - 1];
  if (!last || last.label !== m.label) {{
    phaseGroups.push({{ label: m.label, color: m.color, items: [] }});
  }}
  phaseGroups[phaseGroups.length - 1].items.push(m);
}});

phaseGroups.forEach(pg => {{
  const grp = document.createElement('div');
  grp.className = 'phase-group';

  const lbl = document.createElement('div');
  lbl.className = 'phase-label';
  lbl.textContent = pg.label;
  lbl.style.color = pg.color;
  grp.appendChild(lbl);

  const dotsRow = document.createElement('div');
  dotsRow.className = 'phase-dots';

  pg.items.forEach(m => {{
    const d = document.createElement('div');
    d.className = 'dot';   // classe base (tamanho/forma); paintDot adiciona o status
    const id = m.match_id.replace('copa_2026_jogo_', 'Jogo ');
    d.title = m.status === 'live' ? `${{id}} — AO VIVO`
            : m.status === 'done' ? `${{id}} — clique para ver`
            : `${{id}} — ainda não disputado`;
    // só navega para jogos já processados (têm snapshot n)
    if (m.n != null) d.onclick = () => goToJogo(m.n);
    else d.style.cursor = 'default';
    dotsRow.appendChild(d);
    if (m.n != null) dotRefs[m.n] = {{ el: d, color: pg.color }};
    allDots.push({{ el: d, color: pg.color, meta: m }});
    paintDot(d, m, pg.color, null);   // estado base (sem filtro de time)
  }});

  grp.appendChild(dotsRow);
  dotsEl.appendChild(grp);
}});

// ── team select
const teamSel = document.getElementById('teamSelect');
ALL_TEAMS.forEach(t => {{
  const o = document.createElement('option');
  o.value = t; o.textContent = `${{TEAM_FLAGS[t] || '🏳️'}} ${{t}}`;
  teamSel.appendChild(o);
}});

// ── bar DOM pool
// Armazena referências diretas ao DOM — sem IDs com acentos que quebram getElementById
const pool = {{}};  // team → {{ row, rankEl, nameEl, fillEl, valEl, tipEl }}

function getRow(team) {{
  if (!pool[team]) {{
    const row = document.createElement('div');
    row.className = 'bar-row';
    row.dataset.team = team;

    const rankEl = document.createElement('div');
    rankEl.className = 'bar-rank';

    const flagEl = document.createElement('div');
    flagEl.className = 'bar-flag';

    const nameEl = document.createElement('div');
    nameEl.className = 'bar-name';
    nameEl.textContent = team;
    nameEl.style.cursor = 'pointer';
    nameEl.addEventListener('click', e => {{ e.stopPropagation(); if (!selectedTeam) openModal(team); }});

    const trackEl = document.createElement('div');
    trackEl.className = 'bar-track';

    const fillEl = document.createElement('div');
    fillEl.className = 'bar-fill';

    const valEl = document.createElement('div');
    valEl.className = 'bar-value';

    trackEl.appendChild(fillEl);
    trackEl.appendChild(valEl);
    row.appendChild(rankEl);
    row.appendChild(flagEl);
    row.appendChild(nameEl);
    row.appendChild(trackEl);

    document.getElementById('barsContainer').appendChild(row);
    pool[team] = {{ row, rankEl, flagEl, nameEl, fillEl, valEl }};
  }}
  return pool[team];
}}

// ── sort teams: sortDir controla a direção manual do usuário
function sortedTeams(frameTeams) {{
  // Ordena pela QUANTIDADE bruta: 'desc' = maior primeiro, 'asc' = menor primeiro.
  const asc = sortDir === 'asc';
  return [...frameTeams].sort((a, b) => {{
    const va = a[currentMetric] ?? (asc ? Infinity : -Infinity);
    const vb = b[currentMetric] ?? (asc ? Infinity : -Infinity);
    return asc ? va - vb : vb - va;
  }});
}}

function toggleDir() {{
  sortDir = sortDir === 'desc' ? 'asc' : 'desc';
  const btn = document.getElementById('btnDir');
  btn.textContent = sortDir === 'desc' ? '↓ Maior primeiro' : '↑ Menor primeiro';
  document.getElementById('metricDirTag').textContent =
    sortDir === 'desc' ? '↓ maior → menor' : '↑ menor → maior';
  renderJogo(currentJogo);
}}

// aproveitamento e clean_sheet_rate estão em fração (0–1); posse_media já é %
const PERCENT_FRAC = new Set(['aproveitamento', 'precisao_chute', 'precisao_passes']);
const PERCENT_DIRECT = new Set(['posse_media']);

function formatVal(v, metric) {{
  if (v === null || v === undefined) return '—';
  if (v === 0) return '0';
  if (PERCENT_FRAC.has(metric)) return (v * 100).toFixed(0) + '%';
  if (PERCENT_DIRECT.has(metric)) return v.toFixed(1) + '%';
  if (Number.isInteger(v) || Math.abs(v - Math.round(v)) < 0.005) return String(Math.round(v));
  return v.toFixed(1);
}}

function renderJogo(n) {{
  const frame = DATA[n];
  if (!frame) return;

  slider.value = n;
  document.getElementById('sliderLabel').textContent = `Jogo ${{n}} / ${{N}}`;
  // título único, bandeiras ao redor do placar: Casa 🏠 placar 🚩 Fora
  document.getElementById('frameTitle').innerHTML =
    `<span style="color:#8b949e;font-weight:400">Após o Jogo ${{frame.match_n}} ·</span> ` +
    `${{frame.home}} ${{frame.home_flag}} ` +
    `<span style="color:#58a6ff">${{frame.score}}</span> ` +
    `${{frame.away_flag}} ${{frame.away}}`;
  document.getElementById('frameSub').textContent = '';

  // weights pills com tooltip explicativo
  const p = frame.pesos || {{}};
  const SCORE_INFO = {score_info_json};
  const pillDefs = [
    ['Resultado',     'score_resultado',    p.score_resultado],
    ['Ataque',        'score_ataque',       p.score_ataque],
    ['Defesa',        'score_defesa',       p.score_defesa],
    ['Eficiência',    'score_eficiencia',   p.score_eficiencia],
    ['Controle',      'score_controle',     p.score_controle],
    ['Força Relativa','score_forca_relativa',p.score_forca_relativa],
    ['Disciplina',    'score_disciplina',   p.score_disciplina],
  ];
  const pillsHtml = pillDefs.filter(([,,v]) => v !== undefined).map(([label, key, v]) => {{
    const info = SCORE_INFO[key] || {{}};
    const metricas = (info.metricas || []).map(m => `<span>${{m}}</span>`).join('');
    return `<div class="w-pill">
      <span class="w-name">${{label}}</span>
      <span class="w-val">${{v}}%</span>
      <div class="w-tip">
        <div class="w-tip-title">${{label}}</div>
        <div class="w-tip-desc">${{info.desc || ''}}</div>
        ${{metricas ? `<div class="w-tip-metrics">${{metricas}}</div>` : ''}}
      </div>
    </div>`;
  }}).join('');
  document.getElementById('weightsPills').innerHTML = pillsHtml || '<span style="font-size:0.7rem;color:#6b7280">Pesos carregando…</span>';

  // dots: marca o snapshot em tela como "current" (régua principal + réguas por time).
  Object.entries(dotRefs).forEach(([j, ref]) => {{
    ref.el.classList.toggle('current', Number(j) === n);
  }});
  document.querySelectorAll('#teamDotRows .dot[data-n]').forEach(d => {{
    d.classList.toggle('current', Number(d.dataset.n) === n);
  }});

  // sort by chosen metric
  const teams = sortedTeams(frame.teams);
  const total = teams.length;

  // largura da barra:
  //  • scores 0–100 → a barra É o valor (58.7 → 58.7% da barra), proporcional de verdade
  //  • estatísticas brutas (gols, passes…) → proporcional ao MÁXIMO (0..máx),
  //    não min-max esticado (que faz o menor virar ~0% e o maior 100% mesmo
  //    quando a diferença real é pequena)
  const vals = teams.map(t => t[currentMetric]).filter(v => v !== null && v !== undefined);
  const isScore = currentMetric.startsWith('score_') ||
                  PERCENT_FRAC.has(currentMetric) || PERCENT_DIRECT.has(currentMetric);
  const maxV = Math.max(...vals, 0);
  const maxRef = PERCENT_FRAC.has(currentMetric) ? 1
               : (PERCENT_DIRECT.has(currentMetric) || currentMetric.startsWith('score_')) ? 100
               : (maxV || 1);

  // hide all — pool armazena {{ row, rankEl, nameEl, fillEl, valEl, tipEl }}
  Object.values(pool).forEach(p => {{ p.row.style.opacity = '0'; p.row.style.pointerEvents = 'none'; }});

  const containerH = total * (ROW_H + 4);
  document.getElementById('barsContainer').style.height = containerH + 'px';

  teams.forEach((t, i) => {{
    const rank = i + 1;
    const els = getRow(t.team);
    const color = rankColor(rank, total);
    const v = t[currentMetric];

    let pct;
    if (v === null || v === undefined) {{
      pct = 0;
    }} else {{
      // proporcional ao valor real: score 0–100 → % direto; bruto → fração do máximo
      pct = (Math.abs(v) / maxRef * 100).toFixed(2);
    }}
    if (+pct > 100) pct = 100;
    if (+pct < 3 && v !== null && v !== 0) pct = 3;

    // posição e visibilidade
    els.row.style.top = `${{i * (ROW_H + 4)}}px`;
    els.row.style.height = `${{ROW_H}}px`;
    const isInCard = openCards.has(t.team);
    const isActive = isInCard || t.team === selectedTeam;
    // cards abertos: sem dimming, todos visíveis e clicáveis — só o destaque diferencia
    // selectedTeam sem cards: comportamento original de dimming
    const dimOthers = !openCards.size && selectedTeam && !isActive;
    els.row.style.opacity = dimOthers ? '0.12' : '1';
    els.row.style.pointerEvents = 'auto';
    els.row.classList.toggle('selected', isActive);

    // rank
    els.rankEl.textContent = rank;
    els.rankEl.className = 'bar-rank' + (rank===1?' r1':rank===2?' r2':rank===3?' r3':'');

    // bandeira
    els.flagEl.textContent = t.flag || '';

    // nome + bola de futebol (indica que o time jogou neste jogo)
    els.nameEl.textContent = t.team;
    if (t.playing) {{
      const badge = document.createElement('span');
      badge.className = 'match-badge';
      badge.textContent = '⚽';
      badge.title = 'Jogou neste jogo';
      els.nameEl.appendChild(badge);
    }}

    // barra
    els.fillEl.style.width = pct + '%';
    els.fillEl.style.background = color;
    els.fillEl.style.boxShadow = isActive ? rankGlow(rank, total) : 'none';

    els.valEl.textContent = formatVal(v, currentMetric);

    // o card detalhado é montado sob demanda em buildCardBody (clique no nome)
  }});

  renderSidebar(n);
  refreshAllCards();
}}

function renderSidebar(n) {{
  const nameEl = document.getElementById('sidebarTeam');
  const bodyEl = document.getElementById('sidebarBody');

  if (!selectedTeam) {{
    nameEl.textContent = '—';
    bodyEl.innerHTML = '<div class="no-team">Clique em um time para ver sua trajetória</div>';
    return;
  }}

  nameEl.textContent = selectedTeam;

  const vals = jogos
    .map(j => {{ const e = DATA[j].teams.find(t => t.team === selectedTeam); return e ? e[currentMetric] : null; }})
    .filter(v => v !== null);
  const _maxV = Math.max(...vals, 0);
  const maxRef = PERCENT_FRAC.has(currentMetric) ? 1
               : (PERCENT_DIRECT.has(currentMetric) || currentMetric.startsWith('score_')) ? 100
               : (_maxV || 1);

  bodyEl.innerHTML = '';
  jogos.forEach(j => {{
    const entry = DATA[j].teams.find(t => t.team === selectedTeam);
    if (!entry) return;
    const sorted = sortedTeams(DATA[j].teams);
    const rank = sorted.findIndex(t => t.team === selectedTeam) + 1;
    const total = sorted.length;
    const color = rankColor(rank, total);
    const v = entry[currentMetric];
    const pct = v !== null ? Math.min(100, Math.abs(v) / maxRef * 100).toFixed(1) : 0;

    const row = document.createElement('div');
    row.className = 'history-row' + (j === n ? ' current' : '');
    row.innerHTML = `
      <span class="h-jogo">J${{j}}</span>
      <div style="flex:1;margin:0 5px;height:4px;background:#21262d;border-radius:2px;position:relative;">
        <div style="width:${{pct}}%;height:100%;background:${{color}};border-radius:2px;transition:width 0.4s;"></div>
      </div>
      <span class="h-val">${{formatVal(v, currentMetric)}}</span>
      <span class="h-rank">#${{rank}}</span>
    `;
    row.onclick = () => goToJogo(j);
    bodyEl.appendChild(row);
  }});

  const cur = bodyEl.querySelector('.current');
  if (cur) cur.scrollIntoView({{block: 'nearest'}});
}}

function changeMetric(metric) {{
  currentMetric = metric;
  const label = METRIC_LABELS[metric] || metric;
  document.getElementById('metricLabelTag').textContent = label.replace(' ↓','');
  document.getElementById('metricDirTag').textContent =
    sortDir === 'desc' ? '↓ maior → menor' : '↑ menor → maior';
  renderJogo(currentJogo);
}}

function selectTeam(t) {{
  selectedTeam = t;
  teamSel.value = t;
  syncDotRows();
  renderJogo(currentJogo);
}}

// ── Cards flutuantes arrastáveis (N times) ──
const openCards = new Map();  // team → {{ el, contentEl }}

// Posição do time numa métrica, ORDENADA PELA QUANTIDADE (igual à barra):
// por padrão maior valor = 1°. 'asc' inverte (menor = 1°).
// Usa "competition ranking" — empates dividem a mesma posição.
// `dir` controla a direção: 'desc' (maior=1°) ou 'asc' (menor=1°).
function metricRank(key, teams, team, dir) {{
  const asc = dir === 'asc';
  const vals = teams
    .map(x => ({{ team: x.team, v: x[key] }}))
    .filter(x => x.v !== null && x.v !== undefined);
  const me = vals.find(x => x.team === team);
  if (!me) return null;
  // quantos estão "à frente" na ordenação atual (mesma lógica da barra)
  const ahead = vals.filter(x => asc ? x.v < me.v : x.v > me.v).length;
  const tiedWith = vals.filter(x => x.v === me.v && x.team !== team).length;
  return {{ rank: ahead + 1, total: vals.length, tied: tiedWith > 0 }};
}}

function rankClass(rank) {{
  if (rank === 1) return ' rk1';
  if (rank === 2) return ' rk2';
  if (rank === 3) return ' rk3';
  return '';
}}

function buildCardBody(team) {{
  const frame = DATA[currentJogo];
  const t = frame.teams.find(x => x.team === team);
  if (!t) return '';
  const allTeams = frame.teams;
  // "#N no ranking" = posição no ranking GERAL (score_geral, maior=melhor),
  // independente da métrica/direção selecionada na tela.
  const gr = metricRank('score_geral', allTeams, team, 'desc');
  const rank = gr ? gr.rank : '?';
  const rankTie = gr && gr.tied ? '=' : '';
  const related  = new Set(METRIC_RELATIONS[currentMetric] || []);
  const indirect = new Set(METRIC_RELATIONS_INDIRECT[currentMetric] || []);
  let colsHtml = '';
  METRIC_GROUPS.forEach(([groupLabel, colCls, metrics]) => {{
    colsHtml += `<div class="tt-col ${{colCls}}"><div class="tt-col-title">${{groupLabel}}</div>`;
    metrics.forEach(([key, label]) => {{
      const val = t[key];
      const isActive   = key === currentMetric;
      const isRelated  = !isActive && related.has(key);
      const isIndirect = !isActive && !isRelated && indirect.has(key);
      const cls = isActive ? ' active' : isRelated ? ' related' : isIndirect ? ' related-indirect' : '';
      const isNeg = val !== null && val !== undefined && val < 0;
      // badge segue a MESMA direção da barra (sortDir): inverte junto com o botão
      const mr = metricRank(key, allTeams, team, sortDir);
      // medalha (ouro/prata/bronze) só para posição ISOLADA; empate fica neutro com "="
      const rkCls = mr && !mr.tied ? rankClass(mr.rank) : '';
      const tie = mr && mr.tied ? '=' : '';
      const rkBadge = mr ? `<span class="tt-rank${{rkCls}}">${{mr.rank}}°${{tie}}</span>` : '';
      colsHtml += `<div class="tt-row${{cls}}" data-metric="${{key}}">
        <span class="tt-label">${{label}}</span>
        <span class="tt-valwrap">
          <span class="tt-val${{isNeg ? ' negative' : ''}}">${{formatVal(val, key)}}</span>
          ${{rkBadge}}
        </span>
      </div>`;
    }});
    colsHtml += '</div>';
  }});
  const hasRelated  = related.size > 0;
  const hasIndirect = indirect.size > 0;
  const legendHtml  = (hasRelated || hasIndirect) ? `<div class="tt-legend">
    ${{hasRelated  ? '<span class="tt-legend-item"><span class="tt-legend-dot" style="background:#4ade80"></span>entra no cálculo</span>' : ''}}
    ${{hasIndirect ? '<span class="tt-legend-item"><span class="tt-legend-dot" style="background:#f0c040"></span>correlação indireta</span>' : ''}}
  </div>` : '';
  // o cabeçalho (bandeira/nome/ranking) vai na barra de arrastar, não aqui
  return `<div class="tt-grid">${{colsHtml}}</div>${{legendHtml}}`;
}}

// Cabeçalho do card (bandeira + nome + posição), exibido na barra de arrastar.
function buildCardHeader(team) {{
  const frame = DATA[currentJogo];
  const t = frame.teams.find(x => x.team === team);
  if (!t) return '';
  const gr = metricRank('score_geral', frame.teams, team, 'desc');
  const rank = gr ? gr.rank : '?';
  const rankTie = gr && gr.tied ? '=' : '';
  return `<span class="drag-flag">${{t.flag || ''}}</span>
    <span class="drag-name">${{t.team}}</span>
    <span class="drag-sub">#${{rank}}${{rankTie}} no ranking · ${{t.jogos}} jogo${{t.jogos !== 1 ? 's' : ''}}</span>`;
}}

function makeDraggable(card, dragBar) {{
  let ox = 0, oy = 0, mx = 0, my = 0;
  dragBar.addEventListener('mousedown', e => {{
    e.preventDefault();
    mx = e.clientX; my = e.clientY;
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }});
  function onMove(e) {{
    const dx = e.clientX - mx, dy = e.clientY - my;
    mx = e.clientX; my = e.clientY;
    card.style.left = (card.offsetLeft + dx) + 'px';
    card.style.top  = (card.offsetTop  + dy) + 'px';
  }}
  function onUp() {{
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  }}
}}

function openModal(team) {{
  if (openCards.has(team)) {{ closeModalCard(team); return; }}

  const card = document.createElement('div');
  card.className = 'modal-card open';

  // posição inicial: cascateia os cards
  const offset = openCards.size * 32;
  const left = Math.max(20, (window.innerWidth - 720) / 2 + offset);
  const top  = Math.max(60, (window.innerHeight - 520) / 2 + offset);
  card.style.left = left + 'px';
  card.style.top  = top  + 'px';

  const dragBar = document.createElement('div');
  dragBar.className = 'modal-drag-bar';
  const headerEl = document.createElement('div');
  headerEl.className = 'drag-header';
  headerEl.innerHTML = buildCardHeader(team);
  dragBar.appendChild(headerEl);
  const closeBtn = document.createElement('button');
  closeBtn.className = 'modal-card-close';
  closeBtn.textContent = '✕';
  closeBtn.onclick = () => closeModalCard(team);
  dragBar.appendChild(closeBtn);

  const contentEl = document.createElement('div');
  contentEl.innerHTML = buildCardBody(team);

  card.appendChild(dragBar);
  card.appendChild(contentEl);
  document.body.appendChild(card);
  makeDraggable(card, dragBar);

  // clique numa métrica → muda filtro e atualiza todos os cards
  card.addEventListener('click', e => {{
    const row = e.target.closest('.tt-row[data-metric]');
    if (!row) return;
    const metric = row.dataset.metric;
    document.getElementById('metricSelect').value = metric;
    changeMetric(metric);
  }});

  openCards.set(team, {{ el: card, contentEl, headerEl }});
  syncDotRows();
  renderJogo(currentJogo);
}}

function closeModalCard(team) {{
  const c = openCards.get(team);
  if (!c) return;
  c.el.remove();
  openCards.delete(team);
  syncDotRows();
  renderJogo(currentJogo);
}}

function refreshAllCards() {{
  openCards.forEach(({{ contentEl, headerEl }}, team) => {{
    contentEl.innerHTML = buildCardBody(team);
    if (headerEl) headerEl.innerHTML = buildCardHeader(team);
  }});
}}

document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') {{
    [...openCards.keys()].forEach(closeModalCard);
  }}
}});

function goToJogo(n) {{
  currentJogo = n;
  renderJogo(n);
}}

function updateSpeed() {{
  speed = +document.getElementById('speedSelect').value;
  if (playing) {{ clearInterval(timer); startPlay(); }}
}}

function startPlay() {{
  timer = setInterval(() => {{
    if (currentJogo >= N) {{ stopPlay(); return; }}
    goToJogo(currentJogo + 1);
  }}, speed);
}}

function stopPlay() {{
  clearInterval(timer);
  playing = false;
  const btn = document.getElementById('btnPlay');
  btn.textContent = '▶ Play';
  btn.classList.remove('playing');
}}

function togglePlay() {{
  if (playing) {{
    stopPlay();
  }} else {{
    playing = true;
    const btn = document.getElementById('btnPlay');
    btn.textContent = '⏸ Pause';
    btn.classList.add('playing');
    if (currentJogo >= N) goToJogo(1);
    startPlay();
  }}
}}

// ── O card só abre ao CLICAR no nome do país (openModal). Sem hover.

// ── Clique numa linha do card → muda métrica ativa
document.addEventListener('click', e => {{
  const metricRow = e.target.closest('.tt-row[data-metric]');
  if (metricRow) {{
    const metric = metricRow.dataset.metric;
    document.getElementById('metricSelect').value = metric;
    changeMetric(metric);
  }}
}});

// ── Clique na barra: toggle seleção do time (bloqueado se há cards abertos)
document.getElementById('barsContainer').addEventListener('click', e => {{
  if (openCards.size > 0) return;
  const row = e.target.closest('.bar-row');
  if (!row) return;
  const team = row.dataset.team;
  selectTeam(selectedTeam === team ? '' : team);
}});

document.addEventListener('keydown', e => {{
  // Esc fecha o modal de seleção, em qualquer aba
  if (e.key === 'Escape' && document.getElementById('teamModal').style.display !== 'none') {{
    closeTeamModal(); return;
  }}
  // controles da race só valem na aba race, com modal fechado e fora de inputs
  if (activeTab !== 'race') return;
  if (document.getElementById('teamModal').style.display !== 'none') return;
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.key === ' ') {{ e.preventDefault(); togglePlay(); }}
  if (e.key === 'ArrowRight' && currentJogo < N) goToJogo(currentJogo + 1);
  if (e.key === 'ArrowLeft' && currentJogo > 1) goToJogo(currentJogo - 1);
}});

// ══════════════════════════════════════════════════════════════════════════
// Abas (Ranking Race / Seleções) + grade de países + modal de detalhe
// ══════════════════════════════════════════════════════════════════════════
let activeTab = 'race';

function switchTab(tab) {{
  activeTab = tab;
  document.querySelectorAll('.tab').forEach(t =>
    t.classList.toggle('active', t.dataset.tab === tab));
  document.getElementById('viewRace').style.display = tab === 'race' ? '' : 'none';
  document.getElementById('viewTeams').style.display = tab === 'teams' ? 'flex' : 'none';
  // o player só faz sentido na race
  document.querySelector('.header-player').style.visibility = tab === 'race' ? 'visible' : 'hidden';
  if (tab === 'teams') {{
    if (playing) togglePlay();
    if (!_teamsInit) {{ initTeamsControls(); _teamsInit = true; }}
    renderTeamsGrid();
  }}
}}
let _teamsInit = false;

function _norm(s) {{
  return (s || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
}}

const STAGE_LABELS_TEAMS = {{
  'Fase de Grupos': 'Fase de Grupos', 'Oitavas': 'Oitavas', 'Quartas': 'Quartas',
  'Semifinais': 'Semifinais', 'Disputa 3º Lugar': 'Disputa 3º Lugar', 'Final': 'Final',
}};

// opções de ordenação: chave especial + acessor do valor por seleção
const TEAM_SORTS = [
  {{ k: 'rank',       label: 'Ranking (#)',     get: d => d.rank, asc: true }},
  {{ k: 'alpha',      label: 'Alfabética (A–Z)', get: d => null,  asc: true }},
  {{ k: 'score_geral',        label: 'Score Geral',    get: d => (d.scores||{{}}).score_geral }},
  {{ k: 'score_resultado',    label: 'Score Resultado',get: d => (d.scores||{{}}).score_resultado }},
  {{ k: 'score_ataque',       label: 'Score Ataque',   get: d => (d.scores||{{}}).score_ataque }},
  {{ k: 'score_defesa',       label: 'Score Defesa',   get: d => (d.scores||{{}}).score_defesa }},
  {{ k: 'score_eficiencia',   label: 'Score Eficiência',get: d => (d.scores||{{}}).score_eficiencia }},
  {{ k: 'score_controle',     label: 'Score Controle', get: d => (d.scores||{{}}).score_controle }},
  {{ k: 'score_forca_relativa',label:'Score Força Rel.',get: d => (d.scores||{{}}).score_forca_relativa }},
  {{ k: 'score_disciplina',   label: 'Score Disciplina',get: d => (d.scores||{{}}).score_disciplina }},
  {{ k: 'pontos',     label: 'Pontos',          get: d => (d.campanha||{{}}).pontos }},
  {{ k: 'gols_pro',   label: 'Gols Marcados',   get: d => (d.campanha||{{}}).gols_pro }},
  {{ k: 'saldo_gols', label: 'Saldo de Gols',   get: d => (d.campanha||{{}}).saldo_gols }},
  {{ k: 'elo_rating', label: 'Rating Elo',      get: d => (d.campanha||{{}}).elo_rating }},
  {{ k: 'n_jogos',    label: 'Jogos disputados',get: d => d.n_jogos }},
];

let teamSortDir = null;  // null = usa o default da opção; senão 'asc'/'desc'

function initTeamsControls() {{
  // ordenação
  const sortSel = document.getElementById('teamSort');
  sortSel.innerHTML = TEAM_SORTS.map(s => `<option value="${{s.k}}">${{s.label}}</option>`).join('');
  // grupos
  const groups = [...new Set(Object.values(TEAMS_DETAIL).map(d => d.group).filter(Boolean))].sort();
  document.getElementById('filterGroup').innerHTML =
    '<option value="">Todos</option>' + groups.map(g => `<option value="${{g}}">Grupo ${{g}}</option>`).join('');
  // confederações
  const confeds = [...new Set(Object.values(TEAMS_DETAIL).map(d => d.confed).filter(Boolean))].sort();
  document.getElementById('filterConfed').innerHTML =
    '<option value="">Todas</option>' + confeds.map(c => `<option value="${{c}}">${{c}}</option>`).join('');
  // fases
  const stages = [...new Set(Object.values(TEAMS_DETAIL).map(d => d.stage_now).filter(Boolean))];
  document.getElementById('filterStage').innerHTML =
    '<option value="">Todas</option>' + stages.map(s => `<option value="${{s}}">${{s}}</option>`).join('');
}}

function toggleTeamSortDir() {{
  const cur = _effectiveSortDir();
  teamSortDir = cur === 'asc' ? 'desc' : 'asc';
  renderTeamsGrid();
}}

function _effectiveSortDir() {{
  if (teamSortDir) return teamSortDir;
  const s = TEAM_SORTS.find(x => x.k === document.getElementById('teamSort').value) || TEAM_SORTS[0];
  return s.asc ? 'asc' : 'desc';  // default: ranking/alpha ascendente, scores descendente
}}

function resetTeamFilters() {{
  document.getElementById('teamSearch').value = '';
  document.getElementById('teamSort').value = 'rank';
  document.getElementById('filterGroup').value = '';
  document.getElementById('filterConfed').value = '';
  document.getElementById('filterStage').value = '';
  document.getElementById('filterPlayed').checked = false;
  teamSortDir = null;
  renderTeamsGrid();
}}

function renderTeamsGrid() {{
  const grid = document.getElementById('teamsGrid');
  const q = _norm(document.getElementById('teamSearch').value.trim());
  const sortKey = document.getElementById('teamSort').value || 'rank';
  const fGroup = document.getElementById('filterGroup').value;
  const fConfed = document.getElementById('filterConfed').value;
  const fStage = document.getElementById('filterStage').value;
  const fPlayed = document.getElementById('filterPlayed').checked;
  const sortDef = TEAM_SORTS.find(s => s.k === sortKey) || TEAM_SORTS[0];
  const dir = _effectiveSortDir();
  document.getElementById('teamSortDir').textContent = dir === 'asc' ? '↑' : '↓';

  // filtra — usa TODAS as seleções da Copa (inclui as que ainda não jogaram)
  let teams = TEAMS_GRID.filter(t => {{
    const d = TEAMS_DETAIL[t] || {{}};
    if (q && !_norm(t).includes(q)) return false;
    if (fGroup && d.group !== fGroup) return false;
    if (fConfed && d.confed !== fConfed) return false;
    if (fStage && d.stage_now !== fStage) return false;
    if (fPlayed && (d.n_jogos || 0) === 0) return false;
    return true;
  }});

  // ordena
  teams.sort((a, b) => {{
    const da = TEAMS_DETAIL[a] || {{}}, db = TEAMS_DETAIL[b] || {{}};
    if (sortKey === 'alpha') {{
      const c = a.localeCompare(b, 'pt-BR');
      return dir === 'asc' ? c : -c;
    }}
    let va = sortDef.get(da), vb = sortDef.get(db);
    // valores ausentes sempre no fim, independentemente da direção
    const na = (va == null), nb = (vb == null);
    if (na && nb) return a.localeCompare(b, 'pt-BR');
    if (na) return 1;
    if (nb) return -1;
    if (va === vb) return a.localeCompare(b, 'pt-BR');
    return dir === 'asc' ? va - vb : vb - va;
  }});

  document.getElementById('teamsCount').textContent =
    teams.length + ' de ' + TEAMS_GRID.length + ' seleções';

  grid.innerHTML = teams.map(t => {{
    const d = TEAMS_DETAIL[t] || {{}};
    const flag = d.flag || TEAM_FLAGS[t] || '🏳️';
    const nj = d.n_jogos || 0;
    const empty = nj === 0;
    const rankBadge = d.rank != null ? `<span class="tc-rank">#${{d.rank}}</span>` : '';
    const sub = empty ? 'sem jogos ainda · ' + (d.group ? 'Grupo ' + d.group : '')
      : nj + (nj === 1 ? ' jogo' : ' jogos') + ' · ' + (d.players ? d.players.length : 0) + ' jogadores';

    const sc = d.scores || {{}}, cp = d.campanha || {{}};
    const fmt = v => v == null ? '—' : v;
    const stats = empty ? '' : `<div class="tc-stats">
      <div class="tc-stat"><div class="v geral">${{sc.score_geral != null ? sc.score_geral.toFixed(1) : '—'}}</div><div class="l">Score</div></div>
      <div class="tc-stat"><div class="v">${{fmt(cp.pontos)}}</div><div class="l">Pts</div></div>
      <div class="tc-stat"><div class="v">${{fmt(cp.gols_pro)}}</div><div class="l">Gols</div></div>
      <div class="tc-stat"><div class="v">${{cp.saldo_gols != null ? (cp.saldo_gols > 0 ? '+' + cp.saldo_gols : cp.saldo_gols) : '—'}}</div><div class="l">Saldo</div></div>
    </div>`;

    const badges = [
      d.group ? `<span class="tc-badge">Grupo ${{d.group}}</span>` : '',
      d.confed ? `<span class="tc-badge">${{d.confed}}</span>` : '',
      d.stage_now ? `<span class="tc-badge">${{d.stage_now}}</span>` : '',
    ].join('');

    return `<div class="team-card${{empty ? ' tc-empty' : ''}}" ${{empty ? '' : `onclick="openTeamModal('${{t.replace(/'/g, "\\\\'")}}')"`}}>
      <div class="tc-head">
        <span class="tc-flag">${{flag}}</span>
        <div class="tc-info">
          <div class="tc-name">${{t}}</div>
          <div class="tc-sub">${{sub}}</div>
        </div>
        ${{rankBadge}}
      </div>
      ${{badges ? `<div class="tc-badges">${{badges}}</div>` : ''}}
      ${{stats}}
    </div>`;
  }}).join('');
}}

let modalTeam = null;
let modalTab = 'scores';

function openTeamModal(team) {{
  const d = TEAMS_DETAIL[team];
  if (!d) return;
  modalTeam = team;
  modalTab = 'scores';
  document.getElementById('modalFlag').textContent = d.flag || '🏳️';
  document.getElementById('modalTeam').textContent = team;
  document.getElementById('modalRank').textContent = d.rank != null ? ('#' + d.rank + ' no ranking') : '';
  const tabs = [
    ['scores', 'Resumo'],
    ['jogos', 'Jogos (' + (d.jogos ? d.jogos.length : 0) + ')'],
    ['elenco', 'Elenco (' + (d.players ? d.players.length : 0) + ')'],
    ['escalacoes', 'Escalações'],
  ];
  document.getElementById('modalTabs').innerHTML = tabs.map(([k, l]) =>
    `<button class="modal-tab${{k === 'scores' ? ' active' : ''}}" data-mt="${{k}}" onclick="switchModalTab('${{k}}')">${{l}}</button>`
  ).join('');
  renderModalBody();
  document.getElementById('teamModal').style.display = 'flex';
}}

function closeTeamModal() {{
  document.getElementById('teamModal').style.display = 'none';
  modalTeam = null;
}}

function switchModalTab(t) {{
  modalTab = t;
  document.querySelectorAll('.modal-tab').forEach(b =>
    b.classList.toggle('active', b.dataset.mt === t));
  renderModalBody();
}}

function _scoreColor(v) {{
  if (v == null) return '#8b949e';
  const t = Math.max(0, Math.min(1, v / 100));
  const r = Math.round(0xea + (0x22 - 0xea) * t);
  const g = Math.round(0x55 + (0xc5 - 0x55) * t);
  const b = Math.round(0x44 + (0x5e - 0x44) * t);
  return `rgb(${{r}},${{g}},${{b}})`;
}}

function renderModalBody() {{
  const d = TEAMS_DETAIL[modalTeam];
  const body = document.getElementById('modalBody');
  if (!d) {{ body.innerHTML = ''; return; }}

  if (modalTab === 'scores') {{
    const labels = d.score_labels || {{}};
    const sc = d.scores || {{}};
    const keys = Object.keys(labels);
    if (!keys.length) {{ body.innerHTML = '<div class="md-empty">Sem scores calculados ainda.</div>'; return; }}
    body.innerHTML = '<div class="md-scores">' + keys.map(k => {{
      const v = sc[k];
      const cls = k === 'score_geral' ? ' ms-geral' : '';
      return `<div class="md-score${{cls}}">
        <div class="ms-val" style="color:${{_scoreColor(v)}}">${{v != null ? v.toFixed(1) : '—'}}</div>
        <div class="ms-lbl">${{labels[k]}}</div>
      </div>`;
    }}).join('') + '</div>';
    return;
  }}

  if (modalTab === 'jogos') {{
    if (!d.jogos || !d.jogos.length) {{ body.innerHTML = '<div class="md-empty">Nenhum jogo disputado ainda.</div>'; return; }}
    body.innerHTML = d.jogos.map(g => {{
      const local = g.home ? 'casa' : 'fora';
      const placar = (g.gf != null && g.ga != null) ? `${{g.gf}} – ${{g.ga}}` : '—';
      return `<div class="md-game">
        <div class="md-game-top">
          <span class="md-res ${{g.res}}">${{g.res}}</span>
          <span class="md-game-score">${{placar}}</span>
          <span class="md-game-opp">vs ${{g.opp_flag}} <b>${{g.opp}}</b> <span class="md-game-meta">(${{local}})</span></span>
          <span class="md-game-meta">${{g.stage}} · ${{g.date}}</span>
        </div>
      </div>`;
    }}).join('');
    return;
  }}

  if (modalTab === 'elenco') {{
    if (!d.players || !d.players.length) {{ body.innerHTML = '<div class="md-empty">Sem dados de jogadores.</div>'; return; }}
    body.innerHTML = `<table class="md-table">
      <thead><tr>
        <th>Jogador</th><th class="num">J</th><th class="num">G</th><th class="num">A</th>
        <th class="num">Chutes</th><th class="num">No alvo</th>
        <th class="num">🟨</th><th class="num">🟥</th><th class="num">Defesas</th>
      </tr></thead><tbody>` + d.players.map(p => `<tr>
        <td class="md-pname">${{p.name}}</td>
        <td class="num">${{p.jogos ?? '—'}}</td>
        <td class="num">${{p.gols || 0}}</td>
        <td class="num">${{p.assist || 0}}</td>
        <td class="num">${{p.chutes ?? '—'}}</td>
        <td class="num">${{p.no_alvo ?? '—'}}</td>
        <td class="num">${{p.amarelos || 0}}</td>
        <td class="num">${{p.vermelhos || 0}}</td>
        <td class="num">${{p.defesas || 0}}</td>
      </tr>`).join('') + '</tbody></table>';
    return;
  }}

  if (modalTab === 'escalacoes') {{
    const withLineup = (d.jogos || []).filter(g => g.starters && g.starters.length);
    if (!withLineup.length) {{ body.innerHTML = '<div class="md-empty">Sem escalações registradas.</div>'; return; }}
    body.innerHTML = withLineup.map(g => {{
      const xi = g.starters.map(p =>
        `<span class="pl"><span class="pn">${{p.num ?? ''}}</span>${{p.name}}</span>`).join('');
      const subs = (g.subs || []).map(p =>
        `<span class="pl"><span class="pn">${{p.num ?? ''}}</span>${{p.name}}</span>`).join('');
      return `<div class="md-game">
        <div class="md-game-top">
          <span class="md-game-opp">vs ${{g.opp_flag}} <b>${{g.opp}}</b></span>
          <span class="md-game-meta">${{g.stage}} · ${{g.date}}</span>
        </div>
        <div class="md-formation">Formação: ${{g.formation || '—'}}</div>
        <div class="md-xi">${{xi}}</div>
        ${{subs ? `<div class="md-sub-label">Reservas</div><div class="md-xi subs">${{subs}}</div>` : ''}}
      </div>`;
    }}).join('');
    return;
  }}
}}

goToJogo(jogos[jogos.length - 1]);
</script>
</body>
</html>"""

OUTPUT.write_text(html, encoding="utf-8")
print(f"Gerado: {OUTPUT}")
