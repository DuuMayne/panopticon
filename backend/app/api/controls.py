from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Control, ControlRun, ControlFailure, ControlCurrentState
from app.schemas import ControlSummary, ControlDetail, RunSummary, RunDetail
from app.scheduler import run_control


class UpdateCadenceRequest(BaseModel):
    cadence_seconds: int

router = APIRouter(prefix="/controls", tags=["controls"])


@router.get("", response_model=list[ControlSummary])
def list_controls(db: Session = Depends(get_db)):
    controls = (
        db.query(Control)
        .options(joinedload(Control.current_state))
        .order_by(Control.key)
        .all()
    )
    return controls


@router.get("/{control_id}", response_model=ControlDetail)
def get_control(control_id: UUID, db: Session = Depends(get_db)):
    control = (
        db.query(Control)
        .options(joinedload(Control.current_state))
        .filter(Control.id == control_id)
        .first()
    )
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")
    return control


@router.get("/{control_id}/runs", response_model=list[RunSummary])
def list_runs(control_id: UUID, limit: int = 50, db: Session = Depends(get_db)):
    runs = (
        db.query(ControlRun)
        .filter(ControlRun.control_id == control_id)
        .order_by(ControlRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return runs


@router.get("/{control_id}/runs/latest", response_model=RunDetail | None)
def get_latest_run(control_id: UUID, db: Session = Depends(get_db)):
    run = (
        db.query(ControlRun)
        .options(joinedload(ControlRun.failures))
        .filter(ControlRun.control_id == control_id)
        .order_by(ControlRun.started_at.desc())
        .first()
    )
    return run


@router.post("/{control_id}/run", response_model=dict)
def trigger_run(control_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    control = db.query(Control).filter(Control.id == control_id).first()
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")
    background_tasks.add_task(run_control, str(control_id))
    return {"message": f"Run triggered for control {control.key}"}


@router.patch("/{control_id}/cadence", response_model=dict)
def update_cadence(control_id: UUID, body: UpdateCadenceRequest, db: Session = Depends(get_db)):
    """Update the run cadence for a specific control."""
    control = db.query(Control).filter(Control.id == control_id).first()
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")
    if body.cadence_seconds < 60:
        raise HTTPException(status_code=400, detail="Cadence must be at least 60 seconds")
    control.cadence_seconds = body.cadence_seconds
    control.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": f"Cadence updated to {body.cadence_seconds}s for {control.key}", "cadence_seconds": body.cadence_seconds}


@router.delete("/{control_id}/runs", response_model=dict)
def delete_runs(control_id: UUID, before: str = None, db: Session = Depends(get_db)):
    """Delete run history for a control.

    Query params:
        before: ISO datetime — delete runs older than this. If omitted, deletes all runs.
    """
    control = db.query(Control).filter(Control.id == control_id).first()
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    query = db.query(ControlRun).filter(ControlRun.control_id == control_id)
    if before:
        try:
            cutoff = datetime.fromisoformat(before.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid datetime format for 'before' parameter")
        query = query.filter(ControlRun.started_at < cutoff)

    # Get IDs to delete (for cascade cleanup)
    run_ids = [r.id for r in query.all()]
    if not run_ids:
        return {"message": "No runs to delete", "deleted": 0}

    # Delete failures first (cascade should handle this but be explicit)
    db.query(ControlFailure).filter(ControlFailure.control_run_id.in_(run_ids)).delete(synchronize_session=False)
    deleted = query.delete(synchronize_session=False)

    # If we deleted the latest run, update current state
    state = db.query(ControlCurrentState).filter(ControlCurrentState.control_id == control_id).first()
    if state and state.last_run_id in run_ids:
        latest = (
            db.query(ControlRun)
            .filter(ControlRun.control_id == control_id)
            .order_by(ControlRun.started_at.desc())
            .first()
        )
        if latest:
            state.last_run_id = latest.id
            state.last_run_at = latest.started_at
            state.current_status = latest.status
        else:
            state.last_run_id = None
            state.last_run_at = None
            state.current_status = "pending"
            state.consecutive_failures = 0
            state.failing_resource_count = 0
            state.first_failed_at = None

    db.commit()
    return {"message": f"Deleted {deleted} runs for {control.key}", "deleted": deleted}
