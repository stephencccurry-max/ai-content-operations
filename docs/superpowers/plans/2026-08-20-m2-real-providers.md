# M2 真实内容生产 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Tavily 调研 + 智谱 GLM-5.3 真实出稿替换 M1 Mock，支持小红书图文与抖音脚本；记录 token 与调用成败；额度用尽时失败可追踪。不做人民币计价，不做预算熔断。

**Architecture:** FastAPI 仍是唯一状态入口。n8n WF-01 调用顺序不变（claim → 按平台 generate → finish）。`generate_output` 内先确保本任务有一份调研来源（Tavily，按 task 缓存），再调 LLM Adapter 产出 JSON payload。测试默认 `LLM_PROVIDER=mock`、`SEARCH_PROVIDER=mock`，用 httpx 假响应覆盖真实 Adapter，禁止测网。

**Tech Stack:** 现有 FastAPI / SQLAlchemy / Alembic / pytest / httpx；智谱 OpenAI 兼容 `POST {ZHIPU_BASE_URL}/chat/completions`；Tavily `POST https://api.tavily.com/search`。

## Global Constraints

- 本项目是个人 Windows 本地应用，不引入多租户、Kubernetes 或微服务。
- FastAPI 是业务状态和状态迁移的唯一入口；n8n 不直接读写核心业务表。
- 所有外部 Provider 必须经过 Adapter：超时、有限重试、记录 `provider_calls`；日志不得输出完整密钥或 Authorization。
- 内容产物采用不可变版本；只有明确批准的版本可导出。`approved` 一旦写入不再变更。
- 公开 API 前缀 `/api/v1`，编排接口前缀 `/internal/v1`，JSON 字段一律 `snake_case`。
- 密钥只走 `.env`，不提交 Git。
- **M2 不做预算熔断，不把 token 换算成人民币。** `provider_calls.estimated_cost` 保持 `0`。`input_tokens` / `output_tokens` 有则写入。
- 用户已选择：搜索 **Tavily**；模型 **`glm-5.3`**；Base URL **`https://open.bigmodel.cn/api/coding/paas/v4`**（Coding Plan 端点）。官方条款限制该端点给白名单编程工具使用，本计划按用户明确决定接入；标准 `paas/v4` 可通过改 `ZHIPU_BASE_URL` 切换。
- 测试不依赖网络。conftest 必须强制 mock provider，避免本机 `.env` 的 `LLM_PROVIDER=zhipu` 污染 pytest。
- TDD：先写失败测试并确认以预期原因失败，再写最小实现。PowerShell 不要用 `&&`。
- 依赖用 `uv add` 锁定，提交锁文件。不要提前做 M3 QC / M4 对账。

## 已拍板（不要在任务里重新讨论）

1. 搜索：Tavily，只要带 `content` 的结果，不自建抓取。
2. LLM：智谱 `glm-5.3`，`ZHIPU_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4`。
3. 不做预算熔断；超限由供应商返回错误（如 1113），记 `provider_calls.status=failed` 并让步骤失败。
4. Key 已在本机 `.env` / `infra/.env` 的 `ZHIPU_*`；Tavily Key 用户稍后自填 `TAVILY_API_KEY`。

## File Structure

```text
apps/api/app/config.py                          # 增加 provider 相关 Settings
apps/api/app/infrastructure/providers/http.py   # 新建：超时、1 次重试、脱敏
apps/api/app/infrastructure/providers/search.py # 新建：SearchProvider + Mock + Tavily
apps/api/app/infrastructure/providers/llm.py    # Protocol + Mock；工厂按 Settings 分发
apps/api/app/infrastructure/providers/zhipu.py  # 新建：GLM-5.3 JSON 出稿
apps/api/app/domain/content/service.py          # 调研缓存 + 调 search/llm + 写 token
apps/api/app/infrastructure/db/models.py        # content_tasks.research_sources JSONB
apps/api/alembic/versions/0002_research_sources.py
apps/api/tests/test_search_provider.py
apps/api/tests/test_zhipu_provider.py
apps/api/tests/test_content_generation.py       # 补失败态；默认仍 mock
apps/api/tests/test_pipeline_contract.py        # 补双平台
infra/docker-compose.yml                        # api 透传 ZHIPU_* / TAVILY_* / LLM_* / SEARCH_*
workflows/wf01-content-pipeline.json            # Generate HTTP timeout 120s
.env.example / README.md / docs/HANDOFF.md
```

