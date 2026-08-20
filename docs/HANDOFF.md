# 交接文档：AI 内容运营控制台

> 最后更新：2026-08-21（收工交接）  
> 面向对象：接手本项目的新 agent 会话  
> 当前阶段：**M1 live 已通过**；**M2 代码已合入 `main`**；下一步只做 **M2 本机 live 验收**，不要重做 M2 实现，不要开工 M3

## 0. 今日工作总结（2026-08-21，给明天新 agent）

**一句话：** M1 冷启动验收昨天已过；今天把 M2（Tavily + 智谱 GLM-5.3）按计划 Task 1–6 做完、评审修复、fast-forward 合入本地 `main`，pytest **88 passed**。完整 V1 仍差 M3/M4；M2 **还没**在本机用真实 Key 跑通 webhook。

**仓库（合入后）：**

- 分支：`main`（M2 已不再需要检出 `feat/m2-real-providers`）
- 合入方式：本地 `git checkout main` 后 fast-forward，`465c383` → `98bb746`（再加本 HANDOFF 提交）
- 远程：`https://github.com/stephencccurry-max/ai-content-operations.git`
- 本会话会 `git push origin main`。接手后先 `git pull` / `git status`，确认与 `origin/main` 一致再干活
- **不要提交：** `.env`、`infra/.env`、`infra/docker-compose.override.yml`、`.superpowers/`

**M2 合入的关键提交（从旧到新）：**

| SHA | 内容 |
|---|---|
| `27d6a64` | Settings + `request_json` + conftest 强制 mock |
| `06d1709` | Tavily adapter |
| `56d4478` | Zhipu GLM-5.3 JSON adapter |
| `c989d58` + `eda5de7` | 调研缓存、失败记 `provider_calls`、避免空 slot |
| `28d3e5a` + `16db7af` | 双平台契约、n8n Generate **120s**、Compose 透传 env、`PROVIDER_TIMEOUT_SECONDS:-45` |
| `8c15450` | README / `.env.example` / 计划入仓 |
| `98bb746` | 非法 JSON 包成 `PROVIDER_INVALID_RESPONSE` |

**用户已拍板（不要重开讨论）：**

1. 搜索：**Tavily**
2. LLM：智谱 **`glm-5.3`**，Base URL 用 **`https://open.bigmodel.cn/api/coding/paas/v4`**（Coding Plan）。标准 `paas/v4` 对该账号会 **1113 余额不足**。官方条款限制给白名单编程工具；用户知情后仍要求用。
3. **不做预算熔断、不算人民币**；`provider_calls.estimated_cost` 恒 **0**；额度不够由供应商报错。

**本机环境（冷启动踩过的坑，继续沿用）：**

- Docker Desktop：`D:\Install\DockerDesktop\Application`；CLI 在 `...\resources\bin\docker.exe`，**默认不在 PATH**
- 本机 PostgreSQL 占 **5432** 且无管理员权限停不掉 → 本地 `infra/docker-compose.override.yml`（**gitignore**）把宿主机端口改成 **5433**
- Compose 插值默认看 `infra/`：根目录 `.env` 需复制为 **`infra/.env`**
- n8n **2.35.5**：compose 已设 `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`；CLI 导入需工作流 JSON **顶层 `id`**；`publish:workflow` 后要重启 n8n
- `ghcr.io/astral-sh/uv` 不可达 → Dockerfile 用 `pip install uv`
- 测试库与宿主机 API 抢同一 Postgres 会死锁：Compose DB 用 `:5433`，或停掉占用 8000 的 uvicorn
- PowerShell **不能用 `&&`**，用 `;`

**智谱 Key（不要把 Key 写进 Git/HANDOFF 正文）：** 已写入本机 `.env` 和 `infra/.env`（`ZHIPU_API_KEY`、`ZHIPU_BASE_URL`、`ZHIPU_MODEL=glm-5.3`）。Adapter 必须发 **`thinking: {type: disabled}`**，并给够 `max_tokens`。错误映射：`1113` → `PROVIDER_QUOTA_EXCEEDED`；`1004`/401 → `PROVIDER_AUTH_FAILED`。

