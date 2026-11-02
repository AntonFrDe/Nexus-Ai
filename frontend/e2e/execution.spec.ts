import os from "node:os";

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const dockTab = (page: Page, name: string) =>
  page.locator(".dv-tab", { hasText: new RegExp(`^${name}$`) });
const tabs = (page: Page) => page.getByRole("navigation", { name: "Workspaces" });
const panel = (page: Page) => page.getByRole("tabpanel", { name: "Executions" });
const status = (page: Page, value: string) => panel(page).locator(`.panel-heading .run-status`).filter({ hasText: value });

const node = (id: string, type: string, config = {}) => ({
  id,
  type: `core.${type}`,
  position: { x: 0, y: 0 },
  config,
});
const edge = (source: string, target: string, source_port = "out") => ({
  id: `${source}-${target}`,
  source,
  source_port,
  target,
  target_port: "in",
});

async function seed(
  request: APIRequestContext,
  name: string,
  nodes: ReturnType<typeof node>[],
  edges: ReturnType<typeof edge>[],
) {
  const created = await (await request.post("/api/workflows", { data: { name } })).json();
  const saved = await request.put(`/api/workflows/${created.id}`, { data: { name, nodes, edges } });
  expect(saved.ok()).toBe(true);
}

async function openWorkflow(page: Page, name: string) {
  await page.goto("/advanced");
  await tabs(page).getByRole("button", { name: "Workflow Builder" }).click();
  await page.getByRole("button", { name: "Reset layout" }).click();
  await dockTab(page, "Workflows").click();
  await page.locator(".row-main", { hasText: name }).last().click();
  await expect(page.getByLabel("Workflow name")).toHaveValue(name);
  await expect(page.locator(".react-flow__node").first()).toBeVisible();
}

async function run(page: Page, input?: string) {
  await page.getByRole("button", { name: "Run", exact: true }).click();
  if (input) await page.getByLabel("Run input as JSON").fill(input);
  await page.getByRole("button", { name: "Start" }).click();
  await expect(panel(page)).toBeVisible();
}

test("a real workflow runs, reports outputs and marks the canvas", async ({ page, request }) => {
  await seed(
    request,
    "Runs",
    [
      node("in", "input"),
      node("branch", "if_else", { expression: "score > 0.5" }),
      node("yes", "output", { name: "passed" }),
      node("no", "output", { name: "failed" }),
    ],
    [edge("in", "branch"), edge("branch", "yes", "true"), edge("branch", "no", "false")],
  );
  await openWorkflow(page, "Runs");
  await run(page, '{"score": 0.9}');
  await expect(status(page, "COMPLETED")).toBeVisible();
  await expect(panel(page).getByTestId("json-output")).toContainText('"passed"');

  await expect(page.locator('.flow-node[data-run="completed"]')).toHaveCount(3);
  await expect(page.locator('.flow-node[data-run="skipped"]')).toHaveCount(1);
  await dockTab(page, "Execution Logs").click();
  await expect(page.getByRole("tabpanel", { name: "Execution Logs" })).toContainText("Run is COMPLETED");
});

test("a failure shows which node failed and why", async ({ page, request }) => {
  await seed(
    request,
    "Fails",
    [node("in", "input"), node("parse", "json_parser"), node("out", "output")],
    [edge("in", "parse"), edge("parse", "out")],
  );
  await openWorkflow(page, "Fails");
  await run(page, '"not json"');
  await expect(status(page, "FAILED")).toBeVisible();
  await expect(panel(page).getByRole("alert").first()).toContainText("parse:");
  await expect(page.locator('.flow-node[data-run="failed"]')).toHaveCount(1);
});

test("human approval pauses the run until a person decides", async ({ page, request }) => {
  await seed(
    request,
    "Approve",
    [
      node("in", "input"),
      node("ask", "human_approval", { prompt: "Ship it?" }),
      node("yes", "output", { name: "shipped" }),
      node("no", "output", { name: "held" }),
    ],
    [edge("in", "ask"), edge("ask", "yes", "approved"), edge("ask", "no", "rejected")],
  );
  await openWorkflow(page, "Approve");
  await run(page, '"draft"');
  await expect(panel(page).getByText("Ship it?")).toBeVisible();
  await expect(page.locator('.flow-node[data-run="waiting"]')).toHaveCount(1);

  await page.reload();
  await dockTab(page, "Executions").click();
  await panel(page).locator(".execution-row", { hasText: "Approve" }).first().click();
  await panel(page).getByRole("button", { name: "Approve", exact: true }).click();
  await expect(status(page, "COMPLETED")).toBeVisible();
  await expect(panel(page).getByTestId("json-output")).toContainText("shipped");
});

test("pause, resume and cancel a long run", async ({ page, request }) => {
  await seed(
    request,
    "Slow",
    [
      node("in", "input"),
      node("one", "delay", { seconds: 1 }),
      node("two", "delay", { seconds: 60 }),
      node("out", "output"),
    ],
    [edge("in", "one"), edge("one", "two"), edge("two", "out")],
  );
  await openWorkflow(page, "Slow");
  await run(page);
  await panel(page).getByRole("button", { name: "Pause" }).click();
  await expect(status(page, "PAUSED")).toBeVisible({ timeout: 5000 });
  await panel(page).getByRole("button", { name: "Resume" }).click();
  await expect(status(page, "RUNNING")).toBeVisible();
  await panel(page).getByRole("button", { name: "Cancel" }).click();
  await expect(status(page, "CANCELLED")).toBeVisible();
});

test("nodes without an implementation are refused with a reason", async ({ page, request }) => {
  await seed(
    request,
    "Unimplemented node",
    [node("in", "input"), node("agent", "coding_agent", { model: "local", workspace_path: "/tmp" })],
    [edge("in", "agent")],
  );
  await openWorkflow(page, "Unimplemented node");
  await run(page);
  await expect(panel(page)).toContainText("cannot run yet");
});

test("the proxy refuses cross-site callers and the API refuses direct ones", async ({ request }) => {
  const crossSite = await request.get("/api/workflows", {
    headers: { Origin: "https://evil.example" },
  });
  expect(crossSite.status()).toBe(403);
  const rebound = await request.get("/api/workflows", { headers: { Host: "evil.example" } });
  expect(rebound.status()).toBe(403);
  const direct = await request.get("http://127.0.0.1:8100/api/workflows");
  expect(direct.status()).toBe(401);
  expect((await request.get("/api/workflows")).ok()).toBe(true);
});

test("the frontend cannot be reached from the local network", async () => {
  const addresses = Object.values(os.networkInterfaces())
    .flat()
    .filter((item) => item && !item.internal && item.family === "IPv4")
    .map((item) => item!.address);
  test.skip(addresses.length === 0, "This machine has no network address to test");
  for (const address of addresses) {
    // A spoofed Host header is what used to get a remote caller past the proxy.
    const attempt = fetch(`http://${address}:3100/api/workflows`, {
      headers: { Host: "localhost:3100" },
      signal: AbortSignal.timeout(2000),
    });
    await expect(attempt).rejects.toThrow();
  }
});
