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
  return request<
    TaskSummary & {
      steps: {
        step_key: string;
        attempt: number;
        status: string;
        error_message: string | null;
      }[];
      output_slots: { id: string; platform: string; current_version_id: string | null }[];
    }
  >(`/tasks/${taskId}`);
}

export function getSlot(slotId: string) {
  return request<{
    id: string;
    platform: string;
    current_version_id: string | null;
    versions: OutputVersion[];
  }>(`/output-slots/${slotId}`);
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
