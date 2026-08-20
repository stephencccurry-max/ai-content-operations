# n8n 工作流

M1 编排工作流导出文件，供导入本地 n8n 实例。

## WF-01 Content Pipeline

主内容生产流水线：认领运行 → 按平台循环（start step → generate → complete step）→ finish run。

### 所需环境变量

在 n8n 容器或进程环境中配置（`infra/docker-compose.yml` 已注入）：

| 变量 | 说明 |
|------|------|
| `INTERNAL_API_BASE_URL` | FastAPI 内部 API 根地址（不含路径后缀） |
| `INTERNAL_API_TOKEN` | 与 API 侧 `INTERNAL_API_TOKEN` 一致，用于 `X-Internal-Token` 头 |

**取值示例：**

- Docker Compose 全栈：`INTERNAL_API_BASE_URL=http://api:8000`
- 仅 n8n 在容器、API 在宿主机：`INTERNAL_API_BASE_URL=http://host.docker.internal:8000`

### 导入步骤

1. 启动栈：`docker compose -f infra/docker-compose.yml up -d`（需已配置 `.env`）
2. 打开 n8n：`http://127.0.0.1:5678`
3. 菜单 → **Workflows** → **Import from File**
4. 选择本目录下的 `wf01-content-pipeline.json`
5. 打开工作流，点击 **Activate** 启用 Webhook

### 触发 Webhook

先通过公开 API 创建任务，再 POST 编排入口：

```powershell
# 创建任务（示例）
curl.exe -X POST http://127.0.0.1:8000/api/v1/tasks `
  -H "Content-Type: application/json" `
  -H "Idempotency-Key: demo-1" `
  -d "{\"topic\":\"咖啡因如何影响睡眠质量\",\"audience\":\"熬夜上班族\",\"goal\":\"education\",\"platforms\":[\"xiaohongshu\"],\"tone\":\"专业、实用\"}"

# 触发 WF-01（将 <task_id> 替换为上一步返回的 id）
curl.exe -X POST http://127.0.0.1:5678/webhook/wf01 `
  -H "Content-Type: application/json" `
  -d "{\"task_id\":\"<task_id>\",\"platforms\":[\"xiaohongshu\"]}"

# 查询任务状态
curl.exe http://127.0.0.1:8000/api/v1/tasks/<task_id>
```

预期：任务状态变为 `awaiting_review`，`steps` 中含 `generate_xiaohongshu` 且为 `succeeded`。

### 节点说明

| 顺序 | 节点 | 作用 |
|------|------|------|
| 1 | WF-01 Webhook | 接收 `{task_id, platforms}` |
| 2 | Claim Run | `POST /internal/v1/tasks/{task_id}/runs` |
| 3 | Prepare Loop Items | 将 platforms 展开为循环项 |
| 4 | Loop Platforms | Split In Batches 逐平台处理 |
| 5 | Start Step | `POST .../steps/generate_{platform}/start` |
| 6 | Generate Content | `POST .../tasks/{task_id}/generate/{platform}` |
| 7 | Complete Step | `POST .../complete`，body 带 start 返回的 `attempt` |
| 8 | Finish Run | 全部平台完成后 `POST .../finish`（`succeeded`） |

节点间仅传递 ID（`task_id`、`run_id`、`platform`、`attempt`），不传正文内容。

### 错误处理（M1）

M1 主路径为 happy path；未接入 Error Trigger 分支。n8n 的 Error Trigger 在独立执行上下文中运行，无法可靠引用 Claim Run / Start Step 等主路径节点数据，原先 Fail Step 链已移除。

后续可在 HTTP 节点启用 **Continue On Fail**，在主路径上根据 `$json.error` 调用 `/fail` 与 `/finish`（`failed`）；当前失败时工作流会中止，run 状态需通过 API 或运维手段清理。

### 契约测试

不依赖 live n8n 时，可运行 API 侧编排序列测试：

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.venv\Scripts\pytest.exe tests/test_pipeline_contract.py -v
```

该测试直接调用 `/internal/v1` HTTP 序列，验证与 WF-01 相同的调用顺序与终态。