职责：`search.py` / `zhipu.py` 不 import FastAPI；`http.py` 不打印密钥；`get_llm_provider()` / `get_search_provider()` 只读 Settings。

---

### Task 1: Settings、httpx 运行时依赖、conftest 强制 Mock

**Files:**
- Modify: `apps/api/pyproject.toml`（`uv add httpx` 写入主依赖）
- Modify: `apps/api/uv.lock`
- Modify: `apps/api/app/config.py`
- Modify: `apps/api/tests/conftest.py`
- Create: `apps/api/app/infrastructure/providers/http.py`
- Create: `apps/api/tests/test_provider_http.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `Settings` 增加 `llm_provider: str = "mock"`、`search_provider: str = "mock"`、`zhipu_api_key: str | None = None`、`zhipu_base_url: str = "https://open.bigmodel.cn/api/coding/paas/v4"`、`zhipu_model: str = "glm-5.3"`、`tavily_api_key: str | None = None`、`provider_timeout_seconds: float = 45.0`；`request_json(method, url, *, headers, json, timeout) -> dict`（成功返回 JSON object；失败抛 `AppError`）。
- Consumes: 现有 `get_settings()`、`AppError`。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/test_provider_http.py`：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.\.venv\Scripts\pytest.exe tests/test_provider_http.py -v
```

Expected: FAIL，`request_json` 未定义。

- [ ] **Step 3: 实现**

```powershell
cd apps\api
uv add httpx
```

`apps/api/app/config.py` 在 `Settings` 中增加（全部 extra ignore 已有）：

```python
    llm_provider: str = "mock"
    search_provider: str = "mock"
    zhipu_api_key: str | None = None
    zhipu_base_url: str = "https://open.bigmodel.cn/api/coding/paas/v4"
    zhipu_model: str = "glm-5.3"
    tavily_api_key: str | None = None
    provider_timeout_seconds: float = 45.0
```

`apps/api/app/infrastructure/providers/http.py`：

```python
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
```

`apps/api/tests/conftest.py` 的 `client` fixture 开头增加：

```python
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("SEARCH_PROVIDER", "mock")
```

`.env.example` 增加（不要写真实 Key）：

```
LLM_PROVIDER=mock
SEARCH_PROVIDER=mock
TAVILY_API_KEY=
ZHIPU_API_KEY=
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4
ZHIPU_MODEL=glm-5.3
```

本机已有 `ZHIPU_*` 的 `.env` 再补 `LLM_PROVIDER=zhipu`、`SEARCH_PROVIDER=tavily`（Tavily Key 空着也可以先合代码；无 Key 时真实生成应报 `PROVIDER_NOT_CONFIGURED`）。

- [ ] **Step 4: 跑测试确认通过**

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.\.venv\Scripts\pytest.exe tests/test_provider_http.py tests/test_health.py -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/app/config.py apps/api/app/infrastructure/providers/http.py apps/api/tests/test_provider_http.py apps/api/tests/conftest.py .env.example
git commit -m "feat(api): add provider HTTP helper and settings for M2"
```

---

### Task 2: Tavily Search Adapter

**Files:**
- Create: `apps/api/app/infrastructure/providers/search.py`
- Create: `apps/api/tests/test_search_provider.py`

**Interfaces:**
- Consumes: `request_json`、`get_settings()`。
- Produces: `class SearchHit: title: str; url: str; content: str`；`class SearchProvider(Protocol): name: str; def search(self, query: str) -> list[SearchHit]`；`MockSearchProvider`；`TavilySearchProvider`；`get_search_provider() -> SearchProvider`。

Tavily 契约（写死在测试里）：

