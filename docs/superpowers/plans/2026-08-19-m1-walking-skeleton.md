# M1 走通闭环（全 Mock 驱动）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个不依赖任何外部 API 的端到端可演示版本：在浏览器里创建内容任务，n8n 编排 FastAPI 内部接口，Mock Provider 产出小红书文案，页面轮询看到步骤推进，人工批准后导出 Markdown 文件。

**Architecture:** 模块化单体。FastAPI 持有全部业务规则与状态迁移，PostgreSQL 是唯一事实来源，n8n 只按顺序调用 `/internal/v1` 接口并回调步骤状态，Next.js 通过 `/api/v1` 轮询展示。内容产物拆成「槽位（slot）」与「不可变版本（version）」两级，任务总状态是派生值而非写入字段。M1 阶段 LLM 一律走 `MockLLMProvider`，不接任何外部服务。

**Tech Stack:** Python 3.12 / FastAPI / Pydantic v2 / SQLAlchemy 2 / Alembic / PostgreSQL 16 / httpx / pytest；Node 20 / Next.js（App Router）/ TypeScript / Tailwind CSS / TanStack Query / Playwright；n8n；Docker Compose（Docker Desktop + WSL2）。

## Global Constraints

- 本项目是个人 Windows 本地应用，不引入多租户、Kubernetes 或微服务。
- FastAPI 是业务状态和状态迁移的唯一入口；n8n 不直接读写核心业务表。
- 所有外部 Provider 必须经过 Adapter，设置超时、有限重试并记录调用；M1 只实现 Mock Adapter。
- 内容产物采用不可变版本；只有明确批准的版本可导出。`approved` 一旦写入不再变更。
- 公开 API 前缀 `/api/v1`，编排专用接口前缀 `/internal/v1`，JSON 字段一律 `snake_case`。
- 所有时间列使用 `TIMESTAMPTZ`，主键使用 UUID，API 中的时间使用 UTC ISO 8601。
- 容器内进程监听 `0.0.0.0`；访问限制由 Compose 端口映射承担，一律写成 `127.0.0.1:<port>:<port>`。
- 密钥只通过 `.env` 提供，不提交 Git；日志不得输出完整密钥、Cookie 或 Authorization 头。
- M1 不调用任何外部 API。LLM 与搜索一律使用 Mock 实现，测试不依赖网络。
- TDD 强制：每个步骤先写失败测试并确认它以预期原因失败，再写最小实现。先写实现的代码一律删除重来。
- 依赖版本在安装时由包管理器锁定（`uv add` / `npm install`），不要在计划里凭记忆写死版本号；锁文件必须提交。

---

## File Structure

```text
ai-content-operations/
├─ apps/
│  ├─ api/
│  │  ├─ app/
│  │  │  ├─ main.py                       # create_app 与路由挂载
│  │  │  ├─ config.py                     # Settings
│  │  │  ├─ errors.py                     # AppError 与统一错误信封
│  │  │  ├─ middleware.py                 # request_id
│  │  │  ├─ api/
│  │  │  │  ├─ health.py
│  │  │  │  ├─ tasks.py
│  │  │  │  ├─ content.py
│  │  │  │  ├─ reviews.py
│  │  │  │  ├─ exports.py
│  │  │  │  └─ internal.py
│  │  │  ├─ application/
│  │  │  │  └─ idempotency.py
│  │  │  ├─ domain/
│  │  │  │  ├─ enums.py                   # 全部状态枚举
│  │  │  │  ├─ tasks/status.py            # derive_task_status 纯函数
│  │  │  │  ├─ tasks/service.py
│  │  │  │  ├─ runs/service.py
│  │  │  │  ├─ content/service.py
│  │  │  │  └─ review/service.py
│  │  │  └─ infrastructure/
│  │  │     ├─ db/session.py
│  │  │     ├─ db/models.py
│  │  │     ├─ providers/llm.py           # LLMProvider 协议 + MockLLMProvider
│  │  │     └─ exporters/markdown.py
│  │  ├─ alembic/
│  │  └─ tests/
│  └─ web/                                # Next.js App Router
├─ workflows/
│  └─ wf01-content-pipeline.json
├─ infra/
│  └─ docker-compose.yml
├─ data/                                  # git ignore：exports / assets
├─ docs/superpowers/plans/
├─ .env.example
├─ AGENTS.md
└─ README.md
```

职责边界：`domain/` 只放业务规则与纯函数，不 import FastAPI；`api/` 只做请求解析、调用 domain、组织响应；`infrastructure/` 放数据库、Provider、文件导出这些与外界打交道的实现。`derive_task_status` 是纯函数，不接触数据库，这样真值表可以直接单测。

---

## Task 1: 应用骨架与统一错误信封

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/app/__init__.py`
- Create: `apps/api/app/config.py`
- Create: `apps/api/app/errors.py`
- Create: `apps/api/app/middleware.py`
- Create: `apps/api/app/api/__init__.py`
- Create: `apps/api/app/api/health.py`
- Create: `apps/api/app/main.py`
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_health.py`
- Create: `apps/api/tests/test_errors.py`
- Create: `.env.example`
- Create: `.gitignore`

**Interfaces:**
- Produces: `create_app() -> FastAPI`；`Settings`（字段 `database_url: str`、`internal_api_token: str`、`export_dir: Path`、`app_version: str`）；`get_settings() -> Settings`；`AppError(code: str, message: str, *, status_code: int = 400, retryable: bool = False, details: dict | None = None)`；测试夹具 `client: TestClient`。
- Consumes: 无。

- [ ] **Step 1: 初始化 Python 项目**

在仓库根目录执行（PowerShell，逐条执行，不要用 `&&` 连接）：

```powershell
mkdir apps\api\app\api
mkdir apps\api\tests
cd apps\api
uv init --no-workspace
uv add fastapi uvicorn[standard] pydantic-settings
uv add --dev pytest httpx
```

- [ ] **Step 2: 写失败测试**

`apps/api/tests/conftest.py`：

```python
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)
```

`apps/api/tests/test_health.py`：

```python
def test_health_returns_ok_and_version(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_version"]


def test_health_response_carries_request_id_header(client):
    response = client.get("/api/v1/health")

    assert response.headers["x-request-id"]
```

`apps/api/tests/test_errors.py`：

```python
from app.errors import AppError


def test_app_error_is_rendered_as_error_envelope(client):
    app = client.app

    @app.get("/api/v1/boom")
    def boom():
        raise AppError("TASK_NOT_FOUND", "任务不存在", status_code=404)

    response = client.get("/api/v1/boom")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "TASK_NOT_FOUND"
    assert error["message"] == "任务不存在"
    assert error["retryable"] is False
    assert error["request_id"]
```

- [ ] **Step 3: 运行测试确认失败**

Run: `uv run pytest tests -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 4: 写最小实现**

`apps/api/app/config.py`：

```python
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/ai_content_ops"
    internal_api_token: str = "dev-internal-token"
    export_dir: Path = Path("data/exports")
    app_version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`apps/api/app/errors.py`：

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        retryable: bool = False,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "retryable": exc.retryable,
                    "request_id": getattr(request.state, "request_id", ""),
                    "details": exc.details,
                }
            },
        )
```

`apps/api/app/middleware.py`：

```python
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
```

`apps/api/app/api/health.py`：

```python
from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter()


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "app_version": settings.app_version}
```

`apps/api/app/main.py`：

```python
from fastapi import FastAPI

from app.api import health
from app.errors import register_error_handlers
from app.middleware import RequestIdMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="AI Content Ops API")
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    return app


app = create_app()
```

`.env.example`：

```text
DATABASE_URL=postgresql+psycopg://app:app@db:5432/ai_content_ops
INTERNAL_API_TOKEN=change-me-in-local-env
EXPORT_DIR=data/exports
APP_VERSION=0.1.0
INTERNAL_API_BASE_URL=http://api:8000
```

`.gitignore`：

```text
.env
data/
__pycache__/
.venv/
node_modules/
.next/
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests -v`
Expected: 3 passed，输出无 warning

- [ ] **Step 6: 提交**

```powershell
git add apps/api .env.example .gitignore
git commit -m "feat(api): 应用骨架、请求 ID 与统一错误信封"
```

---

## Task 2: 数据库模型与基线迁移

**Files:**
- Create: `apps/api/app/domain/enums.py`
- Create: `apps/api/app/infrastructure/db/session.py`
- Create: `apps/api/app/infrastructure/db/models.py`
- Create: `apps/api/alembic.ini`
- Create: `apps/api/alembic/env.py`
- Create: `apps/api/alembic/versions/0001_baseline.py`
- Create: `infra/docker-compose.yml`
- Modify: `apps/api/app/api/health.py`
- Modify: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_migrations.py`

**Interfaces:**
- Consumes: `Settings.database_url`（Task 1）。
- Produces: ORM 类 `Project`、`ContentTask`、`TaskPlatform`、`WorkflowRun`、`WorkflowStepRun`、`ContentOutputSlot`、`ContentOutputVersion`、`ReviewDecision`、`AuditEvent`、`IdempotencyKey`、`ProviderCall`；`get_session()` 依赖；枚举 `TaskStatus`、`RunStatus`、`StepStatus`、`VersionStatus`、`Platform`、`ContentType`；测试夹具 `db_session`。

- [ ] **Step 1: 起数据库容器**

`infra/docker-compose.yml`：

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: ai_content_ops
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d ai_content_ops"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:
```

```powershell
docker compose -f infra/docker-compose.yml up -d db
docker compose -f infra/docker-compose.yml ps
```

Expected: `db` 状态为 `healthy`

- [ ] **Step 2: 写失败测试**

`apps/api/tests/test_migrations.py`：

```python
from sqlalchemy import inspect


def test_baseline_migration_creates_core_tables(db_session):
    tables = set(inspect(db_session.bind).get_table_names())

    assert {
        "projects",
        "content_tasks",
        "task_platforms",
        "workflow_runs",
        "workflow_step_runs",
        "content_output_slots",
        "content_output_versions",
        "review_decisions",
        "audit_events",
        "idempotency_keys",
        "provider_calls",
    } <= tables


def test_slot_is_unique_per_task_platform_and_content_type(db_session):
    from sqlalchemy import inspect as sa_inspect

    constraints = sa_inspect(db_session.bind).get_unique_constraints(
        "content_output_slots"
    )
    columns = [tuple(c["column_names"]) for c in constraints]

    assert ("task_id", "platform", "content_type") in columns


def test_version_is_unique_per_slot(db_session):
    from sqlalchemy import inspect as sa_inspect

    constraints = sa_inspect(db_session.bind).get_unique_constraints(
        "content_output_versions"
    )
    columns = [tuple(c["column_names"]) for c in constraints]

    assert ("slot_id", "version") in columns


def test_health_reports_database_status(client):
    body = client.get("/api/v1/health").json()

    assert body["database"] == "ok"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `uv run pytest tests/test_migrations.py -v`
Expected: FAIL，`fixture 'db_session' not found`

