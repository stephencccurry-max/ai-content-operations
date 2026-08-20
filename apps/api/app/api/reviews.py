import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.content import serialize_version
from app.domain.enums import VersionStatus
from app.domain.review.service import review_version
from app.infrastructure.db.models import ContentOutputVersion
from app.infrastructure.db.session import get_session

router = APIRouter()


class ReviewRequest(BaseModel):
    version: int
    decision: str
    comment: str | None = None
    human_verified: bool = False


@router.post("/output-versions/{version_id}/review")
def post_review(
    version_id: uuid.UUID,
    payload: ReviewRequest,
    session: Session = Depends(get_session),
) -> dict:
    version = review_version(
        session,
        version_id,
        payload.version,
        payload.decision,
        payload.comment,
        payload.human_verified,
    )
    session.commit()
    return serialize_version(version)


@router.get("/reviews")
def get_reviews(session: Session = Depends(get_session)) -> dict:
    versions = session.scalars(
        select(ContentOutputVersion)
        .where(ContentOutputVersion.status == VersionStatus.AWAITING_REVIEW.value)
        .order_by(ContentOutputVersion.created_at)
    ).all()
    return {"items": [serialize_version(v) for v in versions]}
