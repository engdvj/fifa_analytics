"""Relatórios por jogo — fonte única FIFA.

Wrapper fino sobre `fifa_reports.run_fifa_reports`. A reconciliação multi-fonte
(antigo `canonical_reports`) foi removida na refundação FIFA-only.
"""
from __future__ import annotations

from fifa_analytics.workflows.fifa_reports import run_fifa_reports


def run_basic_reports(source: str = "fifa", status: str = "finalizado") -> dict[str, object]:
    if source not in ("fifa", "canonical"):
        raise ValueError(
            f"Fonte '{source}' não suportada. A única fonte é 'fifa' "
            "(o pipeline FIFA grava o gold lido pelos relatórios)."
        )
    return run_fifa_reports(status=status)
