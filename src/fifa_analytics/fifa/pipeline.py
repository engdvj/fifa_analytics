"""Pipeline FIFA: coleta -> raw -> silver -> gold -> analytics.

Fonte única FIFA. Saídas:
- raw      data/raw/fifa/<endpoint>/date=YYYYMMDD/collected_at=TS/*.json
- silver   data/silver/fifa/*.parquet
- gold     data/gold/*.parquet
- analytics data/gold/analytics/*.parquet + weights.json

Tabelas geradas:
  dim_match                        — todos os 104 jogos (calendário)
  fact_team_match_stats            — 145 métricas por time por jogo (fdh, long)
  fact_player_match_stats          — métricas por jogador por jogo (fdh, long)
  fact_lineups                     — escalações com posição tática (v3/live)
  fact_events                      — gols, cartões, substituições (v3/live)
  fact_power_ranking               — power ranking por jogador (fdh)
  analytics/team_match_wide        — pivot wide das métricas por time/jogo
  analytics/snapshot_timeline      — scores históricos jogo a jogo
  analytics/weights.json           — pesos fixos para o dashboard
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from fifa_analytics.analytics.diagnostic import build_insights
from fifa_analytics.analytics.player_snapshot import build_player_snapshots
from fifa_analytics.analytics.snapshot import build_snapshots
from fifa_analytics.fifa import client, transforms
from fifa_analytics.fifa.pivot import build_team_match_wide
from fifa_analytics.paths import GOLD_DIR, RAW_DIR, SILVER_DIR
from fifa_analytics.utils.gold_guard import prune_unknown_gold
from fifa_analytics.utils.io import write_dataframe, write_json
from fifa_analytics.utils.logging import get_logger

logger = get_logger(__name__)


def _raw_path(endpoint: str, *, ts: str, suffix: str = "") -> str:
    date = ts[:8]
    name = f"{suffix}.json" if suffix else "data.json"
    return str(RAW_DIR / "fifa" / endpoint / f"date={date}" / f"collected_at={ts}" / name)


def _concat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def run(*, only_finished: bool = True) -> dict[str, int]:
    """Executa o pipeline completo. Retorna contadores para log/CLI."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    # 1. calendário (v3) -------------------------------------------------------
    logger.info("FIFA: coletando calendário…")
    results = client.fetch_calendar_matches()
    write_json(_raw_path("calendar", ts=ts), results)

    matches = transforms.normalize_matches(results)
    finished = matches[matches["status"] == "finalizado"]
    logger.info("FIFA: %d jogos (%d finalizados)", len(matches), len(finished))

    targets = finished if only_finished else matches[matches["id_ifes"] != ""]

    # 2. por jogo: live (escalações + eventos) + player stats (fdh) -----------
    team_stats_frames: list[pd.DataFrame] = []
    player_stats_frames: list[pd.DataFrame] = []
    lineup_frames: list[pd.DataFrame] = []
    event_frames: list[pd.DataFrame] = []

    ok_team = miss_team = ok_player = miss_player = ok_live = miss_live = 0

    for row in targets.itertuples():
        # --- team stats (fdh) ---
        if row.id_ifes:
            try:
                payload = client.fetch_match_team_stats(row.id_ifes)
                write_json(_raw_path("match_team_stats", ts=ts, suffix=row.id_ifes), payload)
                team_stats_frames.append(
                    transforms.normalize_match_team_stats(row.match_id, row.id_ifes, payload)
                )
                ok_team += 1
            except client.FifaSourceError as exc:
                logger.warning("FIFA team stats: %s (%s): %s", row.match_id, row.id_ifes, exc)
                miss_team += 1

            # --- player stats (fdh) ---
            try:
                payload = client.fetch_match_player_stats(row.id_ifes)
                write_json(_raw_path("match_player_stats", ts=ts, suffix=row.id_ifes), payload)
                player_stats_frames.append(
                    transforms.normalize_match_player_stats(row.match_id, row.id_ifes, payload)
                )
                ok_player += 1
            except client.FifaSourceError as exc:
                logger.warning("FIFA player stats: %s (%s): %s", row.match_id, row.id_ifes, exc)
                miss_player += 1

        # --- live (v3): escalações + eventos ---
        if row.id_stage and row.id_match:
            try:
                live = client.fetch_match_live(row.id_stage, row.id_match)
                write_json(_raw_path("match_live", ts=ts, suffix=row.id_match), live)
                lineup_frames.append(transforms.normalize_lineups(row.match_id, live))
                event_frames.append(transforms.normalize_match_events(row.match_id, live))
                ok_live += 1
            except client.FifaSourceError as exc:
                logger.warning("FIFA live: %s (%s/%s): %s", row.match_id, row.id_stage, row.id_match, exc)
                miss_live += 1

    # 3. power ranking (fdh) — uma chamada para a temporada inteira -----------
    power_ranking = pd.DataFrame()
    try:
        pr_payload = client.fetch_power_ranking_season()
        write_json(_raw_path("power_ranking_season", ts=ts), pr_payload)
        power_ranking = transforms.normalize_power_ranking_season(pr_payload)
        logger.info("FIFA power ranking: %d jogadores", len(power_ranking))
    except client.FifaSourceError as exc:
        logger.warning("FIFA power ranking: %s", exc)

    # 4. gravar silver + gold --------------------------------------------------
    team_stats = _concat(team_stats_frames)
    player_stats = _concat(player_stats_frames)
    lineups = _concat(lineup_frames)
    events = _concat(event_frames)

    tables = {
        "dim_match.parquet": matches,
        "fact_team_match_stats.parquet": team_stats,
        "fact_player_match_stats.parquet": player_stats,
        "fact_lineups.parquet": lineups,
        "fact_events.parquet": events,
        "fact_power_ranking.parquet": power_ranking,
    }

    for base in (SILVER_DIR / "fifa", GOLD_DIR):
        for name, df in tables.items():
            if not df.empty:
                write_dataframe(base / name, df)

    # 5. pivot wide + analytics ------------------------------------------------
    wide = pd.DataFrame()
    n_snapshots = 0
    if not team_stats.empty:
        wide = build_team_match_wide(team_stats, matches)
        write_dataframe(GOLD_DIR / "analytics" / "team_match_wide.parquet", wide)
        logger.info("FIFA: team_match_wide gravado — %d linhas", len(wide))

        timeline = build_snapshots(wide, matches)
        n_snapshots = timeline["snapshot_jogo"].nunique() if not timeline.empty else 0
        logger.info("FIFA: %d snapshots gerados", n_snapshots)

        # 6. snapshot de JOGADORES (espelha o de times) ----------------------
        if not player_stats.empty:
            player_tl = build_player_snapshots(player_stats, lineups, matches, timeline, power_ranking)
            n_players = player_tl["id_player"].nunique() if not player_tl.empty else 0
            logger.info("FIFA: player_snapshot_timeline — %d jogadores", n_players)

        # 7. ANÁLISE DIAGNÓSTICA: achados do "porquê" por jogo ----------------
        insights = build_insights(wide, matches, timeline)
        logger.info("FIFA: fact_insights — %d achados diagnósticos", len(insights))

        # Nota: o AUTO-APRENDIZADO da preditiva (learn_and_save) NÃO roda aqui — é
        # disparado pelo scheduler logo após a coleta (api/app/scheduler.py),
        # como job próprio visível no histórico, para não bloquear o pipeline.
    else:
        logger.warning("FIFA: sem team_stats — pivot e snapshots pulados")

    # 8. guard anti-stale: remove parquets antigos fora do conjunto canônico
    # (caminhos que mudaram, legado, duplicatas) para o gold não acumular lixo.
    prune_unknown_gold()

    logger.info(
        "FIFA: gold gravado — team_stats=%d/%d, player_stats=%d/%d, live=%d/%d",
        ok_team, ok_team + miss_team,
        ok_player, ok_player + miss_player,
        ok_live, ok_live + miss_live,
    )
    return {
        "matches": len(matches),
        "finished": len(finished),
        "team_stats_ok": ok_team,
        "team_stats_missing": miss_team,
        "player_stats_ok": ok_player,
        "player_stats_missing": miss_player,
        "live_ok": ok_live,
        "live_missing": miss_live,
        "power_ranking_players": len(power_ranking),
        "wide_rows": len(wide),
        "snapshots": n_snapshots,
    }
