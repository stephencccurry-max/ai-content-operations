"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createTask } from "@/lib/api";

export default function NewTaskPage() {
  const router = useRouter();
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    topic: "",
    audience: "",
    goal: "education",
    tone: "专业、实用",
    platforms: ["xiaohongshu"],
  });

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const task = await createTask(form, idempotencyKey);
      setIdempotencyKey(crypto.randomUUID());
      router.push(`/tasks/${task.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-2xl space-y-4 p-8">
      <h1 className="text-xl font-semibold">新建内容任务</h1>
      <input
        className="w-full rounded border p-2"
        placeholder="主题（5-300 字）"
        value={form.topic}
        onChange={(e) => setForm({ ...form, topic: e.target.value })}
      />
      <input
        className="w-full rounded border p-2"
        placeholder="目标受众"
        value={form.audience}
        onChange={(e) => setForm({ ...form, audience: e.target.value })}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
      >
        创建并开始生成
      </button>
    </form>
  );
}
