HEADERS = {"X-Internal-Token": "test-internal-token"}
PAYLOAD = {
    "topic": "咖啡因如何影响睡眠质量",
    "audience": "熬夜上班族",
    "goal": "education",
    "platforms": ["xiaohongshu"],
    "tone": "专业、实用",
}


def test_full_pipeline_sequence_reaches_awaiting_review(client):
    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k"}
    ).json()["id"]

    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs",
        json={"n8n_execution_id": "exec-42"},
        headers=HEADERS,
    ).json()["id"]

    step = client.post(
        f"/internal/v1/runs/{run_id}/steps/generate_xiaohongshu/start",
        headers=HEADERS,
    ).json()
    client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    )
    client.post(
        f"/internal/v1/runs/{run_id}/steps/generate_xiaohongshu/complete",
        json={"attempt": step["attempt"]},
        headers=HEADERS,
    )
    client.post(
        f"/internal/v1/runs/{run_id}/finish",
        json={"status": "succeeded"},
        headers=HEADERS,
    )

    detail = client.get(f"/api/v1/tasks/{task_id}").json()

    assert detail["status"] == "awaiting_review"
    assert detail["steps"][0]["status"] == "succeeded"
    assert len(detail["output_slots"]) == 1


def test_duplicate_complete_callback_is_idempotent(client):
    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k2"}
    ).json()["id"]
    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS
    ).json()["id"]
    step = client.post(
        f"/internal/v1/runs/{run_id}/steps/generate_xiaohongshu/start", headers=HEADERS
    ).json()

    first = client.post(
        f"/internal/v1/runs/{run_id}/steps/generate_xiaohongshu/complete",
        json={"attempt": step["attempt"]},
        headers=HEADERS,
    )
    second = client.post(
        f"/internal/v1/runs/{run_id}/steps/generate_xiaohongshu/complete",
        json={"attempt": step["attempt"]},
        headers=HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "succeeded"


def test_current_step_reflects_latest_started_step(client):
    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k3"}
    ).json()["id"]
    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS
    ).json()["id"]
    client.post(
        f"/internal/v1/runs/{run_id}/steps/generate_xiaohongshu/start", headers=HEADERS
    )

    assert (
        client.get(f"/api/v1/tasks/{task_id}").json()["current_step"]
        == "generate_xiaohongshu"
    )
