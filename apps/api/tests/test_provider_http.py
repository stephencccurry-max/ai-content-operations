from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.errors import AppError
from app.infrastructure.providers.http import request_json


def test_retries_once_on_timeout_then_succeeds():
    ok = httpx.Response(200, json={"ok": True})
    timed_out = httpx.TimeoutException("t")
    mock_client = MagicMock()
    mock_client.request.side_effect = [timed_out, ok]
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch("app.infrastructure.providers.http.httpx.Client", return_value=mock_client):
        body = request_json(
            "POST",
            "https://example.invalid/v1",
            headers={"Authorization": "Bearer secret-token"},
            json={"q": 1},
            timeout=1.0,
        )

    assert body == {"ok": True}
    assert mock_client.request.call_count == 2


def test_does_not_retry_auth_error():
    err = httpx.Response(401, json={"error": {"code": "1004", "message": "auth"}})
    mock_client = MagicMock()
    mock_client.request.return_value = err
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch("app.infrastructure.providers.http.httpx.Client", return_value=mock_client):
        with pytest.raises(AppError) as exc:
            request_json("POST", "https://example.invalid/v1", headers={}, json={}, timeout=1.0)

    assert exc.value.code == "PROVIDER_HTTP_ERROR"
    assert mock_client.request.call_count == 1
