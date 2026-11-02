import { expect, test, type Page } from "@playwright/test";

const FAKE = "http://127.0.0.1:11999";
const panel = (page: Page) => page.getByRole("tabpanel", { name: "Agents" });
const dockTab = (page: Page, name: string) =>
  page.locator(".dv-tab", { hasText: new RegExp(`^${name}$`) });

async function openAgents(page: Page) {
  const name = `Agents ${crypto.randomUUID().slice(0, 8)}`;
  await page.request.post("/api/workspaces", { data: { name, preset: "custom" } });
  await page.goto("/");
  const tab = page.getByRole("navigation", { name: "Workspaces" }).getByRole("button", { name });
  await tab.click();
  await expect(tab).toHaveAttribute("aria-current", "page");
  await expect(dockTab(page, "Panels")).toBeVisible();
  await page.getByRole("checkbox", { name: "Agents", exact: true }).check();
  await dockTab(page, "Agents").click();
}

test("create, version, restore and clone an agent", async ({ page }) => {
  await openAgents(page);
  await panel(page).getByRole("button", { name: "Agent", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name").fill("Reviewer one");
  await dialog.getByLabel("Template").selectOption("reviewer");
  await dialog.getByRole("button", { name: "Create" }).click();
  await expect(panel(page).getByLabel("System prompt")).toHaveValue(/Review independently/);

  await panel(page).getByLabel("System prompt").fill("Changed prompt");
  await panel(page).getByLabel("Agent name").fill("Reviewer renamed");
  await panel(page).getByLabel("System prompt").click();
  await expect(panel(page).getByLabel("System prompt")).toHaveValue("Changed prompt");
  await panel(page).getByRole("button", { name: "Save version" }).click();
  await expect(panel(page).getByRole("button", { name: "Reviewer renamed" })).toBeVisible();
  await panel(page).getByLabel("Agent name").fill("Reviewer one");
  await panel(page).getByRole("button", { name: "Save version" }).click();
  await expect(panel(page).locator(".panel-heading .badge")).toHaveText("v3");

  await panel(page).getByRole("button", { name: "Restore agent version 1" }).click();
  await expect(panel(page).getByLabel("System prompt")).toHaveValue(/Review independently/);
  await panel(page).getByRole("button", { name: "Clone" }).click();
  await expect(panel(page).getByRole("button", { name: "Reviewer one copy" })).toBeVisible();
});

test("runtimes state their capabilities, and a key is never shown back", async ({ page }) => {
  await openAgents(page);
  const row = panel(page).locator(".runtime-row", { hasText: "Claude Agent SDK" });
  await expect(row).toContainText("paid");
  await row.getByLabel("Claude Agent SDK API key").fill("e2e-not-a-real-key");
  await row.getByRole("button", { name: "Save key" }).click();
  await expect(row.getByLabel("Claude Agent SDK API key")).toHaveAttribute("placeholder", /Key stored/);
  await expect(row.getByLabel("Claude Agent SDK API key")).toHaveValue("");
});

test("a workflow runs an agent and shows which model answered", async ({ page, request }) => {
  const provider = await (
    await request.post("/api/providers", {
      data: { type: "ollama", name: "Agent local", endpoint: FAKE },
    })
  ).json();
  await request.post(`/api/providers/${provider.id}/discover`);
  const agent = await (
    await request.post("/api/agents", { data: { name: "Runner", template: "summarizer" } })
  ).json();
  await request.patch(`/api/agents/${agent.id}`, {
    data: { definition: { ...agent.definition, model: "Agent local/local-coder:latest" } },
  });
  const workflow = await (
    await request.post("/api/workflows", { data: { name: "Agent run" } })
  ).json();
  const at = { x: 0, y: 0 };
  await request.put(`/api/workflows/${workflow.id}`, {
    data: {
      name: "Agent run",
      nodes: [
        { id: "in", type: "core.input", position: at },
        { id: "c", type: "core.custom_agent", position: at, config: { agent_id: agent.id } },
        { id: "out", type: "core.output", position: at },
      ],
      edges: [
        { id: "a", source: "in", source_port: "out", target: "c", target_port: "in" },
        { id: "b", source: "c", source_port: "out", target: "out", target_port: "in" },
      ],
    },
  });

  await page.goto("/");
  await page.getByRole("navigation", { name: "Workspaces" }).getByRole("button", { name: "Workflow Builder" }).click();
  await page.getByRole("button", { name: "Reset layout" }).click();
  await dockTab(page, "Workflows").click();
  await page.locator(".row-main", { hasText: "Agent run" }).click();
  await expect(page.getByLabel("Workflow name")).toHaveValue("Agent run");
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await page.getByLabel("Run input as JSON").fill('"long text"');
  await page.getByRole("button", { name: "Start" }).click();
  const runs = page.getByRole("tabpanel", { name: "Executions" });
  await expect(runs.locator(".panel-heading .run-status")).toHaveText("COMPLETED", { timeout: 20_000 });
  await expect(runs.locator(".node-rows")).toContainText("local-coder");
  await expect(runs.getByTestId("json-output")).toContainText("ready");
});
