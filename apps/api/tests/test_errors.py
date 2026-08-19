from app.errors import AppError


def test_app_error_is_rendered_as_error_envelope(client):
    app = client.app

    @app.get("/api/v1/boom")
    def boom():
        raise AppError("TASK_NOT_FOUND", "任务不存在", status_code=404)

    response = client.get("/api/v1/boom")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "TASK_NOT_FOUND"
    assert error["message"] == "任务不存在"
    assert error["retryable"] is False
    assert error["request_id"]
