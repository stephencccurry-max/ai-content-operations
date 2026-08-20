import uuid

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ContentType, Platform, RunStatus, VersionStatus
from app.domain.tasks.status import derive_task_status
from app.errors import AppError
from app.infrastructure.db.models import (
    AuditEvent,
    ContentOutputSlot,
    ContentOutputVersion,
    ContentTask,
    Project,
    ReviewDecision,
    TaskPlatform,
    WorkflowRun,
    WorkflowStepRun,
)

DEFAULT_PROJECT_NAME = "默认项目"

CONTENT_TYPE_BY_PLATFORM = {
    Platform.XIAOHONGSHU: ContentType.NOTE,
    Platform.DOUYIN: ContentType.SCRIPT,
}


class TaskCreate(BaseModel):
    topic: str = Field(min_length=5, max_length=300)
    audience: str = Field(min_length=2, max_length=200)
    goal: str
    platforms: list[Platform] = Field(min_length=1)
    tone: str = Field(min_length=1, max_length=200)
    requirements: str | None = Field(default=None, max_length=1000)
    prohibited_items: str | None = Field(default=None, max_length=1000)

    @field_validator("platforms")
    @classmethod
    def platforms_must_be_unique(cls, platforms: list[Platform]) -> list[Platform]:
        if len(platforms) != len(set(platforms)):
            raise ValueError("platforms must contain unique values")
        return platforms


class TaskStepSummary(BaseModel):
    step_key: str
    attempt: int
    status: str
    error_code: str | None
    error_message: str | None
    started_at: str
    ended_at: str | None


class TaskOutputSlotSummary(BaseModel):
    id: str
    platform: str
    content_type: str
    current_version_id: str | None


class TaskSummary(BaseModel):
    id: str
    topic: str
    platforms: list[str]
    status: str
    current_step: str | None
    created_at: str
    updated_at: str


class TaskDetail(TaskSummary):
    audience: str
    goal: str
    tone: str
    requirements: str | None
    prohibited_items: str | None
    steps: list[TaskStepSummary]
    output_slots: list[TaskOutputSlotSummary]


def ensure_default_project(session: Session) -> Project:
    project = session.scalar(select(Project).limit(1))
    if project is None:
        project = Project(name=DEFAULT_PROJECT_NAME)
        session.add(project)
        session.flush()
    return project


def create_task(session: Session, payload: TaskCreate) -> ContentTask:
    project = ensure_default_project(session)
    task = ContentTask(
        project_id=project.id,
        topic=payload.topic,
        audience=payload.audience,
        goal=payload.goal,
        tone=payload.tone,
        requirements=payload.requirements,
        prohibited_items=payload.prohibited_items,
    )
    session.add(task)
    session.flush()

    for platform in payload.platforms:
        session.add(
            TaskPlatform(
                task_id=task.id,
                platform=platform.value,
                content_type=CONTENT_TYPE_BY_PLATFORM[platform].value,
            )
        )

    session.add(
        AuditEvent(
            task_id=task.id,
            actor="local_admin",
            action="task.created",
            entity_type="content_task",
            entity_id=task.id,
            metadata_json={"platforms": [p.value for p in payload.platforms]},
        )
    )
    session.flush()
    return task


def _active_run(session: Session, task_id: uuid.UUID) -> WorkflowRun | None:
    return session.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.task_id == task_id)
        .order_by(WorkflowRun.started_at.desc())
        .limit(1)
    )


def _current_version_statuses(
    session: Session, task_id: uuid.UUID
) -> list[VersionStatus]:
    rows = session.execute(
        select(ContentOutputVersion.status)
        .join(ContentOutputSlot, ContentOutputSlot.current_version_id == ContentOutputVersion.id)
        .where(ContentOutputSlot.task_id == task_id)
    ).all()
    return [VersionStatus(row[0]) for row in rows]


def _has_change_requests(session: Session, task_id: uuid.UUID) -> bool:
    rows = session.execute(
        select(ReviewDecision.version_id, ReviewDecision.decision)
        .join(
            ContentOutputVersion,
            ContentOutputVersion.id == ReviewDecision.version_id,
        )
        .join(
            ContentOutputSlot,
            ContentOutputSlot.current_version_id == ContentOutputVersion.id,
        )
        .where(ContentOutputSlot.task_id == task_id)
        .order_by(ReviewDecision.created_at)
    ).all()
    latest_by_version = {row.version_id: row.decision for row in rows}
    return "request_changes" in latest_by_version.values()


def task_status(session: Session, task: ContentTask):
    run = _active_run(session, task.id)
    expected = len(
        session.scalars(
            select(TaskPlatform.id).where(TaskPlatform.task_id == task.id)
        ).all()
    )
    return derive_task_status(
        run_status=RunStatus(run.status) if run else None,
        version_statuses=_current_version_statuses(session, task.id),
        expected_platform_count=expected,
        needs_attention=task.needs_attention,
        cancelled=task.cancelled,
        archived=task.archived,
        has_change_requests=_has_change_requests(session, task.id),
    )


def get_task_or_404(session: Session, task_id: uuid.UUID) -> ContentTask:
    task = session.get(ContentTask, task_id)
    if task is None:
        raise AppError("TASK_NOT_FOUND", "任务不存在", status_code=404)
    return task


def list_steps(session: Session, task_id: uuid.UUID) -> list[WorkflowStepRun]:
    return list(
        session.scalars(
            select(WorkflowStepRun)
            .join(WorkflowRun, WorkflowRun.id == WorkflowStepRun.run_id)
            .where(WorkflowRun.task_id == task_id)
            .order_by(WorkflowStepRun.started_at)
        ).all()
    )


def _task_summary(session: Session, task: ContentTask) -> TaskSummary:
    platforms = session.scalars(
        select(TaskPlatform.platform).where(TaskPlatform.task_id == task.id)
    ).all()
    return TaskSummary(
        id=str(task.id),
        topic=task.topic,
        platforms=list(platforms),
        status=task_status(session, task).value,
        current_step=task.current_step,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
    )


def task_summary(session: Session, task: ContentTask) -> TaskSummary:
    return _task_summary(session, task)


def list_tasks(session: Session) -> list[TaskSummary]:
    tasks = session.scalars(
        select(ContentTask).order_by(ContentTask.updated_at.desc())
    ).all()
    return [_task_summary(session, task) for task in tasks]


def get_task_detail(session: Session, task_id: uuid.UUID) -> TaskDetail:
    task = get_task_or_404(session, task_id)
    summary = _task_summary(session, task)
    slots = session.scalars(
        select(ContentOutputSlot).where(ContentOutputSlot.task_id == task.id)
    ).all()
    return TaskDetail(
        **summary.model_dump(),
        audience=task.audience,
        goal=task.goal,
        tone=task.tone,
        requirements=task.requirements,
        prohibited_items=task.prohibited_items,
        steps=[
            TaskStepSummary(
                step_key=step.step_key,
                attempt=step.attempt,
                status=step.status,
                error_code=step.error_code,
                error_message=step.error_message,
                started_at=step.started_at.isoformat(),
                ended_at=step.ended_at.isoformat() if step.ended_at else None,
            )
            for step in list_steps(session, task.id)
        ],
        output_slots=[
            TaskOutputSlotSummary(
                id=str(slot.id),
                platform=slot.platform,
                content_type=slot.content_type,
                current_version_id=str(slot.current_version_id)
                if slot.current_version_id
                else None,
            )
            for slot in slots
        ],
    )
