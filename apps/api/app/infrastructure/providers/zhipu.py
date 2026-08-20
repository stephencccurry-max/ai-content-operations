from __future__ import annotations

import json

from app.errors import AppError
from app.infrastructure.providers.http import request_json
from app.infrastructure.providers.llm import GenerateResult
from app.infrastructure.providers.search import SearchHit

NOTE_REQUIRED = ("title", "hook", "body", "cover_text", "hashtags", "factual_claims", "claim_source_map")
SCRIPT_REQUIRED = (
    "hook",
    "script",
    "estimated_duration_seconds",
    "scenes",
    "cta",
    "factual_claims",
    "claim_source_map",
)

NOTE_PROMPT = (
    "你是小红书图文作者。只输出一个 JSON 对象，不要 Markdown 解释。"
    "字段必须齐全：title, hook, body, cover_text, hashtags, factual_claims, claim_source_map。"
    "factual_claims 中的事实声明必须能在下方 sources 中找到对应 url；"
    "claim_source_map 为 [{claim, source_url}]。"
)

SCRIPT_PROMPT = (
    "你是抖音口播脚本作者。只输出一个 JSON 对象，不要 Markdown 解释。"
    "字段必须齐全：hook, script, estimated_duration_seconds, scenes, cta, factual_claims, claim_source_map。"
    "factual_claims 中的事实声明必须能在下方 sources 中找到对应 url；"
    "claim_source_map 为 [{claim, source_url}]。"
)


def _extract_json(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        raise AppError(
            "PROVIDER_INVALID_RESPONSE",
            "模型返回空内容",
            status_code=502,
            retryable=False,
        )
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            raw = "\n".join(lines[1:-1]).strip()
        else:
            raw = "\n".join(lines[1:]).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppError(
            "PROVIDER_INVALID_RESPONSE",
            "模型返回了非法 JSON",
            status_code=502,
            retryable=False,
        ) from exc
    if not isinstance(data, dict):
        raise AppError(
            "PROVIDER_INVALID_RESPONSE",
            "模型返回了非对象 JSON",
            status_code=502,
            retryable=False,
        )
    return data


def _validate_note(payload: dict) -> None:
    missing = [k for k in NOTE_REQUIRED if k not in payload]
    if missing or not str(payload.get("title") or "").strip() or not str(payload.get("body") or "").strip():
        raise AppError(
            "PROVIDER_INVALID_RESPONSE",
            "模型返回缺少必填字段或空标题/正文",
            status_code=502,
            retryable=False,
        )


def _validate_script(payload: dict) -> None:
    missing = [k for k in SCRIPT_REQUIRED if k not in payload]
    if missing or not str(payload.get("script") or "").strip():
        raise AppError(
            "PROVIDER_INVALID_RESPONSE",
            "模型返回缺少必填字段或空脚本",
            status_code=502,
            retryable=False,
        )


def _translate_http_error(exc: AppError) -> AppError:
    details = exc.details or {}
    snippet = str(details.get("body_snippet") or "")
    status = details.get("status_code")
    if '"code":"1113"' in snippet:
        return AppError(
            "PROVIDER_QUOTA_EXCEEDED",
            "模型额度不足",
            status_code=429,
            retryable=False,
        )
    if status == 401 or '"code":"1004"' in snippet:
        return AppError(
            "PROVIDER_AUTH_FAILED",
            "模型鉴权失败",
            status_code=401,
            retryable=False,
        )
    return exc


def _format_sources(sources: list[SearchHit]) -> str:
    if not sources:
        return "[]"
    items = [{"title": s.title, "url": s.url, "content": s.content} for s in sources]
    return json.dumps(items, ensure_ascii=False)


class ZhipuLLMProvider:
    name = "zhipu"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self.model = model
        self._timeout = timeout

    def generate_note(
        self, topic: str, audience: str, tone: str, sources: list[SearchHit]
    ) -> GenerateResult:
        user = (
            f"topic: {topic}\naudience: {audience}\ntone: {tone}\n"
            f"sources: {_format_sources(sources)}"
        )
        return self._complete(NOTE_PROMPT, user, _validate_note)

    def generate_script(
        self, topic: str, audience: str, tone: str, sources: list[SearchHit]
    ) -> GenerateResult:
        user = (
            f"topic: {topic}\naudience: {audience}\ntone: {tone}\n"
            f"sources: {_format_sources(sources)}"
        )
        return self._complete(SCRIPT_PROMPT, user, _validate_script)

    def _complete(
        self,
        system: str,
        user: str,
        validate,
    ) -> GenerateResult:
        url = f"{self._base_url}/chat/completions"
        try:
            data = request_json(
                "POST",
                url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.7,
                    "thinking": {"type": "disabled"},
                },
                timeout=self._timeout,
            )
        except AppError as exc:
            if exc.code == "PROVIDER_HTTP_ERROR":
                raise _translate_http_error(exc) from exc
            raise

        content = ""
        choices = data.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content") or ""
        payload = _extract_json(content)
        validate(payload)
        usage = data.get("usage") or {}
        return GenerateResult(
            payload=payload,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
        )
