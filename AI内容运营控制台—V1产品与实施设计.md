# AI 内容运营控制台—V1 产品与实施设计

> 文档版本：V1.1  
> 面向对象：产品设计、Cursor 工程实施、联调、测试与验收  
> 前置文档：《AI 内容运营控制台—项目总体方案》  
> 技术基线：个人 Windows + Next.js + FastAPI + PostgreSQL + n8n + 外部 API/MCP

## 1. V1 定义

V1 是一套本地单用户内容生产工作台，支持从主题输入到批准版本的稳定主链路，并提供手动导出与受控发布扩展点。

### 1.1 V1 核心用户故事

> 作为个人内容运营者，我希望输入一个主题与目标，系统自动完成有来源的调研、内容策划、小红书稿和抖音脚本，并把质量问题和来源一起展示给我；我可以修改、批准明确版本，再导出或发布，以减少重复劳动且保持最终控制权。

### 1.2 P0 完成定义

用户可以在本地浏览器中完成：

1. 创建内容任务。
2. 查看每个步骤进度与错误。
3. 查看调研来源和结构化 Brief。
4. 查看、编辑小红书文案和抖音脚本。
5. 查看自动质检报告。
6. 批准或驳回某个明确版本。
7. 导出批准内容。
8. 对失败步骤执行安全重试。

自动发布属于 P1/Beta，不阻塞 V1 P0 验收。

## 2. 信息架构

```text
AI 内容运营控制台
├─ 仪表盘
├─ 内容任务
│  ├─ 新建任务
│  ├─ 任务列表
│  └─ 任务详情
│     ├─ 概览与进度
│     ├─ 调研
│     ├─ 内容
│     ├─ 质检与审核
│     ├─ 发布与导出
│     └─ 运行日志
├─ 审核队列
├─ 发布中心（P1，V1 仅 manual_export 与 Fake Publisher）
└─ 设置
   ├─ Provider 状态
   ├─ Prompt 版本
   ├─ 发布适配器
   └─ 系统信息
```

V1 不单独建设选题中心、素材库、账号矩阵和复杂数据分析页。候选选题先作为“新建任务”的输入；附件作为任务详情的一部分；账号配置属于发布适配器配置。

## 3. 全局交互规范

### 3.1 导航与布局

- 左侧固定主导航，顶部显示当前环境、系统健康与新建任务入口。
- 桌面端优先，设计基准宽度 1440px；最低支持 1280px。
- 状态颜色统一：进行中蓝色、待人工黄色、成功绿色、失败红色、取消/归档灰色。
- 所有时间按本机时区显示，并在 API 中使用 UTC ISO 8601。

### 3.2 反馈原则

- 创建、批准、发布等动作必须有明确成功/失败反馈。
- 耗时动作返回 `202 Accepted` 与运行 ID，不阻塞页面。
- 危险或不可逆动作二次确认：取消运行、归档、发布。
- 错误信息包含：发生步骤、用户可理解原因、是否可重试、下一步建议、错误追踪 ID。
- 页面刷新后任务状态不丢失；浏览器不是状态来源。

进度轮询遵循以下规则，避免空转请求：

- 只对非终态任务发起轮询；`completed`、`cancelled`、`archived`、`publish_failed` 等终态任务不再轮询。
- 页面切到后台或标签不可见时暂停轮询，重新可见时立即拉取一次再恢复节奏。
- 连续请求失败时按指数退避拉长间隔，并在界面提示“连接不稳定，正在重试”。
- 任务进入终态后立即停止该任务的轮询，不依赖下一次定时器自然结束。

### 3.3 自动保存与编辑

- 内容编辑器每 3 秒防抖保存草稿，页面同时提供“保存新版本”。
- 自动保存仅更新未提交的本地/服务器草稿；点击“提交审核”时固化新版本。
- 已批准版本不可编辑。修改已批准内容时复制为新草稿，并撤销其可发布资格，需重新批准。
- 离开有未保存修改的页面时提示用户。

## 4. 页面与交互详细设计

### 4.1 仪表盘 `/dashboard`

#### 页面目标

让用户 10 秒内知道今天需要处理什么、系统是否健康。

#### 展示内容

- 统计卡：运行中、待审核、失败、待发布。
- 最近任务：主题、平台、阶段、更新时间、成本、快捷操作。
- 系统健康：API、数据库、n8n、主要模型 Provider。
- 近 7 日轻量统计：任务数、成功率、平均耗时、估算成本。

#### 交互

- 点击统计卡带条件进入任务列表。
- 失败任务显示“查看原因”；待审核显示“去审核”。
- 系统不可用时显示降级信息，不使用泛化的“未知错误”。

### 4.2 新建任务 `/tasks/new`

#### 字段

| 字段 | 类型 | 必填 | 规则 |
|---|---|---:|---|
| 主题 `topic` | 文本域 | 是 | 5–300 字 |
| 目标受众 `audience` | 文本 | 是 | 2–200 字 |
| 内容目标 `goal` | 单选+补充 | 是 | 涨粉/教育/转化/品牌/其他 |
| 目标平台 `platforms` | 多选 | 是 | `xiaohongshu`、`douyin`，至少 1 个 |
| 语气 `tone` | 多选/文本 | 是 | 专业、实用、不夸张等 |
| 核心要求 `requirements` | 文本域 | 否 | 0–1000 字 |
| 禁止事项 `prohibited_items` | 文本域 | 否 | 如不得承诺收益 |
| 参考链接 `reference_urls` | URL 列表 | 否 | 最多 10 个 |
| 是否联网调研 | 开关 | 是 | 默认开启 |

#### 交互流程

1. 本地即时校验。
2. 点击“创建并开始生成”。
3. 前端在表单挂载时生成一次 `Idempotency-Key` 并在整个填写过程中复用，只有提交成功或用户主动重置表单后才更换。每次点击都重新生成的做法无效，双击照样会产生两个任务。
4. 创建成功跳转任务详情；工作流异步启动。
5. 如果工作流启动失败，任务仍保留为 `queued/failed`，允许重试。

### 4.3 任务列表 `/tasks`

#### 列

- 主题。
- 目标平台。
- 总状态和当前步骤。
- QC 分数（有报告时）。
- 创建/更新时间。
- 估算成本。
- 操作：查看、重试、取消、归档。

#### 筛选

- 状态、平台、创建日期、是否失败、是否待审核。
- 搜索主题。
- 默认按更新时间倒序。

#### 空状态

首次使用时解释产品流程并提供“创建第一个任务”，不展示空白表格。

### 4.4 任务详情 `/tasks/{taskId}`

#### 顶部区

- 主题、总状态、当前步骤、创建时间、累计耗时、估算成本。
- 操作：取消、从失败步骤重试、归档。
- 步骤条：输入 → 调研 → 策划 → 生成 → QC → 人工审核 → 导出/发布。

#### Tab：概览与进度

- 原始需求快照。
- 每个步骤状态、开始/结束时间、重试次数。
- 最近错误和建议动作。
- 只显示业务友好日志；技术详情折叠展示。