- URL: `https://api.tavily.com/search`
- Header: `Authorization: Bearer {tavily_api_key}`，`Content-Type: application/json`
- Body: `{"query": <topic>, "max_results": 5, "search_depth": "basic"}`
- 使用 `results[].title` / `url` / `content`；`content` 为空的结果丢弃。至少 1 条有效结果，否则 `AppError("SEARCH_EMPTY", ...)`。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/test_search_provider.py`：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.\.venv\Scripts\pytest.exe tests/test_search_provider.py -v
```

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现 `search.py`**

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.\.venv\Scripts\pytest.exe tests/test_search_provider.py -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/infrastructure/providers/search.py apps/api/tests/test_search_provider.py
git commit -m "feat(api): add Tavily search adapter with mock fallback"
```

---

### Task 3: 智谱 GLM-5.3 Adapter

**Files:**
- Modify: `apps/api/app/infrastructure/providers/llm.py`（保留 Protocol 与 Mock；工厂按 Settings 分发；prompt version 常量）
- Create: `apps/api/app/infrastructure/providers/zhipu.py`
- Create: `apps/api/tests/test_zhipu_provider.py`

**Interfaces:**
- Consumes: `request_json`、`SearchHit`、`Settings`。
- Produces: `ZhipuLLMProvider` 实现 `LLMProvider`，方法签名改为带 `sources: list[SearchHit]`（同步改 Mock 与 Protocol，避免双路径）。

返回 payload 字段必须与现有测试兼容：

- 小红书 note：`title, hook, body, cover_text, hashtags, factual_claims, claim_source_map`
- 抖音 script：`hook, script, estimated_duration_seconds, scenes, cta, factual_claims, claim_source_map`

智谱请求（测试断言）：

- URL: `{zhipu_base_url.rstrip('/')}/chat/completions`
- Header: `Authorization: Bearer {zhipu_api_key}`
- JSON：`model`、`messages`、`max_tokens=4096`、`temperature=0.7`、`thinking: {"type": "disabled"}`
- 从 `choices[0].message.content` 取正文；去掉 ` ```json ` 围栏后 `json.loads`。
- `usage.prompt_tokens` → input；`usage.completion_tokens` → output。Adapter 返回 `(payload, usage)` 或在 payload 外提供 `GenerateResult`。

使用数据类，避免把 token 塞进内容 JSON：

```python
@dataclass
class GenerateResult:
    payload: dict
    input_tokens: int
    output_tokens: int
```

Protocol 改为：

```python
def generate_note(self, topic: str, audience: str, tone: str, sources: list[SearchHit]) -> GenerateResult: ...
def generate_script(self, topic: str, audience: str, tone: str, sources: list[SearchHit]) -> GenerateResult: ...
```

Mock 返回 `GenerateResult(..., input_tokens=0, output_tokens=0)`，并把 `claim_source_map` 填成 `[{claim: ..., source_url: sources[0].url}]`（sources 为空则 `[]`）。

智谱错误映射（在 `zhipu.py` 捕获 `PROVIDER_HTTP_ERROR` 的 details）：

- body 含 `"code":"1113"` → `AppError("PROVIDER_QUOTA_EXCEEDED", "模型额度不足", status_code=429, retryable=False)`
- `"code":"1004"` 或 HTTP 401 → `AppError("PROVIDER_AUTH_FAILED", "模型鉴权失败", status_code=401, retryable=False)`
- content 空或 JSON 非法 → `PROVIDER_INVALID_RESPONSE`，retryable=False

- [ ] **Step 1: 写失败测试**

`apps/api/tests/test_zhipu_provider.py`：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.\.venv\Scripts\pytest.exe tests/test_zhipu_provider.py -v
```

Expected: FAIL。

- [ ] **Step 3: 实现**

`zhipu.py` 要点：

1. `NOTE_PROMPT` / `SCRIPT_PROMPT` 要求「只输出 JSON，字段必须齐全，事实声明必须能在 sources 中找到对应 url」。
2. `_extract_json(text)`：strip，若以 ` ``` ` 开头则去掉第一行和末行围栏。
3. `_validate_note` / `_validate_script`：缺字段或 `title`/`body`/`script` 为空则 `PROVIDER_INVALID_RESPONSE`。
4. `_translate_http_error(exc: AppError)`：检查 `body_snippet` 中的 `1113` / `1004`。
5. MockLLMProvider 同步改签名并返回 `GenerateResult`。
6. `get_llm_provider()`：`mock` → Mock；`zhipu` 且无 key → `PROVIDER_NOT_CONFIGURED`；`zhipu` → `ZhipuLLMProvider`。