**Tavily Key：用户还没给。** live 需要同时有 `LLM_PROVIDER=zhipu`、`SEARCH_PROVIDER=tavily`、`TAVILY_API_KEY`。

**已知残留（不挡合并，live 时注意）：** `uv.lock` 曾手工改 httpx 为主依赖；HTTP 429 可能在映射 1113 前重试一次；n8n 120s 盖不住 search+LLM 各超时+重试的最坏路径。

**明天优先做：**

1. `git pull` 确认 `main` 最新；读本文件 + `README.md` + `docs/superpowers/plans/2026-08-20-m2-real-providers.md`
2. 向用户要 Tavily Key（若仍没有），写入根目录 `.env` **和** `infra/.env`
3. Compose `up -d --build`（5432 冲突继续用 override **5433**）→ **重新导入/激活 WF-01**
4. 双平台 webhook live：两份稿 + `claim_source_map`；额度/错 Key 应看到 `PROVIDER_*` 失败记录
5. **不要开工 M3**，除非用户要求先写 `docs/superpowers/plans/` 里的 M3 计划
6. 继续 SDD：主 agent 不亲自写实现（除非用户改口）；用简体中文

## 1. 三十秒了解现状

个人本地运行的 AI 内容运营控制台。设计文档已定稿；M1 的 12 个任务已实现并 live 验收；M2 代码已合入 `main`。

**已有能力（M1）：** 浏览器创建任务 →（n8n WF-01 或内部 HTTP）→ Mock 出稿 → 人工批准 → 导出 Markdown。

**已有能力（M2，代码层）：** Settings 切换 mock/live；Tavily 调研（每 task 缓存到 `content_tasks.research_sources`）；智谱 GLM-5.3 JSON 出稿；双平台契约；`provider_calls` 记成功/失败（`estimated_cost=0`）。合入后 API 测试 **88 passed**。

**还不是完整 V1：** M3（规则+模型 QC）、M4（稳定性与试运行）未开始；M2 **live 验收尚未跑通**。

你接手后优先做：

1. ~~本机 Docker 冷启动 + live n8n webhook 验收（M1 Mock）~~ **已通过（2026-08-20）**。
2. ~~按计划实现 M2~~ **代码已合入 `main`（2026-08-21）**。
3. **M2 live 验收**（人工，见上文 §0 与 `README.md`）。

## 2. 项目是什么

一套跑在个人 Windows 电脑上的本地 Web 控制台，帮一个人完成自媒体内容运营：输入主题 → 自动调研 → 生成小红书图文与抖音脚本 → 自动质检 → 人工审核批准 → 导出或受控发布。

它不是聊天工具，核心价值在于**可追踪、可审核、可重试**：每条内容都能回溯到来源、版本、质检结果和人工批准记录。

- 用户：一个人，同时是选题人、编辑、审核人。不做多用户、不做权限。
- 技术栈：Next.js + FastAPI + PostgreSQL + n8n + Docker Compose（Docker Desktop + WSL2）。
- 运行环境：个人 Windows 电脑，**shell 是 PowerShell**（注意：不支持 `&&` 连接命令，用 `;`）。

## 3. 权威文档与各自的职责

| 文件 | 职责 | 冲突时以谁为准 |
|---|---|---|
| `AI内容运营控制台—项目总体方案.md`（V1.1） | 立项背景、范围边界、架构决策、路线图、风险 | 范围与架构决策以它为准 |
| `AI内容运营控制台—V1产品与实施设计.md`（V1.1） | 页面、状态机、数据模型、API、Schema、测试、验收 | **所有量化指标和技术细节以它为准** |
| `docs/superpowers/plans/2026-08-19-m1-walking-skeleton.md` | M1 任务级实施计划 | M1 历史执行细节以它为准；与设计冲突时先问人 |
| `docs/superpowers/plans/2026-08-20-m2-real-providers.md` | M2 任务级实施计划 | M2 执行以它为准；预算熔断不在本里程碑 |
| `README.md` / `AGENTS.md` | 冷启动与代理约定 | 日常启动与协作以它们为准 |
| `.superpowers/sdd/progress.md` | M1 任务完成台账（本地，通常不提交） | 恢复进度时优先于记忆 |
| `.superpowers/sdd-workspace/task-*-report.md` | 各任务实现/评审报告（本地） | 追溯某任务决策时查阅 |

