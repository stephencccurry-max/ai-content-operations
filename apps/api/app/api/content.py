import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.content.service import create_manual_version
from app.errors import AppError
from app.infrastructure.db.models import ContentOutputSlot, ContentOutputVersion
from app.infrastructure.db.session import get_session

router = APIRouter()


class ManualVersionRequest(BaseModel):
    payload: dict


def serialize_version(version: ContentOutputVersion) -> dict:
    return {
        "id": str(version.id),
        "slot_id": str(version.slot_id),
        "version": version.version,
        "status": version.status,
        "has_blocking_issues": version.has_blocking_issues,
        "title_snapshot": version.title_snapshot,
        "payload": version.payload_json,
        "model": version.model,
        "prompt_version": version.prompt_version,
        "created_at": version.created_at.isoformat(),
    }


@router.get("/output-slots/{slot_id}")
def get_slot(slot_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    slot = session.get(ContentOutputSlot, slot_id)
    if slot is None:
        raise AppError("SLOT_NOT_FOUND", "内容位不存在", status_code=404)
    versions = session.scalars(
        select(ContentOutputVersion)
        .where(ContentOutputVersion.slot_id == slot_id)
        .order_by(ContentOutputVersion.version)
    ).all()
    return {
        "id": str(slot.id),
        "task_id": str(slot.task_id),
        "platform": slot.platform,
        "content_type": slot.content_type,
        "current_version_id": str(slot.current_version_id)
        if slot.current_version_id
        else None,
        "versions": [serialize_version(v) for v in versions],
    }


@router.post("/output-slots/{slot_id}/versions", status_code=201)
def post_version(
    slot_id: uuid.UUID,
    payload: ManualVersionRequest,
    session: Session = Depends(get_session),
) -> dict:
    version = create_manual_version(session, slot_id, payload.payload)
    session.commit()
    return serialize_version(version)