- [ ] **Step 4: 写枚举与模型**

`apps/api/app/domain/enums.py`：

```python
from enum import StrEnum


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PARTIALLY_READY = "partially_ready"
    AWAITING_REVIEW = "awaiting_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_ATTENTION = "needs_attention"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class VersionStatus(StrEnum):
    DRAFT = "draft"
    QC_PENDING = "qc_pending"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Platform(StrEnum):
    XIAOHONGSHU = "xiaohongshu"
    DOUYIN = "douyin"


class ContentType(StrEnum):
    NOTE = "note"
    SCRIPT = "script"
```

`apps/api/app/infrastructure/db/models.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = _created_at()


class ContentTask(Base):
    __tablename__ = "content_tasks"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    topic: Mapped[str] = mapped_column(Text())
    audience: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(String(50))
    tone: Mapped[str] = mapped_column(String(200))
    requirements: Mapped[str | None] = mapped_column(Text(), nullable=True)
    prohibited_items: Mapped[str | None] = mapped_column(Text(), nullable=True)
    current_step: Mapped[str | None] = mapped_column(String(50), nullable=True)
    needs_attention: Mapped[bool] = mapped_column(Boolean(), default=False)
    cancelled: Mapped[bool] = mapped_column(Boolean(), default=False)
    archived: Mapped[bool] = mapped_column(Boolean(), default=False)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TaskPlatform(Base):
    __tablename__ = "task_platforms"
    __table_args__ = (UniqueConstraint("task_id", "platform"),)

    id: Mapped[uuid.UUID] = _pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_tasks.id"))
    platform: Mapped[str] = mapped_column(String(30))
    content_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    last_error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = _pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_tasks.id"))
    workflow_key: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30))
    n8n_execution_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = _created_at()
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class WorkflowStepRun(Base):
    __tablename__ = "workflow_step_runs"
    __table_args__ = (UniqueConstraint("run_id", "step_key", "attempt"),)

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id"))
    step_key: Mapped[str] = mapped_column(String(50))
    attempt: Mapped[int] = mapped_column(Integer())
    status: Mapped[str] = mapped_column(String(30))
    retryable: Mapped[bool] = mapped_column(Boolean(), default=False)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime] = _created_at()
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ContentOutputSlot(Base):
    __tablename__ = "content_output_slots"
    __table_args__ = (UniqueConstraint("task_id", "platform", "content_type"),)

    id: Mapped[uuid.UUID] = _pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_tasks.id"))
    platform: Mapped[str] = mapped_column(String(30))
    content_type: Mapped[str] = mapped_column(String(30))
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()


class ContentOutputVersion(Base):
    __tablename__ = "content_output_versions"
    __table_args__ = (UniqueConstraint("slot_id", "version"),)

    id: Mapped[uuid.UUID] = _pk()
    slot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_output_slots.id"))
    version: Mapped[int] = mapped_column(Integer())
    status: Mapped[str] = mapped_column(String(30))
    has_blocking_issues: Mapped[bool] = mapped_column(Boolean(), default=False)
    title_snapshot: Mapped[str | None] = mapped_column(String(300), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSONB())
    based_on_brief_version: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    temperature: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    provider_call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    revision_count: Mapped[int] = mapped_column(Integer(), default=0)
    revision_of_version: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    created_at: Mapped[datetime] = _created_at()


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[uuid.UUID] = _pk()
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_output_versions.id")
    )
    decision: Mapped[str] = mapped_column(String(30))
    comment: Mapped[str | None] = mapped_column(Text(), nullable=True)
    human_verified: Mapped[bool] = mapped_column(Boolean(), default=False)
    actor: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = _created_at()


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = _pk()
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    actor: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(50))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB(), default=dict)
    created_at: Mapped[datetime] = _created_at()


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("key", "endpoint"),)

    id: Mapped[uuid.UUID] = _pk()
    key: Mapped[str] = mapped_column(String(200))
    endpoint: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(Integer())
    response_body: Mapped[dict] = mapped_column(JSONB())
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProviderCall(Base):
    __tablename__ = "provider_calls"

    id: Mapped[uuid.UUID] = _pk()
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    step_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer(), default=0)
    output_tokens: Mapped[int] = mapped_column(Integer(), default=0)
    latency_ms: Mapped[int] = mapped_column(Integer(), default=0)
    estimated_cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    status: Mapped[str] = mapped_column(String(30))
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = _created_at()
```

- [ ] **Step 5: 配好 Alembic 并生成基线迁移**

```powershell
cd apps\api
uv add sqlalchemy psycopg[binary] alembic
uv run alembic init alembic
```

把 `apps/api/alembic/env.py` 中的元数据与连接串改为读取应用配置：

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.infrastructure.db.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

生成并重命名迁移：

```powershell
uv run alembic revision --autogenerate -m "baseline"
uv run alembic upgrade head
```

把生成的文件重命名为 `apps/api/alembic/versions/0001_baseline.py`，并核对它确实包含上面 11 张表和三处唯一约束。

- [ ] **Step 6: 写 session 与测试夹具**

`apps/api/app/infrastructure/db/session.py`：

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
```

`apps/api/tests/conftest.py` 追加：

```python
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.infrastructure.db.models import Base
from app.infrastructure.db.session import SessionLocal


@pytest.fixture(scope="session", autouse=True)
def _schema():
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield


@pytest.fixture()
def db_session():
    with SessionLocal() as session:
        yield session
        session.rollback()


@pytest.fixture(autouse=True)
def _truncate(db_session):
    yield
    tables = ",".join(reversed([t.name for t in Base.metadata.sorted_tables]))
    db_session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    db_session.commit()
