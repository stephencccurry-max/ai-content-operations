# AI Content Operations

个人 Windows 本地 AI 内容运营控制台：FastAPI 管状态，n8n 编排生成，Next.js 控制台审阅与导出。

## 项目结构

| 路径 | 说明 |
|------|------|
| `apps/api` | FastAPI 业务 API 与内部编排回调 |
| `apps/web` | Next.js 控制台（任务列表、创建、审阅、导出） |
| `infra/docker-compose.yml` | PostgreSQL、API、n8n 本地栈 |
| `workflows/` | n8n WF-01 工作流导出与说明 |
| `data/exports` | Markdown 导出目录（运行时生成） |

## 五分钟启动（冷启动）

前置：**Docker Desktop** 已安装并运行；本机已安装 [Node.js 20+](https://nodejs.org/) 与 [uv](https://docs.astral.sh/uv/)（仅本地开发 API 时需要）。

### 1. 配置环境

```powershell
copy .env.example .env
```

编辑 `.env`，至少设置 `POSTGRES_PASSWORD` 与 `INTERNAL_API_TOKEN`（两处 token 需一致）。

**默认 Mock（与 pytest 一致）：** 仓库内 `.env.example` 使用 `LLM_PROVIDER=mock`、`SEARCH_PROVIDER=mock`，不调用外网；`cd apps\api` 下 pytest 的 `conftest.py` 也会强制 mock，与本机 `.env` 里的 live 配置无关。

**可选 — M2 真实出稿（Tavily + 智谱）：** 在本机 `.env`（及 Compose 用的 `infra/.env` 副本）中设置：

```env
LLM_PROVIDER=zhipu
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=<your-tavily-key>
ZHIPU_API_KEY=<your-zhipu-key>
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4
ZHIPU_MODEL=glm-5.3
```

- 调研走 Tavily（每任务只 search 一次，结果缓存在 `research_sources`）。
- LLM 走智谱 OpenAI 兼容 `chat/completions`；`estimated_cost` 恒为 0，有 usage 则记 token。
- **Coding Plan 端点**（`/api/coding/paas/v4`）按用户要求接入；官方条款限制其供白名单编程工具使用。若标准 API 有余额，可改 `ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4`。
- **无预算熔断**（M2 不做日限额/人民币计价）；额度用尽时由供应商报错（如智谱 1113），步骤记 `failed`。
- 本机 PostgreSQL 已占 **5432** 时，使用 gitignore 的 `infra/docker-compose.override.yml` 把宿主机端口改为 **5433**，启动时加 `-f infra/docker-compose.override.yml`。

### 2. 启动基础设施与 API

```powershell
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml exec api alembic upgrade head
curl.exe http://127.0.0.1:8000/api/v1/health
```

若使用端口 override（见上文）：

```powershell
docker compose -f infra/docker-compose.yml -f infra/docker-compose.override.yml up -d --build
```

预期 health 响应：

```json
{"status":"ok","app_version":"0.1.0","database":"ok"}
```

> API 容器启动时会自动执行 `alembic upgrade head`；若数据库为空，上述 `exec` 可再跑一遍以确保迁移到位。

### 3. 导入 n8n 工作流 WF-01

1. 打开 `http://127.0.0.1:5678`
2. **Workflows → Import from File** → 选择 `workflows/wf01-content-pipeline.json`
3. 打开工作流并 **Activate**，记下 Webhook 路径 `/webhook/wf01`

M2 已将 **Generate Content** 节点超时改为 **120s**（真实 LLM 较慢）。若你曾导入旧版 WF-01，需**重新导入并激活**后再测 webhook。

详见 [`workflows/README.md`](workflows/README.md)。

### 4. 启动 Web 控制台

```powershell
cd apps\web
copy .env.local.example .env.local
npm install
npm run dev
```

浏览器访问 `http://127.0.0.1:3000/tasks/new` 创建任务；创建后可通过 n8n Webhook 触发生成：

```powershell
curl.exe -X POST http://127.0.0.1:5678/webhook/wf01 `
  -H "Content-Type: application/json" `
  -d "{\"task_id\":\"<task_id>\",\"platforms\":[\"xiaohongshu\"]}"
```

## 测试

### API 单元 / 集成测试

测试**不访问外网**：`conftest.py` 强制 `LLM_PROVIDER=mock`、`SEARCH_PROVIDER=mock`，即使用户本机 `.env` 已配 Tavily/智谱 live 值。

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
uv run pytest tests -v
```

### 前端构建

```powershell
cd apps\web
npm run build
```

### E2E 冒烟（Playwright）

需 API（`:8000`）与 Web（`:3000`）已运行；n8n 可选（未运行时测试会回退到内部 HTTP 编排序列）。E2E 通过 `X-Internal-Token` 调用内部 API：未设置 `INTERNAL_API_TOKEN` 时默认使用 `change-me-in-local-env`（与 `.env.example` 一致），API 侧须使用相同 token。

```powershell
cd apps\web
npm install
npx playwright install chromium
$env:INTERNAL_API_TOKEN='change-me-in-local-env'  # 可选；省略则 E2E 使用同默认值
npx playwright test
```

## 无 Docker 时的本地开发

若暂不可用 Docker，可本机 PostgreSQL + 宿主机跑 API：

```powershell
# 根目录 .env 中 DATABASE_URL 指向 localhost，例如：
# DATABASE_URL=postgresql+psycopg://app:<password>@127.0.0.1:5432/ai_content_ops

cd apps\api
uv sync
uv run alembic upgrade head
$env:INTERNAL_API_TOKEN='change-me-in-local-env'
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

另开终端启动 Web（见上文第 4 步）。

## 代理开发约定

见 [`AGENTS.md`](AGENTS.md)。
