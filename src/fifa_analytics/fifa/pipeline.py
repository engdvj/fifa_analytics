"""Pipeline FIFA: coleta -> raw -> silver -> gold (parquet).

Fatia vertical fina: calendário (todos os jogos) + stats de time dos jogos
finalizados. Fonte única FIFA. Saídas:
- raw    data/raw/fifa/<endpoint>/date=YYYYMMDD/collected_at=TS/*.json
- silver data/silver/fifa/dim_match.parquet, fact_team_match_stats.parquet
- gold   data/gold/dim_match.parquet, fact_team_match_stats.parquet
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from fifa_analytics.fifa import client, transforms
from fifa_analytics.paths import GOLD_DIR, RAW_DIR, SILVER_DIR
from fifa_analytics.utils.io import write_dataframe, write_json
from fifa_analytics.utils.logging import get_logger

logger = get_logger(__name__)


def _raw_path(endpoint: str, *, ts: str, suffix: str = "") -> str:
    date = ts[:8]
    name = f"{suffix}.json" if suffix else "data.json"
    return str(RAW_DIR / "fifa" / endpoint / f"date={date}" / f"collected_at={ts}" / name)


def run(*, only_finished: bool = True) -> dict[str, int]:
    """Executa o pipeline completo. Retorna contadores para log/CLI."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    # 1. coleta calendário (raw) ------------------------------------------
    logger.info("FIFA: coletando calendário…")
    results = client.fetch_calendar_matches()
    write_json(_raw_path("calendar", ts=ts), results)

    matches = transforms.normalize_matches(results)
    finished = matches[matches["status"] == "finalizado"]
    logger.info("FIFA: %d jogos (%d finalizados)", len(matches), len(finished))

    # 2. stats de time por jogo finalizado (raw + transform) --------------
    targets = finished if only_finished else matches[matches["id_ifes"] != ""]
    stats_frames = []
    ok = miss = 0
    for row in targets.itertuples():
        if not row.id_ifes:
            continue
        try:
            payload = client.fetch_match_team_stats(row.id_ifes)
        except client.FifaSourceError as exc:
            logger.warning("FIFA: sem stats p/ %s (%s): %s", row.match_id, row.id_ifes, exc)
            miss += 1
            continue
        write_json(_raw_path("match_team_stats", ts=ts, suffix=row.id_ifes), payload)
        stats_frames.append(
            transforms.normalize_match_team_stats(row.match_id, row.id_ifes, payload)
        )
        ok += 1

    team_stats = (
        pd.concat(stats_frames, ignore_index=True) if stats_frames else pd.DataFrame()
    )

    # 3. silver + gold (parquet) ------------------------------------------
    for base in (SILVER_DIR / "fifa", GOLD_DIR):
        write_dataframe(base / "dim_match.parquet", matches)
        if not team_stats.empty:
            write_dataframe(base / "fact_team_match_stats.parquet", team_stats)

    logger.info("FIFA: gold gravado — stats de %d jogos (%d sem dados)", ok, miss)
    return {
        "matches": len(matches),
        "finished": len(finished),
        "stats_ok": ok,
        "stats_missing": miss,
    }
