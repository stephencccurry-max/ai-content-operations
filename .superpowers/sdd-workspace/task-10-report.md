# Task 10 Report: n8n WF-01 编排接线

**Status:** ✅ Complete  
**Date:** 2026-08-20  
**Branch:** main  

## Summary

Implemented WF-01 orchestration wiring: pipeline contract tests (HTTP sequence without live n8n), `current_step` update on step start, n8n workflow JSON export, Compose stack with `api` + `n8n`, and env documentation for `INTERNAL_API_BASE_URL` / `INTERNAL_API_TOKEN`.

## TDD Evidence

### RED (Step 2)

Command:
```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.venv\Scripts\pytest.exe tests/test_pipeline_contract.py -v
```

Result: **1 failed, 2 passed**

| Test | Result |
|------|--------|
| test_full_pipeline_sequence_reaches_awaiting_review | PASSED |
| test_duplicate_complete_callback_is_idempotent | PASSED |
| test_current_step_reflects_latest_started_step | FAILED (`None == "generate_xiaohongshu"`) |

### GREEN (Step 4)

Command:
```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.venv\Scripts\pytest.exe tests -v
```

Result: **72 passed in 21.80s**

| New Test | Result |
|----------|--------|
| test_full_pipeline_sequence_reaches_awaiting_review | PASSED |
| test_duplicate_complete_callback_is_idempotent | PASSED |
| test_current_step_reflects_latest_started_step | PASSED |

## Files Created

| File | Purpose |
|------|---------|
| `apps/api/tests/test_pipeline_contract.py` | 3 tests: full pipeline sequence, idempotent complete, `current_step` reflection |
| `workflows/wf01-content-pipeline.json` | Importable n8n WF-01 (Webhook → claim → platform loop → finish + error branch) |
| `workflows/README.md` | Import steps, env vars, webhook trigger examples |

## Files Modified

| File | Change |
|------|--------|
| `apps/api/app/domain/runs/service.py` | `start_step` sets `ContentTask.current_step = step_key` after flush |
| `infra/docker-compose.yml` | Added `api` and `n8n` services; `n8ndata` volume |
| `.env.example` | Documented dual `INTERNAL_API_BASE_URL` values (Compose vs host API) |

## Interfaces Delivered

- **WF-01 Webhook** `POST /webhook/wf01` — body `{task_id, platforms}`
- **Env vars** — `INTERNAL_API_BASE_URL`, `INTERNAL_API_TOKEN` injected into n8n container
- **Pipeline contract** — test suite calls `/internal/v1` in WF-01 order without requiring live n8n

### WF-01 Node Sequence

1. Webhook → 2. Claim Run → 3. Prepare Loop Items → 4. Split In Batches → 5. Start Step → 6. Generate → 7. Complete Step → (loop) → 8. Finish Run  
Error branch: On Workflow Error → Fail Step → Finish Run Failed

## Manual Verification (Step 7)

**Not run** — Docker unavailable in this session. Contract tests substitute for live n8n validation per brief allowance.

## Concerns / Follow-ups

1. **No `apps/api/Dockerfile`** — Compose `api` service uses `build: ../apps/api` but Dockerfile is not in Task 10 scope; `docker compose up api` will fail until a Dockerfile is added (likely a later task).
2. **Workflow JSON hand-crafted** — Not exported from a live n8n instance; import/activate should be smoke-tested when Docker is available.
3. **Error branch context** — Fail Step uses `$('Loop Platforms')` / `$('Start Step')` references; early failures (e.g. Claim Run) may need expression hardening in production.
4. **n8n not in `depends_on`** — n8n can start before API; first webhook may fail if API is not ready (retry or health gate in Task 12+).

## Commit

```
94c6d9d feat(orchestration): WF-01 主流程接线与编排契约测试
```

---

## Follow-up Fix (Important Findings)

**Status:** ✅ Complete  
**Date:** 2026-08-20  

### Changes

| File | Fix |
|------|-----|
| `workflows/wf01-content-pipeline.json` | SplitInBatches v3 wiring: `main[0]` → Finish Run (done), `main[1]` → Start Step (loop body). Loop now correctly runs start→generate→complete per platform before finishing. |
| `apps/api/Dockerfile` | Minimal FastAPI image: Python 3.12, `uv sync` from pyproject/uv.lock, uvicorn on `0.0.0.0:8000`. |
| `infra/docker-compose.yml` | `api` service reads `DATABASE_URL` / `INTERNAL_API_TOKEN` from `.env` via `env_file`; removed hardcoded `app:app` credentials. |

### Test Evidence

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.venv\Scripts\pytest.exe tests/test_pipeline_contract.py -v   # 3 passed
.venv\Scripts\pytest.exe tests -v                             # 72 passed in 22.24s
```

### Resolved Concerns

1. ~~No `apps/api/Dockerfile`~~ — Added minimal M1 Dockerfile.
2. ~~SplitInBatches loop/done outputs swapped~~ — Fixed per n8n v3 convention.
3. ~~Hardcoded DB credentials in Compose~~ — Now aligned with `.env.example`.

### Commit

```
5f79a27 fix(orchestration): WF-01 loop wiring, API Dockerfile, Compose env
```

---

## Follow-up Fix (Important Findings — Round 2)

**Status:** ✅ Complete  
**Date:** 2026-08-20  

### Changes

| File | Fix |
|------|-----|
| `apps/api/Dockerfile` | Layered build: deps-only `uv sync --no-install-project` before COPY app/alembic; correct `COPY alembic/ alembic/`; second sync installs project; CMD runs `alembic upgrade head` then uvicorn via `uv run`. |
| `workflows/wf01-content-pipeline.json` | Removed non-functional Error Trigger → Fail Step → Finish Run Failed chain (Error Trigger cannot access main-path node data). |
| `workflows/README.md` | Documented M1 error-handling strategy: happy path only; future Continue On Fail on main path. |

### Test Evidence

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.venv\Scripts\pytest.exe tests -v   # 72 passed in 19.63s
```

### Resolved Concerns

4. ~~Error branch context~~ — Broken Error Trigger chain removed; documented M1 reliance on main-path HTTP handling.

### Commit

```
7a3ae35 fix(orchestration): Dockerfile layer cache and remove broken WF-01 error branch
```

---

## Follow-up Fix (Important Findings — Round 3)

**Status:** ✅ Complete  
**Date:** 2026-08-20  

### Changes

| File | Fix |
|------|-----|
| `workflows/wf01-content-pipeline.json` | Start Step / Generate / Complete 启用 `continueOnFail` + `alwaysOutputData`；主路径 IF 检查 `$json.error`；Generate/Complete 失败 → Fail Step（`run_id`、`step_key`、`attempt`）→ Finish Run Failed → Stop After Failure；Start 失败（无 attempt）直接 Finish Run Failed。Happy path 不变。 |
| `workflows/README.md` | 记录 M1 使用主路径 Continue On Fail 而非 Error Trigger 的原因与失败收敛路径。 |

### Test Evidence

```powershell
cd apps\api
$env:INTERNAL_API_TOKEN='test-internal-token'
.venv\Scripts\pytest.exe tests/test_pipeline_contract.py -v   # 3 passed
.venv\Scripts\pytest.exe tests -v                             # 72 passed in 22.33s
```

### Resolved Concerns

5. ~~Failure must converge run to failed~~ — In-main-path IF + `/fail` + `/finish` replaces broken Error Trigger; same execution retains Loop/Start Step context.

### Commit

```
eee6aca fix(orchestration): WF-01 in-main-path failure convergence
```
