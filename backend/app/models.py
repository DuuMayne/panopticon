from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import String, Boolean, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Control(Base):
    __tablename__ = "controls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner: Mapped[Optional[str]] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cadence_seconds: Mapped[int] = mapped_column(Integer, default=21600, nullable=False)
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    evaluator_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)

    runs: Mapped[List[ControlRun]] = relationship(back_populates="control", lazy="dynamic")
    current_state: Mapped[Optional[ControlCurrentState]] = relationship(back_populates="control", uselist=False)


class ControlRun(Base):
    __tablename__ = "control_runs"
    __table_args__ = (
        Index("idx_control_runs_control_id", "control_id"),
        Index("idx_control_runs_started_at", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    control_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("controls.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    evidence_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    run_metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

    control: Mapped[Control] = relationship(back_populates="runs")
    failures: Mapped[List[ControlFailure]] = relationship(back_populates="run", cascade="all, delete-orphan")


class ControlFailure(Base):
    __tablename__ = "control_failures"
    __table_args__ = (
        Index("idx_control_failures_run_id", "control_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    control_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("control_runs.id", ondelete="CASCADE"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_identifier: Mapped[str] = mapped_column(String(500), nullable=False)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB)

    run: Mapped[ControlRun] = relationship(back_populates="failures")


class ControlCurrentState(Base):
    __tablename__ = "control_current_state"

    control_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("controls.id"), primary_key=True)
    current_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    last_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("control_runs.id"))
    last_run_at: Mapped[Optional[datetime]] = mapped_column()
    first_failed_at: Mapped[Optional[datetime]] = mapped_column()
    last_status_changed_at: Mapped[Optional[datetime]] = mapped_column()
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failing_resource_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)

    control: Mapped[Control] = relationship(back_populates="current_state")
    last_run: Mapped[Optional[ControlRun]] = relationship(foreign_keys=[last_run_id])
