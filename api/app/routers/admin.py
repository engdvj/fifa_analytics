"""Endpoints administrativos: dispara coleta/recálculo e acompanha os jobs.

Tudo aqui exige admin (`require_admin`). A coleta e o recálculo rodam em
background (thread própria via BackgroundTasks) para não bloquear o request; o
progresso é registrado num `CollectionJob`. O runner é resiliente: nunca derruba
o servidor — encapsula tudo em try/except e grava o desfecho no log do job.
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db import SessionLocal, get_db
from api.app.loaders.load_matches import load_matches
from api.app.models import CollectionJob, User
from api.app.routers.auth import require_admin
from api.app.scoring.recompute import recompute_pool_points
from api.app.schemas import JobOut

router = APIRouter(prefix="/admin", tags=["admin"])

# Fábrica de sessão usada pelo runner de background. Em produção é a SessionLocal
# real; os testes (SQLite) sobrescrevem para apontar ao mesmo banco do request.
_session_factory = SessionLocal
_ROOT = Path(__file__).resolve().parents[3]
_PIPELINE_TIMEOUT_SECONDS = int(os.getenv("ADMIN_COLLECT_TIMEOUT_SECONDS", "1800"))


def set_session_factory(factory) -> None:
    """Sobrescreve a fábrica de sessão do runner (usado em testes)."""
    global _session_factory
    _session_factory = factory


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _append_log(job: CollectionJob, line: str) -> None:
    job.log = (job.log + "\n" if job.log else "") + line


def _run_pipeline() -> dict:
    """Roda o pipeline FIFA (coleta -> gold) em subprocesso matável.

    Rodar em processo separado evita que uma chamada externa presa deixe a thread
    do servidor e o job eternamente em `running`. Em timeout, o subprocesso é
    encerrado e o job registra erro.
    """
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    cmd = [sys.executable, "-m", "fifa_analytics", "fifa-coletar"]
    try:
        completed = subprocess.run(
            cmd,
            cwd=_ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=_PIPELINE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        partial = "\n".join(part for part in [exc.stdout, exc.stderr] if part)
        tail = partial[-4000:] if partial else ""
        raise TimeoutError(
            f"pipeline excedeu {_PIPELINE_TIMEOUT_SECONDS}s e foi encerrado"
            + (f"\n{tail}" if tail else "")
        ) from exc
    output = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
    if completed.returncode != 0:
        tail = output[-4000:] if output else "(sem saída)"
        raise RuntimeError(f"pipeline saiu com código {completed.returncode}\n{tail}")
    return {"returncode": completed.returncode, "output": output[-4000:]}


def _job_age_seconds(job: CollectionJob) -> float:
    ref = job.started_at or job.created_at
    if ref is None:
        return 0.0
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return max(0.0, (_now() - ref).total_seconds())


def recover_stale_jobs(db: Session, *, reason: str = "servidor reiniciado") -> int:
    """Marca jobs ativos órfãos como erro.

    BackgroundTasks não sobrevivem a restart do processo. Portanto, qualquer
    job `pending`/`running` encontrado no boot é órfão do processo anterior.
    """
    jobs = db.scalars(
        select(CollectionJob).where(CollectionJob.status.in_(["pending", "running"]))
    ).all()
    for job in jobs:
        _append_log(job, f"job marcado como interrompido: {reason}")
        job.status = "error"
        job.finished_at = _now()
    if jobs:
        db.commit()
    return len(jobs)


def _expire_overdue_jobs(db: Session) -> int:
    """Fecha jobs ativos que passaram do teto sem depender de restart."""
    max_age = _PIPELINE_TIMEOUT_SECONDS + 60
    jobs = db.scalars(
        select(CollectionJob).where(CollectionJob.status.in_(["pending", "running"]))
    ).all()
    expired = 0
    for job in jobs:
        if _job_age_seconds(job) <= max_age:
            continue
        _append_log(job, f"job excedeu {max_age}s sem finalizar; marcado como erro")
        job.status = "error"
        job.finished_at = _now()
        expired += 1
    if expired:
        db.commit()
    return expired


def _active_job(db: Session) -> CollectionJob | None:
    _expire_overdue_jobs(db)
    return db.scalars(
        select(CollectionJob)
        .where(CollectionJob.status.in_(["pending", "running"]))
        .order_by(CollectionJob.id.desc())
    ).first()


def _reject_if_active(db: Session) -> None:
    active = _active_job(db)
    if active is None:
        return
    raise HTTPException(
        409,
        {
            "message": "ja existe um job administrativo em andamento",
            "job_id": active.id,
            "kind": active.kind,
            "status": active.status,
        },
    )


# ── Runners (rodam em thread de background, com sessão própria) ────────────────

def _run_job(job_id: int, *, do_collect: bool) -> None:
    """Executa o job. Sessão própria (não compartilha a do request).

    `do_collect=True` tenta rodar o pipeline FIFA antes de recarregar; em recalc
    pula a coleta. Sempre recarrega matches do gold e recalcula pontos."""
    db: Session = _session_factory()
    try:
        job = db.get(CollectionJob, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = _now()
        db.commit()

        ok = True

        if do_collect:
            try:
                counters = _run_pipeline()
                _append_log(job, f"pipeline ok: {counters}")
            except Exception as exc:  # noqa: BLE001 — coleta pode falhar (rede/env)
                ok = False
                _append_log(job, f"pipeline falhou (segue mesmo assim): {exc!r}")
            db.commit()

        # Recarrega matches do gold (se o parquet existir) e recalcula pontos.
        try:
            result = load_matches(db)
            _append_log(job, f"load_matches: {result}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            _append_log(job, f"load_matches falhou: {exc!r}")

        try:
            scored = recompute_pool_points(db)
            db.commit()
            _append_log(job, f"recompute_pool_points: {scored} palpites pontuados")
        except Exception as exc:  # noqa: BLE001
            ok = False
            db.rollback()
            _append_log(job, f"recompute falhou: {exc!r}")

        job.status = "success" if ok else "error"
        job.finished_at = _now()
        db.commit()
    except Exception:  # noqa: BLE001 — blindagem final, nunca derruba o servidor
        try:
            job = db.get(CollectionJob, job_id)
            if job is not None:
                _append_log(job, "erro inesperado:\n" + traceback.format_exc())
                job.status = "error"
                job.finished_at = _now()
                db.commit()
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


def _create_job(db: Session, kind: str, user: User) -> CollectionJob:
    job = CollectionJob(kind=kind, status="pending", triggered_by=user.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/collect", response_model=JobOut, status_code=202)
def trigger_collect(
    background: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Dispara coleta FIFA + reload + recálculo, em background."""
    _reject_if_active(db)
    job = _create_job(db, "coleta", admin)
    background.add_task(_run_job, job.id, do_collect=True)
    return job


