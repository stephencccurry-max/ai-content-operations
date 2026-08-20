from dataclasses import dataclass
from typing import Protocol

from app.config import get_settings
from app.errors import AppError
from app.infrastructure.providers.http import request_json

TAVILY_URL = "https://api.tavily.com/search"


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    content: str


class SearchProvider(Protocol):
    name: str

    def search(self, query: str) -> list[SearchHit]: ...


class MockSearchProvider:
    name = "mock-search"

    def search(self, query: str) -> list[SearchHit]:
        return [
            SearchHit(
                title=f"{query} 资料 1",
                url="https://example.com/mock-1",
                content=f"与「{query}」相关的占位调研正文，供 Mock 出稿引用。",
            )
        ]


class TavilySearchProvider:
    name = "tavily"

    def __init__(self, api_key: str, timeout: float) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def search(self, query: str) -> list[SearchHit]:
        data = request_json(
            "POST",
            TAVILY_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={"query": query, "max_results": 5, "search_depth": "basic"},
            timeout=self._timeout,
        )
        hits: list[SearchHit] = []
        for item in data.get("results") or []:
            content = (item.get("content") or "").strip()
            url = (item.get("url") or "").strip()
            title = (item.get("title") or "").strip() or url
            if content and url:
                hits.append(SearchHit(title=title, url=url, content=content))
        if not hits:
            raise AppError("SEARCH_EMPTY", "搜索未返回可用正文", status_code=502, retryable=True)
        return hits


def get_search_provider() -> SearchProvider:
    settings = get_settings()
    if settings.search_provider == "mock":
        return MockSearchProvider()
    if settings.search_provider == "tavily":
        if not settings.tavily_api_key:
            raise AppError(
                "PROVIDER_NOT_CONFIGURED",
                "未配置 TAVILY_API_KEY",
                status_code=503,
                retryable=False,
            )
        return TavilySearchProvider(settings.tavily_api_key, settings.provider_timeout_seconds)
    raise AppError(
        "PROVIDER_NOT_CONFIGURED",
        f"未知 SEARCH_PROVIDER={settings.search_provider}",
        status_code=500,
        retryable=False,
    )
