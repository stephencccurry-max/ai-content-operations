from unittest.mock import patch

import pytest

from app.errors import AppError
from app.infrastructure.providers.search import TavilySearchProvider, get_search_provider


def test_tavily_maps_title_url_content():
    provider = TavilySearchProvider(api_key="tvly-test", timeout=1.0)
    payload = {
        "results": [
            {"title": "睡眠", "url": "https://example.com/a", "content": "咖啡因影响入睡。"},
            {"title": "空", "url": "https://example.com/b", "content": ""},
        ]
    }
    with patch(
        "app.infrastructure.providers.search.request_json", return_value=payload
    ) as mocked:
        hits = provider.search("咖啡因如何影响睡眠质量")

    assert len(hits) == 1
    assert hits[0].url == "https://example.com/a"
    mocked.assert_called_once()
    args, kwargs = mocked.call_args
    assert args[0] == "POST"
    assert args[1] == "https://api.tavily.com/search"
    assert kwargs["headers"]["Authorization"] == "Bearer tvly-test"
    assert kwargs["json"]["max_results"] == 5


def test_tavily_empty_results_raise():
    provider = TavilySearchProvider(api_key="tvly-test", timeout=1.0)
    with patch(
        "app.infrastructure.providers.search.request_json",
        return_value={"results": []},
    ):
        with pytest.raises(AppError) as exc:
            provider.search("x")
    assert exc.value.code == "SEARCH_EMPTY"


def test_factory_defaults_to_mock(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "mock")
    from app.config import get_settings

    get_settings.cache_clear()
    provider = get_search_provider()
    hits = provider.search("主题五个字以上")
    assert hits
    assert hits[0].content
