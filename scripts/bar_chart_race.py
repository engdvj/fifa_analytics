"""
Bar chart race — ranking de seleções jogo a jogo (Copa 2026)
Gera reports/tournament/ranking_race.html
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import yaml

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
    # estilo de jogo (eixos descritivos 0-100, 50 = média do torneio)
    "estilo_posse": "estilo_posse",
    "estilo_pressao": "estilo_pressao",
    "estilo_verticalidade": "estilo_verticalidade",
    "estilo_largura": "estilo_largura",
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
        # estilo_jogo é o rótulo textual (não numérico) — vai no cabeçalho do modal
        estilo = row.get("estilo_jogo")
        entry["estilo_jogo"] = str(estilo) if estilo is not None and not pd.isna(estilo) else None
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
_events = _read_optional(Path("data/gold/fact_events/canonical_events.parquet"))
_tstats = _read_optional(Path("data/gold/fact_team_match_stats/canonical_team_stats.parquet"))
_commentary = _read_optional(Path("data/gold/fact_commentary/canonical_commentary.parquet"))


def _strip_name_cols(df: pd.DataFrame, cols: tuple[str, ...]) -> pd.DataFrame:
    """Normaliza nomes de jogador (tira espaços nas pontas). Fontes às vezes trazem
    'Gavi ', 'Raphinha ' etc., o que quebra o match por nome entre lineup, eventos,
    substituições e cartões — destaque/troca não casava. Limpa na raiz."""
    if df.empty:
        return df
    for c in cols:
        if c in df.columns:
            # não checar dtype==object: colunas pyarrow são dtype 'str', não object,
            # e seriam puladas. map() lida com qualquer backend de string.
            df[c] = df[c].map(lambda v: v.strip() if isinstance(v, str) else v)
    return df


_p365 = _read_optional(Path("data/gold/fact_player_match_stats/365scores.parquet"))

_lineups = _strip_name_cols(_lineups, ("player_name",))
_pstats = _strip_name_cols(_pstats, ("player_name",))
_events = _strip_name_cols(_events, ("player", "related_player"))
_commentary = _strip_name_cols(_commentary, ("player", "participants"))
_p365 = _strip_name_cols(_p365, ("player_name",))

import re as _re
import unicodedata as _ud


def _name_key(s) -> str:
    """Chave de nome sem acento/caixa, p/ casar 365scores (sem match_id) com canonical."""
    if not isinstance(s, str):
        return ""
    return _ud.normalize("NFKD", s).encode("ASCII", "ignore").decode().lower().strip()


def _num0(v):
    try:
        return None if v is None or pd.isna(v) else (int(v) if float(v) == int(float(v)) else round(float(v), 2))
    except (TypeError, ValueError):
        return None


def _player_stats_for(mid: str, team: str, date: str) -> dict:
    """Stats por jogador deste jogo: canonical (ESPN, por match_id) + 365scores
    (rating/xA/passes, casado por nome normalizado). Retorna {nome → dict de stats}."""
    out = {}
    if not _pstats.empty:
        cps = _pstats[(_pstats["match_id"] == mid) & (_pstats["team"] == team)]
        for _, r in cps.iterrows():
            nm = r.get("player_name")
            if not nm:
                continue
            out[nm] = {
                "goals": _num0(r.get("goals")), "assists": _num0(r.get("assists")),
                "shots": _num0(r.get("shots")), "on_target": _num0(r.get("shots_on_target")),
                "saves": _num0(r.get("saves")),
                "fouls_committed": _num0(r.get("fouls_committed")), "fouls_drawn": _num0(r.get("fouls_drawn")),
                "offsides": _num0(r.get("offsides")),
                "yellow": _num0(r.get("yellow_cards")), "red": _num0(r.get("red_cards")),
            }
    # enriquecimento 365scores (rating, minutos, xA, key passes, % passes) por nome+time
    if not _p365.empty:
        s365 = _p365[(_p365["team"] == team)]
        by_key = {_name_key(r.get("player_name")): r for _, r in s365.iterrows()}
        for nm, st in out.items():
            r = by_key.get(_name_key(nm))
            if r is None:
                continue
            st["rating"] = _num0(r.get("rating"))
            st["minutes"] = _num0(r.get("minutes"))
            st["xa"] = _num0(r.get("expected_assists"))
            st["key_passes"] = _num0(r.get("key_passes"))
            ap, pc = _num0(r.get("accurate_passes")), _num0(r.get("passes"))
            st["pass_acc"] = round(ap / pc * 100) if ap and pc else None
    return out

def _subs_for(match_id: str, team: str) -> list[dict]:
    """Substituições de um time num jogo, do fact_commentary (ESPN).
    Texto 'X replaces Y' → entra=X, sai=Y. Retorna [{minute, in, out, reason}]."""
    if _commentary.empty or "play_type" not in _commentary.columns:
        return []
    sub = _commentary[
        (_commentary["match_id"] == match_id)
        & (_commentary["play_type"] == "substitution")
        & (_commentary["team"] == team)
    ]
    out = []
    for _, r in sub.sort_values("minute_sort" if "minute_sort" in sub.columns else "minute").iterrows():
        txt = str(r.get("text") or "")
        mt = _re.match(r"Substitution,.*?\.\s*(.+?)\s+replaces\s+(.+?)(\s+because[^.]*)?\.?\s*$", txt)
        if mt:
            entra, saiu, reason = mt.group(1).strip(), mt.group(2).strip(), mt.group(3)
        else:
            parts = [p.strip() for p in str(r.get("participants") or "").split(",")]
            entra = parts[0] if parts else None
            saiu = parts[1] if len(parts) > 1 else None
            reason = None
        if not entra and not saiu:
            continue
        out.append({
            "minute": str(r.get("minute") or ""),
            "in": entra, "out": saiu,
            "reason": "lesão" if reason and "injur" in reason.lower() else None,
        })
    return out

# Narrativa ("A história do jogo") — lê o fragmento markdown de cada jogo, sem o
# marcador HTML e o título "## A historia do jogo".
def _read_story(match_id: str) -> str | None:
    p = Path("reports/fragments") / match_id / "01b_story.md"
    if not p.exists():
        return None
    txt = p.read_text(encoding="utf-8")
    lines = [
        ln for ln in txt.splitlines()
        if not ln.strip().startswith("<!--") and not ln.strip().startswith("## ")
    ]
    return "\n".join(lines).strip() or None


# Rótulos de tipo de evento → símbolo para a linha do tempo
_EVENT_LABEL = {
    "gol": ("⚽", "Gol"),
    "gol_penalti": ("⚽", "Gol (pênalti)"),
    "gol_contra": ("🥅", "Gol contra"),
    "cartao_amarelo": ("🟨", "Cartão amarelo"),
    "cartao_vermelho": ("🟥", "Cartão vermelho"),
    "substituicao": ("🔄", "Substituição"),
}

# Estatísticas de time a comparar no detalhe do jogo: (coluna, rótulo, formato)
# formato: "num" = número cru | "pct100" = já em 0-100 | "ratio" = razão calculada (×100)
# "ratio" usa (col_num / col_den) — precisão de passe = passes certos / total de passes.
_MATCH_STAT_ROWS = [
    ("possession", "Posse de bola", "pct100"),
    ("shots", "Finalizações", "num"),
    ("shots_on_target", "No alvo", "num"),
    ("corners", "Escanteios", "num"),
    ("fouls", "Faltas", "num"),
    (("accurate_passes", "passes"), "Precisão de passe", "ratio"),
    ("offsides", "Impedimentos", "num"),
]

# Infos curadas das seleções (títulos, técnico, histórico) — config/teams_info.yaml
_info_path = Path("config/teams_info.yaml")
TEAMS_INFO = (yaml.safe_load(_info_path.read_text(encoding="utf-8")) or {}).get("teams", {}) if _info_path.exists() else {}

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


# Posição horizontal (x: 0=esquerda, 100=direita) a partir do código de posição.
# O sufixo -L/-R e prefixos L/R indicam o lado; centro fica em ~50.
def _pos_x_hint(position: str | None) -> float | None:
    if not position:
        return None
    p = position.upper()
    if p.endswith("-L") or p.startswith("L"):
        return 25.0
    if p.endswith("-R") or p.startswith("R"):
        return 75.0
    if p in ("CD", "CM", "AM", "DM", "CF", "M", "F", "G", "SW"):
        return 50.0
    return None


# "Altura" tática de cada código de posição: menor = mais defensivo (perto do gol),
# maior = mais ofensivo. Usado para agrupar os jogadores nas linhas da formação.
_POS_DEPTH = {
    "G": 0,
    "SW": 1, "CD": 2, "CD-L": 2, "CD-R": 2, "LB": 2, "RB": 2,
    "DM": 3,
    "CM": 4, "CM-L": 4, "CM-R": 4, "LM": 4, "RM": 4, "M": 4,
    "AM": 5, "AM-L": 5, "AM-R": 5,
    "LF": 6, "RF": 6, "CF-L": 6, "CF-R": 6, "F": 6,
}


def _build_pitch(starters: list[dict], formation: str | None) -> list[dict]:
    """Deriva coordenadas (x,y) de cada titular para desenhar o campo.

    y: 8 (goleiro, fundo) → 92 (atacantes, topo). x: 0..100 (esq→dir).
    Agrupa os jogadores em linhas pela profundidade tática da position (não pela
    ordem do array, que é por camisa) e distribui cada linha conforme a formation."""
    if not formation or not starters:
        return []
    try:
        line_counts = [int(n) for n in formation.split("-")]
    except ValueError:
        return []
    if sum(line_counts) != 10:  # formação descreve os 10 de linha (sem o goleiro)
        return []

    gk = [p for p in starters if (p.get("pos") or "").upper() == "G"]
    field = [p for p in starters if (p.get("pos") or "").upper() != "G"]
    if len(field) != sum(line_counts):
        return []

    # ordena os jogadores de linha por profundidade tática (defensivo → ofensivo)
    field_sorted = sorted(field, key=lambda p: _POS_DEPTH.get((p.get("pos") or "").upper(), 4))

    n_lines = len(line_counts)
    pitch = []
    if gk:
        pitch.append({**gk[0], "x": 50.0, "y": 8.0})

    idx = 0
    for li, count in enumerate(line_counts):
        y = 24 + li * (68 / max(n_lines - 1, 1)) if n_lines > 1 else 50
        linha = field_sorted[idx: idx + count]
        idx += count
        # ordena a linha esquerda→direita pela dica de lado da position
        linha_lr = sorted(
            linha,
            key=lambda p: (_pos_x_hint(p.get("pos")) if _pos_x_hint(p.get("pos")) is not None else 50.0),
        )
        for ci, p in enumerate(linha_lr):
            x = (100 / (count + 1)) * (ci + 1) if count > 1 else 50.0
            pitch.append({**p, "x": round(x, 1), "y": round(y, 1)})
    return pitch


def _build_team_lineup(mid: str, team: str) -> dict:
    """Monta a escalação completa de um time num jogo: titulares + reservas (com
    marcações de gol/cartão/substituição) + coordenadas do campo. Reutilizável
    para os DOIS times do confronto."""
    lu = _lineups[(_lineups["match_id"] == mid) & (_lineups["team"] == team)]
    formation = None
    starters, subs = [], []
    if not lu.empty:
        fvals = lu["formation"].dropna().unique()
        formation = str(fvals[0]) if len(fvals) else None
        for _, p in lu.sort_values("shirt_number", na_position="last").iterrows():
            _pname = p.get("player_name")
            item = {
                "name": _pname.strip() if isinstance(_pname, str) else _pname,
                "num": _num(p.get("shirt_number")),
                "pos": p.get("position") if not pd.isna(p.get("position")) else None,
            }
            (starters if bool(p.get("is_starter")) else subs).append(item)

    nrm = lambda s: (s or "").strip()
    game_subs = _subs_for(mid, team)
    entrou_min = {nrm(s["in"]): s["minute"] for s in game_subs if s.get("in")}
    saiu_min = {nrm(s["out"]): s["minute"] for s in game_subs if s.get("out")}
    partner_of = {}
    for s in game_subs:
        if s.get("in") and s.get("out"):
            partner_of[nrm(s["in"])] = nrm(s["out"])
            partner_of[nrm(s["out"])] = nrm(s["in"])

    roster_names = [it["name"] for it in starters + subs if it.get("name")]

    def resolve_name(ply):
        ply = (ply or "").strip()
        mt = _re.match(r"^([A-Z])\.\s+(.+)$", ply)
        if mt:
            ini, surname = mt.group(1), mt.group(2)
            for full in roster_names:
                parts = full.split()
                if parts and parts[0][:1] == ini and surname.lower() in full.lower():
                    return full
        return ply

    cards_of, goals_of = {}, {}
    if not _events.empty:
        ce = _events[(_events["match_id"] == mid) & (_events["team"] == team)]
        for _, e in ce.iterrows():
            et, ply = e.get("event_type"), resolve_name(e.get("player"))
            if not ply:
                continue
            if et == "cartao_vermelho":
                cards_of[ply] = "vermelho"
            elif et == "cartao_amarelo" and cards_of.get(ply) != "vermelho":
                cards_of[ply] = "vermelho" if cards_of.get(ply) == "amarelo" else "amarelo"
            elif et in ("gol", "gol_penalti"):
                goals_of[ply] = goals_of.get(ply, 0) + 1

    pstats_map = _player_stats_for(mid, team, "")
    for it in starters + subs:
        nm = it.get("name")
        if nm in entrou_min:
            it["entered"] = entrou_min[nm]
        if nm in saiu_min:
            it["exited"] = saiu_min[nm]
        if nm in partner_of:
            it["sub_with"] = partner_of[nm]
        if nm in cards_of:
            it["card"] = cards_of[nm]
        if nm in goals_of:
            it["goals"] = goals_of[nm]
        if nm in pstats_map:
            # só guarda chaves com valor, p/ o card não mostrar campos vazios
            it["stats"] = {k: v for k, v in pstats_map[nm].items() if v is not None}

    return {
        "formation": formation, "starters": starters, "subs": subs,
        "pitch": _build_pitch(starters, formation), "game_subs": game_subs,
    }


def _timeline_for(mid: str, team: str, game_subs: list) -> list:
    """Linha do tempo: gols/cartões de AMBOS os times + substituições do time visto.
    mine=True nos eventos do `team`."""
    timeline = []
    if not _events.empty:
        ev = _events[_events["match_id"] == mid]
        sort_col = "minute_sort" if "minute_sort" in ev.columns else "minute"
        for _, e in ev.sort_values(sort_col, na_position="last").iterrows():
            sym_lbl = _EVENT_LABEL.get(e.get("event_type"))
            if not sym_lbl:
                continue
            sym, lbl = sym_lbl
            ply = e.get("player") if not pd.isna(e.get("player")) else None
            timeline.append({
                "minute": str(e.get("minute") or ""), "player": ply,
                "team": e.get("team") if not pd.isna(e.get("team")) else None,
                "mine": e.get("team") == team, "sym": sym, "label": lbl, "hl_name": ply,
            })
    for s in game_subs:
        entra, saiu = s.get("in"), s.get("out")
        extra = f" ({s['reason']})" if s.get("reason") else ""
        timeline.append({
            "minute": s["minute"],
            "player": f"{entra} ↔ {saiu}{extra}" if entra and saiu else (entra or saiu),
            "team": team, "mine": True, "sym": "🔄", "label": "Substituição",
            "is_sub": True, "hl_name": entra or saiu,
        })

    def _min_key(t):
        mm = str(t.get("minute") or "0").replace("'", "").split("+")
        try:
            return int(mm[0]) * 100 + (int(mm[1]) if len(mm) > 1 else 0)
        except ValueError:
            return 0
    timeline.sort(key=_min_key)
    return timeline


_finalizados = matches_df[matches_df["status"] == "finalizado"]
# Todas as seleções da Copa (não só as que já jogaram) — para a grade da aba.
_all_cup_teams = sorted(
    {t for t in matches_df["home_team"].dropna()} | {t for t in matches_df["away_team"].dropna()},
    key=_sort_key_ptbr,
)
teams_detail: dict[str, dict] = {}
for _team in _all_cup_teams:
    # todos os jogos do time com adversário definido (finalizados + agendados);
    # confrontos de mata-mata ainda indefinidos (sem adversário) ficam de fora.
    mine = matches_df[
        (matches_df["home_team"] == _team) | (matches_df["away_team"] == _team)
    ].sort_values(["temporal_order", "date", "kickoff_time"])

    # — jogos + escalações
    jogos_list = []
    for _, m in mine.iterrows():
        mid = m["match_id"]
        is_finalizado = m.get("status") == "finalizado"
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

        # escalação dos DOIS times (campo + reservas com marcações)
        lineup = _build_team_lineup(mid, _team)
        formation, starters, subs = lineup["formation"], lineup["starters"], lineup["subs"]
        opp_lineup = _build_team_lineup(mid, opp)

        # linha do tempo do jogo (eventos de ambos; mine=True nos do time visto)
        timeline = _timeline_for(mid, _team, lineup["game_subs"])

        # — estatísticas comparadas (meu time × adversário) nesta partida
        stats_cmp = []
        if not _tstats.empty:
            mine_row = _tstats[(_tstats["match_id"] == mid) & (_tstats["team"] == _team)]
            opp_row = _tstats[(_tstats["match_id"] == mid) & (_tstats["team"] == opp)]
            if not mine_row.empty and not opp_row.empty:
                mr, orow = mine_row.iloc[0], opp_row.iloc[0]

                def _ratio_pct(row, num_col, den_col):
                    num, den = _num(row.get(num_col)), _num(row.get(den_col))
                    if num is None or not den:
                        return None
                    return round(num / den * 100, 1)

                for col, lbl, fmt in _MATCH_STAT_ROWS:
                    is_pct = fmt in ("pct100", "ratio")
                    if fmt == "ratio":
                        num_col, den_col = col
                        if num_col not in _tstats.columns or den_col not in _tstats.columns:
                            continue
                        mv, ov = _ratio_pct(mr, num_col, den_col), _ratio_pct(orow, num_col, den_col)
                    else:
                        if col not in _tstats.columns:
                            continue
                        mv = _num(mr.get(col), 1 if is_pct else 0)
                        ov = _num(orow.get(col), 1 if is_pct else 0)
                    if mv is None and ov is None:
                        continue
                    stats_cmp.append({"label": lbl, "mine": mv, "opp": ov, "pct": is_pct})

        try:
            _round = int(m.get("round") or 0)
        except (TypeError, ValueError):
            _round = 0
        # nomes/bandeiras/placar em ORDEM REAL (mandante × visitante), p/ o card
        home_team, away_team = m.get("home_team"), m.get("away_team")
        home_score = _num(m.get("home_score"))
        away_score = _num(m.get("away_score"))
        jogos_list.append({
            "match_id": mid,
            "finalizado": bool(is_finalizado),
            "opp": opp, "opp_flag": FLAGS.get(opp, "🏳️"),
            "home": bool(is_home),
            # ordem real do confronto (independe da seleção sendo vista)
            "home_team": home_team, "home_flag": FLAGS.get(home_team, "🏳️"), "home_score": home_score,
            "away_team": away_team, "away_flag": FLAGS.get(away_team, "🏳️"), "away_score": away_score,
            "gf": gf_i, "ga": ga_i, "res": res if is_finalizado else "",
            "date": str(m.get("date", ""))[:10],
            "stage": _STAGE_LABEL.get(m.get("stage"), m.get("stage") or ""),
            "stage_key": m.get("stage") or "fase_de_grupos",
            "round": _round,
            "formation": formation,
            "starters": starters, "subs": subs,
            "pitch": lineup["pitch"],
            # escalação do adversário (campo + reservas) p/ a vista de 2 times
            "opp_formation": opp_lineup["formation"],
            "opp_pitch": opp_lineup["pitch"],
            "opp_subs": opp_lineup["subs"],
            "timeline": timeline,
            "stats_cmp": stats_cmp,
            "story": _read_story(mid),
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

    # — infos curadas (YAML); confederação do YAML tem prioridade sobre o mapa local
    info = TEAMS_INFO.get(_team, {}) or {}
    confed = info.get("confederacao") or CONFEDERATION.get(_team)

    # — artilheiro do time nesta Copa (do elenco agregado)
    artilheiro = None
    if players:
        top = max(players, key=lambda p: (p.get("gols") or 0, p.get("assist") or 0))
        if (top.get("gols") or 0) > 0:
            artilheiro = {"name": top["name"], "gols": top["gols"]}

    teams_detail[_team] = {
        "team": _team,
        "flag": FLAGS.get(_team, "🏳️"),
        "rank": rank,
        "n_jogos": len(jogos_list),
        "group": TEAM_GROUP.get(_team),
        "confed": confed,
        "stage_now": stage_now,
        "scores": scores,
        "campanha": campanha,
        "artilheiro": artilheiro,
        "info": {
            "apelido": info.get("apelido"),
            "tecnico": info.get("tecnico"),
            "titulos_copa": info.get("titulos_copa"),
            "vices_copa": info.get("vices_copa"),
            "participacoes": info.get("participacoes"),
            "estreia": info.get("estreia"),
            "melhor_campanha": info.get("melhor_campanha"),
            "curiosidade": info.get("curiosidade"),
        },
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
    # Estilo de jogo: eixos descritivos 0-100 (50 = média do torneio). Não é
    # qualidade — caracteriza COMO o time joga. O rótulo textual (estilo_jogo)
    # aparece à parte, no cabeçalho do modal; aqui ficam só os eixos numéricos.
    ("Estilo de jogo · onde o time pende em cada eixo (centro = média do torneio)", "tt-col-estilo", [
        ("estilo_posse", "Construção"),
        ("estilo_pressao", "Recuperação"),
        ("estilo_verticalidade", "Chegada ao ataque"),
        ("estilo_largura", "Largura"),
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
    "posse_media":             ["passes_por_jogo", "precisao_passes", "chutes_no_alvo_por_jogo", "score_controle", "estilo_posse"],
    "passes_por_jogo":         ["posse_media", "precisao_passes", "key_passes_por_jogo", "score_controle", "estilo_posse"],
    "precisao_passes":         ["passes_por_jogo", "posse_media", "score_controle", "estilo_posse"],
    "dribbles_won_por_jogo":   ["posse_media", "key_passes_por_jogo", "score_controle", "estilo_largura"],

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

    # ── Estilo de jogo (descritivo): acende as métricas brutas do painel que
    # compõem cada eixo. Insumos sem coluna no painel (recuperação no terço
    # final, desarmes, cruzamentos certos) entram só como indireta (amarelo).
    "estilo_posse":            ["posse_media", "passes_por_jogo", "precisao_passes"],
    "estilo_verticalidade":    ["chutes_por_jogo", "chutes_no_alvo_por_jogo"],
    "estilo_largura":          ["dribbles_won_por_jogo", "key_passes_por_jogo"],
    "estilo_pressao":          [],  # nenhum insumo direto tem coluna no painel
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

    # disciplina: faltas geram escanteios/cartões (e correlacionam com pressão alta)
    "faltas_por_jogo":         ["escanteios_por_jogo", "estilo_pressao"],
    "amarelos_por_jogo":       ["escanteios_por_jogo"],

    # escanteios: resultado de pressão ofensiva
    "escanteios_por_jogo":     ["score_ataque", "gols_por_jogo", "chutes_por_jogo", "estilo_largura"],
    "chutes_por_jogo":         ["score_ataque", "gols_por_jogo", "estilo_verticalidade"],
    "key_passes_por_jogo":     ["chutes_por_jogo", "escanteios_por_jogo", "score_ataque", "estilo_largura"],

    # ── Estilo (descritivo): correlatos sem coluna própria no painel.
    # Pressão alta correlaciona com mais faltas (disputa no campo de frente) e
    # escanteios (pressão ofensiva); verticalidade com escanteios; largura com
    # escanteios (cruzamentos viram escanteios).
    "estilo_posse":            ["key_passes_por_jogo", "dribbles_won_por_jogo"],
    "estilo_pressao":          ["faltas_por_jogo", "escanteios_por_jogo"],
    "estilo_verticalidade":    ["escanteios_por_jogo", "gols_por_jogo"],
    "estilo_largura":          ["escanteios_por_jogo"],
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
/* wrapper da aba Race: precisa ser flex-column que preenche o body, senão o
   .main não recebe altura limitada e a .bars-viewport não rola. */
#viewRace {{
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}}
.main {{
  display: flex;
  flex: 1;
  min-height: 0;
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
.tt-col-controle  {{ grid-column: span 2; }}
.tt-col-disciplina {{ grid-column: span 2; border-right: none; }}
/* Estilo ocupa uma 3ª linha inteira (6 colunas): os 4 eixos viram um grid
   horizontal dentro do bloco, para não esticar uma única coluna estreita. */
.tt-col-estilo {{ grid-column: 1 / -1; border-right: none; border-bottom: none; }}
/* Estilo: 4 eixos bipolares lado a lado (25% cada), cada um com polos + barra. */
.tt-style-row {{
  display: inline-block; width: 24.5%; vertical-align: top;
  padding: 6px 12px 8px; box-sizing: border-box;
}}
.tt-style-row.related      {{ background: rgba(74,222,128,0.10); }}
.tt-style-row.related-indirect {{ background: rgba(240,192,64,0.10); }}
.tt-style-poles {{
  display: flex; justify-content: space-between;
  font-size: 0.6rem; color: #8b949e; margin-bottom: 3px;
}}
.tt-style-bar {{
  position: relative; height: 5px; background: #21262d;
  border-radius: 3px; margin: 2px 0 5px;
}}
.tt-style-mid {{
  position: absolute; left: 50%; top: -1px; width: 1px; height: 7px;
  background: #484f58;  /* marca o centro = média do torneio */
}}
.tt-style-dot {{
  position: absolute; top: 50%; width: 9px; height: 9px;
  background: #58a6ff; border-radius: 50%;
  transform: translate(-50%, -50%); box-shadow: 0 0 0 2px #0d1117;
}}
.tt-style-foot {{
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 0.66rem;
}}
.tt-style-name {{ color: #c9d1d9; }}
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
.drag-why {{ color: #8b949e; font-style: italic; }}
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
/* min-height:0 é essencial: sem isso o item flex não encolhe abaixo do conteúdo
   e a grade cresce além da viewport em vez de rolar internamente. */
#viewTeams {{ flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }}
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
  flex: 1; overflow-y: auto; padding: 26px 28px;
  display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 30px; align-content: start;
}}
.team-card {{
  background: #0d1117; border: 1px solid #21262d; border-radius: 16px;
  padding: 22px 24px; cursor: pointer;
  transition: border-color 0.15s, transform 0.1s, background 0.15s, box-shadow 0.15s;
}}
.team-card:hover {{
  border-color: #1f6feb; background: #11161f; transform: translateY(-2px);
  box-shadow: 0 8px 26px rgba(31,111,235,0.14);
}}
.tc-head {{ display: flex; align-items: center; gap: 18px; }}
.team-card .tc-flag {{ font-size: 3.6rem; line-height: 1; flex-shrink: 0; }}
.team-card .tc-info {{ min-width: 0; flex: 1; }}
.team-card .tc-name {{ font-weight: 800; font-size: 1.35rem; color: #e6edf3; line-height: 1.15; }}
.team-card .tc-sub {{ font-size: 0.82rem; color: #8b949e; margin-top: 4px; }}
.team-card .tc-rank {{
  font-size: 1.3rem; font-weight: 900; color: #58a6ff;
  background: #1f6feb18; border-radius: 9px; padding: 7px 13px; flex-shrink: 0;
}}
/* destaque da métrica ativa */
.tc-metric {{
  display: flex; align-items: baseline; gap: 12px;
  margin-top: 18px; padding-top: 16px; border-top: 1px solid #161b22;
}}
.tc-metric .m-val {{ font-size: 2.6rem; font-weight: 900; line-height: 1; font-variant-numeric: tabular-nums; }}
.tc-metric .m-lbl {{ font-size: 0.78rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 700; }}
.tc-metric .m-rank {{
  margin-left: auto; font-size: 0.74rem; font-weight: 700; color: #9ca3af;
  background: #161b22; border: 1px solid #21262d; border-radius: 6px; padding: 3px 9px;
}}
/* mini-stats secundárias no card */
.tc-stats {{
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
  margin-top: 16px;
}}
.tc-stat {{ text-align: center; background: #11161f; border-radius: 8px; padding: 8px 4px; }}
.tc-stat .v {{ font-size: 1.2rem; font-weight: 800; color: #e6edf3; font-variant-numeric: tabular-nums; }}
.tc-stat .l {{ font-size: 0.66rem; color: #6b7280; margin-top: 3px; text-transform: uppercase; letter-spacing: 0.3px; }}
.tc-badges {{ display: flex; gap: 7px; margin-top: 14px; flex-wrap: wrap; }}
.tc-badge {{
  font-size: 0.7rem; font-weight: 600; color: #9ca3af;
  background: #161b22; border: 1px solid #21262d; border-radius: 6px; padding: 3px 9px;
}}
.team-card.tc-empty {{ opacity: 0.45; cursor: default; }}
.team-card.tc-empty:hover {{ border-color: #21262d; transform: none; background: #0d1117; box-shadow: none; }}

/* ── paginação ── */
.teams-pager {{
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 14px 20px; border-top: 1px solid #21262d; flex-shrink: 0;
}}
.pager-btn {{
  background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
  color: #c9d1d9; font-size: 0.82rem; font-weight: 600; min-width: 34px; height: 32px;
  padding: 0 10px; cursor: pointer; transition: border-color 0.15s, background 0.15s, color 0.15s;
}}
.pager-btn:hover:not(:disabled) {{ border-color: #1f6feb; color: #58a6ff; }}
.pager-btn.active {{ background: #1f6feb; border-color: #1f6feb; color: #fff; }}
.pager-btn:disabled {{ opacity: 0.35; cursor: default; }}
.pager-info {{ color: #6b7280; font-size: 0.74rem; margin: 0 6px; }}

/* ── MODAL ── */
.modal-overlay {{
  position: fixed; inset: 0; background: rgba(1,4,9,0.78);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; padding: 24px; backdrop-filter: blur(2px);
}}
.modal {{
  background: #0d1117; border: 1px solid #30363d; border-radius: 14px;
  width: min(1000px, 100%); max-height: 90vh; display: flex; flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.6);
}}
/* topbar: identidade compacta + abas + fechar, tudo numa linha */
.modal-topbar {{
  display: flex; align-items: center; gap: 14px;
  padding: 6px 16px 0 20px; border-bottom: 1px solid #21262d; flex-shrink: 0;
}}
.modal-mini {{
  display: flex; align-items: center; gap: 9px; font-size: 1rem; font-weight: 800;
  color: #e6edf3; white-space: nowrap; padding-bottom: 8px; flex-shrink: 0;
}}
.modal-mini .modal-flag {{ font-size: 1.6rem; line-height: 1; }}
.modal-close {{
  background: transparent; border: none; color: #8b949e; cursor: pointer;
  font-size: 1.1rem; padding: 4px 8px; border-radius: 6px; margin-bottom: 4px;
}}
.modal-close:hover {{ background: #21262d; color: #e6edf3; }}
.modal-tabs {{ display: flex; gap: 2px; }}
.modal-tab {{
  background: transparent; border: none; border-bottom: 2px solid transparent; cursor: pointer;
  color: #8b949e; font-size: 0.8rem; font-weight: 600; padding: 8px 12px; transition: color 0.15s;
}}
.modal-tab:hover {{ color: #c9d1d9; }}
.modal-tab.active {{ color: #58a6ff; border-bottom-color: #58a6ff; }}
.modal-body {{ overflow-y: auto; padding: 18px 20px; }}

/* blocos do modal — aba Resumo (hero + 2 colunas) */
.rs-hero {{
  position: relative;
  display: flex; align-items: center; gap: 18px;
  padding: 18px 20px; border-radius: 12px; margin-bottom: 16px;
  background: linear-gradient(135deg, #1f6feb1f, #0d1117 70%);
  border: 1px solid #1f6feb33;
}}
/* lâmpada de curiosidade no canto superior direito do hero */
.rs-lamp {{
  position: absolute; top: 50%; right: 16px; transform: translateY(-50%);
  font-size: 1.3rem; cursor: help; line-height: 1; opacity: 0.8;
  transition: opacity 0.15s, transform 0.1s;
}}
.rs-lamp:hover, .rs-lamp:focus {{ opacity: 1; transform: translateY(-50%) scale(1.12); outline: none; }}
.rs-lamp-tip {{
  display: none; position: absolute; top: 130%; right: 0; z-index: 10;
  width: 260px; font-size: 0.82rem; font-weight: 400; line-height: 1.45;
  color: #c9d1d9; background: #161b22; border: 1px solid #1f6feb55;
  border-radius: 10px; padding: 11px 14px; box-shadow: 0 10px 30px rgba(0,0,0,0.6);
}}
.rs-lamp:hover .rs-lamp-tip, .rs-lamp:focus .rs-lamp-tip {{ display: block; }}
.rs-hero-flag {{ font-size: 3rem; line-height: 1; flex-shrink: 0; }}
.rs-hero-info {{ min-width: 0; }}
.rs-hero-top {{ display: flex; align-items: center; gap: 10px; }}
.rs-hero-name {{ font-size: 1.4rem; font-weight: 900; color: #e6edf3; line-height: 1.1; }}
.rs-hero-rank {{
  font-size: 0.74rem; font-weight: 700; color: #58a6ff;
  background: #1f6feb22; border-radius: 6px; padding: 3px 8px;
}}
.rs-hero-nick {{ font-size: 0.92rem; color: #58a6ff; font-weight: 600; margin-top: 3px; }}
.rs-hero-meta {{ font-size: 0.82rem; color: #8b949e; margin-top: 5px; }}

.rs-cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; align-items: stretch; }}
@media (max-width: 620px) {{ .rs-cols {{ grid-template-columns: 1fr; }} }}
.rs-col {{
  background: #0d1117; border: 1px solid #21262d; border-radius: 12px; padding: 16px 18px;
  display: flex; flex-direction: column;
}}
.rs-col-title {{
  font-size: 0.7rem; color: #58a6ff; text-transform: uppercase; letter-spacing: 0.6px;
  font-weight: 700; margin-bottom: 8px;
}}
.rs-kv {{
  display: flex; align-items: baseline; justify-content: space-between;
  padding: 9px 0; border-bottom: 1px solid #161b22;
}}
.rs-kv:last-of-type {{ border-bottom: none; }}
.rs-k {{ font-size: 0.84rem; color: #8b949e; }}
.rs-v {{ font-size: 1.15rem; font-weight: 800; color: #e6edf3; font-variant-numeric: tabular-nums; }}
.rs-highlight {{
  font-size: 0.82rem; color: #c9d1d9; margin-top: auto; line-height: 1.4;
  background: #11161f; border-radius: 8px; padding: 10px 12px;
}}
.rs-highlight + .rs-highlight {{ margin-top: 8px; }}
.rs-na {{ font-size: 0.82rem; color: #6b7280; padding: 6px 0; }}
.rs-curio {{
  font-size: 0.86rem; color: #c9d1d9; margin-top: 16px; padding: 13px 16px;
  background: #1f6feb10; border: 1px solid #1f6feb33; border-radius: 10px; line-height: 1.5;
}}

/* (mantido p/ compat — não usado mais na aba Resumo) */
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

/* ── aba Jogos: card de jogo (accordion) ── */
.mg {{
  background: #161b22; border: 1px solid #21262d; border-radius: 10px;
  margin-bottom: 10px; overflow: hidden; transition: border-color 0.15s;
}}
.mg.open {{ border-color: #1f6feb55; }}
.mg-head {{
  display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer;
  transition: background 0.15s;
}}
.mg-head:hover {{ background: #1a212b; }}
/* lados do confronto: mandante (esq) e visitante (dir), agrupados à esquerda */
.mg-side {{ min-width: 0; color: #8b949e; white-space: nowrap; }}
.mg-side.me {{ color: #e6edf3; }}                 /* a seleção sendo vista, destacada */
.mg-score {{
  font-weight: 800; font-size: 1rem; flex-shrink: 0; padding: 3px 12px; border-radius: 6px;
  background: #21262d; font-variant-numeric: tabular-nums; text-align: center; min-width: 64px;
}}
.mg-score.res-V {{ background: #22c55e22; color: #22c55e; }}
.mg-score.res-E {{ background: #6b728022; color: #9ca3af; }}
.mg-score.res-D {{ background: #ef444422; color: #ef4444; }}
.mg-score.res-next {{ background: #21262d; color: #6b7280; }}
.mg-meta {{ flex-shrink: 0; margin-left: auto; }}  /* empurra data + chevron pra direita */
.mg-chevron {{ color: #6b7280; font-size: 0.7rem; flex-shrink: 0; }}
.mg-detail {{ padding: 4px 16px 16px; border-top: 1px solid #21262d; }}
/* título de fase + jogos agendados (não clicáveis) */
.mg-phase {{
  font-size: 0.72rem; color: #58a6ff; text-transform: uppercase; letter-spacing: 0.6px;
  font-weight: 700; margin: 16px 0 8px;
}}
.mg-phase:first-child {{ margin-top: 4px; }}
.mg.scheduled {{ opacity: 0.7; border-style: dashed; }}
.mg.scheduled .mg-head {{ cursor: default; }}
.mg.scheduled .mg-head:hover {{ background: transparent; }}

.gd-block {{ margin-top: 16px; }}
.gd-block:first-child {{ margin-top: 12px; }}
.gd-title {{
  font-size: 0.72rem; color: #58a6ff; text-transform: uppercase; letter-spacing: 0.5px;
  font-weight: 700; margin-bottom: 10px;
}}
.gd-story {{ font-size: 0.86rem; color: #c9d1d9; line-height: 1.6; }}
.gd-story p {{ margin: 0 0 10px; }}
.gd-story p:last-child {{ margin-bottom: 0; }}
.gd-story b {{ color: #e6edf3; }}
.gd-list {{ margin: 0 0 10px; padding-left: 4px; list-style: none; }}
.gd-list li {{ position: relative; padding: 3px 0 3px 16px; }}
.gd-list li::before {{ content: '▸'; position: absolute; left: 0; color: #58a6ff; }}

.gd-ev {{ display: flex; align-items: center; gap: 10px; padding: 5px 0; font-size: 0.82rem; }}
.gd-ev.opp {{ flex-direction: row-reverse; text-align: right; }}
.gd-min {{ color: #8b949e; font-variant-numeric: tabular-nums; min-width: 38px; flex-shrink: 0; }}
.gd-ev.opp .gd-min {{ min-width: 38px; }}
.gd-sym {{ font-size: 1rem; flex-shrink: 0; }}
.gd-evp {{ flex: 1; color: #e6edf3; }}
.gd-evp.clickable {{ cursor: pointer; }}
.gd-evp.clickable:hover {{ color: #58a6ff; text-decoration: underline; }}

.gd-stat {{ margin-bottom: 10px; }}
.gd-stat-vals {{ display: flex; align-items: center; font-size: 0.82rem; color: #8b949e; }}
.gd-stat-vals span:first-child {{ width: 56px; text-align: left; font-weight: 700; color: #c9d1d9; }}
.gd-stat-vals span:last-child {{ width: 56px; text-align: right; font-weight: 700; color: #c9d1d9; }}
.gd-stat-vals .gd-stat-lbl {{ flex: 1; text-align: center; font-weight: 400; color: #8b949e; }}
.gd-stat-vals .hi {{ color: #58a6ff !important; }}
.gd-bar {{ height: 5px; background: #ef444433; border-radius: 3px; margin-top: 4px; overflow: hidden; }}
.gd-bar-mine {{ height: 100%; background: #58a6ff; border-radius: 3px; transition: width 0.3s; }}
.gd-stat-head {{ display: flex; justify-content: space-between; font-size: 0.74rem; font-weight: 700; color: #8b949e; margin-bottom: 10px; }}

/* mini-abas dentro do jogo */
.gd-tabs {{ display: flex; gap: 2px; margin: 12px 0 4px; border-bottom: 1px solid #21262d; }}
.gd-tab {{
  background: transparent; border: none; border-bottom: 2px solid transparent; cursor: pointer;
  color: #8b949e; font-size: 0.76rem; font-weight: 600; padding: 6px 11px; transition: color 0.15s;
}}
.gd-tab:hover {{ color: #c9d1d9; }}
.gd-tab.active {{ color: #58a6ff; border-bottom-color: #58a6ff; }}
.gd-content {{ padding-top: 12px; }}

/* campo de futebol (esquema tático) */
.pitch {{
  position: relative; width: 100%; max-width: 360px; margin: 6px auto 0;
  aspect-ratio: 2 / 3;
  background:
    repeating-linear-gradient(0deg, #1f7a3a 0 11.11%, #1c6f35 11.11% 22.22%);
  border: 2px solid #ffffff40; border-radius: 8px; overflow: hidden;
}}
.pitch-lines {{ position: absolute; inset: 0; pointer-events: none; }}
.pl-line {{ position: absolute; border: 2px solid #ffffff40; }}
/* linha do meio + círculo central */
.pl-half {{ left: 0; right: 0; top: 50%; height: 0; border-width: 0; border-top: 2px solid #ffffff40; }}
.pl-circle {{
  left: 50%; top: 50%; transform: translate(-50%,-50%);
  width: 90px; height: 90px; border-radius: 50%;
}}
.pl-spot {{ left: 50%; top: 50%; transform: translate(-50%,-50%); width: 4px; height: 4px; background: #ffffff66; border: 0; border-radius: 50%; }}
/* grande área (defesa = embaixo, ataque = em cima) */
.pl-box {{ left: 50%; transform: translateX(-50%); width: 58%; height: 16%; }}
.pl-box.bottom {{ bottom: -2px; border-bottom: 0; }}
.pl-box.top {{ top: -2px; border-top: 0; }}
/* pequena área */
.pl-box-s {{ left: 50%; transform: translateX(-50%); width: 30%; height: 7%; }}
.pl-box-s.bottom {{ bottom: -2px; border-bottom: 0; }}
.pl-box-s.top {{ top: -2px; border-top: 0; }}
/* gol */
.pl-goal {{ left: 50%; transform: translateX(-50%); width: 16%; height: 6px; background: #ffffff22; }}
.pl-goal.bottom {{ bottom: -3px; }}
.pl-goal.top {{ top: -3px; }}
/* curva da grande área (meia-lua) — círculo centrado na borda da área (16% de altura).
   O círculo fica metade dentro/metade fora; o clip mostra só a metade que sai da área. */
.pl-arc {{
  position: absolute; left: 50%; transform: translate(-50%, 50%);
  width: 24%; aspect-ratio: 1 / 1; border: 2px solid #ffffff40; border-radius: 50%;
}}
.pl-arc.bottom {{ bottom: 16%; clip-path: inset(0 0 50% 0); }}   /* mostra só a metade de cima */
.pl-arc.top {{ top: 16%; transform: translate(-50%, -50%); clip-path: inset(50% 0 0 0); }}
.pitch-player {{
  position: absolute; transform: translate(-50%, 50%);
  display: flex; flex-direction: column; align-items: center;
  width: 84px; z-index: 1;
}}
.pitch-shirt {{
  width: 30px; height: 30px; border-radius: 50%;
  background: #d6342c; border: 2px solid #fff; color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.8rem; font-weight: 800; box-shadow: 0 2px 6px rgba(0,0,0,0.4);
}}
.pitch-name {{
  font-size: 0.62rem; color: #fff; font-weight: 600; margin-top: 3px;
  text-align: center; line-height: 1.15; text-shadow: 0 1px 3px rgba(0,0,0,1), 0 0 2px rgba(0,0,0,1);
  word-break: break-word; max-width: 84px;
}}
.pitch-form {{ text-align: center; font-size: 0.8rem; font-weight: 700; color: #58a6ff; margin-bottom: 6px; }}

.lv-col-title {{
  font-size: 0.68rem; color: #58a6ff; text-transform: uppercase; letter-spacing: 0.5px;
  font-weight: 700; margin-bottom: 8px;
}}

/* ── vista do confronto: campo T1 | timeline | campo T2 ── */
.pitch-form-inline {{ font-size: 0.72rem; color: #58a6ff; font-weight: 700; margin: 0 6px; }}

/* ── vista do confronto: UM campo vertical ── */
.lv1 {{ display: flex; flex-direction: column; align-items: center; }}
.lv1-head {{
  display: flex; justify-content: space-between; width: 100%;
  font-size: 0.92rem; color: #e6edf3; margin-bottom: 8px;
}}
.lv1-home b {{ color: #ff8a80; }}   /* time visto (esquerda) em vermelho */
.lv1-away b {{ color: #6ea8ff; }}   /* adversário (direita) em azul */
/* campo único HORIZONTAL, grande */
.pitch-h.pitch-vs {{
  position: relative; width: 100%; aspect-ratio: 3 / 2; margin: 0 auto;
  background: repeating-linear-gradient(90deg, #1f7a3a 0 11.11%, #1c6f35 11.11% 22.22%);
  border: 2px solid #ffffff40; border-radius: 8px; overflow: hidden;
}}
.pitch-vs .pitch-player {{
  position: absolute; transform: translate(-50%, -50%);
  display: flex; flex-direction: column; align-items: center; width: 76px; z-index: 1;
}}
.pitch-vs .pitch-name {{ max-width: 76px; font-size: 0.6rem; }}
.pitch-vs .pitch-shirt {{ width: 28px; height: 28px; font-size: 0.76rem; }}
/* cores por time: visto (home) vermelho, adversário (away) azul */
.pitch-player.home .pitch-shirt {{ background: #d6342c; }}
.pitch-player.away .pitch-shirt {{ background: #2f6fed; }}
/* marcações do campo horizontal */
.plh-half {{ top: 0; bottom: 0; left: 50%; width: 0; border-left: 2px solid #ffffff40; position: absolute; }}
.plh-box {{ top: 50%; transform: translateY(-50%); height: 56%; width: 11%; position: absolute; }}
.plh-box.left {{ left: -2px; border-left: 0; }}
.plh-box.right {{ right: -2px; border-right: 0; }}
.plh-box-s {{ top: 50%; transform: translateY(-50%); height: 28%; width: 5%; position: absolute; }}
.plh-box-s.left {{ left: -2px; border-left: 0; }}
.plh-box-s.right {{ right: -2px; border-right: 0; }}
.pl-goal-h {{ top: 50%; transform: translateY(-50%); height: 14%; width: 5px; background: #ffffff22; position: absolute; }}
.pl-goal-h.left {{ left: -3px; }}
.pl-goal-h.right {{ right: -3px; }}

/* card flutuante de dados do jogador (popover ancorado no jogador) */
.pcard {{
  position: absolute; bottom: 115%; left: 50%; transform: translateX(-50%);
  z-index: 5; width: 190px; cursor: default;
  background: #0d1117; border: 1px solid #30363d; border-radius: 10px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.7); padding: 10px 12px; text-align: left;
}}
/* jogadores perto da borda: joga o card pra dentro */
.pcard-away {{ left: auto; right: 50%; transform: translateX(50%); }}
.pc-head {{ display: flex; align-items: center; gap: 7px; }}
.pc-num {{
  background: #21262d; color: #c9d1d9; font-size: 0.66rem; font-weight: 800;
  border-radius: 5px; padding: 1px 6px; flex-shrink: 0;
}}
.pc-name {{ font-size: 0.84rem; font-weight: 800; color: #e6edf3; flex: 1; line-height: 1.1; }}
.pc-close {{ background: transparent; border: none; color: #8b949e; cursor: pointer; font-size: 0.8rem; padding: 0 2px; }}
.pc-close:hover {{ color: #e6edf3; }}
.pc-pos {{ font-size: 0.66rem; color: #8b949e; margin-top: 2px; }}
.pc-ctx {{ font-size: 0.72rem; color: #f5c542; margin: 7px 0; }}
.pc-stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 2px 12px; margin-top: 6px; }}
.pc-row {{ display: flex; justify-content: space-between; font-size: 0.72rem; color: #8b949e; padding: 2px 0; }}
.pc-row b {{ color: #e6edf3; font-variant-numeric: tabular-nums; }}
.pc-empty {{ font-size: 0.72rem; color: #6b7280; grid-column: 1/-1; }}

/* campo ocupa toda a largura em cima */
.lv1-center {{ width: 100%; min-width: 0; }}
/* embaixo: reservas T1 | linha do tempo | reservas T2 */
.lv1-bottom {{
  display: grid; grid-template-columns: 1fr 1.3fr 1fr; gap: 18px;
  width: 100%; margin-top: 18px; align-items: start;
}}
.lv1-subs {{ min-width: 0; }}
.lv1-subs .md-xi {{ flex-direction: column; gap: 4px; }}
.lv1-subs .md-xi .pl {{ display: flex; align-items: center; gap: 6px; }}
.lv1-subs .md-xi .pl .pn {{ min-width: 18px; text-align: center; flex-shrink: 0; margin-right: 0; }}
.lv1-mid {{ min-width: 0; }}
.lv1-mid .gd-ev {{ font-size: 0.8rem; }}
@media (max-width: 760px) {{
  .lv1-bottom {{ grid-template-columns: 1fr; }}
}}
/* marcação de substituição no campo / reservas */
.pitch-shirt {{ position: relative; }}
.pitch-player.subbed-out .pitch-shirt {{ opacity: 0.6; }}
.sub-out {{
  position: absolute; top: -6px; right: -14px;
  font-size: 0.56rem; font-weight: 800; color: #fff;
  background: #ef4444; border-radius: 8px; padding: 1px 4px; white-space: nowrap;
}}
.md-xi .pl.used {{ border-color: #22c55e66; background: #14241a; opacity: 1; }}
.sub-in {{ color: #22c55e; font-weight: 700; }}
/* cartão no jogador do campo (cantinho da camisa) */
.pl-card {{
  position: absolute; top: -4px; left: -8px; width: 8px; height: 11px;
  border-radius: 1.5px; border: 1px solid rgba(0,0,0,0.4);
}}
.pl-card.amarelo {{ background: #f5c542; }}
.pl-card.vermelho {{ background: #ef4444; }}
/* bolinha de gol no jogador do campo (canto direito da camisa) */
.pl-goal-mark {{
  position: absolute; top: -7px; right: -10px;
  font-size: 0.7rem; line-height: 1; display: flex; align-items: center;
  filter: drop-shadow(0 1px 1px rgba(0,0,0,0.6));
}}
.pl-goal-mark b {{
  font-size: 0.56rem; color: #fff; background: #1f6feb; border-radius: 7px;
  padding: 0 3px; margin-left: -2px;
}}
/* evento da linha do tempo clicável */
.gd-ev.clickable {{ cursor: pointer; border-radius: 6px; transition: background 0.12s; }}
.gd-ev.clickable:hover {{ background: #1a212b; }}
/* clique para destacar a troca */
.pitch-player.clickable, .md-xi .pl.clickable {{ cursor: pointer; }}
/* destaque: escurece o gramado e esmaece os outros jogadores; o(s) realçado(s) sobressaem */
.dim-others {{ position: relative; }}
.dim-others::after {{
  content: ''; position: absolute; inset: 0; z-index: 2;
  background: rgba(0,0,0,0.55); pointer-events: none; transition: background 0.15s;
}}
.dim-others .pitch-player {{ opacity: 0.3; transition: opacity 0.15s; }}
.dim-others .pitch-player.hi {{ opacity: 1; z-index: 3; }}  /* acima do overlay */
.pitch-player.hi .pitch-shirt {{ box-shadow: 0 0 0 3px #f5c542, 0 0 14px 3px #f5c54288; opacity: 1; }}
.pitch-player.hi .pitch-name {{ color: #f5c542; }}
.md-xi .pl.hi {{ border-color: #f5c542; background: #2a2410; color: #f5c542; opacity: 1; }}
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
    <input type="text" id="teamSearch" class="teams-search" placeholder="Buscar seleção…" oninput="applyTeamFilters()">

    <label class="tb-field">Ordenar
      <select id="teamSort" onchange="applyTeamFilters()"></select>
    </label>
    <button class="btn tb-dir" id="teamSortDir" onclick="toggleTeamSortDir()" title="Inverter ordem">↓</button>

    <label class="tb-field">Grupo
      <select id="filterGroup" onchange="applyTeamFilters()"><option value="">Todos</option></select>
    </label>
    <label class="tb-field">Confederação
      <select id="filterConfed" onchange="applyTeamFilters()"><option value="">Todas</option></select>
    </label>
    <label class="tb-field">Fase
      <select id="filterStage" onchange="applyTeamFilters()"><option value="">Todas</option></select>
    </label>
    <label class="tb-check"><input type="checkbox" id="filterPlayed" onchange="applyTeamFilters()"> Só com jogos</label>

    <div style="flex:1"></div>
    <button class="btn" onclick="resetTeamFilters()" title="Limpar filtros">✕ Limpar</button>
    <span class="teams-count" id="teamsCount"></span>
  </div>
  <div class="teams-grid" id="teamsGrid"></div>
  <div class="teams-pager" id="teamsPager"></div>
</div>

<!-- ══ MODAL: detalhe da seleção ══ -->
<div id="teamModal" class="modal-overlay" style="display:none" onclick="if(event.target===this)closeTeamModal()">
  <div class="modal" role="dialog" aria-modal="true">
    <div class="modal-topbar">
      <nav class="modal-tabs" id="modalTabs"></nav>
      <div style="flex:1"></div>
      <button class="modal-close" onclick="closeTeamModal()" title="Fechar (Esc)">✕</button>
    </div>
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
// Eixos de estilo: escala 0-100 (como os scores) para as barras, mas SEM medalha
// de pódio — estilo é descritivo, 50 não é "ruim" nem 90 é "melhor".
const STYLE_AXES = new Set(['estilo_posse', 'estilo_pressao', 'estilo_verticalidade', 'estilo_largura']);
// Cada eixo é BIPOLAR: 50 = meio-termo, sobe para o polo alto, desce para o
// baixo. low/high/curto alimentam o card (polos visíveis) e a linha "por que
// a flag" (usa o nome curto do lado para onde o time pende).
const STYLE_POLES = {{
  estilo_posse:         {{ low: 'Direto',     high: 'Posse',       curtoAlto: 'posse',     curtoBaixo: 'jogo direto' }},
  estilo_pressao:       {{ low: 'Recua',      high: 'Pressiona',   curtoAlto: 'pressão',   curtoBaixo: 'bloco baixo' }},
  estilo_verticalidade: {{ low: 'Paciente',   high: 'Vertical',    curtoAlto: 'verticalidade', curtoBaixo: 'jogo apoiado' }},
  estilo_largura:       {{ low: 'Por dentro', high: 'Pelas pontas',curtoAlto: 'pontas',    curtoBaixo: 'jogo interior' }},
}};

// "Por que a flag": pega os 1-2 eixos onde o time MAIS se afasta da média (50),
// e descreve o lado para onde pende — conecta a flag aos eixos que a definiram.
function styleWhy(t) {{
  const traits = Object.keys(STYLE_POLES)
    .map(k => {{
      const v = t[k];
      if (v === null || v === undefined) return null;
      const dist = Math.abs(v - 50);
      const pole = STYLE_POLES[k];
      return {{ dist, label: v >= 50 ? pole.curtoAlto : pole.curtoBaixo }};
    }})
    .filter(x => x && x.dist >= 8)            // só traços de fato marcantes
    .sort((a, b) => b.dist - a.dist)
    .slice(0, 2)
    .map(x => x.label);
  return traits.length ? traits.join(' + ') : '';
}}

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
                  STYLE_AXES.has(currentMetric) ||
                  PERCENT_FRAC.has(currentMetric) || PERCENT_DIRECT.has(currentMetric);
  const maxV = Math.max(...vals, 0);
  const maxRef = PERCENT_FRAC.has(currentMetric) ? 1
               : (PERCENT_DIRECT.has(currentMetric) || currentMetric.startsWith('score_') || STYLE_AXES.has(currentMetric)) ? 100
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
               : (PERCENT_DIRECT.has(currentMetric) || currentMetric.startsWith('score_') || STYLE_AXES.has(currentMetric)) ? 100
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
    // ── Estilo: layout BIPOLAR (polo baixo ◄─●─► polo alto + nota) ──
    if (colCls === 'tt-col-estilo') {{
      metrics.forEach(([key, label]) => {{
        const val = t[key];
        const pole = STYLE_POLES[key] || {{ low: '', high: '' }};
        const isActive   = key === currentMetric;
        const isRelated  = !isActive && related.has(key);
        const isIndirect = !isActive && !isRelated && indirect.has(key);
        const cls = isActive ? ' active' : isRelated ? ' related' : isIndirect ? ' related-indirect' : '';
        // posição do marcador na barra: 0-100, 50 = centro (média do torneio)
        const pos = val === null || val === undefined ? 50 : Math.max(0, Math.min(100, val));
        const mr = metricRank(key, allTeams, team, sortDir);
        const rkBadge = mr ? `<span class="tt-rank">${{mr.rank}}°${{mr.tied ? '=' : ''}}</span>` : '';
        colsHtml += `<div class="tt-row tt-style-row${{cls}}" data-metric="${{key}}">
          <div class="tt-style-poles">
            <span class="tt-pole-low">${{pole.low}}</span>
            <span class="tt-pole-high">${{pole.high}}</span>
          </div>
          <div class="tt-style-bar">
            <span class="tt-style-mid"></span>
            <span class="tt-style-dot" style="left:${{pos}}%"></span>
          </div>
          <div class="tt-style-foot">
            <span class="tt-style-name">${{label}}</span>
            <span class="tt-valwrap"><span class="tt-val">${{formatVal(val, key)}}</span>${{rkBadge}}</span>
          </div>
        </div>`;
      }});
      colsHtml += '</div>';
      return;
    }}
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
      // Estilo não recebe medalha — é descritivo, não há "1º melhor estilo".
      const rkCls = mr && !mr.tied && !STYLE_AXES.has(key) ? rankClass(mr.rank) : '';
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
  // flag de estilo + por que ela: os 1-2 eixos que mais definiram a classificação
  const why = styleWhy(t);
  const estilo = t.estilo_jogo
    ? ` · 🎭 ${{t.estilo_jogo}}${{why ? ` <span class="drag-why">(${{why}})</span>` : ''}}`
    : '';
  return `<span class="drag-flag">${{t.flag || ''}}</span>
    <span class="drag-name">${{t.team}}</span>
    <span class="drag-sub">#${{rank}}${{rankTie}} no ranking · ${{t.jogos}} jogo${{t.jogos !== 1 ? 's' : ''}}${{estilo}}</span>`;
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
    applyTeamFilters();
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

// formatadores reutilizáveis para o destaque da métrica
const _f1 = v => v == null ? '—' : v.toFixed(1);                    // 1 casa (scores)
const _fi = v => v == null ? '—' : Math.round(v);                   // inteiro
const _fs = v => v == null ? '—' : (v > 0 ? '+' + v : '' + v);     // saldo com sinal
const _fp = v => v == null ? '—' : Math.round(v * 100) + '%';      // fração → %

// opções de ordenação: k, label (dropdown), short (rótulo do destaque), get (acessor),
// fmt (formatação do destaque), asc (direção default). Sem fmt → score 1 casa.
const TEAM_SORTS = [
  {{ k: 'rank',       label: 'Ranking (#)',      short: 'Geral',        get: d => d.rank, asc: true }},
  {{ k: 'alpha',      label: 'Alfabética (A–Z)', short: 'Geral',        get: d => null,  asc: true }},
  {{ k: 'score_geral',        label: 'Score Geral',     short: 'Geral',         get: d => (d.scores||{{}}).score_geral,         fmt: _f1 }},
  {{ k: 'score_resultado',    label: 'Score Resultado', short: 'Resultado',     get: d => (d.scores||{{}}).score_resultado,     fmt: _f1 }},
  {{ k: 'score_ataque',       label: 'Score Ataque',    short: 'Ataque',        get: d => (d.scores||{{}}).score_ataque,        fmt: _f1 }},
  {{ k: 'score_defesa',       label: 'Score Defesa',    short: 'Defesa',        get: d => (d.scores||{{}}).score_defesa,        fmt: _f1 }},
  {{ k: 'score_eficiencia',   label: 'Score Eficiência',short: 'Eficiência',    get: d => (d.scores||{{}}).score_eficiencia,    fmt: _f1 }},
  {{ k: 'score_controle',     label: 'Score Controle',  short: 'Controle',      get: d => (d.scores||{{}}).score_controle,      fmt: _f1 }},
  {{ k: 'score_forca_relativa',label:'Score Força Rel.', short: 'Força Rel.',    get: d => (d.scores||{{}}).score_forca_relativa,fmt: _f1 }},
  {{ k: 'score_disciplina',   label: 'Score Disciplina',short: 'Disciplina',    get: d => (d.scores||{{}}).score_disciplina,    fmt: _f1 }},
  {{ k: 'pontos',     label: 'Pontos',          short: 'Pontos',       get: d => (d.campanha||{{}}).pontos,        fmt: _fi }},
  {{ k: 'gols_pro',   label: 'Gols Marcados',   short: 'Gols',         get: d => (d.campanha||{{}}).gols_pro,      fmt: _fi }},
  {{ k: 'saldo_gols', label: 'Saldo de Gols',   short: 'Saldo',        get: d => (d.campanha||{{}}).saldo_gols,    fmt: _fs }},
  {{ k: 'elo_rating', label: 'Rating Elo',      short: 'Elo',          get: d => (d.campanha||{{}}).elo_rating,    fmt: _fi }},
  {{ k: 'n_jogos',    label: 'Jogos disputados',short: 'Jogos',        get: d => d.n_jogos,                        fmt: _fi }},
];

// qual métrica destacar no card: para rank/alpha usa o Score Geral
function _highlightSort(sortKey) {{
  if (sortKey === 'rank' || sortKey === 'alpha') {{
    return TEAM_SORTS.find(s => s.k === 'score_geral');
  }}
  return TEAM_SORTS.find(s => s.k === sortKey) || TEAM_SORTS.find(s => s.k === 'score_geral');
}}

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

const TEAMS_PER_PAGE = 24;
let teamPage = 1;

// mudou filtro/ordenação → volta pra página 1 e re-renderiza
function applyTeamFilters() {{
  teamPage = 1;
  renderTeamsGrid();
}}

function goTeamPage(p) {{
  teamPage = p;
  renderTeamsGrid();
  document.getElementById('teamsGrid').scrollTop = 0;
}}

function toggleTeamSortDir() {{
  const cur = _effectiveSortDir();
  teamSortDir = cur === 'asc' ? 'desc' : 'asc';
  applyTeamFilters();
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
  applyTeamFilters();
}}

function renderTeamsPager(totalPages) {{
  const pager = document.getElementById('teamsPager');
  if (totalPages <= 1) {{ pager.innerHTML = ''; return; }}
  let btns = `<button class="pager-btn" onclick="goTeamPage(${{teamPage - 1}})" ${{teamPage === 1 ? 'disabled' : ''}}>‹</button>`;
  for (let p = 1; p <= totalPages; p++) {{
    btns += `<button class="pager-btn${{p === teamPage ? ' active' : ''}}" onclick="goTeamPage(${{p}})">${{p}}</button>`;
  }}
  btns += `<button class="pager-btn" onclick="goTeamPage(${{teamPage + 1}})" ${{teamPage === totalPages ? 'disabled' : ''}}>›</button>`;
  pager.innerHTML = btns + `<span class="pager-info">página ${{teamPage}} de ${{totalPages}}</span>`;
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

  // — destaque da métrica ativa: valor + posição entre TODAS as seleções que têm a métrica
  const hl = _highlightSort(sortKey);
  const hlFmt = hl.fmt || _f1;
  // ranking da métrica destacada sobre todas as seleções (maior = melhor, salvo saldo já tratado)
  // empate = mesma posição (standard competition ranking: 1, 2, 2, 4…)
  const ranked = TEAMS_GRID
    .map(t => ({{ t, v: hl.get(TEAMS_DETAIL[t] || {{}}) }}))
    .filter(x => x.v != null)
    .sort((a, b) => b.v - a.v);
  const hlPos = {{}};
  ranked.forEach((x, i) => {{
    hlPos[x.t] = (i > 0 && x.v === ranked[i - 1].v) ? hlPos[ranked[i - 1].t] : i + 1;
  }});
  const hlTotal = ranked.length;

  // — paginação: 24 por página
  const totalPages = Math.max(1, Math.ceil(teams.length / TEAMS_PER_PAGE));
  if (teamPage > totalPages) teamPage = totalPages;
  const start = (teamPage - 1) * TEAMS_PER_PAGE;
  const pageTeams = teams.slice(start, start + TEAMS_PER_PAGE);
  renderTeamsPager(totalPages);

  grid.innerHTML = pageTeams.map(t => {{
    const d = TEAMS_DETAIL[t] || {{}};
    const flag = d.flag || TEAM_FLAGS[t] || '🏳️';
    const nj = d.n_jogos || 0;
    const empty = nj === 0;
    // o badge # reflete a POSIÇÃO na métrica escolhida (não o ranking geral fixo)
    const rankBadge = (!empty && hlPos[t]) ? `<span class="tc-rank">#${{hlPos[t]}}</span>` : '';
    const sub = empty ? 'sem jogos ainda · ' + (d.group ? 'Grupo ' + d.group : '')
      : nj + (nj === 1 ? ' jogo' : ' jogos') + ' · ' + (d.players ? d.players.length : 0) + ' jogadores';

    const cp = d.campanha || {{}};

    // destaque: reflete a métrica escolhida na ordenação
    const hlVal = hl.get(d);
    const hlColor = (hl.k.startsWith('score_') && hlVal != null) ? _scoreColor(hlVal) : '#e6edf3';
    const posBadge = (!empty && hlPos[t]) ? `<span class="m-rank">${{hlPos[t]}}º de ${{hlTotal}}</span>` : '';
    const metric = empty ? '' : `<div class="tc-metric">
      <span class="m-val" style="color:${{hlColor}}">${{hlFmt(hlVal)}}</span>
      <span class="m-lbl">${{hl.short}}</span>
      ${{posBadge}}
    </div>`;

    // mini-stats secundárias: campanha resumida (sempre visível, contexto)
    const fmt = v => v == null ? '—' : v;
    const stats = empty ? '' : `<div class="tc-stats">
      <div class="tc-stat"><div class="v">${{fmt(cp.pontos)}}</div><div class="l">Pts</div></div>
      <div class="tc-stat"><div class="v">${{fmt(cp.gols_pro)}}</div><div class="l">Gols</div></div>
      <div class="tc-stat"><div class="v">${{cp.saldo_gols != null ? (cp.saldo_gols > 0 ? '+' + cp.saldo_gols : cp.saldo_gols) : '—'}}</div><div class="l">Saldo</div></div>
      <div class="tc-stat"><div class="v">${{fmt(cp.elo_rating)}}</div><div class="l">Elo</div></div>
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
      ${{metric}}
      ${{stats}}
    </div>`;
  }}).join('');
}}

let modalTeam = null;
let modalTab = 'scores';
let expandedGame = null;  // índice do jogo expandido na aba Jogos (accordion)

function openTeamModal(team) {{
  const d = TEAMS_DETAIL[team];
  if (!d) return;
  modalTeam = team;
  modalTab = 'scores';
  expandedGame = null;
  const tabs = [
    ['scores', 'Resumo'],
    ['jogos', 'Jogos (' + (d.jogos ? d.jogos.length : 0) + ')'],
    ['elenco', 'Elenco (' + (d.players ? d.players.length : 0) + ')'],
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
  expandedGame = null;  // ao trocar de aba, fecha qualquer jogo expandido
  document.querySelectorAll('.modal-tab').forEach(b =>
    b.classList.toggle('active', b.dataset.mt === t));
  renderModalBody();
}}

function toggleGame(i) {{
  cardPlayer = null; highlightedPlayer = null;
  if (expandedGame === i) {{ expandedGame = null; }}
  else {{ expandedGame = i; gameDetailTab = 'historia'; }}  // abre na História
  renderModalBody();
}}

let gameDetailTab = 'historia';  // mini-aba ativa dentro do jogo expandido
let highlightedPlayer = null;     // jogador destacado no campo (par da troca)
let cardPlayer = null;            // jogador com o card de dados aberto (popover)

function switchGameTab(t) {{
  gameDetailTab = t;
  highlightedPlayer = null;
  cardPlayer = null;
  renderModalBody();
}}

// clica num jogador no campo → abre o card de dados + destaca (e o par da troca)
function showPlayerCard(name) {{
  if (cardPlayer === name) {{ cardPlayer = null; highlightedPlayer = null; }}
  else {{ cardPlayer = name; highlightedPlayer = name; }}
  renderModalBody();
}}

// clica num reserva/timeline → destaca a troca (sem abrir card)
function highlightSub(name) {{
  highlightedPlayer = (highlightedPlayer === name) ? null : name;
  cardPlayer = null;
  renderModalBody();
}}

// clica num jogador na linha do tempo → vai pra escalação e abre o card dele
function focusPlayer(name) {{
  if (!name) return;
  gameDetailTab = 'escalacao';
  cardPlayer = name;
  highlightedPlayer = name;
  renderModalBody();
}}

// monta o card flutuante com as stats do jogador na partida
const _STAT_ROWS = [
  ['rating', 'Nota', v => v.toFixed ? v.toFixed(1) : v],
  ['goals', 'Gols'], ['assists', 'Assistências'],
  ['shots', 'Finalizações'], ['on_target', 'No alvo'],
  ['key_passes', 'Passes-chave'], ['xa', 'xA', v => (+v).toFixed(2)],
  ['pass_acc', '% passes', v => v + '%'],
  ['saves', 'Defesas'],
  ['fouls_committed', 'Faltas'], ['fouls_drawn', 'Faltas sofridas'],
  ['offsides', 'Impedimentos'], ['minutes', 'Minutos', v => v + "'"],
];
function _playerCardHtml(p, who) {{
  const st = p.stats || {{}};
  const ctx = [];
  if (p.goals) ctx.push(`⚽ ${{p.goals}} gol${{p.goals > 1 ? 's' : ''}}`);
  if (p.card) ctx.push(p.card === 'vermelho' ? '🟥 expulso' : '🟨 amarelo');
  if (p.exited) ctx.push(`↓ saiu ${{p.exited}}'`);
  if (p.entered) ctx.push(`↑ entrou ${{p.entered}}'`);
  const rows = _STAT_ROWS
    .filter(([k]) => st[k] != null)
    .map(([k, lbl, fmt]) => `<div class="pc-row"><span>${{lbl}}</span><b>${{fmt ? fmt(st[k]) : st[k]}}</b></div>`)
    .join('');
  const body = rows || '<div class="pc-empty">Sem estatísticas detalhadas.</div>';
  return `<div class="pcard pcard-${{who}}" onclick="event.stopPropagation()">
    <div class="pc-head"><span class="pc-num">${{p.num ?? ''}}</span><span class="pc-name">${{p.name}}</span>
      <button class="pc-close" onclick="event.stopPropagation();showPlayerCard('${{(p.name||'').replace(/'/g, "\\\\'")}}')">✕</button></div>
    ${{p.pos ? `<div class="pc-pos">${{p.pos}}</div>` : ''}}
    ${{ctx.length ? `<div class="pc-ctx">${{ctx.join(' · ')}}</div>` : ''}}
    <div class="pc-stats">${{body}}</div>
  </div>`;
}}

// escapa HTML para evitar injeção e tags acidentais vindas dos dados
function _esc(t) {{
  return (t || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}}

// converte a narrativa markdown (wikilinks, **negrito**, listas, parágrafos) em HTML
function _renderStory(raw) {{
  if (!raw) return '';
  // wikilinks [[a|b]]/[[a]] → texto puro (antes de escapar, pois usam [])
  let t = raw.replace(/\[\[[^|\]]*\|([^\]]+)\]\]/g, '$1').replace(/\[\[([^\]]+)\]\]/g, '$1');
  t = _esc(t);
  // **negrito** e *itálico*
  t = t.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/\*([^*]+)\*/g, '<i>$1</i>');

  // agrupa linhas em parágrafos e listas
  const lines = t.split('\\n');
  let html = '', list = [];
  const flushList = () => {{ if (list.length) {{ html += '<ul class="gd-list">' + list.map(li => `<li>${{li}}</li>`).join('') + '</ul>'; list = []; }} }};
  for (let ln of lines) {{
    ln = ln.trim();
    if (!ln) {{ flushList(); continue; }}
    const m = ln.match(/^[-•]\s+(.*)/);
    if (m) {{ list.push(m[1]); }}
    else {{ flushList(); html += `<p>${{ln}}</p>`; }}
  }}
  flushList();
  return html;
}}

// detalhe expandido de um jogo, em mini-abas
function renderGameDetail(g) {{
  const minitabs = [
    ['historia', 'História', !!g.story],
    ['stats', 'Estatísticas', !!(g.stats_cmp && g.stats_cmp.length)],
    ['escalacao', 'Escalação', !!(g.starters && g.starters.length)],
  ].filter(([, , has]) => has);
  if (!minitabs.length) return '<div class="md-empty">Sem detalhes adicionais para este jogo.</div>';

  // garante que a mini-aba ativa existe pra este jogo (senão usa a 1ª disponível)
  let active = gameDetailTab;
  if (!minitabs.some(([k]) => k === active)) active = minitabs[0][0];

  const nav = `<div class="gd-tabs">${{minitabs.map(([k, l]) =>
    `<button class="gd-tab${{k === active ? ' active' : ''}}" onclick="event.stopPropagation();switchGameTab('${{k}}')">${{l}}</button>`
  ).join('')}}</div>`;

  let content = '';
  if (active === 'historia') {{
    content = `<div class="gd-story">${{_renderStory(g.story)}}</div>`;
  }} else if (active === 'stats') {{
    content = `<div class="gd-stat-head"><span>${{modalTeam}}</span><span>${{g.opp}}</span></div>` +
      g.stats_cmp.map(s => {{
        const mv = s.mine == null ? 0 : s.mine, ov = s.opp == null ? 0 : s.opp;
        const mpct = Math.round(mv / ((mv + ov) || 1) * 100);
        const suf = s.pct ? '%' : '';
        return `<div class="gd-stat">
          <div class="gd-stat-vals"><span class="${{mv >= ov ? 'hi' : ''}}">${{s.mine == null ? '—' : s.mine}}${{suf}}</span>
            <span class="gd-stat-lbl">${{s.label}}</span>
            <span class="${{ov > mv ? 'hi' : ''}}">${{s.opp == null ? '—' : s.opp}}${{suf}}</span></div>
          <div class="gd-bar"><div class="gd-bar-mine" style="width:${{mpct}}%"></div></div>
        </div>`;
      }}).join('');
  }} else if (active === 'escalacao') {{
    content = renderLineupView(g);
  }}

  return nav + `<div class="gd-content">${{content}}</div>`;
}}

// linha do tempo (gols/cartões/subs) — clicável nos jogadores do time visto
function _timelineHtml(g) {{
  if (!g.timeline || !g.timeline.length) return '<div class="md-empty">Sem eventos.</div>';
  const escEv = (s) => (s || '').replace(/'/g, "\\\\'");
  return g.timeline.map(e => {{
    const clickable = !!e.hl_name;               // qualquer evento com jogador (os 2 times)
    const cls = `gd-ev ${{e.mine ? 'mine' : 'opp'}}${{clickable ? ' clickable' : ''}}`;
    const oc = clickable ? ` onclick="focusPlayer('${{escEv(e.hl_name)}}')"` : '';
    return `<div class="${{cls}}"${{oc}}>
      <span class="gd-min">${{e.minute}}'</span><span class="gd-sym">${{e.sym}}</span>
      <span class="gd-evp">${{e.player || ''}}${{e.team ? ` <span class="md-game-meta">(${{e.team}})</span>` : ''}}</span>
    </div>`;
  }}).join('');
}}

// lista de reservas (clicável p/ destacar a troca)
// helper de destaque: o jogador clicado + o par da troca (em qualquer dos dois times)
function _mkIsHi(allPlayers) {{
  return (nm) => highlightedPlayer && (nm === highlightedPlayer
    || (allPlayers.find(x => x.name === highlightedPlayer) || {{}}).sub_with === nm);
}}

// lista de reservas de um time (clicável p/ destacar a troca)
function _subsListHtml(subs, isHi) {{
  const esc = (s) => (s || '').replace(/'/g, "\\\\'");
  if (!subs || !subs.length) return '<div class="md-empty">—</div>';
  return `<div class="md-xi subs">${{subs.map(p => {{
    const cls = `pl${{p.entered ? ' used' : ''}}${{isHi(p.name) ? ' hi' : ''}}${{p.sub_with ? ' clickable' : ''}}`;
    const oc = p.sub_with ? ` onclick="highlightSub('${{esc(p.name)}}')"` : '';
    const goal = p.goals ? ` ⚽${{p.goals > 1 ? p.goals : ''}}` : '';
    return `<span class="${{cls}}"${{oc}}><span class="pn">${{p.num ?? ''}}</span>${{p.name}}${{goal}}${{p.entered ? ` <span class="sub-in">↑${{p.entered}}'</span>` : ''}}</span>`;
  }}).join('')}}</div>`;
}}

// vista do confronto: UM campo vertical (time visto embaixo, adversário em cima),
// e abaixo: reservas T1 | linha do tempo | reservas T2.
function renderLineupView(g) {{
  const allPlayers = (g.pitch || []).concat(g.subs || [], g.opp_pitch || [], g.opp_subs || []);
  const isHi = _mkIsHi(allPlayers);
  const homeFlag = (TEAMS_DETAIL[modalTeam] || {{}}).flag || '';
  return `<div class="lv1">
    <div class="lv1-center">
      <div class="lv1-head">
        <span class="lv1-home">${{homeFlag}} <b>${{modalTeam}}</b> ${{g.formation ? `<span class="pitch-form-inline">${{g.formation}}</span>` : ''}}</span>
        <span class="lv1-away">${{g.opp_formation ? `<span class="pitch-form-inline">${{g.opp_formation}}</span>` : ''}} <b>${{g.opp}}</b> ${{g.opp_flag}}</span>
      </div>
      ${{renderPitch(g.pitch, g.opp_pitch, isHi)}}
    </div>
    <div class="lv1-bottom">
      <div class="lv1-subs">
        <div class="lv-col-title">Reservas · ${{modalTeam}}</div>
        ${{_subsListHtml(g.subs, isHi)}}
      </div>
      <div class="lv1-mid"><div class="lv-col-title">Linha do tempo</div>${{_timelineHtml(g)}}</div>
      <div class="lv1-subs">
        <div class="lv-col-title">Reservas · ${{g.opp}}</div>
        ${{_subsListHtml(g.opp_subs, isHi)}}
      </div>
    </div>
  </div>`;
}}

// UM campo HORIZONTAL com os dois times. Time visto na metade esquerda (gol à esq,
// ataca p/ centro); adversário na metade direita, espelhado (gol à dir).
// coords originais por jogador: x=lado (0..100), y=profundidade (8=gol..92=ataque).
function renderPitch(homePitch, awayPitch, isHi) {{
  const splitName = (full) => {{
    const parts = (full || '').trim().split(/\\s+/);
    if (parts.length <= 1) return parts[0] || '';
    return `${{parts[0]}}<br>${{parts.slice(1).join(' ')}}`;
  }};
  const dimmed = highlightedPlayer ? ' dim-others' : '';
  const esc = (s) => (s || '').replace(/'/g, "\\\\'");
  const cardMark = (p) => p.card ? `<span class="pl-card ${{p.card}}"></span>` : '';
  const goalMark = (p) => p.goals ? `<span class="pl-goal-mark">⚽${{p.goals > 1 ? `<b>${{p.goals}}</b>` : ''}}</span>` : '';

  // horizontal: profundidade (y) → eixo X; lado (x) → eixo Y (top).
  // home: metade esquerda (left 2..48%); away: metade direita espelhada (98..52%).
  const dot = (p, who) => {{
    const half = (p.y / 100) * 46;
    const left = who === 'home' ? (2 + half) : (98 - half);
    const top = p.x;
    // todo jogador é clicável → abre o card de dados (e destaca a troca, se houver)
    const cls = `pitch-player ${{who}} clickable${{p.exited ? ' subbed-out' : ''}}${{isHi(p.name) ? ' hi' : ''}}`;
    const card = (cardPlayer === p.name) ? _playerCardHtml(p, who) : '';
    return `<div class="${{cls}}" style="left:${{left}}%;top:${{top}}%" onclick="showPlayerCard('${{esc(p.name)}}')">
      <div class="pitch-shirt">${{p.num ?? ''}}${{cardMark(p)}}${{goalMark(p)}}${{p.exited ? `<span class="sub-out">↓${{p.exited}}'</span>` : ''}}</div>
      <div class="pitch-name">${{splitName(p.name)}}</div>
      ${{card}}
    </div>`;
  }};
  const dots = (homePitch || []).map(p => dot(p, 'home')).join('')
    + (awayPitch || []).map(p => dot(p, 'away')).join('');
  // marcações horizontais: meio (vertical), círculo, áreas/gols nas laterais
  const lines = `<div class="pitch-lines">
    <div class="pl-line plh-half"></div>
    <div class="pl-line pl-circle"></div>
    <div class="pl-line pl-spot"></div>
    <div class="pl-line plh-box left"></div><div class="pl-line plh-box-s left"></div><div class="pl-goal-h left"></div>
    <div class="pl-line plh-box right"></div><div class="pl-line plh-box-s right"></div><div class="pl-goal-h right"></div>
  </div>`;
  return `<div class="pitch-h pitch-vs${{dimmed}}">${{lines}}${{dots}}</div>`;
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
    const info = d.info || {{}};
    const cp = d.campanha || {{}};

    // — HERO: bandeira + nome + #rank + apelido + meta (técnico · confederação · grupo)
    const metaParts = [
      info.tecnico ? 'Téc. ' + info.tecnico : null,
      d.confed || null,
      d.group ? 'Grupo ' + d.group : null,
    ].filter(Boolean);
    const rankChip = d.rank != null ? `<span class="rs-hero-rank">#${{d.rank}}</span>` : '';
    // lâmpada no canto: curiosidade aparece no hover
    const lamp = info.curiosidade
      ? `<span class="rs-lamp" tabindex="0">💡<span class="rs-lamp-tip">${{info.curiosidade}}</span></span>`
      : '';
    const hero = `<div class="rs-hero">
      <span class="rs-hero-flag">${{d.flag || '🏳️'}}</span>
      <div class="rs-hero-info">
        <div class="rs-hero-top">
          <span class="rs-hero-name">${{d.team}}</span>
          ${{rankChip}}
        </div>
        ${{info.apelido ? `<div class="rs-hero-nick">${{info.apelido}}</div>` : ''}}
        ${{metaParts.length ? `<div class="rs-hero-meta">${{metaParts.join(' · ')}}</div>` : ''}}
      </div>
      ${{lamp}}
    </div>`;

    // — COLUNA 1: História em Copas
    const kv = (k, v) => `<div class="rs-kv"><span class="rs-k">${{k}}</span><span class="rs-v">${{v}}</span></div>`;
    const histStats = [];
    if (info.titulos_copa != null)
      histStats.push(kv(info.titulos_copa === 1 ? 'Título mundial' : 'Títulos mundiais', info.titulos_copa));
    if (info.vices_copa != null)
      histStats.push(kv(info.vices_copa === 1 ? 'Vice-campeonato' : 'Vice-campeonatos', info.vices_copa));
    if (info.participacoes != null)
      histStats.push(kv('Participações', info.participacoes));
    if (info.estreia != null)
      histStats.push(kv('Estreia em Copas', info.estreia));
    const colHist = `<div class="rs-col">
      <div class="rs-col-title">História em Copas</div>
      ${{histStats.length ? histStats.join('') : '<div class="rs-na">sem dados</div>'}}
      ${{info.melhor_campanha ? `<div class="rs-highlight">🏆 ${{info.melhor_campanha}}</div>` : ''}}
    </div>`;

    // — COLUNA 2: Nesta Copa (Gols e Saldo em linhas separadas)
    const temCampanha = d.n_jogos > 0;
    const fmtSaldo = cp.saldo_gols != null ? (cp.saldo_gols > 0 ? '+' + cp.saldo_gols : '' + cp.saldo_gols) : '—';
    const colCopa = `<div class="rs-col">
      <div class="rs-col-title">Nesta Copa</div>
      ${{temCampanha ? `
        ${{kv('Jogos', d.n_jogos)}}
        ${{kv('Pontos', cp.pontos != null ? cp.pontos : '—')}}
        ${{kv('Gols marcados', cp.gols_pro != null ? cp.gols_pro : '—')}}
        ${{kv('Saldo de gols', fmtSaldo)}}
        ${{d.artilheiro ? `<div class="rs-highlight">⚽ ${{d.artilheiro.name}} (${{d.artilheiro.gols}})</div>` : ''}}
      ` : '<div class="rs-na">Ainda não entrou em campo.</div>'}}
    </div>`;

    body.innerHTML = `${{hero}}<div class="rs-cols">${{colHist}}${{colCopa}}</div>`;
    return;
  }}

  if (modalTab === 'jogos') {{
    if (!d.jogos || !d.jogos.length) {{ body.innerHTML = '<div class="md-empty">Nenhum jogo cadastrado ainda.</div>'; return; }}
    const myFlag = d.flag || '🏳️';
    // agrupa por fase preservando a ordem cronológica de aparição
    const phases = [];
    const phaseIdx = {{}};
    d.jogos.forEach((g) => {{
      if (!(g.stage in phaseIdx)) {{ phaseIdx[g.stage] = phases.length; phases.push({{ label: g.stage, games: [] }}); }}
      phases[phaseIdx[g.stage]].games.push(g);
    }});

    // mandante sempre à esquerda, visitante à direita (ordem real do confronto).
    // A seleção sendo vista (modalTeam) fica em negrito destacado.
    const sideHtml = (team, flag, mine) =>
      `<span class="mg-side${{mine ? ' me' : ''}}">${{flag}} <b>${{team}}</b></span>`;

    const cardHtml = (g) => {{
      const i = d.jogos.indexOf(g);
      const homeIsMe = g.home_team === modalTeam;
      const left = sideHtml(g.home_team, g.home_flag, homeIsMe);
      const right = sideHtml(g.away_team, g.away_flag, !homeIsMe);
      if (!g.finalizado) {{
        // próximo jogo: não clicável, sem placar
        return `<div class="mg scheduled">
          <div class="mg-head">
            ${{left}}
            <span class="mg-score res-next">×</span>
            ${{right}}
            <span class="md-game-meta mg-meta">a jogar · ${{g.date}}</span>
          </div>
        </div>`;
      }}
      const placar = (g.home_score != null && g.away_score != null) ? `${{g.home_score}} – ${{g.away_score}}` : '—';
      const open = (expandedGame === i);
      return `<div class="mg ${{open ? 'open' : ''}}" data-gi="${{i}}">
        <div class="mg-head" onclick="toggleGame(${{i}})">
          ${{left}}
          <span class="mg-score res-${{g.res}}">${{placar}}</span>
          ${{right}}
          <span class="md-game-meta mg-meta">${{g.stage}} · ${{g.date}}</span>
          <span class="mg-chevron">${{open ? '▲' : '▼'}}</span>
        </div>
        ${{open ? `<div class="mg-detail">${{renderGameDetail(g)}}</div>` : ''}}
      </div>`;
    }};

    body.innerHTML = phases.map(ph =>
      `<div class="mg-phase">${{ph.label}}</div>` + ph.games.map(cardHtml).join('')
    ).join('');
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

}}

goToJogo(jogos[jogos.length - 1]);
</script>
</body>
</html>"""

OUTPUT.write_text(html, encoding="utf-8")
print(f"Gerado: {OUTPUT}")
