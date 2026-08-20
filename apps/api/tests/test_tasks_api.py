PAYLOAD = {
    "topic": "咖啡因如何影响睡眠质量",
    "audience": "熬夜上班族",
    "goal": "education",
    "platforms": ["xiaohongshu"],
    "tone": "专业、实用",
}


def _create(client, payload=None, key="key-1"):
    return client.post(
        "/api/v1/tasks",
        json=payload or PAYLOAD,
        headers={"Idempotency-Key": key},
    )


def test_create_task_returns_queued_task(client):
    response = _create(client)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["topic"] == PAYLOAD["topic"]
    assert body["platforms"] == ["xiaohongshu"]


def test_create_task_rejects_short_topic(client):
    response = _create(client, {**PAYLOAD, "topic": "太短"})

    assert response.status_code == 422


def test_create_task_requires_at_least_one_platform(client):
    response = _create(client, {**PAYLOAD, "platforms": []})

    assert response.status_code == 422


def test_create_task_rejects_duplicate_platforms(client):
    response = _create(
        client,
        {**PAYLOAD, "platforms": ["xiaohongshu", "xiaohongshu"]},
    )

    assert response.status_code == 422


def test_repeated_idempotency_key_returns_same_task(client):
    first = _create(client)
    second = _create(client)

    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]


def test_create_task_writes_audit_event(client, db_session):
    from sqlalchemy import select

    from app.infrastructure.db.models import AuditEvent

    task_id = _create(client).json()["id"]
    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.action == "task.created")
    ).all()

    assert [str(e.task_id) for e in events] == [task_id]


def test_task_list_is_ordered_by_updated_at_desc(client):
    first = _create(client, key="k-a").json()["id"]
    second = _create(client, {**PAYLOAD, "topic": "另一个足够长的主题内容"}, key="k-b")

    ids = [t["id"] for t in client.get("/api/v1/tasks").json()["items"]]

    assert ids == [second.json()["id"], first]


def test_task_detail_includes_steps_and_slots(client):
    task_id = _create(client).json()["id"]

    body = client.get(f"/api/v1/tasks/{task_id}").json()

    assert body["status"] == "queued"
    assert body["steps"] == []
    assert body["output_slots"] == []


def test_task_detail_includes_prohibited_items(client):
    prohibited = "禁止提及竞品品牌"
    task_id = _create(client, {**PAYLOAD, "prohibited_items": prohibited}).json()["id"]

    body = client.get(f"/api/v1/tasks/{task_id}").json()

    assert body["prohibited_items"] == prohibited


def test_unknown_task_returns_error_envelope(client):
    response = client.get("/api/v1/tasks/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"
