import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import RunStatus, StepStatus
from app.errors import AppError
from app.infrastructure.db.models import ContentTask, WorkflowRun, WorkflowStepRun

_TERMINAL_RUN_STATUSES = frozenset(
    {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}
)


def claim_run(
    session: Session, task_id: uuid.UUID, n8n_execution_id: str | None
) -> WorkflowRun:
    task = session.scalar(
        select(ContentTask).where(ContentTask.id == task_id).with_for_update()
    )
    if task is None:
        raise AppError("TASK_NOT_FOUND", "任务不存在", status_code=404)

    existing = session.scalar(
        select(WorkflowRun)
        .where(
            WorkflowRun.task_id == task_id,
            WorkflowRun.status == RunStatus.RUNNING.value,
        )
        .with_for_update()
    )
    if existing is not None:
        raise AppError(
            "RUN_ALREADY_ACTIVE", "该任务已有一个进行中的运行", status_code=409
        )
    run = WorkflowRun(
        task_id=task_id,
        workflow_key="wf01_content_pipeline",
        status=RunStatus.RUNNING.value,
        n8n_execution_id=n8n_execution_id,
    )
    session.add(run)
    session.flush()
    return run


def start_step(
    session: Session, run_id: uuid.UUID, step_key: str
) -> WorkflowStepRun:
    run = session.scalar(
        select(WorkflowRun).where(WorkflowRun.id == run_id).with_for_update()
    )
    if run is None:
        raise AppError("RUN_NOT_FOUND", "运行不存在", status_code=404)

    last = session.scalar(
        select(func.max(WorkflowStepRun.attempt)).where(
            WorkflowStepRun.run_id == run_id, WorkflowStepRun.step_key == step_key
        )
    )
    step = WorkflowStepRun(
        run_id=run_id,
        step_key=step_key,
        attempt=(last or 0) + 1,
        status=StepStatus.RUNNING.value,
        heartbeat_at=datetime.now(UTC),
    )
    session.add(step)
    session.flush()
    return step


def _get_step(
    session: Session, run_id: uuid.UUID, step_key: str, attempt: int
) -> WorkflowStepRun:
    step = session.scalar(
        select(WorkflowStepRun).where(
            WorkflowStepRun.run_id == run_id,
            WorkflowStepRun.step_key == step_key,
            WorkflowStepRun.attempt == attempt,
        )
    )
    if step is None:
        raise AppError("STEP_NOT_FOUND", "步骤运行记录不存在", status_code=404)
    return step


def complete_step(
    session: Session, run_id: uuid.UUID, step_key: str, attempt: int
) -> WorkflowStepRun:
    step = _get_step(session, run_id, step_key, attempt)
    if step.status == StepStatus.SUCCEEDED.value:
        return step
    step.status = StepStatus.SUCCEEDED.value
    step.ended_at = datetime.now(UTC)
    session.flush()
    return step


def fail_step(
    session: Session,
    run_id: uuid.UUID,
    step_key: str,
    attempt: int,
    error_code: str,
    error_message: str,
    retryable: bool,
) -> WorkflowStepRun:
    step = _get_step(session, run_id, step_key, attempt)
    step.status = StepStatus.FAILED.value
    step.error_code = error_code
    step.error_message = error_message
    step.retryable = retryable
    step.ended_at = datetime.now(UTC)
    session.flush()
    return step


def finish_run(session: Session, run_id: uuid.UUID, status: RunStatus) -> WorkflowRun:
    if status not in _TERMINAL_RUN_STATUSES:
        raise AppError(
            "INVALID_RUN_STATUS",
            "运行只能结束为 succeeded、failed 或 cancelled",
            status_code=400,
        )

    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise AppError("RUN_NOT_FOUND", "运行不存在", status_code=404)
    run.status = status.value
    run.ended_at = datetime.now(UTC)
    session.flush()
    return run