#### Tab：调研

- Research Brief：执行摘要、关键观点、数字、案例、反方观点、不确定项、内容角度。
- 每个观点展示关联来源编号。
- 来源列表：标题、域名、发布日期、访问时间、可信度、摘要、原链接。
- 来源打不开时标记，不删除历史证据。

#### Tab：内容

- 平台切换：小红书 / 抖音。
- 小红书：标题、正文、封面文字建议、标签。
- 抖音：Hook、口播脚本、分镜、CTA、预计时长。
- 版本选择器、版本差异摘要、复制、编辑、保存新版本。

#### Tab：质检与审核

- 总分及维度：事实性、相关性、结构、平台适配、风险。
- 问题分级：阻断、警告、建议。
- 问题可定位到内容字段，并显示修订建议。
- 操作：批准当前版本、驳回、请求修改、应用建议生成新版本。
- 批准弹窗显示将被批准的版本号和内容摘要。

#### Tab：发布与导出

- 仅显示已批准版本可执行操作。
- 导出 Markdown、JSON；显示导出时间与文件。
- P1：选择 Adapter、账号别名、计划时间，创建发布任务。
- 展示每次发布尝试、平台内容 ID/链接、验证状态和错误。

#### Tab：运行日志

- 步骤、Provider、模型、耗时、tokens、估算成本、状态。
- 不展示 Prompt 中可能包含的敏感原文；Prompt 输入输出需受配置控制。
- 提供追踪 ID 供开发排错。

### 4.5 审核队列 `/reviews`

- 显示所有 `awaiting_review` 与 `changes_requested` 的产物版本，包括带阻断问题的版本；阻断问题不影响进入队列，只影响能否批准。
- 列：主题、平台、版本、QC 分数、阻断问题、进入队列时间。
- 筛选项包含“含阻断问题”，命中的行用红色标识。
- 带阻断问题的版本，批准按钮禁用，并在按钮旁写明禁用原因（例如“存在 2 个规则级阻断问题，需先修改内容”）。
- 点击进入任务详情的质检与审核 Tab。
- V1 不做批量批准，避免误操作。

### 4.6 发布中心 `/publishing`（P1）

- V1 只提供 `manual_export` 与 Fake Publisher 两个 Adapter，页面用于验证发布任务的状态流转和契约；小红书、抖音的真实平台发布推迟到 V1.1。
- 筛选：计划中、执行中、成功、需确认、失败、取消。
- 显示任务、平台、版本、Adapter、计划时间、最近尝试、验证结果。
- 失败可重试；`unknown` 必须先人工确认，避免重复发布。

### 4.7 设置 `/settings`

#### Provider 状态

- 显示模型/搜索 Provider 名称、启用状态、连通性、默认模型。
- API Key 仅显示“已配置/未配置”和尾部掩码；V1 默认通过 `.env` 配置。
- “测试连接”执行最小成本请求并显示结果。

#### Prompt 版本

- V1 可只读显示当前版本和文件路径；修改通过 Git/Cursor 完成。
- 禁止在数据库中无审计地覆盖生产 Prompt。

#### 发布适配器

- `manual_export` 始终启用。
- 外部 Adapter 显示 enabled、健康、最后检查时间和风险提示。

#### 系统信息

- 应用版本、数据库 migration 版本、n8n 状态、数据目录、备份提示。

## 5. 功能需求与验收规则

### FR-01 创建任务

- 接口对字段进行服务端校验。
- 相同 Idempotency-Key 在 24 小时内返回同一任务。
- 创建任务与记录审计事件在同一事务中完成。

### FR-02 启动与追踪工作流

- 创建成功后异步触发 n8n。
- 每个任务同一时刻最多一个活动主运行。
- 每个步骤有独立状态、输入摘要、输出引用、次数和错误。

### FR-03 调研

- 生成 3–6 个查询，最大来源数量可配置，建议默认 8–12。
- V1 不自建网页抓取与正文提取，改用自带正文或高质量摘要的搜索 API（Tavily、Exa、Bocha 一类）。系统只对搜索 API 返回的结果做规范化、去重与来源评分，不解析原始 HTML。
- 正文文本由搜索 API 提供而非本地抓取，版权与留存策略据此制定：只保存 API 返回的摘要、证据片段与 URL。
- URL 规范化去重；可选内容哈希去重。
- 每个 Research Claim 至少关联一个 Source；无来源内容必须标为推测/待核实。
- 降级规则：有效来源数达不到配置下限时任务不失败，带“资料不足”警告继续后续步骤，并在审核页显著提示，由人工判断是否可用。
- 外部网页内容当作不可信数据，禁止其中指令影响系统 Prompt。

### FR-04 内容策划与生成

- Research Brief 与 Content Brief 必须通过 Pydantic Schema。
- 小红书与抖音分别调用平台 Adapter 生成，不直接截断同一篇长文。
- 输出 Schema 失败时最多执行一次格式修复。

### FR-05 自动质检

- 先运行确定性规则，再运行模型辅助评价。
- 数字来源不做正文全量数字扫描。生成模型必须在产物 payload 中显式输出 `factual_claims` 数组，每个元素包含数值、单位、口径与关联的 `claim_id` 列表；质检只校验这个数组，不去猜正文里哪些数字是事实。
- 阻断范围收窄到统计、价格、日期、比例四类事实型数字。修辞性与结构性数字（如“3 个技巧”“第 2 点”“3 分钟看完”）不受来源约束。
- 其余阻断规则包括：必填字段缺失、明显敏感/禁用词、超出关键平台限制、Schema 错误。
- 自动修订最多一次。仍不通过的产物照常进入人工审核队列，并在版本上标记阻断问题，不存在单独的质检失败终态。

### FR-06 版本与审核

- 每次生成或人工提交形成不可变版本。
- ReviewDecision 绑定具体的 `version_id`。
- 人工编辑产生的版本同样要有质检归属：保存新版本时同步运行确定性规则 QC（零模型成本），模型 QC 不自动触发，由审核人在页面上手动发起。
- 审核门禁：无规则级阻断，且（无模型级阻断 或 审核人已勾选“我已人工核对”）。勾选人工核对会写入审计事件，记录勾选人、时间和被跳过的模型级问题。
- 驳回或请求修改必须填写原因。
- 批准后生成审计事件；后续编辑必须产生新版本并重新审核。

### FR-07 导出

- 只允许导出批准版本；开发环境可通过显式开关允许草稿导出并带水印。
- Markdown 包含平台内容、来源列表、版本、批准时间。
- JSON 符合公开 Export Schema，便于后续 Adapter 使用。

### FR-08 失败与重试

- 仅对可重试错误显示重试按钮。
- 重试从失败步骤开始，并引用已完成步骤的不可变产物。
- 外部 POST/发布请求必须使用业务幂等键或本地去重。

### FR-09 可观测性

