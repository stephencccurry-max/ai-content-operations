import { expect, test } from "@playwright/test";

const INTERNAL_TOKEN =
  process.env.INTERNAL_API_TOKEN ?? "change-me-in-local-env";

/** WF-01 webhook when n8n is up; otherwise same HTTP sequence as pipeline contract tests. */
async function triggerPipeline(
  request: import("@playwright/test").APIRequestContext,
  taskId: string,
) {
  let webhookOk = false;
  try {
    const webhook = await request.post("http://127.0.0.1:5678/webhook/wf01", {
      data: { task_id: taskId, platforms: ["xiaohongshu"] },
    });
    webhookOk = webhook.ok();
  } catch {
    // n8n not running — fall back to internal HTTP sequence below
  }
  if (webhookOk) return;

  const runRes = await request.post(
    `http://127.0.0.1:8000/internal/v1/tasks/${taskId}/runs`,
    {
      headers: {
        "X-Internal-Token": INTERNAL_TOKEN,
        "Content-Type": "application/json",
      },
      data: { n8n_execution_id: "e2e-smoke" },
    },
  );
  expect(runRes.ok()).toBeTruthy();
  const runId = (await runRes.json()).id as string;

  const stepRes = await request.post(
    `http://127.0.0.1:8000/internal/v1/runs/${runId}/steps/generate_xiaohongshu/start`,
    { headers: { "X-Internal-Token": INTERNAL_TOKEN } },
  );
  expect(stepRes.ok()).toBeTruthy();
  const attempt = (await stepRes.json()).attempt as number;

  await request.post(
    `http://127.0.0.1:8000/internal/v1/tasks/${taskId}/generate/xiaohongshu`,
    { headers: { "X-Internal-Token": INTERNAL_TOKEN } },
  );
  await request.post(
    `http://127.0.0.1:8000/internal/v1/runs/${runId}/steps/generate_xiaohongshu/complete`,
    {
      headers: {
        "X-Internal-Token": INTERNAL_TOKEN,
        "Content-Type": "application/json",
      },
      data: { attempt },
    },
  );
  await request.post(
    `http://127.0.0.1:8000/internal/v1/runs/${runId}/finish`,
    {
      headers: {
        "X-Internal-Token": INTERNAL_TOKEN,
        "Content-Type": "application/json",
      },
      data: { status: "succeeded" },
    },
  );
}

test("从创建任务到导出 Markdown 的完整闭环", async ({ page, request }) => {
  await page.goto("/tasks/new");
  await page.getByPlaceholder("主题（5-300 字）").fill("咖啡因如何影响睡眠质量");
  await page.getByPlaceholder("目标受众").fill("熬夜上班族");
  await page.getByRole("button", { name: "创建并开始生成" }).click();

  await expect(page).toHaveURL(/\/tasks\/[0-9a-f-]{36}/);
  const taskId = page.url().split("/").pop()!;

  await triggerPipeline(request, taskId);

  await expect(page.getByText("状态：awaiting_review")).toBeVisible({
    timeout: 30000,
  });
  await page.getByRole("button", { name: "批准当前版本" }).click();
  await page.getByRole("button", { name: "导出 Markdown" }).click();
  await expect(page.getByText(/\.md$/)).toBeVisible();
});
