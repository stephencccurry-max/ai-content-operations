from unittest.mock import patch

import pytest

from app.errors import AppError

HEADERS = {"X-Internal-Token": "test-internal-token"}
PAYLOAD = {
    "topic": "咖啡因如何影响睡眠质量",
    "audience": "熬夜上班族",
    "goal": "education",
    "platforms": ["xiaohongshu"],
    "tone": "专业、实用",
}


def test_quota_error_recorded_as_failed_call(client, db_session):
    from sqlalchemy import select

    from app.infrastructure.db.models import ContentOutputSlot, ProviderCall

    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k-q"}
    ).json()["id"]
    err = AppError(
        "PROVIDER_QUOTA_EXCEEDED", "额度不足", status_code=429, retryable=False
    )
    with patch("app.domain.content.service.get_llm_provider") as mocked:
        mocked.return_value.generate_note.side_effect = err
        mocked.return_value.name = "zhipu"
        mocked.return_value.model = "glm-5.3"
        response = client.post(
            f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
        )
    assert response.status_code == 429
    call = db_session.scalars(select(ProviderCall)).all()[-1]
    assert call.status == "failed"
    assert call.error_code == "PROVIDER_QUOTA_EXCEEDED"
    slots = db_session.scalars(
        select(ContentOutputSlot).where(ContentOutputSlot.task_id == task_id)
    ).all()
    assert slots == []


@pytest.mark.parametrize(
    "code,status",
    [
        ("SEARCH_EMPTY", 502),
        ("PROVIDER_NOT_CONFIGURED", 503),
    ],
)
def test_search_error_recorded_as_failed_call(client, db_session, code, status):
    from sqlalchemy import select

    from app.infrastructure.db.models import ProviderCall

    task_id = client.post(
        "/api/v1/tasks",
        json=PAYLOAD,
        headers={"Idempotency-Key": f"k-search-{code}"},
    ).json()["id"]
    err = AppError(code, "search failed", status_code=status, retryable=True)
    with patch("app.domain.content.service.get_search_provider") as mocked:
        mocked.side_effect = err
        response = client.post(
            f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
        )
    assert response.status_code == status
    calls = db_session.scalars(select(ProviderCall)).all()
    assert len(calls) == 1
    assert calls[0].status == "failed"
    assert calls[0].error_code == code
