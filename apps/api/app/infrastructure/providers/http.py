from typing import Any

import httpx

from app.errors import AppError

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def _raise_http(response: httpx.Response) -> None:
    snippet = (response.text or "")[:300]
    retryable = response.status_code in _RETRYABLE_STATUS
    raise AppError(
        "PROVIDER_HTTP_ERROR",
        f"外部服务 HTTP {response.status_code}",
        status_code=502,
        retryable=retryable,
        details={"status_code": response.status_code, "body_snippet": snippet},
    )


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    json: dict[str, Any],
    timeout: float,
) -> dict:
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.request(method, url, headers=headers, json=json)
            if response.status_code >= 400:
                if attempt == 0 and response.status_code in _RETRYABLE_STATUS:
                    last_exc = AppError(
                        "PROVIDER_HTTP_ERROR",
                        f"外部服务 HTTP {response.status_code}",
                        status_code=502,
                        retryable=True,
                    )
                    continue
                _raise_http(response)
            data = response.json()
            if not isinstance(data, dict):
                raise AppError(
                    "PROVIDER_INVALID_RESPONSE",
                    "外部服务返回了非对象 JSON",
                    status_code=502,
                    retryable=False,
                )
            return data
        except httpx.TimeoutException as exc:
            last_exc = exc
            if attempt == 0:
                continue
            raise AppError(
                "PROVIDER_TIMEOUT",
                "外部服务超时",
                status_code=504,
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                "PROVIDER_HTTP_ERROR",
                "外部服务网络错误",
                status_code=502,
                retryable=True,
            ) from exc
    if isinstance(last_exc, AppError):
        raise last_exc
    raise AppError("PROVIDER_HTTP_ERROR", "外部服务调用失败", status_code=502, retryable=True)
