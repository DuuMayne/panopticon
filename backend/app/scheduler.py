from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.models import Control, ControlRun, ControlFailure, ControlCurrentState
from app.evaluators.registry import get_evaluator, get_connector
from app.alerting import check_and_alert

logger = logging.getLogger("panopticon.scheduler")

_scheduler = None  # type: Optional[BackgroundScheduler]
_last_heartbeat = None  # type: Optional[datetime]


def get_scheduler_status() -> tuple[bool, datetime | None]:
    return _scheduler is not None and _scheduler.running, _last_heartbeat


def run_control(control_id: str) -> None:
    """Execute a single control evaluation."""
    db = SessionLocal()
    try:
        control = db.query(Control).filter(Control.id == control_id).first()
        if not control or not control.enabled:
            return

        logger.info(f"Running control: {control.key}")
        now = datetime.now(timezone.utc)

        run = ControlRun(control_id=control.id, started_at=now, status="error")
        db.add(run)
        db.flush()

        try:
            connector = get_connector(control.connector_type)
            data = connector.fetch(control.config_json)

            evaluator = get_evaluator(control.evaluator_type)
            result = evaluator.evaluate(data, control.config_json)

            run.status = result.status
            run.summary = result.summary
            run.evidence_json = result.evidence
            run.run_metadata_json = result.metadata
            run.completed_at = datetime.now(timezone.utc)

            for f in result.failures:
                db.add(ControlFailure(
                    control_run_id=run.id,
                    resource_type=f.resource_type,
                    resource_identifier=f.resource_identifier,
                    details_json=f.details,
                ))

        except Exception as e:
            logger.error(f"Control {control.key} failed: {e}")
            run.status = "error"
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)

        # Update current state
        state = db.query(ControlCurrentState).filter(
            ControlCurrentState.control_id == control.id
        ).first()

        previous_status = state.current_status if state else None

        if not state:
            state = ControlCurrentState(control_id=control.id)
            db.add(state)

        state.last_run_id = run.id
        state.last_run_at = run.started_at
        state.updated_at = datetime.now(timezone.utc)

        failing_count = len(run.failures) if run.status == "fail" else 0
        state.failing_resource_count = failing_count

        if run.status != previous_status:
            state.last_status_changed_at = datetime.now(timezone.utc)

        if run.status == "fail":
            state.consecutive_failures = (state.consecutive_failures or 0) + 1
            if previous_status != "fail":
                state.first_failed_at = datetime.now(timezone.utc)
        else:
            state.consecutive_failures = 0
            state.first_failed_at = None

        state.current_status = run.status

        db.commit()

        # Alert after commit
        check_and_alert(
            control_name=control.name,
            previous_status=previous_status,
            new_status=run.status,
            consecutive_failures=state.consecutive_failures,
            summary=run.summary or "",
            failing_count=failing_count,
            error_message=run.error_message,
        )

        logger.info(f"Control {control.key}: {run.status} — {run.summary}")

    except Exception as e:
        logger.error(f"Scheduler error for control {control_id}: {e}")
        db.rollback()
    finally:
        db.close()


def run_all_controls() -> None:
    """Run all enabled controls."""
    global _last_heartbeat
    _last_heartbeat = datetime.now(timezone.utc)
    logger.info("Scheduler heartbeat — running all enabled controls")

    db = SessionLocal()
    try:
        controls = db.query(Control).filter(Control.enabled == True).all()  # noqa: E712
        control_ids = [str(c.id) for c in controls]
    finally:
        db.close()

    for cid in control_ids:
        run_control(cid)


def start_scheduler() -> None:
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        run_all_controls,
        "interval",
        seconds=settings.default_cadence_seconds,
        id="run_all_controls",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(f"Scheduler started — cadence: {settings.default_cadence_seconds}s")

    # Run once immediately on startup
    run_all_controls()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