Prompt version：`NOTE_PROMPT_VERSION = "xiaohongshu.v2"`，`SCRIPT_PROMPT_VERSION = "douyin.v1"`。`generate_output` 下一任务按平台选用。Mock 仍可写 `xiaohongshu.v1` 以免无谓改旧断言——**现有** `test_version_records_model_and_prompt_version` 只断言 truthy。Mock 继续 `xiaohongshu.v1`；Zhipu 用 v2。

- [ ] **Step 4: 跑测试**

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.\.venv\Scripts\pytest.exe tests/test_zhipu_provider.py tests/test_content_generation.py -v
```

Expected: 全部 PASS（content_generation 仍走 Mock）。

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/infrastructure/providers/llm.py apps/api/app/infrastructure/providers/zhipu.py apps/api/tests/test_zhipu_provider.py
git commit -m "feat(api): add Zhipu GLM-5.3 adapter with JSON payloads"
```

---

### Task 4: 调研缓存写入 generate_output

**Files:**
- Modify: `apps/api/app/infrastructure/db/models.py`（`ContentTask.research_sources: dict | list | None` JSONB nullable）
- Create: `apps/api/alembic/versions/0002_research_sources.py`
- Modify: `apps/api/app/domain/content/service.py`
- Modify: `apps/api/tests/test_content_generation.py`
- Create: `apps/api/tests/test_generate_errors.py`

**Interfaces:**
- Consumes: `get_search_provider()`、`get_llm_provider()`、`GenerateResult`。
- Produces: 同一 `task_id` 多次 generate（两个平台）只 search 一次；`provider_calls` 两次 LLM + 一次 search（search 也写一条 `provider=tavily|mock-search`，`model=tavily` 或 `mock-search`，token=0）；LLM 行写入 input/output tokens；`estimated_cost=0`。失败时仍 insert `provider_calls.status=failed` 再 raise。

Alembic `0002_research_sources.py`：

```python
revision = "0002_research_sources"
down_revision = "e88b282a826e"

def upgrade() -> None:
    op.add_column(
        "content_tasks",
        sa.Column("research_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("content_tasks", "research_sources")
```

`generate_output` 流程：

1. lock task
2. 若 `task.research_sources` 为空：`hits = get_search_provider().search(task.topic)`，写成 `[{"title","url","content"}]`，记 search `ProviderCall`
3. `sources = [SearchHit(**row) for row in task.research_sources]`
4. 调 LLM；成功记 call + version；`AppError` 先记 failed call（error_code=exc.code）再 raise

- [ ] **Step 1: 写失败测试**

在 `test_content_generation.py` 增加：

```python
def test_two_platforms_search_once(client, db_session):
    from sqlalchemy import select
    from app.infrastructure.db.models import ProviderCall

    payload = {
        **PAYLOAD,
        "platforms": ["xiaohongshu", "douyin"],
    }
    task_id = client.post(
        "/api/v1/tasks", json=payload, headers={"Idempotency-Key": "k-dual"}
    ).json()["id"]
    client.post(f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS)
    client.post(f"/internal/v1/tasks/{task_id}/generate/douyin", headers=HEADERS)
    providers = [c.provider for c in db_session.scalars(select(ProviderCall)).all()]
    assert providers.count("mock-search") == 1
    assert providers.count("mock") == 2
```

`test_generate_errors.py`：

```python
from unittest.mock import patch
import pytest
from app.errors import AppError

HEADERS = {"X-Internal-Token": "test-internal-token"}
PAYLOAD = {
    "topic": "咖啡因如何影响睡眠质量",
    "audience": "熬夜上班族",
    "goal": "education",
    "platforms": ["xiaohongshu"],
    "tone": "专业、实用",
}


def test_quota_error_recorded_as_failed_call(client, db_session):
    from sqlalchemy import select
    from app.infrastructure.db.models import ProviderCall

    task_id = client.post("/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k-q"}).json()["id"]
    err = AppError("PROVIDER_QUOTA_EXCEEDED", "额度不足", status_code=429, retryable=False)
    with patch(
        "app.domain.content.service.get_llm_provider"
    ) as mocked:
        mocked.return_value.generate_note.side_effect = err
        mocked.return_value.name = "zhipu"
        mocked.return_value.model = "glm-5.3"
        response = client.post(
            f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
        )
    assert response.status_code == 429
    call = db_session.scalars(select(ProviderCall)).all()[-1]
    assert call.status == "failed"
    assert call.error_code == "PROVIDER_QUOTA_EXCEEDED"
```