两份设计文档已互相对齐：总体方案不复述量化数字，统一引用 V1 设计文档 §18；里程碑编号用 M1–M4。

设计评审记录（canvas，不在仓库）：  
`C:\Users\86138\.cursor\projects\c-Users-86138-cursor-projects-ai-content-operations\canvases\v1-design-review.canvas.tsx`

## 4. 已经拍板、不要推翻的决策

这四条是用户明确确认过的，带理由。除非用户主动改口，**不要在执行中重新讨论**。

**保留 n8n 做编排。** 单看本项目的编排复杂度，用 FastAPI 内的任务队列更简单，能省掉一个容器、一套内部 API 鉴权和双状态源的对账开销。用户仍然选择保留，理由是把本项目当作 n8n 能力的试验场。代价（双状态源、WF-04 对账、内部密钥）已被明确接受。

**调研只用自带正文的搜索 API，不自建网页抓取。** 候选是 Tavily / Exa / Bocha 一类。

**人工编辑产生的新版本，保存时同步跑确定性规则 QC，模型 QC 手动触发。** 审核门禁是「无规则级阻断，且（无模型级阻断 或 审核人勾选了我已人工核对）」。M1 尚未实现完整 QC（属 M3）；M1 只实现了批准门禁中与 Mock 相关的部分。

**小红书与抖音的真实发布 Adapter 整体推到 V1.1。** V1 发布能力只有 `manual_export` 导出；Fake Publisher 契约在 M4。

总原则：**快速出一个能跑起来的 demo，不追求完美。** 先跑通再优化。

## 5. 全局约束（每个子代理都要带上）

- 个人 Windows 本地应用，不引入多租户、Kubernetes 或微服务。
- FastAPI 是业务状态和状态迁移的唯一入口；n8n 不直接读写核心业务表。
- 所有外部 Provider 必须经过 Adapter；**M1 Mock 已实现**；**M2 已接 Tavily + 智谱 Zhipu Adapter**（Settings 切换 mock/live）。
- 内容产物采用不可变版本；只有明确批准的版本可导出。`approved` 一旦写入不再变更。
- 公开 API 前缀 `/api/v1`，编排接口前缀 `/internal/v1`，JSON 字段一律 `snake_case`。
- 时间列用 `TIMESTAMPTZ`，主键用 UUID，API 时间用 UTC ISO 8601。
- 容器内监听 `0.0.0.0`，访问限制靠 Compose 端口映射写成 `127.0.0.1:<port>:<port>`。
- 密钥只走 `.env`，不提交 Git；日志不输出完整密钥、Cookie、Authorization 头。
- **`Settings.internal_api_token` 无硬编码默认值**，必须从环境读取；测试用 `INTERNAL_API_TOKEN=test-internal-token`（与 conftest / 多数测试 HEADERS 一致）。
- M1 不调用任何外部 API；测试不依赖网络。
- TDD 强制：先写失败测试再写最小实现。
- 依赖版本由包管理器锁定；锁文件必须提交。

## 6. 里程碑划分