- 记录 Provider、模型、Prompt 版本、耗时、token、估算成本、错误类别。
- 记录模型定价来源与估算方式：单价来自配置文件中的模型定价表，估算成本 = 输入 token × 输入单价 + 输出 token × 输出单价，ProviderCall 同时保存所用定价表的生效时间，历史成本不因后续调价而变化。
- 设置任务级与日级预算：软阈值触发告警并在任务详情与仪表盘提示；硬阈值把任务置为 `needs_attention` 并停止该任务后续的模型与搜索调用，由人工决定是否放行。
- 日志统一携带 `request_id/task_id/run_id/step_run_id`。
- 密钥和 Cookie 必须脱敏。

## 6. 状态机设计

### 6.1 ContentTask 总状态

总状态不是被事件直接写入的字段。它由三组真实状态计算得出：当前活动运行（WorkflowRun）的状态、各平台产物版本（ContentOutputVersion）的状态、以及该任务下发布任务（PublishJob）的状态。总状态只用于列表与卡片展示，任何业务判断都必须读取上述真实状态，不得依赖这个派生值。

状态取值：

```text
queued / running / needs_attention / awaiting_review / changes_requested
partially_ready / approved / publish_pending / publishing / publish_attention
completed / publish_failed / failed / cancelled / archived
```

计算规则按顺序求值，第一条命中即返回：

```text
1. 已归档                                        → archived
2. 任务被取消，或全部平台产物被驳回且用户不再重新生成  → cancelled
3. 存在需要人工处理的异常信号                       → needs_attention
4. 存在发布任务，按发布状态汇总：
     任一 unknown 未确认                          → publish_attention
     任一处于终态失败且无可重试项                    → publish_failed
     任一 running                                → publishing
     全部 scheduled                              → publish_pending
     全部 succeeded 且已验证                       → completed
5. 有活动运行且未结束                              → running
6. 无活动运行，但存在编排层失败且无成功产物            → failed
7. 存在 changes_requested 的产物版本                → changes_requested
8. 所有必需平台均有 approved 当前版本               → approved（仅导出即结束时为 completed）
9. 部分平台已有可审核或已批准的当前版本，其余平台生成失败 → partially_ready
10. 存在 awaiting_review 的产物版本                → awaiting_review
11. 其余情况                                     → queued
```

补充说明：

- `needs_attention` 的进入条件：步骤超时、心跳丢失、n8n execution 与数据库运行状态不一致、成本触及硬阈值。这些情况都需要人工处理，系统不自行恢复，也不宣布成功或失败。
- `partially_ready` 表示部分平台产物已就绪、其余平台失败。用户可以只审核并导出已就绪的平台，同时单独重试失败平台，不必整任务重跑。
- 任务创建后直接进入 `queued`。新建任务页只有“创建并开始生成”，没有保存草稿的入口，因此不存在 `draft` 状态。
- `archived` 只能从终态进入：`completed`、`cancelled`、`publish_failed`。运行中或待人工处理的任务不允许归档。
- 平台产物和发布任务有各自状态，不用一个字段表达所有并行情况。
- 这套派生规则必须有对应的单元测试真值表：枚举运行状态、产物版本状态、发布任务状态的组合，逐条断言期望的总状态，规则调整时先改真值表。

### 6.2 WorkflowStepRun 状态

`pending → running → succeeded | failed | skipped | cancelled`

- `failed` 包含 `retryable=true/false`。
- 同一 `(run_id, step_key, attempt)` 唯一。
- 成功步骤只有在输入版本变化时才重新执行。

### 6.3 ContentOutputVersion 状态

`draft → qc_pending → awaiting_review → approved | rejected`

- 质检未通过不是终点。QC 有阻断问题的版本同样进入 `awaiting_review`，只是在版本上置 `has_blocking_issues = true`，由审核页阻止批准并说明原因。因此没有独立的质检失败状态。
- `has_blocking_issues` 是布尔字段，具体问题明细存在质检报告里，界面据此禁用批准按钮。
- `changes_requested` 不是版本状态，而是最近一次审核决策为 `request_changes` 时的派生表现。版本状态仍是 `awaiting_review`，审核队列和总状态派生规则据最近一次决策区分这两种情况，避免同一件事既写状态又写决策、两处打架。
- `approved` 是版本级状态，一旦写入不再变更。新版本产生时不会把旧版本改成“已被取代”，否则历史发布任务引用的版本状态会失真、审计链断裂。
- “哪个是当前版本”由槽位上的 `current_version_id` 表达，不用版本状态承载这个语义。
- 新版本创建后，旧批准版本仍保留历史；发布任务必须明确引用某个 `version_id`。

### 6.4 PublishJob 状态

`scheduled → running → succeeded | failed | unknown | cancelled`

- `unknown` 表示 Adapter 已执行但无法确认平台结果，禁止自动重试。
- `failed` 只有在确认未发布时才允许重试。

## 7. 数据设计

### 7.1 建议表结构

| 表 | 核心字段 |
|---|---|
| `projects` | id, name, description, created_at |
| `content_tasks` | id, project_id, topic, audience, goal, tone, requirements, status, current_step, created_at, updated_at |
| `task_platforms` | task_id, platform, output_type, status, last_error_code |
| `workflow_runs` | id, task_id, workflow_key, status, n8n_execution_id, started_at, ended_at |
| `workflow_step_runs` | id, run_id, step_key, attempt, status, retryable, error_code, error_message, input_ref, output_ref, timestamps |
| `source_documents` | id, task_id, normalized_url, title, publisher, published_at, accessed_at, content_hash, summary, credibility_score |
| `research_briefs` | id, task_id, version, executive_summary, payload_json, created_at |
| `research_claims` | id, brief_id, claim, evidence, confidence, is_uncertain |
| `claim_sources` | claim_id, source_id |
| `content_briefs` | id, task_id, version, payload_json, created_at |
| `content_output_slots` | id, task_id, platform, content_type, current_version_id, created_at |
| `content_output_versions` | id, slot_id, version, status, payload_json, title_snapshot, based_on_brief_version, prompt_version, model, temperature, provider_call_id, revision_count, revision_of_version, has_blocking_issues, created_at |
| `quality_reports` | id, version_id, overall_score, blocking_count, payload_json, created_at |
| `review_decisions` | id, version_id, decision, comment, actor, created_at |
| `publish_jobs` | id, task_id, version_id, adapter, account_alias, scheduled_at, status, idempotency_key |
| `publish_attempts` | id, publish_job_id, attempt, status, external_id, external_url, verification_status, error_code, created_at |
| `provider_calls` | id, task_id, step_run_id, provider, model, prompt_version, input_tokens, output_tokens, latency_ms, estimated_cost, status, error_code |
| `audit_events` | id, task_id, actor, action, entity_type, entity_id, metadata_json, created_at |
| `attachments` | id, task_id, kind, relative_path, sha256, mime_type, size_bytes |
| `idempotency_keys` | key, endpoint, request_hash, response_status, response_body, created_at, expires_at |