（实现时 search 仍会先成功走 MockSearch；failed 行是 LLM。断言用 `error_code` 最稳。）

- [ ] **Step 2: 跑测试确认失败**

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.\.venv\Scripts\pytest.exe tests/test_content_generation.py::test_two_platforms_search_once tests/test_generate_errors.py -v
```

Expected: FAIL。

- [ ] **Step 3: 迁移 + 改 `generate_output`**

更新 `ContentTask` 模型字段 `research_sources`。`generate_output` 按上面流程改；prompt_version：xiaohongshu 用 `PROMPT_VERSION`（mock）或从 provider 读取。给 Protocol 加 `prompt_version: str` 属性：Mock=`xiaohongshu.v1` / 对 script 仍同一 Mock 类可用 `douyin.v1` 属性或按方法选择。最简单：`generate_output` 里 `prompt_version = "xiaohongshu.v2" if provider.name=="zhipu" and platform is XIAOHONGSHU else ...` 不要散落魔法字符串，放到 `llm.py` 常量。

`test_generation_records_provider_call` 现在会多一条 mock-search：改断言为

```python
providers = {c.provider for c in calls}
assert "mock" in providers
assert "mock-search" in providers
assert all(c.status == "succeeded" for c in calls)
```

- [ ] **Step 4: 跑测试**

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.\.venv\Scripts\pytest.exe tests -v
```

Expected: 全绿（现 75 + 新增）。

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/infrastructure/db/models.py apps/api/alembic/versions/0002_research_sources.py apps/api/app/domain/content/service.py apps/api/tests/test_content_generation.py apps/api/tests/test_generate_errors.py
git commit -m "feat(api): cache Tavily research per task and record provider failures"
```

---

### Task 5: 双平台契约、n8n 超时、Compose 透传环境变量

**Files:**
- Modify: `apps/api/tests/test_pipeline_contract.py`
- Modify: `workflows/wf01-content-pipeline.json`（Generate Content 节点 `options.timeout` 改为 `120000`；Claim / Start / Complete 可保持 30000）
- Modify: `infra/docker-compose.yml`（api `environment` 增加 `LLM_PROVIDER`、`SEARCH_PROVIDER`、`ZHIPU_API_KEY`、`ZHIPU_BASE_URL`、`ZHIPU_MODEL`、`TAVILY_API_KEY`、`PROVIDER_TIMEOUT_SECONDS`）
- Modify: `apps/web/e2e/smoke.spec.ts`（内部 HTTP 回退路径在 generate 小红书前不必改；可选：创建任务带双平台。M2 验收仍允许单平台 smoke，另加 pytest 契约即可。**不要**让 Playwright 依赖真实智谱。）

**Interfaces:**
- Consumes: 现有 `/internal/v1`。
- Produces: 双平台任务 generate 两次后 `awaiting_review`（两槽位都 settled）。

双平台契约测试：

```python
def test_dual_platform_pipeline_reaches_awaiting_review(client):
    payload = {**PAYLOAD, "platforms": ["xiaohongshu", "douyin"]}
    task_id = client.post("/api/v1/tasks", json=payload, headers={"Idempotency-Key": "k-dual-pipe"}).json()["id"]
    run_id = client.post(f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS).json()["id"]
    for platform in ("xiaohongshu", "douyin"):
        step = client.post(
            f"/internal/v1/runs/{run_id}/steps/generate_{platform}/start", headers=HEADERS
        ).json()
        gen = client.post(f"/internal/v1/tasks/{task_id}/generate/{platform}", headers=HEADERS)
        assert gen.status_code == 201
        client.post(
            f"/internal/v1/runs/{run_id}/steps/generate_{platform}/complete",
            json={"attempt": step["attempt"]},
            headers=HEADERS,
        )
    client.post(f"/internal/v1/runs/{run_id}/finish", json={"status": "succeeded"}, headers=HEADERS)
    detail = client.get(f"/api/v1/tasks/{task_id}").json()
    assert detail["status"] == "awaiting_review"
    assert len(detail["output_slots"]) == 2