| 里程碑 | 交付物 | 状态 |
|---|---|---|
| **M1 走通闭环（全 Mock）** | 建任务 → n8n/内部编排 → Mock 出稿 → 批准 → 导出 Markdown | **开发完成且本机 live 验收通过** |
| **M2 真实内容生产** | Tavily 调研 + 智谱 GLM-5.3 出稿、双平台、token 记录；**预算熔断/人民币计价明确不做** | **代码已合入 `main`，待本机 live 验收** |
| **M3 质检与人工审核** | 规则 QC + 模型 QC + 一次修订 + 审核门禁与队列 | 未开始 |
| **M4 稳定性与试运行** | 错误分类、对账、备份、E2E、Prompt 回归、Fake Publisher、20 选题试运行 | 未开始 |
| **V1.1** | 图片能力、真实发布 Adapter、发布后数据反馈 | 未开始 |

每个里程碑开工前，先在 `docs/superpowers/plans/` 产出该里程碑的实施计划，再动代码。

## 7. 当前仓库状态（2026-08-21）

```text
ai-content-operations/
├─ AI内容运营控制台—项目总体方案.md
├─ AI内容运营控制台—V1产品与实施设计.md
├─ README.md / AGENTS.md / .env.example / .gitignore
├─ apps/
│  ├─ api/          # FastAPI、Alembic、pytest、Dockerfile
│  └─ web/          # Next.js App Router、TanStack Query、Playwright e2e
├─ infra/docker-compose.yml   # db + api + n8n
├─ workflows/                 # wf01-content-pipeline.json + README
└─ docs/
   ├─ HANDOFF.md              # 本文件
   └─ superpowers/plans/
      ├─ 2026-08-19-m1-walking-skeleton.md
      └─ 2026-08-20-m2-real-providers.md
```

- **远程：** `https://github.com/stephencccurry-max/ai-content-operations.git`
- **分支：** 工作在 **`main`**。M2 已从 `feat/m2-real-providers` fast-forward 合入（代码 HEAD 基线 `98bb746`）。本地 feature 分支可删，不要再基于它开发。
- **本机 git 身份（仅仓库级）：** `stephencccurry-max` / `stephencccurry-max@users.noreply.github.com`（全局曾缺失 `user.name`/`user.email`，导致提交失败；已用本地 config 解决）
- **未纳入 Git 的本地内容：** `.superpowers/`（SDD briefs/reports/progress，通常不提交）、`.env` / `infra/.env`、`infra/docker-compose.override.yml`。接手后可继续用本地台账，**禁止提交密钥**

### 关键路径速查

| 能力 | 位置 |
|---|---|
| 应用工厂 / CORS | `apps/api/app/main.py`（允许 `localhost:3000` / `127.0.0.1:3000`） |
| 配置 | `apps/api/app/config.py`（`internal_api_token` 必填） |
| 模型与迁移 | `apps/api/app/infrastructure/db/`、`apps/api/alembic/versions/0001_baseline.py` |
| 幂等 | `apps/api/app/application/idempotency.py` |
| 任务状态派生 | `apps/api/app/domain/tasks/status.py`（**批准前必须 settled 平台数 ≥ expected**） |
| 任务 / 编排 / 内容 / 审核 / 导出 API | `apps/api/app/api/*.py` + `domain/*` |
| Mock / Tavily / Zhipu LLM | `apps/api/app/infrastructure/providers/search.py`、`zhipu.py`、`llm.py` |
| Provider HTTP + 调用记录 | `apps/api/app/infrastructure/providers/http.py`；`provider_calls`；`estimated_cost=0` |
| 调研缓存 | `content_tasks.research_sources`（`0002_research_sources` 迁移） |
| WF-01 | `workflows/wf01-content-pipeline.json`（主路径 continueOnFail 失败收敛；不用跨执行 Error Trigger） |
| Web | `apps/web/` → `/tasks`、`/tasks/new`、`/tasks/[taskId]` |
| E2E | `apps/web/e2e/smoke.spec.ts`（无 n8n 时可回退 `/internal/v1`） |

## 8. 本会话已完成工作摘要（2026-08-19 → 2026-08-20）

### 流程