`content_tasks.status` 是按 §6.1 规则算出来的派生缓存列，只为列表筛选与排序而落库，由统一的重算入口在相关真实状态变化后写入；任何事件处理器都不得直接赋值。

`task_platforms` 的 `status` 与 `last_error_code` 用于表达“这个平台生成失败、但还没有任何产物行”的情况。没有这两列时，失败平台在数据里是一片空白，页面无法区分“还没轮到它”和“它已经挂了”，总状态也无从判断 `partially_ready`。

关于内容产物的两张表：

- `content_output_slots` 是“某个任务在某个平台上的一个内容位”，一个任务两个平台就是两行，槽位本身不携带内容，只用 `current_version_id` 指向当前生效版本。
- `content_output_versions` 是不可变的版本行，所有内容与生成参数都落在这里。
- `quality_reports`、`review_decisions`、`publish_jobs` 一律通过单一外键 `version_id` 引用具体版本，不再使用“产物 ID + 版本号”的两列组合定位。

关于版本行的字段约定：

- `payload_json` 是内容的唯一真相。版本表不单独保存 title、body 两列，因为抖音脚本根本没有 body 这个概念，两套结构硬塞进同一组列只会产生大量空值和特判。
- `title_snapshot` 是为列表检索保留的派生列，由服务端在写入版本时从 `payload_json` 中提取。它不接受直接更新，任何接口都不允许单独改这一列。
- `provider_call_id`、`prompt_version`、`model`、`temperature` 直接挂在版本行上，保证版本可独立复现。

关于幂等表：

- 同一个 `key` 命中已有记录且 `request_hash` 一致时，直接回放 `response_status` 与 `response_body`，不重复执行业务逻辑。
- 同一个 `key` 但 `request_hash` 不同时返回 `409`，表示这个键已经被另一个请求体占用。
- 记录写入 24 小时后过期，由定时清理任务按 `expires_at` 删除。

### 7.2 约束与索引

- `content_output_slots(task_id, platform, content_type)` 唯一。
- `content_output_versions(slot_id, version)` 唯一。
- `idempotency_keys(key, endpoint)` 唯一。
- `publish_jobs(idempotency_key)` 唯一。
- `source_documents(task_id, normalized_url)` 唯一。
- 列表查询索引：`content_tasks(status, updated_at desc)`。
- 审核索引：`content_output_versions(status, created_at)`。
- 发布索引：`publish_jobs(status, scheduled_at)`。
- JSONB 用于变化较快的结构化产物，但业务主键、状态、版本和关联关系使用普通列。
- 所有时间使用 `TIMESTAMPTZ`，ID 使用 UUID。

### 7.3 版本策略

- Research Brief、Content Brief、内容产物分别版本化。
- 产物版本保存其依赖的 Brief 版本，保证可复现。
- 产物版本自带 `prompt_version`、`model` 与 `provider_call_id`，复现某个版本时直接读版本行即可，不需要反查步骤运行记录去猜当时用了哪个 Prompt 和模型。
- Prompt 文件使用 Git 管理，并以 `prompt_version` 写入 ProviderCall。
- V1 不要求完整保存网页原文；保存必要摘要、证据片段哈希与 URL，避免数据库膨胀和版权风险。

## 8. API 设计

### 8.1 公共约定

- 前缀：`/api/v1`。
- JSON 使用 `snake_case` 或 `camelCase` 二选一并全局一致；推荐 API 使用 `snake_case` 与 Pydantic 对齐。
- 错误格式：

```json
{
  "error": {
    "code": "PROVIDER_RATE_LIMITED",
    "message": "模型服务限流，请稍后重试",
    "retryable": true,
    "request_id": "uuid",
    "details": {}
  }
}
```

- 所有 mutation 支持/要求 `Idempotency-Key`。键由前端在表单挂载时生成一次并复用，提交成功或用户主动重置后才更换；不要在每次点击提交时重新生成，否则双击仍会产生两个任务。
- 幂等键的服务端行为见 `idempotency_keys` 表约定：同键同请求体回放原响应，同键不同请求体返回 `409`，记录 24 小时后过期。
- 列表采用 `limit + cursor`；V1 也可先用 `page + page_size`，但需保持响应稳定。

### 8.2 任务接口

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/tasks` | 创建任务并异步启动 |
| GET | `/tasks` | 列表与筛选 |
| GET | `/tasks/{id}` | 任务概览 |
| POST | `/tasks/{id}/cancel` | 取消活动运行 |
| POST | `/tasks/{id}/retry` | 从安全步骤重试 |
| POST | `/tasks/{id}/archive` | 归档 |
| GET | `/tasks/{id}/runs` | 运行和步骤 |
| GET | `/tasks/{id}/sources` | 来源与 claims |

### 8.3 内容与审核接口

产物槽位与产物版本都是顶层资源，路径不嵌在任务下面；任务路径只保留列表查询。这样同一个版本在审核队列、发布中心和任务详情里是同一个 URL，不会出现两套写法。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/tasks/{id}/output-slots` | 列出该任务的平台内容位及当前版本 |
| GET | `/output-slots/{slot_id}` | 槽位详情与版本列表 |
| POST | `/output-slots/{slot_id}/versions` | 保存新版本 |
| POST | `/output-slots/{slot_id}/regenerate` | 定向重新生成 |
| GET | `/output-versions/{version_id}/quality-report` | 获取 QC |
| POST | `/output-versions/{version_id}/review` | approve/reject/request_changes |
| POST | `/output-versions/{version_id}/export` | 导出批准版本 |
| GET | `/reviews` | 审核队列 |

`POST /output-versions/{version_id}/review` 示例：

```json
{
  "version": 3,
  "decision": "approve",
  "comment": "来源已核对，可以发布",
  "human_verified": true
}
```

`version` 字段用于版本冲突校验：服务端必须防止对过期版本批准，如果槽位当前版本与请求版本不一致，返回 `409 VERSION_CONFLICT`。

`human_verified` 对应审核页的“我已人工核对”勾选。存在模型级阻断问题时必须为 `true` 才允许批准，服务端据此写入审计事件；存在规则级阻断问题时无论该字段取值都拒绝批准。

