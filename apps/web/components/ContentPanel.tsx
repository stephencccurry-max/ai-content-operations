"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { exportVersion, getSlot, reviewVersion, type OutputVersion } from "@/lib/api";

function resolveCurrentVersion(
  versions: OutputVersion[],
  currentVersionId: string | null,
): OutputVersion | undefined {
  if (currentVersionId) {
    return versions.find((version) => version.id === currentVersionId);
  }
  return versions.at(-1);
}

function displayTitle(version: OutputVersion): string {
  const payload = version.payload;
  const fromPayload =
    (typeof payload.title === "string" && payload.title) ||
    (typeof payload.hook === "string" && payload.hook);
  return fromPayload || version.title_snapshot || "—";
}

function displayBody(version: OutputVersion): string {
  const payload = version.payload;
  if (typeof payload.body === "string") return payload.body;
  if (typeof payload.script === "string") return payload.script;
  return "";
}

export function ContentPanel({ slotId }: { slotId: string }) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const [exportPath, setExportPath] = useState<string | null>(null);
  const [busy, setBusy] = useState<"approve" | "export" | null>(null);

  const { data, error } = useQuery({
    queryKey: ["slot", slotId],
    queryFn: () => getSlot(slotId),
  });

  if (error) return <p className="text-red-600">{(error as Error).message}</p>;
  if (!data) return <p>加载内容…</p>;

  const current = resolveCurrentVersion(data.versions, data.current_version_id);
  if (!current) {
    return <p className="text-sm text-gray-600">平台 {data.platform}：暂无内容版本</p>;
  }

  async function onApprove() {
    setBusy("approve");
    setActionError(null);
    try {
      await reviewVersion(current!.id, current!.version, "approve");
      await queryClient.invalidateQueries({ queryKey: ["slot", slotId] });
      await queryClient.invalidateQueries({ queryKey: ["task"] });
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function onExport() {
    setBusy("export");
    setActionError(null);
    try {
      const result = await exportVersion(current!.id);
      setExportPath(result.file_path);
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3 rounded border p-4">
      <h2 className="font-medium">平台：{data.platform}</h2>
      <p className="text-sm text-gray-600">
        版本 {current.version} · {current.status}
      </p>
      <h3 className="text-lg font-semibold">{displayTitle(current)}</h3>
      <pre className="whitespace-pre-wrap text-sm">{displayBody(current)}</pre>
      {actionError && <p className="text-sm text-red-600">{actionError}</p>}
      <div className="flex gap-2">
        {current.status !== "approved" && (
          <button
            type="button"
            disabled={busy !== null}
            onClick={onApprove}
            className="rounded bg-green-700 px-3 py-1 text-sm text-white disabled:opacity-50"
          >
            批准当前版本
          </button>
        )}
        <button
          type="button"
          disabled={busy !== null || current.status !== "approved"}
          onClick={onExport}
          className="rounded border px-3 py-1 text-sm disabled:opacity-50"
        >
          导出 Markdown
        </button>
      </div>
      {exportPath && <p>{exportPath}</p>}
    </div>
  );
}
