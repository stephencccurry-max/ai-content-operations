"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { use } from "react";

import { ContentPanel } from "@/components/ContentPanel";
import { TaskDetail } from "@/components/TaskDetail";
import { getTask } from "@/lib/api";

export default function TaskPage({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = use(params);
  const { data } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => getTask(taskId),
  });

  return (
    <div className="mx-auto max-w-4xl space-y-8 p-8">
      <Link href="/tasks" className="text-sm text-gray-600 hover:underline">
        ← 返回任务列表
      </Link>
      <TaskDetail taskId={taskId} />
      {data?.output_slots.map((slot) => (
        <ContentPanel key={slot.id} slotId={slot.id} />
      ))}
    </div>
  );
}
