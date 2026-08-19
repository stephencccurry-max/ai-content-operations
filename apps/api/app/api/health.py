from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get("/health")
def health(
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict:
    try:
        session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "error"
    return {"status": "ok", "app_version": settings.app_version, "database": database}
