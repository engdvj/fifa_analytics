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
    "xg_por_jogo": "xg_por_jogo",                 # xG agregado do elenco (365Scores)
    "chutes_por_jogo": "_chutes_por_jogo",       # calculado abaixo
    "chutes_no_alvo_por_jogo": "chutes_no_alvo_por_jogo",
    "precisao_chute": "chutes_no_alvo_por_chute", # % chutes no alvo
    "escanteios_por_jogo": "_escanteios_por_jogo", # calculado abaixo
    "key_passes_por_jogo": "key_passes_por_jogo",
    "dribbles_won_por_jogo": "dribbles_won_por_jogo",
    # médias defensivas por jogo
    "gols_contra_por_jogo": "gols_contra_por_jogo",
    "xgp_por_jogo": "xgp_por_jogo",               # xGP: gols evitados acima do esperado (365Scores)
    "chutes_sofridos_por_jogo": "chutes_sofridos_por_jogo",
    "shots_blocked_por_jogo": "shots_blocked_por_jogo",
    "duels_won_por_jogo": "duels_won_por_jogo",
    "defesas_por_jogo": "_defesas_por_jogo",
    "jogos_sem_sofrer_gol": "jogos_sem_sofrer_gol",
    # cobertura de dados avançados (365Scores) — usado pelo filtro, não exibido como métrica
    "advanced_coverage": "advanced_coverage",
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

matches_df = pd.read_parquet(Path("data/gold/dim_match/canonical_matches.parquet"))
match_info = matches_df.set_index("match_id")[["home_team", "away_team", "home_score", "away_score"]].to_dict("index")

tl = pd.read_parquet(SNAPSHOTS_DIR / "snapshot_timeline.parquet")
snapshot_match_by_n = tl.groupby("snapshot_jogo")["match_id_referencia"].first().to_dict()
match_snapshot_n = {mid: int(n) for n, mid in snapshot_match_by_n.items()}
match_temporal_order = matches_df.set_index("match_id")["temporal_order"].to_dict() if "temporal_order" in matches_df.columns else {}


def _snapshot_order_key(n: int) -> tuple[float, int]:
    mid = snapshot_match_by_n.get(n)
    order = match_temporal_order.get(mid)
    try:
        order_num = float(order)
    except (TypeError, ValueError):
        order_num = float("inf")
    if pd.isna(order_num):
        order_num = float("inf")
    return order_num, int(n)


jogos = sorted(tl["snapshot_jogo"].unique(), key=_snapshot_order_key)
valid_snapshots = set(int(n) for n in jogos)
prev_jogo_by_n = {n: (jogos[i - 1] if i else None) for i, n in enumerate(jogos)}

# Nota: o placar AO VIVO não fica no HTML (estático demais para tempo real) —
# vive na janela do watcher (watcher/fifa_progress.py), que é leve e atualiza
# sozinha. O HTML foca no ranking dos jogos já processados.

data: dict = {}
for n in jogos:
    snap = tl[tl["snapshot_jogo"] == n].copy()
    wp = SNAPSHOTS_DIR / f"weights_jogo_{n:03d}.json"
    pesos = json.loads(wp.read_text())["pesos"] if wp.exists() else {}
    match_id = snap["match_id_referencia"].iloc[0]
    match_source_n = str(match_id).rsplit("_", 1)[-1] if "_" in str(match_id) else str(n).zfill(3)

    mi = match_info.get(match_id, {})
    home = mi.get("home_team", "?")
    away = mi.get("away_team", "?")
    hs = mi.get("home_score")
    as_ = mi.get("away_score")
    score_str = f"{int(hs)}–{int(as_)}" if hs is not None and not pd.isna(hs) else "?"
    match_label = f"Jogo {match_source_n} · {home} {score_str} {away}"
    home_flag = FLAGS.get(home, "🏳️")
    away_flag = FLAGS.get(away, "🏳️")

    prev_n = prev_jogo_by_n.get(n)
    if prev_n is not None:
        prev = tl[tl["snapshot_jogo"] == prev_n].set_index("team")["jogos"]
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
        "source_match_n": match_source_n,
        "home": home, "away": away, "score": score_str,
        "home_flag": home_flag, "away_flag": away_flag,
        "pesos": {k: round(float(v) * 100, 1) for k, v in pesos.items()},
        "teams": teams,
    }

data_json = json.dumps(data, ensure_ascii=False)


# ── Dados de JOGADORES por snapshot (aba Jogadores) ────────────────────────────
# Espelha a estrutura de seleções: PLAYER_DATA[n] = lista de jogadores no
# snapshot do jogo n (scores acumulados até ali). PLAYER_META = metadados
# estáticos (time/perfil/slug) usados para filtro e link. Gerado pelo
# snapshot_pipeline em player_snapshot_timeline.parquet.
_PLAYER_TL_PATH = SNAPSHOTS_DIR / "player_snapshot_timeline.parquet"
player_data: dict = {}
player_meta: dict = {}
if _PLAYER_TL_PATH.exists():
    ptl = pd.read_parquet(_PLAYER_TL_PATH)
    if not ptl.empty and "snapshot_jogo" in ptl.columns:
        ptl = ptl[ptl["snapshot_jogo"].map(lambda n: int(n) in valid_snapshots)].copy()
    # campos numéricos/textuais expostos por jogador no snapshot
    _PNUM = [
        "jogos", "score_geral", "ranking_score_geral", "rating_365",
        "goals", "assists", "participacoes_gol", "saves", "goals_conceded",
        "shots", "shots_on_target", "fouls_committed", "fouls_drawn",
        "yellow_cards", "red_cards",
        "expected_goals", "expected_assists", "expected_goals_on_target",
        "key_passes", "big_chances_created", "big_chances_missed",
        "big_chances_scored", "dribbles_won", "tackles_won",
        "interceptions", "clearances", "ball_recovery", "duels_won",
        "shots_blocked", "expected_goals_prevented", "penalties_saved",
        "high_claims", "punches",
        "gols_por_jogo", "assistencias_por_jogo", "participacoes_por_jogo",
        "chutes_no_alvo_por_jogo", "defesas_por_jogo",
        "faltas_cometidas_por_jogo", "faltas_sofridas_por_jogo",
        "expected_goals_por_jogo", "expected_assists_por_jogo",
        "expected_goals_on_target_por_jogo", "key_passes_por_jogo",
        "big_chances_created_por_jogo", "big_chances_missed_por_jogo",
        "big_chances_scored_por_jogo", "dribbles_won_por_jogo",
        "tackles_won_por_jogo", "interceptions_por_jogo",
        "clearances_por_jogo", "ball_recovery_por_jogo",
        "duels_won_por_jogo", "shots_blocked_por_jogo",
        "expected_goals_prevented_por_jogo", "penalties_saved_por_jogo",
        "high_claims_por_jogo", "punches_por_jogo",
    ]
    for n in sorted(ptl["snapshot_jogo"].unique()):
        snap = ptl[ptl["snapshot_jogo"] == n]
        rows = []
        for _, r in snap.iterrows():
            entry = {"slug": r["player_slug"], "name": r["player_name"],
                     "team": r["team"], "perfil": r.get("perfil"),
                     "nivel_evidencia": r.get("nivel_evidencia")}
            for k in _PNUM:
                v = r.get(k)
                try:
                    entry[k] = round(float(v), 2) if v is not None and not pd.isna(v) else None
                except (TypeError, ValueError):
                    entry[k] = None
            rows.append(entry)
        player_data[str(int(n))] = rows
    # metadados estáticos (do estado final): perfil/time/slug/camisa por jogador
    if not ptl.empty:
        last = ptl[ptl["snapshot_jogo"] == ptl["snapshot_jogo"].max()]
        for _, r in last.iterrows():
            _sn = r.get("shirt_number")
            player_meta[r["player_slug"]] = {
                "name": r["player_name"], "team": r["team"], "perfil": r.get("perfil"),
                "shirt": int(_sn) if _sn is not None and not pd.isna(_sn) else None,
            }

player_data_json = json.dumps(player_data, ensure_ascii=False)
player_meta_json = json.dumps(player_meta, ensure_ascii=False)


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
_pfeatures = _read_optional(Path("data/gold/analytics/player_match_features.parquet"))
_events = _read_optional(Path("data/gold/fact_events/canonical_events.parquet"))
_tstats = _read_optional(Path("data/gold/fact_team_match_stats/canonical_team_stats.parquet"))
_commentary = _read_optional(Path("data/gold/fact_commentary/canonical_commentary.parquet"))
_rosters = _read_optional(Path("data/gold/rosters/espn_rosters.parquet"))


try:
    from fifa_analytics.utils.text import (
        clean_person_name as _clean_person_name,
        person_name_exact_key as _person_name_exact_key,
        person_name_words_key as _person_name_words_key,
    )
except Exception:  # standalone sem pacote instalado
    def _clean_person_name(v):
        return " ".join(v.replace("\u00a0", " ").split()) if isinstance(v, str) else v

    def _person_name_exact_key(v):
        return _clean_person_name(v).casefold() if isinstance(v, str) else ""

    def _person_name_words_key(v):
        if not isinstance(v, str):
            return ""
        import unicodedata as _unicodedata
        text = _clean_person_name(v).replace("-", " ")
        text = _unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode().lower()
        return " ".join(text.split())


def _strip_name_cols(df: pd.DataFrame, cols: tuple[str, ...]) -> pd.DataFrame:
    """Normaliza nomes de jogador sem perder acento/identidade."""
    if df.empty:
        return df
    for c in cols:
        if c in df.columns:
            # não checar dtype==object: colunas pyarrow são dtype 'str', não object,
            # e seriam puladas. map() lida com qualquer backend de string.
            df[c] = df[c].map(_clean_person_name)
    return df


_p365 = _read_optional(Path("data/gold/fact_player_match_stats/365scores.parquet"))

_lineups = _strip_name_cols(_lineups, ("player_name",))
_pstats = _strip_name_cols(_pstats, ("player_name",))
_pfeatures = _strip_name_cols(_pfeatures, ("player_name",))
_events = _strip_name_cols(_events, ("player", "related_player"))
_commentary = _strip_name_cols(_commentary, ("player", "participants"))
_p365 = _strip_name_cols(_p365, ("player_name",))
_rosters = _strip_name_cols(_rosters, ("player_name",))

# Aplica os apelidos curados (config/player_aliases.yaml) ao nome do jogador,
# pela MESMA fonte única usada no pipeline — assim o detalhe do jogo no dashboard
# mostra o nome canônico (ex.: "Agustín Cano" das stats vira "Agustín Canobbio")
# e não duplica o jogador entre lineup/stats e o elenco oficial.
try:
    from fifa_analytics.analytics.name_reconciliation import apply_player_aliases as _apply_aliases
    _lineups = _apply_aliases(_lineups)
    _pstats = _apply_aliases(_pstats)
    _pfeatures = _apply_aliases(_pfeatures)
    _rosters = _apply_aliases(_rosters)
except Exception:  # standalone sem o pacote instalado: segue sem aliases
    pass

import re as _re


def _name_key(s) -> str:
    """Chave de nome sem acento/caixa, p/ casar 365scores (sem match_id) com canonical."""
    return _person_name_words_key(s)


def _name_key_exact(s) -> str:
    """Chave que PRESERVA acento/caixa (só normaliza espaços) — distingue jogadores
    homônimos quando o acento é o que os diferencia (ex.: 'Ederson' goleiro vs
    'Éderson' volante, ambos do Brasil). Usada nos joins DENTRO do mesmo time
    (camisa, posição, rating), onde o nome exato é confiável; o _name_key folded
    fica só p/ casamento fuzzy entre fontes (365scores)."""
    return _person_name_exact_key(s)


def _surname_key(s) -> str:
    parts = _name_key(s).split()
    return parts[-1] if parts else ""


def _find_365_player_row(rows: pd.DataFrame, player_name: str):
    """Casa jogador da 365Scores com o canônico.

    A 365 às vezes traz só o sobrenome no lineup (ex.: "Touré"), enquanto o
    canônico/ESPN vem com nome completo ("Mohamed Toure"). Primeiro tentamos o
    nome completo; se falhar, aceitamos sobrenome apenas quando for inequívoco
    dentro do mesmo time/jogo.
    """
    if rows.empty:
        return None

    key = _name_key(player_name)
    exact = rows[rows["player_name"].map(_name_key) == key]
    if len(exact) == 1:
        return exact.iloc[0]

    surname = _surname_key(player_name)
    if not surname:
        return None
    source_keys = rows["player_name"].map(_name_key)
    surname_only = rows[source_keys == surname]
    if len(surname_only) == 1:
        return surname_only.iloc[0]
    return None


def _find_365_player_rows(rows: pd.DataFrame, player_name: str) -> pd.DataFrame:
    """Versão agregada do match 365Scores: retorna todas as linhas do jogador."""
    if rows.empty:
        return rows

    key = _name_key(player_name)
    source_keys = rows["player_name"].map(_name_key)
    exact = rows[source_keys == key]
    if not exact.empty:
        return exact

    surname = _surname_key(player_name)
    if not surname:
        return rows.iloc[0:0]
    surname_only = rows[source_keys == surname]
    if surname_only.empty:
        return surname_only
    return surname_only if surname_only["player_name"].map(_name_key).nunique() == 1 else rows.iloc[0:0]


def _num0(v):
    try:
        return None if v is None or pd.isna(v) else (int(v) if float(v) == int(float(v)) else round(float(v), 2))
    except (TypeError, ValueError):
        return None


def _player_stats_for(mid: str, team: str, date: str, opponent: str = "") -> dict:
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
                "saves": _num0(r.get("saves")), "goals_conceded": _num0(r.get("goals_conceded")),
                "fouls_committed": _num0(r.get("fouls_committed")), "fouls_drawn": _num0(r.get("fouls_drawn")),
                "offsides": _num0(r.get("offsides")),
                "yellow": _num0(r.get("yellow_cards")), "red": _num0(r.get("red_cards")),
                "own_goals": _num0(r.get("own_goals")),
                "xg": _num0(r.get("expected_goals")),
                "xa": _num0(r.get("expected_assists")),
                "xgot": _num0(r.get("expected_goals_on_target")),
                "key_passes": _num0(r.get("key_passes")),
                "big_chances_created": _num0(r.get("big_chances_created")),
                "big_chances_missed": _num0(r.get("big_chances_missed")),
                "big_chances_scored": _num0(r.get("big_chances_scored")),
                "dribbles_won": _num0(r.get("dribbles_won")),
                "tackles_won": _num0(r.get("tackles_won")),
                "interceptions": _num0(r.get("interceptions")),
                "clearances": _num0(r.get("clearances")),
                "ball_recovery": _num0(r.get("ball_recovery")),
                "shots_blocked": _num0(r.get("shots_blocked")),
                "xgp": _num0(r.get("expected_goals_prevented")),
                "penalties_saved": _num0(r.get("penalties_saved")),
                "high_claims": _num0(r.get("high_claims")),
                "punches": _num0(r.get("punches")),
                # nota de atuação: vem do canonical (fonte única, já casada)
                "rating": _num0(r.get("rating")),
            }
            ground_duels = _num0(r.get("ground_duels_won"))
            aerial_duels = _num0(r.get("aerial_duels_won"))
            if ground_duels is not None or aerial_duels is not None:
                out[nm]["duels_won"] = (ground_duels or 0) + (aerial_duels or 0)
    # enriquecimento 365scores (minutos, xA, key passes, % passes) por nome+time —
    # a nota (rating) NÃO é sobrescrita aqui: já veio do canonical acima.
    if not _p365.empty:
        s365 = _p365[(_p365["team"] == team)]
        if opponent and "opponent" in s365.columns:
            s365 = s365[s365["opponent"] == opponent]
        if date and "match_date" in s365.columns:
            d365 = pd.to_datetime(s365["match_date"], errors="coerce")
            dcan = pd.to_datetime(str(date)[:10], errors="coerce")
            if not pd.isna(dcan):
                s365 = s365[(d365 - dcan).abs().dt.days <= 1]
        for nm, st in out.items():
            r = _find_365_player_row(s365, nm)
            if r is None:
                continue
            st["minutes"] = _num0(r.get("minutes"))
            for key, col in (
                ("xg", "expected_goals"),
                ("xgot", "expected_goals_on_target"),
                ("xa", "expected_assists"),
                ("key_passes", "key_passes"),
                ("big_chances_created", "big_chances_created"),
                ("big_chances_missed", "big_chances_missed"),
                ("big_chances_scored", "big_chances_scored"),
                ("dribbles_won", "dribbles_won"),
                ("tackles_won", "tackles_won"),
                ("interceptions", "interceptions"),
                ("clearances", "clearances"),
                ("ball_recovery", "ball_recovery"),
                ("shots_blocked", "shots_blocked"),
                ("xgp", "expected_goals_prevented"),
                ("goals_conceded", "goals_conceded"),
                ("penalties_saved", "penalties_saved"),
                ("high_claims", "high_claims"),
                ("punches", "punches"),
            ):
                v = _num0(r.get(col))
                if v is not None:
                    st[key] = v
            ground_duels = _num0(r.get("ground_duels_won"))
            aerial_duels = _num0(r.get("aerial_duels_won"))
            if ground_duels is not None or aerial_duels is not None:
                st["duels_won"] = (ground_duels or 0) + (aerial_duels or 0)
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
    "fase_de_grupos": "Fase de Grupos", "dezesseis_avos": "16-avos de Final",
    "oitavas_de_final": "Oitavas de Final", "quartas_de_final": "Quartas de Final",
    "semifinal": "Semifinais", "terceiro_lugar": "Disputa 3º Lugar", "final": "Final",
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
    if p in ("CD", "CB", "CM", "AM", "CAM", "DM", "CDM", "CF", "ST", "SS", "M", "F", "G", "GK", "SW"):
        return 50.0
    return None


# "Altura" tática de cada código de posição: menor = mais defensivo (perto do gol),
# maior = mais ofensivo. Usado para agrupar os jogadores nas linhas da formação.
_POS_DEPTH = {
    "G": 0, "GK": 0,
    "SW": 1, "CD": 2, "CD-L": 2, "CD-R": 2, "CB": 2, "LB": 2, "RB": 2, "LWB": 2, "RWB": 2,
    "DM": 3, "CDM": 3,
    "CM": 4, "CM-L": 4, "CM-R": 4, "LM": 4, "RM": 4, "M": 4, "MF": 4,
    "AM": 5, "AM-L": 5, "AM-R": 5, "CAM": 5,
    "LF": 6, "RF": 6, "LW": 6, "RW": 6, "CF": 6, "CF-L": 6, "CF-R": 6, "RCF": 6, "ST": 6, "SS": 6, "F": 6, "FW": 6,
}

_POS_GROUP_ORDER = {
    "Goleiros": 0,
    "Defensores": 1,
    "Meias": 2,
    "Atacantes": 3,
    "Sem posição": 4,
}


def _clean_pos(v) -> str:
    if v is None or pd.isna(v):
        return ""
    return str(v).strip()


def _position_group(pos: str | None) -> str:
    p = _clean_pos(pos).upper()
    if not p or p == "SUB":
        return "Sem posição"
    if p in {"G", "GK", "GOALKEEPER"}:
        return "Goleiros"
    if p in {"D", "DEFENDER", "SW", "CD", "CD-L", "CD-R", "CB", "LB", "RB", "LWB", "RWB"} or "BACK" in p:
        return "Defensores"
    if p in {"M", "MF", "MIDFIELDER", "DM", "CDM", "CM", "CM-L", "CM-R", "LM", "RM", "AM", "AM-L", "AM-R", "CAM"} or "MIDFIELD" in p:
        return "Meias"
    if p in {"F", "FW", "FORWARD", "ATTACKER", "LF", "RF", "LW", "RW", "CF", "CF-L", "CF-R", "RCF", "ST", "SS", "STRIKER"} or "FORWARD" in p or "WINGER" in p:
        return "Atacantes"
    return "Sem posição"


def _position_label(pos: str | None) -> str:
    p = _clean_pos(pos)
    if not p or p.upper() == "SUB":
        return "—"
    norm = p.upper().replace("_", " ").replace("-", " ")
    mapped = {
        "G": "Goleiro",
        "GK": "Goleiro",
        "GOALKEEPER": "Goleiro",
        "D": "Defensor",
        "DEFENDER": "Defensor",
        "SW": "Líbero",
        "CD": "Zagueiro",
        "CD L": "Zagueiro esquerdo",
        "CD R": "Zagueiro direito",
        "CB": "Zagueiro",
        "CENTRE BACK": "Zagueiro",
        "CENTER BACK": "Zagueiro",
        "LB": "Lateral esquerdo",
        "LEFT BACK": "Lateral esquerdo",
        "RB": "Lateral direito",
        "RIGHT BACK": "Lateral direito",
        "LWB": "Ala esquerdo",
        "LEFT WING BACK": "Ala esquerdo",
        "RWB": "Ala direito",
        "RIGHT WING BACK": "Ala direito",
        "M": "Meia",
        "MF": "Meia",
        "MIDFIELDER": "Meia",
        "DM": "Volante",
        "CDM": "Volante",
        "DEFENSIVE MIDFIELD": "Volante",
        "CM": "Meia central",
        "CM L": "Meia central esquerdo",
        "CM R": "Meia central direito",
        "CENTRAL MIDFIELD": "Meia central",
        "CENTRE MIDFIELD": "Meia central",
        "CENTER MIDFIELD": "Meia central",
        "AM": "Meia ofensivo",
        "AM L": "Meia ofensivo esquerdo",
        "AM R": "Meia ofensivo direito",
        "CAM": "Meia ofensivo",
        "ATTACKING MIDFIELD": "Meia ofensivo",
        "LM": "Meia esquerdo",
        "LEFT MIDFIELD": "Meia esquerdo",
        "RM": "Meia direito",
        "RIGHT MIDFIELD": "Meia direito",
        "F": "Atacante",
        "FW": "Atacante",
        "ATTACKER": "Atacante",
        "FORWARD": "Atacante",
        "ST": "Atacante",
        "STRIKER": "Atacante",
        "SS": "Segundo atacante",
        "CF": "Centroavante",
        "CF L": "Centroavante esquerdo",
        "CF R": "Centroavante direito",
        "RCF": "Centroavante direito",
        "CENTRE FORWARD": "Centroavante",
        "CENTER FORWARD": "Centroavante",
        "LF": "Atacante esquerdo",
        "LEFT FORWARD": "Atacante esquerdo",
        "RF": "Atacante direito",
        "RIGHT FORWARD": "Atacante direito",
        "LW": "Ponta esquerdo",
        "LEFT WINGER": "Ponta esquerdo",
        "RW": "Ponta direito",
        "RIGHT WINGER": "Ponta direito",
    }
    return mapped.get(norm, p.upper())


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

    gk = [p for p in starters if (p.get("pos_code") or p.get("pos") or "").upper() in {"G", "GK"}]
    field = [p for p in starters if (p.get("pos_code") or p.get("pos") or "").upper() not in {"G", "GK"}]
    if len(field) != sum(line_counts):
        return []

    # ordena os jogadores de linha por profundidade tática (defensivo → ofensivo)
    field_sorted = sorted(field, key=lambda p: _POS_DEPTH.get((p.get("pos_code") or p.get("pos") or "").upper(), 4))

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
            key=lambda p: (_pos_x_hint(p.get("pos_code") or p.get("pos")) if _pos_x_hint(p.get("pos_code") or p.get("pos")) is not None else 50.0),
        )
        for ci, p in enumerate(linha_lr):
            x = (100 / (count + 1)) * (ci + 1) if count > 1 else 50.0
            pitch.append({**p, "x": round(x, 1), "y": round(y, 1)})
    return pitch


def _build_team_lineup(mid: str, team: str, date: str = "", opponent: str = "") -> dict:
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
            pos_code = p.get("position") if not pd.isna(p.get("position")) else None
            item = {
                "name": _clean_person_name(_pname),
                "num": _num(p.get("shirt_number")),
                "pos_code": _clean_pos(pos_code) or None,
                "pos": _position_label(pos_code),
            }
            (starters if bool(p.get("is_starter")) else subs).append(item)

    # chave de match tolerante: minúsculas, sem acento, hífen→espaço, espaços
    # colapsados. Necessária porque lineup e commentary divergem (ex.: lineup
    # "Al-Harbi" vs commentary "Al Harbi"; "Mohammed Abu Al-Shamat" vs "...Al Shamat").
    def _mk(s):
        return _name_key(s)

    game_subs = _subs_for(mid, team)
    # mapa chave-normalizada → nome de exibição do lineup (p/ o par da troca)
    name_by_mk = {_mk(it["name"]): it["name"] for it in starters + subs if it.get("name")}
    entrou_min = {_mk(s["in"]): s["minute"] for s in game_subs if s.get("in")}
    saiu_min = {_mk(s["out"]): s["minute"] for s in game_subs if s.get("out")}
    partner_of = {}
    for s in game_subs:
        if s.get("in") and s.get("out"):
            ki, ko = _mk(s["in"]), _mk(s["out"])
            # guarda o nome de exibição do parceiro (do lineup se existir; senão o do commentary)
            partner_of[ki] = name_by_mk.get(ko, _clean_person_name(s["out"]))
            partner_of[ko] = name_by_mk.get(ki, _clean_person_name(s["in"]))

    roster_names = [it["name"] for it in starters + subs if it.get("name")]

    def resolve_name(ply):
        ply = _clean_person_name(ply)
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
            et, ply = e.get("event_type"), _mk(resolve_name(e.get("player")))
            if not ply:
                continue
            if et == "cartao_vermelho":
                cards_of[ply] = "vermelho"
            elif et == "cartao_amarelo" and cards_of.get(ply) != "vermelho":
                cards_of[ply] = "vermelho" if cards_of.get(ply) == "amarelo" else "amarelo"
            elif et in ("gol", "gol_penalti"):
                goals_of[ply] = goals_of.get(ply, 0) + 1

    pstats_map = _player_stats_for(mid, team, date, opponent)
    for it in starters + subs:
        nm = it.get("name")
        k = _mk(nm)
        if k in entrou_min:
            it["entered"] = entrou_min[k]
        if k in saiu_min:
            it["exited"] = saiu_min[k]
        if k in partner_of:
            it["sub_with"] = partner_of[k]
        if k in cards_of:
            it["card"] = cards_of[k]
        if k in goals_of:
            it["goals"] = goals_of[k]
        if nm in pstats_map:
            # só guarda chaves com valor, p/ o card não mostrar campos vazios
            it["stats"] = {k: v for k, v in pstats_map[nm].items() if v is not None}
            if it["stats"].get("own_goals"):
                it["own_goal"] = it["stats"]["own_goals"]  # marca negativa no card

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
            "hl_names": [x for x in (entra, saiu) if x],
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
        match_date = str(m.get("date", ""))[:10]
        lineup = _build_team_lineup(mid, _team, match_date, opp)
        formation, starters, subs = lineup["formation"], lineup["starters"], lineup["subs"]
        opp_lineup = _build_team_lineup(mid, opp, match_date, _team)

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
            "match_n": match_snapshot_n.get(mid),
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
    player_detail_source = _pfeatures if not _pfeatures.empty else _pstats
    ps = player_detail_source[player_detail_source["team"] == _team]
    roster_team = _rosters[_rosters["team"] == _team] if not _rosters.empty else pd.DataFrame()
    roster_keys = set(roster_team["player_name"].dropna().map(_name_key_exact)) if not roster_team.empty and "player_name" in roster_team.columns else set()
    roster_count = len(roster_keys)
    players = []
    if not ps.empty or not roster_team.empty:
        pos_by_name: dict[str, str] = {}
        num_by_name: dict[str, int] = {}

        def _mode_pos(df: pd.DataFrame, col: str) -> dict[str, str]:
            out = {}
            if df.empty or col not in df.columns:
                return out
            for nm, grp in df.groupby("player_name", dropna=True):
                vals = [
                    _clean_pos(v) for v in grp[col].tolist()
                    if _clean_pos(v) and _clean_pos(v).upper() != "SUB"
                ]
                if vals:
                    out[_name_key_exact(nm)] = pd.Series(vals).value_counts().index[0]
            return out

        def _mode_num(df: pd.DataFrame, col: str) -> dict[str, int]:
            out = {}
            if df.empty or col not in df.columns:
                return out
            for nm, grp in df.groupby("player_name", dropna=True):
                vals = [_num(v) for v in grp[col].tolist()]
                vals = [v for v in vals if v is not None]
                if vals:
                    out[_name_key_exact(nm)] = int(pd.Series(vals).value_counts().index[0])
            return out

        if not _lineups.empty:
            lineup_team = _lineups[_lineups["team"] == _team]
            pos_by_name.update(_mode_pos(lineup_team, "position"))
            num_by_name.update(_mode_num(lineup_team, "shirt_number"))
        if not roster_team.empty and "squad_position" in roster_team.columns:
            # No elenco agregado, prioriza a função de convocação. A posição de
            # escalação é tática e pode listar pontas como AM-L/AM-R em um jogo.
            pos_by_name.update(_mode_pos(roster_team, "squad_position"))
            for key, num in _mode_num(roster_team, "shirt_number").items():
                num_by_name.setdefault(key, num)
        if not _p365.empty:
            p365_team = _p365[_p365["team"] == _team]
            for col in ("formation_position", "position"):
                for key, pos in _mode_pos(p365_team, col).items():
                    pos_by_name.setdefault(key, pos)
        else:
            p365_team = pd.DataFrame()

        stat_cols = [
            "jogos", "gols", "assist", "chutes", "no_alvo", "amarelos", "vermelhos", "defesas", "faltas", "faltas_sofridas", "impedimentos", "gols_contra",
            "xg", "xa", "xgot", "passes_chave", "gr_chances_criadas", "gr_chances_perdidas", "gr_chances_convertidas", "dribles",
            "desarmes", "interceptacoes", "cortes", "recuperacoes", "duelos", "bloqueios",
            "xgp", "penaltis_defendidos", "bolas_altas", "socos",
        ]
        if not ps.empty:
            _og_agg = ("own_goals", "sum") if "own_goals" in ps.columns else ("goals", lambda s: 0)
            agg_spec = {
                "jogos": ("appearances", "sum"), "gols": ("goals", "sum"), "assist": ("assists", "sum"),
                "chutes": ("shots", "sum"), "no_alvo": ("shots_on_target", "sum"),
                "amarelos": ("yellow_cards", "sum"), "vermelhos": ("red_cards", "sum"),
                "defesas": ("saves", "sum"),
                "faltas": ("fouls_committed", "sum"), "faltas_sofridas": ("fouls_drawn", "sum"),
                "impedimentos": ("offsides", "sum"),
                "gols_contra": _og_agg,
                "xg": ("expected_goals", "sum"), "xa": ("expected_assists", "sum"), "xgot": ("expected_goals_on_target", "sum"),
                "passes_chave": ("key_passes", "sum"), "gr_chances_criadas": ("big_chances_created", "sum"),
                "gr_chances_perdidas": ("big_chances_missed", "sum"), "gr_chances_convertidas": ("big_chances_scored", "sum"),
                "dribles": ("dribbles_won", "sum"), "desarmes": ("tackles_won", "sum"),
                "interceptacoes": ("interceptions", "sum"), "cortes": ("clearances", "sum"),
                "recuperacoes": ("ball_recovery", "sum"), "bloqueios": ("shots_blocked", "sum"),
                "xgp": ("expected_goals_prevented", "sum"), "penaltis_defendidos": ("penalties_saved", "sum"),
                "bolas_altas": ("high_claims", "sum"), "socos": ("punches", "sum"),
            }
            available_agg = {out_col: spec for out_col, spec in agg_spec.items() if spec[0] in ps.columns}
            agg = ps.groupby("player_name", dropna=True).agg(**available_agg).reset_index()
            if {"ground_duels_won", "aerial_duels_won"}.issubset(ps.columns):
                duels = (
                    ps.assign(_duels=pd.to_numeric(ps["ground_duels_won"], errors="coerce").fillna(0) + pd.to_numeric(ps["aerial_duels_won"], errors="coerce").fillna(0))
                    .groupby("player_name", dropna=True)["_duels"].sum()
                    .rename("duelos")
                    .reset_index()
                )
                agg = agg.merge(duels, on="player_name", how="left")
        else:
            agg = pd.DataFrame(columns=["player_name", *stat_cols])
        for col in stat_cols:
            if col not in agg.columns:
                agg[col] = 0
        if not roster_team.empty and "player_name" in roster_team.columns:
            present = set(agg["player_name"].map(_name_key_exact)) if not agg.empty else set()
            roster_missing = roster_team[
                roster_team["player_name"].notna()
                & ~roster_team["player_name"].map(_name_key_exact).isin(present)
            ][["player_name"]].drop_duplicates()
            if not roster_missing.empty:
                for col in stat_cols:
                    roster_missing[col] = 0
                agg = pd.concat([agg, roster_missing], ignore_index=True)
        # ordena: gols, assistências, jogos
        agg = agg.sort_values(["gols", "assist", "jogos"], ascending=False)
        for _, p in agg.iterrows():
            pkey = _name_key_exact(p["player_name"])
            pos_raw = pos_by_name.get(pkey)
            pos_group = _position_group(pos_raw)
            # nota de atuação média: do CANONICAL (fonte única, já casada por
            # match+nome em _attach_player_rating) — substitui o casamento 365
            # próprio do dashboard, que dava valores divergentes.
            rating_media = None
            rating_jogos = 0
            if not player_detail_source.empty and "rating" in player_detail_source.columns:
                cps_p = player_detail_source[
                    (player_detail_source["team"] == _team)
                    & (player_detail_source["player_name"] == p["player_name"])
                ]
                ratings = pd.to_numeric(cps_p.get("rating"), errors="coerce").dropna() if not cps_p.empty else pd.Series(dtype=float)
                if len(ratings):
                    rating_media = round(float(ratings.mean()), 1)
                    rating_jogos = int(len(ratings))
            players.append({
                "name": p["player_name"],
                "num": num_by_name.get(pkey),
                "pos_code": _clean_pos(pos_raw) or None,
                "pos": _position_label(pos_raw),
                "pos_group": pos_group,
                "pos_order": _POS_GROUP_ORDER.get(pos_group, 99),
                "in_roster": (pkey in roster_keys) if roster_keys else True,
                "rating_media": rating_media,
                "rating_jogos": rating_jogos,
                "jogos": _num(p["jogos"]), "gols": _num(p["gols"]), "assist": _num(p["assist"]),
                "chutes": _num(p["chutes"]), "no_alvo": _num(p["no_alvo"]),
                "amarelos": _num(p["amarelos"]), "vermelhos": _num(p["vermelhos"]),
                "defesas": _num(p["defesas"]),
                "faltas": _num(p["faltas"]), "faltas_sofridas": _num(p["faltas_sofridas"]),
                "impedimentos": _num(p["impedimentos"]),
                "gols_contra": _num(p.get("gols_contra", 0)),
                "xg": _num(p.get("xg"), 2), "xa": _num(p.get("xa"), 2), "xgot": _num(p.get("xgot"), 2),
                "passes_chave": _num(p.get("passes_chave")), "gr_chances_criadas": _num(p.get("gr_chances_criadas")),
                "gr_chances_perdidas": _num(p.get("gr_chances_perdidas")), "gr_chances_convertidas": _num(p.get("gr_chances_convertidas")),
                "dribles": _num(p.get("dribles")), "desarmes": _num(p.get("desarmes")),
                "interceptacoes": _num(p.get("interceptacoes")), "cortes": _num(p.get("cortes")),
                "recuperacoes": _num(p.get("recuperacoes")), "duelos": _num(p.get("duelos")),
                "bloqueios": _num(p.get("bloqueios")), "xgp": _num(p.get("xgp"), 2),
                "penaltis_defendidos": _num(p.get("penaltis_defendidos")), "bolas_altas": _num(p.get("bolas_altas")),
                "socos": _num(p.get("socos")),
            })

    # — resumo de scores + campanha (snapshot mais recente)
    scores = {}
    rank = None
    campanha = {}
    estilo = {}
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
        # — estilo de jogo: flag + 4 eixos (0-100, 50=média) + stats brutas que
        # justificam cada eixo (mostradas na aba Resumo do modal do time).
        _j = max(srow.get("jogos", 1) or 1, 1)
        def _pg(col):  # média por jogo de uma coluna acumulada
            v = srow.get(col)
            return _num(v / _j, 1) if v is not None and not pd.isna(v) else None
        _afin = srow.get("estilo_afinidades")
        try:
            afinidades = json.loads(_afin) if _afin is not None and not pd.isna(_afin) else {}
        except (TypeError, ValueError):
            afinidades = {}
        _det = srow.get("estilo_detalhe")
        try:
            detalhe = json.loads(_det) if _det is not None and not pd.isna(_det) else {}
        except (TypeError, ValueError):
            detalhe = {}
        estilo = {
            "flag": str(srow.get("estilo_jogo")) if srow.get("estilo_jogo") is not None and not pd.isna(srow.get("estilo_jogo")) else None,
            "afinidades": afinidades,  # {arquétipo: 0-100}
            "detalhe": detalhe,        # {arquétipo: [{metrica,valor,meta,score,direcao}]}
            "posse": _num(srow.get("estilo_posse"), 1),
            "pressao": _num(srow.get("estilo_pressao"), 1),
            "verticalidade": _num(srow.get("estilo_verticalidade"), 1),
            "largura": _num(srow.get("estilo_largura"), 1),
            # stats brutas por jogo que alimentam os eixos / arquétipos
            "posse_media": _num(srow.get("posse_media"), 1),
            "passes_pj": _pg("passes"),
            "precisao": _num((srow.get("precisao_passes_media") or 0) * 100, 0),
            "dribles_pj": _pg("dribbles_won"),
            "key_passes_pj": _pg("key_passes"),
            "cruzamentos_pj": _pg("accurate_crosses"),
            "chutes_pj": _pg("chutes"),
            "no_alvo_pj": _pg("chutes_no_alvo"),
            "gols_pj": _pg("gols_pro"),
            "clearances_pj": _pg("clearances"),
            "chutes_sofridos_pj": _pg("chutes_sofridos"),
        }

    # — fase atual (do último jogo) e flag de eliminada
    stage_now = jogos_list[-1]["stage"] if jogos_list else None
    jogos_finalizados = sum(1 for j in jogos_list if j.get("finalizado"))

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
        "n_jogos": jogos_finalizados,
        "group": TEAM_GROUP.get(_team),
        "confed": confed,
        "stage_now": stage_now,
        "scores": scores,
        "campanha": campanha,
        "estilo": estilo,
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
        "roster_count": roster_count or len(players),
        "players": players,
    }

teams_detail_json = json.dumps(teams_detail, ensure_ascii=False)

# Metadados de fase por snapshot — para colorir e agrupar os dots
matches = matches_df

STAGE_META = {
    "fase_de_grupos":   {"label": "Fase de Grupos",    "color": "#3b82f6"},
    "dezesseis_avos":   {"label": "16-avos de Final",  "color": "#8b5cf6"},
    "oitavas_de_final": {"label": "Oitavas de Final",  "color": "#a855f7"},
    "quartas_de_final": {"label": "Quartas de Final",  "color": "#f59e0b"},
    "semifinal":        {"label": "Semifinais",        "color": "#ef4444"},
    "terceiro_lugar":   {"label": "Disputa 3º Lugar",  "color": "#6b7280"},
    "final":            {"label": "Final",             "color": "#f5c542"},
}

ROUND_LABELS = {
    ("fase_de_grupos", 1): "Grupos · Rodada 1",
    ("fase_de_grupos", 2): "Grupos · Rodada 2",
    ("fase_de_grupos", 3): "Grupos · Rodada 3",
    ("dezesseis_avos",   4): "16-avos de Final",
    ("oitavas_de_final", 5): "Oitavas de Final",
    ("quartas_de_final", 6): "Quartas de Final",
    ("semifinal",        7): "Semifinais",
    ("terceiro_lugar",   8): "Disputa 3º Lugar",
    ("final",            9): "Final",
}

# match_id → número do snapshot real, se já processado. Usa o DATA gerado a
# partir da timeline, não a posição do match_order persistido, porque a ordem
# canônica pode ser corrigida sem mudar imediatamente os arquivos antigos.
snapshot_n_by_mid = {frame["match_id"]: int(n) for n, frame in data.items()}

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
    elif status == "finalizado":
        dot_status = "missing"
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

round_end_orders = {}
phase_end_orders = {}
for item in snapshot_meta:
    if item.get("stage") == "fase_de_grupos":
        round_end_orders[item["round"]] = item["order"]
    else:
        phase_end_orders[item["stage"]] = item["order"]
for item in snapshot_meta:
    item["round_end"] = item.get("stage") == "fase_de_grupos" and item["order"] == round_end_orders.get(item["round"])
    item["phase_end"] = item.get("stage") != "fase_de_grupos" and item["order"] == phase_end_orders.get(item["stage"])

snapshot_meta_json = json.dumps(snapshot_meta, ensure_ascii=False)
snapshot_order_json = json.dumps([m["n"] for m in snapshot_meta if m["n"] is not None], ensure_ascii=False)

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
        ("xg_por_jogo", "xG (Gols Esperados)"),
        ("chutes_por_jogo", "Chutes"),
        ("chutes_no_alvo_por_jogo", "No Alvo"),
        ("precisao_chute", "Precisão de Chute %"),
        ("escanteios_por_jogo", "Escanteios"),
    ]),
    ("Defesa · Média/jogo", "tt-col-defesa", [
        ("gols_contra_por_jogo", "Gols Sofridos"),
        ("xgp_por_jogo", "xGP (Gols Evitados)"),
        ("chutes_sofridos_por_jogo", "Chutes Sofridos"),
        ("shots_blocked_por_jogo", "Bloqueios"),
        ("duels_won_por_jogo", "Duelos Ganhos"),
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
    # Estilo de jogo NÃO entra no painel de métricas do card — virava sopa
    # visual no espaço estreito. A flag (estilo_jogo) + o "porquê" aparecem só
    # no cabeçalho do modal (ver buildCardHeader / styleWhy); os 4 eixos
    # detalhados ficam nos relatórios Markdown da seleção.
]

# Métricas onde menor = melhor (barra mais comprida = mais destaque negativo)
LOWER_IS_BETTER = {
    "gols_contra", "gols_contra_por_jogo", "chutes_sofridos_por_jogo",
    "faltas_por_jogo", "amarelos_por_jogo", "vermelhos_por_jogo",
}

metric_groups_json = json.dumps(METRIC_GROUPS, ensure_ascii=False)
lower_is_better_json = json.dumps(list(LOWER_IS_BETTER), ensure_ascii=False)
snapshot_meta_json_var = snapshot_meta_json  # alias para usar no f-string
snapshot_order_json_var = snapshot_order_json

# Métricas relacionadas: ao selecionar uma, as outras ficam destacadas no card
METRIC_RELATIONS: dict[str, list[str]] = {
    # ── score_resultado ← aproveitamento_ponderado + saldo_gols/jogo
    "score_resultado":         ["aproveitamento", "pontos", "saldo_gols", "gols_pro", "gols_contra", "score_geral"],
    "aproveitamento":          ["pontos", "saldo_gols", "score_resultado"],
    "pontos":                  ["aproveitamento", "saldo_gols", "score_resultado"],
    "saldo_gols":              ["gols_pro", "gols_contra", "aproveitamento", "score_resultado"],
    "gols_pro":                ["saldo_gols", "gols_por_jogo", "score_resultado", "score_ataque"],
    "gols_contra":             ["saldo_gols", "gols_contra_por_jogo", "jogos_sem_sofrer_gol", "score_resultado", "score_defesa"],

    # ── score_ataque ← gols/jogo + xG/jogo (qualidade) + chutes_no_alvo/jogo (× contexto adversário)
    "score_ataque":            ["gols_por_jogo", "xg_por_jogo", "chutes_no_alvo_por_jogo", "score_eficiencia"],
    "gols_por_jogo":           ["gols_pro", "xg_por_jogo", "chutes_no_alvo_por_jogo", "precisao_chute", "score_ataque", "score_eficiencia"],
    "xg_por_jogo":             ["gols_por_jogo", "chutes_no_alvo_por_jogo", "score_ataque", "score_eficiencia"],
    "chutes_no_alvo_por_jogo": ["chutes_por_jogo", "precisao_chute", "gols_por_jogo", "score_ataque", "score_eficiencia"],
    "chutes_por_jogo":         ["chutes_no_alvo_por_jogo", "precisao_chute", "escanteios_por_jogo"],
    "escanteios_por_jogo":     ["chutes_por_jogo", "key_passes_por_jogo"],

    # ── score_eficiencia ← gols/chute (precisao_chute) + gols vs xG + chutes_no_alvo/chute + key_passes/jogo
    "score_eficiencia":        ["precisao_chute", "xg_por_jogo", "chutes_no_alvo_por_jogo", "gols_por_jogo", "key_passes_por_jogo", "score_ataque"],
    "precisao_chute":          ["chutes_por_jogo", "chutes_no_alvo_por_jogo", "gols_por_jogo", "score_eficiencia"],
    "key_passes_por_jogo":     ["gols_por_jogo", "escanteios_por_jogo", "score_eficiencia", "score_controle"],

    # ── score_defesa ← gols sofridos/jogo (eixo dominante, gol contra pesa +) +
    #    QUALIDADE defensiva (xGP, bloqueios, duelos) ponderada pela força do adversário (Elo)
    "score_defesa":            ["gols_contra_por_jogo", "gols_contra", "chutes_sofridos_por_jogo", "xgp_por_jogo", "shots_blocked_por_jogo", "duels_won_por_jogo"],
    "gols_contra_por_jogo":    ["gols_contra", "chutes_sofridos_por_jogo", "score_defesa"],
    "chutes_sofridos_por_jogo":["gols_contra_por_jogo", "score_defesa", "shots_blocked_por_jogo"],
    "xgp_por_jogo":            ["gols_contra_por_jogo", "defesas_por_jogo", "score_defesa"],
    "shots_blocked_por_jogo":  ["chutes_sofridos_por_jogo", "score_defesa"],
    "duels_won_por_jogo":      ["score_defesa", "chutes_sofridos_por_jogo"],
    "defesas_por_jogo":        ["chutes_sofridos_por_jogo", "gols_contra_por_jogo", "xgp_por_jogo"],
    "jogos_sem_sofrer_gol":    ["gols_contra_por_jogo", "gols_contra"],

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

    # defesa: clean sheet e defesas do goleiro são CONSEQUÊNCIA da solidez, não
    # insumo direto do score (que usa gols sofridos + volume × Elo do adversário).
    "score_defesa":            ["jogos_sem_sofrer_gol", "defesas_por_jogo", "faltas_por_jogo"],
    "gols_contra_por_jogo":    ["faltas_por_jogo", "jogos_sem_sofrer_gol"],
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
        "title": "Resultado",
        "role": "Desempenho no placar",
        "desc": "Resume o que a seleção já converteu em campanha: pontos, saldo e gols marcados.",
        "detail": "É o componente mais determinante porque confirma produção em resultado. Vitórias e empates ganham mais contexto quando vêm contra adversários competitivos.",
        "good": "prioriza pontuação consistente, saldo positivo e impacto real no jogo",
    },
    "score_ataque": {
        "title": "Ataque",
        "role": "Produção ofensiva",
        "desc": "Avalia quanto a seleção cria e qual é a qualidade das chances, além dos gols já marcados.",
        "detail": "Gols continuam sendo o sinal principal, mas chances claras, xG e chutes no alvo ajudam a separar pressão produtiva de volume sem perigo.",
        "good": "prioriza criação de chances relevantes, presença na área e finalizações perigosas",
    },
    "score_defesa": {
        "title": "Defesa",
        "role": "Solidez sem a bola",
        "desc": "Mede a capacidade de proteger o gol, limitar chances claras e resistir contra adversários fortes.",
        "detail": "Gols sofridos definem a base da nota. Dentro dessa faixa, pesam ações que indicam controle defensivo: duelos ganhos, bloqueios, xGP e contexto do rival.",
        "good": "prioriza poucos gols sofridos, proteção de área e resposta eficiente à pressão",
    },
    "score_eficiencia": {
        "title": "Eficiência",
        "role": "Aproveitamento das chances",
        "desc": "Mostra se a seleção transforma suas oportunidades em gols com precisão e tomada de decisão.",
        "detail": "Diferencia volume de aproveitamento. Conversão, pontaria e gols acima do esperado indicam um ataque que não desperdiça as melhores chances.",
        "good": "prioriza conversão alta, boa pontaria e decisões limpas no último terço",
    },
    "score_controle": {
        "title": "Controle",
        "role": "Gestão do jogo",
        "desc": "Observa como a seleção sustenta posse, circula a bola e reduz instabilidade durante a partida.",
        "detail": "Tem peso menor porque posse, sozinha, não vence jogo. Ainda assim, ajuda a identificar equipes que controlam ritmo, território e tomada de risco.",
        "good": "prioriza circulação segura, posse produtiva e capacidade de ditar o ritmo",
    },
    "score_forca_relativa": {
        "title": "Força Relativa",
        "role": "Qualidade da campanha",
        "desc": "Contextualiza o desempenho pela força dos adversários enfrentados e pela evolução do rating da seleção.",
        "detail": "No início pesa menos porque as seleções partem próximas. Conforme a Copa avança, bons resultados contra rivais fortes passam a diferenciar melhor as campanhas.",
        "good": "prioriza desempenho sustentado contra adversários de maior dificuldade",
    },
    "score_disciplina": {
        "title": "Disciplina",
        "role": "Risco disciplinar",
        "desc": "Mostra o quanto faltas e cartões atrapalham o time.",
        "detail": "É informativo e normalmente fica fora do peso principal quando não aparece nos pills. Vermelho pesa mais que amarelo.",
        "good": "favorece times que competem sem se expor a punições",
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
  cursor: pointer;
  font-family: inherit;
  appearance: none;
}}
.w-pill:hover {{ border-color: #58a6ff; background: #1a2233; }}
.w-pill.open {{ border-color: #58a6ff; background: #1a2233; }}
.w-pill .w-name {{ color: #c8d3e0; font-weight: 600; }}
.w-pill .w-val  {{ color: #58a6ff; font-weight: 700; }}
/* tooltip do peso — abre PARA BAIXO (os pills ficam no topo da tela) */
.w-pill .w-tip {{
  display: none;
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(180deg, #161d27 0%, #0d1117 100%);
  border: 1px solid #2b3950;
  border-radius: 8px;
  padding: 14px;
  width: min(520px, calc(100vw - 32px));
  white-space: normal;
  z-index: 20000;
  box-shadow: 0 18px 46px rgba(0,0,0,0.85), 0 0 0 1px rgba(88,166,255,0.10);
  pointer-events: none;
}}
.w-pill.open .w-tip {{ display: block; pointer-events: auto; }}
.w-tip::before {{
  content: ""; position: absolute; top: -6px; left: 50%; transform: translateX(-50%) rotate(45deg);
  width: 10px; height: 10px; background: #161d27; border-left: 1px solid #2b3950; border-top: 1px solid #2b3950;
}}
.w-pill:first-child .w-tip {{ left: 0; transform: none; }}
.w-pill:first-child .w-tip::before {{ left: 44px; transform: rotate(45deg); }}
.w-pill:last-child .w-tip {{ left: auto; right: 0; transform: none; }}
.w-pill:last-child .w-tip::before {{ left: auto; right: 44px; transform: rotate(45deg); }}
.w-tip-head {{
  display: flex; align-items: flex-start; justify-content: space-between; gap: 14px;
  margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #263241;
}}
.w-tip-title {{ font-size: 0.74rem; font-weight: 900; color: #79c0ff; text-transform: uppercase; letter-spacing: 0.8px; }}
.w-tip-role {{ color: #9aa4b2; font-size: 0.68rem; font-weight: 700; margin-top: 3px; }}
.w-tip-weight {{
  min-width: 58px; text-align: right; color: #e6edf3; font-size: 1.15rem; font-weight: 900;
  font-variant-numeric: tabular-nums; line-height: 1;
}}
.w-tip-weight span {{ display: block; margin-top: 3px; color: #6b7280; font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.5px; }}
.w-tip-desc  {{ font-size: 0.79rem; color: #d6dee8; line-height: 1.42; margin-bottom: 7px; }}
.w-tip-detail {{ color: #9aa4b2; font-size: 0.72rem; line-height: 1.42; margin-bottom: 10px; }}
.w-tip-good {{
  border: 1px solid #1f6feb55; background: #1f6feb16; color: #b7dcff;
  border-radius: 7px; padding: 8px 9px; font-size: 0.71rem; font-weight: 700; margin-bottom: 11px; line-height: 1.35;
}}
.w-tip-good::before {{
  content: "Leitura";
  display: block; color: #79c0ff; font-size: 0.56rem; font-weight: 900;
  text-transform: uppercase; letter-spacing: 0.7px; margin-bottom: 3px;
}}
.w-tip-metrics {{ display: grid; grid-template-columns: repeat(4, minmax(88px, 1fr)); gap: 6px; align-items: stretch; }}
.w-tip-metrics::before {{
  content: "Indicadores";
  grid-column: 1 / -1; color: #6b7280; font-size: 0.56rem; font-weight: 900;
  text-transform: uppercase; letter-spacing: 0.7px; margin-bottom: -1px;
}}
.w-tip-metrics span {{
  display: inline-flex; align-items: center; justify-content: center; min-width: 0;
  background: #0f2418; border: 1px solid #1f6f3a; color: #8de09f;
  border-radius: 6px; padding: 5px 6px; font-size: 0.62rem; font-weight: 800;
  text-align: center; line-height: 1.15; word-break: break-word; hyphens: auto;
}}
/* chips com glossário: cursor de ajuda + sublinhado pontilhado discreto sinalizam
   que há explicação ao passar o mouse (tooltip flutuante via data-tip). */
.w-tip-metrics span.has-tip {{ cursor: help; text-decoration: underline dotted #1f6f3a 1px; text-underline-offset: 2px; }}
/* tooltip flutuante (instantâneo, estilizado) — substitui o title nativo, que é
   lento e pouco confiável. Um único elemento reposicionado por JS. */
#chipTip {{
  position: fixed; z-index: 30000; display: none; max-width: 260px;
  background: #0d1117; border: 1px solid #2b3950; border-radius: 8px;
  padding: 8px 10px; font-size: 0.66rem; font-weight: 600; line-height: 1.35;
  color: #c8d3e0; box-shadow: 0 10px 30px rgba(0,0,0,0.8);
  pointer-events: none; white-space: normal;
}}
.weights-help-btn {{
  width: 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid #31557c; background: #10213a; color: #9fd1ff;
  border-radius: 6px; font-size: 0.78rem; font-weight: 900; cursor: pointer;
  margin-right: 4px; flex-shrink: 0;
}}
.weights-help-btn:hover {{ border-color: #58a6ff; background: #16345c; color: #d7ecff; }}
.weights-guide-overlay {{
  position: fixed; inset: 0; z-index: 26000; display: none; align-items: center; justify-content: center;
  background: rgba(1, 4, 9, 0.64); padding: 18px;
}}
.weights-guide {{
  width: min(1320px, calc(100vw - 48px)); height: min(760px, calc(100vh - 48px));
  display: grid; grid-template-rows: auto minmax(0, 1fr);
  background: linear-gradient(180deg, #121923 0%, #0d1117 100%);
  border: 1px solid #2b3950; border-radius: 10px; overflow: hidden;
  box-shadow: 0 24px 80px rgba(0,0,0,0.86), 0 0 0 1px rgba(88,166,255,0.10);
}}
.wg-top {{
  display: flex; align-items: center; justify-content: space-between; gap: 14px;
  padding: 14px 16px; border-bottom: 1px solid #263241; background: #0f1620;
}}
.wg-title {{ min-width: 0; }}
.wg-title strong {{ display: block; color: #e6edf3; font-size: 0.95rem; line-height: 1.15; }}
.wg-title span {{ display: block; color: #8b949e; font-size: 0.72rem; margin-top: 3px; }}
.wg-close {{
  width: 30px; height: 30px; border: 0; border-radius: 6px; background: transparent;
  color: #8b949e; cursor: pointer; font-size: 1.1rem;
}}
.wg-close:hover {{ color: #e6edf3; background: #21262d; }}
.wg-shell {{ min-height: 0; display: grid; grid-template-columns: 160px 1fr; overflow: hidden; }}
.wg-nav {{ padding: 14px 10px; border-right: 1px solid #263241; background: #0b1017; overflow-y: auto; }}
.wg-tab {{
  width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 8px;
  border: 1px solid transparent; background: transparent; color: #9aa4b2;
  padding: 9px 10px; border-radius: 7px; cursor: pointer; font-size: 0.76rem; font-weight: 800;
  text-align: left; margin-bottom: 5px;
}}
.wg-tab:hover {{ color: #d6dee8; background: #161b22; }}
.wg-tab.active {{ color: #79c0ff; background: #1f6feb1f; border-color: #1f6feb55; }}
.wg-body {{ min-width: 0; overflow: hidden; padding: 16px 24px 18px; }}
.wg-section {{ display: none; }}
.wg-section.active {{ display: grid; align-content: start; min-height: 0; }}
.wg-kicker {{ color: #79c0ff; font-size: 0.72rem; font-weight: 900; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 7px; }}
.wg-h2 {{ color: #e6edf3; font-size: 1.34rem; line-height: 1.18; margin-bottom: 9px; }}
.wg-lead {{ color: #c8d3e0; font-size: 0.92rem; line-height: 1.48; max-width: 980px; margin-bottom: 12px; }}
.wg-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 10px 0; }}
.wg-card {{ border: 1px solid #263241; background: #0f1620; border-radius: 8px; padding: 11px 12px; }}
.wg-card b {{ display: block; color: #e6edf3; font-size: 0.9rem; margin-bottom: 6px; }}
.wg-card p {{ color: #9aa4b2; font-size: 0.8rem; line-height: 1.42; }}
.wg-flow {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 10px 0; }}
.wg-flow.single {{ grid-template-columns: minmax(0, 1fr); }}
.wg-step {{ display: grid; grid-template-columns: 34px 1fr; gap: 12px; align-items: start; border: 1px solid #263241; background: #0f1620; border-radius: 8px; padding: 12px; }}
.wg-step-num {{ width: 34px; height: 34px; border-radius: 7px; background: #1f6feb24; border: 1px solid #1f6feb66; color: #9fd1ff; display: inline-flex; align-items: center; justify-content: center; font-weight: 900; font-size: 0.86rem; }}
.wg-step p {{ color: #b8c4d2; font-size: 0.84rem; line-height: 1.45; padding-top: 1px; }}
.wg-why-main {{ min-width: 0; }}
.wg-example-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }}
.wg-example-card {{ border: 1px solid #1f6feb55; background: #10213a; border-radius: 8px; padding: 12px; min-width: 0; }}
.wg-example-card span {{ display: block; color: #79c0ff; font-size: 0.65rem; font-weight: 900; text-transform: uppercase; letter-spacing: 0.7px; margin-bottom: 6px; }}
.wg-example-card b {{ display: block; color: #e6edf3; font-size: 0.92rem; line-height: 1.22; margin-bottom: 6px; }}
.wg-example-card p {{ color: #c9d7e8; font-size: 0.82rem; line-height: 1.42; }}
.wg-weight-donut-card {{ display: grid; justify-items: center; gap: 10px; margin: 8px auto 12px; max-width: 700px; }}
.wg-weight-donut-wrap {{ position: relative; width: min(240px, 56vw); aspect-ratio: 1; }}
.wg-weight-donut {{ width: 100%; height: 100%; display: block; overflow: visible; }}
.wg-weight-donut-bg {{ fill: none; stroke: #0b1017; stroke-width: 18; }}
.wg-weight-arc {{ fill: none; stroke: var(--wg-color); stroke-width: 18; stroke-linecap: butt; filter: drop-shadow(0 1px 1px rgba(0,0,0,0.55)); cursor: pointer; transition: opacity 0.16s ease, stroke-width 0.16s ease; }}
.wg-weight-arc:hover, .wg-weight-arc.active {{ opacity: 1; stroke-width: 20; }}
.wg-weight-arc.dimmed {{ opacity: 0.34; }}
.wg-weight-donut-center {{
  position: absolute;
  inset: 43px;
  display: grid;
  place-items: center;
  text-align: center;
  border: 1px solid #263241;
  border-radius: 999px;
  background: radial-gradient(circle, #101923 0%, #0b1017 72%);
}}
.wg-weight-donut-center b {{ color: #e6edf3; font-size: 1.48rem; line-height: 1; font-weight: 900; font-variant-numeric: tabular-nums; }}
.wg-weight-donut-center span {{ display: block; color: #79c0ff; font-size: 0.62rem; font-weight: 900; text-transform: uppercase; letter-spacing: 0.7px; margin-top: 5px; }}
.wg-weight-panel {{ display: grid; gap: 10px; min-width: 0; width: 100%; }}
.wg-weight-panel-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }}
.wg-weight-panel-head span {{ color: #c8d3e0; font-size: 0.74rem; font-weight: 900; }}
.wg-weight-panel-head b {{ color: #79c0ff; font-size: 0.74rem; font-weight: 900; font-variant-numeric: tabular-nums; }}
.wg-weight-legend {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px 12px; }}
.wg-weight-item {{ min-width: 0; display: grid; grid-template-columns: 10px 1fr auto; align-items: center; gap: 7px; border: 1px solid transparent; background: transparent; border-radius: 7px; padding: 6px 7px; text-align: left; font-family: inherit; cursor: pointer; }}
.wg-weight-item:hover, .wg-weight-item.active {{ border-color: #1f6feb66; background: #1f6feb18; }}
.wg-weight-swatch {{ width: 10px; height: 10px; border-radius: 3px; background: var(--wg-color); box-shadow: 0 0 0 1px #ffffff22 inset; }}
.wg-weight-name {{ color: #c8d3e0; font-size: 0.74rem; font-weight: 800; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.wg-weight-val {{ color: #79c0ff; font-size: 0.74rem; font-weight: 900; font-variant-numeric: tabular-nums; }}
.wg-compare-controls {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 12px 0 14px; }}
.wg-field {{ display: grid; gap: 5px; }}
.wg-field span {{ color: #8b949e; font-size: 0.64rem; font-weight: 900; text-transform: uppercase; letter-spacing: 0.7px; }}
.wg-field select {{
  width: 100%; background: #0b1017; color: #e6edf3; border: 1px solid #30363d;
  border-radius: 7px; padding: 8px 9px; font-size: 0.78rem;
}}
.wg-field select:focus {{ outline: none; border-color: #1f6feb; }}
.wg-snapshot-control {{
  display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 10px;
  border: 1px solid #263241; background: #0f1620; border-radius: 8px; padding: 10px 12px;
  margin: 10px 0 10px;
}}
.wg-snap-btn {{
  width: 28px; height: 28px; border: 1px solid #30363d; background: #161b22;
  color: #c8d3e0; border-radius: 6px; cursor: pointer; font-weight: 900;
}}
.wg-snap-btn:hover {{ border-color: #58a6ff; color: #79c0ff; }}
.wg-snap-mid {{ display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 10px; min-width: 0; }}
.wg-snap-mid input[type=range] {{ width: 100%; }}
.wg-snap-label {{ color: #79c0ff; font-size: 0.76rem; font-weight: 900; white-space: nowrap; font-variant-numeric: tabular-nums; }}
.wg-snapshot-strip {{
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px;
  border: 1px solid #263241; background: #0b1017; border-radius: 8px;
  padding: 8px; margin: 0 0 12px;
}}
.wg-snapshot-pill {{
  min-width: 0; border: 1px solid #263241; background: #0f1620; border-radius: 7px;
  padding: 8px 9px;
}}
.wg-snapshot-pill span {{
  display: block; color: #6b7280; font-size: 0.54rem; font-weight: 900;
  text-transform: uppercase; letter-spacing: 0.65px; margin-bottom: 3px;
}}
.wg-snapshot-pill b {{
  display: block; color: #e6edf3; font-size: 0.8rem; line-height: 1.2;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.wg-snapshot-pill small {{ display: block; color: #8b949e; font-size: 0.68rem; line-height: 1.25; margin-top: 3px; }}
.wg-scoreboard {{
  display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: 10px;
  align-items: stretch; margin: 10px 0 10px;
}}
.wg-team-score {{ border: 1px solid #263241; background: #0f1620; border-radius: 8px; padding: 14px; min-width: 0; }}
.wg-team-score.a {{ border-color: #1f6feb66; }}
.wg-team-score.b {{ border-color: #f59e0b66; }}
.wg-team-name {{ color: #e6edf3; font-size: 1rem; font-weight: 900; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.wg-team-meta {{ color: #8b949e; font-size: 0.68rem; font-weight: 800; margin-top: 2px; }}
.wg-team-kpis {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 11px; }}
.wg-kpi {{ border: 1px solid #263241; background: #0b1017; border-radius: 7px; padding: 8px; }}
.wg-kpi span {{ display: block; color: #8b949e; font-size: 0.55rem; font-weight: 900; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 3px; }}
.wg-kpi b {{ color: #e6edf3; font-size: 1rem; font-weight: 900; font-variant-numeric: tabular-nums; }}
.wg-score-delta {{
  align-self: center; min-width: 86px; border: 1px solid #30363d; border-radius: 8px;
  background: #0b1017; padding: 10px; text-align: center;
}}
.wg-score-delta span {{ display: block; color: #8b949e; font-size: 0.56rem; font-weight: 900; text-transform: uppercase; letter-spacing: 0.6px; }}
.wg-score-delta b {{ display: block; color: #79c0ff; font-size: 1.22rem; font-weight: 900; margin-top: 3px; font-variant-numeric: tabular-nums; }}
.wg-diagnosis {{
  border: 1px solid #1f6feb66; background: #10213a; border-radius: 8px;
  padding: 12px 13px; margin: 10px 0 12px;
}}
.wg-diagnosis-main {{ color: #d7ecff; font-size: 0.84rem; line-height: 1.45; }}
.wg-diagnosis-main b {{ color: #fff; }}
.wg-diagnosis-meta {{ display: flex; flex-wrap: wrap; gap: 7px; margin-top: 10px; }}
.wg-diag-chip {{
  border: 1px solid #31557c; background: #0b1828; color: #b7dcff;
  border-radius: 6px; padding: 6px 8px; font-size: 0.68rem; font-weight: 800;
}}
.wg-diag-chip span {{ color: #79c0ff; text-transform: uppercase; letter-spacing: 0.55px; font-size: 0.56rem; margin-right: 5px; }}
.wg-verdict {{
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 12px 0;
}}
.wg-verdict-card {{ border: 1px solid #263241; background: #0f1620; border-radius: 8px; padding: 11px; }}
.wg-verdict-card span {{ display: block; color: #8b949e; font-size: 0.62rem; font-weight: 900; text-transform: uppercase; letter-spacing: 0.7px; margin-bottom: 4px; }}
.wg-verdict-card b {{ display: block; color: #e6edf3; font-size: 0.86rem; line-height: 1.25; }}
.wg-verdict-card p {{ color: #9aa4b2; font-size: 0.72rem; line-height: 1.38; margin-top: 5px; }}
.wg-compare-table-wrap {{ margin-top: 12px; overflow-x: auto; }}
.wg-compare-table {{
  width: 100%; min-width: 760px; border-collapse: separate; border-spacing: 0 6px;
  table-layout: fixed;
}}
.wg-compare-table th {{
  color: #6b7280; font-size: 0.58rem; font-weight: 900; text-transform: uppercase;
  letter-spacing: 0.6px; text-align: right; padding: 0 10px 2px;
}}
.wg-compare-table th:first-child {{ text-align: left; }}
.wg-compare-table td {{
  background: #0f1620; border-top: 1px solid #263241; border-bottom: 1px solid #263241;
  color: #c8d3e0; font-size: 0.75rem; font-weight: 850; padding: 9px 10px;
  text-align: right; font-variant-numeric: tabular-nums;
}}
.wg-compare-table td:first-child {{
  text-align: left; border-left: 1px solid #263241; border-radius: 7px 0 0 7px;
  color: #e6edf3; font-weight: 900;
}}
.wg-compare-table td:last-child {{ border-right: 1px solid #263241; border-radius: 0 7px 7px 0; }}
.wg-compare-table tr.top td {{ background: #10213a; border-color: #1f6feb66; }}
.wg-compare-weight {{ color: #79c0ff; }}
.wg-compare-delta.pos {{ color: #79c0ff; }}
.wg-compare-delta.neg {{ color: #f0c040; }}
.wg-impact {{ display: grid; grid-template-columns: 1fr 58px; align-items: center; gap: 8px; min-width: 0; }}
.wg-compare-track {{
  position: relative; height: 7px; background: #0b1017; border: 1px solid #263241;
  border-radius: 999px; overflow: hidden; min-width: 0;
}}
.wg-compare-track::before {{
  content: ""; position: absolute; left: 50%; top: -1px; bottom: -1px;
  width: 1px; background: #3b4654; z-index: 1;
}}
.wg-compare-fill {{ height: 100%; border-radius: 999px; }}
.wg-compare-fill.a {{ margin-right: 50%; margin-left: auto; background: linear-gradient(90deg, #79c0ff, #58a6ff); }}
.wg-compare-fill.b {{ margin-left: 50%; background: linear-gradient(90deg, #f0c040, #f59e0b); }}
.wg-compare-val {{ color: #c8d3e0; font-size: 0.72rem; font-weight: 900; text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.wg-compare-note {{ color: #8b949e; font-size: 0.7rem; line-height: 1.42; margin-top: 8px; }}
.wg-component-picker {{ display: flex; gap: 6px; flex-wrap: wrap; margin: 12px 0 14px; }}
.wg-comp-btn {{
  border: 1px solid #30363d; background: #161b22; color: #c8d3e0; border-radius: 6px;
  padding: 6px 8px; font-size: 0.72rem; font-weight: 800; cursor: pointer;
}}
.wg-comp-btn:hover {{ border-color: #58a6ff; color: #79c0ff; }}
.wg-comp-btn.active {{ border-color: #1f6feb; background: #1f6feb24; color: #9fd1ff; }}
.wg-component-card {{ border: 1px solid #2b3950; background: #0f1620; border-radius: 8px; padding: 14px; }}
.wg-component-head {{ display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid #263241; padding-bottom: 10px; margin-bottom: 10px; }}
.wg-component-head h3 {{ color: #79c0ff; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.7px; }}
.wg-component-head span {{ color: #8b949e; font-size: 0.7rem; font-weight: 800; }}
.wg-component-weight {{ color: #e6edf3; font-size: 1.6rem; font-weight: 900; line-height: 1; text-align: right; font-variant-numeric: tabular-nums; }}
.wg-component-card p {{ color: #b8c4d2; font-size: 0.78rem; line-height: 1.48; margin-bottom: 8px; }}
.wg-factor-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 9px; margin-top: 12px; }}
.wg-factor-card {{ border: 1px solid #263241; background: #0b1017; border-radius: 8px; padding: 10px; min-width: 0; }}
.wg-factor-card span {{ display: block; color: #79c0ff; font-size: 0.62rem; font-weight: 900; text-transform: uppercase; letter-spacing: 0.65px; margin-bottom: 5px; }}
.wg-factor-card b {{ display: block; color: #e6edf3; font-size: 0.86rem; line-height: 1.2; margin-bottom: 5px; }}
.wg-factor-card p {{ color: #9aa4b2; font-size: 0.72rem; line-height: 1.35; margin: 0; }}
.wg-factor-note {{ border: 1px solid #31557c; background: #10213a; border-radius: 8px; padding: 10px 12px; color: #c9e6ff; font-size: 0.78rem; line-height: 1.42; margin-top: 12px; }}
.wg-example {{
  border: 1px solid #1f6feb55; background: #1f6feb14; color: #c9e6ff;
  border-radius: 8px; padding: 10px 12px; font-size: 0.75rem; line-height: 1.38; margin: 10px 0 0;
}}
.wg-faq {{ display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; max-width: 1120px; }}
.wg-faq-item {{ border: 1px solid #263241; background: #0f1620; border-radius: 8px; overflow: hidden; }}
.wg-faq-q {{
  width: 100%; display: grid; grid-template-columns: 34px 1fr; gap: 12px; align-items: start;
  border: 0; background: transparent; color: #e6edf3; cursor: pointer;
  font-family: inherit; text-align: left; padding: 12px;
}}
.wg-faq-q:hover {{ background: #121b27; }}
.wg-faq-num {{ width: 34px; height: 34px; border-radius: 7px; background: #1f6feb24; border: 1px solid #1f6feb66; color: #9fd1ff; display: inline-flex; align-items: center; justify-content: center; font-weight: 900; font-size: 0.86rem; }}
.wg-faq-title {{ color: #e6edf3; font-size: 0.94rem; font-weight: 900; line-height: 1.28; padding-top: 6px; }}
.wg-faq-item.open .wg-faq-q {{ border-bottom: 1px solid #263241; background: #10213a; }}
.wg-faq-item.open .wg-faq-title {{ color: #9fd1ff; }}
.wg-faq-a {{ display: none; color: #c8d3e0; font-size: 0.86rem; line-height: 1.5; padding: 12px 14px 14px 58px; }}
.wg-faq-item.open .wg-faq-a {{ display: block; }}
.wg-link-btn {{ border: 0; background: transparent; color: #79c0ff; cursor: pointer; font: inherit; font-weight: 800; }}
.wg-link-btn:hover {{ text-decoration: underline; text-underline-offset: 2px; }}
@media (max-width: 760px) {{
  .weights-guide-overlay {{ padding: 8px; align-items: stretch; }}
  .weights-guide {{ width: calc(100vw - 16px); height: calc(100vh - 16px); }}
  .wg-shell {{ grid-template-columns: 1fr; grid-template-rows: auto 1fr; }}
  .wg-nav {{ display: flex; gap: 6px; overflow-x: auto; border-right: 0; border-bottom: 1px solid #263241; padding: 10px; }}
  .wg-tab {{ width: auto; white-space: nowrap; margin-bottom: 0; }}
  .wg-body {{ padding: 14px; overflow-y: auto; }}
  .wg-grid {{ grid-template-columns: 1fr; }}
  .wg-factor-grid {{ grid-template-columns: 1fr; }}
  .wg-example-grid {{ grid-template-columns: 1fr; }}
  .wg-flow {{ grid-template-columns: 1fr; }}
  .wg-faq {{ grid-template-columns: 1fr; }}
  .wg-weight-legend {{ grid-template-columns: 1fr 1fr; }}
  .wg-snapshot-control {{ grid-template-columns: 1fr; }}
  .wg-snapshot-strip {{ grid-template-columns: 1fr; }}
  .wg-snap-mid {{ grid-template-columns: 1fr; }}
  .wg-compare-controls, .wg-verdict, .wg-scoreboard {{ grid-template-columns: 1fr; }}
  .wg-score-delta {{ width: 100%; }}
  .wg-impact {{ grid-template-columns: 1fr; gap: 3px; }}
}}

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
  --team-dot-label-w: 170px;
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
  flex-shrink: 0; width: var(--team-dot-label-w); min-width: var(--team-dot-label-w);
  overflow: hidden; text-overflow: ellipsis;
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
.phase-label-spacer {{
  visibility: hidden;         /* reserva a largura do rótulo nas linhas dos times */
  height: 0;
  overflow: hidden;
}}
.phase-dots {{
  display: flex;
  gap: var(--dot-gap);
  flex-wrap: nowrap;          /* cada fase numa linha só */
  justify-content: center;    /* bolinhas centralizadas no container (largura = do texto) */
}}
.dot {{
  position: relative;
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
/* finalizado no calendário, mas sem snapshot gerado no dashboard */
.dot-missing {{
  opacity: 0.95;
  cursor: default;
  background: transparent !important;
  border-color: #f59e0b !important;
  box-shadow: 0 0 6px 1px #f59e0b66;
}}
/* dot "apagado" por filtro de seleção (jogo sem o time em foco):
   continua visível (contorno perceptível), só não se destaca */
.dot-faded {{ opacity: 0.4; }}
/* realce do PRIMEIRO (verde) e ÚLTIMO (dourado) jogo do time —
   sem scale (não desloca o layout); só cor + brilho */
.dot-first, .dot-last {{ opacity: 1; }}
.dot-first {{ box-shadow: 0 0 7px 1px #35c46fcc; }}
.dot-last  {{ box-shadow: 0 0 7px 1px #f5c542cc; }}
.dot-round-end, .dot-phase-end {{
  opacity: 1;
  box-shadow: 0 0 0 1px #ffffff88, 0 0 9px 2px #f5c542aa;
}}
.dot-round-end::after, .dot-phase-end::after {{
  content: "⚽";
  position: absolute; left: 50%; top: 50%; transform: translate(-50%, -52%);
  font-size: calc(var(--dot) * 1.25); line-height: 1;
  filter: drop-shadow(0 1px 2px rgba(0,0,0,0.85));
  pointer-events: none;
}}
.dot-phase-end::after {{ content: "🏆"; }}
.dot-round-end.dot-pending,
.dot-phase-end.dot-pending {{
  box-shadow: 0 0 0 1px #6b728088, 0 0 7px 1px #6b728055;
}}
.dot-round-end.dot-pending::after,
.dot-phase-end.dot-pending::after {{
  filter: grayscale(1) opacity(0.62) drop-shadow(0 1px 2px rgba(0,0,0,0.85));
}}
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
  --trajectory-sidebar-w: 190px;
}}
.main.trajectory-bottom {{
  flex-direction: column;
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
/* marca ESTÁTICA: métrica que alimenta o score_geral (vs. apenas informativa).
   Um ponto discreto antes do rótulo — não compete com o verde "entra no cálculo"
   (que é relativo à métrica selecionada), apenas sinaliza "é insumo de qualidade". */
.tt-row.score-input .tt-label::before {{
  content: '▪';
  color: #4a86d8;
  font-size: 0.62rem;
  margin-right: 5px;
  vertical-align: middle;
  opacity: 0.85;
}}
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
.tt-empty {{
  padding: 18px 18px 20px;
  min-height: 132px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 10px;
  color: #8b949e;
  background: linear-gradient(135deg, rgba(13,17,23,0.96), rgba(17,23,32,0.96));
}}
.tt-empty-title {{
  color: #e6edf3;
  font-size: 0.92rem;
  font-weight: 800;
}}
.tt-empty-copy {{
  font-size: 0.76rem;
  line-height: 1.45;
  max-width: 560px;
}}
.tt-empty-actions {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 2px; }}
.tt-empty-btn {{
  border: 1px solid #1f6feb88;
  background: #0d419d55;
  color: #79c0ff;
  border-radius: 6px;
  padding: 6px 9px;
  font-size: 0.72rem;
  font-weight: 800;
  cursor: pointer;
}}
.tt-empty-btn:hover {{ background: #0d419d88; color: #c9e6ff; }}
.tt-empty-hint {{ font-size: 0.68rem; color: #6b7280; }}

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
  width: var(--trajectory-sidebar-w);
  background: #0d1117;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}}
.trajectory-sidebar-resizer {{
  width: 7px;
  flex: 0 0 7px;
  cursor: col-resize;
  background: #0d1117;
  border-left: 1px solid #21262d;
  border-right: 1px solid #21262d;
  position: relative;
}}
.trajectory-sidebar-resizer::before {{
  content: "";
  position: absolute;
  left: 2px;
  top: 50%;
  width: 3px;
  height: 52px;
  transform: translateY(-50%);
  border-radius: 999px;
  background: #30363d;
}}
.trajectory-sidebar-resizer:hover::before,
.trajectory-sidebar-resizer.dragging::before {{
  background: #58a6ff;
}}
.main.trajectory-bottom .sidebar {{
  width: 100%;
  height: 270px;
  border-left: 0;
  border-top: 1px solid #21262d;
}}
.main.trajectory-bottom .sidebar-header {{
  display: grid;
  grid-template-columns: auto minmax(220px, 1fr) minmax(260px, auto) auto;
  align-items: center;
  gap: 10px;
}}
.sidebar-header {{
  padding: 12px 12px 8px;
  border-bottom: 1px solid #21262d;
  flex-shrink: 0;
}}
.sidebar-title-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}}
.traj-open-btn {{
  border: 1px solid #30363d;
  border-radius: 6px;
  background: #161b22;
  color: #c9d1d9;
  padding: 5px 8px;
  font-size: 0.68rem;
  font-weight: 800;
  cursor: pointer;
  white-space: nowrap;
}}
.traj-open-btn:hover {{ border-color: #58a6ff; color: #79c0ff; background: #1f6feb18; }}
.sidebar-header h3 {{
  font-size: 0.68rem;
  color: #8b949e;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 0;
}}
.trajectory-dock,
.trajectory-mode {{
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: #060910;
  border: 1px solid #21262d;
  border-radius: 6px;
  padding: 2px;
}}
.traj-icon-btn,
.traj-mode-btn {{
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #8b949e;
  font-size: 0.68rem;
  font-weight: 800;
  line-height: 1;
  cursor: pointer;
  padding: 5px 6px;
}}
.traj-mode-btn {{ padding: 5px 7px; }}
.traj-icon-btn:hover,
.traj-mode-btn:hover {{ color: #c9d1d9; background: #161b22; }}
.traj-icon-btn.active,
.traj-mode-btn.active {{ color: #58a6ff; background: #1f6feb22; }}
.trajectory-controls {{
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}}
.main.trajectory-bottom .trajectory-controls {{ margin-top: 0; }}
.trajectory-controls select {{
  min-width: 0;
  flex: 1;
  background: #060910;
  border: 1px solid #30363d;
  border-radius: 6px;
  color: #e6edf3;
  padding: 5px 7px;
  font-size: 0.72rem;
}}
.trajectory-controls select:focus {{ outline: none; border-color: #1f6feb; }}
.trajectory-teams {{
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
  margin-top: 8px;
  min-height: 24px;
}}
.main.trajectory-bottom .trajectory-teams {{
  margin-top: 0;
  justify-content: flex-end;
}}
.traj-chip {{
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 100%;
  border: 1px solid #30363d;
  background: #161b22;
  color: #c9d1d9;
  border-radius: 6px;
  padding: 3px 6px;
  font-size: 0.68rem;
  font-weight: 800;
}}
.traj-chip-dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}}
.traj-chip-name {{
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
.traj-chip button {{
  border: 0;
  background: transparent;
  color: #8b949e;
  cursor: pointer;
  font-size: 0.78rem;
  line-height: 1;
  padding: 0 1px;
}}
.traj-chip button:hover {{ color: #e6edf3; }}
.trajectory-empty-chip {{
  color: #6b7280;
  font-size: 0.68rem;
}}
.sidebar-team {{
  font-size: 0.85rem;
  font-weight: 700;
  color: #58a6ff;
  min-height: 18px;
  margin-top: 7px;
}}
.main.trajectory-bottom .sidebar-team {{
  margin-top: 0;
  text-align: right;
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
.trajectory-panel {{
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 100%;
}}
.main.trajectory-bottom .trajectory-panel {{
  display: grid;
  grid-template-columns: minmax(360px, 1fr) minmax(280px, 430px);
  gap: 12px;
  min-height: 0;
}}
.trajectory-chart {{
  position: relative;
  min-height: 138px;
  border: 1px solid #21262d;
  border-radius: 9px;
  background:
    radial-gradient(circle at 18% 14%, rgba(88,166,255,0.08), transparent 32%),
    linear-gradient(180deg, #0b111b 0%, #070b12 100%);
  overflow: hidden;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.035);
}}
.main.trajectory-bottom .trajectory-chart {{ min-height: 190px; }}
.trajectory-chart svg {{
  width: 100%;
  height: 100%;
  display: block;
}}
.trajectory-axis-label {{
  position: absolute;
  left: 14px;
  top: 12px;
  color: #6b7280;
  font-size: 0.62rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
.trajectory-current-label {{
  position: absolute;
  right: 14px;
  top: 12px;
  color: #c9d1d9;
  background: #161b22cc;
  border: 1px solid #30363d;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 0.62rem;
  font-weight: 800;
}}
.trajectory-summary {{
  display: flex;
  flex-direction: column;
  gap: 5px;
}}
.main.trajectory-bottom .trajectory-summary {{
  overflow-y: auto;
  padding-right: 4px;
}}
.trajectory-row {{
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  border: 1px solid #21262d;
  border-radius: 8px;
  background: linear-gradient(180deg, #101722 0%, #0b1018 100%);
  padding: 7px 8px;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.025);
  overflow: hidden;
}}
.trajectory-row::before {{
  content: "";
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--traj-color, #58a6ff);
  opacity: 0.85;
}}
.trajectory-row:hover {{
  border-color: #3b536f;
  background: linear-gradient(180deg, #121c29 0%, #0d1420 100%);
}}
.trajectory-row.focused {{
  border-color: var(--traj-color, #58a6ff);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.025), 0 0 0 1px color-mix(in srgb, var(--traj-color, #58a6ff) 42%, transparent);
}}
.trajectory-row-main {{
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}}
.trajectory-row-dot {{
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}}
.trajectory-row-name {{
  color: #e6edf3;
  font-weight: 800;
  font-size: 0.74rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
.trajectory-row-value {{
  color: var(--traj-color, #dce6f2);
  font-weight: 900;
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}}
.trajectory-row-delta {{
  min-width: 34px;
  text-align: center;
  color: #8b949e;
  background: #060910;
  border: 1px solid #21262d;
  border-radius: 999px;
  padding: 2px 7px;
  font-size: 0.66rem;
  font-weight: 800;
  white-space: nowrap;
}}
.trajectory-row-delta.good {{ color: #4ade80; border-color: #1f6f3a; background: #0d2618; }}
.trajectory-row-delta.bad {{ color: #f87171; border-color: #7f1d1d; background: #2a1114; }}
.trajectory-mini {{
  display: flex;
  flex-direction: column;
  gap: 3px;
}}
.point-compare {{
  border: 1px solid #21262d;
  border-radius: 9px;
  background: linear-gradient(180deg, #0f1620 0%, #0a0f16 100%);
  overflow: hidden;
  margin-top: 8px;
}}
.point-compare.inline {{
  border: 0;
  border-radius: 0;
  background: transparent;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #21262d;
  overflow: visible;
}}
.pcmp-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 10px;
  border-bottom: 1px solid #21262d;
}}
.point-compare.inline .pcmp-head {{
  display: block;
  padding: 0 4px 8px;
  border-bottom: 0;
}}
.pcmp-title {{
  color: #8b949e;
  font-size: 0.68rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 1px;
}}
.trajectory-modal-body .pcmp-title {{
  color: #e6edf3;
  font-size: 0.78rem;
  letter-spacing: 0.6px;
}}
.pcmp-sub {{ color: #8b949e; font-size: 0.68rem; white-space: nowrap; }}
.point-compare.inline .pcmp-sub {{ margin-top: 8px; white-space: normal; line-height: 1.35; }}
.pcmp-empty {{ color: #8b949e; font-size: 0.74rem; line-height: 1.42; padding: 12px; }}
.point-compare.inline .pcmp-empty {{ padding: 4px; font-style: italic; }}
.pcmp-scroll {{ overflow-x: auto; }}
.point-compare-modal .pcmp-scroll {{ overflow-x: hidden; }}
.point-compare.inline .pcmp-scroll {{
  border: 1px solid #21262d;
  border-radius: 8px;
  background: #0f1620;
}}
.pcmp-table {{
  width: 100%;
  min-width: 520px;
  border-collapse: collapse;
  table-layout: fixed;
}}
.pcmp-table th {{
  color: #6b7280;
  font-size: calc(0.58rem * var(--pcmp-scale, 1));
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.55px;
  text-align: center;
  padding: calc(7px * var(--pcmp-scale, 1)) calc(8px * var(--pcmp-scale, 1));
  border-bottom: 1px solid #21262d;
  background: #0b1017;
}}
.pcmp-table th:first-child {{ text-align: left; width: 128px; }}
.pcmp-table td {{
  color: #c8d3e0;
  font-size: calc(0.72rem * var(--pcmp-scale, 1));
  font-weight: 850;
  text-align: center;
  vertical-align: middle;
  padding: calc(8px * var(--pcmp-scale, 1));
  border-bottom: 1px solid #161d27;
  font-variant-numeric: tabular-nums;
}}
.pcmp-table td:first-child {{
  color: #e6edf3;
  text-align: left;
  font-weight: 900;
}}
.pcmp-table tr:last-child td {{ border-bottom: 0; }}
.pcmp-metric-btn {{
  all: unset;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  cursor: pointer;
  color: #e6edf3;
  font-weight: 900;
}}
.pcmp-metric-btn:hover {{ color: #79c0ff; }}
.pcmp-sort-row td:first-child {{
  background:
    linear-gradient(90deg, rgba(88,166,255,0.28), rgba(88,166,255,0.11)) !important;
  color: #f0f6fc;
  box-shadow: inset 3px 0 0 #58a6ff;
}}
.pcmp-sort-row td {{
  background:
    linear-gradient(90deg, rgba(88,166,255,0.16), rgba(88,166,255,0.08)),
    hsl(var(--rank-hue, 214) 58% 22% / var(--rank-alpha, 0.28)) !important;
  border-top: 1px solid rgba(88,166,255,0.36);
  border-bottom-color: rgba(88,166,255,0.36);
}}
.pcmp-sort-row .pcmp-value {{
  color: #f0f6fc;
}}
.pcmp-sort-row .pcmp-order {{
  border-color: rgba(121,192,255,0.62);
}}
.pcmp-sort-chip {{
  flex-shrink: 0;
  border: 1px solid rgba(88,166,255,0.42);
  border-radius: 999px;
  padding: 2px 5px;
  color: #79c0ff;
  font-size: 0.56rem;
  font-weight: 950;
  line-height: 1;
  text-transform: uppercase;
}}
.pcmp-team-head {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  max-width: 100%;
}}
.pcmp-team-dot {{ width: 8px; height: 8px; border-radius: 999px; flex-shrink: 0; }}
.pcmp-team-name {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.pcmp-rank-cell {{
  background:
    linear-gradient(90deg, rgba(8,12,20,0.36), rgba(8,12,20,0.10)),
    hsl(var(--rank-hue, 214) 58% 22% / var(--rank-alpha, 0.18)) !important;
}}
.pcmp-cell-main {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: calc(7px * var(--pcmp-scale, 1));
  width: 100%;
  min-width: 0;
}}
.pcmp-value {{
  color: #dbe7f5;
  font-size: calc(0.74rem * var(--pcmp-scale, 1));
  font-weight: 900;
}}
.pcmp-order {{
  min-width: calc(24px * var(--pcmp-scale, 1));
  padding: calc(2px * var(--pcmp-scale, 1)) calc(5px * var(--pcmp-scale, 1));
  border-radius: 999px;
  border: 1px solid #30363d;
  background: rgba(13,17,23,0.72);
  color: #9aa4b2;
  font-size: calc(0.58rem * var(--pcmp-scale, 1));
  font-weight: 950;
  line-height: 1;
  text-align: center;
}}
.pcmp-rank-cell.rk1 {{
  box-shadow: inset 0 0 0 1px rgba(247,215,116,0.38);
}}
.pcmp-rank-cell.rk1 .pcmp-order {{
  border-color: rgba(247,215,116,0.62);
  background: rgba(247,215,116,0.16);
  color: #ffe28a;
}}
.pcmp-rank-cell.rk2 .pcmp-order {{
  border-color: rgba(190,203,219,0.48);
  background: rgba(190,203,219,0.12);
  color: #dbe7f5;
}}
.pcmp-rank-cell.rk3 .pcmp-order {{
  border-color: rgba(232,165,90,0.48);
  background: rgba(232,165,90,0.12);
  color: #efbd82;
}}
.pcmp-rank-cell.rk-last .pcmp-value {{
  color: #aeb8c6;
}}
.pcmp-note {{
  color: #6b7280;
  font-size: 0.66rem;
  line-height: 1.35;
  padding: 8px 10px 10px;
  border-top: 1px solid #161d27;
}}
.point-compare.inline .pcmp-note {{
  border-top: 0;
  padding: 8px 4px 0;
  font-style: italic;
}}
.trajectory-modal-body .point-compare {{ margin-top: 10px; }}
.trajectory-modal-body .pcmp-table {{ min-width: 700px; }}
.trajectory-modal-body .pcmp-table th:first-child {{ width: 160px; }}
.point-compare-module {{
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #21262d;
}}
.pcmp-module-title {{
  color: #8b949e;
  font-size: 0.68rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 10px;
}}
.pcmp-module-teams {{
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
  min-height: 24px;
  margin-bottom: 8px;
}}
.pcmp-module-summary {{
  color: #58a6ff;
  font-size: 0.82rem;
  font-weight: 900;
  margin-bottom: 10px;
}}
.pcmp-module-empty {{
  color: #8b949e;
  font-size: 0.74rem;
  line-height: 1.42;
  font-style: italic;
  margin-bottom: 10px;
}}
.trajectory-modal.point-compare-modal {{
  width: min(980px, calc(100vw - 120px));
  height: auto;
  min-width: 720px;
  min-height: 0;
  max-height: calc(100vh - 130px);
}}
.point-compare-modal .trajectory-modal-body {{
  flex: 0 1 auto;
  min-height: 0;
}}
.point-compare-modal.is-resized .trajectory-modal-body {{
  flex: 1;
}}
.point-compare-modal.is-resized .point-compare {{
  display: flex;
  flex-direction: column;
  height: 100%;
}}
.point-compare-modal.is-resized .pcmp-scroll {{
  display: flex;
  flex: 1;
  min-height: 0;
}}
.point-compare-modal.is-resized .pcmp-table {{
  height: 100%;
}}
.point-compare-modal.is-resized .pcmp-note {{
  flex: 0 0 auto;
}}
.point-compare-modal .trajectory-modal-title {{
  align-items: flex-start;
  flex-direction: column;
  gap: 2px;
}}
.point-compare-modal .trajectory-modal-title strong {{
  color: #8b949e;
  font-size: 0.68rem;
}}
.point-compare-modal .point-compare {{
  margin: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}}
.point-compare-modal .pcmp-head {{
  display: none;
}}
.point-compare-modal .pcmp-scroll {{
  border: 1px solid #21262d;
  border-radius: 9px;
  background: #0f1620;
}}
.point-compare-modal .pcmp-table {{
  min-width: 0;
}}
.point-compare-modal .pcmp-table th,
.point-compare-modal .pcmp-table td {{
  overflow: hidden;
}}
.point-compare-modal .pcmp-table th:first-child {{
  width: clamp(96px, 14%, 150px);
}}
.point-compare-modal .trajectory-resize-handle {{
  display: block;
}}
.trajectory-modal {{
  position: fixed;
  left: 260px;
  top: 92px;
  width: min(1120px, calc(100vw - 320px));
  height: min(630px, calc((100vw - 320px) * 0.5625), calc(100vh - 130px));
  min-width: 760px;
  min-height: 428px;
  max-width: calc(100vw - 24px);
  max-height: calc(100vh - 24px);
  z-index: 1100;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 10px;
  box-shadow: 0 24px 70px rgba(0,0,0,0.88);
  overflow: hidden;
  flex-direction: column;
}}
.trajectory-resize-handle {{
  position: absolute;
  right: 0;
  bottom: 0;
  width: 22px;
  height: 22px;
  cursor: nwse-resize;
  z-index: 3;
}}
.trajectory-resize-handle::before {{
  content: "";
  position: absolute;
  right: 6px;
  bottom: 6px;
  width: 10px;
  height: 10px;
  border-right: 1px solid #6b7280;
  border-bottom: 1px solid #6b7280;
  box-shadow: 4px 4px 0 -3px #6b7280;
  opacity: 0.85;
}}
.trajectory-modal-bar {{
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 12px 0 14px;
  border-bottom: 1px solid #21262d;
  background: #111720;
  cursor: grab;
}}
.trajectory-modal-bar:active {{ cursor: grabbing; }}
.trajectory-modal-title {{
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}}
.trajectory-modal-title span {{
  color: #e6edf3;
  font-weight: 900;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}}
.trajectory-modal-title strong {{
  color: #58a6ff;
  font-size: 0.78rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
.trajectory-modal-actions {{ display: flex; align-items: center; gap: 6px; }}
.trajectory-modal-toolbar {{
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto auto minmax(260px, 1.2fr);
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid #21262d;
  background: #0b1018;
}}
.trajectory-modal-toolbar select {{
  min-width: 0;
  background: #060910;
  border: 1px solid #30363d;
  border-radius: 6px;
  color: #e6edf3;
  padding: 7px 9px;
  font-size: 0.78rem;
}}
.trajectory-modal-toolbar select:focus {{ outline: none; border-color: #1f6feb; }}
.trajectory-modal-teams {{
  margin-top: 0;
  justify-content: flex-end;
}}
.trajectory-modal-body {{
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 14px;
}}
.trajectory-modal-body .trajectory-panel {{
  display: grid;
  grid-template-columns: minmax(520px, 1fr) minmax(250px, 330px);
  gap: 14px;
  min-height: 100%;
}}
.trajectory-modal-body .trajectory-chart {{
  min-height: 430px;
  height: 100%;
}}
.trajectory-modal-body .trajectory-summary {{
  overflow-y: auto;
  padding-right: 4px;
}}
.trajectory-modal-body .trajectory-row {{
  padding: 10px 11px;
  grid-template-columns: minmax(0, 1fr) auto auto;
}}
.trajectory-modal-body .trajectory-row-name {{ font-size: 0.82rem; }}
.trajectory-modal-body .trajectory-row-value {{ font-size: 0.82rem; }}
.trajectory-modal-body .trajectory-row-delta {{ font-size: 0.72rem; }}
@media (max-width: 980px) {{
  .trajectory-modal {{
    left: 12px;
    top: 80px;
    width: calc(100vw - 24px);
    min-width: 0;
  }}
  .trajectory-modal-toolbar {{
    grid-template-columns: 1fr;
    align-items: stretch;
  }}
  .trajectory-modal-teams {{ justify-content: flex-start; }}
  .trajectory-modal-body .trajectory-panel {{
    grid-template-columns: 1fr;
  }}
  .trajectory-modal-body .trajectory-chart {{ min-height: 280px; }}
}}
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
#viewPlayers {{ flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }}
.teams-toolbar {{
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 12px 20px; border-bottom: 1px solid #21262d; flex-shrink: 0;
}}
.teams-search {{
  background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
  color: #e6edf3; padding: 6px 12px; font-size: 0.82rem; width: 260px;
}}
.teams-search:focus {{ outline: none; border-color: #1f6feb; }}
.team-search-wrap {{ position: relative; flex: 0 0 auto; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; max-width: 560px; }}
.selected-team-chips {{ display: flex; align-items: center; gap: 5px; flex-wrap: wrap; max-width: 320px; }}
.selected-team-chips:empty {{ display: none; }}
.search-team-chip {{
  --chip-color: #58a6ff;
  display: inline-flex; align-items: center; gap: 5px; max-width: 150px;
  border: 1px solid color-mix(in srgb, var(--chip-color) 70%, #30363d);
  background: color-mix(in srgb, var(--chip-color) 18%, #10213a);
  color: #dbeafe;
  border-radius: 6px; padding: 4px 6px; font-size: 0.7rem; font-weight: 800;
}}
.search-team-chip span {{ min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.search-team-chip button {{
  border: 0; background: transparent; color: #8b949e; cursor: pointer;
  padding: 0 1px; line-height: 1; font-size: 0.78rem;
}}
.search-team-chip button:hover {{ color: #e6edf3; }}
.team-suggest {{
  display: none; position: absolute; top: calc(100% + 6px); left: 0;
  width: min(320px, calc(100vw - 24px)); max-height: 280px; overflow: auto;
  background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
  box-shadow: 0 14px 34px rgba(0,0,0,0.65); z-index: 12000; padding: 5px;
}}
.team-suggest.open {{ display: block; }}
.team-suggest-item {{
  width: 100%; display: grid; grid-template-columns: auto 1fr auto; align-items: center;
  gap: 8px; border: 0; background: transparent; color: #e6edf3; text-align: left;
  padding: 8px 9px; border-radius: 6px; cursor: pointer; font-size: 0.8rem;
}}
.team-suggest-item:hover,
.team-suggest-item.active {{ background: #1f6feb22; color: #79c0ff; }}
.team-suggest-item.selected {{ background: #10213a; color: #dbeafe; }}
.team-suggest-flag {{ font-size: 1rem; line-height: 1; }}
.team-suggest-name {{ min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 800; }}
.team-suggest-meta {{ color: #8b949e; font-size: 0.68rem; font-weight: 800; white-space: nowrap; }}
.team-suggest-empty {{ padding: 10px; color: #8b949e; font-size: 0.76rem; }}
.tb-field {{ display: flex; align-items: center; gap: 6px; font-size: 0.72rem; color: #6b7280; white-space: nowrap; }}
.tb-field select {{
  background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
  color: #e6edf3; padding: 5px 8px; font-size: 0.78rem;
}}
.tb-field select:focus {{ outline: none; border-color: #1f6feb; }}
.tb-field.has-suggestion select {{
  border-color: #58a6ff88;
  box-shadow: 0 0 0 1px #1f6feb22 inset, 0 0 0 2px #1f6feb14;
  background-image: var(--suggest-gradient);
  background-repeat: no-repeat;
  background-position: left bottom;
  background-size: 100% 3px;
}}
.tb-field option[data-suggested="1"] {{
  color: #79c0ff;
  font-weight: 800;
}}
.filter-hints {{
  display: inline-flex; align-items: center; gap: 4px; max-width: 190px;
  overflow: hidden; white-space: nowrap;
}}
.filter-hints:empty {{ display: none; }}
.filter-hint {{
  --hint-color: #58a6ff;
  display: inline-flex; align-items: center; gap: 4px; min-width: 0; max-width: 76px;
  color: #dbeafe; background: color-mix(in srgb, var(--hint-color) 18%, #0d1117);
  border: 1px solid color-mix(in srgb, var(--hint-color) 72%, #30363d);
  border-radius: 999px; padding: 2px 6px; font-size: 0.62rem; font-weight: 900;
}}
.filter-hint-dot {{
  width: 7px; height: 7px; border-radius: 999px; flex: 0 0 auto; background: var(--hint-color);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--hint-color) 25%, transparent);
}}
.filter-hint-text {{ min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
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
  --focus-color: #58a6ff;
  background: #0d1117; border: 1px solid #21262d; border-radius: 16px;
  padding: 22px 24px; cursor: pointer;
  transition: border-color 0.15s, transform 0.1s, background 0.15s, box-shadow 0.15s;
}}
/* card do time em FOCO (busca/destacar compartilhado) */
.team-card.tc-focus {{
  border-color: var(--focus-color);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--focus-color) 14%, transparent), transparent 52%),
    #11161f;
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--focus-color) 68%, transparent),
    0 0 28px color-mix(in srgb, var(--focus-color) 26%, transparent),
    0 12px 32px rgba(0,0,0,0.28);
}}
.team-card.tc-focus .tc-rank {{
  color: var(--focus-color);
  background: color-mix(in srgb, var(--focus-color) 18%, #0d1117);
}}
.team-card.tc-focus .tc-metric {{
  border-top-color: color-mix(in srgb, var(--focus-color) 32%, #161b22);
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
.team-card .tc-rank.muted {{ color: #6b7280; background: #161b22; }}
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
  padding: 18px 84px 18px 20px; border-radius: 12px; margin-bottom: 16px;
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
.rs-hero-shirt {{
  position: relative; width: 72px; height: 58px; flex: 0 0 72px;
  display: inline-flex; align-items: center; justify-content: center;
  color: #e6edf3; font-size: 1.15rem; font-weight: 950; font-variant-numeric: tabular-nums;
  isolation: isolate;
}}
.rs-hero-shirt::before {{
  content: ""; position: absolute; inset: 2px 0 0; z-index: 0;
  background: linear-gradient(180deg, var(--shirt-main, #2f81f7), var(--shirt-main, #2f81f7) 62%, var(--shirt-dark, #1158c7));
  border: 1px solid var(--shirt-border, #58a6ff70);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.10), 0 8px 20px rgba(0,0,0,0.28);
  clip-path: polygon(18% 7%, 34% 0, 43% 10%, 57% 10%, 66% 0, 82% 7%, 100% 34%, 82% 49%, 75% 33%, 75% 100%, 25% 100%, 25% 33%, 18% 49%, 0 34%);
}}
.rs-hero-shirt::after {{
  content: ""; position: absolute; top: 5px; left: 31px; width: 10px; height: 8px; z-index: 1;
  border-radius: 0 0 999px 999px; border: 1px solid var(--shirt-border, rgba(13,17,23,0.75)); border-top: 0;
  background: var(--shirt-border, #0d1117);
}}
.rs-hero-shirt .shirt-number {{
  position: relative; z-index: 2; margin-top: 8px; color: var(--shirt-text, #e6edf3);
  text-shadow: none;
}}
.rs-hero-info {{ min-width: 0; }}
.rs-hero-top {{ display: flex; align-items: center; gap: 10px; }}
.rs-hero-name {{ font-size: 1.4rem; font-weight: 900; color: #e6edf3; line-height: 1.1; }}
.rs-hero-rank {{
  font-size: 0.74rem; font-weight: 700; color: #58a6ff;
  background: #1f6feb22; border-radius: 6px; padding: 3px 8px;
}}
.rs-hero-nick {{ font-size: 0.92rem; color: #58a6ff; font-weight: 600; margin-top: 3px; }}
.rs-hero-meta {{ font-size: 0.82rem; color: #8b949e; margin-top: 5px; }}
.rs-team-flag-link {{
  position: absolute; right: 18px; top: 50%; transform: translateY(-50%);
  display: inline-flex; align-items: center; justify-content: center;
  width: 48px; height: 38px; border-radius: 9px;
  border: 1px solid #263241; background: #0d1117; text-decoration: none;
  font-size: 1.75rem; line-height: 1; transition: border-color .12s, background .12s, transform .12s;
}}
.rs-team-flag-link:hover {{
  border-color: #58a6ff; background: #1f6feb18; transform: translateY(-50%) scale(1.04);
}}

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
.pm-kpi-row {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: -4px 0 14px; }}
.pm-kpi {{
  min-width: 0; border: 1px solid #263241; border-radius: 10px; padding: 11px 12px;
  background: #0d1117;
}}
.pm-kpi span {{
  display: block; color: #8b949e; font-size: 0.68rem; font-weight: 800;
  text-transform: uppercase; letter-spacing: 0.55px; margin-bottom: 6px;
}}
.pm-kpi b {{ display: block; color: #e6edf3; font-size: 1.16rem; font-weight: 900; line-height: 1; font-variant-numeric: tabular-nums; }}
.pm-role-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: stretch; }}
.pm-role-grid.two {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
.pm-role-card {{
  min-width: 0; border: 1px solid #21262d; border-radius: 12px; padding: 14px;
  background: #0d1117; display: flex; flex-direction: column;
}}
.pm-role-title {{
  color: #58a6ff; font-size: 0.72rem; font-weight: 900; text-transform: uppercase;
  letter-spacing: 0.7px; margin-bottom: 10px;
}}
.pm-metric-list {{ display: grid; grid-auto-rows: 1fr; gap: 8px; flex: 1; }}
.pm-metric {{
  min-width: 0; border: 1px solid #1c2532; border-radius: 8px; padding: 10px 11px;
  background: #111821; display: grid; grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas: "label value" "note note"; column-gap: 12px; row-gap: 7px;
  align-items: center; min-height: 70px;
}}
.pm-metric.up {{ border-color: #23863655; background: linear-gradient(180deg, #12301f55, #111821 72%); }}
.pm-metric.mid {{ border-color: #1f6feb44; }}
.pm-metric.down {{ border-color: #d2992244; background: linear-gradient(180deg, #35271042, #111821 72%); }}
.pm-metric-label {{ grid-area: label; color: #b8c4d2; font-size: 0.82rem; font-weight: 850; min-width: 0; overflow: visible; text-overflow: clip; white-space: normal; line-height: 1.18; }}
.pm-metric-value {{ grid-area: value; color: #e6edf3; font-size: 1.08rem; font-weight: 950; font-variant-numeric: tabular-nums; white-space: nowrap; text-align: right; }}
.pm-metric-note {{ grid-area: note; min-width: 0; color: #8b949e; font-size: 0.72rem; line-height: 1.28; text-align: left; }}
.pm-discipline-strip {{
  margin-top: 12px; border: 1px solid #21262d; border-radius: 10px; padding: 12px;
  background: #0d1117; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px;
}}
.pm-discipline-item {{
  min-width: 0; display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; align-items: center;
  gap: 9px; border: 1px solid #1c2532; border-radius: 8px; padding: 9px 10px; background: #111821;
}}
.pm-discipline-item .pm-icon {{
  width: 22px; height: 22px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center;
  font-size: 0.78rem; font-weight: 950;
}}
.pm-discipline-item.card-yellow .pm-icon {{ background: #facc15; color: #111827; }}
.pm-discipline-item.card-red .pm-icon {{ background: #ef4444; color: #fff; }}
.pm-discipline-item.foul-made .pm-icon {{ background: #d2992226; color: #f0c040; }}
.pm-discipline-item.foul-won .pm-icon {{ background: #23863626; color: #5ee787; }}
.pm-discipline-item span {{ color: #8b949e; font-size: 0.78rem; white-space: normal; overflow: visible; line-height: 1.15; }}
.pm-discipline-item b {{ color: #e6edf3; font-size: 1.02rem; font-weight: 900; font-variant-numeric: tabular-nums; }}
@media (max-width: 760px) {{
  .pm-kpi-row {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .pm-role-grid, .pm-role-grid.two {{ grid-template-columns: 1fr; }}
  .pm-metric {{ grid-template-columns: minmax(0, 1fr) auto; }}
  .pm-discipline-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}
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
/* — Aba Estilo de jogo (modal do time) — */
.es-tab {{ padding: 2px; }}
.es-hero {{
  display: flex; align-items: center; gap: 16px; padding: 16px 18px;
  background: linear-gradient(135deg, #1f6feb22, #0d111700);
  border: 1px solid #1f6feb44; border-radius: 12px;
}}
.es-hero-flag {{ font-size: 2.4rem; line-height: 1; flex-shrink: 0; }}
.es-hero-nome {{ font-size: 1.5rem; font-weight: 900; color: #e6edf3; line-height: 1.1; }}
.es-hero-glos {{ font-size: 0.9rem; color: #8b949e; margin-top: 4px; }}
.es-help {{
  font-size: 0.8rem; color: #8b949e; line-height: 1.5; margin: 14px 2px 4px;
}}
.es-help b {{ color: #c9d1d9; }}
.es-axes {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px;
}}
@media (max-width: 620px) {{ .es-axes {{ grid-template-columns: 1fr; }} }}
.es-axis {{
  padding: 12px 14px; background: #0d111788;
  border: 1px solid #21262d; border-radius: 10px;
}}
.es-axis-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }}
.es-axis-nome {{ font-size: 0.92rem; font-weight: 700; color: #e6edf3; }}
.es-axis-desc {{ display: block; font-size: 0.72rem; color: #6b7280; margin-top: 1px; }}
.es-axis-lean {{
  font-size: 0.74rem; color: #8b949e; white-space: nowrap; flex-shrink: 0;
  background: #161b22; border: 1px solid #30363d; border-radius: 999px; padding: 3px 10px;
}}
.es-axis-lean b {{ color: #58a6ff; }}
.es-bar {{ display: flex; align-items: center; gap: 8px; margin: 12px 0 10px; }}
.es-bar-low, .es-bar-high {{ font-size: 0.66rem; color: #6b7280; white-space: nowrap; flex-shrink: 0; }}
.es-bar-low {{ text-align: right; width: 72px; }}
.es-bar-high {{ width: 72px; }}
.es-bar-track {{
  position: relative; flex: 1; height: 6px;
  background: linear-gradient(90deg, #21262d, #2d333b, #21262d);
  border-radius: 3px;
}}
.es-bar-mid {{ position: absolute; left: 50%; top: -2px; width: 1px; height: 10px; background: #484f58; }}
.es-bar-dot {{
  position: absolute; top: 50%; width: 12px; height: 12px; background: #58a6ff;
  border-radius: 50%; transform: translate(-50%, -50%);
  box-shadow: 0 0 0 2px #0d1117, 0 0 8px #58a6ff66;
}}
.es-ings {{ display: flex; flex-wrap: wrap; gap: 5px; }}
.es-ing {{
  display: inline-flex; align-items: baseline; gap: 5px; font-size: 0.74rem; color: #8b949e;
  background: #161b22; border-radius: 5px; padding: 2px 8px;
}}
.es-ing-l {{ color: #6b7280; }}
.es-ing b {{ color: #c9d1d9; }}
.es-aviso {{
  font-size: 0.78rem; color: #c9a227; margin-top: 14px; padding: 10px 13px;
  background: #c9a22712; border: 1px solid #c9a22733; border-radius: 8px; line-height: 1.5;
}}
.es-arq-detail {{
  margin-top: 12px; padding: 14px 16px; background: #0d111788;
  border: 1px solid #21262d; border-radius: 12px;
}}
.es-arq-bar-row {{ display: flex; justify-content: space-between; align-items: baseline; }}
.es-arq-afin-lbl {{ font-size: 0.8rem; color: #8b949e; }}
.es-arq-afin-val {{ font-size: 1.2rem; font-weight: 900; color: #58a6ff; }}
.es-arq-bar {{ height: 8px; background: #21262d; border-radius: 4px; overflow: hidden; margin: 7px 0 6px; }}
.es-arq-bar-fill {{
  display: block; height: 100%; border-radius: 4px;
  background: linear-gradient(90deg, #1f6feb, #58a6ff); transition: width 0.35s;
}}
.es-arq-gloss {{ font-size: 0.82rem; color: #8b949e; }}
.es-arq-isflag {{ color: #4ade80; font-weight: 600; }}
.es-am-title {{
  font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px;
  color: #8b949e; margin: 14px 0 8px;
}}
.es-am-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px 10px; }}
@media (max-width: 620px) {{ .es-am-grid {{ grid-template-columns: 1fr; }} }}
.es-am-row {{
  display: flex; justify-content: space-between; align-items: baseline;
  background: #161b22; border-radius: 6px; padding: 6px 11px;
}}
.es-am-lbl {{ font-size: 0.8rem; color: #8b949e; }}
.es-am-val {{ font-size: 0.92rem; font-weight: 700; color: #e6edf3; }}
.es-na {{ font-size: 0.8rem; color: #6b7280; padding: 6px 0; }}
/* métricas valor/meta com barra de progresso */
.es-mm-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; }}
@media (max-width: 620px) {{ .es-mm-grid {{ grid-template-columns: 1fr; }} }}
.es-mm {{ background: #161b22; border-radius: 7px; padding: 7px 11px; }}
.es-mm-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }}
.es-mm-lbl {{ font-size: 0.78rem; color: #8b949e; }}
.es-mm-vals {{ font-size: 0.82rem; color: #e6edf3; white-space: nowrap; }}
.es-mm-vals b {{ color: #e6edf3; }}
.es-mm-sep {{ color: #484f58; }}
.es-mm-meta {{ color: #8b949e; }}
.es-mm-bar {{ height: 5px; background: #0d1117; border-radius: 3px; overflow: hidden; margin-top: 6px; }}
.es-mm-fill {{ display: block; height: 100%; border-radius: 3px; transition: width 0.3s; }}
.es-mm-desc {{ font-size: 0.7rem; color: #6b7280; margin-top: 5px; line-height: 1.35; }}
/* gráfico de perfil: afinidade do time aos 7 arquétipos (substitui os 4 eixos) */
.es-perfil-title {{
  font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px;
  color: #8b949e; margin: 18px 2px 8px;
}}
.es-perfil {{ display: flex; flex-direction: column; gap: 5px; }}
.es-perfil-row {{
  display: grid; grid-template-columns: minmax(235px, 0.36fr) minmax(120px, 0.64fr) 44px; align-items: center; gap: 10px;
  padding: 4px 8px; border-radius: 7px; cursor: pointer; transition: background 0.15s;
}}
@media (max-width: 620px) {{
  .es-perfil-row {{ grid-template-columns: minmax(185px, 0.5fr) minmax(90px, 0.5fr) 40px; }}
}}
.es-perfil-row:hover {{ background: #161b22; }}
.es-perfil-row.flag {{ background: #1f6feb1a; }}
/* barra selecionada (a que está detalhada abaixo): contorno + leve realce */
.es-perfil-row.sel {{
  background: #1f6feb26;
  box-shadow: inset 0 0 0 1px #58a6ff88;
}}
.es-perfil-row.sel .es-perfil-nome {{ color: #e6edf3; font-weight: 700; }}
.es-perfil-nome {{ font-size: 0.82rem; color: #c9d1d9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.es-perfil-row.flag .es-perfil-nome {{ color: #e6edf3; font-weight: 700; }}
.es-perfil-tag {{
  font-size: 0.62rem; color: #58a6ff; background: #1f6feb22; border-radius: 4px;
  padding: 1px 5px; margin-left: 5px; font-weight: 600; vertical-align: middle;
}}
.es-perfil-bar {{ height: 8px; background: #161b22; border-radius: 4px; overflow: hidden; }}
.es-perfil-fill {{ display: block; height: 100%; border-radius: 4px; transition: width 0.3s; }}
.es-perfil-val {{ font-size: 0.8rem; font-weight: 700; color: #e6edf3; text-align: right; }}
.es-axes-title {{
  font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px;
  color: #8b949e; margin: 18px 2px 4px;
}}
.es-axes-title span {{ text-transform: none; letter-spacing: 0; font-weight: 400; color: #6b7280; }}

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
/* modal do jogador: comparação + histórico */
.pm-section {{ margin-top: 14px; }}
.pm-hist {{ margin-top: 16px; }}
.pm-table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-top: 8px; }}
.pm-table th {{ text-align: left; color: #8b949e; font-weight: 600; padding: 5px 8px; border-bottom: 1px solid #21262d; }}
.pm-table td {{ padding: 5px 8px; border-bottom: 1px solid #161b22; color: #c9d1d9; }}
.pm-table tr:hover td {{ background: #161b22; }}
/* tabela densa de jogadores */
.players-wrap {{ flex: 1; min-height: 0; overflow: auto; padding: 0 20px; }}
.players-table {{ width: 100%; }}
.players-table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
.players-table th {{
  position: sticky; top: 0; z-index: 1; background: #0d1117;
  text-align: left; color: #8b949e; font-weight: 600; letter-spacing: .2px;
  padding: 8px 10px; border-bottom: 1px solid #21262d; white-space: nowrap;
}}
.players-table td {{ padding: 7px 10px; border-bottom: 1px solid #161b22; white-space: nowrap; }}
.players-table .pt-num {{ text-align: right; }}
.players-table .pt-rank {{ text-align: right; width: 38px; color: #6b7280; }}
.players-table .pt-shirt {{ text-align: center; width: 34px; color: #8b949e; font-variant-numeric: tabular-nums; }}
.players-table .pt-name {{ color: #e6edf3; font-weight: 600; }}
.players-table .pt-dim {{ color: #8b949e; }}
.players-table .pt-team-link {{ color: #9db3cf; cursor: pointer; font-weight: 600; }}
.players-table .pt-team-link:hover {{ color: #58a6ff; text-decoration: underline; text-underline-offset: 2px; }}
.players-table .pt-team-active {{ color: #58a6ff; }}
.players-table .pt-metric {{ background: #1f6feb12; color: #e6edf3; }}
.players-table th.pt-metric {{ color: #58a6ff; }}
.players-table th.pt-sort {{ cursor: pointer; user-select: none; }}
.players-table th.pt-sort:hover {{ color: #c9d1d9; background: #161b22; }}
.players-table th.pt-active {{ color: #58a6ff; }}
.pt-row {{ cursor: pointer; transition: background .12s; }}
.pt-row:hover td {{ background: #161b22; }}
.pt-row.pt-focus td {{ background: #1f6feb22; box-shadow: inset 2px 0 0 #58a6ff; }}
.pt-row.pt-empty {{ opacity: .4; cursor: default; }}
.pt-row.pt-empty:hover td {{ background: transparent; }}

/* ── aba Elenco ── */
.el-board {{ display: flex; flex-direction: column; gap: 14px; }}
.el-leaders {{
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px;
}}
.el-leader {{
  min-width: 0; border: 1px solid #263241; border-radius: 8px; padding: 10px 11px;
  background: linear-gradient(180deg, rgba(22,27,34,0.88), rgba(13,17,23,0.88));
}}
.el-leader-label {{
  color: #9aa4b2; font-size: 0.68rem; font-weight: 800; text-transform: uppercase;
  letter-spacing: 0.4px; margin-bottom: 8px;
}}
.el-leader-main {{ display: flex; align-items: baseline; gap: 8px; min-width: 0; }}
.el-leader-val {{ color: #58a6ff; font-size: 1.25rem; font-weight: 900; font-variant-numeric: tabular-nums; }}
.el-leader-name {{
  color: #e6edf3; font-size: 0.82rem; font-weight: 800; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.el-section-title {{
  color: #9aa4b2; font-size: 0.7rem; font-weight: 800; text-transform: uppercase;
  letter-spacing: 0.5px; margin: 2px 0 -4px;
}}
.el-player-grid {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 9px;
}}
.el-player {{
  min-width: 0; border: 1px solid #222b38; border-radius: 8px; padding: 10px 11px;
  background: rgba(22,27,34,0.64); position: relative; cursor: pointer;
}}
.el-player:hover {{ border-color: #1f6feb55; background: rgba(31,111,235,0.09); }}
.el-player.open {{ z-index: 30; border-color: #58a6ff88; }}
.el-player-top {{ display: flex; align-items: center; gap: 9px; min-width: 0; }}
.el-avatar {{
  width: 34px; height: 34px; border-radius: 50%; flex: 0 0 auto;
  display: inline-flex; align-items: center; justify-content: center;
  background: #1f6feb22; border: 1px solid #1f6feb55; color: #79b8ff;
  font-size: 0.78rem; font-weight: 900; font-variant-numeric: tabular-nums;
}}
.kit-shirt {{
  position: relative; width: 38px; height: 32px; flex: 0 0 auto;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--shirt-text, #e6edf3); font-size: 0.72rem; font-weight: 950;
  font-variant-numeric: tabular-nums; isolation: isolate;
}}
.kit-shirt::before {{
  content: ""; position: absolute; inset: 1px 0 0; z-index: 0;
  background: linear-gradient(180deg, var(--shirt-main, #2f81f7), var(--shirt-main, #2f81f7) 62%, var(--shirt-dark, #1158c7));
  border: 1px solid var(--shirt-border, #58a6ff70);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.10), 0 5px 12px rgba(0,0,0,0.24);
  clip-path: polygon(18% 7%, 34% 0, 43% 10%, 57% 10%, 66% 0, 82% 7%, 100% 34%, 82% 49%, 75% 33%, 75% 100%, 25% 100%, 25% 33%, 18% 49%, 0 34%);
}}
.kit-shirt::after {{
  content: ""; position: absolute; top: 3px; left: 16px; width: 6px; height: 5px; z-index: 1;
  border-radius: 0 0 999px 999px; border: 1px solid var(--shirt-border, rgba(13,17,23,0.75)); border-top: 0;
  background: var(--shirt-border, #0d1117);
}}
.kit-shirt .shirt-number {{ position: relative; z-index: 2; margin-top: 6px; color: var(--shirt-text, #e6edf3); }}
.el-shirt {{ width: 38px; height: 32px; }}
.pc-shirt {{ width: 34px; height: 29px; font-size: 0.68rem; }}
.pc-shirt::after {{ left: 14px; }}
.el-player-id {{ min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 2px; }}
.el-name {{
  color: #e6edf3; font-size: 0.84rem; font-weight: 800; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.el-pos-label {{ color: #8b949e; font-size: 0.66rem; font-weight: 700; letter-spacing: 0.2px; }}
.el-marks {{ display: flex; align-items: center; gap: 5px; flex: 0 0 auto; }}
.el-mark {{
  min-width: 22px; height: 20px; border-radius: 999px; padding: 0 6px;
  display: inline-flex; align-items: center; justify-content: center; gap: 4px;
  color: #e6edf3; font-size: 0.66rem; font-weight: 900; font-variant-numeric: tabular-nums;
  border: 1px solid #263241; background: #0d1117;
}}
.el-mark.goal {{ border-color: #1f6feb55; background: #1f6feb18; color: #79b8ff; }}
.el-card-dot {{ width: 8px; height: 11px; border-radius: 1px; display: inline-block; }}
.el-card-dot.yellow {{ background: #f5c542; }}
.el-card-dot.red {{ background: #ef4444; }}
.el-pos-group {{ display: flex; flex-direction: column; gap: 9px; }}
.el-pos-head {{
  display: flex; align-items: center; gap: 8px; color: #c9d1d9;
  font-size: 0.78rem; font-weight: 900; text-transform: uppercase; letter-spacing: 0.5px;
}}
.el-pos-count {{ color: #6b7280; font-size: 0.7rem; font-weight: 800; }}
.el-stat-grid {{ display: flex; flex-wrap: wrap; gap: 5px; }}
.el-stat {{
  display: inline-flex; align-items: baseline; gap: 5px; min-width: 0;
  border: 1px solid #263241; border-radius: 6px; padding: 3px 6px;
  background: #0d1117; font-variant-numeric: tabular-nums;
}}
.el-stat b {{ color: #e6edf3; font-size: 0.78rem; }}
.el-stat span {{ color: #8b949e; font-size: 0.66rem; font-weight: 700; }}
.el-stat.hot {{ border-color: #1f6feb55; background: #1f6feb18; }}
.el-stat.warn {{ border-color: #f5c54255; background: #f5c54214; }}
.el-stat.danger {{ border-color: #ef444455; background: #ef444414; }}
.el-unused {{
  border-top: 1px solid #21262d; padding-top: 12px;
}}
.el-extra {{
  border-top: 1px solid #3b2f18; padding-top: 12px;
}}
.el-extra-note {{
  color: #8b949e; font-size: 0.72rem; line-height: 1.35; margin: -4px 0 10px;
}}
.el-unused-group {{ margin-top: 9px; }}
.el-unused-group:first-of-type {{ margin-top: 8px; }}
.el-unused-head {{ color: #8b949e; font-size: 0.68rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.4px; }}
.el-unused-list {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
.el-unused-chip {{
  color: #8b949e; background: #161b22; border: 1px solid #222b38;
  border-radius: 6px; padding: 3px 7px 3px 5px; font-size: 0.72rem; font-weight: 700;
  display: inline-flex; align-items: center; gap: 5px;
}}
.pcard.el-pop {{
  position: fixed; left: var(--el-pop-left, 16px); top: var(--el-pop-top, 16px);
  right: auto; transform: translate(var(--pc-x, 0px), var(--pc-y, 0px));
  z-index: 10000; width: 340px; max-height: calc(100vh - 16px); overflow: auto;
}}
.pcard.el-pop .pc-head {{ cursor: move; touch-action: none; }}
.pcard.el-pop .pc-num {{ background: #1f6feb; }}
.pcard.el-pop .pc-head {{ padding: 8px 10px; gap: 8px; }}
.pcard.el-pop .pc-name {{ font-size: 0.86rem; }}
.pc-name-link {{
  appearance: none; border: 0; background: transparent; padding: 0; margin: 0;
  color: #e6edf3; font: inherit; font-weight: 850; text-align: left; cursor: pointer;
}}
.pc-name-link:hover {{ color: #58a6ff; text-decoration: underline; text-underline-offset: 2px; }}
.pcard.el-pop .pc-meta {{ grid-template-columns: 48px 1fr; min-height: 42px; padding: 8px 10px 0; }}
.pcard.el-pop .pc-meta-side {{ gap: 7px; }}
.pcard.el-pop .pc-group {{ padding: 8px 10px 0; }}
.pcard.el-pop .pc-group:last-child {{ padding-bottom: 10px; }}
.pcard.el-pop .pc-grid {{ gap: 5px 14px; }}
@media (max-width: 760px) {{
  .el-leaders {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .el-player-grid {{ grid-template-columns: 1fr; }}
  .pcard.el-pop {{ width: min(340px, calc(100vw - 16px)); }}
}}

/* ── aba Jogos: card de jogo (accordion) ── */
.mg {{
  background: #161b22; border: 1px solid #21262d; border-radius: 10px;
  margin-bottom: 10px; overflow: hidden; transition: border-color 0.15s;
}}
.mg.open {{ border-color: #1f6feb55; }}
.mg-head {{
  position: relative;
  display: flex; align-items: center; justify-content: center;
  padding: 12px 116px; cursor: pointer;
  transition: background 0.15s;
}}
.mg-head:hover {{ background: #1a212b; }}
/* confronto centralizado: time 1 bandeira 5 x 1 bandeira time 2 */
.mg-match {{
  width: 100%; min-width: 0;
  display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center; gap: 10px;
}}
.mg-side {{ min-width: 0; color: #8b949e; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.mg-side.left {{ text-align: right; }}
.mg-side.right {{ text-align: left; }}
.mg-side.me {{ color: #e6edf3; }}                 /* a seleção sendo vista, destacada */
.mg-score {{
  justify-self: center;
  font-weight: 800; font-size: 1rem; padding: 3px 12px; border-radius: 6px;
  background: #21262d; font-variant-numeric: tabular-nums; text-align: center; min-width: 64px;
}}
.mg-score.res-V {{ background: #22c55e22; color: #22c55e; }}
.mg-score.res-E {{ background: #6b728022; color: #9ca3af; }}
.mg-score.res-D {{ background: #ef444422; color: #ef4444; }}
.mg-score.res-next {{ background: #21262d; color: #6b7280; }}
.mg-date {{
  position: absolute; right: 36px; top: 50%; transform: translateY(-50%);
  color: #58a6ff; font-size: 0.76rem; font-weight: 700; font-variant-numeric: tabular-nums;
  background: #1f6feb1a; border: 1px solid #1f6feb33; border-radius: 6px; padding: 3px 8px;
}}
.mg-chevron {{
  position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
  color: #6b7280; font-size: 0.7rem;
}}
.mg-detail {{ padding: 4px 16px 16px; border-top: 1px solid #21262d; }}
/* jogos agendados (não clicáveis) */
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

.gd-stats-board {{
  border: 1px solid #263241; border-radius: 8px; padding: 14px 16px 16px;
  background:
    linear-gradient(180deg, rgba(22,27,34,0.96), rgba(13,17,23,0.96)),
    radial-gradient(circle at 50% 0%, rgba(88,166,255,0.12), transparent 48%);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}}
.gd-stat-legend {{
  display: grid; grid-template-columns: minmax(0, 1fr) 28px minmax(0, 1fr);
  align-items: center; gap: 10px; margin-bottom: 12px;
}}
.gd-side-key {{
  min-width: 0; display: flex; align-items: center; gap: 7px;
  font-size: 0.78rem; font-weight: 800; color: #c9d1d9;
}}
.gd-side-key.left {{ justify-content: flex-end; color: #79b8ff; }}
.gd-side-key.right {{ justify-content: flex-start; color: #ff8b8b; }}
.gd-side-key b {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.gd-axis-dot {{
  justify-self: center; width: 5px; height: 5px; border-radius: 50%; background: #3b4452;
  box-shadow: 0 0 0 4px rgba(48,56,70,0.22);
}}
.gd-spotlight {{
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px;
}}
.gd-spot {{
  min-width: 0; border: 1px solid #263241; border-radius: 8px; padding: 10px 11px;
  background: rgba(13,17,23,0.72);
}}
.gd-spot-top {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }}
.gd-spot-title {{ color: #9aa4b2; font-size: 0.72rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.4px; }}
.gd-spot-edge {{
  max-width: 58%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: #e6edf3; font-size: 0.68rem; font-weight: 800;
}}
.gd-spot-edge.left {{ color: #79b8ff; }}
.gd-spot-edge.right {{ color: #ff8b8b; }}
.gd-spot-edge.even {{ color: #9aa4b2; }}
.gd-spot-values {{
  display: grid; grid-template-columns: minmax(0, 1fr) 18px minmax(0, 1fr);
  align-items: baseline; gap: 6px; margin-bottom: 8px;
}}
.gd-spot-num {{
  font-size: 1.08rem; font-weight: 900; font-variant-numeric: tabular-nums;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.gd-spot-num.left {{ color: #79b8ff; text-align: right; }}
.gd-spot-num.right {{ color: #ff8b8b; text-align: left; }}
.gd-spot-x {{ color: #6b7280; text-align: center; font-size: 0.72rem; font-weight: 800; }}
.gd-balance {{
  position: relative; display: grid; grid-template-columns: 1fr 1fr; gap: 3px; height: 6px;
}}
.gd-balance::after {{
  content: ''; position: absolute; left: 50%; top: -3px; bottom: -3px; width: 1px;
  background: #3b4452; transform: translateX(-50%);
}}
.gd-bal-half {{ position: relative; overflow: hidden; border-radius: 999px; background: #202733; }}
.gd-bal-fill {{ position: absolute; top: 0; bottom: 0; border-radius: 999px; }}
.gd-bal-half.left .gd-bal-fill {{ right: 0; background: linear-gradient(90deg, #1f6feb, #58a6ff); }}
.gd-bal-half.right .gd-bal-fill {{ left: 0; background: linear-gradient(90deg, #ef4444, #ff7b72); }}
.gd-mini-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }}
.gd-mini-stat {{
  min-width: 0; border: 1px solid #222b38; border-radius: 8px; padding: 9px 10px;
  background: rgba(22,27,34,0.64);
}}
.gd-mini-label {{
  color: #9aa4b2; font-size: 0.7rem; font-weight: 700; margin-bottom: 7px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.gd-mini-values {{
  display: grid; grid-template-columns: minmax(0, 1fr) 14px minmax(0, 1fr);
  align-items: baseline; gap: 5px; font-variant-numeric: tabular-nums;
}}
.gd-mini-v {{ font-size: 0.92rem; font-weight: 900; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.gd-mini-v.left {{ color: #79b8ff; text-align: right; }}
.gd-mini-v.right {{ color: #ff8b8b; text-align: left; }}
.gd-mini-sep {{ color: #4b5563; text-align: center; font-size: 0.68rem; font-weight: 800; }}
@media (max-width: 760px) {{
  .gd-spotlight {{ grid-template-columns: 1fr; }}
  .gd-mini-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}

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
/* quando um card de jogador está aberto, deixa ele transbordar o campo */
.pitch-h.pitch-vs.has-card {{ overflow: visible; }}
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

/* ── card flutuante de dados do jogador (popover ancorado no jogador) ── */
.pcard {{
  position: absolute; left: 50%; z-index: 6; width: 380px; max-width: calc(100vw - 16px); cursor: default;
  background: linear-gradient(180deg, #161b22, #0d1117);
  border: 1px solid #30363d; border-radius: 12px;
  box-shadow: 0 16px 40px rgba(0,0,0,0.75); text-align: left; overflow: hidden;
}}
.pcard.v-above {{ bottom: 130%; transform: translate(calc(-50% + var(--pc-x, 0px)), var(--pc-y, 0px)); }}
.pcard.v-below {{ top: 130%; transform: translate(calc(-50% + var(--pc-x, 0px)), var(--pc-y, 0px)); }}
.pcard.h-l {{ left: auto; right: 100%; transform: translate(calc(-8px + var(--pc-x, 0px)), var(--pc-y, 0px)); }}
.pcard.h-r {{ left: 100%; transform: translate(calc(8px + var(--pc-x, 0px)), var(--pc-y, 0px)); }}
.pcard.field-pop {{
  position: fixed; left: var(--field-pop-left, 16px); top: var(--field-pop-top, 16px);
  right: auto; bottom: auto; transform: translate(var(--pc-x, 0px), var(--pc-y, 0px));
  z-index: 10000; max-height: calc(100vh - 16px); overflow: auto;
}}
.pcard.dragging {{ user-select: none; box-shadow: 0 20px 48px rgba(0,0,0,0.85), 0 0 0 1px #58a6ff66; }}

.pc-head {{
  display: flex; align-items: center; gap: 10px; padding: 11px 12px;
  background: #1c2330; border-bottom: 1px solid #21262d;
  cursor: move; touch-action: none;
}}
.pc-num {{
  background: #d6342c; color: #fff; font-size: 0.8rem; font-weight: 900;
  width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}}
.pc-id {{ flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }}
.pc-name {{ font-size: 0.92rem; font-weight: 800; color: #e6edf3; line-height: 1.1; }}
.pc-pos {{ font-size: 0.66rem; color: #8b949e; letter-spacing: 0.2px; }}
.pc-close {{
  background: transparent; border: none; color: #8b949e; cursor: pointer;
  font-size: 0.95rem; padding: 2px 4px; border-radius: 5px; flex-shrink: 0;
}}
.pc-close:hover {{ background: #30363d; color: #e6edf3; }}

.pc-meta {{
  display: grid; grid-template-columns: 50px 1fr; align-items: center; gap: 10px;
  min-height: 46px; padding: 10px 12px 0;
}}
.pc-rating {{
  display: flex; flex-direction: column; align-items: center; line-height: 1;
  background: #1f6feb1f; border: 1px solid #1f6feb55; border-radius: 8px;
  padding: 5px 10px; font-size: 1.15rem; font-weight: 900; color: #58a6ff;
}}
.pc-rating small {{ font-size: 0.54rem; font-weight: 600; color: #8b949e; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.4px; }}
.pc-rating.empty {{ visibility: hidden; }}
.pc-meta-side {{
  min-width: 0; display: flex; flex-direction: column; justify-content: center; gap: 6px;
}}
.pc-chip {{ font-size: 0.72rem; color: #8b949e; }}

.pc-ctx {{ display: flex; flex-wrap: wrap; gap: 5px; min-height: 18px; align-items: center; }}
.pc-ctx.empty {{ visibility: hidden; }}
.pc-tag {{ font-size: 0.68rem; font-weight: 700; border-radius: 6px; padding: 2px 7px; }}
.pc-tag.goal {{ background: #1f6feb22; color: #79b8ff; }}
.pc-tag.neutral {{ background: #21262d; color: #c9d1d9; }}
.pc-tag.amarelo {{ background: #f5c54222; color: #f5c542; }}
.pc-tag.vermelho {{ background: #ef444422; color: #ef4444; }}
.pc-tag.out {{ background: #ef444418; color: #f0867d; }}
.pc-tag.in {{ background: #22c55e22; color: #4ade80; }}

.pc-group {{ padding: 10px 12px 0; }}
.pc-group:last-child {{ padding-bottom: 12px; }}
.pc-gt {{ font-size: 0.62rem; color: #58a6ff; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 700; margin-bottom: 6px; }}
.pc-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 20px; }}
.pc-stat {{ display: flex; align-items: baseline; justify-content: space-between; gap: 10px; min-width: 0; }}
.pc-sl {{ min-width: 0; font-size: 0.72rem; line-height: 1.16; color: #8b949e; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: help; }}
.pc-sv {{ flex-shrink: 0; font-size: 0.82rem; font-weight: 800; color: #e6edf3; font-variant-numeric: tabular-nums; }}
.pc-empty {{ font-size: 0.74rem; color: #6b7280; padding: 12px; }}

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
/* minuto de saída: canto inferior-direito da camisa (cartão fica no topo-esq,
   gol no topo-dir — assim os três marcadores não se sobrepõem) */
.sub-out {{
  position: absolute; bottom: -5px; right: -10px;
  font-size: 0.52rem; font-weight: 800; color: #fff;
  background: #ef4444; border-radius: 8px; padding: 0 4px; white-space: nowrap;
  border: 1px solid #0d1117;
}}
.sub-in-field {{
  position: absolute; bottom: -5px; right: -10px;
  font-size: 0.52rem; font-weight: 800; color: #fff;
  background: #22c55e; border-radius: 8px; padding: 0 4px; white-space: nowrap;
  border: 1px solid #0d1117;
}}
.pitch-sub-toggle {{
  position: absolute; right: -15px; top: 13px;
  width: 18px; height: 18px; border-radius: 50%;
  border: 1px solid #58a6ff99; background: #0d419dcc; color: #c9e6ff;
  font-size: 0.72rem; line-height: 16px; font-weight: 900;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; z-index: 5;
  box-shadow: 0 1px 5px rgba(0,0,0,0.55);
}}
.pitch-sub-toggle:hover {{ background: #1f6feb; color: #fff; transform: scale(1.06); }}
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
<div id="chipTip"></div>
<div id="weightsGuide" class="weights-guide-overlay" style="display:none" onclick="if(event.target===this)closeWeightsGuide()">
  <div class="weights-guide" role="dialog" aria-modal="true" aria-labelledby="weightsGuideTitle">
    <div class="wg-top">
      <div class="wg-title">
        <strong id="weightsGuideTitle">Guia dos pesos do ranking</strong>
        <span id="weightsGuideSub">Como os componentes mudam e afetam a leitura da Copa</span>
      </div>
      <button class="wg-close" onclick="closeWeightsGuide()" title="Fechar">✕</button>
    </div>
    <div class="wg-shell">
      <nav class="wg-nav" id="weightsGuideNav"></nav>
      <div class="wg-body" id="weightsGuideBody"></div>
    </div>
  </div>
</div>

<header>
  <div class="header-left">
    <div class="header-title">Copa 2026</div>
    <nav class="tabs">
      <button class="tab active" data-tab="race" onclick="switchTab('race')">Ranking Race</button>
      <button class="tab" data-tab="teams" onclick="switchTab('teams')">Seleções</button>
      <button class="tab" data-tab="players" onclick="switchTab('players')">Jogadores</button>
    </nav>
  </div>
  <div class="weights-row" id="weightsPills"></div>
  <div class="header-player">
    <button class="btn" id="btnPlay" onclick="togglePlay()">▶ Play</button>
    <span class="slider-label" id="sliderLabel" style="font-size:0.75rem;color:#8b949e;white-space:nowrap">Jogo 1</span>
    <input type="range" id="jogoSlider" min="1" value="1" style="width:160px" oninput="goToJogo(jogoFromSliderValue(this.value))">
    <select id="speedSelect" onchange="updateSpeed()" style="font-size:0.75rem;padding:3px 6px">
      <option value="1400">Lenta</option>
      <option value="900" selected>Normal</option>
      <option value="450">Rápida</option>
    </select>
  </div>
</header>

<!-- ══ BARRA DE FILTROS ÚNICA — idêntica e compartilhada pelas duas abas ══ -->
<div class="controls" id="sharedControls">
  <div class="team-search-wrap">
    <div id="selectedTeamChips" class="selected-team-chips"></div>
    <input type="text" id="teamSearch" class="teams-search" placeholder="Buscar/destacar seleção…" autocomplete="off" oninput="onFocusInput()" onfocus="renderTeamSuggestions()" onkeydown="onTeamSearchKey(event)">
    <div id="teamSuggestions" class="team-suggest"></div>
  </div>
  <label class="tb-field">Métrica
    <select id="metricSelect" onchange="changeMetric(this.value)"></select>
  </label>
  <button class="btn" id="btnDir" onclick="toggleDir()">↓ Maior primeiro</button>
  <div style="width:1px;height:18px;background:#30363d;margin:0 4px"></div>
  <label class="tb-field" id="fieldPos" style="display:none">Posição
    <select id="filterPos" onchange="applyTeamFilters()">
      <option value="">Todas</option>
      <option value="goleiro">Goleiro</option>
      <option value="defensor">Defensor</option>
      <option value="meio">Meio</option>
      <option value="atacante">Atacante</option>
    </select>
  </label>
  <label class="tb-field">Grupo
    <select id="filterGroup" onchange="applyTeamFilters()"><option value="">Todos</option></select>
    <span class="filter-hints" id="filterGroupHints"></span>
  </label>
  <label class="tb-field">Confederação
    <select id="filterConfed" onchange="applyTeamFilters()"><option value="">Todas</option></select>
    <span class="filter-hints" id="filterConfedHints"></span>
  </label>
  <label class="tb-field">Fase
    <select id="filterStage" onchange="applyTeamFilters()"><option value="">Todas</option></select>
    <span class="filter-hints" id="filterStageHints"></span>
  </label>
  <label class="tb-check"><input type="checkbox" id="filterPlayed" onchange="applyTeamFilters()"> Só com jogos</label>
  <label class="tb-check" title="Só seleções com cobertura de dados avançados (xG, xGP, duelos) no jogo atual"><input type="checkbox" id="filterAdvanced" onchange="applyTeamFilters()"> Só com dados avançados</label>
  <div style="flex:1"></div>
  <button class="btn" onclick="resetAllFilters()" title="Limpar filtros">✕ Limpar</button>
  <span class="teams-count" id="teamsCount"></span>
</div>

<!-- ══ BARRA DE BOLINHAS (navegação no tempo) — compartilhada ══ -->
<div class="dots-wrap" id="progressDots"></div>
<div id="teamDotRows"></div>

<!-- ══ VIEW: Ranking Race ══ -->
<div id="viewRace">
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

  <div class="trajectory-sidebar-resizer" id="trajectorySidebarResizer" title="Arrastar para ajustar a largura da trajetória"></div>
  <div class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-title-row">
        <h3>Trajetória</h3>
      </div>
      <div class="trajectory-teams" id="trajectoryTeams"></div>
      <div class="sidebar-team" id="sidebarTeam">—</div>
    </div>
    <div class="sidebar-body" id="sidebarBody">
      <div class="no-team">Clique em até 16 seleções para comparar a trajetória</div>
    </div>
  </div>
</div>
</div><!-- /viewRace -->

<!-- ══ MODAL FLUTUANTE: trajetória comparativa ══ -->
<div id="trajectoryModal" class="trajectory-modal" style="display:none">
  <div class="trajectory-modal-bar" id="trajectoryModalBar">
    <div class="trajectory-modal-title">
      <span>Trajetória</span>
      <strong id="trajectoryModalSubtitle">—</strong>
    </div>
    <div class="trajectory-modal-actions">
      <button class="modal-card-close" onclick="closeTrajectoryModal()" title="Fechar">✕</button>
    </div>
  </div>
  <div class="trajectory-modal-toolbar">
    <select id="trajectoryMetricSelect" onchange="setTrajectoryMetric(this.value)"></select>
    <div class="trajectory-mode">
      <button class="traj-mode-btn active" id="trajModeRank" onclick="setTrajectoryMode('rank')">Ranking</button>
      <button class="traj-mode-btn" id="trajModeValue" onclick="setTrajectoryMode('value')">Valor</button>
    </div>
    <div class="trajectory-mode">
      <button class="traj-mode-btn active" id="trajAxisTournament" onclick="setTrajectoryAxis('tournament')">Torneio</button>
      <button class="traj-mode-btn" id="trajAxisTeam" onclick="setTrajectoryAxis('team')">Jogo do time</button>
    </div>
    <div class="trajectory-teams trajectory-modal-teams" id="trajectoryModalTeams"></div>
  </div>
  <div class="trajectory-modal-body" id="trajectoryModalBody">
    <div class="no-team">Clique em até 16 seleções para comparar a trajetória</div>
  </div>
  <div class="trajectory-resize-handle" id="trajectoryResizeHandle" title="Redimensionar mantendo proporção"></div>
</div>

<!-- ══ MODAL FLUTUANTE: comparação ponto a ponto ══ -->
<div id="pointCompareModal" class="trajectory-modal point-compare-modal" style="display:none">
  <div class="trajectory-modal-bar" id="pointCompareModalBar">
    <div class="trajectory-modal-title">
      <span>Comparação ponto a ponto</span>
      <strong id="pointCompareModalSubtitle">—</strong>
    </div>
    <div class="trajectory-modal-actions">
      <button class="modal-card-close" onclick="closePointCompareModal()" title="Fechar">✕</button>
    </div>
  </div>
  <div class="trajectory-modal-body" id="pointCompareModalBody">
    <div class="no-team">Fixe pelo menos 2 seleções na trajetória para comparar.</div>
  </div>
  <div class="trajectory-resize-handle" id="pointCompareResizeHandle" title="Redimensionar mantendo proporção"></div>
</div>

<!-- ══ VIEW: Seleções (grade de países) ══ -->
<div id="viewTeams" style="display:none">
  <div class="teams-grid" id="teamsGrid"></div>
  <div class="teams-pager" id="teamsPager"></div>
</div>

<!-- ══ VIEW: Jogadores (grade de jogadores) ══ -->
<div id="viewPlayers" style="display:none">
  <div id="playersGrid" class="players-wrap"></div>
  <div class="teams-pager" id="playersPager"></div>
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

<!-- ══ MODAL: detalhe do jogador ══ -->
<div id="playerModal" class="modal-overlay" style="display:none" onclick="if(event.target===this)closePlayerModal()">
  <div class="modal" role="dialog" aria-modal="true">
    <div class="modal-topbar">
      <div class="modal-mini" id="playerModalTitle"></div>
      <div style="flex:1"></div>
      <button class="modal-close" onclick="closePlayerModal()" title="Fechar (Esc)">✕</button>
    </div>
    <div class="modal-body" id="playerModalBody"></div>
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
const TEAM_SHIRT_COLORS = {{
  'África do Sul': '#facc15', 'Alemanha': '#f8fafc', 'Angola': '#c1121f', 'Arábia Saudita': '#15803d',
  'Argélia': '#f8fafc', 'Argentina': '#75aadb', 'Austrália': '#facc15', 'Bélgica': '#dc2626',
  'Brasil': '#facc15', 'Cabo Verde': '#2563eb', 'Camarões': '#16a34a', 'Canadá': '#dc2626',
  'Chile': '#dc2626', 'China': '#dc2626', 'Colômbia': '#facc15', 'Coreia do Sul': '#f8fafc',
  'Costa Rica': '#dc2626', 'Croácia': '#f8fafc', 'Dinamarca': '#dc2626', 'Egito': '#dc2626',
  'Equador': '#facc15', 'Espanha': '#dc2626', 'Estados Unidos': '#1d4ed8', 'França': '#1d4ed8',
  'Gana': '#facc15', 'Holanda': '#f97316', 'Inglaterra': '#f8fafc', 'Irã': '#f8fafc',
  'Itália': '#2563eb', 'Japão': '#2563eb', 'Marrocos': '#dc2626', 'México': '#15803d',
  'Nigéria': '#16a34a', 'Noruega': '#dc2626', 'Nova Zelândia': '#111827', 'Panamá': '#dc2626',
  'Paraguai': '#dc2626', 'Peru': '#f8fafc', 'Polônia': '#f8fafc', 'Portugal': '#dc2626',
  'Qatar': '#7f1d1d', 'Senegal': '#16a34a', 'Sérvia': '#dc2626', 'Suécia': '#2563eb',
  'Suíça': '#dc2626', 'Tunísia': '#dc2626', 'Uruguai': '#60a5fa', 'Uzbequistão': '#2563eb',
  'Venezuela': '#7f1d1d',
}};
const TEAM_KIT_COLORS = {{
  'Alemanha': {{ main: '#f8fafc', border: '#111827', text: '#111827' }},
  'Argentina': {{ main: '#75aadb', border: '#f8fafc', text: '#111827' }},
  'Austrália': {{ main: '#facc15', border: '#15803d', text: '#15803d' }},
  'Bélgica': {{ main: '#dc2626', border: '#111827', text: '#f8fafc' }},
  'Brasil': {{ main: '#f4d21f', border: '#078930', text: '#1d4ed8' }},
  'Cabo Verde': {{ main: '#2563eb', border: '#f8fafc', text: '#f8fafc' }},
  'Canadá': {{ main: '#dc2626', border: '#f8fafc', text: '#f8fafc' }},
  'Chile': {{ main: '#dc2626', border: '#2563eb', text: '#f8fafc' }},
  'Colômbia': {{ main: '#facc15', border: '#2563eb', text: '#111827' }},
  'Coreia do Sul': {{ main: '#f8fafc', border: '#dc2626', text: '#111827' }},
  'Croácia': {{ main: '#f8fafc', border: '#dc2626', text: '#111827' }},
  'Dinamarca': {{ main: '#dc2626', border: '#f8fafc', text: '#f8fafc' }},
  'Espanha': {{ main: '#dc2626', border: '#facc15', text: '#f8fafc' }},
  'Estados Unidos': {{ main: '#f8fafc', border: '#1d4ed8', text: '#1f2a44' }},
  'França': {{ main: '#1d4ed8', border: '#f8fafc', text: '#f8fafc' }},
  'Holanda': {{ main: '#f97316', border: '#111827', text: '#111827' }},
  'Inglaterra': {{ main: '#f8fafc', border: '#dc2626', text: '#1f2a44' }},
  'Itália': {{ main: '#2563eb', border: '#f8fafc', text: '#f8fafc' }},
  'Japão': {{ main: '#2563eb', border: '#f8fafc', text: '#f8fafc' }},
  'México': {{ main: '#15803d', border: '#f8fafc', text: '#f8fafc' }},
  'Nigéria': {{ main: '#16a34a', border: '#f8fafc', text: '#f8fafc' }},
  'Noruega': {{ main: '#dc2626', border: '#1d4ed8', text: '#f8fafc' }},
  'Peru': {{ main: '#f8fafc', border: '#dc2626', text: '#111827' }},
  'Polônia': {{ main: '#f8fafc', border: '#dc2626', text: '#111827' }},
  'Portugal': {{ main: '#7f1d1d', border: '#15803d', text: '#f8fafc' }},
  'Suécia': {{ main: '#2563eb', border: '#facc15', text: '#facc15' }},
  'Suíça': {{ main: '#dc2626', border: '#f8fafc', text: '#f8fafc' }},
  'Uruguai': {{ main: '#60a5fa', border: '#111827', text: '#111827' }},
}};

// dados de JOGADORES por snapshot + metadados estáticos
const PLAYER_DATA = {player_data_json};
const PLAYER_META = {player_meta_json};

const JOGO_ORDER = {snapshot_order_json_var};
const jogos = (JOGO_ORDER.length ? JOGO_ORDER : Object.keys(DATA).map(Number).sort((a,b)=>a-b))
  .map(Number)
  .filter(n => DATA[n]);
const N = jogos.length;
const ROW_H = 44;

// — Metadados ESTÁTICOS por time (grupo/confederação/fase): não mudam com o
// tempo, vêm do TEAMS_DETAIL. Usados pelos filtros nas DUAS abas.
const TEAM_META = {{}};
Object.entries(TEAMS_DETAIL).forEach(([t, d]) => {{
  TEAM_META[t] = {{ group: d.group || null, confed: d.confed || null, stage: d.stage_now || null }};
}});

// — Índice [jogo][time] → linha de números daquele snapshot, para lookup O(1).
// Também pré-calcula a posição no ranking geral (score_geral) de cada snapshot,
// já que o timeline não traz o rank pronto.
const SNAP_BY_TEAM = {{}};
const SNAP_RANK = {{}};
Object.entries(DATA).forEach(([n, frame]) => {{
  const byTeam = {{}};
  (frame.teams || []).forEach(row => {{ byTeam[row.team] = row; }});
  SNAP_BY_TEAM[n] = byTeam;
  // ranking por score_geral (maior = 1º), empate = mesma posição
  const ranked = (frame.teams || [])
    .filter(r => r.score_geral != null)
    .sort((a, b) => b.score_geral - a.score_geral);
  const rk = {{}};
  ranked.forEach((r, i) => {{
    rk[r.team] = (i > 0 && r.score_geral === ranked[i - 1].score_geral) ? rk[ranked[i - 1].team] : i + 1;
  }});
  SNAP_RANK[n] = rk;
}});

// Estado de FILTRO global, compartilhado entre Ranking Race e Seleções.
const teamFilters = {{ group: '', confed: '', stage: '' }};

// Um time passa nos filtros globais (grupo/confederação/fase)?
function passesGlobalFilters(team) {{
  const meta = TEAM_META[team] || {{}};
  if (teamFilters.group && meta.group !== teamFilters.group) return false;
  if (teamFilters.confed && meta.confed !== teamFilters.confed) return false;
  if (teamFilters.stage && meta.stage !== teamFilters.stage) return false;
  return true;
}}

function _posGroupFromPerfil(perfil) {{
  return {{
    goleiro: 'Goleiros',
    defensor: 'Defensores',
    meio: 'Meias',
    atacante: 'Atacantes',
  }}[perfil] || 'Sem posição';
}}

function _posOrderFromGroup(group) {{
  return {{
    'Goleiros': 0,
    'Defensores': 1,
    'Meias': 2,
    'Atacantes': 3,
    'Sem posição': 4,
  }}[group || 'Sem posição'] ?? 99;
}}

function _playersAtTeamSnapshot(team, n) {{
  const basePlayers = ((TEAMS_DETAIL[team] || {{}}).players || []);
  const baseByName = {{}};
  basePlayers.forEach(p => {{ if (p && p.name) baseByName[p.name] = p; }});
  return (PLAYER_DATA[n] || [])
    .filter(r => r.team === team)
    .map(r => {{
      const meta = PLAYER_META[r.slug] || {{}};
      const hasBase = Object.prototype.hasOwnProperty.call(baseByName, r.name);
      const base = hasBase ? baseByName[r.name] : {{}};
      const posGroup = base.pos_group || _posGroupFromPerfil(r.perfil);
      const rating = r.rating_365 == null ? null : r.rating_365;
      return Object.assign({{}}, base, {{
        name: r.name,
        num: base.num ?? meta.shirt,
        pos_code: base.pos_code,
        pos: base.pos || PERFIL_LABEL[r.perfil] || '—',
        pos_group: posGroup,
        pos_order: base.pos_order ?? _posOrderFromGroup(posGroup),
        in_roster: hasBase ? base.in_roster !== false : !basePlayers.length,
        rating_media: rating,
        rating_jogos: rating == null ? 0 : Math.round(r.jogos || 0),
        jogos: r.jogos || 0,
        gols: r.goals || 0,
        assist: r.assists || 0,
        chutes: r.shots || 0,
        no_alvo: r.shots_on_target || 0,
        amarelos: r.yellow_cards || 0,
        vermelhos: r.red_cards || 0,
        defesas: r.saves || 0,
        faltas: r.fouls_committed || 0,
        faltas_sofridas: r.fouls_drawn || 0,
        gols_contra: base.gols_contra || 0,
        xg: r.expected_goals || 0,
        xa: r.expected_assists || 0,
        xgot: r.expected_goals_on_target || 0,
        passes_chave: r.key_passes || 0,
        gr_chances_criadas: r.big_chances_created || 0,
        gr_chances_perdidas: r.big_chances_missed || 0,
        gr_chances_convertidas: r.big_chances_scored || 0,
        dribles: r.dribbles_won || 0,
        desarmes: r.tackles_won || 0,
        interceptacoes: r.interceptions || 0,
        cortes: r.clearances || 0,
        recuperacoes: r.ball_recovery || 0,
        duelos: r.duels_won || 0,
        bloqueios: r.shots_blocked || 0,
        xgp: r.expected_goals_prevented || 0,
        penaltis_defendidos: r.penalties_saved || 0,
        bolas_altas: r.high_claims || 0,
        socos: r.punches || 0,
      }});
    }});
}}

function _artilheiroFromPlayers(players) {{
  const top = (players || [])
    .filter(p => (p.gols || 0) > 0)
    .sort((a, b) => (b.gols || 0) - (a.gols || 0) || (b.assist || 0) - (a.assist || 0))[0];
  return top ? {{ name: top.name, gols: top.gols }} : null;
}}

// "Detalhe" do time NO MOMENTO selecionado (jogo n): mescla metadados estáticos
// (TEAMS_DETAIL) com os números daquele snapshot (DATA[n]) — assim a grade
// Seleções reflete o jogo selecionado, não só o estado final.
function teamDetailAt(team, n = currentJogo) {{
  const base = TEAMS_DETAIL[team] || {{}};
  const snap = (SNAP_BY_TEAM[n] || {{}})[team];
  const jogosAteAgora = (base.jogos || []).filter(g => g.match_n == null || g.match_n <= n);
  const playersAteAgora = _playersAtTeamSnapshot(team, n);
  const rosterCount = playersAteAgora.filter(p => p.in_roster !== false).length || base.roster_count || 0;
  if (!snap) {{
    // time ainda não entrou no ranking nesse momento: zera números, mantém metadados
    return Object.assign({{}}, base, {{
      n_jogos: 0, rank: null,
      scores: {{}}, campanha: {{}}, estilo: base.estilo,
      jogos: jogosAteAgora, players: playersAteAgora, roster_count: rosterCount,
      artilheiro: null,
    }});
  }}
  // posição no ranking geral daquele snapshot (pré-calculada em SNAP_RANK)
  return Object.assign({{}}, base, {{
    n_jogos: snap.jogos,
    rank: (SNAP_RANK[n] || {{}})[team] != null ? SNAP_RANK[n][team] : base.rank,
    scores: {{
      score_geral: snap.score_geral, score_resultado: snap.score_resultado,
      score_ataque: snap.score_ataque, score_defesa: snap.score_defesa,
      score_eficiencia: snap.score_eficiencia, score_controle: snap.score_controle,
      score_forca_relativa: snap.score_forca_relativa, score_disciplina: snap.score_disciplina,
    }},
    campanha: {{
      pontos: snap.pontos, gols_pro: snap.gols_pro, gols_contra: snap.gols_contra,
      saldo_gols: snap.saldo_gols, elo_rating: snap.elo_rating, aproveitamento: snap.aproveitamento,
    }},
    estilo: Object.assign({{}}, base.estilo || {{}}, {{ flag: snap.estilo_jogo }}),
    jogos: jogosAteAgora,
    players: playersAteAgora,
    roster_count: rosterCount,
    artilheiro: _artilheiroFromPlayers(playersAteAgora),
  }});
}}

let currentJogo = jogos[jogos.length - 1];
let selectedTeam = '';
let teamSuggestItems = [];
let teamSuggestIndex = -1;
let currentMetric = 'score_geral';
let sortDir = 'desc';   // 'desc' = maior primeiro, 'asc' = menor primeiro
let playing = false;
let timer = null;
let speed = 900;
const MAX_TRAJECTORY_TEAMS = 16;
const TRAJECTORY_COLORS = [
  '#4ade80', '#58a6ff', '#f5c542', '#f87171',
  '#a78bfa', '#2dd4bf', '#fb923c', '#f472b6',
  '#22d3ee', '#bef264', '#c084fc', '#60a5fa',
  '#facc15', '#34d399', '#fb7185', '#94a3b8',
];
let trajectoryTeams = [];
let trajectoryMetric = '__current';
let trajectoryMode = 'rank';
let trajectoryAxis = 'tournament';
let trajectoryDock = 'right';
let trajectorySliderDrag = null;
const trajectoryFocusTeams = new Set();

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

function initTrajectoryMetricSelect() {{
  const sel = document.getElementById('trajectoryMetricSelect');
  if (!sel) return;
  sel.innerHTML = '<option value="__current">Seguir métrica</option>' +
    METRIC_GROUPS.map(([gl, , opts]) =>
      `<optgroup label="${{gl}}">` + opts.map(([k, l]) => `<option value="${{k}}">${{l}}</option>`).join('') + '</optgroup>'
    ).join('');
  sel.value = trajectoryMetric;
}}
initTrajectoryMetricSelect();

const METRIC_RELATIONS = {metric_relations_json};
const METRIC_RELATIONS_INDIRECT = {metric_relations_indirect_json};

// ── init slider
const slider = document.getElementById('jogoSlider');
slider.min = 1;
slider.max = N;
slider.step = 1;

function jogoIndex(n) {{
  return jogos.indexOf(Number(n));
}}

function jogoFromSliderValue(value) {{
  const idx = Math.max(0, Math.min(jogos.length - 1, Number(value) - 1));
  return jogos[idx];
}}

function sliderValueForJogo(n) {{
  const idx = jogoIndex(n);
  return idx >= 0 ? idx + 1 : 1;
}}

function firstJogo() {{
  return jogos[0];
}}

function lastJogo() {{
  return jogos[jogos.length - 1];
}}

function nextJogo(n = currentJogo) {{
  const idx = jogoIndex(n);
  return idx >= 0 && idx < jogos.length - 1 ? jogos[idx + 1] : null;
}}

function prevJogo(n = currentJogo) {{
  const idx = jogoIndex(n);
  return idx > 0 ? jogos[idx - 1] : null;
}}

// ── dots agrupados por fase
const SNAPSHOT_META = {snapshot_meta_json_var};
const dotRefs = {{}};  // n → dot element (só jogos processados/navegáveis)
const allDots = [];   // todos os dots: {{ el, meta }} — p/ filtrar por seleção
let dotPhaseFilter = '';

const dotsEl = document.getElementById('progressDots');

// Snapshots comparáveis por "jogo do time".
// Para 2+ seleções, Jogo 1/2/3 fecha quando todas as seleções visíveis
// chegaram naquela quantidade de jogos. Assim a comparação acompanha o recorte
// escolhido, sem esperar as 48 seleções completarem a mesma rodada.
function comparableTeamGameSnapshots(teams) {{
  const out = {{}};
  const comparableTeams = [...new Set((teams || []).filter(team => TEAMS_GRID.includes(team)))];
  if (!comparableTeams.length) return out;
  const maxGames = Math.max(...comparableTeams.map(team =>
    Math.max(...jogos.map(n => ((SNAP_BY_TEAM[n] || {{}})[team] || {{}}).jogos || 0), 0)
  ), 0);
  const currentIdx = Math.max(0, jogoIndex(currentJogo));
  for (let order = 1; order <= maxGames; order++) {{
    for (let idx = 0; idx <= currentIdx; idx++) {{
      const n = jogos[idx];
      const byTeam = SNAP_BY_TEAM[n] || {{}};
      const allReachedOrder = comparableTeams.every(team => byTeam[team] && (byTeam[team].jogos || 0) >= order);
      if (allReachedOrder) {{
        out[order] = n;
        break;
      }}
    }}
  }}
  return out;
}}

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
                      'dot-missing', 'dot-first', 'dot-last', 'dot-round-end', 'dot-phase-end');

  if (debutOrder != null && m.order < debutOrder) {{
    el.classList.add('dot-pending', 'dot-faded');
    el.style.background = 'transparent';
    el.style.borderColor = color + '66';
    if (m.round_end) el.classList.add('dot-round-end');
    if (m.phase_end) el.classList.add('dot-phase-end');
    return;
  }}
  el.classList.add('dot-' + m.status);
  if (m.status === 'done') {{
    el.style.background = color;
    el.style.borderColor = 'transparent';
  }} else if (m.status === 'live') {{
    el.style.background = '#f85149';
    el.style.borderColor = 'transparent';
  }} else if (m.status === 'missing') {{
    el.style.background = 'transparent';
    el.style.borderColor = '#f59e0b';
  }} else {{
    el.style.background = 'transparent';
    el.style.borderColor = color + '66';
  }}
  // realce do primeiro / último jogo do time
  if (marker === 'first') {{ el.classList.add('dot-first'); el.style.background = '#35c46f'; el.style.borderColor = '#fff'; }}
  if (marker === 'last')  {{ el.classList.add('dot-last');  el.style.background = '#f5c542'; el.style.borderColor = '#fff'; }}
  if (m.round_end) el.classList.add('dot-round-end');
  if (m.phase_end) el.classList.add('dot-phase-end');
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

  visiblePhaseGroups().forEach(pg => {{
    const grp = document.createElement('div');
    grp.className = 'phase-group';
    const lblSpacer = document.createElement('div');
    lblSpacer.className = 'phase-label phase-label-spacer';
    lblSpacer.textContent = pg.label;
    grp.appendChild(lblSpacer);
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

  visiblePhaseGroups().forEach(pg => {{
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

function measureTeamDotLabelWidth(teams) {{
  if (!teams.length) return 170;
  const probe = document.createElement('div');
  probe.className = 'team-dot-flag';
  probe.style.position = 'absolute';
  probe.style.visibility = 'hidden';
  probe.style.left = '-9999px';
  probe.style.width = 'auto';
  probe.style.minWidth = '0';
  probe.style.maxWidth = 'none';
  probe.style.overflow = 'visible';
  document.body.appendChild(probe);
  let maxW = 0;
  teams.forEach(team => {{
    probe.textContent = (TEAM_FLAGS[team] || '🏳️') + ' ' + team;
    maxW = Math.max(maxW, probe.scrollWidth);
  }});
  probe.remove();
  return Math.ceil(Math.max(170, Math.min(maxW + 4, 260)));
}}

// Sincroniza as réguas conforme os cards/seleção:
//  • 0-1 time em foco → só a régua principal (filtrada)
//  • 2+ cards abertos → ESCONDE a principal; cabeçalho de fases + 1 régua por time
function syncDotRows() {{
  const mainRow = document.getElementById('progressDots');
  const teamRows = document.getElementById('teamDotRows');
  teamRows.innerHTML = '';
  const cards = [...openCards.keys()];
  const timelineTeams = [...new Set([...trajectoryTeams, ...cards])];

  if (timelineTeams.length >= 2) {{
    mainRow.style.display = 'none';           // esconde a régua principal
    teamRows.style.setProperty('--team-dot-label-w', measureTeamDotLabelWidth(timelineTeams) + 'px');
    teamRows.appendChild(buildPhaseLabelRow());
    timelineTeams.forEach(t => teamRows.appendChild(buildTeamDotRow(t)));
  }} else {{
    mainRow.style.display = '';               // mostra a principal
    teamRows.style.removeProperty('--team-dot-label-w');
    const focus = timelineTeams.length === 1 ? timelineTeams[0] : (selectedTeam || null);
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

function visiblePhaseGroups() {{
  return dotPhaseFilter ? phaseGroups.filter(pg => pg.label === dotPhaseFilter) : phaseGroups;
}}

function renderMainDots() {{
  dotsEl.innerHTML = '';
  Object.keys(dotRefs).forEach(k => delete dotRefs[k]);
  allDots.length = 0;

  visiblePhaseGroups().forEach(pg => {{
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
      const markerEnd = m.round_end ? ' · fim da rodada' : (m.phase_end ? ' · fim da fase eliminatória' : '');
      d.title = m.status === 'live' ? `${{id}} — AO VIVO`
              : m.status === 'done' ? `${{id}} — clique para ver${{markerEnd}}`
              : m.status === 'missing' ? `${{id}} — finalizado, snapshot ainda não gerado${{markerEnd}}`
              : `${{id}} — ainda não disputado${{markerEnd}}`;
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
}}

renderMainDots();

// O "destacar time" da Race agora é controlado pela busca compartilhada
// (onFocusInput): digitar um nome exato destaca a barra correspondente.

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
    nameEl.addEventListener('click', e => {{ e.stopPropagation(); openModal(team); }});

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
  // Aplica os filtros GLOBAIS (grupo/confederação/fase) também às barras da Race.
  const advOnly = document.getElementById('filterAdvanced') && document.getElementById('filterAdvanced').checked;
  const filtered = frameTeams.filter(t =>
    passesGlobalFilters(t.team) && (!advOnly || (t.advanced_coverage > 0)));
  // Ordena pela QUANTIDADE bruta: 'desc' = maior primeiro, 'asc' = menor primeiro.
  const asc = sortDir === 'asc';
  return filtered.sort((a, b) => {{
    const va = a[currentMetric] ?? (asc ? Infinity : -Infinity);
    const vb = b[currentMetric] ?? (asc ? Infinity : -Infinity);
    return asc ? va - vb : vb - va;
  }});
}}

function toggleDir() {{
  sortDir = sortDir === 'desc' ? 'asc' : 'desc';
  const btn = document.getElementById('btnDir');
  btn.textContent = sortDir === 'desc' ? '↓ Maior primeiro' : '↑ Menor primeiro';
  renderBothViews();  // direção é compartilhada: vale na corrida E na grade
}}

// Card de explicação do componente (pills de peso): abre no CLIQUE, não no hover.
// Um aberto por vez; clicar de novo fecha; clicar fora também fecha.
function closeWeightPills() {{
  document.querySelectorAll('.w-pill.open').forEach(p => p.classList.remove('open'));
}}
function toggleWeightPill(event, el) {{
  event.stopPropagation();
  const wasOpen = el.classList.contains('open');
  closeWeightPills();
  if (!wasOpen) el.classList.add('open');
}}
document.addEventListener('click', () => closeWeightPills());

// Tooltip flutuante dos chips de glossário (data-tip). Delegado no document para
// pegar chips renderizados dinamicamente; segue o mouse e some ao sair.
(function initChipTip() {{
  const tip = document.getElementById('chipTip');
  if (!tip) return;
  function show(el) {{
    tip.textContent = el.getAttribute('data-tip') || '';
    tip.style.display = 'block';
    place(el);
  }}
  function place(el) {{
    const r = el.getBoundingClientRect();
    const tr = tip.getBoundingClientRect();
    let left = r.left + r.width / 2 - tr.width / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - tr.width - 8));
    let top = r.bottom + 6;
    if (top + tr.height > window.innerHeight - 8) top = r.top - tr.height - 6;  // vira p/ cima se não couber
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }}
  function hide() {{ tip.style.display = 'none'; }}
  document.addEventListener('mouseover', e => {{
    const el = e.target.closest && e.target.closest('.has-tip[data-tip]');
    if (el) show(el);
  }});
  document.addEventListener('mouseout', e => {{
    const el = e.target.closest && e.target.closest('.has-tip[data-tip]');
    if (el) hide();
  }});
}})();

// aproveitamento e clean_sheet_rate estão em fração (0–1); posse_media já é %
const PERCENT_FRAC = new Set(['aproveitamento', 'precisao_chute', 'precisao_passes']);
const PERCENT_DIRECT = new Set(['posse_media']);
// Métricas que podem ser NEGATIVAS — a barra é escalada por [min,max], não por
// |valor| (senão um valor muito negativo viraria barra cheia). xGP = gols
// evitados acima do esperado (negativo = defesa sofreu mais que o esperado).
const SIGNED_METRICS = new Set(['xgp_por_jogo', 'saldo_gols']);
// Métricas que ALIMENTAM o score_geral (insumos de qualidade), vs. as apenas
// informativas (disciplina, estilo, totais brutos). Marca estática ▪ no painel.
const SCORE_INPUT_METRICS = new Set([
  'score_resultado', 'score_ataque', 'score_defesa', 'score_eficiencia',
  'score_controle', 'score_forca_relativa',
  'pontos', 'aproveitamento', 'saldo_gols', 'elo_rating',
  'gols_por_jogo', 'xg_por_jogo', 'chutes_no_alvo_por_jogo', 'precisao_chute', 'key_passes_por_jogo',
  'gols_contra_por_jogo', 'xgp_por_jogo', 'chutes_sofridos_por_jogo', 'shots_blocked_por_jogo', 'duels_won_por_jogo',
  'posse_media', 'passes_por_jogo', 'precisao_passes', 'dribbles_won_por_jogo',
]);
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

// formatador da métrica para a grade Seleções (reusa formatVal da corrida)
function _metricFmt(metric) {{ return v => formatVal(v, metric); }}

const SCORE_INFO = {score_info_json};
const WEIGHT_COMPONENTS = [
  ['score_resultado', 'Resultado'],
  ['score_ataque', 'Ataque'],
  ['score_defesa', 'Defesa'],
  ['score_eficiencia', 'Eficiência'],
  ['score_controle', 'Controle'],
  ['score_forca_relativa', 'Força Relativa'],
];
const WEIGHT_COLORS = {{
  score_resultado: '#58a6ff',
  score_ataque: '#f97316',
  score_defesa: '#22c55e',
  score_eficiencia: '#f0c040',
  score_controle: '#a78bfa',
  score_forca_relativa: '#fb7185',
}};
const COMPONENT_FACTORS = {{
  score_resultado: [
    ['Pontos', 'Campanha convertida', 'Vitórias e empates são o sinal mais direto de produção real.'],
    ['Aproveitamento', 'Consistência', 'Mostra quanto do máximo possível a seleção transformou em tabela.'],
    ['Saldo de gols', 'Margem do placar', 'Diferencia vitória controlada de jogo decidido no detalhe.'],
    ['Gols marcados', 'Capacidade de resolver', 'Gols marcados sustentam resultado quando aparecem junto de pontos e saldo.'],
  ],
  score_ataque: [
    ['Gols por jogo', 'Produção final', 'Mostra quanto o ataque já colocou no placar.'],
    ['Gols esperados por jogo', 'Qualidade das chances', 'Ajuda a separar pressão perigosa de chute sem valor real.'],
    ['Finalizações no alvo', 'Ameaça ao goleiro', 'Finalização no alvo indica que o volume está chegando perto do gol.'],
    ['Finalizações totais', 'Volume ofensivo', 'Importa mais quando vem acompanhado de chances claras, alvo e gols.'],
  ],
  score_defesa: [
    ['Gols sofridos', 'Dano permitido', 'É a base da defesa: sofrer pouco mantém a seleção viva no ranking.'],
    ['Gols evitados por jogo', 'Proteção acima do esperado', 'Captura defesa e goleiro superando ou ficando abaixo do esperado.'],
    ['Duelos ganhos', 'Controle dos confrontos', 'Mostra força em disputas diretas, bolas aéreas e segundas bolas.'],
    ['Força do rival', 'Contexto da pressão', 'Segurar ataque forte vale mais que sobreviver contra rival inofensivo.'],
  ],
  score_eficiencia: [
    ['Gols por finalização', 'Conversão', 'Mostra se a seleção transforma tentativas em gol sem precisar de volume enorme.'],
    ['Gols contra gols esperados', 'Acima do esperado', 'Indica finalização clínica ou queda de rendimento quando fica abaixo das chances criadas.'],
    ['Precisão das finalizações', 'Pontaria', 'Chutar no alvo aumenta a chance de converter e força defesa/rebote.'],
    ['Passes-chave', 'Último passe', 'Mede criação de finalizações, ligando construção a chance concreta.'],
  ],
  score_controle: [
    ['Posse de bola', 'Ritmo do jogo', 'Ajuda a entender quem dita território e reduz fases de instabilidade.'],
    ['Passes por jogo', 'Circulação', 'Volume de passes indica capacidade de sustentar ataques e descansar com bola.'],
    ['Precisão dos passes', 'Segurança', 'Passe certo evita transição contra e mantém a estrutura da equipe.'],
    ['Dribles certos', 'Quebra de linha', 'Drible efetivo transforma posse em progressão quando rompe marcação.'],
  ],
  score_forca_relativa: [
    ['Rating Elo', 'Força estimada', 'Resume evolução da seleção considerando resultados e dificuldade.'],
    ['Margem de vitória', 'Tamanho do resultado', 'Ganhar bem contra rival competitivo melhora a leitura da campanha.'],
    ['Força dos adversários', 'Dificuldade do caminho', 'O mesmo placar vale mais quando vem contra uma seleção mais forte.'],
    ['Sequência de resultados', 'Sustentação', 'Resultados repetidos reduzem a chance de uma leitura baseada em jogo isolado.'],
  ],
}};
const WEIGHT_GUIDE_TABS = [
  ['overview', 'Visão geral'],
  ['why', 'Por que muda?'],
  ['impact', 'Impacto'],
  ['component', 'Componentes'],
  ['faq', 'FAQ'],
];
const WEIGHT_GUIDE_FAQ = [
  {{
    q: 'Os pesos mudam por opinião ou por dado?',
    a: 'Mudam por dado. Resultado e Força Relativa têm uma regra de design mais estável; Ataque, Defesa, Eficiência e Controle são recalibrados conforme os jogos finalizados mostram quais sinais explicam melhor o desempenho real — pontos + saldo de gols + saldo de xG (quão merecido foi o resultado).'
  }},
  {{
    q: 'Por que recalibrar a cada jogo?',
    a: 'Porque a Copa começa com pouca amostra. Um jogo novo pode revelar que, naquele momento do torneio, defesa está separando melhor as seleções do que posse, ou que eficiência está explicando mais o placar do que volume ofensivo. A recalibração evita congelar uma suposição ruim.'
  }},
  {{
    q: 'Isso muda o passado?',
    a: 'O dashboard mostra cada snapshot com os pesos daquele momento da análise. A leitura correta é temporal: após cada jogo, o modelo reavalia o que já sabe e recalcula o ranking com a evidência disponível até ali.'
  }},
  {{
    q: 'Um peso baixo significa que o componente não importa?',
    a: 'Não. Significa que, naquele recorte, ele explicou menos a diferença de desempenho entre as seleções do que os outros componentes. Controle, por exemplo, pode ser importante para estilo, mas ter peso baixo se a posse não estiver virando vantagem no placar.'
  }},
  {{
    q: 'Como isso influencia a nota geral?',
    a: 'A nota geral é uma média ponderada. Se Ataque pesa 18%, uma melhora ofensiva mexe mais no score do que mexeria com Ataque a 8%. O peso define a força de cada lente dentro da leitura final.'
  }},
  {{
    q: 'Por que Resultado pesa tanto?',
    a: 'Porque ranking de torneio precisa respeitar o placar. Métricas de processo ajudam a explicar e antecipar qualidade, mas a campanha real continua sendo o eixo mais sólido da classificação.'
  }},
  {{
    q: 'E a Força Relativa?',
    a: 'Ela contextualiza contra quem a seleção jogou. No início, todo mundo parte próximo no Elo, então o peso prático é menor. Conforme rivais fortes e fracos se separam, esse componente ganha mais capacidade de explicar campanhas difíceis.'
  }},
];
let weightsGuideTab = 'overview';
let weightsGuideComponent = 'score_resultado';
let weightsGuideWeightFocus = null;
let weightsCompareA = '';
let weightsCompareB = '';
let weightsGuideJogo = null;

function _guideJogo() {{
  return DATA[weightsGuideJogo] ? weightsGuideJogo : currentJogo;
}}
function _guideFrame() {{
  return DATA[_guideJogo()] || DATA[lastJogo()] || {{}};
}}
function _guideWeight(key) {{
  const p = _guideFrame().pesos || {{}};
  return p[key] === undefined ? null : p[key];
}}
function _guideMatchLabel() {{
  const frame = _guideFrame();
  const n = _guideJogo();
  const pos = sliderValueForJogo(n);
  const match = frame.source_match_n || (frame.match_n ? String(frame.match_n).padStart(3, '0') : '');
  return `Jogo ${{pos || 'atual'}}${{match ? ` · ${{match}}` : ''}}`;
}}
function _guideSnapshotControlHtml() {{
  const n = _guideJogo();
  const pos = sliderValueForJogo(n);
  return `<div class="wg-snapshot-control">
    <button type="button" class="wg-snap-btn" onclick="stepWeightsGuideSnapshot(-1)" title="Snapshot anterior">‹</button>
    <div class="wg-snap-mid">
      <input type="range" min="1" max="${{N}}" value="${{pos}}" oninput="setWeightsGuideSnapshot(jogoFromSliderValue(this.value))">
      <div class="wg-snap-label">${{_guideMatchLabel()}}</div>
    </div>
    <button type="button" class="wg-snap-btn" onclick="stepWeightsGuideSnapshot(1)" title="Próximo snapshot">›</button>
  </div>`;
}}
function _availableCompareTeams() {{
  const frame = _guideFrame();
  return (frame.teams || []).filter(t => t && t.team).map(t => t.team);
}}
function _ensureCompareTeams() {{
  const teams = _availableCompareTeams();
  const preferred = [...trajectoryTeams, selectedTeam].filter(Boolean);
  if (!teams.includes(weightsCompareA)) weightsCompareA = preferred.find(t => teams.includes(t)) || teams[0] || '';
  if (!teams.includes(weightsCompareB) || weightsCompareB === weightsCompareA) {{
    weightsCompareB = preferred.find(t => teams.includes(t) && t !== weightsCompareA)
      || teams.find(t => t !== weightsCompareA)
      || '';
  }}
}}
function _weightPctText(value) {{
  const n = Number(value);
  if (!Number.isFinite(n)) return '0.0';
  return n.toFixed(1);
}}
function _guideWeightRows() {{
  return WEIGHT_COMPONENTS
    .map(c => ({{ key: c[0], label: c[1], value: Number(_guideWeight(c[0]) || 0), color: WEIGHT_COLORS[c[0]] || '#58a6ff' }}))
    .filter(r => r.value > 0);
}}
function _sumGuideWeights(keys) {{
  return keys.reduce((sum, key) => sum + Number(_guideWeight(key) || 0), 0);
}}
function _weightBarsHtml() {{
  const rows = _guideWeightRows();
  const total = rows.reduce((sum, r) => sum + r.value, 0);
  if (!rows.length || total <= 0) return '<div class="wg-example">Pesos ainda não carregados para este snapshot.</div>';
  const focused = rows.find(r => r.key === weightsGuideWeightFocus) || null;
  const centerValue = focused ? _weightPctText(focused.value) : _weightPctText(total);
  const centerLabel = focused ? focused.label : 'Total';
  const radius = 42;
  const circ = 2 * Math.PI * radius;
  let offset = 0;
  const arcs = rows.map(r => {{
    const pct = Math.max(0, r.value / total);
    const len = pct * circ;
    const label = `${{r.label}} · ${{_weightPctText(r.value)}}%`;
    const stateCls = focused ? (focused.key === r.key ? ' active' : ' dimmed') : '';
    const arc = `<circle class="wg-weight-arc${{stateCls}}" cx="50" cy="50" r="${{radius}}" pathLength="${{circ.toFixed(3)}}" stroke-dasharray="${{len.toFixed(3)}} ${{circ.toFixed(3)}}" stroke-dashoffset="${{(-offset).toFixed(3)}}" style="--wg-color:${{r.color}}" transform="rotate(-90 50 50)" tabindex="0" role="button" onclick="setWeightDonutFocus('${{r.key}}')" onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();setWeightDonutFocus('${{r.key}}')}}"><title>${{label}}</title></circle>`;
    offset += len;
    return arc;
  }}).join('');
  const legend = rows.map(r => `
    <button type="button" class="wg-weight-item${{focused && focused.key === r.key ? ' active' : ''}}" title="${{r.label}} · ${{_weightPctText(r.value)}}%" onclick="setWeightDonutFocus('${{r.key}}')">
      <span class="wg-weight-swatch" style="--wg-color:${{r.color}}"></span>
      <span class="wg-weight-name">${{r.label}}</span>
      <span class="wg-weight-val">${{_weightPctText(r.value)}}%</span>
    </button>`).join('');
  const aria = rows.map(r => `${{r.label}} ${{_weightPctText(r.value)}}%`).join(', ');
  return `<div class="wg-weight-donut-card">
    <div class="wg-weight-donut-wrap">
      <svg class="wg-weight-donut" viewBox="0 0 100 100" role="img" aria-label="Distribuição dos pesos do ranking: ${{aria}}">
        <circle class="wg-weight-donut-bg" cx="50" cy="50" r="${{radius}}"></circle>
        ${{arcs}}
      </svg>
      <div class="wg-weight-donut-center"><div><b>${{centerValue}}%</b><span>${{centerLabel}}</span></div></div>
    </div>
    <div class="wg-weight-panel">
      <div class="wg-weight-panel-head"><span>Distribuição dos pesos</span><b>${{rows.length}} componentes</b></div>
      <div class="wg-weight-legend">${{legend}}</div>
    </div>
  </div>`;
}}
function _componentPickerHtml() {{
  return `<div class="wg-component-picker">${{WEIGHT_COMPONENTS.map(c => `
    <button class="wg-comp-btn${{weightsGuideComponent === c[0] ? ' active' : ''}}" onclick="setWeightsGuideComponent('${{c[0]}}')">${{c[1]}}</button>
  `).join('')}}</div>`;
}}
function _componentGuideHtml() {{
  const key = weightsGuideComponent;
  const label = (WEIGHT_COMPONENTS.find(c => c[0] === key) || [key, key])[1];
  const info = SCORE_INFO[key] || {{}};
  const weight = _guideWeight(key);
  const factors = COMPONENT_FACTORS[key] || [];
  const factorHtml = factors.map(([metric, title, copy]) => `
    <div class="wg-factor-card">
      <span>${{metric}}</span>
      <b>${{title}}</b>
      <p>${{copy}}</p>
    </div>`).join('');
  return `${{_componentPickerHtml()}}
    <div class="wg-component-card">
      <div class="wg-component-head">
        <div>
          <h3>${{info.title || label}}</h3>
          <span>${{info.role || 'Componente da nota'}}</span>
        </div>
        <div class="wg-component-weight">${{weight == null ? '—' : _weightPctText(weight)}}%</div>
      </div>
      <p>${{info.desc || ''}}</p>
      <p>${{info.detail || ''}}</p>
      ${{info.good ? `<div class="wg-example"><b>Como ler:</b> ${{info.good}}.</div>` : ''}}
      ${{factorHtml ? `<div class="wg-factor-grid">${{factorHtml}}</div>` : ''}}
      <div class="wg-factor-note"><b>Cuidado de leitura:</b> nenhum item decide sozinho. O componente fica forte quando os sinais contam a mesma história — por exemplo, volume com qualidade, defesa com pouco dano sofrido, ou resultado com contexto de rival.</div>
    </div>`;
}}
function _faqHtml() {{
  return `<div class="wg-faq">${{WEIGHT_GUIDE_FAQ.map((item, i) => `
    <div class="wg-faq-item${{i === 0 ? ' open' : ''}}">
      <button type="button" class="wg-faq-q" onclick="toggleWeightsFaq(this)">
        <span class="wg-faq-num">${{i + 1}}</span>
        <span class="wg-faq-title">${{item.q}}</span>
      </button>
      <div class="wg-faq-a">${{item.a}}</div>
    </div>
  `).join('')}}</div>`;
}}
function _fmtSigned(v, digits = 1) {{
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  const s = Math.abs(v).toFixed(digits);
  return `${{v > 0 ? '+' : v < 0 ? '-' : ''}}${{s}}`;
}}
function _teamOptionHtml(team) {{
  const flag = TEAM_FLAGS[team] || (TEAMS_DETAIL[team] || {{}}).flag || '';
  const snap = teamEntryAt(team, _guideJogo());
  const rank = (SNAP_RANK[_guideJogo()] || {{}})[team];
  const suffix = rank ? ` · #${{rank}}` : snap && snap.score_geral != null ? ` · ${{snap.score_geral.toFixed(1)}}` : '';
  return `${{flag}} ${{team}}${{suffix}}`;
}}
function _compareTeamSelectHtml(id, label, value) {{
  const teams = _availableCompareTeams();
  return `<label class="wg-field"><span>${{label}}</span>
    <select id="${{id}}" onchange="setWeightsCompareTeam('${{id}}', this.value)">
      ${{teams.map(t => `<option value="${{_esc(t)}}" ${{t === value ? 'selected' : ''}}>${{_esc(_teamOptionHtml(t))}}</option>`).join('')}}
    </select>
  </label>`;
}}
function _weightedCompareRows(a, b) {{
  const neutralWeight = 100 / WEIGHT_COMPONENTS.length;
  return WEIGHT_COMPONENTS.map(([key, label]) => {{
    const weight = _guideWeight(key) ?? 0;
    const av = a[key];
    const bv = b[key];
    const delta = (av ?? 0) - (bv ?? 0);
    const weighted = delta * weight / 100;
    const neutral = delta * neutralWeight / 100;
    const shift = weighted - neutral;
    return {{ key, label, weight, av, bv, delta, weighted, neutral, shift }};
  }});
}}
function _weightedTeamScore(t, neutral = false) {{
  const neutralWeight = 100 / WEIGHT_COMPONENTS.length;
  if (!neutral && t.score_geral != null) return t.score_geral;
  return WEIGHT_COMPONENTS.reduce((sum, [key]) => {{
    const weight = neutral ? neutralWeight : (_guideWeight(key) ?? 0);
    return sum + ((t[key] ?? 0) * weight / 100);
  }}, 0);
}}
function _snapshotWeightMapHtml() {{
  const teams = (_guideFrame().teams || []).filter(t => t && t.team);
  if (!teams.length) return '';
  const effects = teams.map(t => {{
    const weighted = _weightedTeamScore(t, false);
    const neutral = _weightedTeamScore(t, true);
    return {{ team: t.team, flag: t.flag || TEAM_FLAGS[t.team] || '', estilo: t.estilo_jogo || 'Sem estilo definido', effect: weighted - neutral }};
  }}).sort((a, b) => b.effect - a.effect);
  const top = effects[0];
  const low = effects[effects.length - 1];
  const byStyle = {{}};
  effects.forEach(x => {{
    if (!byStyle[x.estilo]) byStyle[x.estilo] = {{ estilo: x.estilo, effect: 0, n: 0 }};
    byStyle[x.estilo].effect += x.effect;
    byStyle[x.estilo].n += 1;
  }});
  const style = Object.values(byStyle)
    .map(x => Object.assign(x, {{ avg: x.effect / Math.max(1, x.n) }}))
    .sort((a, b) => b.avg - a.avg)[0];
  return `<div class="wg-snapshot-strip">
    <div class="wg-snapshot-pill"><span>Favorecida no snapshot</span><b>${{top.flag}} ${{top.team}}</b><small>${{_fmtSigned(top.effect)}} vs. régua neutra</small></div>
    <div class="wg-snapshot-pill"><span>Mais cobrada pela régua</span><b>${{low.flag}} ${{low.team}}</b><small>-${{Math.abs(low.effect).toFixed(1)}} vs. régua neutra</small></div>
    <div class="wg-snapshot-pill"><span>Estilo favorecido</span><b>${{style.estilo}}</b><small>Média ${{_fmtSigned(style.avg)}} por seleção</small></div>
  </div>`;
}}
function _compareNarrative(rows, aTeam, bTeam, a, b) {{
  const actualDelta = (a.score_geral ?? 0) - (b.score_geral ?? 0);
  const weightedDelta = actualDelta;
  const neutralDelta = rows.reduce((s, r) => s + r.neutral, 0);
  const weightEffect = weightedDelta - neutralDelta;
  const winner = actualDelta >= 0 ? aTeam : bTeam;
  const loser = actualDelta >= 0 ? bTeam : aTeam;
  const decisive = rows.slice().sort((x, y) => Math.abs(y.weighted) - Math.abs(x.weighted))[0];
  const shiftRow = rows.slice().sort((x, y) => Math.abs(y.shift) - Math.abs(x.shift))[0];
  const favored = Math.abs(weightEffect) < 0.15 ? 'Neutro' : (weightEffect > 0 ? aTeam : bTeam);
  const favoredWhy = !shiftRow || Math.abs(weightEffect) < 0.15
    ? 'Os pesos atuais não mudam muito a leitura contra pesos iguais.'
    : `${{shiftRow.label}} pesa ${{_weightPctText(shiftRow.weight)}}% e ${{weightEffect > 0 ? aTeam : bTeam}} está melhor posicionado nessa lente.`;
  const flip = Math.sign(weightedDelta || actualDelta) !== Math.sign(neutralDelta || actualDelta) && Math.abs(neutralDelta) > 0.15;
  return {{ actualDelta, weightedDelta, neutralDelta, weightEffect, winner, loser, decisive, favored, favoredWhy, flip }};
}}
function _compareGuideHtml() {{
  _ensureCompareTeams();
  const aTeam = weightsCompareA;
  const bTeam = weightsCompareB;
  if (!aTeam || !bTeam) return '<div class="wg-example">Ainda não há duas seleções com dados neste snapshot para comparar.</div>';
  const a = teamEntryAt(aTeam, _guideJogo());
  const b = teamEntryAt(bTeam, _guideJogo());
  if (!a || !b) return '<div class="wg-example">Escolha duas seleções que já tenham entrado no ranking neste snapshot.</div>';
  const rows = _weightedCompareRows(a, b);
  const story = _compareNarrative(rows, aTeam, bTeam, a, b);
  const maxAbs = Math.max(0.01, ...rows.map(r => Math.abs(r.weighted)));
  const sortedRows = rows.slice().sort((x, y) => Math.abs(y.weighted) - Math.abs(x.weighted));
  const styleA = a.estilo_jogo ? ` · ${{a.estilo_jogo}}` : '';
  const styleB = b.estilo_jogo ? ` · ${{b.estilo_jogo}}` : '';
  const rankA = (SNAP_RANK[_guideJogo()] || {{}})[aTeam];
  const rankB = (SNAP_RANK[_guideJogo()] || {{}})[bTeam];
  const neutralA = _weightedTeamScore(a, true);
  const neutralB = _weightedTeamScore(b, true);
  const currentA = _weightedTeamScore(a, false);
  const currentB = _weightedTeamScore(b, false);
  const effectA = currentA - neutralA;
  const effectB = currentB - neutralB;
  const rowHtml = sortedRows.map((r, idx) => {{
    const side = r.weighted >= 0 ? 'a' : 'b';
    const width = Math.max(3, Math.abs(r.weighted) / maxAbs * 50);
    const who = r.weighted >= 0 ? aTeam : bTeam;
    return `<tr class="${{idx === 0 ? 'top' : ''}}">
      <td>${{r.label}}</td>
      <td class="wg-compare-weight">${{_weightPctText(r.weight)}}%</td>
      <td>${{(r.av ?? 0).toFixed(1)}}</td>
      <td>${{(r.bv ?? 0).toFixed(1)}}</td>
      <td class="wg-compare-delta ${{r.delta >= 0 ? 'pos' : 'neg'}}">${{_fmtSigned(r.delta)}}</td>
      <td><div class="wg-impact" title="Impacto no score final: ${{who}} ${{_fmtSigned(Math.abs(r.weighted))}}">
        <div class="wg-compare-track"><div class="wg-compare-fill ${{side}}" style="width:${{width}}%"></div></div>
        <div class="wg-compare-val">${{r.weighted >= 0 ? 'A' : 'B'}} ${{_fmtSigned(Math.abs(r.weighted))}}</div>
      </div></td>
    </tr>`;
  }}).join('');
  return `
    <div class="wg-compare-controls">
      ${{_compareTeamSelectHtml('weightsCompareA', 'Seleção A', aTeam)}}
      ${{_compareTeamSelectHtml('weightsCompareB', 'Seleção B', bTeam)}}
    </div>
    <div class="wg-scoreboard">
      <div class="wg-team-score a">
        <div class="wg-team-name">${{TEAM_FLAGS[aTeam] || ''}} ${{aTeam}}</div>
        <div class="wg-team-meta">Seleção A${{rankA ? ` · #${{rankA}}` : ''}}${{styleA}}</div>
        <div class="wg-team-kpis">
          <div class="wg-kpi"><span>Score atual</span><b>${{currentA.toFixed(1)}}</b></div>
          <div class="wg-kpi"><span>Score neutro</span><b>${{neutralA.toFixed(1)}}</b></div>
          <div class="wg-kpi"><span>Efeito pesos</span><b>${{_fmtSigned(effectA)}}</b></div>
        </div>
      </div>
      <div class="wg-score-delta"><span>Diferença</span><b>${{_fmtSigned(story.actualDelta)}}</b></div>
      <div class="wg-team-score b">
        <div class="wg-team-name">${{TEAM_FLAGS[bTeam] || ''}} ${{bTeam}}</div>
        <div class="wg-team-meta">Seleção B${{rankB ? ` · #${{rankB}}` : ''}}${{styleB}}</div>
        <div class="wg-team-kpis">
          <div class="wg-kpi"><span>Score atual</span><b>${{currentB.toFixed(1)}}</b></div>
          <div class="wg-kpi"><span>Score neutro</span><b>${{neutralB.toFixed(1)}}</b></div>
          <div class="wg-kpi"><span>Efeito pesos</span><b>${{_fmtSigned(effectB)}}</b></div>
        </div>
      </div>
    </div>
    <div class="wg-diagnosis">
      <div class="wg-diagnosis-main"><b>${{story.winner}}</b> lidera contra <b>${{story.loser}}</b> por ${{_fmtSigned(Math.abs(story.actualDelta))}} ponto(s). A régua atual favorece <b>${{story.favored === 'Neutro' ? 'uma leitura quase neutra' : story.favored}}</b> em relação a pesos iguais.${{story.flip ? ' Com pesos iguais, a leitura mudaria de lado ou ficaria praticamente invertida.' : ''}}</div>
      <div class="wg-diagnosis-meta">
        <div class="wg-diag-chip"><span>Lente decisiva</span>${{story.decisive.label}}</div>
        <div class="wg-diag-chip"><span>Por quê</span>${{story.favoredWhy}}</div>
        <div class="wg-diag-chip"><span>Perfis</span>${{aTeam}}${{styleA}} · ${{bTeam}}${{styleB}}</div>
      </div>
    </div>
    <div class="wg-compare-table-wrap">
      <table class="wg-compare-table">
        <colgroup>
          <col style="width: 22%">
          <col style="width: 9%">
          <col style="width: 10%">
          <col style="width: 10%">
          <col style="width: 10%">
          <col style="width: 39%">
        </colgroup>
        <thead><tr><th>Componente</th><th>Peso</th><th>A pts</th><th>B pts</th><th>Delta</th><th>Impacto no score</th></tr></thead>
        <tbody>${{rowHtml}}</tbody>
      </table>
    </div>
    <div class="wg-compare-note">“A pts” e “B pts” são as notas de 0 a 100 em cada componente. “Impacto” é a diferença multiplicada pelo peso atual; azul favorece a Seleção A e amarelo favorece a Seleção B. Score neutro usa 16,7% para cada componente.</div>`;
}}
function toggleWeightsFaq(btn) {{
  const item = btn.closest('.wg-faq-item');
  if (!item) return;
  const wasOpen = item.classList.contains('open');
  const root = item.parentElement;
  root.querySelectorAll('.wg-faq-item.open').forEach(el => el.classList.remove('open'));
  if (!wasOpen) item.classList.add('open');
}}
function _guideSectionHtml(tab) {{
  if (tab === 'overview') return `
    <div class="wg-kicker">Pesos atuais · ${{_guideMatchLabel()}}</div>
    <div class="wg-h2">O ranking combina placar, processo e contexto.</div>
    <p class="wg-lead">Cada peso diz quanto uma lente entra na nota geral naquele momento do torneio. O placar ancora a análise; os componentes de processo ajudam a separar desempenho sustentável de resultado ocasional; a força relativa ajusta a dificuldade do caminho.</p>
    ${{_weightBarsHtml()}}
    <div class="wg-grid">
      <div class="wg-card"><b>Não é uma tabela fixa</b><p>Os pesos acompanham o que os jogos já mostraram. Conforme a amostra cresce, o modelo entende melhor quais sinais estão explicando o saldo real.</p></div>
      <div class="wg-card"><b>Comparação justa no tempo</b><p>Após cada partida, o snapshot usa a evidência disponível até aquele ponto. A leitura vira uma história da Copa, não só uma foto final.</p></div>
      <div class="wg-card"><b>Processo importa, mas com limite</b><p>Chutar, controlar e defender bem ajudam; vencer e construir saldo continuam tendo prioridade porque ranking de torneio precisa respeitar o resultado.</p></div>
    </div>`;
  if (tab === 'why') return `
    <div class="wg-kicker">Recalibração</div>
    <div class="wg-h2">Os pesos variam porque o torneio muda a evidência.</div>
    <p class="wg-lead">No começo, há poucos jogos e muito ruído: uma goleada, uma expulsão ou um adversário fraco podem distorcer métricas. A cada jogo finalizado, os componentes de processo são comparados com desempenho real — <b>pontos</b>, <b>saldo de gols</b> e <b>saldo de xG</b> — para ajustar o quanto cada lente deve pesar.</p>
    <div class="wg-flow single">
      <div class="wg-step"><span class="wg-step-num">1</span><p><b>Entra evidência nova.</b><br>Placar, volume ofensivo, qualidade das chances, defesa, controle e força do rival entram no snapshot.</p></div>
      <div class="wg-step"><span class="wg-step-num">2</span><p><b>O modelo compara sinais.</b><br>Ele mede quais componentes estão mais alinhados com desempenho real, não só com uma posse bonita ou um placar isolado.</p></div>
      <div class="wg-step"><span class="wg-step-num">3</span><p><b>Processo é recalibrado.</b><br>Ataque, Defesa, Eficiência e Controle sobem ou descem conforme explicam melhor pontos, saldo e xG.</p></div>
      <div class="wg-step"><span class="wg-step-num">4</span><p><b>A leitura fica temporal.</b><br>Resultado e Força Relativa preservam a lógica de torneio; o restante acompanha o que a Copa já mostrou.</p></div>
    </div>
    <div class="wg-example-grid">
      <div class="wg-example-card"><span>Quando controle cai</span><b>Posse sem dano perde voz.</b><p>Se a bola fica muito tempo com uma seleção, mas isso não vira chance clara, xG ou saldo, Controle explica estilo e não vantagem real.</p></div>
      <div class="wg-example-card"><span>Quando defesa sobe</span><b>Evitar chance começa a separar times.</b><p>Se quem concede pouco xG, poucos chutes perigosos e poucos gols começa a abrir saldo, Defesa ganha peso porque está explicando resultado.</p></div>
      <div class="wg-example-card"><span>Quando eficiência pesa</span><b>Finalizar melhor que o volume importa.</b><p>Se duas seleções chutam parecido, mas uma converte chances melhores e erra menos decisões no terço final, Eficiência passa a contar mais.</p></div>
    </div>`;
  if (tab === 'impact') return `
    <div class="wg-kicker">Influência na análise</div>
    <div class="wg-h2">Peso é a força de cada pergunta dentro da nota final.</div>
    <p class="wg-lead">A nota geral funciona como uma média ponderada dos componentes. Por isso, a mesma melhora em uma métrica pode mudar muito ou pouco a posição dependendo do peso atual daquela lente.</p>
    <div class="wg-flow single">
      <div class="wg-step"><span class="wg-step-num">1</span><p><b>No ranking.</b><br>Componentes com maior peso movem mais as barras e a ordem das seleções. Um Ataque a 18% tem mais impacto que um Ataque a 8%.</p></div>
      <div class="wg-step"><span class="wg-step-num">2</span><p><b>Na interpretação.</b><br>O peso mostra qual narrativa está mais forte naquele ponto: campanha, defesa, criação, eficiência, controle ou dificuldade do caminho.</p></div>
      <div class="wg-step"><span class="wg-step-num">3</span><p><b>Na comparação.</b><br>Seleções parecidas em pontos podem se separar por processo. Seleções bonitas de ver, mas pouco efetivas, perdem força se processo não vira placar.</p></div>
    </div>
    <div class="wg-example-grid">
      <div class="wg-example-card"><span>Quando o peso é alto</span><b>A mesma diferença vale mais.</b><p>Se Ataque pesa 18%, abrir 10 pontos no ataque rende mais score final do que abrir os mesmos 10 pontos em uma lente de 7%.</p></div>
      <div class="wg-example-card"><span>Quando o peso é baixo</span><b>Boa métrica não garante subida.</b><p>Uma seleção pode controlar bem o jogo, mas subir pouco se Controle estiver baixo e esse domínio não estiver virando chance, gol ou saldo.</p></div>
      <div class="wg-example-card"><span>Quando comparar times</span><b>Olhe a lente que separa.</b><p>Entre duas seleções parecidas em pontos, a posição costuma sair da lente com maior peso: resultado, defesa, ataque, eficiência ou força do rival.</p></div>
    </div>`;
  if (tab === 'component') return `
    <div class="wg-kicker">Componentes</div>
    <div class="wg-h2">Explore cada lente do ranking.</div>
    <p class="wg-lead">Clique em um componente para ver o peso atual, o que ele mede e como ele deve ser interpretado dentro da análise.</p>
    ${{_componentGuideHtml()}}`;
  return `
    <div class="wg-kicker">Perguntas frequentes</div>
    <div class="wg-h2">Dúvidas comuns sobre pesos dinâmicos.</div>
    <p class="wg-lead">Use estas perguntas como guia de leitura quando um peso subir, cair ou parecer contraintuitivo durante a Copa.</p>
    ${{_faqHtml()}}`;
}}
function renderWeightsGuide() {{
  const modal = document.getElementById('weightsGuide');
  const nav = document.getElementById('weightsGuideNav');
  const body = document.getElementById('weightsGuideBody');
  const sub = document.getElementById('weightsGuideSub');
  if (!modal || !nav || !body) return;
  if (sub) sub.textContent = `Pesos do snapshot selecionado · ${{_guideMatchLabel()}}`;
  nav.innerHTML = WEIGHT_GUIDE_TABS.map(t =>
    `<button class="wg-tab${{weightsGuideTab === t[0] ? ' active' : ''}}" onclick="switchWeightsGuideTab('${{t[0]}}')">${{t[1]}}</button>`
  ).join('');
  body.innerHTML = `<section class="wg-section active">${{_guideSectionHtml(weightsGuideTab)}}</section>`;
}}
function openWeightsGuide(tab = 'overview', componentKey = null) {{
  if (tab) weightsGuideTab = tab;
  if (componentKey) weightsGuideComponent = componentKey;
  closeWeightPills();
  const modal = document.getElementById('weightsGuide');
  if (!modal) return;
  if (modal.style.display === 'none' || !weightsGuideJogo) weightsGuideJogo = currentJogo;
  modal.style.display = 'flex';
  renderWeightsGuide();
}}
function closeWeightsGuide() {{
  const modal = document.getElementById('weightsGuide');
  if (modal) modal.style.display = 'none';
}}
function switchWeightsGuideTab(tab) {{
  weightsGuideTab = tab;
  renderWeightsGuide();
}}
function setWeightsGuideComponent(key) {{
  weightsGuideTab = 'component';
  weightsGuideComponent = key;
  renderWeightsGuide();
}}
function setWeightDonutFocus(key) {{
  weightsGuideWeightFocus = weightsGuideWeightFocus === key ? null : key;
  renderWeightsGuide();
}}
function setWeightsGuideSnapshot(n) {{
  n = Number(n);
  if (!DATA[n]) return;
  weightsGuideJogo = n;
  _ensureCompareTeams();
  renderWeightsGuide();
}}
function stepWeightsGuideSnapshot(dir) {{
  const n = _guideJogo();
  const next = dir > 0 ? nextJogo(n) : prevJogo(n);
  if (next != null) setWeightsGuideSnapshot(next);
}}
function setWeightsCompareTeam(id, team) {{
  if (id === 'weightsCompareA') weightsCompareA = team;
  if (id === 'weightsCompareB') weightsCompareB = team;
  if (weightsCompareA && weightsCompareA === weightsCompareB) {{
    const teams = _availableCompareTeams();
    const other = teams.find(t => t !== weightsCompareA);
    if (id === 'weightsCompareA') weightsCompareB = other || '';
    else weightsCompareA = other || '';
  }}
  renderWeightsGuide();
}}

function renderJogo(n) {{
  const frame = DATA[n];
  if (!frame) return;

  const timelinePos = sliderValueForJogo(n);
  slider.value = timelinePos;
  document.getElementById('sliderLabel').textContent = `Jogo ${{timelinePos}} / ${{N}}`;
  // título único, bandeiras ao redor do placar: Casa 🏠 placar 🚩 Fora
  document.getElementById('frameTitle').innerHTML =
    `<span style="color:#8b949e;font-weight:400">Após ${{timelinePos}}/${{N}} · Jogo ${{frame.source_match_n || String(frame.match_n).padStart(3, '0')}} ·</span> ` +
    `${{frame.home}} ${{frame.home_flag}} ` +
    `<span style="color:#58a6ff">${{frame.score}}</span> ` +
    `${{frame.away_flag}} ${{frame.away}}`;
  document.getElementById('frameSub').textContent = '';

  // weights pills com tooltip explicativo
  const p = frame.pesos || {{}};
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
    return `<button type="button" class="w-pill" onclick="openWeightsGuide('component', '${{key}}')" title="Abrir explicação de ${{label}}">
      <span class="w-name">${{label}}</span>
      <span class="w-val">${{_weightPctText(v)}}%</span>
    </button>`;
  }}).join('');
  const helpHtml = `<button type="button" class="weights-help-btn" onclick="openWeightsGuide('overview')" title="Entenda pesos dinâmicos">?</button>`;
  document.getElementById('weightsPills').innerHTML = pillsHtml ? helpHtml + pillsHtml : '<span style="font-size:0.7rem;color:#6b7280">Pesos carregando…</span>';
  closeWeightPills();  // re-render fecha qualquer card aberto (evita ficar preso ao trocar de jogo)
  if (document.getElementById('weightsGuide')?.style.display !== 'none') renderWeightsGuide();

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
  // Métricas COM SINAL (podem ser negativas): xGP, saldo de gols. A barra por
  // |valor| faria um -1.76 virar barra cheia (parecendo ótimo). Aqui mapeamos
  // linearmente de [min, max] → [3%, 100%], então negativos ficam curtos e o
  // comprimento reflete a ordem real. O ranking/sort já está correto à parte.
  const isSigned = SIGNED_METRICS.has(currentMetric) && vals.some(v => v < 0);
  const signedMin = isSigned ? Math.min(...vals) : 0;
  const signedMax = isSigned ? Math.max(...vals) : 0;
  const signedSpan = (signedMax - signedMin) || 1;

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
    }} else if (isSigned) {{
      // mapeia [min,max] → [3,100]; o pior (mais negativo) fica curto, não cheio
      pct = (3 + (v - signedMin) / signedSpan * 97).toFixed(2);
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
    const isInTrajectory = trajectoryTeams.includes(t.team);
    const isActive = isInCard || isInTrajectory || t.team === selectedTeam;
    // cards abertos: sem dimming, todos visíveis e clicáveis — só o destaque diferencia
    // selectedTeam sem cards: comportamento original de dimming
    const dimOthers = !openCards.size && (selectedTeam || trajectoryTeams.length) && !isActive;
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
  renderTrajectoryModal();
  renderPointCompareModal();
  refreshAllCards();
}}

function trajectoryMetricKey() {{
  return trajectoryMetric === '__current' ? currentMetric : trajectoryMetric;
}}

function trajectoryMetricDir(metric) {{
  if (trajectoryMetric === '__current') return sortDir;
  return LOWER_IS_BETTER.has(metric) ? 'asc' : 'desc';
}}

function trajectoryColor(team) {{
  const idx = Math.max(0, trajectoryTeams.indexOf(team));
  return TRAJECTORY_COLORS[idx % TRAJECTORY_COLORS.length];
}}

function trajectoryUniverse(frame, team) {{
  let teams = (frame.teams || []).filter(x => passesGlobalFilters(x.team));
  if (!teams.some(x => x.team === team)) teams = frame.teams || [];
  return teams;
}}

function trajectoryPoint(team, j, metric, dir) {{
  const frame = DATA[j];
  if (!frame) return null;
  const entry = (SNAP_BY_TEAM[j] || {{}})[team];
  if (!entry || entry[metric] === null || entry[metric] === undefined) return null;
  const universe = trajectoryAxis === 'team' ? (frame.teams || []) : trajectoryUniverse(frame, team);
  const mr = metricRank(metric, universe, team, dir);
  if (!mr) return null;
  return {{ jogo: j, value: entry[metric], rank: mr.rank, total: mr.total, teamGames: entry.jogos || 0 }};
}}

function trajectorySeries(team, metric, dir) {{
  const all = jogos.map(j => trajectoryPoint(team, j, metric, dir)).filter(Boolean);
  if (trajectoryAxis !== 'team') {{
    return all.map(p => Object.assign({{}}, p, {{ teamOrder: p.teamGames || 0 }}));
  }}
  const byGame = [];
  let lastGames = 0;
  all.forEach(p => {{
    const games = p.teamGames || 0;
    if (p.jogo <= currentJogo && games > lastGames) {{
      byGame.push(Object.assign({{}}, p, {{ teamOrder: games }}));
      lastGames = games;
    }}
  }});
  return byGame;
}}

function trajectorySeriesByTeam(teams, metric, dir) {{
  const out = {{}};
  teams.forEach(team => {{ out[team] = trajectorySeries(team, metric, dir); }});
  if (trajectoryAxis !== 'team' || teams.length < 2) return out;

  const aligned = {{}};
  teams.forEach(team => {{ aligned[team] = []; }});
  Object.entries(comparableTeamGameSnapshots(teams)).forEach(([teamOrder, snapshot]) => {{
    const order = Number(teamOrder);
    const n = Number(snapshot);
    teams.forEach(team => {{
      const p = trajectoryPoint(team, n, metric, dir);
      if (p && (p.teamGames || 0) >= order) {{
        aligned[team].push(Object.assign({{}}, p, {{ teamOrder: order }}));
      }}
    }});
  }});
  return aligned;
}}

function trajectoryCurrentPoint(series) {{
  let cur = null;
  series.forEach(p => {{
    if (p.jogo <= currentJogo) cur = p;
  }});
  return cur || series[series.length - 1] || null;
}}

function trajectoryPreviousPoint(series, point) {{
  if (!point) return null;
  let prev = null;
  series.forEach(p => {{
    if (p.jogo < point.jogo) prev = p;
  }});
  return prev;
}}

function trajectoryPointState(series) {{
  if (!series.length) return {{ point: null, status: 'none' }};
  let cur = null;
  series.forEach(p => {{
    if (p.jogo <= currentJogo) cur = p;
  }});
  if (cur) return {{ point: cur, status: cur.jogo === currentJogo ? 'current' : 'past' }};
  return {{ point: series[0], status: 'future' }};
}}

function trajectoryValueRange(seriesByTeam, metric, dir) {{
  const vals = Object.values(seriesByTeam).flat().map(p => p.value).filter(v => v !== null && v !== undefined);
  if (!vals.length) return {{ min: 0, max: 1 }};
  let min = Math.min(...vals);
  let max = Math.max(...vals);
  if (min === max) {{
    const pad = Math.max(1, Math.abs(max) * 0.1);
    min -= pad; max += pad;
  }} else {{
    const pad = (max - min) * 0.14;
    min -= pad; max += pad;
  }}
  if (PERCENT_FRAC.has(metric)) {{ min = Math.max(0, min); max = Math.min(1, max); }}
  if (PERCENT_DIRECT.has(metric) || metric.startsWith('score_') || STYLE_AXES.has(metric)) {{
    min = Math.max(0, min); max = Math.min(100, max);
  }}
  return {{ min, max }};
}}

function trajectoryRankRange(seriesByTeam) {{
  const pts = Object.values(seriesByTeam).flat();
  const ranks = pts.map(p => p.rank).filter(v => v != null);
  const totals = pts.map(p => p.total).filter(v => v != null);
  const universeMax = Math.max(...totals, 1);
  if (!ranks.length) return {{ min: 1, max: universeMax, universeMax }};
  let min = Math.min(...ranks);
  let max = Math.max(...ranks);
  const spread = Math.max(max - min, 1);
  const pad = Math.max(2, Math.ceil(spread * 0.35));
  min = Math.max(1, min - pad);
  max = Math.min(universeMax, max + pad);
  if (max - min < 6) {{
    const need = 6 - (max - min);
    min = Math.max(1, min - Math.ceil(need / 2));
    max = Math.min(universeMax, max + Math.floor(need / 2));
  }}
  return {{ min, max, universeMax }};
}}

function trajectoryY(point, mode, metric, dir, range, h, pad) {{
  if (mode === 'rank') {{
    const denom = Math.max((range.rankMax || point.total) - 1, 1);
    return pad + ((point.rank - 1) / denom) * (h - pad * 2);
  }}
  const span = Math.max(range.max - range.min, 1e-9);
  const norm = (point.value - range.min) / span;
  const betterTop = dir === 'asc' ? norm : 1 - norm;
  return pad + betterTop * (h - pad * 2);
}}

function trajectoryDeltaClass(delta, mode, dir) {{
  if (!delta) return '';
  const good = mode === 'rank' ? delta < 0 : (dir === 'asc' ? delta < 0 : delta > 0);
  return good ? ' good' : ' bad';
}}

function trajectoryDeltaText(cur, prev, mode, metric) {{
  if (!cur || !prev) return 'novo';
  if (mode === 'rank') {{
    const d = cur.rank - prev.rank;
    if (d === 0) return '=';
    return (d < 0 ? '↑ ' : '↓ ') + Math.abs(d);
  }}
  const d = cur.value - prev.value;
  if (Math.abs(d) < 0.005) return '=';
  return (d > 0 ? '+' : '') + formatVal(d, metric);
}}

function trajectorySmoothPath(points) {{
  if (!points.length) return '';
  if (points.length === 1) return `M ${{points[0].x}} ${{points[0].y}}`;
  let d = `M ${{points[0].x}} ${{points[0].y}}`;
  for (let i = 0; i < points.length - 1; i++) {{
    const p0 = points[i - 1] || points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] || p2;
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${{cp1x.toFixed(1)}} ${{cp1y.toFixed(1)}}, ${{cp2x.toFixed(1)}} ${{cp2y.toFixed(1)}}, ${{p2.x}} ${{p2.y}}`;
  }}
  return d;
}}

function trajectoryShortTeam(team) {{
  return team.length > 13 ? team.slice(0, 12) + '…' : team;
}}

function trajectoryLabelKey(team) {{
  return encodeURIComponent(team);
}}

function toggleTrajectoryFocus(team) {{
  if (trajectoryFocusTeams.has(team)) trajectoryFocusTeams.delete(team);
  else trajectoryFocusTeams.add(team);
  selectedTeam = team;
  renderTrajectoryModal();
  renderJogo(currentJogo);
}}

function renderTrajectoryChips(teams, targetId = 'trajectoryTeams') {{
  const el = document.getElementById(targetId);
  if (!el) return;
  if (!teams.length) {{
    el.innerHTML = '<span class="trajectory-empty-chip">Nenhuma seleção fixa</span>';
    return;
  }}
  el.innerHTML = teams.map(team => {{
    const color = trajectoryColor(team);
    const flag = TEAM_FLAGS[team] || (TEAMS_DETAIL[team] || {{}}).flag || '';
    return `<span class="traj-chip" title="${{_esc(team)}}">
      <span class="traj-chip-dot" style="background:${{color}}"></span>
      <span class="traj-chip-name">${{flag}} ${{_esc(team)}}</span>
      <button type="button" data-traj-remove="${{encodeURIComponent(team)}}" title="Remover">×</button>
    </span>`;
  }}).join('');
  el.querySelectorAll('[data-traj-remove]').forEach(btn => {{
    btn.onclick = e => {{
      e.stopPropagation();
      removeTrajectoryTeam(decodeURIComponent(btn.dataset.trajRemove));
    }};
  }});
}}

function renderTrajectoryChart(teams, seriesByTeam, metric, dir) {{
  const w = 920, h = 520, padX = 64, padTop = 62, padBottom = 58;
  const visibleSeries = {{}};
  teams.forEach(team => {{ visibleSeries[team] = seriesByTeam[team] || []; }});
  const range = trajectoryValueRange(visibleSeries, metric, dir);
  const rankRange = trajectoryRankRange(visibleSeries);
  const maxTeamOrder = Math.max(...Object.values(visibleSeries).flat().map(p => p.teamOrder || 0), 1);
  const xFor = j => {{
    const idx = jogos.indexOf(j);
    return padX + (idx / Math.max(N - 1, 1)) * (w - padX * 2);
  }};
  const xForPoint = p => {{
    if (trajectoryAxis === 'team') {{
      return padX + ((p.teamOrder - 1) / Math.max(maxTeamOrder - 1, 1)) * (w - padX * 2);
    }}
    return xFor(p.jogo);
  }};
  const plotBottom = h - padBottom;
  const plotH = plotBottom - padTop;
  const yManual = ratio => padTop + ratio * plotH;
  const yFor = p => {{
    if (trajectoryMode === 'rank') {{
      const denom = Math.max(rankRange.max - rankRange.min, 1);
      return padTop + ((p.rank - rankRange.min) / denom) * plotH;
    }}
    const span = Math.max(range.max - range.min, 1e-9);
    const norm = (p.value - range.min) / span;
    return padTop + (dir === 'asc' ? norm : 1 - norm) * plotH;
  }};
  const gridDefs = trajectoryMode === 'rank'
    ? [
        {{ label: '#' + rankRange.min, y: yManual(0) }},
        {{ label: '#' + Math.round((rankRange.min + rankRange.max) / 2), y: yManual(0.5) }},
        {{ label: '#' + rankRange.max, y: yManual(1) }},
      ]
    : [0, 0.5, 1].map(r => {{
        const val = dir === 'asc'
          ? range.min + (1 - r) * (range.max - range.min)
          : range.max - r * (range.max - range.min);
        return {{ label: formatVal(val, metric), y: yManual(r) }};
      }});
  const grid = gridDefs.map(g => {{
    const y = g.y.toFixed(1);
    return `<line x1="${{padX}}" y1="${{y}}" x2="${{w - padX}}" y2="${{y}}" stroke="#233044" stroke-width="1" opacity="0.72" />
      <text x="${{padX - 12}}" y="${{(+y + 4).toFixed(1)}}" fill="#6b7280" font-size="12" font-weight="800" text-anchor="end">${{g.label}}</text>`;
  }}).join('');
  const currentX = xFor(currentJogo);
  const startLabel = trajectoryAxis === 'team' ? 'Jogo 1' : `J${{jogos[0]}}`;
  const endLabel = trajectoryAxis === 'team' ? `Jogo ${{maxTeamOrder}}` : `J${{jogos[jogos.length - 1]}}`;
  const lines = teams.map(team => {{
    const series = seriesByTeam[team] || [];
    if (!series.length) return '';
    const color = trajectoryColor(team);
    const pts = series.map(p => ({{ p, x: +xForPoint(p).toFixed(1), y: +yFor(p).toFixed(1) }}));
    const path = trajectorySmoothPath(pts);
    const activePoint = trajectoryPointState(series).point;
    const activePt = activePoint ? (pts.find(x => x.p.jogo === activePoint.jogo) || pts[0]) : pts[0];
    const flag = TEAM_FLAGS[team] || (TEAMS_DETAIL[team] || {{}}).flag || '';
    const labelKey = trajectoryLabelKey(team);
    const circles = series.map(p => {{
      const state = trajectoryPointState(series);
      const isCurrent = trajectoryAxis === 'team'
        ? (state.point && p.jogo === state.point.jogo)
        : p.jogo === currentJogo;
      const r = isCurrent ? 5.6 : 2.2;
      const opacity = isCurrent ? 1 : 0.62;
      const label = trajectoryMode === 'rank'
        ? `${{trajectoryAxis === 'team' ? `Jogo do time ${{p.teamOrder}}` : `J${{p.jogo}}`}} · #${{p.rank}} · ${{formatVal(p.value, metric)}}`
        : `${{trajectoryAxis === 'team' ? `Jogo do time ${{p.teamOrder}}` : `J${{p.jogo}}`}} · ${{formatVal(p.value, metric)}} · #${{p.rank}}`;
      const x = xForPoint(p).toFixed(1);
      const y = yFor(p).toFixed(1);
      return `${{isCurrent ? `<circle cx="${{x}}" cy="${{y}}" r="11" fill="${{color}}" opacity="0.13" />` : ''}}
        <circle cx="${{x}}" cy="${{y}}" r="${{r}}" fill="${{color}}" stroke="#07101a" stroke-width="${{isCurrent ? 2.2 : 1.4}}" opacity="${{opacity}}" onclick="goToJogo(${{p.jogo}})" style="cursor:pointer"><title>${{_esc(team)}} · ${{label}}</title></circle>`;
    }}).join('');
    return `<path d="${{path}}" fill="none" stroke="${{color}}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" opacity="0.11" />
      <path d="${{path}}" fill="none" stroke="${{color}}" stroke-width="3.1" stroke-linecap="round" stroke-linejoin="round" />
      ${{circles}}
      <g class="traj-flag-label" data-label-key="${{labelKey}}" transform="translate(${{activePt.x.toFixed(1)}} ${{activePt.y.toFixed(1)}})" onmousedown="startTrajectorySliderDrag(event, '${{labelKey}}')" style="cursor:grab;transition:transform 0.22s ease">
        <circle cx="0" cy="0" r="18" fill="transparent" />
        <text x="0" y="0" dominant-baseline="middle" text-anchor="middle" font-size="24">${{flag}}</text>
        <title>${{_esc(team)}} · arraste para navegar pelos jogos do time</title>
      </g>`;
  }}).join('');
  return `<div class="trajectory-chart">
    <div class="trajectory-axis-label">${{trajectoryMode === 'rank' ? '# melhor no topo' : 'melhor no topo'}}</div>
    <div class="trajectory-current-label">J${{currentJogo}}</div>
    <svg viewBox="0 0 ${{w}} ${{h}}" preserveAspectRatio="xMidYMid meet" role="img">
      <defs>
        <linearGradient id="trajPlotFade" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#172236" stop-opacity="0.32" />
          <stop offset="100%" stop-color="#060910" stop-opacity="0.02" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="${{w}}" height="${{h}}" fill="transparent" />
      <rect x="${{padX}}" y="${{padTop}}" width="${{w - padX * 2}}" height="${{plotH}}" rx="10" fill="url(#trajPlotFade)" stroke="#1d293a" />
      ${{grid}}
      ${{trajectoryAxis === 'tournament' ? `<line x1="${{currentX.toFixed(1)}}" y1="${{padTop}}" x2="${{currentX.toFixed(1)}}" y2="${{plotBottom}}" stroke="#79c0ff" stroke-width="1.4" stroke-dasharray="5 7" opacity="0.45" />` : ''}}
      <text x="${{padX}}" y="${{h - 14}}" fill="#6b7280" font-size="12" font-weight="800">${{startLabel}}</text>
      ${{trajectoryAxis === 'tournament' ? `<text x="${{currentX.toFixed(1)}}" y="${{h - 14}}" fill="#9ecfff" font-size="12" font-weight="900" text-anchor="middle">J${{currentJogo}}</text>` : ''}}
      <text x="${{w - padX}}" y="${{h - 14}}" fill="#6b7280" font-size="12" font-weight="800" text-anchor="end">${{endLabel}}</text>
      ${{lines}}
    </svg>
  </div>`;
}}

function renderTrajectorySummary(teams, seriesByTeam, metric, dir) {{
  const rows = teams.map(team => {{
    const series = seriesByTeam[team] || [];
    const state = trajectoryPointState(series);
    const cur = state.point;
    const prev = trajectoryPreviousPoint(series, cur);
    const color = trajectoryColor(team);
    const flag = TEAM_FLAGS[team] || (TEAMS_DETAIL[team] || {{}}).flag || '';
    const focusCls = trajectoryFocusTeams.has(team) ? ' focused' : '';
    if (!cur) {{
      return `<div class="trajectory-row${{focusCls}}" style="--traj-color:${{color}}" data-traj-team="${{encodeURIComponent(team)}}">
        <div class="trajectory-row-main"><span class="trajectory-row-dot" style="background:${{color}}"></span><span class="trajectory-row-name">${{flag}} ${{_esc(team)}}</span></div>
        <span class="trajectory-row-value">sem dados</span>
        <span class="trajectory-row-delta">—</span>
      </div>`;
    }}
    const deltaRaw = state.status !== 'future' && trajectoryMode === 'rank' && prev ? cur.rank - prev.rank : (state.status !== 'future' && prev ? cur.value - prev.value : 0);
    const deltaCls = trajectoryDeltaClass(deltaRaw, trajectoryMode, dir);
    const mainVal = state.status === 'future' ? `entra J${{cur.jogo}}` : trajectoryMode === 'rank'
      ? `#${{cur.rank}} de ${{cur.total}}`
      : formatVal(cur.value, metric);
    const subVal = trajectoryMode === 'rank'
      ? formatVal(cur.value, metric)
      : `#${{cur.rank}}`;
    const deltaText = state.status === 'future' ? 'novo' : trajectoryDeltaText(cur, prev, trajectoryMode, metric);
    return `<div class="trajectory-row${{focusCls}}" style="--traj-color:${{color}}" data-traj-team="${{encodeURIComponent(team)}}">
      <div class="trajectory-row-main"><span class="trajectory-row-dot" style="background:${{color}}"></span><span class="trajectory-row-name">${{flag}} ${{_esc(team)}}</span></div>
      <span class="trajectory-row-value">${{mainVal}}</span>
      <span class="trajectory-row-delta${{deltaCls}}" title="${{subVal}}">${{deltaText}}</span>
    </div>`;
  }}).join('');
  return `<div class="trajectory-summary">${{rows}}</div>`;
}}

const POINT_COMPARE_METRICS = [
  ['score_geral', 'Score'],
  ['score_resultado', 'Resultado'],
  ['score_ataque', 'Ataque'],
  ['score_defesa', 'Defesa'],
  ['score_eficiencia', 'Eficiência'],
  ['score_controle', 'Controle'],
  ['score_forca_relativa', 'Força Relativa'],
];

let pointCompareSortMetric = null;

function pointCompareMetricLabel(metric) {{
  const item = POINT_COMPARE_METRICS.find(([key]) => key === metric);
  return item ? item[1] : null;
}}

function pointCompareValue(team, metric) {{
  const entry = teamEntryAt(team, currentJogo);
  return entry && entry[metric] !== null && entry[metric] !== undefined ? entry[metric] : null;
}}

function pointCompareRankStyle(order, total) {{
  if (!order || !total) return '--rank-hue:214;--rank-alpha:0.08';
  const denom = Math.max(total - 1, 1);
  const strength = total <= 1 ? 1 : 1 - ((order - 1) / denom);
  const hue = order === 1 ? 45 : order === 2 ? 210 : order === 3 ? 28 : 214;
  const alpha = (0.10 + strength * 0.30).toFixed(3);
  return `--rank-hue:${{hue}};--rank-alpha:${{alpha}}`;
}}

function pointCompareRankClass(order, total) {{
  if (order === 1) return 'rk1';
  if (order === 2) return 'rk2';
  if (order === 3) return 'rk3';
  if (total > 3 && order === total) return 'rk-last';
  return '';
}}

function pointCompareSortedTeams(teams) {{
  const metric = pointCompareMetricLabel(pointCompareSortMetric) ? pointCompareSortMetric : null;
  const uniqTeams = [...new Set((teams || []).filter(t => teamEntryAt(t, currentJogo)))];
  if (!metric) return uniqTeams;
  return uniqTeams.slice().sort((a, b) => {{
    const av = pointCompareValue(a, metric);
    const bv = pointCompareValue(b, metric);
    const aMissing = av === null || av === undefined;
    const bMissing = bv === null || bv === undefined;
    if (aMissing && bMissing) return a.localeCompare(b);
    if (aMissing) return 1;
    if (bMissing) return -1;
    if (bv !== av) return bv - av;
    return a.localeCompare(b);
  }});
}}

function setPointCompareSort(metric) {{
  if (!pointCompareMetricLabel(metric)) return;
  pointCompareSortMetric = metric;
  renderPointCompareModal();
}}

function renderPointCompare(teams, inline = false) {{
  const uniqTeams = pointCompareSortedTeams(teams);
  const title = 'Comparação ponto a ponto';
  const cls = inline ? 'point-compare inline' : 'point-compare';
  if (uniqTeams.length < 2) {{
    return `<div class="${{cls}}">
      <div class="pcmp-head"><div class="pcmp-title">${{title}}</div><div class="pcmp-sub">J${{currentJogo}}</div></div>
      <div class="pcmp-empty">Fixe pelo menos 2 seleções na trajetória para comparar os pontos de cada componente lado a lado.</div>
    </div>`;
  }}

  const minWidth = 160 + uniqTeams.length * 122;
  const tableStyle = inline ? ` style="min-width:${{minWidth}}px"` : '';
  const header = `<tr><th>Componente</th>${{uniqTeams.map(team => {{
    const flag = TEAM_FLAGS[team] || '';
    const color = trajectoryColor(team);
    const name = team;
    return `<th title="${{_esc(team)}}"><span class="pcmp-team-head"><span class="pcmp-team-dot" style="background:${{color}}"></span><span class="pcmp-team-name">${{flag}} ${{_esc(name)}}</span></span></th>`;
  }}).join('')}}</tr>`;

  const rows = POINT_COMPARE_METRICS.map(([metric, label]) => {{
    const values = uniqTeams.map(team => {{
      return pointCompareValue(team, metric);
    }});
    const ranked = uniqTeams.map((team, i) => ({{ team, value: values[i] }}))
      .filter(x => x.value !== null && x.value !== undefined)
      .sort((a, b) => b.value - a.value);
    const orderByTeam = {{}};
    let lastValue = null;
    let lastOrder = 0;
    ranked.forEach((item, idx) => {{
      const order = lastValue !== null && item.value === lastValue ? lastOrder : idx + 1;
      orderByTeam[item.team] = order;
      lastValue = item.value;
      lastOrder = order;
    }});
    const comparableCount = ranked.length;
    const cells = uniqTeams.map((team, i) => {{
      const v = values[i];
      const mr = metricRank(metric, DATA[currentJogo].teams || [], team, 'desc');
      const title = mr ? ` title="${{_esc(team)}}: #${{mr.rank}}${{mr.tied ? '=' : ''}} no ranking geral de ${{label}}"` : '';
      const order = orderByTeam[team] || null;
      const cls = pointCompareRankClass(order, comparableCount);
      const style = pointCompareRankStyle(order, comparableCount);
      const orderLabel = order ? `${{order}}º` : '—';
      return `<td class="pcmp-rank-cell ${{cls}}" style="${{style}}"${{title}}>
        <span class="pcmp-cell-main"><span class="pcmp-value">${{formatVal(v, metric)}}</span><span class="pcmp-order">${{orderLabel}}</span></span>
      </td>`;
    }}).join('');
    const active = metric === pointCompareSortMetric;
    const sortChip = active ? '<span class="pcmp-sort-chip">ordem</span>' : '';
    return `<tr class="${{active ? 'pcmp-sort-row' : ''}}"><td><button class="pcmp-metric-btn" onclick="setPointCompareSort('${{metric}}')" title="Ordenar seleções por ${{label}}"><span>${{label}}</span>${{sortChip}}</button></td>${{cells}}</tr>`;
  }}).join('');

  return `<div class="${{cls}}">
    <div class="pcmp-head">
      <div class="pcmp-title">${{title}}</div>
      <div class="pcmp-sub">Snapshot J${{currentJogo}} · ${{uniqTeams.length}} seleções</div>
    </div>
    <div class="pcmp-scroll">
      <table class="pcmp-table"${{tableStyle}}>
        <thead>${{header}}</thead>
        <tbody>${{rows}}</tbody>
      </table>
    </div>
    <div class="pcmp-note">Clique em uma métrica para ordenar os países por aquela linha. Cada célula mostra a pontuação no snapshot atual e a ordem entre as seleções escolhidas; passe o mouse para ver a posição no ranking geral.</div>
  </div>`;
}}

function renderPointCompareTeamChips(teams) {{
  const uniqTeams = [...new Set((teams || []).filter(Boolean))];
  if (!uniqTeams.length) return '<span class="trajectory-empty-chip">Nenhuma seleção fixa</span>';
  return uniqTeams.map(team => {{
    const flag = TEAM_FLAGS[team] || '';
    const color = trajectoryColor(team);
    return `<span class="traj-chip" title="${{_esc(team)}}">
      <span class="traj-chip-dot" style="background:${{color}}"></span>
      <span class="traj-chip-name">${{flag}} ${{_esc(team)}}</span>
    </span>`;
  }}).join('');
}}

function renderPointCompareModule(teams) {{
  const uniqTeams = [...new Set((teams || []).filter(Boolean))];
  const metric = trajectoryMetricKey();
  const metricLabel = METRIC_LABELS[metric] || metric;
  const summary = uniqTeams.length
    ? `${{uniqTeams.length}} seleção${{uniqTeams.length !== 1 ? 'es' : ''}} · ${{metricLabel}}`
    : 'Nenhuma seleção fixa';
  const body = uniqTeams.length >= 2
    ? `<button class="traj-open-btn" onclick="openPointCompareModal()">Abrir painel flutuante</button>
       <div class="pcmp-module-empty">${{uniqTeams.length}} seleções prontas para comparar ponto a ponto.</div>`
    : `<button class="traj-open-btn" onclick="openPointCompareModal()">Abrir painel flutuante</button>
       <div class="pcmp-module-empty">Fixe pelo menos 2 seleções para comparar os componentes lado a lado.</div>`;
  return `<div class="point-compare-module">
    <div class="pcmp-module-title">Comparação ponto a ponto</div>
    <div class="pcmp-module-teams">${{renderPointCompareTeamChips(uniqTeams)}}</div>
    <div class="pcmp-module-summary">${{summary}}</div>
    ${{body}}
  </div>`;
}}

function renderPointCompareModal() {{
  const modal = document.getElementById('pointCompareModal');
  const bodyEl = document.getElementById('pointCompareModalBody');
  const subEl = document.getElementById('pointCompareModalSubtitle');
  if (!modal || !bodyEl || !subEl) return;
  const teams = trajectoryTeams.length ? trajectoryTeams.slice() : (selectedTeam ? [selectedTeam] : []);
  const metric = trajectoryMetricKey();
  const metricLabel = METRIC_LABELS[metric] || metric;
  const sortLabel = pointCompareMetricLabel(pointCompareSortMetric);
  subEl.textContent = teams.length
    ? `${{teams.length}} seleção${{teams.length !== 1 ? 'es' : ''}} · Snapshot J${{currentJogo}} · ${{metricLabel}}${{sortLabel ? ` · ordem: ${{sortLabel}}` : ''}}`
    : 'sem seleções fixadas';
  bodyEl.innerHTML = renderPointCompare(teams, false);
  applyPointCompareScale(modal);
}}

function openPointCompareModal() {{
  const modal = document.getElementById('pointCompareModal');
  if (!modal) return;
  if (!modal.style.width) modal.style.width = Math.min(980, window.innerWidth - 140) + 'px';
  if (!modal.dataset.resized) modal.style.height = 'auto';
  modal.style.display = 'flex';
  renderPointCompareModal();
  applyPointCompareScale(modal);
  if (!modal.dataset.positioned) {{
    modal.style.left = Math.max(12, (window.innerWidth - (modal.offsetWidth || 980)) / 2) + 'px';
    modal.style.top = Math.max(12, (window.innerHeight - (modal.offsetHeight || 360)) / 2) + 'px';
    modal.style.right = 'auto';
    modal.style.bottom = 'auto';
    modal.dataset.positioned = '1';
  }}
  keepPointCompareModalInViewport();
}}

function closePointCompareModal() {{
  const modal = document.getElementById('pointCompareModal');
  if (modal) modal.style.display = 'none';
}}

function renderSidebar(n) {{
  const nameEl = document.getElementById('sidebarTeam');
  const bodyEl = document.getElementById('sidebarBody');
  const teams = trajectoryTeams.length ? trajectoryTeams.slice() : (selectedTeam ? [selectedTeam] : []);

  renderTrajectoryChips(trajectoryTeams);

  if (!teams.length) {{
    nameEl.textContent = '—';
    bodyEl.innerHTML = '<button class="traj-open-btn" onclick="openTrajectoryModal()">Abrir painel flutuante</button><div class="no-team">Clique em até 16 seleções para comparar a trajetória.</div>' + renderPointCompareModule([]);
    return;
  }}

  const metric = trajectoryMetricKey();
  const metricLabel = METRIC_LABELS[metric] || metric;
  nameEl.textContent = teams.length === 1 ? teams[0] : `${{teams.length}} seleções · ${{metricLabel}}`;
  bodyEl.innerHTML = `<button class="traj-open-btn" onclick="openTrajectoryModal()">Abrir painel flutuante</button>
    <div class="no-team">${{teams.length}} seleção${{teams.length !== 1 ? 'es' : ''}} · ${{metricLabel}}</div>
    ${{renderPointCompareModule(teams)}}`;
}}

function renderTrajectoryModal() {{
  const modal = document.getElementById('trajectoryModal');
  const bodyEl = document.getElementById('trajectoryModalBody');
  const subEl = document.getElementById('trajectoryModalSubtitle');
  if (!modal || !bodyEl || !subEl) return;

  const teams = trajectoryTeams.length ? trajectoryTeams.slice() : (selectedTeam ? [selectedTeam] : []);
  renderTrajectoryChips(trajectoryTeams, 'trajectoryModalTeams');
  const metric = trajectoryMetricKey();
  const dir = trajectoryMetricDir(metric);
  const metricLabel = METRIC_LABELS[metric] || metric;
  const axisLabel = trajectoryAxis === 'team' ? 'por jogo do time' : 'por jogo do torneio';
  const focusCount = [...trajectoryFocusTeams].filter(t => teams.includes(t)).length;
  const focusLabel = focusCount ? ` · ${{focusCount}} em foco` : '';
  subEl.textContent = teams.length ? `${{teams.length}} seleção${{teams.length !== 1 ? 'es' : ''}}${{focusLabel}} · ${{metricLabel}} · ${{axisLabel}}` : 'sem seleções fixadas';

  if (!teams.length) {{
    bodyEl.innerHTML = '<div class="no-team">Clique em uma seleção na corrida para começar a comparar.</div>';
    return;
  }}

  const seriesByTeam = trajectorySeriesByTeam(teams, metric, dir);
  const focusTeams = [...trajectoryFocusTeams].filter(t => teams.includes(t));
  const chartTeams = focusTeams.length ? focusTeams : teams;
  bodyEl.innerHTML = `<div class="trajectory-panel">
    ${{renderTrajectoryChart(chartTeams, seriesByTeam, metric, dir)}}
    ${{renderTrajectorySummary(teams, seriesByTeam, metric, dir)}}
  </div>`;
  bodyEl.querySelectorAll('[data-traj-team]').forEach(row => {{
    row.onclick = () => {{
      const team = decodeURIComponent(row.dataset.trajTeam);
      toggleTrajectoryFocus(team);
    }};
  }});
}}

function openTrajectoryModal() {{
  const modal = document.getElementById('trajectoryModal');
  if (!modal) return;
  if (!modal.style.width || !modal.style.height) {{
    const size = clampTrajectoryModalSize(Math.min(1120, window.innerWidth - 120), 630);
    modal.style.width = size.w + 'px';
    modal.style.height = size.h + 'px';
  }}
  modal.style.display = 'flex';
  keepTrajectoryModalInViewport();
  renderTrajectoryModal();
}}

function closeTrajectoryModal() {{
  const modal = document.getElementById('trajectoryModal');
  if (modal) modal.style.display = 'none';
}}

let trajectoryDrag = null;
let trajectoryResize = null;
let trajectorySidebarDrag = null;
let pointCompareDrag = null;
let pointCompareResize = null;
const TRAJECTORY_MODAL_RATIO = 16 / 9;
const POINT_COMPARE_MODAL_RATIO = 3.25;

function clampTrajectoryModalSize(w, h) {{
  const minW = Math.min(760, window.innerWidth - 24);
  const maxW = Math.max(minW, window.innerWidth - 24);
  const maxH = Math.max(428, window.innerHeight - 24);
  let outW = Math.max(minW, Math.min(w, maxW, maxH * TRAJECTORY_MODAL_RATIO));
  let outH = outW / TRAJECTORY_MODAL_RATIO;
  if (outH > maxH) {{
    outH = maxH;
    outW = outH * TRAJECTORY_MODAL_RATIO;
  }}
  return {{ w: outW, h: outH }};
}}

function clampPointCompareModalSize(w) {{
  const minW = Math.min(720, window.innerWidth - 24);
  const maxW = Math.max(minW, window.innerWidth - 24);
  const maxH = Math.max(260, window.innerHeight - 24);
  let outW = Math.max(minW, Math.min(w, maxW, maxH * POINT_COMPARE_MODAL_RATIO));
  let outH = outW / POINT_COMPARE_MODAL_RATIO;
  if (outH > maxH) {{
    outH = maxH;
    outW = outH * POINT_COMPARE_MODAL_RATIO;
  }}
  return {{ w: outW, h: outH }};
}}

function applyPointCompareScale(modal, size = null) {{
  if (!modal) return;
  const rect = size || modal.getBoundingClientRect();
  const scaleFromWidth = rect.w ? rect.w / 980 : rect.width / 980;
  const scaleFromHeight = rect.h ? rect.h / 320 : rect.height / 320;
  const table = modal.querySelector('.pcmp-table');
  const colCount = Math.max(1, (table ? table.querySelectorAll('thead th').length - 1 : 3));
  const width = rect.w || rect.width || 980;
  const usableColWidth = Math.max(1, (width - 118) / colCount);
  const fitScale = Math.max(0.78, Math.min(1, usableColWidth / 92));
  const scale = Math.max(0.78, Math.min(1.42, Math.min(scaleFromWidth, scaleFromHeight, fitScale)));
  if (modal.style && typeof modal.style.setProperty === 'function') {{
    modal.style.setProperty('--pcmp-scale', scale.toFixed(3));
  }} else if (modal.style) {{
    modal.style['--pcmp-scale'] = scale.toFixed(3);
  }}
}}

function keepTrajectoryModalInViewport() {{
  const modal = document.getElementById('trajectoryModal');
  if (!modal) return;
  const rect = modal.getBoundingClientRect();
  const margin = 8;
  const left = Math.max(margin, Math.min(rect.left, window.innerWidth - margin - rect.width));
  const top = Math.max(margin, Math.min(rect.top, window.innerHeight - margin - rect.height));
  modal.style.left = left + 'px';
  modal.style.top = top + 'px';
  modal.style.right = 'auto';
  modal.style.bottom = 'auto';
}}

function startTrajectoryDrag(e) {{
  const modal = document.getElementById('trajectoryModal');
  if (!modal || e.button !== 0) return;
  if (e.target.closest('button, select')) return;
  e.preventDefault();
  const rect = modal.getBoundingClientRect();
  trajectoryDrag = {{
    startX: e.clientX,
    startY: e.clientY,
    left: rect.left,
    top: rect.top,
  }};
  document.addEventListener('mousemove', moveTrajectoryDrag);
  document.addEventListener('mouseup', endTrajectoryDrag);
}}

function moveTrajectoryDrag(e) {{
  if (!trajectoryDrag) return;
  const modal = document.getElementById('trajectoryModal');
  if (!modal) return;
  const margin = 8;
  const w = modal.offsetWidth || 640;
  const h = modal.offsetHeight || 380;
  let left = trajectoryDrag.left + e.clientX - trajectoryDrag.startX;
  let top = trajectoryDrag.top + e.clientY - trajectoryDrag.startY;
  left = Math.max(margin, Math.min(left, window.innerWidth - margin - w));
  top = Math.max(margin, Math.min(top, window.innerHeight - margin - h));
  modal.style.left = left + 'px';
  modal.style.top = top + 'px';
  modal.style.right = 'auto';
  modal.style.bottom = 'auto';
}}

function endTrajectoryDrag() {{
  trajectoryDrag = null;
  document.removeEventListener('mousemove', moveTrajectoryDrag);
  document.removeEventListener('mouseup', endTrajectoryDrag);
}}

document.getElementById('trajectoryModalBar')?.addEventListener('mousedown', startTrajectoryDrag);

function keepPointCompareModalInViewport() {{
  const modal = document.getElementById('pointCompareModal');
  if (!modal) return;
  const rect = modal.getBoundingClientRect();
  const margin = 8;
  const left = Math.max(margin, Math.min(rect.left, window.innerWidth - margin - rect.width));
  const top = Math.max(margin, Math.min(rect.top, window.innerHeight - margin - rect.height));
  modal.style.left = left + 'px';
  modal.style.top = top + 'px';
  modal.style.right = 'auto';
  modal.style.bottom = 'auto';
}}

function startPointCompareDrag(e) {{
  const modal = document.getElementById('pointCompareModal');
  if (!modal || e.button !== 0) return;
  if (e.target.closest('button, select')) return;
  e.preventDefault();
  const rect = modal.getBoundingClientRect();
  pointCompareDrag = {{
    startX: e.clientX,
    startY: e.clientY,
    left: rect.left,
    top: rect.top,
  }};
  document.addEventListener('mousemove', movePointCompareDrag);
  document.addEventListener('mouseup', endPointCompareDrag);
}}

function movePointCompareDrag(e) {{
  if (!pointCompareDrag) return;
  const modal = document.getElementById('pointCompareModal');
  if (!modal) return;
  const margin = 8;
  const w = modal.offsetWidth || 640;
  const h = modal.offsetHeight || 380;
  let left = pointCompareDrag.left + e.clientX - pointCompareDrag.startX;
  let top = pointCompareDrag.top + e.clientY - pointCompareDrag.startY;
  left = Math.max(margin, Math.min(left, window.innerWidth - margin - w));
  top = Math.max(margin, Math.min(top, window.innerHeight - margin - h));
  modal.style.left = left + 'px';
  modal.style.top = top + 'px';
  modal.style.right = 'auto';
  modal.style.bottom = 'auto';
}}

function endPointCompareDrag() {{
  pointCompareDrag = null;
  document.removeEventListener('mousemove', movePointCompareDrag);
  document.removeEventListener('mouseup', endPointCompareDrag);
}}

document.getElementById('pointCompareModalBar')?.addEventListener('mousedown', startPointCompareDrag);

function startPointCompareResize(e) {{
  const modal = document.getElementById('pointCompareModal');
  if (!modal || e.button !== 0) return;
  e.preventDefault();
  e.stopPropagation();
  const rect = modal.getBoundingClientRect();
  pointCompareResize = {{
    startX: e.clientX,
    startY: e.clientY,
    width: rect.width,
    height: rect.height,
  }};
  document.addEventListener('mousemove', movePointCompareResize);
  document.addEventListener('mouseup', endPointCompareResize);
}}

function movePointCompareResize(e) {{
  if (!pointCompareResize) return;
  const modal = document.getElementById('pointCompareModal');
  if (!modal) return;
  const dx = e.clientX - pointCompareResize.startX;
  const dy = e.clientY - pointCompareResize.startY;
  const desiredW = pointCompareResize.width + dx;
  const desiredH = pointCompareResize.height + dy;
  const useHeight = Math.abs(dy / Math.max(pointCompareResize.height, 1)) > Math.abs(dx / Math.max(pointCompareResize.width, 1));
  const rawW = useHeight ? desiredH * POINT_COMPARE_MODAL_RATIO : desiredW;
  const size = clampPointCompareModalSize(rawW);
  modal.style.width = size.w + 'px';
  modal.style.height = size.h + 'px';
  applyPointCompareScale(modal, size);
  modal.dataset.resized = '1';
  modal.classList.add('is-resized');
  keepPointCompareModalInViewport();
}}

function endPointCompareResize() {{
  pointCompareResize = null;
  document.removeEventListener('mousemove', movePointCompareResize);
  document.removeEventListener('mouseup', endPointCompareResize);
}}

document.getElementById('pointCompareResizeHandle')?.addEventListener('mousedown', startPointCompareResize);

function startTrajectoryResize(e) {{
  const modal = document.getElementById('trajectoryModal');
  if (!modal || e.button !== 0) return;
  e.preventDefault();
  e.stopPropagation();
  const rect = modal.getBoundingClientRect();
  trajectoryResize = {{
    startX: e.clientX,
    startY: e.clientY,
    width: rect.width,
    height: rect.height,
    left: rect.left,
    top: rect.top,
  }};
  document.addEventListener('mousemove', moveTrajectoryResize);
  document.addEventListener('mouseup', endTrajectoryResize);
}}

function moveTrajectoryResize(e) {{
  if (!trajectoryResize) return;
  const modal = document.getElementById('trajectoryModal');
  if (!modal) return;
  const dx = e.clientX - trajectoryResize.startX;
  const dy = e.clientY - trajectoryResize.startY;
  const desiredW = trajectoryResize.width + dx;
  const desiredH = trajectoryResize.height + dy;
  const useHeight = Math.abs(dy / Math.max(trajectoryResize.height, 1)) > Math.abs(dx / Math.max(trajectoryResize.width, 1));
  const rawW = useHeight ? desiredH * TRAJECTORY_MODAL_RATIO : desiredW;
  const size = clampTrajectoryModalSize(rawW, rawW / TRAJECTORY_MODAL_RATIO);
  modal.style.width = size.w + 'px';
  modal.style.height = size.h + 'px';
  keepTrajectoryModalInViewport();
}}

function endTrajectoryResize() {{
  trajectoryResize = null;
  document.removeEventListener('mousemove', moveTrajectoryResize);
  document.removeEventListener('mouseup', endTrajectoryResize);
}}

document.getElementById('trajectoryResizeHandle')?.addEventListener('mousedown', startTrajectoryResize);

function startTrajectorySidebarResize(e) {{
  const main = document.querySelector('#viewRace .main');
  const sidebar = document.querySelector('#viewRace .sidebar');
  const handle = document.getElementById('trajectorySidebarResizer');
  if (!main || !sidebar || !handle || e.button !== 0) return;
  e.preventDefault();
  trajectorySidebarDrag = {{
    startX: e.clientX,
    width: sidebar.getBoundingClientRect().width,
  }};
  handle.classList.add('dragging');
  document.addEventListener('mousemove', moveTrajectorySidebarResize);
  document.addEventListener('mouseup', endTrajectorySidebarResize);
}}

function moveTrajectorySidebarResize(e) {{
  if (!trajectorySidebarDrag) return;
  const main = document.querySelector('#viewRace .main');
  if (!main) return;
  const dx = trajectorySidebarDrag.startX - e.clientX;
  const w = Math.max(170, Math.min(520, trajectorySidebarDrag.width + dx));
  main.style.setProperty('--trajectory-sidebar-w', w + 'px');
}}

function endTrajectorySidebarResize() {{
  trajectorySidebarDrag = null;
  const handle = document.getElementById('trajectorySidebarResizer');
  if (handle) handle.classList.remove('dragging');
  document.removeEventListener('mousemove', moveTrajectorySidebarResize);
  document.removeEventListener('mouseup', endTrajectorySidebarResize);
}}

document.getElementById('trajectorySidebarResizer')?.addEventListener('mousedown', startTrajectorySidebarResize);

function trajectorySvgXFromMouse(e) {{
  const svg = document.querySelector('#trajectoryModalBody .trajectory-chart svg');
  if (!svg) return null;
  const rect = svg.getBoundingClientRect();
  const viewW = 920, viewH = 520, viewRatio = viewW / viewH;
  const rectRatio = rect.width / Math.max(rect.height, 1);
  let renderW = rect.width, offsetX = 0;
  if (rectRatio > viewRatio) {{
    renderW = rect.height * viewRatio;
    offsetX = (rect.width - renderW) / 2;
  }}
  const x = (e.clientX - rect.left - offsetX) / Math.max(renderW, 1) * viewW;
  return Math.max(0, Math.min(viewW, x));
}}

function trajectorySliderPoints(team) {{
  const metric = trajectoryMetricKey();
  const dir = trajectoryMetricDir(metric);
  const teams = trajectoryTeams.length ? trajectoryTeams.slice() : (selectedTeam ? [selectedTeam] : []);
  const focusTeams = [...trajectoryFocusTeams].filter(t => teams.includes(t));
  const chartTeams = focusTeams.length ? focusTeams : teams;
  const visible = trajectorySeriesByTeam(chartTeams, metric, dir);
  const maxTeamOrder = Math.max(...Object.values(visible).flat().map(p => p.teamOrder || 0), 1);
  const padX = 64, w = 920;
  const xFor = j => {{
    const idx = jogos.indexOf(j);
    return padX + (idx / Math.max(N - 1, 1)) * (w - padX * 2);
  }};
  const xForPoint = p => trajectoryAxis === 'team'
    ? padX + ((p.teamOrder - 1) / Math.max(maxTeamOrder - 1, 1)) * (w - padX * 2)
    : xFor(p.jogo);
  return (visible[team] || trajectorySeries(team, metric, dir)).map(p => ({{ jogo: p.jogo, x: xForPoint(p) }}));
}}

function startTrajectorySliderDrag(e, key) {{
  e.preventDefault();
  e.stopPropagation();
  const team = decodeURIComponent(key);
  const points = trajectorySliderPoints(team);
  if (!points.length) return;
  trajectorySliderDrag = {{
    key,
    team,
    points,
    lastJogo: null,
  }};
  moveTrajectorySliderDrag(e);
  document.addEventListener('mousemove', moveTrajectorySliderDrag);
  document.addEventListener('mouseup', endTrajectorySliderDrag);
}}

function moveTrajectorySliderDrag(e) {{
  if (!trajectorySliderDrag) return;
  e.preventDefault();
  const x = trajectorySvgXFromMouse(e);
  if (x == null) return;
  const nearest = trajectorySliderDrag.points.reduce((best, p) =>
    Math.abs(p.x - x) < Math.abs(best.x - x) ? p : best,
    trajectorySliderDrag.points[0]);
  if (nearest && nearest.jogo !== trajectorySliderDrag.lastJogo) {{
    trajectorySliderDrag.lastJogo = nearest.jogo;
    goToJogo(nearest.jogo);
  }}
}}

function endTrajectorySliderDrag() {{
  trajectorySliderDrag = null;
  document.removeEventListener('mousemove', moveTrajectorySliderDrag);
  document.removeEventListener('mouseup', endTrajectorySliderDrag);
}}

// Métrica COMPARTILHADA: anima a corrida E ordena a grade Seleções. Atualiza
// as duas views ao trocar.
function changeMetric(metric) {{
  currentMetric = metric;
  renderBothViews();
}}

function selectTeam(t) {{
  selectedTeam = t;
  if (t) addTrajectoryTeam(t, false);
  renderSelectedTeamChips();
  refreshFilterOptions();
  syncDotRows();
  renderJogo(currentJogo);
  if (activeTab === 'teams') renderTeamsGrid();
  if (activeTab === 'players') {{
    playerPage = 1;
    renderPlayersGrid();
  }}
}}

function setTrajectoryMetric(metric) {{
  trajectoryMetric = metric;
  renderJogo(currentJogo);
}}

function setTrajectoryMode(mode) {{
  trajectoryMode = mode === 'value' ? 'value' : 'rank';
  document.getElementById('trajModeRank').classList.toggle('active', trajectoryMode === 'rank');
  document.getElementById('trajModeValue').classList.toggle('active', trajectoryMode === 'value');
  renderJogo(currentJogo);
}}

function setTrajectoryAxis(axis) {{
  trajectoryAxis = axis === 'team' ? 'team' : 'tournament';
  document.getElementById('trajAxisTournament').classList.toggle('active', trajectoryAxis === 'tournament');
  document.getElementById('trajAxisTeam').classList.toggle('active', trajectoryAxis === 'team');
  renderJogo(currentJogo);
}}

function setTrajectoryDock(dock) {{
  // Mantida só por compatibilidade com HTML antigo em cache.
}}

function addTrajectoryTeam(team, rerender = true) {{
  if (!team || !TEAMS_DETAIL[team]) return;
  if (!trajectoryTeams.includes(team)) {{
    if (trajectoryTeams.length >= MAX_TRAJECTORY_TEAMS) {{
      const removed = trajectoryTeams.shift();
      trajectoryFocusTeams.delete(removed);
    }}
    trajectoryTeams.push(team);
  }}
  selectedTeam = team;
  renderSelectedTeamChips();
  if (rerender) {{
    syncDotRows();
    renderBothViews();
  }}
}}

function removeTrajectoryTeam(team) {{
  trajectoryTeams = trajectoryTeams.filter(t => t !== team);
  trajectoryFocusTeams.delete(team);
  if (selectedTeam === team) selectedTeam = trajectoryTeams[trajectoryTeams.length - 1] || '';
  renderSelectedTeamChips();
  syncDotRows();
  renderBothViews();
}}

function toggleTrajectoryTeam(team) {{
  if (trajectoryTeams.includes(team)) removeTrajectoryTeam(team);
  else addTrajectoryTeam(team);
}}

function activeTeamFilters() {{
  if (trajectoryTeams.length) return trajectoryTeams.slice();
  return selectedTeam && TEAMS_DETAIL[selectedTeam] ? [selectedTeam] : [];
}}

function renderSelectedTeamChips() {{
  const el = document.getElementById('selectedTeamChips');
  if (!el) return;
  const escJs = s => (s || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
  el.innerHTML = activeTeamFilters().map((team, index) => {{
    const flag = TEAM_FLAGS[team] || (TEAMS_DETAIL[team] || {{}}).flag || '🏳️';
    const color = _focusColor(team, index);
    return `<span class="search-team-chip" style="--chip-color:${{color}}" title="${{_esc(team)}}"><span>${{flag}} ${{_esc(team)}}</span><button type="button" onclick="removeSearchTeam('${{escJs(team)}}')" title="Remover">×</button></span>`;
  }}).join('');
}}

function removeSearchTeam(team) {{
  removeTrajectoryTeam(team);
  renderTeamSuggestions();
}}

// Re-renderiza a view ativa (grades são time-aware e dependem dos mesmos
// controles compartilhados de busca, métrica, direção e filtros).
function renderBothViews() {{
  renderSelectedTeamChips();
  refreshFilterOptions();
  renderJogo(currentJogo);
  if (activeTab === 'teams') renderTeamsGrid();
  if (activeTab === 'players') renderPlayersGrid();
}}

// Busca compartilhada: o texto filtra sugestões; a escolha vira chip multi-seleção.
function onFocusInput() {{
  teamPage = 1;
  playerPage = 1;
  renderTeamSuggestions();
  renderBothViews();
}}

function _teamSuggestLabel(team) {{
  const meta = TEAM_META[team] || {{}};
  return [meta.group ? 'Grupo ' + meta.group : '', meta.confed || ''].filter(Boolean).join(' · ');
}}

function renderTeamSuggestions() {{
  const box = document.getElementById('teamSuggestions');
  const input = document.getElementById('teamSearch');
  if (!box || !input) return;
  const qRaw = input.value.trim();
  const q = _norm(qRaw);
  const scored = TEAMS_GRID
    .filter(t => !q || _norm(t).includes(q))
    .sort((a, b) => {{
      const an = _norm(a), bn = _norm(b);
      const ap = q && an.startsWith(q) ? 0 : 1;
      const bp = q && bn.startsWith(q) ? 0 : 1;
      return ap - bp || a.localeCompare(b);
    }})
    .slice(0, 12);
  teamSuggestItems = scored;
  if (teamSuggestIndex >= scored.length) teamSuggestIndex = scored.length - 1;
  if (!scored.length) {{
    box.innerHTML = '<div class="team-suggest-empty">Nenhuma seleção encontrada</div>';
    box.classList.add('open');
    return;
  }}
  const escJs = s => (s || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
  box.innerHTML = scored.map((team, i) => {{
    const flag = TEAM_FLAGS[team] || (TEAMS_DETAIL[team] || {{}}).flag || '🏳️';
    const meta = _teamSuggestLabel(team);
    const isSelected = activeTeamFilters().includes(team);
    return `<button type="button" class="team-suggest-item${{i === teamSuggestIndex ? ' active' : ''}}${{isSelected ? ' selected' : ''}}" onmousedown="event.preventDefault();chooseTeamSuggestion('${{escJs(team)}}')">
      <span class="team-suggest-flag">${{flag}}</span>
      <span class="team-suggest-name">${{_esc(team)}}</span>
      <span class="team-suggest-meta">${{isSelected ? 'selecionado' : _esc(meta)}}</span>
    </button>`;
  }}).join('');
  box.classList.add('open');
}}

function hideTeamSuggestions() {{
  const box = document.getElementById('teamSuggestions');
  if (box) box.classList.remove('open');
  teamSuggestIndex = -1;
}}

function chooseTeamSuggestion(team) {{
  const input = document.getElementById('teamSearch');
  if (trajectoryTeams.includes(team)) removeTrajectoryTeam(team);
  else addTrajectoryTeam(team, false);
  if (input) {{
    input.value = '';
    input.focus();
  }}
  teamPage = 1;
  playerPage = 1;
  renderSelectedTeamChips();
  renderTeamSuggestions();
  syncDotRows();
  renderBothViews();
}}

function onTeamSearchKey(e) {{
  const box = document.getElementById('teamSuggestions');
  const isOpen = box && box.classList.contains('open');
  if (e.key === 'ArrowDown') {{
    e.preventDefault();
    if (!isOpen) renderTeamSuggestions();
    if (teamSuggestItems.length) teamSuggestIndex = (teamSuggestIndex + 1) % teamSuggestItems.length;
    renderTeamSuggestions();
  }} else if (e.key === 'ArrowUp') {{
    e.preventDefault();
    if (!isOpen) renderTeamSuggestions();
    if (teamSuggestItems.length) teamSuggestIndex = teamSuggestIndex <= 0 ? teamSuggestItems.length - 1 : teamSuggestIndex - 1;
    renderTeamSuggestions();
  }} else if (e.key === 'Enter') {{
    if (isOpen && teamSuggestIndex >= 0 && teamSuggestItems[teamSuggestIndex]) {{
      e.preventDefault();
      chooseTeamSuggestion(teamSuggestItems[teamSuggestIndex]);
    }}
  }} else if (e.key === 'Escape') {{
    hideTeamSuggestions();
  }}
}}

document.addEventListener('click', e => {{
  if (!e.target.closest('.team-search-wrap')) hideTeamSuggestions();
}});

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

function teamEntryAt(team, n = currentJogo) {{
  const frame = DATA[n];
  return frame ? frame.teams.find(x => x.team === team) : null;
}}

function teamAvailableJogos(team) {{
  return jogos.filter(j => teamEntryAt(team, j));
}}

function firstTeamJogo(team) {{
  const js = teamAvailableJogos(team);
  return js.length ? js[0] : null;
}}

function buildNoDataCardBody(team) {{
  const first = firstTeamJogo(team);
  const d = TEAMS_DETAIL[team] || {{}};
  const firstMatch = first ? DATA[first] : null;
  const firstLabel = firstMatch
    ? `Jogo ${{first}} · ${{firstMatch.home}} ${{firstMatch.home_flag}} ${{firstMatch.score}} ${{firstMatch.away_flag}} ${{firstMatch.away}}`
    : '';
  const action = first
    ? `<button class="tt-empty-btn" onclick="event.stopPropagation(); goToJogo(${{first}})">Ir para o primeiro dado</button>
       <span class="tt-empty-hint">${{firstLabel}}</span>`
    : '<span class="tt-empty-hint">Essa seleção ainda não tem snapshot processado.</span>';
  const group = d.group ? ` no Grupo ${{d.group}}` : '';
  return `<div class="tt-empty">
    <div class="tt-empty-title">Sem dados para este período</div>
    <div class="tt-empty-copy">${{team}} ainda não tinha entrado no ranking após o Jogo ${{currentJogo}}${{group}}. O card fica aberto para você continuar comparando a trajetória sem perder a seleção.</div>
    <div class="tt-empty-actions">${{action}}</div>
  </div>`;
}}

function buildCardBody(team) {{
  const frame = DATA[currentJogo];
  const t = teamEntryAt(team);
  if (!t) return buildNoDataCardBody(team);
  // universo de comparação = times do snapshot que passam nos filtros ativos
  // (Grupo/Confed/Fase) — assim os ranks do painel ("33º") ficam DENTRO do
  // filtro. Sem filtro, é o universo inteiro, como antes.
  let allTeams = frame.teams.filter(x => passesGlobalFilters(x.team));
  if (!allTeams.some(x => x.team === team)) allTeams = frame.teams;
  // "#N no ranking" = posição no ranking (score_geral, maior=melhor),
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
      const cls = (isActive ? ' active' : isRelated ? ' related' : isIndirect ? ' related-indirect' : '')
                + (SCORE_INPUT_METRICS.has(key) ? ' score-input' : '');
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
  const legendHtml  = `<div class="tt-legend">
    <span class="tt-legend-item"><span style="color:#4a86d8;font-size:0.62rem">▪</span> alimenta o score</span>
    ${{hasRelated  ? '<span class="tt-legend-item"><span class="tt-legend-dot" style="background:#4ade80"></span>entra no cálculo</span>' : ''}}
    ${{hasIndirect ? '<span class="tt-legend-item"><span class="tt-legend-dot" style="background:#f0c040"></span>correlação indireta</span>' : ''}}
  </div>`;
  // o cabeçalho (bandeira/nome/ranking) vai na barra de arrastar, não aqui
  return `<div class="tt-grid">${{colsHtml}}</div>${{legendHtml}}`;
}}

// Cabeçalho do card (bandeira + nome + posição), exibido na barra de arrastar.
function buildCardHeader(team) {{
  const frame = DATA[currentJogo];
  const t = teamEntryAt(team);
  if (!t) {{
    const d = TEAMS_DETAIL[team] || {{}};
    const first = firstTeamJogo(team);
    const firstTxt = first ? ` · entra no Jogo ${{first}}` : '';
    return `<span class="drag-flag">${{d.flag || TEAM_FLAGS[team] || ''}}</span>
      <span class="drag-name">${{team}}</span>
      <span class="drag-sub">sem dados neste período${{firstTxt}}</span>`;
  }}
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
  n = Number(n);
  if (!DATA[n]) return;
  currentJogo = n;
  renderJogo(n);
  // grades refletem o momento selecionado — re-renderiza a que estiver ativa
  if (activeTab === 'teams') renderTeamsGrid();
  if (activeTab === 'players') renderPlayersGrid();
  if (modalTeam && document.getElementById('teamModal').style.display !== 'none') {{
    renderModalBody();
  }}
}}

function updateSpeed() {{
  speed = +document.getElementById('speedSelect').value;
  if (playing) {{ clearInterval(timer); startPlay(); }}
}}

function startPlay() {{
  timer = setInterval(() => {{
    const next = nextJogo();
    if (next == null) {{ stopPlay(); return; }}
    goToJogo(next);
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
    if (currentJogo === lastJogo()) goToJogo(firstJogo());
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
  toggleTrajectoryTeam(team);
}});

document.addEventListener('keydown', e => {{
  // Esc fecha o modal de seleção, em qualquer aba
  if (e.key === 'Escape' && document.getElementById('teamModal').style.display !== 'none') {{
    closeTeamModal(); return;
  }}
  if (e.key === 'Escape' && document.getElementById('playerModal').style.display !== 'none') {{
    closePlayerModal(); return;
  }}
  if (e.key === 'Escape' && document.getElementById('trajectoryModal').style.display !== 'none') {{
    closeTrajectoryModal(); return;
  }}
  if (e.key === 'Escape' && document.getElementById('pointCompareModal').style.display !== 'none') {{
    closePointCompareModal(); return;
  }}
  if (e.key === 'Escape' && document.getElementById('weightsGuide').style.display !== 'none') {{
    closeWeightsGuide(); return;
  }}
  // controles da race só valem na aba race, com modal fechado e fora de inputs
  if (activeTab !== 'race') return;
  if (document.getElementById('teamModal').style.display !== 'none') return;
  if (document.getElementById('weightsGuide').style.display !== 'none') return;
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.key === ' ') {{ e.preventDefault(); togglePlay(); }}
  if (e.key === 'ArrowRight') {{
    const next = nextJogo();
    if (next != null) goToJogo(next);
  }}
  if (e.key === 'ArrowLeft') {{
    const prev = prevJogo();
    if (prev != null) goToJogo(prev);
  }}
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
  document.getElementById('viewPlayers').style.display = tab === 'players' ? 'flex' : 'none';
  // barra de tempo compartilhada por todas as abas
  document.querySelector('.header-player').style.visibility = 'visible';
  // filtro de Posição só na aba Jogadores; placeholder da busca muda por contexto
  document.getElementById('fieldPos').style.display = tab === 'players' ? '' : 'none';
  document.getElementById('teamSearch').placeholder =
    tab === 'players' ? 'Buscar jogador ou adicionar seleção…' : 'Buscar/adicionar seleção…';
  // a métrica disponível muda entre seleções e jogadores
  syncMetricOptions(tab);
  refreshFilterOptions();
  if (tab === 'teams') {{
    if (!_teamsInit) {{ initTeamsControls(); _teamsInit = true; }}
    renderTeamsGrid();
  }} else if (tab === 'players') {{
    renderPlayersGrid();
  }}
}}
let _teamsInit = false;

// Métricas por aba: a corrida/seleções usam METRIC_GROUPS; jogadores têm um
// conjunto próprio (score geral, gols, assistências, defesas…). Troca o
// dropdown e garante uma métrica válida ao mudar de contexto.
const PLAYER_METRICS = [
  ['rating_365', 'Nota de atuação'],
  ['score_geral', 'Score (qualidade)'],
  ['gols_por_jogo', 'Gols / jogo'],
  ['assistencias_por_jogo', 'Assistências / jogo'],
  ['participacoes_por_jogo', 'G+A / jogo'],
  ['expected_goals_por_jogo', 'xG / jogo'],
  ['expected_assists_por_jogo', 'xA / jogo'],
  ['expected_goals_on_target_por_jogo', 'xGOT / jogo'],
  ['key_passes_por_jogo', 'Passes-chave / jogo'],
  ['tackles_won_por_jogo', 'Desarmes / jogo'],
  ['interceptions_por_jogo', 'Interceptações / jogo'],
  ['clearances_por_jogo', 'Cortes / jogo'],
  ['ball_recovery_por_jogo', 'Recuperações / jogo'],
  ['duels_won_por_jogo', 'Duelos ganhos / jogo'],
  ['expected_goals_prevented_por_jogo', 'xGP / jogo'],
  ['chutes_no_alvo_por_jogo', 'Chutes no alvo / jogo'],
  ['defesas_por_jogo', 'Defesas / jogo'],
  ['goals', 'Gols (total)'],
  ['assists', 'Assistências (total)'],
  ['expected_goals', 'xG (total)'],
  ['expected_assists', 'xA (total)'],
  ['key_passes', 'Passes-chave (total)'],
  ['tackles_won', 'Desarmes (total)'],
  ['interceptions', 'Interceptações (total)'],
  ['clearances', 'Cortes (total)'],
  ['ball_recovery', 'Recuperações (total)'],
  ['duels_won', 'Duelos ganhos (total)'],
  ['expected_goals_prevented', 'xGP (total)'],
  ['saves', 'Defesas (total)'],
  ['jogos', 'Jogos disputados'],
];
const PLAYER_METRIC_LABELS = {{}};
PLAYER_METRICS.forEach(([k, l]) => PLAYER_METRIC_LABELS[k] = l);
const PLAYER_METRIC_CORE = [
  ['rating_365', 'Nota de atuação'],
  ['score_geral', 'Score (qualidade)'],
  ['jogos', 'Jogos disputados'],
];
const PLAYER_METRICS_BY_POS = {{
  goleiro: [
    ['defesas_por_jogo', 'Defesas / jogo'],
    ['expected_goals_prevented_por_jogo', 'xGP / jogo'],
    ['goals_conceded', 'Gols sofridos (total)'],
    ['saves', 'Defesas (total)'],
    ['expected_goals_prevented', 'xGP (total)'],
  ],
  defensor: [
    ['tackles_won_por_jogo', 'Desarmes / jogo'],
    ['interceptions_por_jogo', 'Interceptações / jogo'],
    ['clearances_por_jogo', 'Cortes / jogo'],
    ['shots_blocked_por_jogo', 'Bloqueios / jogo'],
    ['ball_recovery_por_jogo', 'Recuperações / jogo'],
    ['duels_won_por_jogo', 'Duelos ganhos / jogo'],
    ['expected_goals_prevented_por_jogo', 'xGP / jogo'],
    ['tackles_won', 'Desarmes (total)'],
    ['interceptions', 'Interceptações (total)'],
    ['clearances', 'Cortes (total)'],
    ['ball_recovery', 'Recuperações (total)'],
    ['duels_won', 'Duelos ganhos (total)'],
  ],
  meio: [
    ['assistencias_por_jogo', 'Assistências / jogo'],
    ['expected_assists_por_jogo', 'xA / jogo'],
    ['key_passes_por_jogo', 'Passes-chave / jogo'],
    ['big_chances_created_por_jogo', 'Grandes chances criadas / jogo'],
    ['dribbles_won_por_jogo', 'Dribles ganhos / jogo'],
    ['ball_recovery_por_jogo', 'Recuperações / jogo'],
    ['tackles_won_por_jogo', 'Desarmes / jogo'],
    ['gols_por_jogo', 'Gols / jogo'],
    ['expected_goals_por_jogo', 'xG / jogo'],
    ['chutes_no_alvo_por_jogo', 'Chutes no alvo / jogo'],
    ['assists', 'Assistências (total)'],
    ['expected_assists', 'xA (total)'],
    ['key_passes', 'Passes-chave (total)'],
  ],
  atacante: [
    ['gols_por_jogo', 'Gols / jogo'],
    ['participacoes_por_jogo', 'G+A / jogo'],
    ['expected_goals_por_jogo', 'xG / jogo'],
    ['expected_goals_on_target_por_jogo', 'xGOT / jogo'],
    ['chutes_no_alvo_por_jogo', 'Chutes no alvo / jogo'],
    ['assistencias_por_jogo', 'Assistências / jogo'],
    ['expected_assists_por_jogo', 'xA / jogo'],
    ['key_passes_por_jogo', 'Passes-chave / jogo'],
    ['dribbles_won_por_jogo', 'Dribles ganhos / jogo'],
    ['big_chances_scored_por_jogo', 'Grandes chances em gol / jogo'],
    ['big_chances_missed_por_jogo', 'Grandes chances perdidas / jogo'],
    ['goals', 'Gols (total)'],
    ['assists', 'Assistências (total)'],
    ['expected_goals', 'xG (total)'],
  ],
}};
Object.values(PLAYER_METRICS_BY_POS).flat().forEach(([k, l]) => {{
  if (!PLAYER_METRIC_LABELS[k]) PLAYER_METRIC_LABELS[k] = l;
}});
function playerMetricOptionsForCurrentPos() {{
  const pos = playerFilters.pos || '';
  if (!pos || !PLAYER_METRICS_BY_POS[pos]) return PLAYER_METRICS;
  const seen = new Set();
  return [...PLAYER_METRIC_CORE, ...PLAYER_METRICS_BY_POS[pos]].filter(([k]) => {{
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  }});
}}

function syncMetricOptions(tab) {{
  const sel = document.getElementById('metricSelect');
  if (tab === 'players') {{
    const options = playerMetricOptionsForCurrentPos();
    const valid = new Set(options.map(([k]) => k));
    sel.innerHTML = options.map(([k, l]) => `<option value="${{k}}">${{l}}</option>`).join('');
    if (!valid.has(currentMetric)) currentMetric = 'score_geral';
    sel.value = currentMetric;
  }} else {{
    // restaura as métricas de seleção/corrida (agrupadas)
    sel.innerHTML = METRIC_GROUPS.map(([gl, , opts]) =>
      `<optgroup label="${{gl}}">` + opts.map(([k, l]) => `<option value="${{k}}">${{l}}</option>`).join('') + '</optgroup>'
    ).join('');
    if (!METRIC_LABELS[currentMetric]) currentMetric = 'score_geral';
    sel.value = currentMetric;
  }}
}}

function _norm(s) {{
  return (s || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
}}

function _hashColor(text) {{
  const palette = ['#2563eb', '#dc2626', '#16a34a', '#f97316', '#7c3aed', '#0891b2', '#be123c', '#ca8a04'];
  let h = 0;
  for (const ch of String(text || '')) h = ((h << 5) - h + ch.charCodeAt(0)) | 0;
  return palette[Math.abs(h) % palette.length];
}}
function _hexRgb(hex) {{
  const h = String(hex || '').replace('#', '');
  if (h.length !== 6) return {{ r: 37, g: 99, b: 235 }};
  return {{ r: parseInt(h.slice(0, 2), 16), g: parseInt(h.slice(2, 4), 16), b: parseInt(h.slice(4, 6), 16) }};
}}
function _mixHex(hex, pct) {{
  const c = _hexRgb(hex);
  const t = pct < 0 ? 0 : 255;
  const p = Math.abs(pct);
  const to = v => Math.max(0, Math.min(255, Math.round(v + (t - v) * p))).toString(16).padStart(2, '0');
  return `#${{to(c.r)}}${{to(c.g)}}${{to(c.b)}}`;
}}
function _shirtColors(team) {{
  const kit = TEAM_KIT_COLORS[team] || {{}};
  const main = kit.main || TEAM_SHIRT_COLORS[team] || TEAM_SHIRT_COLORS[_norm(team)] || _hashColor(team);
  const rgb = _hexRgb(main);
  const luminance = (0.2126 * rgb.r + 0.7152 * rgb.g + 0.0722 * rgb.b) / 255;
  const text = kit.text || (luminance > 0.62 ? '#0d1117' : '#f8fafc');
  const dark = _mixHex(main, -0.36);
  const border = kit.border || _mixHex(main, luminance > 0.62 ? -0.28 : 0.22);
  return `--shirt-main:${{main}};--shirt-dark:${{dark}};--shirt-border:${{border}};--shirt-text:${{text}}`;
}}
function _kitShirtHtml(num, team, cls = '') {{
  const n = num == null || num === '—' ? '' : _esc(String(num));
  return `<span class="kit-shirt ${{cls}}" style="${{_shirtColors(team)}}"><span class="shirt-number">${{n}}</span></span>`;
}}
function _playerSlugFor(team, name) {{
  const targetTeam = _norm(team);
  const targetName = _norm(name);
  return PLAYER_SLUGS.find(slug => {{
    const meta = PLAYER_META[slug] || {{}};
    return _norm(meta.team) === targetTeam && _norm(meta.name) === targetName;
  }}) || null;
}}

const STAGE_LABELS_TEAMS = {{
  'Fase de Grupos': 'Fase de Grupos', '16-avos de Final': '16-avos de Final',
  'Oitavas de Final': 'Oitavas de Final', 'Quartas de Final': 'Quartas de Final',
  'Semifinais': 'Semifinais', 'Disputa 3º Lugar': 'Disputa 3º Lugar', 'Final': 'Final',
}};

// formatadores reutilizáveis
const _f1 = v => v == null ? '—' : v.toFixed(1);                    // 1 casa (scores)
const _fi = v => v == null ? '—' : Math.round(v);                   // inteiro
const _fe = v => v == null ? '—' : v.toFixed(1);                    // Elo com 1 casa
const _fs = v => v == null ? '—' : (v > 0 ? '+' + v : '' + v);     // saldo com sinal

function initTeamsControls() {{
  refreshFilterOptions();
}}

// Preenche um <select> de filtro com as opções válidas + preserva o valor atual
// se ainda for válido (senão volta para "todas").
function _focusColor(team, fallbackIndex = 0) {{
  const idx = trajectoryTeams.indexOf(team);
  return TRAJECTORY_COLORS[(idx >= 0 ? idx : fallbackIndex) % TRAJECTORY_COLORS.length];
}}

function _focusedFilterSuggestions() {{
  const out = {{ group: new Map(), confed: new Map(), stage: new Map() }};
  activeTeamFilters().forEach((team, index) => {{
    const meta = TEAM_META[team] || {{}};
    const flag = TEAM_FLAGS[team] || (TEAMS_DETAIL[team] || {{}}).flag || '';
    const color = _focusColor(team, index);
    ['group', 'confed', 'stage'].forEach(axis => {{
      const value = meta[axis];
      if (!value) return;
      if (!out[axis].has(value)) out[axis].set(value, []);
      out[axis].get(value).push({{ team, flag, color }});
    }});
  }});
  return out;
}}

function _renderFilterHints(id, suggestedMap, hintFmt) {{
  const el = document.getElementById(id + 'Hints');
  if (!el) return;
  const chips = [];
  suggestedMap.forEach((teams, value) => {{
    teams.forEach(t => {{
      chips.push(`<span class="filter-hint" style="--hint-color:${{t.color}}" title="${{_esc(t.team)}} · ${{_esc(hintFmt(value))}}">
        <span class="filter-hint-dot"></span><span class="filter-hint-text">${{t.flag ? _esc(t.flag) + ' ' : ''}}${{_esc(hintFmt(value))}}</span>
      </span>`);
    }});
  }});
  el.innerHTML = chips.join('');
}}

function _suggestGradient(suggestedMap) {{
  const colors = [];
  suggestedMap.forEach(teams => teams.forEach(t => colors.push(t.color)));
  if (!colors.length) return '';
  const step = 100 / colors.length;
  return `linear-gradient(90deg, ${{colors.map((c, i) => `${{c}} ${{(i * step).toFixed(2)}}%, ${{c}} ${{((i + 1) * step).toFixed(2)}}%`).join(', ')}})`;
}}

function _fillFilterSelect(id, values, allLabel, fmt, suggestedMap = new Map(), hintFmt = fmt) {{
  const sel = document.getElementById(id);
  if (!sel) return;
  const cur = sel.value;
  const opts = values.slice().sort();
  const still = opts.includes(cur) ? cur : '';
  const hasSuggestion = suggestedMap.size > 0;
  sel.innerHTML = `<option value="">${{allLabel}}</option>` +
    opts.map(v => {{
      const teams = suggestedMap.get(v) || [];
      const suggested = teams.length > 0;
      const teamLabel = suggested ? (teams.length === 1 ? ` · ${{teams[0].team}}` : ` · ${{teams.length}} seleções`) : '';
      const colorStyle = suggested && teams.length === 1 ? ` style="color:${{teams[0].color}};font-weight:800"` : '';
      return `<option value="${{_esc(v)}}"${{v === still ? ' selected' : ''}}${{suggested ? ' data-suggested="1"' : ''}}${{colorStyle}}>${{suggested ? '★ ' : ''}}${{_esc(fmt(v))}}${{_esc(teamLabel)}}</option>`;
    }}).join('');
  sel.value = still;
  const field = sel.closest('.tb-field');
  if (field) field.classList.toggle('has-suggestion', hasSuggestion);
  sel.style['--suggest-gradient'] = hasSuggestion ? _suggestGradient(suggestedMap) : '';
  _renderFilterHints(id, suggestedMap, hintFmt);
}}

// CROSS-FILTER: cada dropdown mostra só opções compatíveis com os OUTROS
// filtros ativos. Ex: com Grupo C selecionado, Confederação lista só as
// confederações presentes no Grupo C; com UEFA, Grupo lista só grupos com
// times UEFA. O próprio filtro não se restringe (senão você não poderia
// trocar o valor dele). Sincroniza o estado global se algum valor caiu fora.
function refreshFilterOptions() {{
  const metas = Object.values(TEAM_META);
  const suggested = _focusedFilterSuggestions();
  // candidatos a cada eixo, dado o estado dos OUTROS dois eixos
  const valid = (axis) => {{
    const out = new Set();
    metas.forEach(m => {{
      if (axis !== 'group'  && teamFilters.group  && m.group  !== teamFilters.group)  return;
      if (axis !== 'confed' && teamFilters.confed && m.confed !== teamFilters.confed) return;
      if (axis !== 'stage'  && teamFilters.stage  && m.stage  !== teamFilters.stage)  return;
      const v = m[axis];
      if (v) out.add(v);
    }});
    return [...out];
  }};
  _fillFilterSelect('filterGroup',  valid('group'),  'Todos',  g => 'Grupo ' + g, suggested.group, g => 'G ' + g);
  _fillFilterSelect('filterConfed', valid('confed'), 'Todas',  c => c, suggested.confed, c => c);
  _fillFilterSelect('filterStage',  valid('stage'),  'Todas',  s => s, suggested.stage, s => STAGE_LABELS_TEAMS[s] || s);
  // se algum valor saiu da lista (ficou inválido), atualiza o estado global
  teamFilters.group  = document.getElementById('filterGroup').value;
  teamFilters.confed = document.getElementById('filterConfed').value;
  teamFilters.stage  = document.getElementById('filterStage').value;
}}

const TEAMS_PER_PAGE = 24;
let teamPage = 1;

// mudou filtro/ordenação na aba Seleções → sincroniza o estado GLOBAL de
// filtros (grupo/confed/fase), volta pra página 1 e re-renderiza AS DUAS abas.
function applyTeamFilters() {{
  syncFiltersFromTeamsUI();
  if (activeTab === 'players') syncMetricOptions('players');
  refreshFilterOptions();   // dropdowns se cruzam: só opções compatíveis
  teamPage = 1; playerPage = 1;
  renderTeamsGrid();
  if (activeTab === 'players') renderPlayersGrid();
  renderJogo(currentJogo);  // reflete os filtros nas barras da Race também
}}

// lê os selects da aba Seleções → grava no estado global teamFilters.
// (O phaseSelect da Race é NAVEGAÇÃO de bolinhas, conceito distinto — não mexe aqui.)
function syncFiltersFromTeamsUI() {{
  const g = document.getElementById('filterGroup');
  const c = document.getElementById('filterConfed');
  const s = document.getElementById('filterStage');
  if (g) teamFilters.group = g.value;
  if (c) teamFilters.confed = c.value;
  if (s) teamFilters.stage = s.value;
  const pos = document.getElementById('filterPos');
  if (pos) playerFilters.pos = pos.value;
}}

function goTeamPage(p) {{
  teamPage = p;
  renderTeamsGrid();
  document.getElementById('teamsGrid').scrollTop = 0;
}}

// Limpa TODOS os filtros compartilhados (busca, grupo, confed, fase, só com
// jogos) e o foco de time. Métrica/direção são preservados (foco da análise).
function resetAllFilters() {{
  document.getElementById('teamSearch').value = '';
  document.getElementById('filterGroup').value = '';
  document.getElementById('filterConfed').value = '';
  document.getElementById('filterStage').value = '';
  document.getElementById('filterPlayed').checked = false;
  const adv = document.getElementById('filterAdvanced'); if (adv) adv.checked = false;
  teamFilters.group = ''; teamFilters.confed = ''; teamFilters.stage = '';
  const pos = document.getElementById('filterPos'); if (pos) pos.value = '';
  playerFilters.pos = '';
  selectedTeam = ''; selectedPlayer = '';
  trajectoryTeams = [];
  hideTeamSuggestions();
  teamPage = 1; playerPage = 1;
  refreshFilterOptions();   // volta os dropdowns à lista completa
  if (activeTab === 'players') syncMetricOptions('players');
  syncDotRows();
  renderBothViews();
  if (activeTab === 'players') renderPlayersGrid();
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
  const teamFocuses = activeTeamFilters();
  // ordenação/destaque pela MÉTRICA COMPARTILHADA (a mesma da corrida).
  const sortKey = currentMetric;
  const fGroup = document.getElementById('filterGroup').value;
  const fConfed = document.getElementById('filterConfed').value;
  const fStage = document.getElementById('filterStage').value;
  const fPlayed = document.getElementById('filterPlayed').checked;
  const fAdvanced = document.getElementById('filterAdvanced').checked;
  const dir = sortDir;  // direção COMPARTILHADA com a corrida

  // — DETALHE NO MOMENTO selecionado: a grade reflete o jogo da barra de tempo.
  const detAt = {{}};
  TEAMS_GRID.forEach(t => {{ detAt[t] = teamDetailAt(t, currentJogo); }});
  // valor da métrica compartilhada por time, lido direto do snapshot atual.
  const snap = SNAP_BY_TEAM[currentJogo] || {{}};
  const mval = t => {{ const r = snap[t]; return r ? r[currentMetric] : null; }};

  // filtra — usa TODAS as seleções da Copa (inclui as que ainda não jogaram).
  // Grupo/Confed/Fase vêm do estado GLOBAL (compartilhado com a Race).
  let teams = TEAMS_GRID.filter(t => {{
    const d = detAt[t];
    if (teamFocuses.length && !teamFocuses.includes(t)) return false;
    if (q && !_norm(t).includes(q)) return false;
    if (!passesGlobalFilters(t)) return false;
    if (fPlayed && (d.n_jogos || 0) === 0) return false;
    if (fAdvanced && !(snap[t] && snap[t].advanced_coverage > 0)) return false;
    return true;
  }});

  // ordena pela métrica compartilhada (ausentes sempre no fim)
  teams.sort((a, b) => {{
    let va = mval(a), vb = mval(b);
    const na = (va == null), nb = (vb == null);
    if (na && nb) return a.localeCompare(b, 'pt-BR');
    if (na) return 1;
    if (nb) return -1;
    if (va === vb) return a.localeCompare(b, 'pt-BR');
    return dir === 'asc' ? va - vb : vb - va;
  }});

  document.getElementById('teamsCount').textContent =
    teams.length + ' de ' + TEAMS_GRID.length + ' seleções';

  // — destaque: valor + posição na métrica compartilhada DENTRO DO FILTRO ativo
  // (não entre todas as 46). Com Grupo C filtrado, o rank é "Xº de 4".
  const hlFmt = _metricFmt(currentMetric);
  const hlShort = METRIC_LABELS[currentMetric] || currentMetric;
  // ranking da métrica entre os times FILTRADOS; empate = mesma posição
  const ranked = teams
    .map(t => ({{ t, v: mval(t) }}))
    .filter(x => x.v != null)
    .sort((a, b) => dir === 'asc' ? a.v - b.v : b.v - a.v);
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
    const d = detAt[t];
    const flag = d.flag || TEAM_FLAGS[t] || '🏳️';
    const nj = d.n_jogos || 0;
    const empty = nj === 0;
    // o badge # reflete a POSIÇÃO na métrica escolhida; vazio reserva o mesmo espaço.
    const rankBadge = (!empty && hlPos[t]) ? `<span class="tc-rank">#${{hlPos[t]}}</span>` : '<span class="tc-rank muted">#—</span>';
    const playerCount = d.roster_count || (d.players ? d.players.filter(p => p.in_roster !== false).length : 0);
    const sub = empty ? 'sem jogos ainda · ' + (d.group ? 'Grupo ' + d.group : '')
      : nj + (nj === 1 ? ' jogo' : ' jogos') + ' · ' + playerCount + ' jogadores';

    const cp = d.campanha || {{}};

    // destaque: a MÉTRICA COMPARTILHADA (mesma da corrida)
    const hlVal = mval(t);
    const hlColor = (currentMetric.startsWith('score_') && hlVal != null) ? _scoreColor(hlVal) : '#e6edf3';
    const posBadge = (!empty && hlPos[t]) ? `<span class="m-rank">${{hlPos[t]}}º de ${{hlTotal}}</span>` : '<span class="m-rank">—</span>';
    const metric = `<div class="tc-metric">
      <span class="m-val" style="color:${{empty ? '#6b7280' : hlColor}}">${{empty ? '—' : hlFmt(hlVal)}}</span>
      <span class="m-lbl">${{hlShort}}</span>
      ${{posBadge}}
    </div>`;

    // mini-stats secundárias: campanha resumida (sempre visível, contexto)
    const fmt = v => v == null ? '—' : v;
    const stats = `<div class="tc-stats">
      <div class="tc-stat"><div class="v">${{empty ? 0 : fmt(cp.pontos)}}</div><div class="l">Pts</div></div>
      <div class="tc-stat"><div class="v">${{empty ? 0 : fmt(cp.gols_pro)}}</div><div class="l">Gols</div></div>
      <div class="tc-stat"><div class="v">${{empty ? 0 : (cp.saldo_gols != null ? (cp.saldo_gols > 0 ? '+' + cp.saldo_gols : cp.saldo_gols) : '—')}}</div><div class="l">Saldo</div></div>
      <div class="tc-stat"><div class="v">${{empty ? '—' : _fe(cp.elo_rating)}}</div><div class="l">Elo</div></div>
    </div>`;

    const badges = [
      d.group ? `<span class="tc-badge">Grupo ${{d.group}}</span>` : '',
      d.confed ? `<span class="tc-badge">${{d.confed}}</span>` : '',
      d.stage_now ? `<span class="tc-badge">${{d.stage_now}}</span>` : '',
    ].join('');

    const isFocused = ((selectedTeam && t === selectedTeam) || trajectoryTeams.includes(t));
    const focusCls = isFocused ? ' tc-focus' : '';
    const focusStyle = isFocused ? ` style="--focus-color:${{_focusColor(t)}}"` : '';
    return `<div class="team-card${{empty ? ' tc-empty' : ''}}${{focusCls}}"${{focusStyle}} ${{empty ? '' : `onclick="openTeamModal('${{t.replace(/'/g, "\\\\'")}}')"`}}>
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

// ════════════════════════════════════════════════════════════════════════════
// ABA JOGADORES — grade time-aware + filtros compartilhados + modal de detalhe
// ════════════════════════════════════════════════════════════════════════════
const PLAYER_SLUGS = Object.keys(PLAYER_META);
const PLAYERS_PER_PAGE = 50;
let playerPage = 1;
let selectedPlayer = '';
const playerFilters = {{ pos: '' }};
const PERFIL_LABEL = {{ goleiro: 'Goleiro', defensor: 'Defensor', meio: 'Meio', atacante: 'Atacante' }};
const PERFIL_PLURAL = {{ goleiro: 'Goleiros', defensor: 'Defensores', meio: 'Meias', atacante: 'Atacantes' }};

// índice [jogo][slug] → linha do jogador naquele snapshot (lookup O(1))
const PSNAP_BY_SLUG = {{}};
Object.entries(PLAYER_DATA).forEach(([n, rows]) => {{
  const by = {{}};
  rows.forEach(r => {{ by[r.slug] = r; }});
  PSNAP_BY_SLUG[n] = by;
}});

// jogador passa nos filtros (posição + os filtros de SELEÇÃO via time dele)
function playerPasses(slug, snapRow) {{
  const meta = PLAYER_META[slug] || {{}};
  if (playerFilters.pos && (snapRow ? snapRow.perfil : meta.perfil) !== playerFilters.pos) return false;
  // reaproveita os filtros de grupo/confed/fase aplicados ao TIME do jogador
  if (!passesGlobalFilters(meta.team)) return false;
  return true;
}}

function _pmetricFmt(metric) {{
  return v => {{
    if (v == null) return '—';
    if (metric === 'score_geral' || metric === 'rating_365') return v.toFixed(1);
    if (Number.isInteger(v) || Math.abs(v - Math.round(v)) < 0.005) return String(Math.round(v));
    return v.toFixed(2);
  }};
}}

function goPlayerPage(p) {{
  playerPage = p;
  renderPlayersGrid();
  document.getElementById('playersGrid').scrollTop = 0;
}}

function renderPlayersGrid() {{
  const host = document.getElementById('playersGrid');
  if (!host) return;
  const q = _norm(document.getElementById('teamSearch').value.trim());
  const teamFocuses = activeTeamFilters();
  const dir = sortDir;
  const metric = PLAYER_METRIC_LABELS[currentMetric] ? currentMetric : 'score_geral';
  const snap = PSNAP_BY_SLUG[currentJogo] || {{}};
  const pv = slug => {{ const r = snap[slug]; return r ? r[metric] : null; }};

  // filtra
  let players = PLAYER_SLUGS.filter(slug => {{
    const r = snap[slug];
    const meta = PLAYER_META[slug] || {{}};
    if (teamFocuses.length && !teamFocuses.includes(meta.team)) return false;
    if (q && !_norm(meta.name).includes(q) && !_norm(meta.team).includes(q)) return false;
    if (!playerPasses(slug, r)) return false;
    if (document.getElementById('filterPlayed').checked && (!r || !(r.jogos > 0))) return false;
    return true;
  }});

  // ordena pela métrica (ausentes no fim)
  players.sort((a, b) => {{
    let va = pv(a), vb = pv(b);
    const na = va == null, nb = vb == null;
    if (na && nb) return PLAYER_META[a].name.localeCompare(PLAYER_META[b].name, 'pt-BR');
    if (na) return 1; if (nb) return -1;
    if (va === vb) return PLAYER_META[a].name.localeCompare(PLAYER_META[b].name, 'pt-BR');
    return dir === 'asc' ? va - vb : vb - va;
  }});

  document.getElementById('teamsCount').textContent = teamFocuses.length
    ? players.length + ' jogadores · ' + (teamFocuses.length === 1 ? teamFocuses[0] : teamFocuses.length + ' seleções')
    : players.length + ' de ' + PLAYER_SLUGS.length + ' jogadores';

  // ranking da métrica DENTRO do conjunto filtrado (Xº de N)
  const ranked = players.map(s => ({{ s, v: pv(s) }})).filter(x => x.v != null)
    .sort((a, b) => dir === 'asc' ? a.v - b.v : b.v - a.v);
  const posR = {{}};
  ranked.forEach((x, i) => {{ posR[x.s] = (i > 0 && x.v === ranked[i - 1].v) ? posR[ranked[i - 1].s] : i + 1; }});

  // colunas POR POSIÇÃO: 'Todas' = só básicas; posição filtrada = stats dela.
  // Cada coluna: [chave no snapshot, rótulo curto, formatação].
  const intF = v => v == null ? '—' : String(Math.round(v));
  const f2F = v => v == null ? '—' : v.toFixed(2);
  const colsByPos = {{
    goleiro:  [['saves','Defesas',intF], ['goals_conceded','Sofridos',intF], ['expected_goals_prevented','xGP',f2F], ['high_claims','Bolas altas',intF]],
    defensor: [['tackles_won','Desarmes',intF], ['interceptions','Intercept.',intF], ['clearances','Cortes',intF], ['ball_recovery','Recup.',intF]],
    meio:     [['goals','Gols',intF], ['assists','Assist',intF], ['expected_assists','xA',f2F], ['key_passes','P-chave',intF]],
    atacante: [['goals','Gols',intF], ['expected_goals','xG',f2F], ['expected_goals_on_target','xGOT',f2F], ['shots_on_target','No alvo',intF]],
  }};
  const pos = playerFilters.pos;
  // 'Todas' = Gols e Assist separados (não G+A); posição filtrada = stats dela.
  let statCols = pos && colsByPos[pos] ? colsByPos[pos] : [['goals','Gols',intF], ['assists','Assist',intF]];
  // a métrica selecionada vira coluna destacada (se já não estiver entre as fixas)
  const baseKeys = new Set(['rating_365', 'score_geral', 'jogos', ...statCols.map(c => c[0])]);
  const metricCol = (!baseKeys.has(metric)) ? metric : null;

  // paginação (tabela cabe mais linhas)
  const totalPages = Math.max(1, Math.ceil(players.length / PLAYERS_PER_PAGE));
  if (playerPage > totalPages) playerPage = totalPages;
  const startI = (playerPage - 1) * PLAYERS_PER_PAGE;
  const pageSlugs = players.slice(startI, startI + PLAYERS_PER_PAGE);
  renderPlayersPager(totalPages);

  // cabeçalho — colunas de métrica são CLICÁVEIS para ordenar (seta ↑/↓ na ativa)
  const arrow = key => key === metric ? (dir === 'asc' ? ' ▲' : ' ▼') : '';
  const thSort = (key, label, extra='') =>
    `<th class="pt-num pt-sort${{extra}}${{key === metric ? ' pt-active' : ''}}" onclick="sortByCol('${{key}}')">${{label}}${{arrow(key)}}</th>`;
  let head = `<th class="pt-rank">#</th><th class="pt-shirt">Nº</th><th class="pt-name">Jogador</th><th>Time</th><th>Pos</th>`;
  if (metricCol) head += thSort(metricCol, PLAYER_METRIC_LABELS[metricCol] || metricCol, ' pt-metric');
  head += thSort('rating_365', 'Nota');   // nota de atuação (365scores, ~2.9-9.8)
  head += thSort('score_geral', 'Score');  // z-score de qualidade (0-100, vs posição)
  statCols.forEach(c => head += thSort(c[0], c[1]));
  head += thSort('jogos', 'Jogos');

  const rows = pageSlugs.map(slug => {{
    const meta = PLAYER_META[slug];
    const r = snap[slug];
    const empty = !r || !(r.jogos > 0);
    const flag = (TEAMS_DETAIL[meta.team] || {{}}).flag || TEAM_FLAGS[meta.team] || '🏳️';
    const perfil = (r ? r.perfil : meta.perfil) || '';
    const focusCls = (selectedPlayer && slug === selectedPlayer) ? ' pt-focus' : '';
    const rk = posR[slug] ? posR[slug] : '';
    const score = r && r.score_geral != null ? r.score_geral : null;
    const scoreColor = score != null ? _scoreColor(score) : '#8b949e';
    const rating = r && r.rating_365 != null ? r.rating_365 : null;
    const ratingColor = rating != null ? _ratingColor(rating) : '#8b949e';
    let tds = `<td class="pt-rank">${{rk}}</td>` +
      `<td class="pt-shirt">${{meta.shirt != null ? meta.shirt : ''}}</td>` +
      `<td class="pt-name">${{flag}} ${{meta.name}}</td>` +
      `<td><span class="pt-team-link${{teamFocuses.includes(meta.team) ? ' pt-team-active' : ''}}" onclick="event.stopPropagation(); selectTeamFromPlayerRow('${{meta.team.replace(/'/g, "\\'")}}')">${{meta.team}}</span></td>` +
      `<td class="pt-dim">${{(PERFIL_LABEL[perfil]||perfil||'').slice(0,3)}}</td>`;
    if (metricCol) {{
      const mv = r ? r[metricCol] : null;
      tds += `<td class="pt-num pt-metric"><b>${{_pmetricFmt(metricCol)(mv)}}</b></td>`;
    }}
    tds += `<td class="pt-num" style="color:${{ratingColor}};font-weight:700">${{rating != null ? rating.toFixed(1) : '—'}}</td>`;
    tds += `<td class="pt-num" style="color:${{scoreColor}}">${{score != null ? score.toFixed(1) : '—'}}</td>`;
    statCols.forEach(([k,, ff]) => {{ tds += `<td class="pt-num">${{r ? ff(r[k]) : '—'}}</td>`; }});
    tds += `<td class="pt-num pt-dim">${{r ? Math.round(r.jogos||0) : 0}}</td>`;
    const click = empty ? '' : `onclick="openPlayerModal('${{slug.replace(/'/g, "\\'")}}')"`;
    return `<tr class="pt-row${{empty ? ' pt-empty' : ''}}${{focusCls}}" ${{click}}>${{tds}}</tr>`;
  }}).join('');

  host.innerHTML = `<table class="players-table"><thead><tr>${{head}}</tr></thead><tbody>${{rows}}</tbody></table>`;
}}

// clicar no cabeçalho ordena por aquela coluna: 1º clique = métrica ativa
// (maior primeiro); reclique na mesma coluna inverte a direção. Sincroniza o
// dropdown de Métrica quando a coluna corresponde a uma métrica do seletor.
function sortByCol(key) {{
  if (currentMetric === key) {{
    sortDir = sortDir === 'desc' ? 'asc' : 'desc';
  }} else {{
    currentMetric = key;
    sortDir = 'desc';
  }}
  // reflete no dropdown de Métrica (se a coluna existe lá) e no botão de direção
  const sel = document.getElementById('metricSelect');
  if (sel && PLAYER_METRIC_LABELS[key]) sel.value = key;
  const btn = document.getElementById('btnDir');
  if (btn) btn.textContent = sortDir === 'desc' ? '↓ Maior primeiro' : '↑ Menor primeiro';
  renderPlayersGrid();
}}

function renderPlayersPager(totalPages) {{
  const pager = document.getElementById('playersPager');
  if (!pager) return;
  if (totalPages <= 1) {{ pager.innerHTML = ''; return; }}
  let btns = `<button class="pager-btn" onclick="goPlayerPage(${{playerPage - 1}})" ${{playerPage === 1 ? 'disabled' : ''}}>‹</button>`;
  for (let p = 1; p <= totalPages; p++)
    btns += `<button class="pager-btn${{p === playerPage ? ' active' : ''}}" onclick="goPlayerPage(${{p}})">${{p}}</button>`;
  btns += `<button class="pager-btn" onclick="goPlayerPage(${{playerPage + 1}})" ${{playerPage === totalPages ? 'disabled' : ''}}>›</button>`;
  pager.innerHTML = btns + `<span class="pager-info">página ${{playerPage}} de ${{totalPages}}</span>`;
}}

function selectTeamFromPlayerRow(team) {{
  if (!TEAMS_DETAIL[team]) return;
  selectTeam(team);
}}

// histórico do jogador: progressão score/jogos por snapshot (do PLAYER_DATA)
function playerHistory(slug, uptoN = currentJogo) {{
  const hist = [];
  let prevJogos = null;
  Object.keys(PLAYER_DATA).map(Number).sort((a, b) => a - b).forEach(n => {{
    if (n > uptoN) return;
    const r = (PSNAP_BY_SLUG[n] || {{}})[slug];
    if (!r || !(r.jogos > 0)) return;
    // só registra quando o nº de jogos AUMENTA (jogador entrou em campo num jogo novo)
    if (prevJogos === null || r.jogos > prevJogos) {{
      hist.push(n);
      prevJogos = r.jogos;
    }}
  }});
  return hist.map(n => (PSNAP_BY_SLUG[n] || {{}})[slug]);
}}

function _playerMetricValue(row, metric) {{
  if (!row) return null;
  if (metric === 'goals_conceded_por_jogo') {{
    return row.jogos > 0 && row.goals_conceded != null ? row.goals_conceded / row.jogos : null;
  }}
  return row[metric] == null ? null : row[metric];
}}

// média do PERFIL no snapshot atual (para comparação "acima/abaixo da posição")
function profileAvg(perfil, metric, n = currentJogo) {{
  const rows = (PLAYER_DATA[n] || []).filter(r => r.perfil === perfil && r.jogos > 0);
  const vals = rows.map(r => _playerMetricValue(r, metric)).filter(v => v != null);
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}}

function openPlayerModal(slug) {{
  const meta = PLAYER_META[slug];
  if (!meta) return;
  const r = (PSNAP_BY_SLUG[currentJogo] || {{}})[slug];
  const perfil = r ? r.perfil : meta.perfil;
  const shirt = meta.shirt != null ? meta.shirt : '—';
  const playerMeta = `${{shirt}} · ${{PERFIL_LABEL[perfil] || perfil || 'Jogador'}} · ${{meta.team}}`;
  document.getElementById('playerModalTitle').innerHTML =
    `<span style="font-size:0.82rem;color:#8b949e;font-weight:800">${{_esc(playerMeta)}}</span>`;
  document.getElementById('playerModalBody').innerHTML = renderPlayerModalBody(slug, r);
  document.getElementById('playerModal').style.display = 'flex';
}}
function closePlayerModal() {{ document.getElementById('playerModal').style.display = 'none'; }}

function renderPlayerModalBody(slug, r) {{
  const meta = PLAYER_META[slug];
  if (!r || !(r.jogos > 0)) {{
    return `<div class="md-empty">${{meta.name}} ainda não entrou em campo até o Jogo ${{currentJogo}}.</div>`;
  }}
  const perfil = r.perfil;
  // hero compacto: camisa + nome; ranking fica no KPI, não no cabeçalho visual.
  const teamEsc = meta.team.replace(/'/g, "\\'");
  const teamFlag = (TEAMS_DETAIL[meta.team] || {{}}).flag || TEAM_FLAGS[meta.team] || '🏳️';
  const shirtStyle = _shirtColors(meta.team);
  const hero = `<div class="rs-hero">
    <span class="rs-hero-shirt" style="${{shirtStyle}}"><span class="shirt-number">${{meta.shirt != null ? meta.shirt : ''}}</span></span>
    <div class="rs-hero-info">
      <div class="rs-hero-top"><span class="rs-hero-name">${{_esc(meta.name)}}</span></div>
    </div>
    <a class="rs-team-flag-link" href="#" onclick="event.preventDefault(); openTeamFromPlayer('${{teamEsc}}')" title="Ver ${{meta.team}}">${{teamFlag}}</a>
  </div>`;

  const fmtStat = (v, digits = 2) => {{
    if (v == null || !Number.isFinite(Number(v))) return '—';
    const n = Number(v);
    return digits === 0 ? String(Math.round(n)) : n.toFixed(digits).replace(/\\.00$/, '').replace(/(\\.\\d)0$/, '$1');
  }};
  const kv = (k, v) => `<div class="rs-kv"><span class="rs-k">${{k}}</span><span class="rs-v">${{v}}</span></div>`;
  const rankLabel = r.ranking_score_geral != null ? `#${{Math.round(r.ranking_score_geral)}}` : '—';
  const kpis = `<div class="pm-kpi-row">
    <div class="pm-kpi"><span>Nota</span><b style="color:${{r.rating_365 != null ? _ratingColor(r.rating_365) : '#e6edf3'}}">${{fmtStat(r.rating_365, 1)}}</b></div>
    <div class="pm-kpi"><span>Score</span><b>${{fmtStat(r.score_geral, 1)}}</b></div>
    <div class="pm-kpi"><span>Ranking da posição</span><b>${{rankLabel}}</b></div>
    <div class="pm-kpi"><span>Jogos</span><b>${{Math.round(r.jogos || 0)}}</b></div>
  </div>`;

  const metricTone = (metric, val, inverse = false) => {{
    const avg = profileAvg(perfil, metric);
    if (avg == null || avg <= 0 || val == null) return 'mid';
    const raw = inverse ? (avg - val) / avg : (val - avg) / avg;
    return raw >= 0.15 ? 'up' : raw <= -0.15 ? 'down' : 'mid';
  }};
  const metricTile = (label, metric, note, digits = 2, inverse = false) => {{
    const val = _playerMetricValue(r, metric);
    const tone = metricTone(metric, val, inverse);
    return `<div class="pm-metric ${{tone}}">
      <span class="pm-metric-label">${{label}}</span>
      <span class="pm-metric-value">${{fmtStat(val, digits)}}</span>
      <span class="pm-metric-note">${{note}}</span>
    </div>`;
  }};
  const card = (title, items) => `<div class="pm-role-card">
    <div class="pm-role-title">${{title}}</div>
    <div class="pm-metric-list">${{items.map(item => metricTile(...item)).join('')}}</div>
  </div>`;
  const roleSections = {{
    goleiro: [
      ['Proteção do gol', [
        ['Defesas', 'defesas_por_jogo', 'volume real de intervenções', 2],
        ['Gols sofridos', 'goals_conceded_por_jogo', 'quanto dano passou pela defesa', 2, true],
        ['Gols evitados', 'expected_goals_prevented_por_jogo', 'defesa/goleiro acima do esperado', 2],
      ]],
      ['Área e pressão', [
        ['Bolas altas', 'high_claims_por_jogo', 'saída em cruzamentos e bolas longas', 2],
        ['Socos', 'punches_por_jogo', 'resposta quando não dá para encaixar', 2],
        ['Pênaltis defendidos', 'penalties_saved_por_jogo', 'eventos raros, mas decisivos', 2],
      ]],
    ],
    defensor: [
      ['Proteção', [
        ['Desarmes', 'tackles_won_por_jogo', 'vence duelos diretos no chão', 2],
        ['Interceptações', 'interceptions_por_jogo', 'antecipa linhas de passe', 2],
        ['Cortes', 'clearances_por_jogo', 'remove perigo da área', 2],
        ['Chutes bloqueados', 'shots_blocked_por_jogo', 'protege a finalização', 2],
      ]],
      ['Cobertura', [
        ['Recuperações', 'ball_recovery_por_jogo', 'ganha segunda bola e reorganiza', 2],
        ['Duelos ganhos', 'duels_won_por_jogo', 'força física e disputa aérea', 2],
        ['Gols evitados', 'expected_goals_prevented_por_jogo', 'impacto defensivo acima do esperado', 2],
      ]],
      ['Apoio com bola', [
        ['Assistências', 'assistencias_por_jogo', 'participação direta em gol', 2],
        ['xA', 'expected_assists_por_jogo', 'qualidade dos passes para chance', 2],
        ['Passes-chave', 'key_passes_por_jogo', 'passes que viram finalização', 2],
      ]],
    ],
    meio: [
      ['Criação', [
        ['Assistências', 'assistencias_por_jogo', 'passe final convertido em gol', 2],
        ['xA', 'expected_assists_por_jogo', 'qualidade das chances criadas', 2],
        ['Passes-chave', 'key_passes_por_jogo', 'criação que vira finalização', 2],
        ['Chances claras criadas', 'big_chances_created_por_jogo', 'passes para chances claras', 2],
      ]],
      ['Controle e disputa', [
        ['Dribles ganhos', 'dribbles_won_por_jogo', 'quebra linhas com a bola', 2],
        ['Recuperações', 'ball_recovery_por_jogo', 'sustenta pressão pós-perda', 2],
        ['Desarmes', 'tackles_won_por_jogo', 'contribuição sem bola', 2],
      ]],
      ['Chegada ao gol', [
        ['Gols', 'gols_por_jogo', 'ameaça final', 2],
        ['xG', 'expected_goals_por_jogo', 'qualidade das próprias chances', 2],
        ['Chutes no alvo', 'chutes_no_alvo_por_jogo', 'finalização que exige defesa', 2],
      ]],
    ],
    atacante: [
      ['Finalização', [
        ['Gols', 'gols_por_jogo', 'produção que já virou placar', 2],
        ['xG', 'expected_goals_por_jogo', 'qualidade das chances recebidas', 2],
        ['xGOT', 'expected_goals_on_target_por_jogo', 'qualidade do chute no alvo', 2],
        ['Chutes no alvo', 'chutes_no_alvo_por_jogo', 'ameaça que força defesa', 2],
      ]],
      ['Criação e 1x1', [
        ['Assistências', 'assistencias_por_jogo', 'passe final convertido em gol', 2],
        ['xA', 'expected_assists_por_jogo', 'qualidade dos passes para chance', 2],
        ['Passes-chave', 'key_passes_por_jogo', 'criação que vira finalização', 2],
        ['Dribles ganhos', 'dribbles_won_por_jogo', 'vantagem criada no duelo', 2],
      ]],
      ['Decisão', [
        ['Chances claras marcadas', 'big_chances_scored_por_jogo', 'chance clara convertida', 2],
        ['Chances claras perdidas', 'big_chances_missed_por_jogo', 'chance clara desperdiçada', 2, true],
        ['Participações em gol', 'participacoes_por_jogo', 'gols + assistências por jogo', 2],
      ]],
    ],
  }};
  const sections = roleSections[perfil] || roleSections.atacante;
  const roleHtml = `<div class="pm-role-grid${{sections.length === 2 ? ' two' : ''}}">${{sections.map(([title, items]) => card(title, items)).join('')}}</div>`;
  const disciplineHtml = `<div class="pm-discipline-strip">
    <div class="pm-discipline-item card-yellow"><span class="pm-icon">C</span><span>Cartões amarelos</span><b>${{fmtStat(r.yellow_cards || 0, 0)}}</b></div>
    <div class="pm-discipline-item card-red"><span class="pm-icon">C</span><span>Cartões vermelhos</span><b>${{fmtStat(r.red_cards || 0, 0)}}</b></div>
    <div class="pm-discipline-item foul-made"><span class="pm-icon">F</span><span>Faltas cometidas</span><b>${{fmtStat(r.faltas_cometidas_por_jogo || 0, 1)}}</b></div>
    <div class="pm-discipline-item foul-won"><span class="pm-icon">+</span><span>Faltas sofridas</span><b>${{fmtStat(r.faltas_sofridas_por_jogo || 0, 1)}}</b></div>
  </div>`;

  // histórico jogo a jogo (acumulado por snapshot em que jogou)
  const hist = playerHistory(slug);
  const histRows = hist.map(h => {{
    return `<tr><td>J${{h.jogos}}</td><td>${{h.score_geral != null ? h.score_geral.toFixed(1) : '—'}}</td>
      <td>${{Math.round(h.goals||0)}}</td><td>${{Math.round(h.assists||0)}}</td>
      <td>#${{Math.round(h.ranking_score_geral)}}</td></tr>`;
  }}).join('');
  const histHtml = hist.length > 1 ? `<div class="pm-hist">
    <div class="rs-col-title">Evolução por jogo disputado</div>
    <table class="pm-table"><thead><tr><th>Após</th><th>Nota</th><th>G</th><th>A</th><th>Rank</th></tr></thead>
    <tbody>${{histRows}}</tbody></table></div>` : '';

  return `${{hero}}${{kpis}}
    <div class="pm-section"><div class="rs-col-title">Leitura por função · valores por jogo e comparação com a posição</div>${{roleHtml}}</div>
    ${{disciplineHtml}}
    ${{histHtml}}`;
}}

// abre o modal da seleção a partir do jogador
function openTeamFromPlayer(team) {{
  closePlayerModal();
  if (TEAMS_DETAIL[team]) openTeamModal(team);
}}

let modalTeam = null;
let modalTab = 'scores';
let expandedGame = null;  // índice do jogo expandido na aba Jogos (accordion)

function openTeamModal(team) {{
  const d = teamDetailAt(team, currentJogo);
  if (!d) return;
  if (selectedTeam !== team) {{
    selectedTeam = team;
    addTrajectoryTeam(team, false);
    syncDotRows();
    renderJogo(currentJogo);
    if (activeTab === 'teams') renderTeamsGrid();
    if (activeTab === 'players') {{
      playerPage = 1;
      renderPlayersGrid();
    }}
  }}
  refreshFilterOptions();
  modalTeam = team;
  modalTab = 'scores';
  expandedGame = null;
  openRosterCards.clear();
  const tabs = [
    ['scores', 'Resumo'],
    ['estilo', 'Estilo'],
    ['jogos', 'Jogos (' + (d.jogos ? d.jogos.length : 0) + ')'],
    ['elenco', 'Elenco (' + (d.roster_count || (d.players ? d.players.filter(p => p.in_roster !== false).length : 0)) + ')'],
  ];
  document.getElementById('modalTabs').innerHTML = tabs.map(([k, l]) =>
    `<button class="modal-tab${{k === 'scores' ? ' active' : ''}}" data-mt="${{k}}" onclick="switchModalTab('${{k}}')">${{l}}</button>`
  ).join('');
  renderModalBody();
  document.getElementById('teamModal').style.display = 'flex';
}}

function closeTeamModal() {{
  document.getElementById('teamModal').style.display = 'none';
  openPlayerCards.clear();
  openRosterCards.clear();
  highlightedPlayer = null;
  modalTeam = null;
}}

function switchModalTab(t) {{
  modalTab = t;
  expandedGame = null;  // ao trocar de aba, fecha qualquer jogo expandido
  openPlayerCards.clear();
  openRosterCards.clear();
  highlightedPlayer = null;
  document.querySelectorAll('.modal-tab').forEach(b =>
    b.classList.toggle('active', b.dataset.mt === t));
  renderModalBody();
}}

function toggleGame(i) {{
  openPlayerCards.clear(); highlightedPlayer = null;
  if (expandedGame === i) {{ expandedGame = null; }}
  else {{ expandedGame = i; gameDetailTab = 'historia'; }}  // abre na História
  renderModalBody();
}}

let gameDetailTab = 'historia';  // mini-aba ativa dentro do jogo expandido
let highlightedPlayer = null;     // jogador destacado no campo (par da troca)
const openPlayerCards = new Set(); // jogadores com card de dados aberto
const openRosterCards = new Set(); // cards acumulados abertos na aba Elenco
const rosterCardAnchors = {{}};
const fieldCardAnchors = {{}};
const fieldSubOverrides = {{}};     // jogo/par -> jogador que aparece na vaga
const playerCardOffsets = {{}};      // chave jogador/jogo -> deslocamento arrastado
let playerCardDrag = null;

function _playerCardKey(name) {{
  return `${{modalTeam || ''}}|${{expandedGame ?? ''}}|${{name || ''}}`;
}}

function _rosterCardKey(name) {{
  return `${{modalTeam || ''}}|elenco|${{name || ''}}`;
}}

function _subPairKey(a, b) {{
  return `${{modalTeam || ''}}|${{expandedGame ?? ''}}|sub|${{[a || '', b || ''].sort().join('|')}}`;
}}

function startPlayerCardDrag(ev, key) {{
  if (ev.button != null && ev.button !== 0) return;
  if (ev.target.closest('.pc-close')) return;
  ev.preventDefault();
  ev.stopPropagation();
  const card = ev.currentTarget.closest('.pcard');
  const off = playerCardOffsets[key] || {{ x: 0, y: 0 }};
  playerCardDrag = {{
    key, card,
    startX: ev.clientX,
    startY: ev.clientY,
    baseX: off.x || 0,
    baseY: off.y || 0,
    fixed: card.classList.contains('el-pop') || card.classList.contains('field-pop'),
    anchorLeft: parseFloat(getComputedStyle(card).left) || 0,
    anchorTop: parseFloat(getComputedStyle(card).top) || 0,
  }};
  card.classList.add('dragging');
  ev.currentTarget.setPointerCapture?.(ev.pointerId);
}}

function movePlayerCardDrag(ev) {{
  if (!playerCardDrag) return;
  ev.preventDefault();
  let x = playerCardDrag.baseX + ev.clientX - playerCardDrag.startX;
  let y = playerCardDrag.baseY + ev.clientY - playerCardDrag.startY;
  if (playerCardDrag.fixed) {{
    const margin = 8;
    const w = playerCardDrag.card.offsetWidth || 260;
    const h = playerCardDrag.card.offsetHeight || 260;
    x = Math.max(margin - playerCardDrag.anchorLeft, Math.min(x, window.innerWidth - margin - w - playerCardDrag.anchorLeft));
    y = Math.max(margin - playerCardDrag.anchorTop, Math.min(y, window.innerHeight - margin - h - playerCardDrag.anchorTop));
  }}
  playerCardOffsets[playerCardDrag.key] = {{ x, y }};
  playerCardDrag.card.style.setProperty('--pc-x', `${{x}}px`);
  playerCardDrag.card.style.setProperty('--pc-y', `${{y}}px`);
}}

function endPlayerCardDrag() {{
  if (!playerCardDrag) return;
  playerCardDrag.card.classList.remove('dragging');
  playerCardDrag = null;
}}

document.addEventListener('pointermove', movePlayerCardDrag);
document.addEventListener('pointerup', endPlayerCardDrag);
document.addEventListener('pointercancel', endPlayerCardDrag);

function switchGameTab(t) {{
  gameDetailTab = t;
  highlightedPlayer = null;
  openPlayerCards.clear();
  renderModalBody();
}}

function anchorPlayerCard(name, anchorEl = null, index = 0) {{
  if (!anchorEl) return;
  const key = _playerCardKey(name);
  const rect = anchorEl.getBoundingClientRect();
  const margin = 8;
  const w = Math.min(248, window.innerWidth - margin * 2);
  const estimatedH = 286;
  let left = rect.right + 12 + index * 28;
  if (left + w > window.innerWidth - margin) left = rect.left - w - 12 - index * 28;
  if (left < margin) left = rect.left + rect.width / 2 - w / 2 + index * 28;
  left = Math.max(margin, Math.min(left, window.innerWidth - margin - w));
  let top = rect.top + rect.height / 2 - estimatedH / 2 + index * 24;
  top = Math.max(margin, Math.min(top, window.innerHeight - margin - 120));
  fieldCardAnchors[key] = {{ left: Math.round(left), top: Math.round(top) }};
  playerCardOffsets[key] = {{ x: 0, y: 0 }};
}}

// clica num jogador → alterna o card dele, sem fechar os outros
function showPlayerCard(name, anchorEl = null) {{
  const key = _playerCardKey(name);
  if (openPlayerCards.has(name)) {{
    openPlayerCards.delete(name);
    highlightedPlayer = highlightedPlayer === name
      ? (Array.from(openPlayerCards).pop() || null)
      : highlightedPlayer;
  }} else {{
    openPlayerCards.add(name);
    highlightedPlayer = name;
    anchorPlayerCard(name, anchorEl, 0);
  }}
  renderModalBody();
}}

// usado na timeline de substituição: abre os dois envolvidos lado a lado.
function showPlayerCards(names, anchorEl = null) {{
  const clean = [...new Set((names || []).filter(Boolean))];
  if (!clean.length) return;
  const allOpen = clean.every(n => openPlayerCards.has(n));
  if (allOpen) {{
    clean.forEach(n => openPlayerCards.delete(n));
    highlightedPlayer = Array.from(openPlayerCards).pop() || null;
  }} else {{
    clean.forEach((n, i) => {{
      openPlayerCards.add(n);
      anchorPlayerCard(n, anchorEl, i);
    }});
    highlightedPlayer = clean[0];
  }}
  renderModalBody();
}}

function togglePitchSub(a, b, anchorEl = null) {{
  if (!a || !b) return;
  const key = _subPairKey(a, b);
  const current = fieldSubOverrides[key] || a;
  const next = current === a ? b : a;
  fieldSubOverrides[key] = next;

  openPlayerCards.delete(current);
  openPlayerCards.add(next);
  highlightedPlayer = next;
  anchorPlayerCard(next, anchorEl, 0);
  renderModalBody();
}}

function showRosterPlayer(name, anchorEl = null) {{
  const key = _rosterCardKey(name);
  if (openRosterCards.has(name)) {{
    openRosterCards.delete(name);
    renderModalBody();
    return;
  }}
  openRosterCards.add(name);
  if (anchorEl) {{
    const rect = anchorEl.getBoundingClientRect();
    const margin = 8;
    const w = Math.min(260, window.innerWidth - margin * 2);
    const estimatedH = 286;
    let left = rect.left + rect.width / 2 - w / 2;
    left = Math.max(margin, Math.min(left, window.innerWidth - margin - w));
    let top = rect.bottom + 8;
    if (top + estimatedH > window.innerHeight - margin) top = rect.top - estimatedH - 8;
    top = Math.max(margin, Math.min(top, window.innerHeight - margin - 120));
    rosterCardAnchors[key] = {{ left: Math.round(left), top: Math.round(top) }};
    playerCardOffsets[key] = {{ x: 0, y: 0 }};
  }}
  renderModalBody();
}}

// clica num reserva/timeline → destaca a troca (sem abrir card)
function highlightSub(name) {{
  highlightedPlayer = (highlightedPlayer === name) ? null : name;
  openPlayerCards.clear();
  renderModalBody();
}}

// clica num jogador na linha do tempo → vai pra escalação e abre o card dele
function focusPlayer(name) {{
  if (!name) return;
  gameDetailTab = 'escalacao';
  openPlayerCards.add(name);
  highlightedPlayer = name;
  renderModalBody();
}}

// monta o card flutuante com as stats do jogador na partida.
// Cada perfil mostra um pacote próprio, para comparação limpa entre jogadores da mesma função.
const _fmt2 = v => Number(v || 0).toFixed(2);
const _fmtPct = v => v == null ? '—' : v + '%';
const _PC_LABEL_HELP = {{
  'Faltas comet.': 'Faltas cometidas',
  'Amarelos': 'Cartões amarelos',
  'Vermelhos': 'Cartões vermelhos',
  'xGP': 'xGP (gols evitados): gols evitados acima do esperado pelo goleiro/defesa',
  'Pênaltis def.': 'Pênaltis defendidos',
  'Bolas altas': 'Bolas altas seguradas',
  'Socos': 'Bolas socadas pelo goleiro',
  'Cortes def.': 'Cortes defensivos',
  'Chutes bloq.': 'Chutes bloqueados',
  'Bolas recup.': 'Bolas recuperadas',
  'xA': 'xA (assistências esperadas)',
  'Passes p/ chute': 'Passes para chute',
  'Gr. chances criadas': 'Grandes chances criadas',
  'xG': 'xG (gols esperados)',
  'xGOT': 'xGOT (qualidade do chute no alvo)',
  'Gr. chances em gol': 'Grandes chances em gol',
  'Gr. chances perdidas': 'Grandes chances perdidas',
}};
function _pcTitleAttr(lbl, help) {{
  const title = help || _PC_LABEL_HELP[lbl] || '';
  return title ? ` title="${{_esc(title)}}"` : '';
}}
const _DISCIPLINE_GAME_GROUP = ['Disciplina', [
  ['fouls_committed', 'Faltas comet.', null, true],
  ['fouls_drawn', 'Faltas sofridas', null, true],
  ['yellow', 'Amarelos', null, true],
  ['red', 'Vermelhos', null, true],
]];
function _playerRoleFromPos(pos) {{
  const p = String(pos || '').toUpperCase();
  if (p === 'G' || p === 'GK' || p.includes('GOAL') || p.includes('GOLEIRO')) return 'goleiro';
  if (p.includes('CF') || p.includes('FW') || p.includes('FORWARD') || p.includes('WINGER') || p.includes('ATACANTE') || p.includes('CENTROAVANTE') || p.includes('PONTA') || /^F/.test(p) || /^ST/.test(p) || p === 'LF' || p === 'RF' || p === 'LW' || p === 'RW' || p === 'RCF' || p === 'SS') return 'atacante';
  if (p.includes('DM') || p.includes('CM') || p.includes('AM') || p.includes('MID') || p.includes('MEIA') || p.includes('VOLANTE') || p === 'M' || p === 'MF' || p === 'LM' || p === 'RM') return 'meio';
  return 'defensor';
}}
const _STAT_GROUPS_BY_ROLE = {{
  goleiro: [
    ['Goleiro', [
      ['saves', 'Defesas feitas', null, true],
      ['goals_conceded', 'Gols sofridos', null, true],
    ]],
    ['Ações do goleiro', [
      ['xgp', 'xGP', _fmt2, true],
      ['penalties_saved', 'Pênaltis def.', null, true],
      ['high_claims', 'Bolas altas', null, true],
      ['punches', 'Socos', null, true],
    ]],
    ['Distribuição', [
      ['pass_acc', 'Acerto de passe', _fmtPct, true],
    ]],
  ],
  defensor: [
    ['Defesa', [
      ['tackles_won', 'Desarmes', null, true],
      ['interceptions', 'Interceptações', null, true],
      ['clearances', 'Cortes def.', null, true],
      ['shots_blocked', 'Chutes bloq.', null, true],
    ]],
    ['Cobertura', [
      ['ball_recovery', 'Bolas recup.', null, true],
      ['duels_won', 'Duelos ganhos', null, true],
    ]],
    ['Apoio', [
      ['assists', 'Assistências', null, true],
      ['xa', 'xA', _fmt2, true],
      ['key_passes', 'Passes p/ chute', null, true],
      ['goals', 'Gols', null, true],
    ]],
  ],
  meio: [
    ['Criação', [
      ['assists', 'Assistências', null, true],
      ['xa', 'xA', _fmt2, true],
      ['key_passes', 'Passes p/ chute', null, true],
      ['big_chances_created', 'Gr. chances criadas', null, true],
    ]],
    ['Controle', [
      ['pass_acc', 'Acerto de passe', _fmtPct],
      ['dribbles_won', 'Dribles ganhos', null, true],
      ['ball_recovery', 'Bolas recup.', null, true],
      ['tackles_won', 'Desarmes', null, true],
    ]],
    ['Finalização', [
      ['goals', 'Gols', null, true],
      ['xg', 'xG', _fmt2, true],
      ['shots', 'Finalizações', null, true],
      ['on_target', 'Chutes no alvo', null, true],
    ]],
  ],
  atacante: [
    ['Finalização', [
      ['goals', 'Gols', null, true],
      ['shots', 'Finalizações', null, true],
      ['on_target', 'Chutes no alvo', null, true],
      ['xg', 'xG', _fmt2, true],
    ]],
    ['Chances', [
      ['xgot', 'xGOT', _fmt2, true],
      ['big_chances_scored', 'Gr. chances em gol', null, true],
      ['big_chances_missed', 'Gr. chances perdidas', null, true],
      ['offsides', 'Impedimentos', null, true],
    ]],
    ['Criação', [
      ['assists', 'Assistências', null, true],
      ['xa', 'xA', _fmt2, true],
      ['key_passes', 'Passes p/ chute', null, true],
      ['dribbles_won', 'Dribles ganhos', null, true],
    ]],
  ],
}};
function _playerCardHtml(p, vside, hside) {{
  const st = p.stats || {{}};
  // tags de contexto (gol/cartão/entrada-saída)
  const ctx = [];
  if (p.goals) ctx.push(`<span class="pc-tag goal">⚽ ${{p.goals}} gol${{p.goals > 1 ? 's' : ''}}</span>`);
  if (p.own_goal) ctx.push(`<span class="pc-tag vermelho">🥅 ${{p.own_goal > 1 ? p.own_goal + ' gols contra' : 'Gol contra'}}</span>`);
  if (p.card) ctx.push(`<span class="pc-tag ${{p.card}}">${{p.card === 'vermelho' ? '🟥 Expulso' : '🟨 Amarelo'}}</span>`);
  if (p.exited) ctx.push(`<span class="pc-tag out">↓ Saiu ${{p.exited}}'</span>`);
  if (p.entered) ctx.push(`<span class="pc-tag in">↑ Entrou ${{p.entered}}'</span>`);

  const role = _playerRoleFromPos(p.pos_code || p.pos);
  const groupDefs = [...(_STAT_GROUPS_BY_ROLE[role] || _STAT_GROUPS_BY_ROLE.defensor), _DISCIPLINE_GAME_GROUP];
  const groups = groupDefs.map(([title, rows]) => {{
    const cells = rows.filter(([k, , , always]) => always || st[k] != null)
      .map(([k, lbl, fmt, , help]) => {{
        const raw = st[k] != null ? st[k] : 0;
        return `<div class="pc-stat"><span class="pc-sl"${{_pcTitleAttr(lbl, help)}}>${{lbl}}</span><span class="pc-sv">${{fmt ? fmt(raw) : raw}}</span></div>`;
      }})
      .join('');
    return cells ? `<div class="pc-group"><div class="pc-gt">${{title}}</div><div class="pc-grid">${{cells}}</div></div>` : '';
  }}).join('');

  // topo estável: nota à esquerda, minutos/tags à direita, sempre com mesma altura.
  const ratingHtml = st.rating != null
    ? `<span class="pc-rating">${{(+st.rating).toFixed(1)}}<small>nota</small></span>`
    : '<span class="pc-rating empty">0.0<small>nota</small></span>';
  const minutesHtml = st.minutes != null
    ? `<span class="pc-chip">${{st.minutes}}' em campo</span>`
    : '<span class="pc-chip">&nbsp;</span>';
  const ctxHtml = ctx.length
    ? `<div class="pc-ctx">${{ctx.join('')}}</div>`
    : '<div class="pc-ctx empty"><span class="pc-tag">placeholder</span></div>';

  const key = _playerCardKey(p.name);
  const off = playerCardOffsets[key] || {{ x: 0, y: 0 }};
  const anchor = fieldCardAnchors[key] || {{ left: 16, top: 16 }};
  const keyEsc = key.replace(/\\\\/g, "\\\\\\\\").replace(/'/g, "\\\\'");
  const esc = (p.name || '').replace(/'/g, "\\\\'");
  return `<div class="pcard field-pop" style="--field-pop-left:${{anchor.left}}px;--field-pop-top:${{anchor.top}}px;--pc-x:${{off.x || 0}}px;--pc-y:${{off.y || 0}}px" onclick="event.stopPropagation()">
    <div class="pc-head" onpointerdown="startPlayerCardDrag(event, '${{keyEsc}}')">
      <span class="pc-num">${{p.num ?? ''}}</span>
      <div class="pc-id"><span class="pc-name">${{p.name}}</span>${{p.pos ? `<span class="pc-pos">${{p.pos}}</span>` : ''}}</div>
      <button class="pc-close" onclick="event.stopPropagation();showPlayerCard('${{esc}}')">✕</button>
    </div>
    <div class="pc-meta">${{ratingHtml}}<div class="pc-meta-side">${{minutesHtml}}${{ctxHtml}}</div></div>
    ${{groups || '<div class="pc-empty">Sem estatísticas detalhadas.</div>'}}
  </div>`;
}}

function _rosterPlayerCardHtml(p) {{
  const n = (k) => p[k] == null ? 0 : Number(p[k] || 0);
  const fmt = (v, digits = 0) => {{
    if (v == null || !Number.isFinite(Number(v))) return null;
    return digits ? Number(v).toFixed(digits) : String(Math.round(Number(v)));
  }};
  const ctx = [];
  if (n('gols')) ctx.push(`<span class="pc-tag goal">⚽ ${{n('gols')}} gol${{n('gols') > 1 ? 's' : ''}}</span>`);
  if (n('gols_contra')) ctx.push(`<span class="pc-tag vermelho">🥅 ${{n('gols_contra')}} gol${{n('gols_contra') > 1 ? 's' : ''}} contra</span>`);
  if (n('amarelos')) ctx.push(`<span class="pc-tag amarelo">🟨 ${{n('amarelos')}} amarelo${{n('amarelos') > 1 ? 's' : ''}}</span>`);
  if (n('vermelhos')) ctx.push(`<span class="pc-tag vermelho">🟥 ${{n('vermelhos')}} vermelho${{n('vermelhos') > 1 ? 's' : ''}}</span>`);

  const group = (title, rows) => {{
    const cells = rows
      .filter(([, key, , always]) => always || p[key] != null)
      .map(([lbl, key, digits = 0, , help]) => `<div class="pc-stat"><span class="pc-sl"${{_pcTitleAttr(lbl, help)}}>${{lbl}}</span><span class="pc-sv">${{fmt(n(key), digits)}}</span></div>`)
      .join('');
    return cells ? `<div class="pc-group"><div class="pc-gt">${{title}}</div><div class="pc-grid">${{cells}}</div></div>` : '';
  }};

  const escName = _esc(p.name || '');
  const playerSlug = _playerSlugFor(modalTeam, p.name);
  const slugEsc = playerSlug ? playerSlug.replace(/\\\\/g, "\\\\\\\\").replace(/'/g, "\\\\'") : '';
  const nameHtml = playerSlug
    ? `<button class="pc-name-link" onpointerdown="event.stopPropagation()" onclick="event.stopPropagation();openPlayerModal('${{slugEsc}}')">${{escName}}</button>`
    : `<span class="pc-name">${{escName}}</span>`;
  const closeName = (p.name || '').replace(/'/g, "\\\\'");
  const key = _rosterCardKey(p.name);
  const keyEsc = key.replace(/\\\\/g, "\\\\\\\\").replace(/'/g, "\\\\'");
  const anchor = rosterCardAnchors[key] || {{ left: 16, top: 16 }};
  const off = playerCardOffsets[key] || {{ x: 0, y: 0 }};
  const ctxHtml = ctx.length
    ? `<div class="pc-ctx">${{ctx.join('')}}</div>`
    : '<div class="pc-ctx empty"><span class="pc-tag">placeholder</span></div>';
  const ratingHtml = p.rating_media != null
    ? `<span class="pc-rating">${{(+p.rating_media).toFixed(1)}}<small>média</small></span>`
    : '<span class="pc-rating empty">0.0<small>média</small></span>';
  const gameCount = n('jogos');
  const ratingCount = n('rating_jogos');
  const ratingCtx = gameCount > 0 && ratingCount !== gameCount
    ? `<span class="pc-chip">${{ratingCount}} nota${{ratingCount === 1 ? '' : 's'}}</span>`
    : '';
  const gamesCtx = `<span class="pc-tag neutral">${{gameCount}} jogo${{gameCount === 1 ? '' : 's'}}</span>`;
  const role = p.pos_group || 'Sem posição';
  const disciplineGroup = ['Disciplina', [
    ['Faltas comet.', 'faltas', 0, true],
    ['Faltas sofridas', 'faltas_sofridas', 0, true],
    ['Amarelos', 'amarelos', 0, true],
    ['Vermelhos', 'vermelhos', 0, true],
  ]];
  const roleGroups = {{
    'Goleiros': [
      ['Goleiro', [
        ['Defesas feitas', 'defesas', 0, true],
        ['Gols sofridos', 'gols_contra', 0, true],
      ]],
      ['Ações do goleiro', [
        ['xGP', 'xgp', 2, true],
        ['Pênaltis def.', 'penaltis_defendidos', 0, true],
        ['Bolas altas', 'bolas_altas', 0, true],
        ['Socos', 'socos', 0, true],
      ]],
    ],
    'Defensores': [
      ['Defesa', [
        ['Desarmes', 'desarmes', 0, true],
        ['Interceptações', 'interceptacoes', 0, true],
        ['Cortes def.', 'cortes', 0, true],
        ['Chutes bloq.', 'bloqueios', 0, true],
      ]],
      ['Cobertura', [
        ['Bolas recup.', 'recuperacoes', 0, true],
        ['Duelos ganhos', 'duelos', 0, true],
      ]],
      ['Apoio', [
        ['Assistências', 'assist', 0, true],
        ['xA', 'xa', 2, true],
        ['Passes p/ chute', 'passes_chave', 0, true],
        ['Gols', 'gols', 0, true],
      ]],
    ],
    'Meias': [
      ['Criação', [
        ['Assistências', 'assist', 0, true],
        ['xA', 'xa', 2, true],
        ['Passes p/ chute', 'passes_chave', 0, true],
        ['Gr. chances criadas', 'gr_chances_criadas', 0, true],
      ]],
      ['Controle', [
        ['Dribles ganhos', 'dribles', 0, true],
        ['Bolas recup.', 'recuperacoes', 0, true],
        ['Desarmes', 'desarmes', 0, true],
        ['Interceptações', 'interceptacoes', 0, true],
      ]],
      ['Finalização', [
        ['Gols', 'gols', 0, true],
        ['xG', 'xg', 2, true],
        ['Finalizações', 'chutes', 0, true],
        ['Chutes no alvo', 'no_alvo', 0, true],
      ]],
    ],
    'Atacantes': [
      ['Finalização', [
        ['Gols', 'gols', 0, true],
        ['Finalizações', 'chutes', 0, true],
        ['Chutes no alvo', 'no_alvo', 0, true],
        ['xG', 'xg', 2, true],
      ]],
      ['Chances', [
        ['xGOT', 'xgot', 2, true],
        ['Gr. chances em gol', 'gr_chances_convertidas', 0, true],
        ['Gr. chances perdidas', 'gr_chances_perdidas', 0, true],
        ['Impedimentos', 'impedimentos', 0, true],
      ]],
      ['Criação', [
        ['Assistências', 'assist', 0, true],
        ['xA', 'xa', 2, true],
        ['Passes p/ chute', 'passes_chave', 0, true],
        ['Dribles ganhos', 'dribles', 0, true],
      ]],
    ],
  }};
  const groupsHtml = [...(roleGroups[role] || roleGroups['Defensores']), disciplineGroup]
    .map(([title, rows]) => group(title, rows))
    .join('');
  return `<div class="pcard el-pop" style="--el-pop-left:${{anchor.left}}px;--el-pop-top:${{anchor.top}}px;--pc-x:${{off.x || 0}}px;--pc-y:${{off.y || 0}}px" onclick="event.stopPropagation()">
    <div class="pc-head" onpointerdown="startPlayerCardDrag(event, '${{keyEsc}}')">
      ${{_kitShirtHtml(p.num, modalTeam, 'pc-shirt')}}
      <div class="pc-id">${{nameHtml}}<span class="pc-pos">${{_esc(p.pos || '—')}}</span></div>
      <button class="pc-close" onclick="event.stopPropagation();showRosterPlayer('${{closeName}}')">✕</button>
    </div>
    <div class="pc-meta">${{ratingHtml}}<div class="pc-meta-side"><div class="pc-ctx">${{gamesCtx}}${{ratingCtx}}</div>${{ctxHtml}}</div></div>
    ${{groupsHtml || '<div class="pc-empty">Sem estatísticas detalhadas.</div>'}}
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
  let t = raw.replace(/\\[\\[[^|\\]]*\\|([^\\]]+)\\]\\]/g, '$1').replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1');
  t = _esc(t);
  // **negrito** e *itálico*
  t = t.replace(/\\*\\*([^*]+)\\*\\*/g, '<b>$1</b>').replace(/\\*([^*]+)\\*/g, '<i>$1</i>');

  // agrupa linhas em parágrafos e listas
  const lines = t.split('\\n');
  let html = '', list = [];
  const flushList = () => {{ if (list.length) {{ html += '<ul class="gd-list">' + list.map(li => `<li>${{li}}</li>`).join('') + '</ul>'; list = []; }} }};
  for (let ln of lines) {{
    ln = ln.trim();
    if (!ln) {{ flushList(); continue; }}
    const m = ln.match(/^[-•]\\s+(.*)/);
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
    // segue a ordem real do confronto: mandante à esquerda, visitante à direita.
    // s.mine = time visto, s.opp = adversário; troca os lados se o visto é visitante.
    const homeIsMe = g.home_team === modalTeam;
    const leftName = g.home_team || (homeIsMe ? modalTeam : g.opp);
    const rightName = g.away_team || (homeIsMe ? g.opp : modalTeam);
    const leftFlag = g.home_flag || '';
    const rightFlag = g.away_flag || '';
    const statByLabel = (label) => (g.stats_cmp || []).find(s => s.label === label);
    const sideVals = (s) => {{
      const lv = (homeIsMe ? s.mine : s.opp);
      const rv = (homeIsMe ? s.opp : s.mine);
      const lvn = lv == null ? 0 : lv, rvn = rv == null ? 0 : rv;
      const total = lvn + rvn;
      const suf = s.pct ? '%' : '';
      return {{ lv, rv, lvn, rvn, suf, lpct: total ? Math.round(lvn / total * 100) : 0, rpct: total ? Math.round(rvn / total * 100) : 0 }};
    }};
    const fmtStat = (v, suf) => v == null ? '—' : `${{v}}${{suf}}`;
    const fmtDiff = (v) => Number.isInteger(v) ? `${{v}}` : v.toFixed(1).replace(/\\.0$/, '');
    const edgeText = (s, d) => {{
      if (d.lvn === d.rvn) return 'igual';
      return `+${{fmtDiff(Math.abs(d.lvn - d.rvn))}}${{s.pct ? ' p.p.' : ''}}`;
    }};
    const spotlightCard = (title, label) => {{
      const s = statByLabel(label);
      if (!s) return '';
      const d = sideVals(s);
      const edgeSide = d.lvn === d.rvn ? 'even' : (d.lvn > d.rvn ? 'left' : 'right');
      return `<div class="gd-spot">
        <div class="gd-spot-top"><span class="gd-spot-title">${{title}}</span><span class="gd-spot-edge ${{edgeSide}}">${{edgeText(s, d)}}</span></div>
        <div class="gd-spot-values">
          <span class="gd-spot-num left">${{fmtStat(d.lv, d.suf)}}</span>
          <span class="gd-spot-x">x</span>
          <span class="gd-spot-num right">${{fmtStat(d.rv, d.suf)}}</span>
        </div>
        <div class="gd-balance">
          <div class="gd-bal-half left"><span class="gd-bal-fill" style="width:${{d.lpct}}%"></span></div>
          <div class="gd-bal-half right"><span class="gd-bal-fill" style="width:${{d.rpct}}%"></span></div>
        </div>
      </div>`;
    }};
    const miniStat = (label) => {{
      const s = statByLabel(label);
      if (!s) return '';
      const d = sideVals(s);
      return `<div class="gd-mini-stat">
        <div class="gd-mini-label">${{label}}</div>
        <div class="gd-mini-values">
          <span class="gd-mini-v left">${{fmtStat(d.lv, d.suf)}}</span>
          <span class="gd-mini-sep">x</span>
          <span class="gd-mini-v right">${{fmtStat(d.rv, d.suf)}}</span>
        </div>
      </div>`;
    }};
    const spotlight = [
      spotlightCard('Posse de bola', 'Posse de bola'),
      spotlightCard('Finalizações', 'Finalizações'),
      spotlightCard('Precisão de passe', 'Precisão de passe'),
    ].join('');
    const compactStats = ['No alvo', 'Escanteios', 'Faltas', 'Impedimentos'].map(miniStat).join('');
    content = `<div class="gd-stats-board">
      <div class="gd-stat-legend">
        <div class="gd-side-key left"><b>${{leftName}}</b><span>${{leftFlag}}</span></div>
        <span class="gd-axis-dot"></span>
        <div class="gd-side-key right"><span>${{rightFlag}}</span><b>${{rightName}}</b></div>
      </div>
      <div class="gd-spotlight">${{spotlight}}</div>
      <div class="gd-mini-grid">${{compactStats}}</div>
    </div>`;
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
    const names = e.hl_names || (e.hl_name ? [e.hl_name] : []);
    const clickable = names.length > 0;          // qualquer evento com jogador (os 2 times)
    const payload = JSON.stringify(names).replace(/"/g, '&quot;');
    const cls = `gd-ev ${{e.mine ? 'mine' : 'opp'}}${{clickable ? ' clickable' : ''}}`;
    const oc = clickable ? ` onclick="showPlayerCards(${{payload}}, this)"` : '';
    return `<div class="${{cls}}"${{oc}}>
      <span class="gd-min">${{e.minute}}'</span><span class="gd-sym">${{e.sym}}</span>
      <span class="gd-evp">${{e.player || ''}}${{e.team ? ` <span class="md-game-meta">(${{e.team}})</span>` : ''}}</span>
    </div>`;
  }}).join('');
}}

// lista de reservas (clicável p/ destacar a troca)
// helper de destaque: o jogador clicado + o par da troca (em qualquer dos dois times)
function _mkIsHi(allPlayers) {{
  return (nm) => openPlayerCards.has(nm) || (highlightedPlayer && (
    nm === highlightedPlayer
    || (allPlayers.find(x => x.name === highlightedPlayer) || {{}}).sub_with === nm
  ));
}}

// lista de reservas de um time (clicável p/ destacar a troca)
function _subsListHtml(subs, isHi) {{
  const esc = (s) => (s || '').replace(/'/g, "\\\\'");
  if (!subs || !subs.length) return '<div class="md-empty">—</div>';
  return `<div class="md-xi subs">${{subs.map(p => {{
    const cls = `pl${{p.entered ? ' used' : ''}}${{isHi(p.name) ? ' hi' : ''}} clickable`;
    const oc = ` onclick="showPlayerCard('${{esc(p.name)}}', this)"`;
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
  const cards = allPlayers
    .filter(p => openPlayerCards.has(p.name))
    .map(p => _playerCardHtml(p, 'above', 'c'))
    .join('');
  // cabeçalho na mesma orientação do campo: mandante à esquerda, visitante à direita.
  // O time visto mantém a cor (lv1-home/vermelho); só troca de lado se jogou fora.
  const seenHead = `<span class="lv1-home">${{homeFlag}} <b>${{modalTeam}}</b> ${{g.formation ? `<span class="pitch-form-inline">${{g.formation}}</span>` : ''}}</span>`;
  const oppHead = `<span class="lv1-away">${{g.opp_formation ? `<span class="pitch-form-inline">${{g.opp_formation}}</span>` : ''}} <b>${{g.opp}}</b> ${{g.opp_flag}}</span>`;
  const headHtml = g.home ? (seenHead + oppHead) : (oppHead + seenHead);
  return `<div class="lv1">
    <div class="lv1-center">
      <div class="lv1-head">
        ${{headHtml}}
      </div>
      ${{renderPitch(g.pitch, g.opp_pitch, isHi, allPlayers, g.home)}}
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
    ${{cards}}
  </div>`;
}}

// UM campo HORIZONTAL com os dois times. Time visto na metade esquerda (gol à esq,
// ataca p/ centro); adversário na metade direita, espelhado (gol à dir).
// coords originais por jogador: x=lado (0..100), y=profundidade (8=gol..92=ataque).
function renderPitch(homePitch, awayPitch, isHi, allPlayers = [], isHomeGame = true) {{
  const splitName = (full) => {{
    const parts = (full || '').trim().split(/\\s+/);
    if (parts.length <= 1) return parts[0] || '';
    return `${{parts[0]}}<br>${{parts.slice(1).join(' ')}}`;
  }};
  const dimmed = (highlightedPlayer || openPlayerCards.size) ? ' dim-others' : '';
  const esc = (s) => (s || '').replace(/'/g, "\\\\'");
  const cardMark = (p) => p.card ? `<span class="pl-card ${{p.card}}"></span>` : '';
  const goalMark = (p) => p.goals ? `<span class="pl-goal-mark">⚽${{p.goals > 1 ? `<b>${{p.goals}}</b>` : ''}}</span>` : '';
  const playerByName = Object.fromEntries((allPlayers || []).filter(p => p && p.name).map(p => [p.name, p]));

  // horizontal: profundidade (y) → eixo X; lado (x) → eixo Y (top).
  // `who` é a COR (home=seleção vista/vermelho, away=adversário/azul); `side` é o
  // LADO físico do campo ('left'/'right'), orientado pelo mando real do confronto:
  // o mandante sempre ocupa a metade esquerda (gol à esq), o visitante a direita.
  const dot = (p, who, side) => {{
    const partner = p.sub_with ? playerByName[p.sub_with] : null;
    const pairKey = partner ? _subPairKey(p.name, partner.name) : '';
    const activeName = partner ? (fieldSubOverrides[pairKey] || p.name) : p.name;
    const visible = partner && activeName === partner.name ? {{ ...partner, x: p.x, y: p.y, sub_slot_from: p.name }} : p;
    const half = (p.y / 100) * 46;
    const left = side === 'left' ? (2 + half) : (98 - half);
    const top = p.x;
    const visibleEsc = esc(visible.name);
    const aEsc = esc(p.name);
    const bEsc = partner ? esc(partner.name) : '';
    const toggle = partner
      ? `<button class="pitch-sub-toggle" title="Alternar substituição" onclick="event.stopPropagation();togglePitchSub('${{aEsc}}','${{bEsc}}', this.closest('.pitch-player'))">↔</button>`
      : '';
    const minuteBadge = visible.exited
      ? `<span class="sub-out">↓${{visible.exited}}'</span>`
      : visible.entered ? `<span class="sub-in-field">↑${{visible.entered}}'</span>` : '';
    // todo jogador é clicável → abre o card de dados (e destaca a troca, se houver)
    const cls = `pitch-player ${{who}} clickable${{visible.exited ? ' subbed-out' : ''}}${{isHi(visible.name) ? ' hi' : ''}}`;
    return `<div class="${{cls}}" style="left:${{left}}%;top:${{top}}%" onclick="showPlayerCard('${{visibleEsc}}', this)">
      <div class="pitch-shirt">${{visible.num ?? ''}}${{cardMark(visible)}}${{goalMark(visible)}}${{minuteBadge}}${{toggle}}</div>
      <div class="pitch-name">${{splitName(visible.name)}}</div>
    </div>`;
  }};
  // homePitch é sempre a seleção VISTA (cor home/vermelho), awayPitch o adversário.
  // Se a seleção vista jogou em casa, ela fica à esquerda; se jogou fora, à direita.
  const seenSide = isHomeGame ? 'left' : 'right';
  const oppSide = isHomeGame ? 'right' : 'left';
  const dots = (homePitch || []).map(p => dot(p, 'home', seenSide)).join('')
    + (awayPitch || []).map(p => dot(p, 'away', oppSide)).join('');
  // marcações horizontais: meio (vertical), círculo, áreas/gols nas laterais
  const lines = `<div class="pitch-lines">
    <div class="pl-line plh-half"></div>
    <div class="pl-line pl-circle"></div>
    <div class="pl-line pl-spot"></div>
    <div class="pl-line plh-box left"></div><div class="pl-line plh-box-s left"></div><div class="pl-goal-h left"></div>
    <div class="pl-line plh-box right"></div><div class="pl-line plh-box-s right"></div><div class="pl-goal-h right"></div>
  </div>`;
  const hasCard = openPlayerCards.size ? ' has-card' : '';
  return `<div class="pitch-h pitch-vs${{dimmed}}${{hasCard}}">${{lines}}${{dots}}</div>`;
}}

// cor da nota de atuação (365scores, ~3-10): vermelho fraco → verde destaque
function _ratingColor(v) {{
  if (v == null) return '#8b949e';
  if (v >= 7.5) return '#3fb950';
  if (v >= 6.8) return '#7bc96f';
  if (v >= 6.2) return '#d29922';
  return '#e0795b';
}}

function _scoreColor(v) {{
  if (v == null) return '#8b949e';
  const t = Math.max(0, Math.min(1, v / 100));
  const r = Math.round(0xea + (0x22 - 0xea) * t);
  const g = Math.round(0x55 + (0xc5 - 0x55) * t);
  const b = Math.round(0x44 + (0x5e - 0x44) * t);
  return `rgb(${{r}},${{g}},${{b}})`;
}}

// Aba "Estilo": flag em destaque + 4 eixos, cada um com seus próprios
// ingredientes logo abaixo (conecta o número à causa). Frase curta de uma
// linha explicando, por extenso, o que a classificação significou.
const ESTILO_GLOSSARIO = {{
  'Toque e Posse':       'domina a bola e constrói tocando, com paciência',
  'Ofensivo':            'pressão ofensiva constante, muito volume de finalização',
  'Drible e Individual': 'cria pelo talento individual: dribles e jogadas de meio',
  'Defensivo':           'bloco baixo, abre mão da bola e segura o resultado',
  'Contra-ataque':       'pouca posse, mas vertical e letal na transição',
  'Jogo pelas Pontas':   'ataca pelos lados, com muitos cruzamentos',
  'Pressão Alta':        'recupera a bola alto, no campo do adversário',
  'Equilibrado':         'sem um traço dominante claro — perfil versátil',
}};

// Rótulos amigáveis + sufixo das métricas brutas usadas pelos arquétipos.
const ESTILO_METRIC_LABELS = {{
  posse:        ['Posse média', '%'],
  passes:       ['Passes/jogo', ''],
  precisao:     ['Precisão de passe', '%'],
  gols:         ['Gols/jogo', ''],
  no_alvo:      ['Chutes no alvo/jogo', ''],
  chutes:       ['Chutes/jogo', ''],
  dribles:      ['Dribles/jogo', ''],
  key_passes:   ['Passes-chave/jogo', ''],
  cruzamentos:  ['Cruzamentos certos/jogo', ''],
  clearances:   ['Cortes/jogo', ''],
  verticalidade:['Verticalidade (eixo)', ''],
  pressao:      ['Pressão (eixo)', ''],
}};
const ARCHETYPE_ORDER = ['Toque e Posse','Ofensivo','Drible e Individual','Defensivo','Contra-ataque','Jogo pelas Pontas','Pressão Alta'];

// Estado: qual arquétipo está selecionado no dropdown da aba Estilo.
let estiloArqSel = null;

// Uma linha "valor / meta" com barra de progresso colorida pelo score (0-1) +
// uma frase DESCRITIVA do que a meta significa (não é regra, é o padrão do estilo).
function styleMetricRow(item) {{
  const [lbl, suf] = ESTILO_METRIC_LABELS[item.metrica] || [item.metrica, ''];
  const pct = Math.round((item.score || 0) * 100);
  // verde = tem o perfil (≥85%), amarelo = perto (≥55%), vermelho = vai contra
  const cor = pct >= 85 ? '#3fb950' : pct >= 55 ? '#d29922' : '#f85149';
  const icone = pct >= 85 ? '✅' : pct >= 55 ? '⚠️' : '❌';
  const mais = item.direcao !== 'menos';
  const alvo = mais ? `≥${{item.meta}}` : `≤${{item.meta}}`;
  // frase: "este estilo costuma ter MUITOS/POUCOS X (~meta); o time tem VALOR"
  const qtd = mais ? 'bastante' : 'pouco';
  const desc = `times deste estilo têm ${{qtd}} (~${{item.meta}}${{suf}}); este time tem ${{item.valor}}${{suf}}`;
  return `<div class="es-mm">
    <div class="es-mm-head">
      <span class="es-mm-lbl">${{lbl}}</span>
      <span class="es-mm-vals"><b>${{item.valor}}${{suf}}</b> <span class="es-mm-sep">·</span> meta <span class="es-mm-meta">${{alvo}}${{suf}}</span> ${{icone}}</span>
    </div>
    <div class="es-mm-bar"><span class="es-mm-fill" style="width:${{pct}}%;background:${{cor}}"></span></div>
    <div class="es-mm-desc">${{desc}}</div>
  </div>`;
}}

// Render do bloco "ver como estilo X": afinidade + métricas valor/meta.
function renderArchetypeDetail(e) {{
  const af = e.afinidades || {{}};
  const det = e.detalhe || {{}};
  const arq = estiloArqSel || e.flag;
  const afin = af[arq];
  const items = det[arq] || [];
  const isFlag = arq === e.flag;
  const metricsHtml = items.map(styleMetricRow).join('') || '<div class="es-na">sem métricas com cobertura</div>';
  const afinPct = afin !== undefined ? afin.toFixed(0) : '—';
  return `<div class="es-arq-detail">
    <div class="es-arq-bar-row">
      <span class="es-arq-afin-lbl">Encaixe neste estilo</span>
      <span class="es-arq-afin-val">${{afinPct}}%</span>
    </div>
    <div class="es-arq-bar"><span class="es-arq-bar-fill" style="width:${{afin || 0}}%"></span></div>
    <div class="es-arq-gloss">${{ESTILO_GLOSSARIO[arq] || ''}}${{isFlag ? ' <span class="es-arq-isflag">· estilo do time</span>' : ''}}</div>
    <div class="es-am-title">Métricas deste estilo — valor do time / meta ideal</div>
    <div class="es-mm-grid">${{metricsHtml}}</div>
  </div>`;
}}

// Troca o arquétipo selecionado, re-renderiza o detalhe e realça a barra
// correspondente no gráfico de perfil (liga "o que detalho" a "onde está").
function selectArquetipo(arq) {{
  estiloArqSel = arq;
  const host = document.getElementById('esArqDetail');
  const d = teamDetailAt(modalTeam, currentJogo);
  if (host && d) host.innerHTML = renderArchetypeDetail(d.estilo);
  document.querySelectorAll('.es-perfil-row').forEach(r =>
    r.classList.toggle('sel', r.dataset.arq === arq));
}}

function renderEstiloSection(e, nJogos) {{
  if (!e || !e.flag) {{
    return '<div class="md-empty">Estilo ainda não disponível (sem jogos processados).</div>';
  }}
  const af = e.afinidades || {{}};
  const glos = ESTILO_GLOSSARIO[e.flag] || '';
  const aviso = nJogos < 3
    ? `<div class="es-aviso">⏳ Assinatura provisória — baseada em ${{nJogos}} jogo${{nJogos !== 1 ? 's' : ''}}. Reflete o que o time FEZ até agora, não a fama; se firma conforme o torneio avança.</div>`
    : '';

  // Arquétipos ordenados por afinidade. Default = a flag; clique nas barras troca o detalhe.
  estiloArqSel = e.flag;
  const ordenados = ARCHETYPE_ORDER.slice().sort((a, b) => (af[b] || 0) - (af[a] || 0));

  // gráfico de afinidade aos 7 arquétipos (substitui os antigos 4 eixos):
  // mostra o perfil completo de uma vez, o estilo do time em destaque.
  const perfilHtml = ordenados.map(arq => {{
    const v = af[arq];
    if (v === undefined) return '';
    const isFlag = arq === e.flag;
    // a barra começa selecionada no estilo do time (= o que o detalhe mostra).
    const isSel = arq === estiloArqSel;
    const cor = isFlag ? '#58a6ff' : '#3a4a63';
    return `<div class="es-perfil-row${{isFlag ? ' flag' : ''}}${{isSel ? ' sel' : ''}}" data-arq="${{arq}}" onclick="selectArquetipo('${{arq.replace(/'/g, "\\\\'")}}')">
      <span class="es-perfil-nome">${{arq}}${{isFlag ? ' <span class="es-perfil-tag">estilo do time</span>' : ''}}</span>
      <div class="es-perfil-bar"><span class="es-perfil-fill" style="width:${{v}}%;background:${{cor}}"></span></div>
      <span class="es-perfil-val">${{v.toFixed(0)}}%</span>
    </div>`;
  }}).join('');

  return `<div class="es-tab">
    <div class="es-hero">
      <div class="es-hero-flag">🎭</div>
      <div class="es-hero-info">
        <div class="es-hero-nome">${{e.flag}}</div>
        ${{glos ? `<div class="es-hero-glos">${{glos}}</div>` : ''}}
      </div>
    </div>
    <div class="es-help">A flag é o <b>arquétipo de estilo</b> que mais combina com as estatísticas do time. O perfil abaixo mostra o quanto o time se encaixa em <b>cada um dos estilos</b>.</div>
    <div class="es-perfil-title">Perfil de estilo — encaixe em cada arquétipo</div>
    <div class="es-perfil">${{perfilHtml}}</div>
    <div id="esArqDetail">${{renderArchetypeDetail(e)}}</div>
    ${{aviso}}
  </div>`;
}}

// Compat antigo: clicar numa barra detalha aquele estilo.
function selectArquetipoDropdown(arq) {{
  selectArquetipo(arq);
}}

function renderModalBody() {{
  const d = teamDetailAt(modalTeam, currentJogo);
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

  if (modalTab === 'estilo') {{
    body.innerHTML = renderEstiloSection(d.estilo, d.n_jogos);
    return;
  }}

  if (modalTab === 'jogos') {{
    if (!d.jogos || !d.jogos.length) {{ body.innerHTML = '<div class="md-empty">Nenhum jogo cadastrado ainda.</div>'; return; }}
    const myFlag = d.flag || '🏳️';
    // mandante sempre à esquerda, visitante à direita (ordem real do confronto).
    // A seleção sendo vista (modalTeam) fica em negrito destacado.
    const sideHtml = (team, flag, mine, side) => {{
      const cls = `mg-side ${{side}}${{mine ? ' me' : ''}}`;
      return side === 'left'
        ? `<span class="${{cls}}"><b>${{team}}</b> ${{flag}}</span>`
        : `<span class="${{cls}}">${{flag}} <b>${{team}}</b></span>`;
    }};

    const cardHtml = (g) => {{
      const i = d.jogos.indexOf(g);
      const homeIsMe = g.home_team === modalTeam;
      const left = sideHtml(g.home_team, g.home_flag, homeIsMe, 'left');
      const right = sideHtml(g.away_team, g.away_flag, !homeIsMe, 'right');
      if (!g.finalizado) {{
        // próximo jogo: não clicável, sem placar
        return `<div class="mg scheduled">
          <div class="mg-head">
            <span class="mg-match">
              ${{left}}
              <span class="mg-score res-next">×</span>
              ${{right}}
            </span>
            <span class="mg-date">${{g.date}}</span>
          </div>
        </div>`;
      }}
      const placar = (g.home_score != null && g.away_score != null) ? `${{g.home_score}} x ${{g.away_score}}` : '—';
      const open = (expandedGame === i);
      return `<div class="mg ${{open ? 'open' : ''}}" data-gi="${{i}}">
        <div class="mg-head" onclick="toggleGame(${{i}})">
          <span class="mg-match">
            ${{left}}
            <span class="mg-score res-${{g.res}}">${{placar}}</span>
            ${{right}}
          </span>
          <span class="mg-date">${{g.date}}</span>
          <span class="mg-chevron">${{open ? '▲' : '▼'}}</span>
        </div>
        ${{open ? `<div class="mg-detail">${{renderGameDetail(g)}}</div>` : ''}}
      </div>`;
    }};

    body.innerHTML = d.jogos.map(cardHtml).join('');
    return;
  }}

  if (modalTab === 'elenco') {{
    if (!d.players || !d.players.length) {{ body.innerHTML = '<div class="md-empty">Sem dados de jogadores.</div>'; return; }}
    const players = d.players || [];
    const rosterPlayers = players.filter(p => p.in_roster !== false);
    const extraPlayers = players.filter(p => p.in_roster === false);
    const val = (p, k) => p[k] == null ? 0 : Number(p[k] || 0);
    const fmt = (v, digits = 0) => {{
      if (v == null || !Number.isFinite(Number(v))) return '—';
      return digits ? Number(v).toFixed(digits) : String(Math.round(Number(v)));
    }};
    const impact = (p) => (
      val(p, 'gols') * 7 + val(p, 'assist') * 5 + val(p, 'xg') * 2.5 + val(p, 'xa') * 2.5 +
      val(p, 'no_alvo') * 3 + val(p, 'passes_chave') * 1.2 + val(p, 'defesas') * 4 +
      val(p, 'xgp') * 3 + val(p, 'desarmes') * 1.2 + val(p, 'interceptacoes') +
      val(p, 'recuperacoes') * 0.7 + val(p, 'rating_media') * 0.8
    );
    const sortPlayer = (a, b) => (a.pos_order ?? 99) - (b.pos_order ?? 99) || impact(b) - impact(a) || val(b, 'jogos') - val(a, 'jogos') || _esc(a.name).localeCompare(_esc(b.name));
    const active = rosterPlayers.filter(p => val(p, 'jogos') > 0).sort(sortPlayer);
    const unused = rosterPlayers.filter(p => val(p, 'jogos') <= 0).sort(sortPlayer);
    const extras = extraPlayers.sort(sortPlayer);
    const posGroups = ['Goleiros', 'Defensores', 'Meias', 'Atacantes', 'Sem posição'];
    const topBy = (key) => {{
      const ranked = rosterPlayers.filter(p => val(p, key) > 0).sort((a, b) => val(b, key) - val(a, key) || impact(b) - impact(a));
      return ranked[0] || null;
    }};
    const leader = (label, key, digits = 0) => {{
      const p = topBy(key);
      return `<div class="el-leader">
        <div class="el-leader-label">${{label}}</div>
        <div class="el-leader-main">
          <span class="el-leader-val">${{p ? fmt(val(p, key), digits) : '—'}}</span>
          <span class="el-leader-name">${{p ? _esc(p.name) : 'sem registro'}}</span>
        </div>
      </div>`;
    }};
    const stat = (label, value, cls = '') => `<span class="el-stat ${{cls}}"><b>${{value}}</b><span>${{label}}</span></span>`;
    const displayRosterPos = (p) => {{
      const pos = p.pos && p.pos !== '—' ? p.pos : '';
      const group = p.pos_group || '';
      const generic = {{
        'Goleiros': 'Goleiro',
        'Defensores': 'Defensor',
        'Meias': 'Meia',
        'Atacantes': 'Atacante',
        'Sem posição': '',
      }};
      return pos && generic[group] !== pos ? pos : '';
    }};
    const marks = (p) => [
      val(p, 'gols') ? `<span class="el-mark goal">⚽ ${{val(p, 'gols')}}</span>` : '',
      val(p, 'amarelos') ? `<span class="el-mark"><span class="el-card-dot yellow"></span>${{val(p, 'amarelos')}}</span>` : '',
      val(p, 'vermelhos') ? `<span class="el-mark"><span class="el-card-dot red"></span>${{val(p, 'vermelhos')}}</span>` : '',
    ].filter(Boolean).join('');
    const playerCard = (p) => {{
      const pos = displayRosterPos(p);
      const num = p.num ?? '—';
      const nameEscAttr = (p.name || '').replace(/'/g, "\\\\'");
      const isOpen = openRosterCards.has(p.name);
      return `<div class="el-player${{isOpen ? ' open' : ''}}" onclick="showRosterPlayer('${{nameEscAttr}}', this)">
        <div class="el-player-top">
          ${{_kitShirtHtml(num, modalTeam, 'el-shirt')}}
          <div class="el-player-id">
            <span class="el-name">${{_esc(p.name)}}</span>
            ${{pos ? `<span class="el-pos-label">${{_esc(pos)}}</span>` : ''}}
          </div>
          <div class="el-marks">${{marks(p)}}</div>
        </div>
        ${{isOpen ? _rosterPlayerCardHtml(p) : ''}}
      </div>`;
    }};
    const activeGroup = (group) => {{
      const items = active.filter(p => (p.pos_group || 'Sem posição') === group);
      if (!items.length) return '';
      return `<div class="el-pos-group">
        <div class="el-pos-head">${{group}} <span class="el-pos-count">· ${{items.length}}</span></div>
        <div class="el-player-grid">${{items.map(playerCard).join('')}}</div>
      </div>`;
    }};
    const unusedGroup = (group) => {{
      const items = unused.filter(p => (p.pos_group || 'Sem posição') === group);
      if (!items.length) return '';
      return `<div class="el-unused-group">
        <div class="el-unused-head">${{group}} · ${{items.length}}</div>
        <div class="el-unused-list">${{items.map(p => `<span class="el-unused-chip">${{_kitShirtHtml(p.num, modalTeam, 'pc-shirt')}}<span>${{_esc(p.name)}}</span></span>`).join('')}}</div>
      </div>`;
    }};
    const extraHtml = extras.length ? `<div class="el-extra">
      <div class="el-section-title">Dados de jogo fora do roster · ${{extras.length}}</div>
      <div class="el-extra-note">Aparecem em estatísticas/escalação, mas não no elenco oficial da ESPN usado para a contagem.</div>
      <div class="el-player-grid">${{extras.map(playerCard).join('')}}</div>
    </div>` : '';
    const leaders = [
      leader('Gols', 'gols'),
      leader('xG', 'xg', 2),
      leader('xA', 'xa', 2),
      leader('Passes-chave', 'passes_chave'),
      leader('Desarmes', 'desarmes'),
      leader('Nota média', 'rating_media', 1),
      leader('xGP', 'xgp', 2),
      leader('Defesas', 'defesas'),
    ].join('');
    body.innerHTML = `<div class="el-board">
      <div class="el-leaders">${{leaders}}</div>
      ${{active.length ? `<div class="el-section-title">Entraram em campo · ${{active.length}}</div>${{posGroups.map(activeGroup).join('')}}` : ''}}
      ${{unused.length ? `<div class="el-unused"><div class="el-section-title">Ainda não jogaram · ${{unused.length}}</div>${{posGroups.map(unusedGroup).join('')}}</div>` : ''}}
      ${{extraHtml}}
    </div>`;
    return;
  }}

}}

// popula os selects de filtro compartilhados já no boot (a barra é visível nas
// duas abas, então não dá para esperar entrar na aba Seleções).
initTeamsControls();
_teamsInit = true;
goToJogo(jogos[jogos.length - 1]);
</script>
</body>
</html>"""

OUTPUT.write_text(html, encoding="utf-8")
print(f"Gerado: {OUTPUT}")