```

Compose api environment 示例：

```yaml
      LLM_PROVIDER: ${LLM_PROVIDER:-mock}
      SEARCH_PROVIDER: ${SEARCH_PROVIDER:-mock}
      ZHIPU_API_KEY: ${ZHIPU_API_KEY:-}
      ZHIPU_BASE_URL: ${ZHIPU_BASE_URL:-https://open.bigmodel.cn/api/coding/paas/v4}
      ZHIPU_MODEL: ${ZHIPU_MODEL:-glm-5.3}
      TAVILY_API_KEY: ${TAVILY_API_KEY:-}
```

`env_file: ../.env` 已能注入；显式 environment 防止被空覆盖时仍有默认 mock。

- [ ] **Step 1: 写失败测试（双平台契约）并确认失败（若 Task 4 已让它能过则本步应已 PASS，直接进入 n8n/compose）**
- [ ] **Step 2: 改 n8n timeout 与 compose**
- [ ] **Step 3: 跑全量 pytest**

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.\.venv\Scripts\pytest.exe tests -v
```

Expected: 全绿。

- [ ] **Step 4: Commit**

```powershell
git add apps/api/tests/test_pipeline_contract.py workflows/wf01-content-pipeline.json infra/docker-compose.yml
git commit -m "feat: dual-platform pipeline contract and longer n8n generate timeout"
```

---

### Task 6: 文档与本机 live 说明

**Files:**
- Modify: `README.md`（冷启动增加 Tavily Key、`LLM_PROVIDER=zhipu`、`SEARCH_PROVIDER=tavily`；说明测试仍 mock）
- Modify: `workflows/README.md`（Generate 超时 120s；真实 LLM 较慢）
- Modify: `docs/HANDOFF.md`（M2 进行中，指向本计划；预算熔断明确推迟）
- Modify: `.env.example`（若 Task 1 已写则只补 Tavily 注释）

**Live 验收（实现完成后人工，不写进 pytest）：**

1. 根目录 `.env`：`LLM_PROVIDER=zhipu`、`SEARCH_PROVIDER=tavily`、`TAVILY_API_KEY`、已有 `ZHIPU_*`。
2. `docker compose -f infra/docker-compose.yml -f infra/docker-compose.override.yml up -d --build`（本机 Postgres 占 5432 时继续用 override 5433）。
3. 重新导入/激活 WF-01（timeout 变更后需再 import）。
4. 创建双平台任务，webhook 触发，详情出现两份稿、`claim_source_map` 非空。
5. 额度错误：可临时改错 Key 看任务步骤 `failed` + `PROVIDER_AUTH_FAILED` / `PROVIDER_QUOTA_EXCEEDED`。

- [ ] **Step 1: 更新文档（无密钥）**
- [ ] **Step 2: Commit**

```powershell
git add README.md workflows/README.md docs/HANDOFF.md .env.example
git commit -m "docs: describe M2 Tavily and Zhipu live configuration"
```

---

## 验收标准

- pytest 全绿，不访问外网。
- 默认 mock 行为下 M1 闭环（创建→generate→批准→导出）仍可用。
- `SEARCH_PROVIDER=tavily` + `LLM_PROVIDER=zhipu` 时，Adapter 走真实 HTTP；失败码 1113/1004 可区分。
- 双平台只 search 一次。
- `estimated_cost` 恒为 0；有 usage 则写 token。
- 无预算熔断代码。
- 文档说明 Coding Plan 端点风险与标准 API 切换方法（改 `ZHIPU_BASE_URL`）。

## 明确不做（M3/M4/V1.1）

- 规则/模型 QC、审核门禁增强
- 人民币单价表、日预算熔断
- 真实发布 Adapter、图片生成
- Playwright 打真实智谱/Tavily

---

## 实现完成后的执行方式

用 `superpowers:subagent-driven-development`：一任务一子代理，评审后再下一任务。不要并行实现子代理。