```

`apps/api/app/api/health.py` 增加数据库探测：

```python
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get("/health")
def health(
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict:
    try:
        session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "error"
    return {"status": "ok", "app_version": settings.app_version, "database": database}
```

- [ ] **Step 7: 运行测试确认通过**

Run: `uv run pytest tests -v`
Expected: 全部 passed

- [ ] **Step 8: 提交**

```powershell
git add apps/api infra/docker-compose.yml
git commit -m "feat(api): 核心表模型与基线迁移"
```

---

## Task 3: 幂等键

**Files:**
- Create: `apps/api/app/application/idempotency.py`
- Create: `apps/api/tests/test_idempotency.py`

**Interfaces:**
- Consumes: `IdempotencyKey` 模型（Task 2）、`AppError`（Task 1）。
- Produces: `request_fingerprint(endpoint: str, body: bytes) -> str`；`IdempotencyStore(session: Session)`，方法 `lookup(key: str, endpoint: str, fingerprint: str) -> dict | None`（命中且指纹一致返回首次响应体，指纹不一致抛 `AppError("IDEMPOTENCY_KEY_REUSED", ..., status_code=409)`）与 `remember(key, endpoint, fingerprint, status, body) -> None`。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/test_idempotency.py`：

```python
import pytest

from app.application.idempotency import IdempotencyStore, request_fingerprint
from app.errors import AppError


def test_lookup_returns_none_when_key_is_new(db_session):
    store = IdempotencyStore(db_session)

    assert store.lookup("k1", "/api/v1/tasks", "hash-a") is None


def test_lookup_returns_first_response_for_same_key_and_body(db_session):
    store = IdempotencyStore(db_session)
    store.remember("k1", "/api/v1/tasks", "hash-a", 201, {"id": "abc"})

    assert store.lookup("k1", "/api/v1/tasks", "hash-a") == {"id": "abc"}


def test_lookup_rejects_same_key_with_different_body(db_session):
    store = IdempotencyStore(db_session)
    store.remember("k1", "/api/v1/tasks", "hash-a", 201, {"id": "abc"})

    with pytest.raises(AppError) as exc:
        store.lookup("k1", "/api/v1/tasks", "hash-b")

    assert exc.value.code == "IDEMPOTENCY_KEY_REUSED"
    assert exc.value.status_code == 409


def test_same_key_on_different_endpoint_is_independent(db_session):
    store = IdempotencyStore(db_session)
    store.remember("k1", "/api/v1/tasks", "hash-a", 201, {"id": "abc"})

    assert store.lookup("k1", "/api/v1/exports", "hash-b") is None


def test_fingerprint_changes_with_body():
    assert request_fingerprint("/x", b"{}") != request_fingerprint("/x", b"{'a':1}")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_idempotency.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.application.idempotency'`

- [ ] **Step 3: 写最小实现**

```python
import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.infrastructure.db.models import IdempotencyKey

TTL = timedelta(hours=24)


def request_fingerprint(endpoint: str, body: bytes) -> str:
    return hashlib.sha256(endpoint.encode("utf-8") + b"|" + body).hexdigest()


class IdempotencyStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lookup(self, key: str, endpoint: str, fingerprint: str) -> dict | None:
        record = self._session.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.key == key, IdempotencyKey.endpoint == endpoint
            )
        )
        if record is None:
            return None
        if record.request_hash != fingerprint:
            raise AppError(
                "IDEMPOTENCY_KEY_REUSED",
                "相同的幂等键被用于不同的请求内容",
                status_code=409,
            )
        return record.response_body

    def remember(
        self,
        key: str,
        endpoint: str,
        fingerprint: str,
        status: int,
        body: dict,
    ) -> None:
        self._session.add(
            IdempotencyKey(
                key=key,
                endpoint=endpoint,
                request_hash=fingerprint,
                response_status=status,
                response_body=body,
                expires_at=datetime.now(UTC) + TTL,
            )
        )
        self._session.flush()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_idempotency.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```powershell
git add apps/api/app/application apps/api/tests/test_idempotency.py
git commit -m "feat(api): 幂等键存取与冲突检测"
```

---

## Task 4: 派生任务状态

**Files:**
- Create: `apps/api/app/domain/tasks/status.py`
- Create: `apps/api/tests/test_task_status.py`

**Interfaces:**
- Consumes: `TaskStatus`、`RunStatus`、`VersionStatus`（Task 2）。
- Produces: 纯函数

```python
def derive_task_status(
    *,
    run_status: RunStatus | None,
    version_statuses: Sequence[VersionStatus],
    expected_platform_count: int,
    needs_attention: bool = False,
    cancelled: bool = False,
    archived: bool = False,
    has_change_requests: bool = False,
) -> TaskStatus
```

不接触数据库、不做 IO。求值顺序对应设计文档 §6.1 的规则表：archived → cancelled → needs_attention → 无运行 → 运行失败 → 运行中 → changes_requested → approved → partially_ready → awaiting_review。

设计文档 §6.1 的第 4 条（按发布任务状态汇总出 `publish_pending` / `publishing` / `publish_attention` / `publish_failed` / `completed`）属于 M4 范围，M1 不实现，函数签名里也不预留发布参数——等 M4 引入发布任务表时再连同真值表一起扩展。

- [ ] **Step 1: 写失败测试（真值表）**

`apps/api/tests/test_task_status.py`：

```python
import pytest

from app.domain.enums import RunStatus, TaskStatus, VersionStatus
from app.domain.tasks.status import derive_task_status

A = VersionStatus.APPROVED
W = VersionStatus.AWAITING_REVIEW
R = VersionStatus.REJECTED


@pytest.mark.parametrize(
    ("run_status", "versions", "expected_count", "expected"),
    [
        (None, [], 2, TaskStatus.QUEUED),
        (RunStatus.RUNNING, [], 2, TaskStatus.RUNNING),
        (RunStatus.FAILED, [], 2, TaskStatus.FAILED),
        (RunStatus.SUCCEEDED, [W, W], 2, TaskStatus.AWAITING_REVIEW),
        (RunStatus.SUCCEEDED, [W], 2, TaskStatus.PARTIALLY_READY),
        (RunStatus.SUCCEEDED, [A, W], 2, TaskStatus.AWAITING_REVIEW),
        (RunStatus.SUCCEEDED, [A, A], 2, TaskStatus.APPROVED),
        (RunStatus.SUCCEEDED, [R, R], 2, TaskStatus.CANCELLED),
        (RunStatus.SUCCEEDED, [A, R], 2, TaskStatus.APPROVED),
    ],
)
def test_status_truth_table(run_status, versions, expected_count, expected):
    assert (
        derive_task_status(
            run_status=run_status,
            version_statuses=versions,
            expected_platform_count=expected_count,
        )
        == expected
    )


def test_archived_wins_over_everything():
    assert (
        derive_task_status(
            run_status=RunStatus.RUNNING,
            version_statuses=[A],
            expected_platform_count=1,
            needs_attention=True,
            cancelled=True,
            archived=True,
        )
        == TaskStatus.ARCHIVED
    )


def test_cancelled_wins_over_needs_attention():
    assert (
        derive_task_status(
            run_status=RunStatus.RUNNING,
            version_statuses=[],
            expected_platform_count=1,
            needs_attention=True,
            cancelled=True,
        )
        == TaskStatus.CANCELLED
    )


def test_needs_attention_wins_over_running():
    assert (
        derive_task_status(
            run_status=RunStatus.RUNNING,
            version_statuses=[],
            expected_platform_count=1,
            needs_attention=True,
        )
        == TaskStatus.NEEDS_ATTENTION
    )


def test_change_requests_take_precedence_over_awaiting_review():
    assert (
        derive_task_status(
            run_status=RunStatus.SUCCEEDED,
            version_statuses=[W, W],
            expected_platform_count=2,
            has_change_requests=True,
        )
        == TaskStatus.CHANGES_REQUESTED
    )


def test_change_requests_do_not_override_cancellation():
    assert (
        derive_task_status(
            run_status=RunStatus.SUCCEEDED,
            version_statuses=[R, R],
            expected_platform_count=2,
            has_change_requests=True,
        )
        == TaskStatus.CANCELLED
    )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_task_status.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.domain.tasks.status'`

- [ ] **Step 3: 写最小实现**

```python
from collections.abc import Sequence

from app.domain.enums import RunStatus, TaskStatus, VersionStatus


def derive_task_status(
    *,
    run_status: RunStatus | None,
    version_statuses: Sequence[VersionStatus],
    expected_platform_count: int,
    needs_attention: bool = False,
    cancelled: bool = False,
    archived: bool = False,
    has_change_requests: bool = False,
) -> TaskStatus:
    if archived:
        return TaskStatus.ARCHIVED
    if cancelled:
        return TaskStatus.CANCELLED
    if needs_attention:
        return TaskStatus.NEEDS_ATTENTION
    if run_status is None:
        return TaskStatus.QUEUED
    if run_status is RunStatus.FAILED:
        return TaskStatus.FAILED
    if run_status is RunStatus.CANCELLED:
        return TaskStatus.CANCELLED
    if run_status is RunStatus.RUNNING:
        return TaskStatus.RUNNING

    settled = [s for s in version_statuses if s is not VersionStatus.DRAFT]
    if not settled:
        return TaskStatus.RUNNING
    if all(s is VersionStatus.REJECTED for s in settled):
        return TaskStatus.CANCELLED
    if has_change_requests:
        return TaskStatus.CHANGES_REQUESTED
    live = [s for s in settled if s is not VersionStatus.REJECTED]
    if all(s is VersionStatus.APPROVED for s in live):
        return TaskStatus.APPROVED
    if len(settled) < expected_platform_count:
        return TaskStatus.PARTIALLY_READY
    return TaskStatus.AWAITING_REVIEW
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_task_status.py -v`
Expected: 14 passed

- [ ] **Step 5: 提交**

```powershell
git add apps/api/app/domain apps/api/tests/test_task_status.py
git commit -m "feat(api): 任务总状态派生规则与真值表测试"
```

---

## Task 5: 任务创建、列表与详情

**Files:**
- Create: `apps/api/app/domain/tasks/service.py`
- Create: `apps/api/app/api/tasks.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_tasks_api.py`

**Interfaces:**
- Consumes: `IdempotencyStore`、`request_fingerprint`（Task 3）；`derive_task_status`（Task 4）；ORM 模型（Task 2）。
- Produces: `create_task(session, payload: TaskCreate) -> ContentTask`；`list_tasks(session) -> list[TaskSummary]`；`get_task_detail(session, task_id) -> TaskDetail`；Pydantic 模型 `TaskCreate`（字段 `topic`、`audience`、`goal`、`platforms: list[Platform]`、`tone`、`requirements`、`prohibited_items`）、`TaskSummary`、`TaskDetail`；路由 `POST /api/v1/tasks`、`GET /api/v1/tasks`、`GET /api/v1/tasks/{task_id}`。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/test_tasks_api.py`：

```python
PAYLOAD = {
    "topic": "咖啡因如何影响睡眠质量",
    "audience": "熬夜上班族",
    "goal": "education",
    "platforms": ["xiaohongshu"],
    "tone": "专业、实用",
}


def _create(client, payload=None, key="key-1"):
    return client.post(
        "/api/v1/tasks",
        json=payload or PAYLOAD,
        headers={"Idempotency-Key": key},
    )


def test_create_task_returns_queued_task(client):
    response = _create(client)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["topic"] == PAYLOAD["topic"]
    assert body["platforms"] == ["xiaohongshu"]


def test_create_task_rejects_short_topic(client):
    response = _create(client, {**PAYLOAD, "topic": "太短"})

    assert response.status_code == 422


def test_create_task_requires_at_least_one_platform(client):
    response = _create(client, {**PAYLOAD, "platforms": []})

    assert response.status_code == 422


def test_repeated_idempotency_key_returns_same_task(client):
    first = _create(client)
    second = _create(client)

    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]


def test_create_task_writes_audit_event(client, db_session):
    from sqlalchemy import select

    from app.infrastructure.db.models import AuditEvent

    task_id = _create(client).json()["id"]
    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.action == "task.created")
    ).all()

    assert [str(e.task_id) for e in events] == [task_id]


def test_task_list_is_ordered_by_updated_at_desc(client):
    first = _create(client, key="k-a").json()["id"]
    second = _create(client, {**PAYLOAD, "topic": "另一个足够长的主题内容"}, key="k-b")

    ids = [t["id"] for t in client.get("/api/v1/tasks").json()["items"]]

    assert ids == [second.json()["id"], first]


def test_task_detail_includes_steps_and_slots(client):
    task_id = _create(client).json()["id"]

    body = client.get(f"/api/v1/tasks/{task_id}").json()

    assert body["status"] == "queued"
    assert body["steps"] == []
    assert body["output_slots"] == []