### 8.4 发布接口

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/publish-jobs` | 创建发布任务 |
| GET | `/publish-jobs` | 查询发布中心 |
| GET | `/publish-jobs/{id}` | 详情与尝试 |
| POST | `/publish-jobs/{id}/cancel` | 取消未执行任务 |
| POST | `/publish-jobs/{id}/retry` | 仅确认未发布后重试 |
| POST | `/publish-jobs/{id}/confirm` | 人工确认 unknown 结果 |

### 8.5 内部 n8n 接口

使用 `/internal/v1`，只允许共享密钥/本机网络访问：

- `POST /runs/{run_id}/steps/{step_key}/start`
- `POST /runs/{run_id}/steps/{step_key}/complete`
- `POST /runs/{run_id}/steps/{step_key}/fail`
- `POST /tasks/{task_id}/research`
- `POST /tasks/{task_id}/plan`
- `POST /tasks/{task_id}/generate/{platform}`
- `POST /output-versions/{version_id}/quality-check`
- `POST /publish-jobs/claim`

关于步骤 attempt：

- `start` 由服务端分配并在响应中返回 `attempt` 序号，保证 `(run_id, step_key, attempt)` 唯一。编排器不自己计数，也无法猜到当前是第几次。
- `complete` 与 `fail` 必须带上 `start` 返回的 `attempt`，否则无法确定要收尾哪一次执行；attempt 不匹配时拒绝写入。

关于发布任务认领：

- `POST /publish-jobs/claim` 由服务端用 `SELECT ... FOR UPDATE SKIP LOCKED` 或状态 CAS 完成原子认领，返回本次可执行的任务，没有可领任务时返回空列表。
- 编排器不自行判断某个任务能不能领取。“查出来再决定”这种两步做法在重启、并发或重复触发时必然产生重复发布。

n8n 不直接拼接 SQL 写业务表。

## 9. Schema 示例

### 9.1 ResearchBrief

```json
{
  "executive_summary": "string",
  "claims": [
    {
      "claim_id": "uuid",
      "claim": "string",
      "evidence": "string",
      "source_ids": ["uuid"],
      "confidence": 0.85,
      "is_uncertain": false
    }
  ],
  "statistics": [
    {
      "value": "string",
      "context": "string",
      "source_id": "uuid",
      "needs_manual_verification": false
    }
  ],
  "counterpoints": ["string"],
  "uncertain_points": ["string"],
  "content_angles": ["string"]
}
```

### 9.2 XiaohongshuOutput

```json
{
  "title": "string",
  "hook": "string",
  "body": "string",
  "cover_text": "string",
  "hashtags": ["string"],
  "claim_source_map": [
    {"claim_id": "uuid", "source_ids": ["uuid"]}
  ],
  "factual_claims": [
    {
      "value": "string",
      "unit": "string",
      "basis": "string",
      "claim_id": "uuid",
      "source_ids": ["uuid"]
    }
  ]
}
```

### 9.3 DouyinScriptOutput

```json
{
  "hook": "string",
  "script": "string",
  "estimated_duration_seconds": 45,
  "scenes": [
    {
      "order": 1,
      "duration_seconds": 5,
      "voiceover": "string",
      "visual_hint": "string",
      "on_screen_text": "string"
    }
  ],
  "cta": "string",
  "claim_source_map": [
    {"claim_id": "uuid", "source_ids": ["uuid"]}
  ],
  "factual_claims": [
    {
      "value": "string",
      "unit": "string",
      "basis": "string",
      "claim_id": "uuid",
      "source_ids": ["uuid"]
    }
  ]
}
```

### 9.4 引用锚点约定

`claim_source_map` 用 `claim_id` 而不是 claim 文本做锚点。用文本做锚点时，用户在编辑器里改一个字，整条引用关系就断了，而系统还以为它有来源。

- 正文中的引用位置由轻量标记承载（例如 `[[c:{claim_id}]]`），渲染时转成上标序号，导出时转成来源编号。
- 保存新版本时校验引用完整性：正文标记引用的 `claim_id` 必须存在于 `claim_source_map`，反之 map 中的每个 `claim_id` 也要能在 Research Brief 里找到。
- 校验不通过的引用标记为 stale，不阻断保存，但在审核页明确提示“有 N 处引用已失联”，由人工决定是补回来源还是删掉相应表述。
- `factual_claims` 的每个元素都必须有 `claim_id` 与至少一个 `source_ids`，这是质检的直接校验对象。

## 10. n8n 工作流设计

不建议第一版建立八个高度碎片化工作流，也不要做一个上百节点的超级工作流。建议 4 个主工作流：

### WF-01 内容生产主流程

```text
Webhook/Execute
 → API: claim run
 → API: research
 → API: plan
 → Split platforms
 → API: generate platform output
 → API: QC
 → If fixable and revision_count < 1: revise → QC
 → API: mark awaiting_review
 → complete
```

要求：

- n8n 节点只传递 ID，较大产物从 FastAPI/PostgreSQL 读取。
- 每步开始/完成/失败都回调 FastAPI。
- 重试由错误类型决定，最大 2 次；模型格式修复最大 1 次。
- 使用 execution ID 与 run ID 关联。

### WF-02 发布调度流程（P1）

```text
Schedule Trigger
 → fetch due jobs
 → claim job atomically
 → adapter.publish()
 → verify()
 → persist result
 → notify attention if unknown/failed
```

### WF-03 错误处理流程

- 接收 n8n Error Trigger。
- 通过 run/step ID 写入标准错误。
- 不发送重复通知；按错误指纹去重。
- 不在错误流程里自动重跑发布动作。

### WF-04 健康与对账流程

- 每日检查卡住超过阈值的 `running` 任务。
- 对比 n8n execution 与 PostgreSQL run 状态。
- 将不一致标为 `needs_attention`，不擅自宣布成功。

## 11. 外部 Provider 与 MCP 设计

### 11.1 Provider 接口

```python
class LLMProvider:
    async def generate_structured(self, *, schema, messages, options): ...

class SearchProvider:
    # 返回项：url、title、publisher、published_at、score
    # 以及 content（正文或长摘要，由搜索 API 直接提供）
    async def search(self, *, queries, limit): ...

class PublisherAdapter:
    async def validate(self, payload): ...
    async def publish(self, payload, idempotency_key): ...
    async def verify(self, external_ref): ...
