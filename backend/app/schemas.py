from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel


class ControlCurrentStateSchema(BaseModel):
    current_status: str
    last_run_at: Optional[datetime] = None
    first_failed_at: Optional[datetime] = None
    last_status_changed_at: Optional[datetime] = None
    consecutive_failures: int = 0
    failing_resource_count: int = 0

    model_config = {"from_attributes": True}


class ControlSummary(BaseModel):
    id: UUID
    key: str
    name: str
    description: Optional[str] = None
    owner: Optional[str] = None
    enabled: bool
    connector_type: str
    evaluator_type: str
    current_state: Optional[ControlCurrentStateSchema] = None

    model_config = {"from_attributes": True}


class ControlDetail(ControlSummary):
    cadence_seconds: int
    config_json: dict
    created_at: datetime
    updated_at: datetime


class FailureSchema(BaseModel):
    id: UUID
    resource_type: str
    resource_identifier: str
    details_json: Optional[dict] = None

    model_config = {"from_attributes": True}


class RunSummary(BaseModel):
    id: UUID
    control_id: UUID
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    summary: Optional[str] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class RunDetail(RunSummary):
    evidence_json: Optional[dict] = None
    run_metadata_json: Optional[dict] = None
    failures: List[FailureSchema] = []


class FailureWithControl(FailureSchema):
    control_run_id: UUID
    control_key: str
    control_name: str
    run_status: str
    run_started_at: datetime


class HealthResponse(BaseModel):
    status: str
    scheduler_running: bool
    last_scheduler_heartbeat: Optional[datetime] = None
