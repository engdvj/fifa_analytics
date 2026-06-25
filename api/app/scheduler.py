"""Coleta automática agendada.

Roda o MESMO fluxo do `POST /admin/collect` (pipeline FIFA → `load_matches` →
recálculo de pontos) num intervalo fixo, numa thread daemon. Assim, alguns
minutos depois de um jogo finalizar na FIFA, o gold, a tabela `matches` e os
pontos dos palpites são atualizados sem ação manual.

Como a FIFA não "avisa" o fim do jogo, isto é polling. Ligado por
`AUTO_COLLECT_MINUTES` (>0). 0/ausente = desligado (padrão em dev/testes).
"""
from __future__ import annotations

import logging
import os
import threading
import time

from api.app.db import SessionLocal
from api.app.models import CollectionJob
from api.app.routers.admin import _run_job

log = logging.getLogger("auto_collect")


def _loop(interval_seconds: float) -> None:
    while True:
        time.sleep(interval_seconds)
        try:
            db = SessionLocal()
            try:
                job = CollectionJob(kind="coleta", status="pending", triggered_by=None)
                db.add(job)
                db.commit()
                db.refresh(job)
                job_id = job.id
            finally:
                db.close()
            log.info("auto-collect: iniciando job %s", job_id)
            _run_job(job_id, do_collect=True)  # cria a própria sessão; é síncrono
            log.info("auto-collect: job %s concluído", job_id)
        except Exception:  # noqa: BLE001 — nunca derruba a thread/servidor
            log.exception("auto-collect: falha no ciclo")


def start_auto_collect() -> threading.Thread | None:
    """Liga o agendador se AUTO_COLLECT_MINUTES > 0. Retorna a thread (ou None)."""
    raw = os.getenv("AUTO_COLLECT_MINUTES", "0") or "0"
    try:
        minutes = float(raw)
    except ValueError:
        minutes = 0.0
    if minutes <= 0:
        return None
    thread = threading.Thread(
        target=_loop, args=(minutes * 60,), name="auto-collect", daemon=True
    )
    thread.start()
    log.info("auto-collect ligado: a cada %.0f min", minutes)
    return thread
