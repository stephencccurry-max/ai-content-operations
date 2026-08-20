from dataclasses import dataclass
from typing import Protocol

from app.config import get_settings
from app.errors import AppError
from app.infrastructure.providers.search import SearchHit

PROMPT_VERSION = "xiaohongshu.v1"
NOTE_PROMPT_VERSION = "xiaohongshu.v2"
SCRIPT_PROMPT_VERSION = "douyin.v1"


@dataclass
class GenerateResult:
    payload: dict
    input_tokens: int
    output_tokens: int


class LLMProvider(Protocol):
    name: str
    model: str

    def generate_note(
        self, topic: str, audience: str, tone: str, sources: list[SearchHit]
    ) -> GenerateResult: ...

    def generate_script(
        self, topic: str, audience: str, tone: str, sources: list[SearchHit]
    ) -> GenerateResult: ...


class MockLLMProvider:
    name = "mock"
    model = "mock-writer-1"

    def generate_note(
        self, topic: str, audience: str, tone: str, sources: list[SearchHit]
    ) -> GenerateResult:
        claim_source_map = (
            [{"claim": sources[0].content, "source_url": sources[0].url}] if sources else []
        )
        return GenerateResult(
            payload={
                "title": f"{topic}：写给{audience}的 5 分钟版本",
                "hook": f"如果你也被「{topic}」困扰，这篇讲清楚了。",
                "body": (
                    f"面向{audience}，语气{tone}。\n\n"
                    "这是 M1 阶段由 Mock Provider 生成的占位正文，"
                    "用于验证任务、版本、审核与导出链路，不代表真实内容质量。"
                ),
                "cover_text": topic[:12],
                "hashtags": ["自我提升", "效率"],
                "factual_claims": [sources[0].content] if sources else [],
                "claim_source_map": claim_source_map,
            },
            input_tokens=0,
            output_tokens=0,
        )

    def generate_script(
        self, topic: str, audience: str, tone: str, sources: list[SearchHit]
    ) -> GenerateResult:
        claim_source_map = (
            [{"claim": sources[0].content, "source_url": sources[0].url}] if sources else []
        )
        return GenerateResult(
            payload={
                "hook": f"三句话讲明白{topic}",
                "script": f"面向{audience}的口播占位脚本，语气{tone}。",
                "estimated_duration_seconds": 45,
                "scenes": [
                    {
                        "order": 1,
                        "duration_seconds": 5,
                        "voiceover": "开场提问",
                        "visual_hint": "特写",
                        "on_screen_text": topic[:12],
                    }
                ],
                "cta": "关注看后续",
                "factual_claims": [sources[0].content] if sources else [],
                "claim_source_map": claim_source_map,
            },
            input_tokens=0,
            output_tokens=0,
        )


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "zhipu":
        if not settings.zhipu_api_key:
            raise AppError(
                "PROVIDER_NOT_CONFIGURED",
                "未配置 ZHIPU_API_KEY",
                status_code=503,
                retryable=False,
            )
        from app.infrastructure.providers.zhipu import ZhipuLLMProvider

        return ZhipuLLMProvider(
            api_key=settings.zhipu_api_key,
            base_url=settings.zhipu_base_url,
            model=settings.zhipu_model,
            timeout=settings.provider_timeout_seconds,
        )
    raise AppError(
        "PROVIDER_NOT_CONFIGURED",
        f"未知 LLM_PROVIDER={settings.llm_provider}",
        status_code=500,
        retryable=False,
    )
