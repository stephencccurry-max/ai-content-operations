import uuid

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.orm import Session

from app.application.idempotency import IdempotencyStore, request_fingerprint
from app.domain.tasks.service import (
    TaskCreate,
    create_task,
    get_task_detail,
    list_tasks,
    task_summary,
)
from app.infrastructure.db.session import get_session

router = APIRouter()


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
    body = task_summary(session, task).model_dump()
    store.remember(idempotency_key, endpoint, fingerprint, 201, body)
    session.commit()
    return body


@router.get("/tasks")
def get_tasks(session: Session = Depends(get_session)) -> dict:
    return {"items": [summary.model_dump() for summary in list_tasks(session)]}


@router.get("/tasks/{task_id}")
def get_task(task_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    return get_task_detail(session, task_id).model_dump()
