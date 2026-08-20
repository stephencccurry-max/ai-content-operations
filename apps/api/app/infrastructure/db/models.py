import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = _created_at()


class ContentTask(Base):
    __tablename__ = "content_tasks"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    topic: Mapped[str] = mapped_column(Text())
    audience: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(String(50))
    tone: Mapped[str] = mapped_column(String(200))
    requirements: Mapped[str | None] = mapped_column(Text(), nullable=True)
    prohibited_items: Mapped[str | None] = mapped_column(Text(), nullable=True)
    current_step: Mapped[str | None] = mapped_column(String(50), nullable=True)
    needs_attention: Mapped[bool] = mapped_column(Boolean(), default=False)
    cancelled: Mapped[bool] = mapped_column(Boolean(), default=False)
    archived: Mapped[bool] = mapped_column(Boolean(), default=False)
    research_sources: Mapped[dict | list | None] = mapped_column(
        JSONB(), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TaskPlatform(Base):
    __tablename__ = "task_platforms"
    __table_args__ = (UniqueConstraint("task_id", "platform"),)

    id: Mapped[uuid.UUID] = _pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_tasks.id"))
    platform: Mapped[str] = mapped_column(String(30))
    content_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    last_error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = _pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_tasks.id"))
    workflow_key: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30))
    n8n_execution_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = _created_at()
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class WorkflowStepRun(Base):
    __tablename__ = "workflow_step_runs"
    __table_args__ = (UniqueConstraint("run_id", "step_key", "attempt"),)

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id"))
    step_key: Mapped[str] = mapped_column(String(50))
    attempt: Mapped[int] = mapped_column(Integer())
    status: Mapped[str] = mapped_column(String(30))
    retryable: Mapped[bool] = mapped_column(Boolean(), default=False)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime] = _created_at()
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ContentOutputSlot(Base):
    __tablename__ = "content_output_slots"
    __table_args__ = (UniqueConstraint("task_id", "platform", "content_type"),)

    id: Mapped[uuid.UUID] = _pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_tasks.id"))
    platform: Mapped[str] = mapped_column(String(30))
    content_type: Mapped[str] = mapped_column(String(30))
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()


class ContentOutputVersion(Base):
    __tablename__ = "content_output_versions"
    __table_args__ = (UniqueConstraint("slot_id", "version"),)

    id: Mapped[uuid.UUID] = _pk()
    slot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_output_slots.id"))
    version: Mapped[int] = mapped_column(Integer())
    status: Mapped[str] = mapped_column(String(30))
    has_blocking_issues: Mapped[bool] = mapped_column(Boolean(), default=False)
    title_snapshot: Mapped[str | None] = mapped_column(String(300), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSONB())
    based_on_brief_version: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    temperature: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    provider_call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    revision_count: Mapped[int] = mapped_column(Integer(), default=0)
    revision_of_version: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    created_at: Mapped[datetime] = _created_at()


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[uuid.UUID] = _pk()
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_output_versions.id")
    )
    decision: Mapped[str] = mapped_column(String(30))
    comment: Mapped[str | None] = mapped_column(Text(), nullable=True)
    human_verified: Mapped[bool] = mapped_column(Boolean(), default=False)
    actor: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = _created_at()


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = _pk()
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    actor: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(50))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB(), default=dict)
    created_at: Mapped[datetime] = _created_at()


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("key", "endpoint"),)

    id: Mapped[uuid.UUID] = _pk()
    key: Mapped[str] = mapped_column(String(200))
    endpoint: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(Integer())
    response_body: Mapped[dict] = mapped_column(JSONB())
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProviderCall(Base):
    __tablename__ = "provider_calls"

    id: Mapped[uuid.UUID] = _pk()
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    step_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer(), default=0)
    output_tokens: Mapped[int] = mapped_column(Integer(), default=0)
    latency_ms: Mapped[int] = mapped_column(Integer(), default=0)
    estimated_cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    status: Mapped[str] = mapped_column(String(30))
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = _created_at()
