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
