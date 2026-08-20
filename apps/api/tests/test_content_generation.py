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
def task_id(client):
    return client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k"}
    ).json()["id"]


def test_generate_creates_slot_and_first_version(client, task_id):
    response = client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    )

    assert response.status_code == 201
    body = response.json()
    assert body["version"] == 1
    assert body["status"] == "awaiting_review"


def test_generated_payload_has_required_fields(client, task_id):
    version = client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    ).json()
    slot = client.get(f"/api/v1/output-slots/{version['slot_id']}").json()

    payload = slot["versions"][0]["payload"]
    assert set(payload) >= {
        "title",
        "hook",
        "body",
        "cover_text",
        "hashtags",
        "factual_claims",
        "claim_source_map",
    }
    assert payload["title"]


def test_generation_records_provider_call(client, task_id, db_session):
    from sqlalchemy import select

    from app.infrastructure.db.models import ProviderCall

    client.post(f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS)
    calls = db_session.scalars(select(ProviderCall)).all()

    providers = {c.provider for c in calls}
    assert "mock" in providers
    assert "mock-search" in providers
    assert all(c.status == "succeeded" for c in calls)


def test_two_platforms_search_once(client, db_session):
    from sqlalchemy import select

    from app.infrastructure.db.models import ProviderCall

    payload = {
        **PAYLOAD,
        "platforms": ["xiaohongshu", "douyin"],
    }
    task_id = client.post(
        "/api/v1/tasks", json=payload, headers={"Idempotency-Key": "k-dual"}
    ).json()["id"]
    client.post(f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS)
    client.post(f"/internal/v1/tasks/{task_id}/generate/douyin", headers=HEADERS)
    providers = [c.provider for c in db_session.scalars(select(ProviderCall)).all()]
    assert providers.count("mock-search") == 1
    assert providers.count("mock") == 2


def test_version_records_model_and_prompt_version(client, task_id):
    version = client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    ).json()
    slot = client.get(f"/api/v1/output-slots/{version['slot_id']}").json()

    assert slot["versions"][0]["model"]
    assert slot["versions"][0]["prompt_version"]


def test_manual_version_increments_and_becomes_current(client, task_id):
    generated = client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    ).json()
    slot_id = generated["slot_id"]

    created = client.post(
        f"/api/v1/output-slots/{slot_id}/versions",
        json={"payload": {"title": "人工改过的标题", "body": "正文", "hashtags": []}},
    ).json()
    slot = client.get(f"/api/v1/output-slots/{slot_id}").json()

    assert created["version"] == 2
    assert slot["current_version_id"] == created["id"]


def test_task_status_is_awaiting_review_after_generation(client, task_id):
    client.post(f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS)
    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS
    ).json()["id"]
    client.post(
        f"/internal/v1/runs/{run_id}/finish",
        json={"status": "succeeded"},
        headers=HEADERS,
    )

    assert client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "awaiting_review"
