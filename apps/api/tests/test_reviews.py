import pytest

HEADERS = {"X-Internal-Token": "test-internal-token"}
PAYLOAD = {
    "topic": "咖啡因如何影响睡眠质量",
    "audience": "熬夜上班族",
    "goal": "education",
    "platforms": ["xiaohongshu"],
    "tone": "专业、实用",
}


@pytest.fixture()
def version(client):
    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k"}
    ).json()["id"]
    return client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    ).json()


def test_approve_marks_version_approved(client, version):
    response = client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "approve"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_approve_with_stale_version_number_conflicts(client, version):
    response = client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 99, "decision": "approve"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_approved_version_cannot_be_reviewed_again(client, version):
    client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "approve"},
    )
    second = client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "reject", "comment": "反悔"},
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "VERSION_IMMUTABLE"


def test_reject_requires_comment(client, version):
    response = client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "reject"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REVIEW_COMMENT_REQUIRED"


def test_blocking_issues_prevent_approval_without_human_verification(
    client, version, db_session
):
    from app.infrastructure.db.models import ContentOutputVersion

    row = db_session.get(ContentOutputVersion, version["id"])
    row.has_blocking_issues = True
    db_session.commit()

    response = client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "approve"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "BLOCKING_ISSUES_PRESENT"


def test_human_verified_flag_allows_approval_and_is_audited(
    client, version, db_session
):
    from sqlalchemy import select

    from app.infrastructure.db.models import AuditEvent, ContentOutputVersion

    row = db_session.get(ContentOutputVersion, version["id"])
    row.has_blocking_issues = True
    db_session.commit()

    response = client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "approve", "human_verified": True},
    )
    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.action == "version.approved")
    ).all()

    assert response.status_code == 200
    assert events[0].metadata_json["human_verified"] is True


def test_review_queue_lists_awaiting_versions(client, version):
    items = client.get("/api/v1/reviews").json()["items"]

    assert [i["id"] for i in items] == [version["id"]]


def test_request_changes_moves_task_to_changes_requested(client):
    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k-cr"}
    ).json()["id"]
    version = client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    ).json()
    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS
    ).json()["id"]
    client.post(
        f"/internal/v1/runs/{run_id}/finish",
        json={"status": "succeeded"},
        headers=HEADERS,
    )

    client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "request_changes", "comment": "标题太夸张"},
    )

    assert (
        client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "changes_requested"
    )
