"""Análise Diagnóstica — *por que* cada resultado aconteceu.

Primeira das seis camadas de análise da plataforma (Descritiva → Exploratória →
**Diagnóstica** → Preditiva → Prescritiva → Preventiva). Lê o gold já coletado
(`team_match_wide` + `dim_match`) e, quando disponível, o `snapshot_timeline`
(força do adversário no momento do confronto), e produz ACHADOS estruturados e
auditáveis por jogo finalizado.

Os achados são organizados no padrão de análise jornalística dos grandes veículos
(ESPN, The Athletic, FotMob, Sofascore):
  - um **veredito** do jogo (resumo + leitura do resultado vs. xG);
  - por seleção, **destaques** (`direcao=positivo`) e **pontos fracos**
    (`direcao=negativo`), cada um numa **categoria** (Ataque, Defesa, Controle,
    Eficiência, Goleiro, Disciplina, Físico, Contexto).

Cada achado carrega a EVIDÊNCIA numérica que o sustenta. A camada de prosa (skill
`analisar-snapshot`) e a aba Analytics consomem este artefato.

Saída: ``data/gold/analytics/insights/fact_insights.parquet`` (long, um achado por
linha; todas as camadas reusam o arquivo, discriminadas por ``tipo_analise``).
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from fifa_analytics.paths import GOLD_DIR
from fifa_analytics.utils.io import write_dataframe
from fifa_analytics.utils.logging import get_logger

logger = get_logger(__name__)

INSIGHTS_DIR = GOLD_DIR / "analytics" / "insights"
INSIGHTS_PATH = INSIGHTS_DIR / "fact_insights.parquet"

TIPO = "diagnostica"

# Colunas do artefato (ordem estável para o parquet e o JSON da API).
INSIGHT_COLUMNS = [
    "snapshot", "match_id", "match_number", "escopo",
    "team", "adversario", "tipo_analise", "categoria",
    "achado_key", "titulo", "detalhe",
    "direcao", "severidade", "evidencia",
]

# --- Limiares (julgamento de design, documentados) --------------------------
_XG_MIN_RELEVANTE = 0.8       # abaixo disso o xG é ruído
_XG_DIFF_RELEVANTE = 0.6      # diferença de xG digna de nota
_RATIO_CLINICO = 1.5          # gols/xG: converteu acima do esperado
_RATIO_DESPERDICIO = 0.55     # criou e não aproveitou
_XG_ATAQUE_FORTE = 1.6        # criou muito perigo
_XG_ATAQUE_FRACO = 0.6        # criou pouco
_XG_DEFESA_SOLIDA = 0.7       # cedeu pouco perigo
_XG_DEFESA_FRACA = 2.0        # cedeu muito perigo
_CONTROLE_DOMINIO = 58.0      # controle no terço final (0-100)
_GK_SAVES_MIN = 4
_GK_SAVE_PCT_MIN = 0.7
_AMARELOS_INDISCIPLINA = 4
_FISICO_VANTAGEM = 1.15       # 15%+ de sprints/distância que o adversário
_RANK_TOP = 8                 # adversário forte (ranking de score_geral)


def _f(row: dict[str, Any] | pd.Series | None, col: str, default: float = float("nan")) -> float:
    """Extrai um float de uma linha (NaN-safe)."""
    if row is None:
        return default
    try:
        v = float(row[col]) if col in row and row[col] is not None else default
    except (TypeError, ValueError, KeyError):
        return default
    return default if (isinstance(v, float) and np.isnan(v)) else v


def _round(v: float) -> float | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return round(float(v), 2)


def _finding(
    *, snapshot: int, match_id: str, match_number: Any, team: str, adversario: str,
    categoria: str, achado_key: str, titulo: str, detalhe: str, direcao: str,
    severidade: str, evidencia: dict[str, Any], escopo: str = "partida",
) -> dict[str, Any]:
    return {
        "snapshot": int(snapshot),
        "match_id": match_id,
        "match_number": int(match_number) if pd.notna(match_number) else None,
        "escopo": escopo,
        "team": team,
        "adversario": adversario,
        "tipo_analise": TIPO,
        "categoria": categoria,
        "achado_key": achado_key,
        "titulo": titulo,
        "detalhe": detalhe,
        "direcao": direcao,
        "severidade": severidade,
        "evidencia": json.dumps(evidencia, ensure_ascii=False),
    }


def _rank_lookup(timeline: pd.DataFrame | None) -> dict[tuple[int, str], int]:
    """(snapshot_jogo, team) -> ranking_score_geral contemporâneo."""
    if timeline is None or timeline.empty:
        return {}
    needed = {"snapshot_jogo", "team", "ranking_score_geral"}
    if not needed.issubset(timeline.columns):
        return {}
    out: dict[tuple[int, str], int] = {}
    for r in timeline.itertuples():
        try:
            out[(int(r.snapshot_jogo), str(r.team))] = int(r.ranking_score_geral)
        except (TypeError, ValueError):
            continue
    return out


def _team_findings(
    *, snapshot: int, mid: str, mnum: Any, team: str, opp: str,
    me: pd.Series | None, op: pd.Series | None, gols: float, gols_contra: float,
    venceu: bool | None,
) -> list[dict[str, Any]]:
    """Destaques (positivo) e pontos fracos (negativo) de UMA seleção no jogo,
    organizados por categoria — o miolo do bloco 'por seleção' da análise."""
    out: list[dict[str, Any]] = []

    def add(categoria, key, titulo, detalhe, direcao, severidade, ev):
        out.append(_finding(
            snapshot=snapshot, match_id=mid, match_number=mnum, team=team, adversario=opp,
            categoria=categoria, achado_key=key, titulo=titulo, detalhe=detalhe,
            direcao=direcao, severidade=severidade, evidencia=ev,
        ))

    xg = _f(me, "xg")
    xg_sofrido = _f(op, "xg")  # xG do adversário = perigo que ESTE time cedeu
    opp_ctrl = _f(op, "final_third_control")
    threat = _f(me, "threat")
    box = _f(me, "chutes_dentro_area")
    sot = _f(me, "chutes_no_alvo")
    chutes = _f(me, "chutes")
    ctrl = _f(me, "final_third_control")
    posse = _f(me, "posse")
    saves = _f(me, "defesas_goleiro")
    save_pct = _f(me, "save_pct_goleiro")
    amarelos = _f(me, "amarelos")
    vermelhos = _f(me, "vermelhos")
    sprints = _f(me, "sprints")
    sprints_op = _f(op, "sprints")
    dist = _f(me, "distancia_total_km")
    dist_op = _f(op, "distancia_total_km")

    # ── Ataque / criação de chances ─────────────────────────────────────────
    if not np.isnan(xg):
        if xg >= _XG_ATAQUE_FORTE:
            det = f"Criou muito perigo: {xg:.2f} de xG"
            if not np.isnan(box) and box > 0:
                det += f", {int(box)} finalização(ões) dentro da área"
            add("Ataque", "ataque_perigoso", "Ataque perigoso", det + ".",
                "positivo", "media" if xg < 2.5 else "alta",
                {"xg": _round(xg), "chutes_dentro_area": _round(box), "chutes_no_alvo": _round(sot)})
        elif xg <= _XG_ATAQUE_FRACO:
            add("Ataque", "ataque_apagado", "Ataque apagado",
                f"Gerou pouquíssimo perigo: apenas {xg:.2f} de xG.",
                "negativo", "media", {"xg": _round(xg)})

    # ── Eficiência / finalização ────────────────────────────────────────────
    if not np.isnan(xg) and xg >= _XG_MIN_RELEVANTE:
        ratio = gols / xg if xg > 0 else float("nan")
        if not np.isnan(ratio):
            if ratio >= _RATIO_CLINICO and gols >= 1:
                add("Eficiência", "finalizacao_clinica", "Finalização clínica",
                    f"{int(gols)} gol(s) de {xg:.2f} de xG — converteu acima do esperado.",
                    "positivo", "media" if ratio < 2.5 else "alta",
                    {"gols": int(gols), "xg": _round(xg), "gols_por_xg": _round(ratio)})
            elif ratio <= _RATIO_DESPERDICIO:
                add("Eficiência", "finalizacao_desperdicio", "Desperdício de chances",
                    f"Só {int(gols)} gol(s) com {xg:.2f} de xG — criou e não aproveitou.",
                    "negativo", "media" if xg < 2.0 else "alta",
                    {"gols": int(gols), "xg": _round(xg), "gols_por_xg": _round(ratio)})

    # ── Controle territorial ────────────────────────────────────────────────
    if not np.isnan(ctrl) and ctrl >= _CONTROLE_DOMINIO:
        if venceu is False:
            add("Controle", "dominio_esteril", "Domínio sem recompensa",
                f"Dominou o terço final ({ctrl:.0f}% de controle), mas não traduziu em resultado.",
                "negativo", "media",
                {"final_third_control": _round(ctrl), "posse": _round(posse)})
        else:
            add("Controle", "controle_jogo", "Controle do jogo",
                f"Mandou no território: {ctrl:.0f}% de controle no terço final.",
                "positivo", "baixa",
                {"final_third_control": _round(ctrl), "posse": _round(posse)})
    elif venceu and not np.isnan(ctrl) and ctrl <= (100 - _CONTROLE_DOMINIO):
        add("Controle", "eficiente_sem_bola", "Eficiente sem a bola",
            f"Venceu cedendo o território ({ctrl:.0f}% de controle) — pragmatismo e transição.",
            "positivo", "baixa", {"final_third_control": _round(ctrl)})

    # ── Defesa ──────────────────────────────────────────────────────────────
    clean_sheet = gols_contra == 0
    if not np.isnan(xg_sofrido):
        if xg_sofrido <= _XG_DEFESA_SOLIDA:
            det = f"Cedeu pouco perigo: {xg_sofrido:.2f} de xG sofrido"
            det += " e não foi vazado." if clean_sheet else "."
            add("Defesa", "defesa_solida", "Defesa sólida", det,
                "positivo", "media", {"xg_sofrido": _round(xg_sofrido), "clean_sheet": clean_sheet})
        elif xg_sofrido >= _XG_DEFESA_FRACA:
            add("Defesa", "defesa_vulneravel", "Defesa exposta",
                f"Cedeu muito perigo: {xg_sofrido:.2f} de xG sofrido.",
                "negativo", "media" if xg_sofrido < 3.0 else "alta",
                {"xg_sofrido": _round(xg_sofrido)})
    elif clean_sheet:
        add("Defesa", "clean_sheet", "Não foi vazado",
            "Manteve o gol em branco.", "positivo", "baixa", {"clean_sheet": True})

    # ── Goleiro ─────────────────────────────────────────────────────────────
    if not np.isnan(saves) and saves >= _GK_SAVES_MIN and not np.isnan(save_pct) and save_pct >= _GK_SAVE_PCT_MIN:
        add("Goleiro", "goleiro_decisivo", "Goleiro decisivo",
            f"{int(saves)} defesas, {save_pct*100:.0f}% de aproveitamento — segurou o resultado.",
            "positivo", "media", {"defesas": int(saves), "save_pct": _round(save_pct)})

    # ── Disciplina ──────────────────────────────────────────────────────────
    if not np.isnan(vermelhos) and vermelhos >= 1:
        add("Disciplina", "expulsao", "Jogou com menos",
            f"{int(vermelhos)} expulsão(ões) — condicionou o jogo em desvantagem numérica.",
            "negativo", "alta", {"vermelhos": int(vermelhos)})
    elif not np.isnan(amarelos) and amarelos >= _AMARELOS_INDISCIPLINA:
        add("Disciplina", "indisciplina", "Indisciplina",
            f"{int(amarelos)} cartões amarelos — jogo no limite.",
            "negativo", "baixa", {"amarelos": int(amarelos)})

    # ── Físico ──────────────────────────────────────────────────────────────
    if not np.isnan(sprints) and not np.isnan(sprints_op) and sprints_op > 0 and sprints >= sprints_op * _FISICO_VANTAGEM:
        det = f"Mais intenso que o adversário: {int(sprints)} sprints"
        if not np.isnan(dist) and not np.isnan(dist_op):
            det += f", {dist:.1f} km percorridos"
        add("Físico", "intensidade_fisica", "Intensidade física", det + ".",
            "positivo", "baixa", {"sprints": int(sprints), "distancia_km": _round(dist)})

    # ── Garantia de cobertura ────────────────────────────────────────────────
    # Todo time fez algo no jogo: se ficou sem destaque (ou sem ponto fraco),
    # preenche com o melhor (ou pior) aspecto RELATIVO ao adversário. Evita a
    # coluna vazia "sem destaques" — sempre honesto, baseado em número real.
    has_pos = any(o["direcao"] == "positivo" for o in out)
    has_neg = any(o["direcao"] == "negativo" for o in out)

    if not has_pos:
        if not np.isnan(xg) and xg > 0 and gols >= 1 and gols / xg >= 1.2:
            add("Eficiência", "aproveitou_chances", "Aproveitou bem as chances",
                f"{int(gols)} gol(s) de {xg:.2f} de xG — rendimento acima do volume criado.",
                "positivo", "baixa", {"gols": int(gols), "xg": _round(xg)})
        elif not np.isnan(xg) and not np.isnan(xg_sofrido) and xg > xg_sofrido + 0.1:
            add("Ataque", "levou_melhor_perigo", "Criou mais perigo",
                f"Levou a melhor na criação de chances (xG {xg:.2f} a {xg_sofrido:.2f}).",
                "positivo", "baixa", {"xg": _round(xg), "xg_adversario": _round(xg_sofrido)})
        elif not np.isnan(ctrl) and not np.isnan(opp_ctrl) and ctrl > opp_ctrl:
            add("Controle", "mais_presente", "Mais presente no ataque",
                f"Esteve mais perto do gol adversário ({ctrl:.0f}% de controle no terço final).",
                "positivo", "baixa", {"final_third_control": _round(ctrl)})
        elif not np.isnan(saves) and saves >= 3:
            add("Goleiro", "goleiro_seguro", "Goleiro seguro",
                f"{int(saves)} defesas para manter a equipe viva no jogo.",
                "positivo", "baixa", {"defesas": int(saves)})
        elif not np.isnan(sprints) and not np.isnan(sprints_op) and sprints > sprints_op:
            add("Físico", "correu_mais", "Correu mais",
                f"Mais intenso fisicamente que o adversário ({int(sprints)} sprints).",
                "positivo", "baixa", {"sprints": int(sprints)})
        elif not np.isnan(chutes) and chutes > 0:
            add("Ataque", "buscou_jogo", "Buscou o jogo",
                f"Levou perigo à frente: {int(chutes)} finalização(ões) na partida.",
                "positivo", "baixa", {"chutes": int(chutes)})
        elif venceu:
            add("Eficiência", "resultado_pragmatico", "Pragmatismo no resultado",
                "Garantiu o resultado mesmo sem dominar as estatísticas.",
                "positivo", "baixa", {})

    if not has_neg:
        if not np.isnan(xg) and not np.isnan(xg_sofrido) and xg < xg_sofrido - 0.1:
            add("Ataque", "menos_perigo", "Criou menos perigo",
                f"Gerou menos perigo que o adversário (xG {xg:.2f} a {xg_sofrido:.2f}).",
                "negativo", "baixa", {"xg": _round(xg), "xg_adversario": _round(xg_sofrido)})
        elif not np.isnan(ctrl) and not np.isnan(opp_ctrl) and ctrl < opp_ctrl:
            add("Controle", "menos_presente", "Menos presença ofensiva",
                f"Ficou mais longe do ataque ({ctrl:.0f}% de controle no terço final).",
                "negativo", "baixa", {"final_third_control": _round(ctrl)})
        elif not np.isnan(amarelos) and amarelos >= 3:
            add("Disciplina", "cartoes_excesso", "Jogo no limite",
                f"{int(amarelos)} cartões amarelos.", "negativo", "baixa", {"amarelos": int(amarelos)})
        elif venceu is False:
            add("Eficiência", "sem_reacao", "Faltou reação",
                "Não encontrou meios de reagir e somar pontos.",
                "negativo", "baixa", {})

    return out


def _diagnose_match(
    *, snapshot: int, match: pd.Series, rows: dict[str, pd.Series | None],
    ranks: dict[tuple[int, str], int],
) -> list[dict[str, Any]]:
    """Todos os achados de um único jogo finalizado: veredito + por seleção."""
    mid = match["match_id"]
    mnum = match.get("match_number")
    home, away = str(match["home_team"]), str(match["away_team"])
    hs, as_ = _f(match, "home_score", 0.0), _f(match, "away_score", 0.0)
    me_home, me_away = rows.get(home), rows.get(away)
    xg = {home: _f(me_home, "xg"), away: _f(me_away, "xg")}

    findings: list[dict[str, Any]] = []

    # ── Veredito (match-level) ───────────────────────────────────────────────
    if hs > as_:
        vencedor, perdedor = home, away
    elif as_ > hs:
        vencedor, perdedor = away, home
    else:
        vencedor = perdedor = None

    placar = f"{int(hs)}–{int(as_)}"
    if vencedor is None:
        xgh, xga = xg[home], xg[away]
        if not np.isnan(xgh) and not np.isnan(xga) and abs(xgh - xga) >= _XG_DIFF_RELEVANTE:
            melhor = home if xgh > xga else away
            det = f"Equilíbrio no placar, mas {melhor} gerou mais perigo (xG {max(xgh, xga):.2f} a {min(xgh, xga):.2f})."
        else:
            det = "Jogo parelho — placar e perigo criado próximos entre os dois lados."
        findings.append(_finding(
            snapshot=snapshot, match_id=mid, match_number=mnum, team="", adversario="",
            categoria="Veredito", achado_key="resumo", titulo=f"Empate {placar}", detalhe=det,
            direcao="neutro", severidade="info",
            evidencia={"placar": placar, "xg_home": _round(xg[home]), "xg_away": _round(xg[away])}))
    else:
        xgv, xgp = xg[vencedor], xg[perdedor]
        merecida = not np.isnan(xgv) and not np.isnan(xgp) and xgv >= xgp
        if merecida and not np.isnan(xgv):
            tipo_vit, det = "vitória consistente", f"{vencedor} venceu fazendo por merecer: mais perigo criado (xG {xgv:.2f} a {xgp:.2f})."
        elif not np.isnan(xgv):
            tipo_vit, det = "vitória eficiente", f"{vencedor} venceu mesmo gerando menos perigo que {perdedor} (xG {xgv:.2f} a {xgp:.2f}) — eficiência decidiu."
        else:
            tipo_vit, det = "vitória", f"{vencedor} venceu por {placar}."
        findings.append(_finding(
            snapshot=snapshot, match_id=mid, match_number=mnum, team=vencedor, adversario=perdedor,
            categoria="Veredito", achado_key="resumo", titulo=f"{vencedor} {placar} {perdedor} — {tipo_vit}",
            detalhe=det, direcao="positivo", severidade="info",
            evidencia={"placar": placar, "vencedor": vencedor, "xg_vencedor": _round(xgv), "xg_perdedor": _round(xgp)}))

        # Resultado contra o xG (quem mereceu mais não levou).
        xgh, xga = xg[home], xg[away]
        if not np.isnan(xgh) and not np.isnan(xga):
            d_gols, d_xg = hs - as_, xgh - xga
            if abs(d_xg) >= _XG_DIFF_RELEVANTE and np.sign(d_gols) != np.sign(d_xg):
                merecedor = home if d_xg > 0 else away
                findings.append(_finding(
                    snapshot=snapshot, match_id=mid, match_number=mnum,
                    team=merecedor, adversario=(away if merecedor == home else home),
                    categoria="Veredito", achado_key="resultado_vs_xg", titulo="Resultado contrariou o xG",
                    detalhe=f"{merecedor} criou mais perigo (xG {max(xgh, xga):.2f} a {min(xgh, xga):.2f}) mas não venceu.",
                    direcao="negativo", severidade="alta" if abs(d_xg) >= 1.0 else "media",
                    evidencia={"delta_gols": int(d_gols), "delta_xg": _round(d_xg)}))

        # Contexto: bateu um adversário forte.
        if ranks:
            rk = ranks.get((snapshot, perdedor))
            if rk is not None and rk <= _RANK_TOP:
                findings.append(_finding(
                    snapshot=snapshot, match_id=mid, match_number=mnum, team=vencedor, adversario=perdedor,
                    categoria="Contexto", achado_key="vitoria_prestigio", titulo="Vitória de prestígio",
                    detalhe=f"Bateu {perdedor}, então {rk}º no ranking geral — resultado de peso.",
                    direcao="positivo", severidade="media", evidencia={"ranking_adversario": rk}))

    # ── Por seleção (destaques + pontos fracos) ──────────────────────────────
    for team, me, op, gf, ga in [(home, me_home, me_away, hs, as_), (away, me_away, me_home, as_, hs)]:
        venceu = None if vencedor is None else (team == vencedor)
        findings += _team_findings(
            snapshot=snapshot, mid=mid, mnum=mnum, team=team, opp=(away if team == home else home),
            me=me, op=op, gols=gf, gols_contra=ga, venceu=venceu)

    return findings


def build_insights(
    wide: pd.DataFrame,
    dim_match: pd.DataFrame,
    timeline: pd.DataFrame | None = None,
    *,
    write: bool = True,
) -> pd.DataFrame:
    """Gera os achados diagnósticos de todos os jogos finalizados.

    `wide` vem de `fifa.pivot.build_team_match_wide` (linha por match+team).
    `dim_match` é o calendário (resultado/status). `timeline` (opcional) é o
    `snapshot_timeline` — habilita o contexto de força do adversário. Com
    `write=True` (padrão) grava o `fact_insights.parquet`; testes usam
    `write=False`. O índice de snapshot de cada jogo é a posição cronológica
    entre os finalizados (mesma convenção de `analytics.snapshot`).
    """
    finished = dim_match[dim_match["status"] == "finalizado"].copy()
    if finished.empty:
        logger.warning("diagnostic: nenhum jogo finalizado")
        empty = pd.DataFrame(columns=INSIGHT_COLUMNS)
        if write:
            INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
            write_dataframe(INSIGHTS_PATH, empty)
        return empty

    sort_col = "date_utc" if "date_utc" in finished.columns else "match_number"
    ordered = finished.sort_values(sort_col).reset_index(drop=True)
    ranks = _rank_lookup(timeline)

    wide_idx: dict[tuple[str, str], pd.Series] = {}
    if not wide.empty:
        for r in wide.itertuples(index=False):
            wide_idx[(r.match_id, str(r.team))] = pd.Series(r._asdict())

    rows: list[dict[str, Any]] = []
    for i, match in enumerate(ordered.itertuples(index=False), start=1):
        m = pd.Series(match._asdict())
        team_rows = {
            str(m["home_team"]): wide_idx.get((m["match_id"], str(m["home_team"]))),
            str(m["away_team"]): wide_idx.get((m["match_id"], str(m["away_team"]))),
        }
        rows.extend(_diagnose_match(snapshot=i, match=m, rows=team_rows, ranks=ranks))

    df = pd.DataFrame(rows, columns=INSIGHT_COLUMNS)
    if write:
        INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        write_dataframe(INSIGHTS_PATH, df)
    logger.info("diagnostic: %d achados em %d jogos", len(df), len(ordered))
    return df
