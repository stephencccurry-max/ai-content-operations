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


def test_internal_endpoint_requires_token(client, task_id):
    response = client.post(f"/internal/v1/tasks/{task_id}/runs", json={})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INTERNAL_AUTH_REQUIRED"


def test_claim_run_creates_running_run(client, task_id):
    response = client.post(
        f"/internal/v1/tasks/{task_id}/runs",
        json={"n8n_execution_id": "exec-1"},
        headers=HEADERS,
    )

    assert response.status_code == 201
    assert response.json()["status"] == "running"


def test_step_attempt_increments_on_each_start(client, task_id):
    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS
    ).json()["id"]

    first = client.post(
        f"/internal/v1/runs/{run_id}/steps/research/start", headers=HEADERS
    ).json()
    second = client.post(
        f"/internal/v1/runs/{run_id}/steps/research/start", headers=HEADERS
    ).json()

    assert first["attempt"] == 1
    assert second["attempt"] == 2


def test_task_status_becomes_running_after_run_claimed(client, task_id):
    client.post(f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS)

    assert client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "running"


def test_failed_step_records_error_and_marks_run_failed(client, task_id):
    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS
    ).json()["id"]
    client.post(f"/internal/v1/runs/{run_id}/steps/research/start", headers=HEADERS)
    client.post(
        f"/internal/v1/runs/{run_id}/steps/research/fail",
        json={
            "attempt": 1,
            "error_code": "PROVIDER_TIMEOUT",
            "error_message": "模型服务超时",
            "retryable": True,
        },
        headers=HEADERS,
    )
    client.post(
        f"/internal/v1/runs/{run_id}/finish", json={"status": "failed"}, headers=HEADERS
    )

    detail = client.get(f"/api/v1/tasks/{task_id}").json()

    assert detail["status"] == "failed"
    assert detail["steps"][0]["error_code"] == "PROVIDER_TIMEOUT"
