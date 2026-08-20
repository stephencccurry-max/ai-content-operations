import uuid

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.idempotency import IdempotencyStore, request_fingerprint
from app.domain.tasks.service import (
    TaskCreate,
    create_task,
    get_task_or_404,
    list_steps,
    task_status,
)
from app.infrastructure.db.models import (
    ContentOutputSlot,
    ContentTask,
    TaskPlatform,
)
from app.infrastructure.db.session import get_session

router = APIRouter()


def _summary(session: Session, task: ContentTask) -> dict:
    platforms = session.scalars(
        select(TaskPlatform.platform).where(TaskPlatform.task_id == task.id)
    ).all()
    return {
        "id": str(task.id),
        "topic": task.topic,
        "platforms": list(platforms),
        "status": task_status(session, task).value,
        "current_step": task.current_step,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


@router.post("/tasks", status_code=201)
async def post_task(
    request: Request,
    response: Response,
    payload: TaskCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> dict:
    endpoint = "/api/v1/tasks"
    fingerprint = request_fingerprint(endpoint, await request.body())
    store = IdempotencyStore(session)

    cached = store.lookup(idempotency_key, endpoint, fingerprint)
    if cached is not None:
        return cached

    task = create_task(session, payload)
    body = _summary(session, task)
    store.remember(idempotency_key, endpoint, fingerprint, 201, body)
    session.commit()
    return body


@router.get("/tasks")
def get_tasks(session: Session = Depends(get_session)) -> dict:
    tasks = session.scalars(
        select(ContentTask).order_by(ContentTask.updated_at.desc())
    ).all()
    return {"items": [_summary(session, t) for t in tasks]}


@router.get("/tasks/{task_id}")
def get_task(task_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    task = get_task_or_404(session, task_id)
    slots = session.scalars(
        select(ContentOutputSlot).where(ContentOutputSlot.task_id == task.id)
    ).all()
    return {
        **_summary(session, task),
        "audience": task.audience,
        "goal": task.goal,
        "tone": task.tone,
        "requirements": task.requirements,
        "steps": [
            {
                "step_key": s.step_key,
                "attempt": s.attempt,
                "status": s.status,
                "error_code": s.error_code,
                "error_message": s.error_message,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            }
            for s in list_steps(session, task.id)
        ],
        "output_slots": [
            {
                "id": str(s.id),
                "platform": s.platform,
                "content_type": s.content_type,
                "current_version_id": str(s.current_version_id)
                if s.current_version_id
                else None,
            }
            for s in slots
        ],
    }
