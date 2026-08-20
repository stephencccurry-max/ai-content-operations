# Task 11 Report: Next.js 控制台

**Status:** ✅ Complete  
**Date:** 2026-08-20  
**Branch:** main  

## Summary

Implemented the Next.js web console: API client, task list/create/detail pages, polling `TaskDetail`, `ContentPanel` with approve/export actions, React Query provider, and `.env.local.example`. Production build and ESLint pass.

## Commits

| Hash | Message |
|------|---------|
| `c735b90` | `feat(web): 任务创建、详情轮询、内容查看与批准导出` |
| `1116c23` | `fix(web): track .env.local.example for API base URL config` |
| `eaa07e9` | `fix(api): enable CORS for local Next.js web console` |

## Build / Lint Verification

### `npm run build`

```powershell
cd apps\web
npm run build
```

Result: **✓ Compiled successfully** — routes `/`, `/tasks`, `/tasks/new`, `/tasks/[taskId]`

### `npm run lint`

```powershell
cd apps\web
npm run lint
```

Result: **exit 0** (no issues)

## Files Created

| File | Purpose |
|------|---------|
| `apps/web/` | Next.js 16 app (create-next-app + Tailwind + App Router) |
| `apps/web/lib/api.ts` | `createTask`, `listTasks`, `getTask`, `getSlot`, `reviewVersion`, `exportVersion` |
| `apps/web/components/Providers.tsx` | `QueryClientProvider` wrapper |
| `apps/web/components/TaskDetail.tsx` | Task detail with active-status polling |
| `apps/web/components/ContentPanel.tsx` | Slot content view, approve, export Markdown |
| `apps/web/app/tasks/page.tsx` | Task list page |
| `apps/web/app/tasks/new/page.tsx` | New task form with stable `Idempotency-Key` |
| `apps/web/app/tasks/[taskId]/page.tsx` | Detail + content panels |
| `apps/web/.env.local.example` | `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` |

## Files Modified

| File | Change |
|------|--------|
| `apps/web/app/layout.tsx` | Wrap app in `Providers`; update metadata |
| `apps/web/.gitignore` | Allow committing `.env.local.example` (`!.env.local.example`) |
| `apps/web/package.json` | Added `@tanstack/react-query` |

## Interfaces Delivered

### Pages

- **`/tasks`** — list tasks with status, link to detail and new task
- **`/tasks/new`** — create task; idempotency key generated once per mount, reset after success
- **`/tasks/{taskId}`** — task detail, step timeline, per-slot content panels

### API Client (`lib/api.ts`)

Consumes backend routes from Tasks 5/7/8/9:

- `POST /api/v1/tasks` (with `Idempotency-Key`)
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{id}`
- `GET /api/v1/output-slots/{id}`
- `POST /api/v1/output-versions/{id}/review`
- `POST /api/v1/output-versions/{id}/export`

### Polling Rules (`TaskDetail`)

| Rule | Implementation |
|------|----------------|
| Active statuses only | `queued`, `running`, `partially_ready` |
| Interval | 3s base |
| Visibility pause | `document.visibilityState !== "visible"` → `false` |
| Backoff | `3000 * 2 ** fetchFailureCount`, cap 30s |
| Terminal state | No refetch when status ∉ ACTIVE |

## Manual Verification (Step 5)

**Not run** — FastAPI API / n8n stack not started in this session. Pages, components, and API client are delivered; browser E2E deferred to Task 12 or local manual run:

```powershell
# Terminal 1: API (if not already running)
cd apps\api
$env:INTERNAL_API_TOKEN='...'
uvicorn app.main:app --reload

# Terminal 2: Web
cd apps\web
Copy-Item .env.local.example .env.local
npm run dev
# Open http://127.0.0.1:3000/tasks/new
```

## Concerns / Follow-ups

1. **Node engine warning** — Next.js 16 / eslint-visitor-keys prefers Node `^20.19.0`; current shell is `v20.10.0`. Build and lint succeed; consider upgrading Node before Task 12 Playwright e2e.
2. **No Playwright e2e yet** — per brief, Task 12 owns automated browser smoke.
3. **Home page (`/`)** — still default create-next-app placeholder; entry points are `/tasks` and `/tasks/new`.
4. ~~**CORS**~~ — **Fixed:** `CORSMiddleware` in `apps/api/app/main.py` allows `http://127.0.0.1:3000` and `http://localhost:3000`; methods GET/POST/OPTIONS; headers `Content-Type`, `Idempotency-Key`, `X-Request-Id`; `allow_credentials=False`. Tests in `tests/test_cors.py`.

## CORS Fix (Task 11 follow-up)

| Item | Detail |
|------|--------|
| File | `apps/api/app/main.py` — `CORSMiddleware` in `create_app()` |
| Origins | `http://127.0.0.1:3000`, `http://localhost:3000` |
| Methods | GET, POST, OPTIONS |
| Headers | Content-Type, Idempotency-Key, X-Request-Id |
| Credentials | false |
| Tests | `tests/test_cors.py` — OPTIONS preflight + GET `Access-Control-Allow-Origin` |
| Suite | 74 passed |

## Dependencies Added

- `next@16.3.1`, `react@19.2.8`, `@tanstack/react-query@^5.101.4` (via create-next-app + npm install)
