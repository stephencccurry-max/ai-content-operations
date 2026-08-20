"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { listTasks } from "@/lib/api";

export default function TasksPage() {
  const { data, error, isLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: listTasks,
  });

  if (error) return <p className="p-8 text-red-600">{(error as Error).message}</p>;
  if (isLoading) return <p className="p-8">加载中…</p>;

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">任务列表</h1>
        <Link href="/tasks/new" className="rounded bg-black px-4 py-2 text-white">
          新建任务
        </Link>
      </div>
      {data?.items.length === 0 ? (
        <p className="text-sm text-gray-600">暂无任务，点击「新建任务」开始。</p>
      ) : (
        <ul className="divide-y rounded border">
          {data?.items.map((task) => (
            <li key={task.id} className="flex items-center justify-between p-4">
              <Link href={`/tasks/${task.id}`} className="font-medium hover:underline">
                {task.topic}
              </Link>
              <span className="text-sm text-gray-600">{task.status}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