def test_unknown_task_returns_error_envelope(client):
    response = client.get("/api/v1/tasks/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_tasks_api.py -v`
Expected: FAIL，全部 404（路由尚未注册）

- [ ] **Step 3: 写 domain 服务**

`apps/api/app/domain/tasks/service.py`：

```python
import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ContentType, Platform, RunStatus, VersionStatus
from app.domain.tasks.status import derive_task_status
from app.errors import AppError
from app.infrastructure.db.models import (
    AuditEvent,
    ContentOutputSlot,
    ContentOutputVersion,
    ContentTask,
    Project,
    ReviewDecision,
    TaskPlatform,
    WorkflowRun,
    WorkflowStepRun,
)

DEFAULT_PROJECT_NAME = "默认项目"

CONTENT_TYPE_BY_PLATFORM = {
    Platform.XIAOHONGSHU: ContentType.NOTE,
    Platform.DOUYIN: ContentType.SCRIPT,
}


class TaskCreate(BaseModel):
    topic: str = Field(min_length=5, max_length=300)
    audience: str = Field(min_length=2, max_length=200)
    goal: str
    platforms: list[Platform] = Field(min_length=1)
    tone: str = Field(min_length=1, max_length=200)
    requirements: str | None = Field(default=None, max_length=1000)
    prohibited_items: str | None = Field(default=None, max_length=1000)


def ensure_default_project(session: Session) -> Project:
    project = session.scalar(select(Project).limit(1))
    if project is None:
        project = Project(name=DEFAULT_PROJECT_NAME)
        session.add(project)
        session.flush()
    return project


def create_task(session: Session, payload: TaskCreate) -> ContentTask:
    project = ensure_default_project(session)
    task = ContentTask(
        project_id=project.id,
        topic=payload.topic,
        audience=payload.audience,
        goal=payload.goal,
        tone=payload.tone,
        requirements=payload.requirements,
        prohibited_items=payload.prohibited_items,
    )
    session.add(task)
    session.flush()

    for platform in payload.platforms:
        session.add(
            TaskPlatform(
                task_id=task.id,
                platform=platform.value,
                content_type=CONTENT_TYPE_BY_PLATFORM[platform].value,
            )
        )

    session.add(
        AuditEvent(
            task_id=task.id,
            actor="local_admin",
            action="task.created",
            entity_type="content_task",
            entity_id=task.id,
            metadata_json={"platforms": [p.value for p in payload.platforms]},
        )
    )
    session.flush()
    return task


def _active_run(session: Session, task_id: uuid.UUID) -> WorkflowRun | None:
    return session.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.task_id == task_id)
        .order_by(WorkflowRun.started_at.desc())
        .limit(1)
    )


def _current_version_statuses(
    session: Session, task_id: uuid.UUID
) -> list[VersionStatus]:
    rows = session.execute(
        select(ContentOutputVersion.status)
        .join(ContentOutputSlot, ContentOutputSlot.current_version_id == ContentOutputVersion.id)
        .where(ContentOutputSlot.task_id == task_id)
    ).all()
    return [VersionStatus(row[0]) for row in rows]


def _has_change_requests(session: Session, task_id: uuid.UUID) -> bool:
    rows = session.execute(
        select(ReviewDecision.version_id, ReviewDecision.decision)
        .join(
            ContentOutputVersion,
            ContentOutputVersion.id == ReviewDecision.version_id,
        )
        .join(
            ContentOutputSlot,
            ContentOutputSlot.current_version_id == ContentOutputVersion.id,
        )
        .where(ContentOutputSlot.task_id == task_id)
        .order_by(ReviewDecision.created_at)
    ).all()
    latest_by_version = {row.version_id: row.decision for row in rows}
    return "request_changes" in latest_by_version.values()


def task_status(session: Session, task: ContentTask):
    run = _active_run(session, task.id)
    expected = len(
        session.scalars(
            select(TaskPlatform.id).where(TaskPlatform.task_id == task.id)
        ).all()
    )
    return derive_task_status(
        run_status=RunStatus(run.status) if run else None,
        version_statuses=_current_version_statuses(session, task.id),
        expected_platform_count=expected,
        needs_attention=task.needs_attention,
        cancelled=task.cancelled,
        archived=task.archived,
        has_change_requests=_has_change_requests(session, task.id),
    )


def get_task_or_404(session: Session, task_id: uuid.UUID) -> ContentTask:
    task = session.get(ContentTask, task_id)
    if task is None:
        raise AppError("TASK_NOT_FOUND", "任务不存在", status_code=404)
    return task


def list_steps(session: Session, task_id: uuid.UUID) -> list[WorkflowStepRun]:
    return list(
        session.scalars(
            select(WorkflowStepRun)
            .join(WorkflowRun, WorkflowRun.id == WorkflowStepRun.run_id)
            .where(WorkflowRun.task_id == task_id)
            .order_by(WorkflowStepRun.started_at)
        ).all()
    )
```

- [ ] **Step 4: 写路由**

`apps/api/app/api/tasks.py`：

```python
import uuid

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.idempotency import IdempotencyStore, request_fingerprint
from app.domain.tasks.service import (
    TaskCreate,
    create_task,
    get_task_or_404,
    list_steps,
    task_status,
)
from app.infrastructure.db.models import (
    ContentOutputSlot,
    ContentTask,
    TaskPlatform,
)
from app.infrastructure.db.session import get_session

router = APIRouter()


def _summary(session: Session, task: ContentTask) -> dict:
    platforms = session.scalars(
        select(TaskPlatform.platform).where(TaskPlatform.task_id == task.id)
    ).all()
    return {
        "id": str(task.id),
        "topic": task.topic,
        "platforms": list(platforms),
        "status": task_status(session, task).value,
        "current_step": task.current_step,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


@router.post("/tasks", status_code=201)
async def post_task(
    request: Request,
    response: Response,
    payload: TaskCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> dict:
    endpoint = "/api/v1/tasks"
    fingerprint = request_fingerprint(endpoint, await request.body())
    store = IdempotencyStore(session)

    cached = store.lookup(idempotency_key, endpoint, fingerprint)
    if cached is not None:
        return cached

    task = create_task(session, payload)
    body = _summary(session, task)
    store.remember(idempotency_key, endpoint, fingerprint, 201, body)
    session.commit()
    return body


@router.get("/tasks")
def get_tasks(session: Session = Depends(get_session)) -> dict:
    tasks = session.scalars(
        select(ContentTask).order_by(ContentTask.updated_at.desc())
    ).all()
    return {"items": [_summary(session, t) for t in tasks]}


@router.get("/tasks/{task_id}")
def get_task(task_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    task = get_task_or_404(session, task_id)
    slots = session.scalars(
        select(ContentOutputSlot).where(ContentOutputSlot.task_id == task.id)
    ).all()
    return {
        **_summary(session, task),
        "audience": task.audience,
        "goal": task.goal,
        "tone": task.tone,
        "requirements": task.requirements,
        "steps": [
            {
                "step_key": s.step_key,
                "attempt": s.attempt,
                "status": s.status,
                "error_code": s.error_code,
                "error_message": s.error_message,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            }
            for s in list_steps(session, task.id)
        ],
        "output_slots": [
            {
                "id": str(s.id),
                "platform": s.platform,
                "content_type": s.content_type,
                "current_version_id": str(s.current_version_id)
                if s.current_version_id
                else None,
            }
            for s in slots
        ],
    }
```

`apps/api/app/main.py` 挂载路由：

```python
from app.api import health, tasks

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests -v`
Expected: 全部 passed

- [ ] **Step 6: 提交**

```powershell
git add apps/api
git commit -m "feat(api): 任务创建、列表与详情接口"
```

---

## Task 6: 编排内部接口与步骤 attempt 分配

**Files:**
- Create: `apps/api/app/domain/runs/service.py`
- Create: `apps/api/app/api/internal.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_internal_runs.py`

**Interfaces:**
- Consumes: `WorkflowRun`、`WorkflowStepRun`、`ContentTask`（Task 2）；`Settings.internal_api_token`（Task 1）。
- Produces: `claim_run(session, task_id, n8n_execution_id) -> WorkflowRun`；`start_step(session, run_id, step_key) -> WorkflowStepRun`（服务端分配 attempt，从 1 递增）；`complete_step(session, run_id, step_key, attempt) -> None`；`fail_step(session, run_id, step_key, attempt, error_code, error_message, retryable) -> None`；`finish_run(session, run_id, status) -> None`；依赖 `require_internal_token`；路由 `POST /internal/v1/tasks/{task_id}/runs`、`POST /internal/v1/runs/{run_id}/steps/{step_key}/start`、`.../complete`、`.../fail`、`POST /internal/v1/runs/{run_id}/finish`。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/test_internal_runs.py`：

```python
import pytest

HEADERS = {"X-Internal-Token": "dev-internal-token"}
PAYLOAD = {
    "topic": "咖啡因如何影响睡眠质量",
    "audience": "熬夜上班族",
    "goal": "education",
    "platforms": ["xiaohongshu"],
    "tone": "专业、实用",
}


@pytest.fixture()
def task_id(client):
    return client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k"}
    ).json()["id"]


def test_internal_endpoint_requires_token(client, task_id):
    response = client.post(f"/internal/v1/tasks/{task_id}/runs", json={})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INTERNAL_AUTH_REQUIRED"


def test_claim_run_creates_running_run(client, task_id):
    response = client.post(
        f"/internal/v1/tasks/{task_id}/runs",
        json={"n8n_execution_id": "exec-1"},
        headers=HEADERS,
    )

    assert response.status_code == 201
    assert response.json()["status"] == "running"


def test_step_attempt_increments_on_each_start(client, task_id):
    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS
    ).json()["id"]

    first = client.post(
        f"/internal/v1/runs/{run_id}/steps/research/start", headers=HEADERS
    ).json()
    second = client.post(
        f"/internal/v1/runs/{run_id}/steps/research/start", headers=HEADERS
    ).json()

    assert first["attempt"] == 1
    assert second["attempt"] == 2


def test_task_status_becomes_running_after_run_claimed(client, task_id):
    client.post(f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS)

    assert client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "running"


def test_failed_step_records_error_and_marks_run_failed(client, task_id):
    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS
    ).json()["id"]
    client.post(f"/internal/v1/runs/{run_id}/steps/research/start", headers=HEADERS)
    client.post(
        f"/internal/v1/runs/{run_id}/steps/research/fail",
        json={
            "attempt": 1,
            "error_code": "PROVIDER_TIMEOUT",
            "error_message": "模型服务超时",
            "retryable": True,
        },
        headers=HEADERS,
    )
    client.post(
        f"/internal/v1/runs/{run_id}/finish", json={"status": "failed"}, headers=HEADERS
    )

    detail = client.get(f"/api/v1/tasks/{task_id}").json()

    assert detail["status"] == "failed"
    assert detail["steps"][0]["error_code"] == "PROVIDER_TIMEOUT"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_internal_runs.py -v`
Expected: FAIL，全部 404

- [ ] **Step 3: 写 domain 服务**

`apps/api/app/domain/runs/service.py`：

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import RunStatus, StepStatus
from app.errors import AppError
from app.infrastructure.db.models import WorkflowRun, WorkflowStepRun


def claim_run(
    session: Session, task_id: uuid.UUID, n8n_execution_id: str | None
) -> WorkflowRun:
    existing = session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.task_id == task_id,
            WorkflowRun.status == RunStatus.RUNNING.value,
        )
    )
    if existing is not None:
        raise AppError(
            "RUN_ALREADY_ACTIVE", "该任务已有一个进行中的运行", status_code=409
        )
    run = WorkflowRun(
        task_id=task_id,
        workflow_key="wf01_content_pipeline",
        status=RunStatus.RUNNING.value,
        n8n_execution_id=n8n_execution_id,
    )
    session.add(run)
    session.flush()
    return run


def start_step(
    session: Session, run_id: uuid.UUID, step_key: str
) -> WorkflowStepRun:
    last = session.scalar(
        select(func.max(WorkflowStepRun.attempt)).where(
            WorkflowStepRun.run_id == run_id, WorkflowStepRun.step_key == step_key
        )
    )
    step = WorkflowStepRun(
        run_id=run_id,
        step_key=step_key,
        attempt=(last or 0) + 1,
        status=StepStatus.RUNNING.value,
        heartbeat_at=datetime.now(UTC),
    )
    session.add(step)
    session.flush()
    return step


def _get_step(
    session: Session, run_id: uuid.UUID, step_key: str, attempt: int
) -> WorkflowStepRun:
    step = session.scalar(
        select(WorkflowStepRun).where(
            WorkflowStepRun.run_id == run_id,
            WorkflowStepRun.step_key == step_key,
            WorkflowStepRun.attempt == attempt,
        )
    )
    if step is None:
        raise AppError("STEP_NOT_FOUND", "步骤运行记录不存在", status_code=404)
    return step


def complete_step(
    session: Session, run_id: uuid.UUID, step_key: str, attempt: int
) -> WorkflowStepRun:
    step = _get_step(session, run_id, step_key, attempt)
    if step.status == StepStatus.SUCCEEDED.value:
        return step
    step.status = StepStatus.SUCCEEDED.value
    step.ended_at = datetime.now(UTC)
    session.flush()
    return step


def fail_step(
    session: Session,
    run_id: uuid.UUID,
    step_key: str,
    attempt: int,
    error_code: str,
    error_message: str,
    retryable: bool,
) -> WorkflowStepRun:
    step = _get_step(session, run_id, step_key, attempt)
    step.status = StepStatus.FAILED.value
    step.error_code = error_code
    step.error_message = error_message
    step.retryable = retryable
    step.ended_at = datetime.now(UTC)
    session.flush()
    return step


def finish_run(session: Session, run_id: uuid.UUID, status: RunStatus) -> WorkflowRun:
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise AppError("RUN_NOT_FOUND", "运行不存在", status_code=404)
    run.status = status.value
    run.ended_at = datetime.now(UTC)
    session.flush()
    return run
```

- [ ] **Step 4: 写鉴权依赖与路由**

`apps/api/app/api/internal.py`：

