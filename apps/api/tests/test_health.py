def test_health_returns_ok_and_version(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_version"]


def test_health_response_carries_request_id_header(client):
    response = client.get("/api/v1/health")

    assert response.headers["x-request-id"]