```

`SearchProvider.search()` 的返回必须包含正文或长摘要字段。这段文本由搜索 API 提供，不是本地抓取页面再抽取正文得到的；选型时把“是否返回可用正文”作为硬性条件，不满足的 Provider 不进 V1。

### 11.2 配置策略

- Provider 由环境变量选择，例如 `LLM_PROVIDER`、`LLM_MODEL`。
- 模型定价单独用配置文件维护：模型标识到输入/输出单价的映射，每份定价记录生效时间。调价时新增一条记录，不覆盖旧记录，历史 ProviderCall 的估算成本保持不变。
- 预算检查放在 Provider 层的统一调用入口，每次调用前累加任务级与日级已用成本并比对阈值，业务代码和 Prompt 逻辑不需要各自判断。软阈值只告警，硬阈值抛出预算错误、把任务置为 `needs_attention` 并停止后续调用。
- 业务代码只依赖接口和领域 DTO。
- MCP Client 放在 infrastructure/adapter 层，把 MCP 结果转换为内部 DTO。
- 调用统一设置 connect/read/total timeout、最大重试和并发限制。
- 对 429、5xx、网络超时、Schema 错误分别分类。

### 11.3 Prompt 管理

建议目录：

```text
packages/prompts/
├─ research/query_generator.v1.md
├─ research/brief.v1.md
├─ planning/content_brief.v1.md
├─ platforms/xiaohongshu.v1.md
├─ platforms/douyin.v1.md
└─ quality/review.v1.md
```

每个 Prompt 包含 role、objective、inputs、constraints、factual rules、output schema 和版本。Prompt 变更必须进入 Git，不直接在线无版本覆盖。

## 12. 异常处理与补偿

### 12.1 错误分类

| 类别 | 例子 | 自动重试 |
|---|---|---:|
| Validation | 用户字段缺失、Schema 不合法 | 否 |
| Authentication | API Key/Cookie 失效 | 否，提示配置 |
| RateLimit | 429 | 是，指数退避+抖动 |
| TransientNetwork | 超时、连接重置、5xx | 是，最多 2 次 |
| ProviderContent | 拒答、安全限制 | 否/改为人工处理 |
| SchemaOutput | 模型 JSON 不合法 | 一次格式修复 |
| BusinessRule | 未批准版本请求发布 | 否 |
| PublishUnknown | 已点击但无法验证 | 否，人工确认 |

### 12.2 重试策略

- 普通外部 GET/模型调用：1s、3s 指数退避，最多 2 次。
- Search 允许部分成功：即使有效来源数低于下限也继续后续步骤，并显示资料不足警告，由人工在审核时判断是否可用。
- 生成平台内容可独立重试，不重复调研。
- 发布动作除非 Adapter 提供幂等或确认未发布，否则不自动重试。

### 12.3 卡住任务

- 步骤有 `heartbeat_at` 或最大执行时间。
- 超时后标记 `failed` 或 `needs_attention`，禁止永久显示 running。
- 对账工作流每天检查，页面也可手工触发刷新状态。

## 13. 人工审核设计

### 13.1 审核门禁

以下任一情况不得批准，且不可绕过：

- Schema/必填字段不完整。
- 存在未处理的规则级阻断问题。
- `factual_claims` 中存在无来源条目，且未删除或改为不确定表述。
- 内容版本已过期或与页面打开时版本不一致。

模型级阻断问题不硬拦截，但需要审核人勾选“我已人工核对”后才能批准，勾选动作连同被跳过的问题一起写入审计事件。规则级与模型级的划分以质检报告中的问题来源为准。

### 13.2 审核人需要看到

- 原始需求。
- 当前内容版本及与上一版差异。
- 关键 Claim 对应来源。
- 自动 QC 及问题定位。
- 模型生成提示：AI 结果可能有误，批准代表人工确认。

### 13.3 决策

- `approve`：当前版本可导出/发布。
- `request_changes`：填写具体修改项，产生修改任务。
- `reject`：终止该产物，不自动重新生成。
- `regenerate`：选择范围（标题/正文/脚本/全部）和要求，产生新版本。

## 14. 发布适配器设计

### 14.1 标准发布载荷

```json
{
  "job_id": "uuid",
  "platform": "xiaohongshu",
  "account_alias": "default",
  "content": {
    "title": "string",
    "body": "string",
    "hashtags": ["string"]
  },
  "assets": [],
  "scheduled_at": null,
  "idempotency_key": "uuid"
}
```

### 14.2 V1 Adapter

V1 只有两个 Adapter：

1. `manual_export`（P0）：生成 Markdown/JSON 文件，状态可可靠确认。
2. `fake_publisher`：用于契约验证，可按配置模拟 `scheduled`、`succeeded`、`failed`、`unknown` 四种结果，覆盖认领、幂等、验证与人工确认路径。

真实平台发布整体推迟到 V1.1：小红书图文必须带图，而 V1 没有图片能力；抖音方向不做视频合成，因而没有视频资产。两个候选 Adapter 在 V1 都拿不出可发布的载荷，接了也只能空跑。这部分与图片、视频能力在 V1.1 一并排期。

### 14.3 发布验证

发布成功至少满足其一：

- 官方 API 返回平台内容 ID 且可查询。
- Adapter 返回内容 URL，并回查可见。
- 浏览器自动化在发布历史中匹配标题/时间/账号，保存截图或明确证据。

仅收到“按钮点击完成”时状态为 `unknown`，不是 `succeeded`。

### 14.4 账号与 Cookie

- 不在业务数据库保存明文 Cookie。
- 由发布组件自己的受保护存储管理，控制台只保存 `account_alias` 和健康状态。
- 登录过期后提示人工重新登录，不尝试绕过验证码。

## 15. 非功能需求

### 15.1 性能与容量

- 单用户，默认最大并发内容任务 2 个。
- 列表首屏 ≤ 2 秒；详情基础数据 ≤ 2 秒（本机健康状态下）。
- 大产物按需加载，不把完整运行日志塞入列表接口。

### 15.2 可靠性

- FastAPI/Next.js 重启不影响已保存业务状态。
- n8n 重启后任务可通过对账恢复或明确失败。
- 数据库 migration 可从空库完整执行。
- 每个外部调用均有超时，不允许无限等待。

### 15.3 安全

- 默认绑定 localhost。
- CORS 只允许本地 Web Origin。
- 内部 n8n API 使用独立密钥，日志脱敏。
- 前端不返回服务器 API Key。
- 导出路径需防止目录穿越，附件校验大小、类型与哈希。

### 15.4 可维护性

- Python 与 TypeScript 启用格式化、Lint 和类型检查。
- OpenAPI 自动生成前端类型或客户端，避免接口漂移。
- 核心状态迁移、审核门禁和发布幂等必须有单元测试。

## 16. 推荐代码结构

```text
ai-content-ops/
├─ apps/
│  ├─ web/                         # Next.js
│  └─ api/                         # FastAPI 模块化单体
│     ├─ app/
│     │  ├─ api/
│     │  ├─ domain/
│     │  │  ├─ tasks/
│     │  │  ├─ research/
│     │  │  ├─ content/
│     │  │  ├─ review/
│     │  │  └─ publishing/
│     │  ├─ application/
│     │  ├─ infrastructure/
│     │  │  ├─ db/
│     │  │  ├─ providers/
│     │  │  └─ adapters/
│     │  └─ main.py
│     ├─ alembic/
│     └─ tests/
├─ packages/
│  ├─ contracts/                   # OpenAPI/schema/共享常量
│  └─ prompts/
├─ workflows/
│  ├─ wf01-content-pipeline.json
│  ├─ wf02-publishing.json
│  ├─ wf03-error-handler.json
│  └─ README.md
├─ infra/
│  ├─ docker-compose.yml
│  └─ scripts/
├─ data/                           # Git ignore
│  ├─ exports/
│  └─ assets/
├─ docs/
│  └─ superpowers/
│     └─ plans/                    # 每个里程碑的实施计划
├─ .env.example
├─ AGENTS.md
└─ README.md
```

`docs/superpowers/plans/` 存放每个里程碑的实施计划：一个里程碑一份文件，写明范围、交付物、拆分出的纵向切片与验收方式，开工前先产出、执行中随进展更新。

## 17. 测试策略

### 17.1 单元测试

- 状态机合法/非法迁移。
- 总状态派生规则真值表。
- 版本与批准门禁。
- URL 规范化与去重。
- Claim 来源约束。
- QC 阻断规则。
- 发布幂等与 unknown 禁止自动重试。
- 错误分类与重试判断。

### 17.2 集成测试

- FastAPI + 临时 PostgreSQL：创建任务到待审核。
- Mock LLM/Search Provider 的成功、429、超时、Schema 错误。
- n8n 回调重复到达时幂等。
- Migration 从空库升级，备份恢复后数据完整。
- 导出文件内容、路径与编码正确。

### 17.3 E2E 测试

使用 Playwright 覆盖：

1. 创建任务并看到运行步骤。
2. 模拟完成后查看来源、内容和 QC。
3. 编辑生成新版本并批准。
4. 版本冲突时阻止批准。
5. 导出 Markdown/JSON。
6. 失败任务显示原因并安全重试。

### 17.4 发布 Adapter 测试

- 首先使用 Fake Adapter 验证 scheduled/success/failed/unknown。
- 自动发布只使用隔离测试账号和非敏感内容。
- 验证重复请求不会产生重复发布。
- 模拟登录过期、页面变化、上传中断和无法确认结果。

### 17.5 Prompt 与输出回归

纯 Mock 测试只能证明流程跑得通，证明不了内容质量没有退化。改一句 Prompt、给 Schema 加一个字段，模型可能就开始漏填 `factual_claims` 或者把来源编号编出来，而所有 Mock 用例照样全绿。因此需要一层基于真实响应的回归：

- 把真实 Provider 的请求与响应录制为 cassette 并纳入 Git，作为回归基线；录制时脱敏密钥，保留完整的模型输出。
- Prompt 或 Schema 变更时回放全部 cassette，断言：输出结构合法、必填字段齐全、每条 `factual_claim` 都有 `claim_id` 与来源、引用锚点无失联。
- 回放不消耗外部额度，可以进本地常规测试命令。基线更新必须是显式动作，不允许测试失败时自动重录。
- 结构合法不等于内容可用，因此另配一份人工评分表（事实性、相关性、结构、平台适配、风险五个维度），用于 M4 的 20 选题试运行，把主观质量也记录成可比较的数据。

## 18. 验收指标

本节是全项目量化指标的唯一来源。总体方案与 README 引用这里的数字，不再各自维护一套，出现不一致时以本节为准。

### 18.1 功能验收

- 两个平台的 P0 结构化产物均能生成、展示、编辑和版本化。
- 调研 Claim 可回溯来源；产物 `factual_claims` 中缺少来源的条目被阻断。
- 已批准版本不可原地修改；未批准版本不能创建发布任务。
- 工作流失败有错误类别、步骤、追踪 ID 和正确重试选项。
- 导出文件可在常用编辑器正常打开，中文无乱码。

### 18.2 质量验收

样本为连续 20 个真实选题任务：

- 工作流成功率 ≥ 80%：外部服务健康时，按任务统计，任务到达待审核即计为成功。
- 产物经一次人工修改即可达到可用标准的比例 ≥ 70%：按产物统计，一个双平台任务贡献两个样本。
- 100% 事实型数字（统计、价格、日期、比例）有来源或被标记阻断。
- 不出现任务状态永久卡住而页面无解释。
- 单任务成本可查看，ProviderCall 记录覆盖率 100%。
- 耗时在 V1 只观测不设阈值：在 M4 试运行中采集 P50/P95 基线，之后再定阈值。作为容量参考，一个双平台任务约需 15–25 次模型或搜索调用。

### 18.3 工程验收

- 新电脑按 README 能通过 Compose 启动。
- 所有 migration、单元测试、集成测试、前端 build 通过。
- `.env.example` 不包含真实密钥，Git 历史无敏感信息。
- 数据库备份与恢复至少演练一次。
- 关闭外部发布 Adapter 时，P0 主链路仍完整可用。

## 19. 里程碑计划

一人使用 Cursor 开发，按四个里程碑推进。不按周估算，只按交付物验收：交付物没有全部通过验收，就不进入下一个里程碑。

每个里程碑开工前，先在 `docs/superpowers/plans/` 产出该里程碑的实施计划，写清纵向切片划分与验收方式，再开始写代码。

### M1 走通闭环（全 Mock 驱动）

范围：

- 工程底座：Monorepo、Docker Compose、环境变量、四项健康检查、日志与 request ID。
- 数据库迁移：核心表、槽位与版本两张表、幂等表、约束与索引。
- 任务能力：创建、列表、详情，派生总状态及其单元测试真值表，幂等提交。
- 编排：n8n WF-01 骨架与步骤开始/完成/失败回调，服务端分配 attempt。
- 内容：Mock Provider 产出符合 Schema 的两个平台产物，页面可查看与批准。
- 导出：Markdown 导出。

交付物：一个不依赖任何外部 API、可在本地完整演示的端到端 demo，从创建任务到批准并导出 Markdown 全程可走通。

### M2 真实内容生产

范围：

- 接入搜索 API 与 LLM Provider，替换 Mock。
- Prompt 管理与版本化。
- Research Brief、Content Brief 的结构化生成与来源去重、来源评分。
- 小红书图文与抖音脚本的平台化生成。
- ProviderCall 记录、成本估算、任务级与日级预算及熔断。

交付物：真实外部 API 下可稳定产出两个平台的结构化产物，每次调用有成本记录，触及硬阈值时任务停在 `needs_attention`。

### M3 质检与人工审核

范围：

- 规则 QC 与模型 QC，一次受控自动修订。
- 版本管理与审核门禁，含“我已人工核对”确认与审计事件。
- 审核队列，含阻断问题筛选与标识。
- 人工编辑、保存新版本、版本冲突处理。
- 来源引用完整性校验与 stale 引用提示。

交付物：从生成到批准的完整审核闭环，带阻断问题的版本无法被批准，所有批准动作可审计。

### M4 稳定性、导出与试运行

范围：

- 错误分类与重试策略落地，卡住任务对账。
- 备份与恢复演练。
- JSON 导出，Fake Publisher 的 Adapter 契约验证（四态覆盖）。
- E2E 测试，Prompt 黄金样本回归。
- 20 个真实选题试运行，采集 §18 指标与耗时 P50/P95 基线。

交付物：P0 正式可用版本，§18 全部验收指标有实测数据支撑。

### V1.1（不在 V1 范围）

- 图片与卡片模板能力。
- 小红书与抖音真实发布 Adapter。
- 发布后数据反馈。

## 20. Cursor 执行建议

### 20.1 使用方式

- 先让 Cursor 阅读本文件和总体方案，再输出当前里程碑的实施计划并写入 `docs/superpowers/plans/`，不要一次要求完成全项目。
- 每个任务限制在一个可验收的纵向切片，要求它运行测试并报告结果。
- 让 Cursor 优先复用已有代码和契约，不在未确认时替换技术栈。
- 每次数据库变更必须同时生成 migration、模型、Schema 和测试。
- 每次接口变更同步 OpenAPI/前端类型与 E2E。
- Prompt 与 JSON Schema 独立版本化，不把长 Prompt 散落在 n8n 节点和业务代码中。

### 20.2 建议写入仓库 `AGENTS.md` 的约束

```text
1. 本项目是个人 Windows 本地应用，不引入多租户、Kubernetes 或微服务。
2. FastAPI 是业务状态和状态迁移唯一入口；n8n 不直接修改核心业务表。
3. 所有外部 Provider 必须经过 Adapter，设置超时、有限重试并记录调用。
4. 内容产物采用不可变版本；只有明确批准的版本可导出或发布。
5. 发布动作必须幂等；结果 unknown 时禁止自动重试。
6. 新功能必须包含测试、错误态、空状态和文档更新。
7. 不提交 API Key、Cookie、真实用户数据或生成资产。
8. 先实现 P0 验收标准，不提前建设 V2 模块。
9. 实现任何功能前先写失败测试，并确认它以预期原因失败；不接受先写实现再补测试。
10. 每个任务完成后必须经过一轮独立代码评审，评审意见处理完再进入下一个任务。
11. 声称完成前必须实际运行测试命令并贴出输出结果，不凭印象判断通过。
```

### 20.3 每个 Cursor 开发请求模板

```text
目标：实现 [一个明确纵向切片]。