```python
import uuid

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.domain.enums import RunStatus
from app.domain.runs.service import (
    claim_run,
    complete_step,
    fail_step,
    finish_run,
    start_step,
)
from app.errors import AppError
from app.infrastructure.db.session import get_session

router = APIRouter()


def require_internal_token(
    x_internal_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if x_internal_token != settings.internal_api_token:
        raise AppError(
            "INTERNAL_AUTH_REQUIRED", "缺少或错误的内部调用凭据", status_code=401
        )


class ClaimRunRequest(BaseModel):
    n8n_execution_id: str | None = None


class StepResultRequest(BaseModel):
    attempt: int


class StepFailureRequest(StepResultRequest):
    error_code: str
    error_message: str
    retryable: bool = False


class FinishRunRequest(BaseModel):
    status: RunStatus


@router.post("/tasks/{task_id}/runs", status_code=201)
def post_run(
    task_id: uuid.UUID,
    payload: ClaimRunRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_internal_token),
) -> dict:
    run = claim_run(session, task_id, payload.n8n_execution_id)
    session.commit()
    return {"id": str(run.id), "status": run.status}


@router.post("/runs/{run_id}/steps/{step_key}/start")
def post_step_start(
    run_id: uuid.UUID,
    step_key: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_internal_token),
) -> dict:
    step = start_step(session, run_id, step_key)
    session.commit()
    return {"step_key": step.step_key, "attempt": step.attempt, "status": step.status}


@router.post("/runs/{run_id}/steps/{step_key}/complete")
def post_step_complete(
    run_id: uuid.UUID,
    step_key: str,
    payload: StepResultRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_internal_token),
) -> dict:
    step = complete_step(session, run_id, step_key, payload.attempt)
    session.commit()
    return {"step_key": step.step_key, "attempt": step.attempt, "status": step.status}


@router.post("/runs/{run_id}/steps/{step_key}/fail")
def post_step_fail(
    run_id: uuid.UUID,
    step_key: str,
    payload: StepFailureRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_internal_token),
) -> dict:
    step = fail_step(
        session,
        run_id,
        step_key,
        payload.attempt,
        payload.error_code,
        payload.error_message,
        payload.retryable,
    )
    session.commit()
    return {"step_key": step.step_key, "attempt": step.attempt, "status": step.status}


@router.post("/runs/{run_id}/finish")
def post_run_finish(
    run_id: uuid.UUID,
    payload: FinishRunRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_internal_token),
) -> dict:
    run = finish_run(session, run_id, payload.status)
    session.commit()
    return {"id": str(run.id), "status": run.status}
```

`apps/api/app/main.py` 追加：

```python
from app.api import health, internal, tasks

    app.include_router(internal.router, prefix="/internal/v1")
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests -v`
Expected: 全部 passed

- [ ] **Step 6: 提交**

```powershell
git add apps/api
git commit -m "feat(api): 编排内部接口与步骤 attempt 分配"
```

---

## Task 7: Mock Provider 与内容生成

**Files:**
- Create: `apps/api/app/infrastructure/providers/llm.py`
- Create: `apps/api/app/domain/content/service.py`
- Create: `apps/api/app/api/content.py`
- Modify: `apps/api/app/api/internal.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_content_generation.py`

**Interfaces:**
- Consumes: `ContentOutputSlot`、`ContentOutputVersion`、`ProviderCall`、`TaskPlatform`（Task 2）；`require_internal_token`（Task 6）。
- Produces: 协议 `LLMProvider`（方法 `generate_note(topic: str, audience: str, tone: str) -> dict`、`generate_script(topic: str, audience: str, tone: str) -> dict`，附带属性 `name: str`、`model: str`）；`MockLLMProvider`；`get_llm_provider() -> LLMProvider`；`generate_output(session, task_id, platform) -> ContentOutputVersion`；`create_manual_version(session, slot_id, payload_json) -> ContentOutputVersion`；路由 `POST /internal/v1/tasks/{task_id}/generate/{platform}`、`GET /api/v1/output-slots/{slot_id}`、`POST /api/v1/output-slots/{slot_id}/versions`。

小红书 payload 结构（M1 固定字段）：`{"title": str, "hook": str, "body": str, "cover_text": str, "hashtags": [str], "factual_claims": [], "claim_source_map": []}`。M1 的 `factual_claims` 与 `claim_source_map` 恒为空数组，M2 接真实调研后才填充。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/test_content_generation.py`：

```python
import pytest

HEADERS = {"X-Internal-Token": "dev-internal-token"}
PAYLOAD = {
    "topic": "咖啡因如何影响睡眠质量",
    "audience": "熬夜上班族",
    "goal": "education",
    "platforms": ["xiaohongshu"],
    "tone": "专业、实用",
}


@pytest.fixture()
def task_id(client):
    return client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k"}
    ).json()["id"]


def test_generate_creates_slot_and_first_version(client, task_id):
    response = client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    )

    assert response.status_code == 201
    body = response.json()
    assert body["version"] == 1
    assert body["status"] == "awaiting_review"


def test_generated_payload_has_required_fields(client, task_id):
    version = client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    ).json()
    slot = client.get(f"/api/v1/output-slots/{version['slot_id']}").json()

    payload = slot["versions"][0]["payload"]
    assert set(payload) >= {
        "title",
        "hook",
        "body",
        "cover_text",
        "hashtags",
        "factual_claims",
        "claim_source_map",
    }
    assert payload["title"]


def test_generation_records_provider_call(client, task_id, db_session):
    from sqlalchemy import select

    from app.infrastructure.db.models import ProviderCall

    client.post(f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS)
    calls = db_session.scalars(select(ProviderCall)).all()

    assert len(calls) == 1
    assert calls[0].provider == "mock"
    assert calls[0].status == "succeeded"


def test_version_records_model_and_prompt_version(client, task_id):
    version = client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    ).json()
    slot = client.get(f"/api/v1/output-slots/{version['slot_id']}").json()

    assert slot["versions"][0]["model"]
    assert slot["versions"][0]["prompt_version"]


def test_manual_version_increments_and_becomes_current(client, task_id):
    generated = client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    ).json()
    slot_id = generated["slot_id"]

    created = client.post(
        f"/api/v1/output-slots/{slot_id}/versions",
        json={"payload": {"title": "人工改过的标题", "body": "正文", "hashtags": []}},
    ).json()
    slot = client.get(f"/api/v1/output-slots/{slot_id}").json()

    assert created["version"] == 2
    assert slot["current_version_id"] == created["id"]


def test_task_status_is_awaiting_review_after_generation(client, task_id):
    client.post(f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS)
    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS
    ).json()["id"]
    client.post(
        f"/internal/v1/runs/{run_id}/finish",
        json={"status": "succeeded"},
        headers=HEADERS,
    )

    assert client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "awaiting_review"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_content_generation.py -v`
Expected: FAIL，全部 404

- [ ] **Step 3: 写 Provider**

`apps/api/app/infrastructure/providers/llm.py`：

```python
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
```

- [ ] **Step 4: 写内容服务**

`apps/api/app/domain/content/service.py`：

```python
import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import Platform, VersionStatus
from app.errors import AppError
from app.infrastructure.db.models import (
    ContentOutputSlot,
    ContentOutputVersion,
    ContentTask,
    ProviderCall,
    TaskPlatform,
)
from app.infrastructure.providers.llm import PROMPT_VERSION, get_llm_provider


def _get_or_create_slot(
    session: Session, task_id: uuid.UUID, platform: Platform
) -> ContentOutputSlot:
    task_platform = session.scalar(
        select(TaskPlatform).where(
            TaskPlatform.task_id == task_id, TaskPlatform.platform == platform.value
        )
    )
    if task_platform is None:
        raise AppError(
            "PLATFORM_NOT_IN_TASK", "该任务未选择这个平台", status_code=400
        )
    slot = session.scalar(
        select(ContentOutputSlot).where(
            ContentOutputSlot.task_id == task_id,
            ContentOutputSlot.platform == platform.value,
            ContentOutputSlot.content_type == task_platform.content_type,
        )
    )
    if slot is None:
        slot = ContentOutputSlot(
            task_id=task_id,
            platform=platform.value,
            content_type=task_platform.content_type,
        )
        session.add(slot)
        session.flush()
    return slot


def _next_version(session: Session, slot_id: uuid.UUID) -> int:
    current = session.scalar(
        select(func.max(ContentOutputVersion.version)).where(
            ContentOutputVersion.slot_id == slot_id
        )
    )
    return (current or 0) + 1


def generate_output(
    session: Session, task_id: uuid.UUID, platform: Platform
) -> ContentOutputVersion:
    task = session.get(ContentTask, task_id)
    if task is None:
        raise AppError("TASK_NOT_FOUND", "任务不存在", status_code=404)

    slot = _get_or_create_slot(session, task_id, platform)
    provider = get_llm_provider()

    started = time.perf_counter()
    if platform is Platform.XIAOHONGSHU:
        payload = provider.generate_note(task.topic, task.audience, task.tone)
    else:
        payload = provider.generate_script(task.topic, task.audience, task.tone)
    latency_ms = int((time.perf_counter() - started) * 1000)

    call = ProviderCall(
        task_id=task_id,
        provider=provider.name,
        model=provider.model,
        prompt_version=PROMPT_VERSION,
        latency_ms=latency_ms,
        status="succeeded",
    )
    session.add(call)
    session.flush()

    version = ContentOutputVersion(
        slot_id=slot.id,
        version=_next_version(session, slot.id),
        status=VersionStatus.AWAITING_REVIEW.value,
        title_snapshot=payload.get("title") or payload.get("hook"),
        payload_json=payload,
        prompt_version=PROMPT_VERSION,
        model=provider.model,
        provider_call_id=call.id,
    )
    session.add(version)
    session.flush()
    slot.current_version_id = version.id
    session.flush()
    return version


def create_manual_version(
    session: Session, slot_id: uuid.UUID, payload: dict
) -> ContentOutputVersion:
    slot = session.get(ContentOutputSlot, slot_id)
    if slot is None:
        raise AppError("SLOT_NOT_FOUND", "内容位不存在", status_code=404)

    version = ContentOutputVersion(
        slot_id=slot.id,
        version=_next_version(session, slot.id),
        status=VersionStatus.AWAITING_REVIEW.value,
        title_snapshot=payload.get("title"),
        payload_json=payload,
    )
    session.add(version)
    session.flush()
    slot.current_version_id = version.id
    session.flush()
    return version
```

- [ ] **Step 5: 写路由**

`apps/api/app/api/content.py`：

```python
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.content.service import create_manual_version
from app.errors import AppError
from app.infrastructure.db.models import ContentOutputSlot, ContentOutputVersion
from app.infrastructure.db.session import get_session

router = APIRouter()


class ManualVersionRequest(BaseModel):
    payload: dict


def serialize_version(version: ContentOutputVersion) -> dict:
    return {
        "id": str(version.id),
        "slot_id": str(version.slot_id),
        "version": version.version,
        "status": version.status,
        "has_blocking_issues": version.has_blocking_issues,
        "title_snapshot": version.title_snapshot,
        "payload": version.payload_json,
        "model": version.model,
        "prompt_version": version.prompt_version,
        "created_at": version.created_at.isoformat(),
    }


