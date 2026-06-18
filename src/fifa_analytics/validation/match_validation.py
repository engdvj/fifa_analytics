from typing import Any

import pandas as pd

# Fontes OPERACIONAIS — só elas bloqueiam a porta de qualidade. A wikipedia é
# referência pública e fica defasada por natureza (não deve travar o pipeline).
_PRIMARY_SOURCES = ("worldcup2026", "espn")


def validate_match_completeness(
    match: pd.Series,
    source_map: pd.DataFrame,
    events: pd.DataFrame,
    team_stats: pd.DataFrame,
    player_stats: pd.DataFrame,
    lineups: pd.DataFrame | None = None,
) -> list[str]:
    """Porta de qualidade de UM jogo finalizado: retorna a lista de ERROS que
    impedem o processamento. Lista vazia = jogo íntegro, pronto para virar
    snapshot/relatório.

    Valida TODAS as dimensões (não só o placar), porque dado incompleto quebra
    depois — narrativa, scores, estatísticas. As checagens:
      1. placar presente (home/away_score não nulos)
      2. status entre fontes: nenhuma fonte ainda em 'ao_vivo'/'agendado' para um
         jogo dito finalizado (caso clássico: ESPN defasada em ao_vivo)
      3. placar concorda entre as fontes que reportam o jogo
      4. eventos: nº de gols nos eventos == soma do placar
      5. estatísticas de time presentes para os 2 times
      6. estatísticas de jogador presentes
      7. lineups presentes (se a fonte foi passada)
    """
    mid = match.get("canonical_match_id") or match.get("match_id")
    errors: list[str] = []

    hs, as_ = match.get("home_score"), match.get("away_score")
    if pd.isna(hs) or pd.isna(as_):
        errors.append("placar ausente no índice canônico")
        return errors  # sem placar, o resto não faz sentido validar
    hs, as_ = int(hs), int(as_)
    total_gols = hs + as_

    # 2 + 3) coerência entre fontes PRIMÁRIAS (status e placar). Só worldcup2026
    # e espn bloqueiam — são as fontes operacionais. A wikipedia é referência e
    # fica sempre atrasada (ela ficaria 'agendado' o tempo todo); travar por ela
    # bloquearia quase tudo, então não entra na porta de qualidade.
    if not source_map.empty:
        rows = source_map[
            (source_map["canonical_match_id"] == mid)
            & (source_map["source"].isin(_PRIMARY_SOURCES))
        ]
        live = rows[rows["status"].isin(["ao_vivo", "agendado"])]
        if not live.empty:
            fontes = ", ".join(f"{r['source']}={r['status']}" for _, r in live.iterrows())
            errors.append(f"fonte primária ainda não finalizada: {fontes} (coleta defasada)")
        # placar divergente entre as fontes primárias que TÊM placar
        scored = rows.dropna(subset=["home_score", "away_score"])
        placares = {(int(r["home_score"]), int(r["away_score"])) for _, r in scored.iterrows()}
        if len(placares) > 1:
            errors.append(f"placar diverge entre fontes primárias: {sorted(placares)}")

    # 4) gols nos eventos == placar
    ev = events[events["match_id"] == mid] if not events.empty else events
    n_gols = int(ev["event_type"].astype(str).str.contains("gol", na=False).sum()) if not ev.empty else 0
    if n_gols != total_gols:
        errors.append(f"eventos têm {n_gols} gol(s), placar soma {total_gols}")

    # 5) team stats para os 2 times
    ts = team_stats[team_stats["match_id"] == mid] if not team_stats.empty else team_stats
    if len(ts) < 2:
        errors.append(f"estatísticas de time incompletas ({len(ts)}/2 times)")

    # 6) player stats presentes
    ps = player_stats[player_stats["match_id"] == mid] if not player_stats.empty else player_stats
    if ps.empty:
        errors.append("estatísticas de jogador ausentes")

    # 7) lineups (opcional)
    if lineups is not None and not lineups.empty:
        lu = lineups[lineups["match_id"] == mid]
        if lu.empty:
            errors.append("escalações ausentes")

    return errors


def compare_match_records(primary: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for field in ["home_score", "away_score", "status", "stadium"]:
        primary_value = primary.get(field)
        reference_value = reference.get(field)
        if primary_value is None or reference_value is None:
            status = "ausente"
        elif primary_value == reference_value:
            status = "ok"
        else:
            status = "aviso"
        checks.append(
            {
                "field": field,
                "primary": primary_value,
                "reference": reference_value,
                "status": status,
            }
        )

    overall = "ok"
    if any(check["status"] == "aviso" for check in checks):
        overall = "aviso"
    if any(check["status"] == "ausente" for check in checks):
        overall = "ausente" if overall == "ok" else overall

    return {"status": overall, "checks": checks}
