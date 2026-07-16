"""
Stay-limit auto-advance scheduler — Pipeline.2 Fase 3.

Periodic in-process sweep (not a thread per entry — a stay_limit is measured
in minutes/hours, and a per-entry sleeping thread would die silently on every
Railway redeploy). Runs in a single daemon thread started at app startup.

Safe under multiple replicas without a distributed lock: every move is a
compare-and-swap UPDATE (`WHERE stage_id = <the stage we read>`). If another
replica already moved the same entry between our SELECT and UPDATE, the
WHERE clause matches zero rows and we silently skip — no double-move.

MVP-appropriate for the current single-replica deployment. If the API scales
to multiple replicas, migrate to Celery Beat / external cron — the CAS
already makes that migration safe to do later without redesigning the guard.
"""

import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database import engine
from app.models.pipeline_entry import PipelineEntry
from app.models.pipeline_stage import PipelineStage
from app.services import pipeline_service
from app.services.plan_feature_service import workspace_allows_feature

logger = logging.getLogger(__name__)

_SWEEP_INTERVAL_SECONDS = 60


def start_background_sweep() -> None:
    t = threading.Thread(target=_sweep_loop, daemon=True, name="pipeline-stay-limit-sweep")
    t.start()
    logger.info("pipeline_stay_limit_sweep started interval=%ds", _SWEEP_INTERVAL_SECONDS)


def _sweep_loop() -> None:
    while True:
        time.sleep(_SWEEP_INTERVAL_SECONDS)
        db = Session(engine)
        try:
            moved = run_sweep_once(db)
            if moved:
                logger.info("pipeline_stay_limit_sweep moved=%d", moved)
        except Exception:
            logger.exception("pipeline_stay_limit_sweep unexpected error")
        finally:
            db.close()


def run_sweep_once(db: Session) -> int:
    """
    One sweep pass. Extracted from the loop so tests can call it directly
    without needing to spin up a background thread.
    """
    now = datetime.now(timezone.utc)

    candidates = db.execute(
        select(
            PipelineEntry.id,
            PipelineEntry.workspace_id,
            PipelineEntry.pipeline_id,
            PipelineEntry.stage_id,
            PipelineEntry.entered_stage_at,
        )
        .join(PipelineStage, PipelineStage.id == PipelineEntry.stage_id)
        .where(
            PipelineEntry.status == "active",
            PipelineEntry.entered_stage_at.is_not(None),
            PipelineStage.stay_limit_enabled.is_(True),
            PipelineStage.stay_limit_minutes.is_not(None),
        )
    ).all()

    moved_count = 0
    for row in candidates:
        if _maybe_advance_entry(db, now, row.id, row.workspace_id, row.pipeline_id, row.stage_id, row.entered_stage_at):
            moved_count += 1
    return moved_count


def _maybe_advance_entry(
    db: Session,
    now: datetime,
    entry_id: uuid.UUID,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID | None,
    stage_id: uuid.UUID | None,
    entered_stage_at: datetime | None,
) -> bool:
    if pipeline_id is None or stage_id is None or entered_stage_at is None:
        return False
    if not workspace_allows_feature(db, workspace_id, "pipeline_automations"):
        return False

    stage = db.scalar(select(PipelineStage).where(PipelineStage.id == stage_id))
    if stage is None or not stage.stay_limit_enabled or not stage.stay_limit_minutes:
        return False

    if now - entered_stage_at < timedelta(minutes=stage.stay_limit_minutes):
        return False

    next_stage = db.scalar(
        select(PipelineStage)
        .where(PipelineStage.pipeline_id == pipeline_id, PipelineStage.position > stage.position)
        .order_by(PipelineStage.position.asc())
        .limit(1)
    )
    if next_stage is None:
        return False  # last stage — nothing to advance to

    # Compare-and-swap: only succeeds if the entry is still in the stage we read.
    result = db.execute(
        update(PipelineEntry)
        .where(PipelineEntry.id == entry_id, PipelineEntry.stage_id == stage_id)
        .values(stage_id=next_stage.id, entered_stage_at=now, updated_at=now)
    )
    if result.rowcount == 0:
        return False  # lost the race — another process already moved it

    entry = db.scalar(select(PipelineEntry).where(PipelineEntry.id == entry_id))
    if entry is None:
        db.commit()
        return True

    pipeline_service.apply_stage_entry_effects(
        db, workspace_id, entry, next_stage, stage_id, "stay_limit"
    )
    db.commit()
    return True
