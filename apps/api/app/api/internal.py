import uuid

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.domain.enums import RunStatus
from app.domain.runs.service import (
    claim_run,
    complete_step,
    fail_step,
    finish_run,
    start_step,
)
from app.errors import AppError
from app.infrastructure.db.session import get_session

router = APIRouter()


def require_internal_token(
    x_internal_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if x_internal_token != settings.internal_api_token:
        raise AppError(
            "INTERNAL_AUTH_REQUIRED", "缺少或错误的内部调用凭据", status_code=401
        )


class ClaimRunRequest(BaseModel):
    n8n_execution_id: str | None = None


class StepResultRequest(BaseModel):
    attempt: int


class StepFailureRequest(StepResultRequest):
    error_code: str
    error_message: str
    retryable: bool = False


class FinishRunRequest(BaseModel):
    status: RunStatus


@router.post("/tasks/{task_id}/runs", status_code=201)
def post_run(
    task_id: uuid.UUID,
    payload: ClaimRunRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_internal_token),
) -> dict:
    run = claim_run(session, task_id, payload.n8n_execution_id)
    session.commit()
    return {"id": str(run.id), "status": run.status}


@router.post("/runs/{run_id}/steps/{step_key}/start")
def post_step_start(
    run_id: uuid.UUID,
    step_key: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_internal_token),
) -> dict:
    step = start_step(session, run_id, step_key)
    session.commit()
    return {"step_key": step.step_key, "attempt": step.attempt, "status": step.status}


@router.post("/runs/{run_id}/steps/{step_key}/complete")
def post_step_complete(
    run_id: uuid.UUID,
    step_key: str,
    payload: StepResultRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_internal_token),
) -> dict:
    step = complete_step(session, run_id, step_key, payload.attempt)
    session.commit()
    return {"step_key": step.step_key, "attempt": step.attempt, "status": step.status}


@router.post("/runs/{run_id}/steps/{step_key}/fail")
def post_step_fail(
    run_id: uuid.UUID,
    step_key: str,
    payload: StepFailureRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_internal_token),
) -> dict:
    step = fail_step(
        session,
        run_id,
        step_key,
        payload.attempt,
        payload.error_code,
        payload.error_message,
        payload.retryable,
    )
    session.commit()
    return {"step_key": step.step_key, "attempt": step.attempt, "status": step.status}


@router.post("/runs/{run_id}/finish")
def post_run_finish(
    run_id: uuid.UUID,
    payload: FinishRunRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_internal_token),
) -> dict:
    run = finish_run(session, run_id, payload.status)
    session.commit()
    return {"id": str(run.id), "status": run.status}
