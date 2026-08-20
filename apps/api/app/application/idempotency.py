import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.infrastructure.db.models import IdempotencyKey

TTL = timedelta(hours=24)


def request_fingerprint(endpoint: str, body: bytes) -> str:
    return hashlib.sha256(endpoint.encode("utf-8") + b"|" + body).hexdigest()


class IdempotencyStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lookup(self, key: str, endpoint: str, fingerprint: str) -> dict | None:
        record = self._session.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.key == key, IdempotencyKey.endpoint == endpoint
            )
        )
        if record is None:
            return None
        if record.request_hash != fingerprint:
            raise AppError(
                "IDEMPOTENCY_KEY_REUSED",
                "相同的幂等键被用于不同的请求内容",
                status_code=409,
            )
        return record.response_body

    def remember(
        self,
        key: str,
        endpoint: str,
        fingerprint: str,
        status: int,
        body: dict,
    ) -> None:
        self._session.add(
            IdempotencyKey(
                key=key,
                endpoint=endpoint,
                request_hash=fingerprint,
                response_status=status,
                response_body=body,
                expires_at=datetime.now(UTC) + TTL,
            )
        )
        self._session.flush()