范围：
- 必须完成：...
- 不做：...

约束：
- 遵循 docs 中的总体方案与 V1 设计。
- 不改变既定技术栈和状态机；如发现冲突先说明。
- 数据库变更必须生成 Alembic migration。
- API 必须有 Pydantic Schema、统一错误和幂等处理。
- 添加单元/集成测试，并实际运行。

验收：
1. ...
2. ...
3. ...

完成后输出：改动摘要、测试结果、已知限制、下一步建议。
```

### 20.4 不建议给 Cursor 的宽泛指令

- “把整个平台全部开发出来”。
- “参考某开源项目直接整合全部功能”。
- “自动选择最好架构并重构”。
- “把所有 n8n 节点、数据库、前后端一次生成完成”。

这些指令容易导致范围漂移、未验证依赖和难以排错的批量改动。

## 21. 实施清单

### 开工前（贯穿全程）

- [ ] P0/P1/V1.1 范围写入 README，量化指标统一引用 §18。
- [ ] 确认默认平台、内容目标和字段字典。
- [ ] 在 `docs/superpowers/plans/` 建立里程碑实施计划目录。

### M1 走通闭环（全 Mock 驱动）

- [ ] 安装并验证 Docker Desktop/WSL2、Git、Cursor。
- [ ] 创建 `.env.example` 与本地 `.env`。
- [ ] 固定主要依赖版本和 Compose 服务健康检查。
- [ ] 创建持久化 volume 与 `data/` 目录。
- [ ] 创建核心表、约束、索引和 migration，含 `content_output_slots` 与 `content_output_versions` 拆分。
- [ ] 建立 `idempotency_keys` 表与幂等服务，覆盖同键同请求回放、同键异请求 409、过期清理。
- [ ] 实现总状态派生计算与单元测试真值表。
- [ ] 实现版本服务、Mock Provider 与 Adapter 接口。
- [ ] 实现统一错误、审计、调用记录和日志脱敏。
- [ ] 导入 WF-01 骨架，配置内部 API 密钥和超时，服务端分配 attempt。
- [ ] 验证重复回调幂等与步骤失败路径。
- [ ] Workflow JSON 纳入 Git，凭据不纳入 Git。
- [ ] 前端：仪表盘、任务创建、列表、详情、非终态轮询规则。
- [ ] 前端：错误态、空状态、加载态和健康提示。
- [ ] 完成 `manual_export` 的 Markdown 导出。

### M2 真实内容生产

- [ ] 配置至少一个 LLM Provider 和一个支持返回正文的 Search Provider。
- [ ] 实现搜索结果规范化、去重与来源评分，含资料不足降级。
- [ ] 建立 Prompt 目录与版本化，实现 Research Brief、Content Brief。
- [ ] 实现小红书图文与抖音脚本生成，产出 `factual_claims` 与 `claim_source_map`。
- [ ] 建立模型定价配置与生效时间，记录 ProviderCall 与估算成本。
- [ ] 实现任务级与日级预算，软阈值告警、硬阈值熔断并置 `needs_attention`。
- [ ] 验证限流、超时、拒答与 Schema 失败。
- [ ] 设置单任务并发上限。

### M3 质检与人工审核

- [ ] 实现规则 QC 与模型 QC，自动修订最多一次。
- [ ] 实现引用完整性校验与 stale 引用提示。
- [ ] 实现审核门禁：规则级阻断硬拦截，模型级阻断需人工核对确认并写审计。
- [ ] 前端：调研、内容、QC/审核、运行日志 Tab。
- [ ] 前端：编辑自动保存、保存新版本触发规则 QC、版本冲突与离开提醒。
- [ ] 前端：审核队列含阻断问题筛选、红色标识与批准按钮禁用原因。

### M4 稳定性、导出与试运行

- [ ] 完成错误分类与重试策略。
- [ ] 导入 WF-03/WF-04，验证 n8n 重启与卡住任务对账。
- [ ] 完成 JSON 导出。
- [ ] 完成 Fake Publisher 的四类状态契约验证。
- [ ] 准备 20 个真实验收选题与人工评分表。
- [ ] 录制 Prompt 黄金样本 cassette 并接入回归测试。

### 测试与交付

- [ ] 单元、集成、E2E 测试通过。
- [ ] 20 个真实任务试运行并记录指标。
- [ ] 备份恢复演练。
- [ ] 新环境按 README 冷启动演练。
- [ ] 记录已知限制和 V1.1 决策。

## 22. 上线前最后检查

只有以下问题全部回答“是”，V1 才算完成：

- 用户能否只通过 Web 控制台完成日常 P0 流程？
- 任一任务失败时，能否知道失败在哪里以及能否重试？
- 任一公开内容能否追溯到明确版本、来源和人工批准？
- 修改已批准内容后，系统是否强制重新审核？
- 发布结果不确定时，系统是否避免重复发布？
- 关闭 n8n 编辑界面和 Cursor 后，日常运营是否仍能进行？
- 外部发布器完全不可用时，是否仍能导出批准内容？
- 备份是否能恢复任务、内容版本和审核记录？

达到这些标准后，再根据真实运营数据决定图片、视频、自动发布、数据分析和团队化，而不是在 V1 中提前建设。

## 23. 修订记录

| 日期 | 版本 | 说明 |
|---|---|---|
| 2026-08-19 | V1.1 | 基于产品与架构评审结论调整：拆分内容产物槽位与版本、总状态改为派生、补幂等表与成本预算、调研改用自带正文的搜索 API、审核门禁纳入人工核对确认、发布收紧为导出与 Fake Adapter、Sprint 重构为 M1–M4 里程碑。 |
