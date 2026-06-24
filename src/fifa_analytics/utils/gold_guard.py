"""Guard anti-stale do gold.

Quando o código muda o caminho de um artefato (ex.: a timeline de times saiu de
`analytics/snapshots/` para `analytics/`), o arquivo antigo fica para trás e vira
dado fantasma — foi exatamente o que aconteceu com os `canonical_*` do pipeline
multi-fonte e com a timeline duplicada. Este guard mantém um conjunto CANÔNICO de
parquets esperados no gold e remove (ou só sinaliza) qualquer outro.

Roda no fim do pipeline (`fifa/pipeline.run`). Mexe só em `*.parquet` dentro de
`data/gold/` — não toca em JSON (weights.json), raw nem silver.
"""
from __future__ import annotations

from pathlib import Path

from fifa_analytics.paths import GOLD_DIR
from fifa_analytics.utils.logging import get_logger

logger = get_logger(__name__)

# Conjunto canônico de parquets do gold, somando TODOS os comandos (fifa-coletar
# escreve a maioria; status-torneio escreve standings/ e tournament_status/).
# Caminhos relativos a GOLD_DIR, em posix. Qualquer *.parquet fora desta lista é
# tratado como stale.
KNOWN_GOLD_PARQUETS: frozenset[str] = frozenset({
    "dim_match.parquet",
    "fact_team_match_stats.parquet",
    "fact_player_match_stats.parquet",
    "fact_lineups.parquet",
    "fact_events.parquet",
    "fact_power_ranking.parquet",
    "analytics/team_match_wide.parquet",
    "analytics/player_match_wide.parquet",
    "analytics/snapshot_timeline.parquet",
    "analytics/snapshots/player_snapshot_timeline.parquet",
    "standings/fifa_group_standings.parquet",
    "tournament_status/tournament_status.parquet",
})


def find_unknown_gold(gold_dir: Path = GOLD_DIR) -> list[Path]:
    """Parquets em `gold_dir` que não pertencem ao conjunto canônico."""
    if not gold_dir.exists():
        return []
    out = [
        p for p in gold_dir.rglob("*.parquet")
        if p.relative_to(gold_dir).as_posix() not in KNOWN_GOLD_PARQUETS
    ]
    return sorted(out)


def prune_unknown_gold(gold_dir: Path = GOLD_DIR, *, remove: bool = True) -> list[Path]:
    """Remove (ou só sinaliza) parquets stale do gold. Retorna o que encontrou.

    Com `remove=False` apenas loga — útil para auditoria sem efeito colateral.
    Diretórios que ficarem vazios após a remoção também são apagados.
    """
    unknown = find_unknown_gold(gold_dir)
    for p in unknown:
        rel = p.relative_to(gold_dir).as_posix()
        if not remove:
            logger.warning("gold stale detectado (não removido): %s", rel)
            continue
        try:
            p.unlink()
            logger.warning("gold stale removido: %s", rel)
        except OSError as exc:  # pragma: no cover - falha de FS é rara
            logger.warning("não consegui remover %s: %s", rel, exc)

    if remove and unknown:
        for d in sorted(gold_dir.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                try:
                    d.rmdir()
                except OSError:  # pragma: no cover
                    pass
    return unknown