1. 同步设计文档与 HANDOFF/计划到 GitHub（中途补仓库级 git 身份）。
2. 按 `subagent-driven-development` 执行 M1：每任务「实现子代理 → 评审 → 修复 → 复评 → 台账」。
3. 全程在 **`main`** 上提交（未开 feature branch；用户事后选择直接 push）。
4. 环境注意：PowerShell；无系统 `bash`（task-brief 脚本改用 Python 截取）；`uv`/`docker` 曾不在 PATH——实现侧用 venv pytest、本机 PostgreSQL 或跳过 live Compose。

### M1 Task 1–12 结论

| Task | 内容 | 结果 |
|---|---|---|
| 1 | FastAPI 骨架、错误信封、request_id、health | 完成；强制 env token；gitignore 加固 |
| 2 | 11 表 + Alembic + Compose db | 完成；凭据走 `.env`；conftest 用绝对 alembic 路径 |
| 3 | 幂等键 | 完成 |
| 4 | `derive_task_status` 真值表 | 完成 |
| 5 | 任务 CRUD API | 完成；补 TaskSummary/Detail、重复 platform→422、`prohibited_items` |
| 6 | `/internal/v1` runs/steps | 完成；FOR UPDATE；404；finish 仅终态；测试 token=`test-internal-token` |
| 7 | Mock 生成 + 槽位/版本 | 完成；版本分配加锁 |
| 8 | 审核门禁 | 完成；**保留计划码 `BLOCKING_ISSUES_PRESENT`**；不可变检查优先于 version conflict；空白 comment 无效 |
| 9 | Markdown 导出 | 完成；路径穿越防护 |
| 10 | WF-01 + Compose api/n8n + Dockerfile | 完成；循环接线；Dockerfile 分层+启动迁移；主路径失败收敛 |
| 11 | Next.js 控制台 | 完成；补 FastAPI CORS |
| 12 | Playwright + README + AGENTS | 完成；**DONE_WITH_CONCERNS**：Docker/live n8n 未 live 验；E2E 可走内部 HTTP |

### 整分支最终评审修复

- `465c383`：`derive_task_status` 在 `expected_platform_count` 未满足前不得返回 `approved`（单平台已批准、双平台任务 → `partially_ready`）。
- README 补充 E2E 与 `INTERNAL_API_TOKEN` 对齐说明。

### 推送

- 2026-08-20：`origin/main` 曾停在 `465c383`（M1）。
- 2026-08-21：M2 合入本地 `main` 后 push `origin/main`（见 §0）。接手先核对远程是否已包含 HANDOFF 本次更新。

### M2 Task 1–6 结论（已合入 `main`）

| Task | 内容 | 结果 |
|---|---|---|
| 1 | Settings、httpx、`request_json`、conftest 强制 mock | 完成 |
| 2 | Tavily Search Adapter + mock | 完成 |
| 3 | Zhipu GLM-5.3 Adapter + JSON payload | 完成 |
| 4 | 调研缓存、`provider_calls` 失败记录 | 完成 |
| 5 | 双平台契约、WF-01 Generate 120s、Compose 透传 provider env | 完成 |
| 6 | README / workflows README / HANDOFF / `.env.example` live 说明 | 完成 |
| 终审 | 非法 JSON → `PROVIDER_INVALID_RESPONSE`（`98bb746`） | **88 passed** |

**M2 明确不做：** 预算熔断、人民币单价、Playwright 打真实 Provider、真实发布 Adapter。

## 9. 执行方式（后续里程碑仍适用）

继续用 `superpowers:subagent-driven-development`：

- 主 agent 协调与评审，**不亲自写实现**（除非用户改口）。
- 每任务：brief 文件 → 实现子代理 → 评审 → Critical/Important 修复循环 → 更新 `.superpowers/sdd/progress.md`。
- 不要并行多个实现子代理；不要跳过评审；不要重新派发台账已完成任务。
- 计划示例代码与评审 finding 冲突时：**摆出双方说法问用户**（例：Task 8 错误码以计划 `BLOCKING_ISSUES_PRESENT` 为准；多平台 approved 语义最终按产品正确性修了计划示例顺序）。

