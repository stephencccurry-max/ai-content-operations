from unittest.mock import patch

import pytest

from app.errors import AppError
from app.infrastructure.providers.search import SearchHit
from app.infrastructure.providers.zhipu import ZhipuLLMProvider

SOURCES = [SearchHit("睡眠", "https://example.com/a", "咖啡因会推迟入睡。")]


def test_zhipu_parses_note_json_and_usage():
    provider = ZhipuLLMProvider(
        api_key="k",
        base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        model="glm-5.3",
        timeout=1.0,
    )
    note = {
        "title": "标题",
        "hook": "钩子",
        "body": "正文",
        "cover_text": "封面",
        "hashtags": ["a"],
        "factual_claims": ["咖啡因会推迟入睡"],
        "claim_source_map": [{"claim": "咖啡因会推迟入睡", "source_url": "https://example.com/a"}],
    }
    api = {
        "choices": [{"message": {"content": "```json\n" + __import__("json").dumps(note, ensure_ascii=False) + "\n```"}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 22},
    }
    with patch("app.infrastructure.providers.zhipu.request_json", return_value=api) as mocked:
        result = provider.generate_note("咖啡因如何影响睡眠质量", "熬夜上班族", "专业", SOURCES)

    assert result.payload["title"] == "标题"
    assert result.input_tokens == 11
    assert result.output_tokens == 22
    sent = mocked.call_args.kwargs["json"]
    assert sent["model"] == "glm-5.3"
    assert sent["thinking"] == {"type": "disabled"}


def test_zhipu_maps_quota_error():
    provider = ZhipuLLMProvider(
        api_key="k",
        base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        model="glm-5.3",
        timeout=1.0,
    )
    err = AppError(
        "PROVIDER_HTTP_ERROR",
        "外部服务 HTTP 429",
        status_code=502,
        details={"status_code": 429, "body_snippet": '{"error":{"code":"1113"}}'},
    )
    with patch("app.infrastructure.providers.zhipu.request_json", side_effect=err):
        with pytest.raises(AppError) as exc:
            provider.generate_note("咖啡因如何影响睡眠质量", "受众两", "专业", SOURCES)
    assert exc.value.code == "PROVIDER_QUOTA_EXCEEDED"