@router.get("/output-slots/{slot_id}")
def get_slot(slot_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    slot = session.get(ContentOutputSlot, slot_id)
    if slot is None:
        raise AppError("SLOT_NOT_FOUND", "内容位不存在", status_code=404)
    versions = session.scalars(
        select(ContentOutputVersion)
        .where(ContentOutputVersion.slot_id == slot_id)
        .order_by(ContentOutputVersion.version)
    ).all()
    return {
        "id": str(slot.id),
        "task_id": str(slot.task_id),
        "platform": slot.platform,
        "content_type": slot.content_type,
        "current_version_id": str(slot.current_version_id)
        if slot.current_version_id
        else None,
        "versions": [serialize_version(v) for v in versions],
    }


@router.post("/output-slots/{slot_id}/versions", status_code=201)
def post_version(
    slot_id: uuid.UUID,
    payload: ManualVersionRequest,
    session: Session = Depends(get_session),
) -> dict:
    version = create_manual_version(session, slot_id, payload.payload)
    session.commit()
    return serialize_version(version)
```

`apps/api/app/api/internal.py` 追加生成端点：

```python
from app.domain.content.service import generate_output
from app.domain.enums import Platform


@router.post("/tasks/{task_id}/generate/{platform}", status_code=201)
def post_generate(
    task_id: uuid.UUID,
    platform: Platform,
    session: Session = Depends(get_session),
    _: None = Depends(require_internal_token),
) -> dict:
    version = generate_output(session, task_id, platform)
    session.commit()
    return {
        "id": str(version.id),
        "slot_id": str(version.slot_id),
        "version": version.version,
        "status": version.status,
    }
```

`apps/api/app/main.py` 挂载 `content.router`（前缀 `/api/v1`）。

- [ ] **Step 6: 运行测试确认通过**

Run: `uv run pytest tests -v`
Expected: 全部 passed

- [ ] **Step 7: 提交**

```powershell
git add apps/api
git commit -m "feat(api): Mock Provider 生成内容槽位与不可变版本"
```

---

## Task 8: 审核与批准门禁

**Files:**
- Create: `apps/api/app/domain/review/service.py`
- Create: `apps/api/app/api/reviews.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_reviews.py`

**Interfaces:**
- Consumes: `ContentOutputVersion`、`ReviewDecision`、`AuditEvent`（Task 2）；`serialize_version`（Task 7）。
- Produces: `review_version(session, version_id, expected_version: int, decision: str, comment: str | None, human_verified: bool) -> ContentOutputVersion`；路由 `POST /api/v1/output-versions/{version_id}/review`、`GET /api/v1/reviews`。

门禁规则（M1 生效部分）：请求里的 `version` 与该版本行的 `version` 不一致时返回 409 `VERSION_CONFLICT`；`has_blocking_issues=True` 且未勾选 `human_verified` 时返回 422 `BLOCKING_ISSUES_PRESENT`；已经是 `approved` 的版本不能再次被评审，返回 409 `VERSION_IMMUTABLE`；`reject` 与 `request_changes` 必须带 comment。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/test_reviews.py`：

```python
import pytest

HEADERS = {"X-Internal-Token": "dev-internal-token"}
PAYLOAD = {
    "topic": "咖啡因如何影响睡眠质量",
    "audience": "熬夜上班族",
    "goal": "education",
    "platforms": ["xiaohongshu"],
    "tone": "专业、实用",
}


@pytest.fixture()
def version(client):
    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k"}
    ).json()["id"]
    return client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    ).json()


def test_approve_marks_version_approved(client, version):
    response = client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "approve"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_approve_with_stale_version_number_conflicts(client, version):
    response = client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 99, "decision": "approve"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_approved_version_cannot_be_reviewed_again(client, version):
    client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "approve"},
    )
    second = client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "reject", "comment": "反悔"},
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "VERSION_IMMUTABLE"


def test_reject_requires_comment(client, version):
    response = client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "reject"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REVIEW_COMMENT_REQUIRED"


def test_blocking_issues_prevent_approval_without_human_verification(
    client, version, db_session
):
    from app.infrastructure.db.models import ContentOutputVersion

    row = db_session.get(ContentOutputVersion, version["id"])
    row.has_blocking_issues = True
    db_session.commit()

    response = client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "approve"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "BLOCKING_ISSUES_PRESENT"


def test_human_verified_flag_allows_approval_and_is_audited(
    client, version, db_session
):
    from sqlalchemy import select

    from app.infrastructure.db.models import AuditEvent, ContentOutputVersion

    row = db_session.get(ContentOutputVersion, version["id"])
    row.has_blocking_issues = True
    db_session.commit()

    response = client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "approve", "human_verified": True},
    )
    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.action == "version.approved")
    ).all()

    assert response.status_code == 200
    assert events[0].metadata_json["human_verified"] is True


def test_review_queue_lists_awaiting_versions(client, version):
    items = client.get("/api/v1/reviews").json()["items"]

    assert [i["id"] for i in items] == [version["id"]]


def test_request_changes_moves_task_to_changes_requested(client):
    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k-cr"}
    ).json()["id"]
    version = client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    ).json()
    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS
    ).json()["id"]
    client.post(
        f"/internal/v1/runs/{run_id}/finish",
        json={"status": "succeeded"},
        headers=HEADERS,
    )

    client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "request_changes", "comment": "标题太夸张"},
    )

    assert (
        client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "changes_requested"
    )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_reviews.py -v`
Expected: FAIL，全部 404

- [ ] **Step 3: 写 domain 服务**

`apps/api/app/domain/review/service.py`：

```python
import uuid

from sqlalchemy.orm import Session

from app.domain.enums import VersionStatus
from app.errors import AppError
from app.infrastructure.db.models import (
    AuditEvent,
    ContentOutputSlot,
    ContentOutputVersion,
    ReviewDecision,
)

DECISION_TO_STATUS = {
    "approve": VersionStatus.APPROVED,
    "reject": VersionStatus.REJECTED,
    "request_changes": VersionStatus.AWAITING_REVIEW,
}


def review_version(
    session: Session,
    version_id: uuid.UUID,
    expected_version: int,
    decision: str,
    comment: str | None,
    human_verified: bool,
) -> ContentOutputVersion:
    version = session.get(ContentOutputVersion, version_id)
    if version is None:
        raise AppError("VERSION_NOT_FOUND", "内容版本不存在", status_code=404)
    if decision not in DECISION_TO_STATUS:
        raise AppError("UNKNOWN_DECISION", "不支持的审核动作", status_code=422)
    if version.version != expected_version:
        raise AppError(
            "VERSION_CONFLICT",
            "页面上的版本已过期，请刷新后重新审核",
            status_code=409,
        )
    if version.status == VersionStatus.APPROVED.value:
        raise AppError(
            "VERSION_IMMUTABLE", "已批准的版本不可再次评审", status_code=409
        )
    if decision in {"reject", "request_changes"} and not comment:
        raise AppError(
            "REVIEW_COMMENT_REQUIRED", "驳回或请求修改必须填写原因", status_code=422
        )
    if decision == "approve" and version.has_blocking_issues and not human_verified:
        raise AppError(
            "BLOCKING_ISSUES_PRESENT",
            "该版本存在阻断问题，需先处理或勾选人工已核对",
            status_code=422,
        )

    version.status = DECISION_TO_STATUS[decision].value
    session.add(
        ReviewDecision(
            version_id=version.id,
            decision=decision,
            comment=comment,
            human_verified=human_verified,
            actor="local_admin",
        )
    )
    slot = session.get(ContentOutputSlot, version.slot_id)
    session.add(
        AuditEvent(
            task_id=slot.task_id if slot else None,
            actor="local_admin",
            action=f"version.{DECISION_TO_STATUS[decision].value}",
            entity_type="content_output_version",
            entity_id=version.id,
            metadata_json={"human_verified": human_verified, "comment": comment},
        )
    )
    session.flush()
    return version
```

- [ ] **Step 4: 写路由**

`apps/api/app/api/reviews.py`：

```python
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.content import serialize_version
from app.domain.enums import VersionStatus
from app.domain.review.service import review_version
from app.infrastructure.db.models import ContentOutputVersion
from app.infrastructure.db.session import get_session

router = APIRouter()


class ReviewRequest(BaseModel):
    version: int
    decision: str
    comment: str | None = None
    human_verified: bool = False


@router.post("/output-versions/{version_id}/review")
def post_review(
    version_id: uuid.UUID,
    payload: ReviewRequest,
    session: Session = Depends(get_session),
) -> dict:
    version = review_version(
        session,
        version_id,
        payload.version,
        payload.decision,
        payload.comment,
        payload.human_verified,
    )
    session.commit()
    return serialize_version(version)


@router.get("/reviews")
def get_reviews(session: Session = Depends(get_session)) -> dict:
    versions = session.scalars(
        select(ContentOutputVersion)
        .where(ContentOutputVersion.status == VersionStatus.AWAITING_REVIEW.value)
        .order_by(ContentOutputVersion.created_at)
    ).all()
    return {"items": [serialize_version(v) for v in versions]}
```

`apps/api/app/main.py` 挂载 `reviews.router`（前缀 `/api/v1`）。

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests -v`
Expected: 全部 passed

- [ ] **Step 6: 提交**

```powershell
git add apps/api
git commit -m "feat(api): 审核决策、版本冲突与批准门禁"
```

---

## Task 9: Markdown 导出

**Files:**
- Create: `apps/api/app/infrastructure/exporters/markdown.py`
- Create: `apps/api/app/api/exports.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_exports.py`

**Interfaces:**
- Consumes: `ContentOutputVersion`、`ContentOutputSlot`、`ContentTask`（Task 2）；`Settings.export_dir`（Task 1）。
- Produces: `render_markdown(task: ContentTask, slot: ContentOutputSlot, version: ContentOutputVersion) -> str`；`write_export(export_dir: Path, task_id: uuid.UUID, version: ContentOutputVersion, content: str) -> Path`；路由 `POST /api/v1/output-versions/{version_id}/export`。

导出文件名固定为 `{task_id}-{platform}-v{version}.md`，落在 `export_dir` 下；`write_export` 必须校验最终路径仍在 `export_dir` 内，防止目录穿越。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/test_exports.py`：

```python
from pathlib import Path

import pytest

HEADERS = {"X-Internal-Token": "dev-internal-token"}
PAYLOAD = {
    "topic": "咖啡因如何影响睡眠质量",
    "audience": "熬夜上班族",
    "goal": "education",
    "platforms": ["xiaohongshu"],
    "tone": "专业、实用",
}


@pytest.fixture()
def version(client):
    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k"}
    ).json()["id"]
    return client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    ).json()


def test_export_rejects_unapproved_version(client, version):
    response = client.post(f"/api/v1/output-versions/{version['id']}/export")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VERSION_NOT_APPROVED"


def test_export_writes_utf8_markdown_file(client, version, tmp_path, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path))

    client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "approve"},
    )
    response = client.post(f"/api/v1/output-versions/{version['id']}/export")

    assert response.status_code == 201
    path = Path(response.json()["file_path"])
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "咖啡因" in text
    assert "版本：1" in text
    get_settings.cache_clear()


def test_rendered_markdown_contains_title_body_and_hashtags():
    from app.infrastructure.exporters.markdown import render_markdown

    class _Task:
        topic = "咖啡因如何影响睡眠质量"

    class _Slot:
        platform = "xiaohongshu"

    class _Version:
        version = 3
        payload_json = {
            "title": "标题",
            "body": "正文内容",
            "hashtags": ["睡眠", "咖啡"],
        }

    text = render_markdown(_Task(), _Slot(), _Version())

    assert "# 标题" in text
    assert "正文内容" in text
    assert "#睡眠" in text
    assert "版本：3" in text


def test_write_export_blocks_path_traversal(tmp_path):
    import uuid

    from app.infrastructure.exporters.markdown import write_export

    class _Version:
        id = uuid.uuid4()
        version = 1
        slot_id = uuid.uuid4()

    with pytest.raises(ValueError):
        write_export(tmp_path, "../../evil", _Version(), "x")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_exports.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.infrastructure.exporters.markdown'`

- [ ] **Step 3: 写实现**

`apps/api/app/infrastructure/exporters/markdown.py`：

```python
from pathlib import Path


def render_markdown(task, slot, version) -> str:
    payload = version.payload_json
    hashtags = " ".join(f"#{tag}" for tag in payload.get("hashtags", []))
    lines = [
        f"# {payload.get('title') or payload.get('hook') or task.topic}",
        "",
        f"> 平台：{slot.platform}　版本：{version.version}",
        "",
        payload.get("body") or payload.get("script") or "",
    ]
    if hashtags:
        lines += ["", hashtags]
    return "\n".join(lines) + "\n"


def write_export(export_dir: Path, task_id, version, content: str) -> Path:
    export_dir = Path(export_dir).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{task_id}-v{version.version}.md"
    target = (export_dir / filename).resolve()
    if export_dir not in target.parents:
        raise ValueError("导出路径超出允许目录")
    target.write_text(content, encoding="utf-8")
    return target
```

`apps/api/app/api/exports.py`：

```python
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.domain.enums import VersionStatus
from app.errors import AppError
from app.infrastructure.db.models import (
    ContentOutputSlot,
    ContentOutputVersion,
    ContentTask,
)
from app.infrastructure.db.session import get_session
from app.infrastructure.exporters.markdown import render_markdown, write_export

router = APIRouter()


@router.post("/output-versions/{version_id}/export", status_code=201)
def post_export(
    version_id: uuid.UUID,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    version = session.get(ContentOutputVersion, version_id)
    if version is None:
        raise AppError("VERSION_NOT_FOUND", "内容版本不存在", status_code=404)
    if version.status != VersionStatus.APPROVED.value:
        raise AppError(
            "VERSION_NOT_APPROVED", "只有已批准的版本可以导出", status_code=422
        )
    slot = session.get(ContentOutputSlot, version.slot_id)
    task = session.get(ContentTask, slot.task_id)

    content = render_markdown(task, slot, version)
    path = write_export(settings.export_dir, f"{task.id}-{slot.platform}", version, content)
    return {"file_path": str(path), "version": version.version}
```

`apps/api/app/main.py` 挂载 `exports.router`（前缀 `/api/v1`）。

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests -v`
Expected: 全部 passed

- [ ] **Step 5: 提交**

```powershell
git add apps/api
git commit -m "feat(api): 已批准版本的 Markdown 导出"
```

---

## Task 10: n8n WF-01 编排接线

**Files:**
- Create: `workflows/wf01-content-pipeline.json`
- Create: `workflows/README.md`
- Modify: `infra/docker-compose.yml`
- Modify: `.env.example`
- Create: `apps/api/tests/test_pipeline_contract.py`

**Interfaces:**
- Consumes: Task 6 与 Task 7 的全部 `/internal/v1` 端点。
- Produces: 可导入 n8n 的工作流 JSON；环境变量 `INTERNAL_API_BASE_URL`、`INTERNAL_API_TOKEN`。

WF-01 节点顺序：Webhook（接收 `{task_id, platforms}`）→ 认领运行 → 逐平台循环（start step → generate → complete step）→ finish run。n8n 节点之间只传 ID，不传内容正文。

- [ ] **Step 1: 写失败测试（用 HTTP 调用序列固化编排契约）**

`apps/api/tests/test_pipeline_contract.py`：

```python
HEADERS = {"X-Internal-Token": "dev-internal-token"}
PAYLOAD = {
    "topic": "咖啡因如何影响睡眠质量",
    "audience": "熬夜上班族",
    "goal": "education",
    "platforms": ["xiaohongshu"],
    "tone": "专业、实用",
}


def test_full_pipeline_sequence_reaches_awaiting_review(client):
    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k"}
    ).json()["id"]

    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs",
        json={"n8n_execution_id": "exec-42"},
        headers=HEADERS,
    ).json()["id"]

    step = client.post(
        f"/internal/v1/runs/{run_id}/steps/generate_xiaohongshu/start",
        headers=HEADERS,
    ).json()
    client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    )
    client.post(
        f"/internal/v1/runs/{run_id}/steps/generate_xiaohongshu/complete",
        json={"attempt": step["attempt"]},
        headers=HEADERS,
    )
    client.post(
        f"/internal/v1/runs/{run_id}/finish",
        json={"status": "succeeded"},
        headers=HEADERS,
    )

    detail = client.get(f"/api/v1/tasks/{task_id}").json()

    assert detail["status"] == "awaiting_review"
    assert detail["steps"][0]["status"] == "succeeded"
    assert len(detail["output_slots"]) == 1


