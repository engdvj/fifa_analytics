"""Coleta automática dirigida pelo calendário oficial da FIFA.

Em vez de rodar o pipeline cegamente a cada N minutos, o agendador faz um
polling LEVE do calendário (uma única chamada HTTP) e só dispara a coleta
pesada quando algum jogo VIRA "finalizado" na FIFA. Ao detectar, espera uma
folga (`AUTO_COLLECT_GRACE_MINUTES`) — as estatísticas avançadas (fdh) publicam
alguns minutos depois do status mudar — e então roda o MESMO fluxo do
`POST /admin/collect` (pipeline FIFA → `load_matches` → recálculo de pontos).

A FIFA não "avisa" o fim do jogo, então isto continua sendo polling; o ganho é
não martelar a coleta inteira à toa e reagir logo após cada jogo terminar.

Env:
  AUTO_COLLECT_MINUTES        intervalo de checagem do calendário (0 = desligado)
  AUTO_COLLECT_GRACE_MINUTES  espera após detectar fim de jogo (default 10)
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone

log = logging.getLogger("auto_collect")

DEFAULT_GRACE_MINUTES = 10.0
# Atraso até a PRIMEIRA checagem do calendário após subir (as seguintes respeitam
# AUTO_COLLECT_MINUTES). Curto p/ o status popular e detectar jogos já encerrados.
INITIAL_DELAY_SECONDS = 20.0

# Estado publicado para a página admin (GET /admin/auto-collect). Atualizado pela
# thread; lido pelo request. dict simples (escritas atômicas em CPython) — não
# precisa de lock para este uso.
_status: dict = {
    "enabled": False,
    "interval_minutes": None,
    "grace_minutes": None,
    "started_at": None,
    "last_check_at": None,
    "last_finished_count": None,
    "last_collect_at": None,
    "last_collect_ok": None,
    "waiting_until": None,
    "pending": [],
    "last_error": None,
}


def get_status() -> dict:
    """Cópia do estado atual da coleta automática (para o endpoint admin)."""
    return dict(_status)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_minutes(name: str, default: float) -> float:
    """Lê uma env em minutos; vazia/ausente/inválida → default."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _finished_from_calendar() -> set[str]:
    """Calendário oficial (chamada live) → match_id já finalizados."""
    from fifa_analytics.fifa import client, transforms

    results = client.fetch_calendar_matches()
    matches = transforms.normalize_matches(results)
    if matches.empty or "status" not in matches.columns:
        return set()
    return set(matches.loc[matches["status"] == "finalizado", "match_id"])


def _finished_from_gold() -> set[str]:
    """Finalizados já refletidos no gold — semente que evita recoletar tudo no
    boot, mas deixa pegar o que terminou enquanto a API esteve fora."""
    import pandas as pd

    from fifa_analytics.paths import GOLD_DIR

    path = GOLD_DIR / "dim_match.parquet"
    if not path.exists():
        return set()
    try:
        df = pd.read_parquet(path, columns=["match_id", "status"])
    except Exception:  # noqa: BLE001 — gold ausente/corrompido não derruba o loop
        return set()
    return set(df.loc[df["status"] == "finalizado", "match_id"])


def _collect_now() -> None:
    """Cria um CollectionJob e roda o mesmo job do POST /admin/collect."""
    from api.app.db import SessionLocal
    from api.app.models import CollectionJob
    from api.app.routers.admin import _run_job

    db = SessionLocal()
    try:
        job = CollectionJob(kind="coleta", status="pending", triggered_by=None)
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()
    _run_job(job_id, do_collect=True)  # cria a própria sessão; é síncrono


def _loop(interval_seconds: float, grace_seconds: float) -> None:
    # Semente: o que o gold já conhece como finalizado. Restart não recoleta tudo;
    # jogo que terminou durante uma queda é detectado no primeiro ciclo.
    try:
        seen = _finished_from_gold()
    except Exception:  # noqa: BLE001
        seen = set()
    log.info("auto-collect: semente com %d jogo(s) finalizado(s)", len(seen))

    _status["last_finished_count"] = len(seen)

    # Primeira checagem logo após subir (não espera o intervalo inteiro): popula o
    # status na hora e pega rápido um jogo que já tenha terminado antes do deploy.
    first = True
    while True:
        time.sleep(INITIAL_DELAY_SECONDS if first else interval_seconds)
        first = False
        try:
            current = _finished_from_calendar()
            _status["last_check_at"] = _utcnow_iso()
            _status["last_finished_count"] = len(current)
        except Exception:  # noqa: BLE001 — erro de rede não derruba a thread
            log.exception("auto-collect: falha ao ler o calendário")
            _status["last_error"] = f"calendário: {_utcnow_iso()}"
            continue

        novos = current - seen
        if not novos:
            continue

        log.info(
            "auto-collect: %d novo(s) finalizado(s) %s — aguardando %.0f min antes de coletar",
            len(novos), sorted(novos), grace_seconds / 60,
        )
        _status["pending"] = sorted(novos)
        _status["waiting_until"] = _utcnow_iso()  # detectado em; folga começa agora
        time.sleep(grace_seconds)
        try:
            _collect_now()
            seen = current  # só marca como visto após coletar com sucesso
            _status["last_collect_at"] = _utcnow_iso()
            _status["last_collect_ok"] = True
            _status["last_error"] = None
            log.info("auto-collect: coleta concluída (%d finalizados no total)", len(seen))
        except Exception:  # noqa: BLE001 — mantém `seen` p/ tentar de novo no próximo ciclo
            _status["last_collect_at"] = _utcnow_iso()
            _status["last_collect_ok"] = False
            _status["last_error"] = f"coleta: {_utcnow_iso()}"
            log.exception("auto-collect: falha na coleta; tenta de novo no próximo ciclo")
        finally:
            _status["pending"] = []
            _status["waiting_until"] = None


def start_auto_collect() -> threading.Thread | None:
    """Liga o agendador se AUTO_COLLECT_MINUTES > 0. Retorna a thread (ou None)."""
    minutes = _env_minutes("AUTO_COLLECT_MINUTES", 0.0)
    if minutes <= 0:
        _status["enabled"] = False
        return None
    grace = max(0.0, _env_minutes("AUTO_COLLECT_GRACE_MINUTES", DEFAULT_GRACE_MINUTES))
    _status.update(
        enabled=True,
        interval_minutes=minutes,
        grace_minutes=grace,
        started_at=_utcnow_iso(),
    )
    thread = threading.Thread(
        target=_loop, args=(minutes * 60, grace * 60), name="auto-collect", daemon=True
    )
    thread.start()
    log.info(
        "auto-collect ligado: checa o calendário a cada %.0f min, folga de %.0f min",
        minutes, grace,
    )
    return thread
