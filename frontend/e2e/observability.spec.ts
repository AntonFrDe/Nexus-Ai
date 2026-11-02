import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const dockTab = (page: Page, name: string) =>
  page.locator(".dv-tab", { hasText: new RegExp(`^${name}$`) });
const at = { x: 0, y: 0 };
const node = (id: string, type: string, config = {}) => ({
  id,
  type: `core.${type}`,
  position: at,
  config,
});
const edge = (source: string, target: string) => ({
  id: `${source}-${target}`,
  source,
  source_port: "out",
  target,
  target_port: "in",
});

async function seed(request: APIRequestContext, name: string, nodes: object[], edges: object[]) {
  const created = await (await request.post("/api/workflows", { data: { name } })).json();
  await request.put(`/api/workflows/${created.id}`, { data: { name, nodes, edges } });
  return created.id as string;
}

async function openDebug(page: Page) {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Workspaces" }).getByRole("button", { name: "Debug Studio" }).click();
  await page.getByRole("button", { name: "Reset layout" }).click();
  await expect(dockTab(page, "Execution Trace")).toBeVisible();
}

async function run(request: APIRequestContext, id: string, input: unknown, extra = {}) {
  return (
    await request.post(`/api/workflows/${id}/executions`, { data: { input, ...extra } })
  ).json();
}

async function selectRun(page: Page, name: string) {
  await dockTab(page, "Executions").click();
  await page
    .getByRole("tabpanel", { name: "Executions" })
    .locator(".execution-row", { hasText: name })
    .first()
    .click();
}

test("the trace shows which node failed and why", async ({ page, request }) => {
  const id = await seed(
    request,
    "Trace failure",
    [node("in", "input"), { ...node("parse", "json_parser"), label: "Parse reply" }, node("out", "output")],
    [edge("in", "parse"), edge("parse", "out")],
  );
  await run(request, id, "not json");
  await openDebug(page);
  await selectRun(page, "Trace failure");
  const trace = page.getByRole("tabpanel", { name: "Execution Trace" });
  const failure = trace.getByTestId("failure-summary");
  await expect(failure).toContainText("Failed at Parse reply");
  await expect(failure).toContainText("Expecting value");
  await expect(failure).toContainText("not json");
  await expect(trace.getByRole("list", { name: "Node timeline" }).getByRole("button")).toHaveCount(2);
});

test("state can be read between nodes", async ({ page, request }) => {
  const id = await seed(
    request,
    "Trace state",
    [node("in", "input"), node("w", "variable", { name: "kept", operation: "write" }), node("out", "output")],
    [edge("in", "w"), edge("w", "out")],
  );
  await run(request, id, 7);
  await openDebug(page);
  await selectRun(page, "Trace state");
  const trace = page.getByRole("tabpanel", { name: "Execution Trace" });
  await expect(trace.getByTestId("trace-kind")).toHaveText("recorded");
  await trace.getByLabel("Checkpoint").selectOption({ label: "Step 4: before out" });
  await expect(trace.getByTestId("checkpoint-state")).toContainText('"kept": 7');
});

test("step through a run, node by node", async ({ page, request }) => {
  const id = await seed(
    request,
    "Stepped",
    [node("in", "input"), node("log", "logger"), node("out", "output")],
    [edge("in", "log"), edge("log", "out")],
  );
  await run(request, id, "x", { step: true });
  await openDebug(page);
  await selectRun(page, "Stepped");
  const runs = page.getByRole("tabpanel", { name: "Executions" });
  await runs.getByRole("button", { name: "Next step" }).click();
  await expect(runs.getByRole("button", { name: "Next step" })).toBeVisible();
  await runs.getByRole("button", { name: "Run to end" }).click();
  await expect(runs.locator(".panel-heading .run-status")).toHaveText("COMPLETED");
});

test("replay is marked as a replay and can be compared", async ({ page, request }) => {
  const id = await seed(
    request,
    "Replayed",
    [node("in", "input"), node("t", "data_transform", { template: '"one"' }), node("out", "output")],
    [edge("in", "t"), edge("t", "out")],
  );
  const first = await run(request, id, "x");
  await expect.poll(async () => (await (await request.get(`/api/executions/${first.id}`)).json()).status).toBe("COMPLETED");
  const second = await (
    await request.post(`/api/executions/${first.id}/replay`, {
      data: { overrides: { t: { template: '"two"' } } },
    })
  ).json();
  await expect.poll(async () => (await (await request.get(`/api/executions/${second.id}`)).json()).status).toBe("COMPLETED");

  await openDebug(page);
  await selectRun(page, "Replayed");
  const trace = page.getByRole("tabpanel", { name: "Execution Trace" });
  await expect(trace.getByTestId("trace-kind")).toHaveText("replay");
  await trace.getByLabel("Compare with").selectOption({ index: 1 });
  await expect(trace.getByRole("table", { name: "Run comparison" })).toContainText("settings, output");
});

test("cost analytics reports runs and failures", async ({ page, request }) => {
  const id = await seed(request, "Counted", [node("in", "input"), node("p", "json_parser")], [edge("in", "p")]);
  await run(request, id, "bad");
  await page.goto("/");
  await page.getByRole("navigation", { name: "Workspaces" }).getByRole("button", { name: "Analytics" }).click();
  await page.getByRole("button", { name: "Reset layout" }).click();
  const panel = page.getByRole("tabpanel", { name: "Cost Analytics" });
  await expect(panel.getByText("Most frequent errors")).toBeVisible();
  await expect(panel.getByLabel("Period").getByRole("button", { name: "7 days" })).toBeVisible();
  await expect(panel.getByRole("checkbox", { name: "Export finished runs" })).not.toBeChecked();
});
