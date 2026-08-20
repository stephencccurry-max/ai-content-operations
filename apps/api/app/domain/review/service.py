import uuid

from sqlalchemy.orm import Session

from app.domain.enums import VersionStatus
from app.errors import AppError
from app.infrastructure.db.models import (
    AuditEvent,
    ContentOutputSlot,
    ContentOutputVersion,
    ReviewDecision,
)

DECISION_TO_STATUS = {
    "approve": VersionStatus.APPROVED,
    "reject": VersionStatus.REJECTED,
    "request_changes": VersionStatus.AWAITING_REVIEW,
}


def review_version(
    session: Session,
    version_id: uuid.UUID,
    expected_version: int,
    decision: str,
    comment: str | None,
    human_verified: bool,
) -> ContentOutputVersion:
    version = session.get(ContentOutputVersion, version_id)
    if version is None:
        raise AppError("VERSION_NOT_FOUND", "内容版本不存在", status_code=404)
    if decision not in DECISION_TO_STATUS:
        raise AppError("UNKNOWN_DECISION", "不支持的审核动作", status_code=422)
    if version.version != expected_version:
        raise AppError(
            "VERSION_CONFLICT",
            "页面上的版本已过期，请刷新后重新审核",
            status_code=409,
        )
    if version.status == VersionStatus.APPROVED.value:
        raise AppError(
            "VERSION_IMMUTABLE", "已批准的版本不可再次评审", status_code=409
        )
    if decision in {"reject", "request_changes"} and not comment:
        raise AppError(
            "REVIEW_COMMENT_REQUIRED", "驳回或请求修改必须填写原因", status_code=422
        )
    if decision == "approve" and version.has_blocking_issues and not human_verified:
        raise AppError(
            "BLOCKING_ISSUES_PRESENT",
            "该版本存在阻断问题，需先处理或勾选人工已核对",
            status_code=422,
        )

    version.status = DECISION_TO_STATUS[decision].value
    session.add(
        ReviewDecision(
            version_id=version.id,
            decision=decision,
            comment=comment,
            human_verified=human_verified,
            actor="local_admin",
        )
    )
    slot = session.get(ContentOutputSlot, version.slot_id)
    session.add(
        AuditEvent(
            task_id=slot.task_id if slot else None,
            actor="local_admin",
            action=f"version.{DECISION_TO_STATUS[decision].value}",
            entity_type="content_output_version",
            entity_id=version.id,
            metadata_json={"human_verified": human_verified, "comment": comment},
        )
    )
    session.flush()
    return version
