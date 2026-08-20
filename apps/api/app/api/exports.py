import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.domain.enums import VersionStatus
from app.errors import AppError
from app.infrastructure.db.models import (
    ContentOutputSlot,
    ContentOutputVersion,
    ContentTask,
)
from app.infrastructure.db.session import get_session
from app.infrastructure.exporters.markdown import render_markdown, write_export

router = APIRouter()


@router.post("/output-versions/{version_id}/export", status_code=201)
def post_export(
    version_id: uuid.UUID,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    version = session.get(ContentOutputVersion, version_id)
    if version is None:
        raise AppError("VERSION_NOT_FOUND", "内容版本不存在", status_code=404)
    if version.status != VersionStatus.APPROVED.value:
        raise AppError(
            "VERSION_NOT_APPROVED", "只有已批准的版本可以导出", status_code=422
        )
    slot = session.get(ContentOutputSlot, version.slot_id)
    task = session.get(ContentTask, slot.task_id)

    content = render_markdown(task, slot, version)
    path = write_export(
        settings.export_dir, f"{task.id}-{slot.platform}", version, content
    )
    return {"file_path": str(path), "version": version.version}