@router.post("/recalc", response_model=JobOut, status_code=202)
def trigger_recalc(
    background: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Recarrega matches do gold + recalcula todos os pontos, em background."""
    _reject_if_active(db)
    job = _create_job(db, "recalc", admin)
    background.add_task(_run_job, job.id, do_collect=False)
    return job


def _run_learn_job(job_id: int) -> None:
    """Re-treina a calibração/pesos da preditiva a partir dos resultados reais."""
    db: Session = _session_factory()
    try:
        job = db.get(CollectionJob, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = _now()
        db.commit()
        try:
            import pandas as pd

            from fifa_analytics.analytics.predictive import learn_and_save
            from fifa_analytics.paths import GOLD_DIR

            dim = pd.read_parquet(GOLD_DIR / "dim_match.parquet")
            timeline = pd.read_parquet(GOLD_DIR / "analytics" / "snapshot_timeline.parquet")
            report = learn_and_save(dim, timeline)
            m = report.get("metrics", {})
            _append_log(
                job,
                "auto-aprendizado ok: log_loss "
                f"{m.get('before', {}).get('log_loss')} -> {m.get('after', {}).get('log_loss')} "
                f"em {report.get('evaluated_games')} jogos",
            )
            job.status = "success"
        except Exception as exc:  # noqa: BLE001 — aprendizado pode falhar sem dados
            _append_log(job, f"auto-aprendizado falhou: {exc!r}")
            job.status = "error"
        job.finished_at = _now()
        db.commit()
    finally:
        db.close()


@router.post("/predictive/learn", response_model=JobOut, status_code=202)
def trigger_predictive_learn(
    background: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Re-treina a preditiva (calibração + pesos) com os resultados reais. Pesado;
    roda em background e pode levar minutos."""
    _reject_if_active(db)
    job = _create_job(db, "preditiva-learn", admin)
    background.add_task(_run_learn_job, job.id)
    return job


@router.get("/auto-collect")
def auto_collect_status(admin: User = Depends(require_admin)) -> dict:
    """Estado da coleta automática dirigida pelo calendário (scheduler)."""
    from api.app.scheduler import get_status

    return get_status()


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lista os jobs, mais recentes primeiro."""
    return db.scalars(select(CollectionJob).order_by(CollectionJob.id.desc())).all()


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    job = db.get(CollectionJob, job_id)
    if job is None:
        raise HTTPException(404, "job não encontrado")
    return job