Windows 实操提示：

- 测试：`cd apps\api`；`$env:INTERNAL_API_TOKEN='test-internal-token'`；`.venv\Scripts\pytest.exe tests -v`（或 `uv run pytest`）。
- 无 bash 时可用 Python 从计划文件截取 `## Task N:` 区块写 brief。

## 10. M1 验收清单（2026-08-20 本机 live 已通过）

- [x] Compose 启动后 `GET http://127.0.0.1:8000/api/v1/health` → `database=ok`
- [x] 导入并激活 `workflows/wf01-content-pipeline.json`，Webhook 触发生成成功（任务 `awaiting_review`）
- [x] Playwright：`/tasks/new` → 详情轮询 → 批准 → 导出路径可见（`1 passed`）
- [x] `cd apps\api` 下 pytest：M1 时点 **75 passed**；M2 合入后 **88 passed**（2026-08-21 合入验证）
- [x] `cd apps\web` 下 `npm run build` 通过

**本机注意（不要当通用默认）：**

- Docker Desktop 安装在 `D:\Install\DockerDesktop\Application`；CLI 为 `...\resources\bin\docker.exe`，默认不在 PATH。
- 本机已有 PostgreSQL 占 5432 且无管理员权限停不掉；验收用 `infra/docker-compose.override.yml` 把宿主机端口改成 **5433**（已 gitignore）。
- Compose 的 `--env-file` 默认看 `infra/`；根目录 `.env` 需复制为 `infra/.env`，或在 `infra/` 下执行 compose。
- n8n **2.35.5** 默认禁止表达式读 `$env`；已在 compose 设 `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`。CLI 导入需要工作流 JSON 顶层 `id`；导入后 `publish:workflow` 并重启 n8n。
- `ghcr.io/astral-sh/uv` 本机不可达；API Dockerfile 改为 `pip install uv`。

## 11. 尚未解决、需要用户决定的事

**M2 决策（2026-08-20，实现已落地）：**

- 搜索：**Tavily**（`SEARCH_PROVIDER=tavily`）。
- LLM：智谱 **`glm-5.3`**，Base URL **`https://open.bigmodel.cn/api/coding/paas/v4`**（Coding Plan 端点；切标准 API 改 `ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4`）。
- **不做预算熔断、不算人民币成本**（推迟至 M3+ 若用户再定）；额度不足由供应商报错（智谱 1113 / 1004 等）。
- 实施计划：`docs/superpowers/plans/2026-08-20-m2-real-providers.md`

**设计判断（保持，勿悄悄改）：**

- `changes_requested` 是派生表现，版本状态仍可是 `awaiting_review`。
- V1 设置页「发布适配器」在 V1 期间可为空，V1.1 再用。

## 12. 与用户协作的注意事项

- 用简体中文回复。
- PowerShell：不用 `&&`，用 `;` 或分次执行。
- 汇报先说结果，再说细节。
- 用户希望快速看到能跑的东西；完整 V1 = M1–M4，不要把「M1 做完」说成「整个 V1 做完」除非用户只问 demo。
- 需要同步云端时：先确认身份与 `git status`，再 push；用户明确选推送方式后再执行。

## 13. 建议的下一会话开场动作

```text
1. 读本 HANDOFF §0 + README + docs/superpowers/plans/2026-08-20-m2-real-providers.md
2. git checkout main；git pull；确认 HEAD 含 M2（98bb746 及之后的 HANDOFF 提交）
3. 确认根目录 .env 与 infra/.env 都有 LLM_PROVIDER=zhipu、SEARCH_PROVIDER=tavily、TAVILY_API_KEY、ZHIPU_*
   （Tavily Key 若仍缺失，先向用户要，不要编造）
4. docker compose -f infra/docker-compose.yml [-f override] up -d --build（5432 冲突用 5433）
5. 重新导入/激活 WF-01；双平台 webhook live；确认两份稿与 claim_source_map
6. 不要开工 M3，除非用户明确要求先写 M3 计划
```