def test_duplicate_complete_callback_is_idempotent(client):
    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k2"}
    ).json()["id"]
    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS
    ).json()["id"]
    step = client.post(
        f"/internal/v1/runs/{run_id}/steps/generate_xiaohongshu/start", headers=HEADERS
    ).json()

    first = client.post(
        f"/internal/v1/runs/{run_id}/steps/generate_xiaohongshu/complete",
        json={"attempt": step["attempt"]},
        headers=HEADERS,
    )
    second = client.post(
        f"/internal/v1/runs/{run_id}/steps/generate_xiaohongshu/complete",
        json={"attempt": step["attempt"]},
        headers=HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "succeeded"


def test_current_step_reflects_latest_started_step(client):
    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k3"}
    ).json()["id"]
    run_id = client.post(
        f"/internal/v1/tasks/{task_id}/runs", json={}, headers=HEADERS
    ).json()["id"]
    client.post(
        f"/internal/v1/runs/{run_id}/steps/generate_xiaohongshu/start", headers=HEADERS
    )

    assert (
        client.get(f"/api/v1/tasks/{task_id}").json()["current_step"]
        == "generate_xiaohongshu"
    )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_pipeline_contract.py -v`
Expected: 前两个用例通过（Task 6/7 已覆盖该契约），`test_current_step_reflects_latest_started_step` FAIL，断言 `None == "generate_xiaohongshu"`

- [ ] **Step 3: 让 API 在步骤开始时更新 `current_step`**

在 `apps/api/app/domain/runs/service.py` 顶部 import 增加 `ContentTask`，并在 `start_step` 的 `session.flush()` 之后、`return step` 之前追加：

```python
    run = session.get(WorkflowRun, run_id)
    task = session.get(ContentTask, run.task_id)
    task.current_step = step_key
    session.flush()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests -v`
Expected: 全部 passed

- [ ] **Step 5: 把 n8n 加进 Compose**

`infra/docker-compose.yml` 追加：

```yaml
  api:
    build: ../apps/api
    environment:
      DATABASE_URL: postgresql+psycopg://app:app@db:5432/ai_content_ops
      INTERNAL_API_TOKEN: ${INTERNAL_API_TOKEN}
      EXPORT_DIR: /data/exports
    volumes:
      - ../data:/data
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      db:
        condition: service_healthy

  n8n:
    image: n8nio/n8n
    environment:
      N8N_SECURE_COOKIE: "false"
      INTERNAL_API_BASE_URL: ${INTERNAL_API_BASE_URL}
      INTERNAL_API_TOKEN: ${INTERNAL_API_TOKEN}
    ports:
      - "127.0.0.1:5678:5678"
    volumes:
      - n8ndata:/home/node/.n8n
```

`volumes` 段追加 `n8ndata:`。`.env.example` 里 `INTERNAL_API_BASE_URL` 给出两套取值并注释说明：Compose 内为 `http://api:8000`，宿主机跑 FastAPI 时为 `http://host.docker.internal:8000`。

- [ ] **Step 6: 在 n8n 里搭 WF-01 并导出**

打开 `http://127.0.0.1:5678`，按下面顺序连接节点，全部 HTTP Request 节点都加 Header `X-Internal-Token: {{$env.INTERNAL_API_TOKEN}}`，超时设为 30 秒：

1. Webhook（POST `/wf01`）：接收 `{ "task_id": "...", "platforms": ["xiaohongshu"] }`
2. HTTP Request：`POST {{$env.INTERNAL_API_BASE_URL}}/internal/v1/tasks/{{$json.task_id}}/runs`
3. Split In Batches：遍历 `platforms`
4. HTTP Request：`POST .../internal/v1/runs/{{run_id}}/steps/generate_{{platform}}/start`
5. HTTP Request：`POST .../internal/v1/tasks/{{task_id}}/generate/{{platform}}`
6. HTTP Request：`POST .../internal/v1/runs/{{run_id}}/steps/generate_{{platform}}/complete`，body 带上第 4 步返回的 `attempt`
7. HTTP Request：`POST .../internal/v1/runs/{{run_id}}/finish`，body `{"status":"succeeded"}`

Error Trigger 分支调用 `.../steps/{{step_key}}/fail` 并把 run 置为 `failed`。

导出为 `workflows/wf01-content-pipeline.json` 并提交（不要导出 credentials）。`workflows/README.md` 写清导入步骤与所需环境变量。

- [ ] **Step 7: 手工验证一次**

```powershell
docker compose -f infra/docker-compose.yml up -d
curl.exe -X POST http://127.0.0.1:5678/webhook/wf01 -H "Content-Type: application/json" -d "{\"task_id\":\"<粘贴任务ID>\",\"platforms\":[\"xiaohongshu\"]}"
curl.exe http://127.0.0.1:8000/api/v1/tasks/<粘贴任务ID>
```

Expected: 任务状态变为 `awaiting_review`，`steps` 里有一条 `succeeded`

- [ ] **Step 8: 提交**

```powershell
git add workflows infra .env.example apps/api
git commit -m "feat(orchestration): WF-01 主流程接线与编排契约测试"
```

---

## Task 11: Next.js 控制台

**Files:**
- Create: `apps/web/package.json`（由 `create-next-app` 生成）
- Create: `apps/web/lib/api.ts`
- Create: `apps/web/app/tasks/new/page.tsx`
- Create: `apps/web/app/tasks/page.tsx`
- Create: `apps/web/app/tasks/[taskId]/page.tsx`
- Create: `apps/web/components/TaskDetail.tsx`
- Create: `apps/web/components/ContentPanel.tsx`
- Create: `apps/web/.env.local.example`

