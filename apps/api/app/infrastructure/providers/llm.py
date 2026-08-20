from typing import Protocol

PROMPT_VERSION = "xiaohongshu.v1"


class LLMProvider(Protocol):
    name: str
    model: str

    def generate_note(self, topic: str, audience: str, tone: str) -> dict: ...

    def generate_script(self, topic: str, audience: str, tone: str) -> dict: ...


class MockLLMProvider:
    name = "mock"
    model = "mock-writer-1"

    def generate_note(self, topic: str, audience: str, tone: str) -> dict:
        return {
            "title": f"{topic}：写给{audience}的 5 分钟版本",
            "hook": f"如果你也被「{topic}」困扰，这篇讲清楚了。",
            "body": (
                f"面向{audience}，语气{tone}。\n\n"
                "这是 M1 阶段由 Mock Provider 生成的占位正文，"
                "用于验证任务、版本、审核与导出链路，不代表真实内容质量。"
            ),
            "cover_text": topic[:12],
            "hashtags": ["自我提升", "效率"],
            "factual_claims": [],
            "claim_source_map": [],
        }

    def generate_script(self, topic: str, audience: str, tone: str) -> dict:
        return {
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
            "factual_claims": [],
            "claim_source_map": [],
        }


def get_llm_provider() -> LLMProvider:
    return MockLLMProvider()