**Interfaces:**
- Consumes: `/api/v1/tasks`、`/api/v1/tasks/{id}`、`/api/v1/output-slots/{id}`、`/api/v1/output-versions/{id}/review`、`/api/v1/output-versions/{id}/export`（Task 5 / 7 / 8 / 9）。
- Produces: 页面 `/tasks/new`、`/tasks`、`/tasks/{taskId}`；`lib/api.ts` 导出 `createTask`、`listTasks`、`getTask`、`getSlot`、`reviewVersion`、`exportVersion`；轮询 hook 行为见下。

轮询规则：只在任务状态属于 `queued / running / partially_ready` 时轮询，间隔 3 秒；`document.visibilityState !== "visible"` 时暂停；连续两次请求失败后间隔翻倍，上限 30 秒；任务进入终态立即停止。

- [ ] **Step 1: 初始化前端**

```powershell
cd apps
npx create-next-app@latest web --typescript --tailwind --app --eslint --no-src-dir --import-alias "@/*"
cd web
npm install @tanstack/react-query
```

`apps/web/.env.local.example`：

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

- [ ] **Step 2: 写 API 客户端**

`apps/web/lib/api.ts`：

```ts
const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type TaskSummary = {
  id: string;
  topic: string;
  platforms: string[];
  status: string;
  current_step: string | null;
  created_at: string;
  updated_at: string;
};

export type OutputVersion = {
  id: string;
  slot_id: string;
  version: number;
  status: string;
  has_blocking_issues: boolean;
  title_snapshot: string | null;
  payload: Record<string, unknown>;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message ?? `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

export function createTask(payload: Record<string, unknown>, idempotencyKey: string) {
  return request<TaskSummary>("/tasks", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(payload),
  });
}

export function listTasks() {
  return request<{ items: TaskSummary[] }>("/tasks");
}

export function getTask(taskId: string) {
  return request<TaskSummary & {
    steps: { step_key: string; attempt: number; status: string; error_message: string | null }[];
    output_slots: { id: string; platform: string; current_version_id: string | null }[];
  }>(`/tasks/${taskId}`);
}

export function getSlot(slotId: string) {
  return request<{ id: string; platform: string; current_version_id: string | null; versions: OutputVersion[] }>(
    `/output-slots/${slotId}`,
  );
}

export function reviewVersion(versionId: string, version: number, decision: string, comment?: string) {
  return request<OutputVersion>(`/output-versions/${versionId}/review`, {
    method: "POST",
    body: JSON.stringify({ version, decision, comment }),
  });
}

export function exportVersion(versionId: string) {
  return request<{ file_path: string }>(`/output-versions/${versionId}/export`, {
    method: "POST",
  });
}
```

- [ ] **Step 3: 写新建任务页**

`apps/web/app/tasks/new/page.tsx` 关键点：组件挂载时用 `useState(() => crypto.randomUUID())` 生成一次 `Idempotency-Key` 并在整个表单生命周期内复用，提交成功后才重置；提交按钮在请求期间禁用；成功后 `router.push(/tasks/${id})`。

```tsx
"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createTask } from "@/lib/api";

export default function NewTaskPage() {
  const router = useRouter();
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    topic: "",
    audience: "",
    goal: "education",
    tone: "专业、实用",
    platforms: ["xiaohongshu"],
  });

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const task = await createTask(form, idempotencyKey);
      setIdempotencyKey(crypto.randomUUID());
      router.push(`/tasks/${task.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-2xl space-y-4 p-8">
      <h1 className="text-xl font-semibold">新建内容任务</h1>
      <input
        className="w-full rounded border p-2"
        placeholder="主题（5-300 字）"
        value={form.topic}
        onChange={(e) => setForm({ ...form, topic: e.target.value })}
      />
      <input
        className="w-full rounded border p-2"
        placeholder="目标受众"
        value={form.audience}
        onChange={(e) => setForm({ ...form, audience: e.target.value })}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
      >
        创建并开始生成
      </button>
    </form>
  );
}
```

- [ ] **Step 4: 写任务详情与轮询**

`apps/web/components/TaskDetail.tsx`：

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";

import { getTask } from "@/lib/api";

const ACTIVE = new Set(["queued", "running", "partially_ready"]);

export function TaskDetail({ taskId }: { taskId: string }) {
  const { data, error } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => getTask(taskId),
    refetchInterval: (query) => {
      if (document.visibilityState !== "visible") return false;
      const status = query.state.data?.status;
      if (!status || !ACTIVE.has(status)) return false;
      return Math.min(3000 * 2 ** query.state.fetchFailureCount, 30000);
    },
  });

  if (error) return <p className="text-red-600">{(error as Error).message}</p>;
  if (!data) return <p>加载中…</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{data.topic}</h1>
      <p className="text-sm text-gray-600">
        状态：{data.status}　当前步骤：{data.current_step ?? "—"}
      </p>
      <ol className="space-y-1 text-sm">
        {data.steps.map((step) => (
          <li key={`${step.step_key}-${step.attempt}`}>
            {step.step_key}（第 {step.attempt} 次）：{step.status}
            {step.error_message ? `　${step.error_message}` : ""}
          </li>
        ))}
      </ol>
    </div>
  );
}
```

`ContentPanel.tsx` 负责读取 slot、展示当前版本的 `title` 与 `body`、提供「批准」与「导出 Markdown」两个按钮，批准时把 `version.version` 一并提交以触发服务端的版本冲突校验；导出成功后显示返回的文件路径。

- [ ] **Step 5: 手工验证**

```powershell
cd apps\web
npm run dev
```

打开 `http://127.0.0.1:3000/tasks/new`，创建任务，触发 WF-01，确认详情页 3 秒刷新一次、切到别的标签页后停止请求（浏览器开发者工具 Network 面板确认）、批准后能导出并看到文件路径。

- [ ] **Step 6: 提交**

```powershell
git add apps/web
git commit -m "feat(web): 任务创建、详情轮询、内容查看与批准导出"
```

---

## Task 12: 端到端冒烟与冷启动验收

**Files:**
- Create: `apps/web/e2e/smoke.spec.ts`
- Create: `apps/web/playwright.config.ts`
- Create: `README.md`
- Create: `AGENTS.md`
- Modify: `infra/docker-compose.yml`

**Interfaces:**
- Consumes: Task 1–11 的全部产出。
- Produces: 一条覆盖「创建 → 生成 → 批准 → 导出」的 Playwright 用例；可从空仓库冷启动的 README。

- [ ] **Step 1: 写失败的 E2E 用例**

```powershell
cd apps\web
npm install --save-dev @playwright/test
npx playwright install chromium
```

`apps/web/e2e/smoke.spec.ts`：

```ts
import { expect, test } from "@playwright/test";

test("从创建任务到导出 Markdown 的完整闭环", async ({ page, request }) => {
  await page.goto("/tasks/new");
  await page.getByPlaceholder("主题（5-300 字）").fill("咖啡因如何影响睡眠质量");
  await page.getByPlaceholder("目标受众").fill("熬夜上班族");
  await page.getByRole("button", { name: "创建并开始生成" }).click();

  await expect(page).toHaveURL(/\/tasks\/[0-9a-f-]{36}/);
  const taskId = page.url().split("/").pop()!;

  await request.post("http://127.0.0.1:5678/webhook/wf01", {
    data: { task_id: taskId, platforms: ["xiaohongshu"] },
  });

  await expect(page.getByText("状态：awaiting_review")).toBeVisible({ timeout: 30000 });
  await page.getByRole("button", { name: "批准当前版本" }).click();
  await page.getByRole("button", { name: "导出 Markdown" }).click();
  await expect(page.getByText(/\.md$/)).toBeVisible();
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npx playwright test`
Expected: FAIL（按钮文案或流程尚未对齐）

- [ ] **Step 3: 对齐前端文案让用例通过**

把 `ContentPanel.tsx` 的两个按钮文案固定为「批准当前版本」和「导出 Markdown」，导出结果用 `<p>{filePath}</p>` 渲染。

- [ ] **Step 4: 运行确认通过**

Run: `npx playwright test`
Expected: 1 passed

- [ ] **Step 5: 冷启动演练**

```powershell
docker compose -f infra/docker-compose.yml down -v
copy .env.example .env
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml exec api alembic upgrade head
curl.exe http://127.0.0.1:8000/api/v1/health
```

Expected: 返回 `{"status":"ok","app_version":"0.1.0","database":"ok"}`

README 里把上面这组命令写成「五分钟启动」章节，并说明需要先在 n8n 里导入 `workflows/wf01-content-pipeline.json`。

- [ ] **Step 6: 写 AGENTS.md**

```text
1. 本项目是个人 Windows 本地应用，不引入多租户、Kubernetes 或微服务。
2. FastAPI 是业务状态和状态迁移唯一入口；n8n 不直接修改核心业务表。
3. 所有外部 Provider 必须经过 Adapter，设置超时、有限重试并记录调用。
4. 内容产物采用不可变版本；只有明确批准的版本可导出或发布。approved 一旦写入不再变更。
5. 发布动作必须幂等；结果 unknown 时禁止自动重试。
6. 实现任何功能前先写失败测试，并确认它以预期原因失败；先写实现的代码删除重来。
7. 每个任务完成后过一轮独立代码评审，再进入下一个任务。
8. 声称完成前必须实际运行测试命令并贴出输出，不凭印象判断通过。
9. 新功能必须包含测试、错误态、空状态和文档更新。
10. 不提交 API Key、Cookie、真实用户数据或生成资产。
11. 先实现当前里程碑的验收标准，不提前建设后续里程碑的模块。
```

- [ ] **Step 7: 全量回归并提交**

```powershell
cd apps\api
uv run pytest tests -v
cd ..\web
npm run build
npx playwright test
```

Expected: 后端全绿、前端 build 成功、E2E 1 passed

```powershell
git add .
git commit -m "test: M1 端到端冒烟与冷启动文档"
```

---

## M1 验收标准

全部满足才算 M1 完成：

- 新电脑按 README 执行 Compose 命令即可启动，健康检查四项（api / database / n8n / web）通过。
- 浏览器创建任务后，详情页能看到步骤推进，不需要打开 n8n 界面。
- 生成的内容版本不可原地修改，人工编辑产生新版本且旧版本仍可查看。
- 用过期版本号批准会被拒绝并提示刷新。
- 未批准的版本无法导出；已批准版本导出的 Markdown 用记事本打开中文不乱码。
- 任一步骤失败时，详情页显示失败步骤、错误码与错误信息，不出现无解释的卡住状态。
- `uv run pytest` 与 `npx playwright test` 全绿，输出无 warning。
- 数据库从空库执行 `alembic upgrade head` 可完整建表。

## 里程碑交接

M1 完成后再写 M2 的实施计划。M2 开始前需要先确定的事项：选定具体搜索 API 供应商并确认其返回正文的字段结构与配额、确定 LLM Provider 与模型、给出模型定价表用于成本估算。这些属于外部依赖决策，不适合在 M1 里预先假设。
