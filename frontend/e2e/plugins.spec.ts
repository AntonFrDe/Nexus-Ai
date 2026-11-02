import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const EXAMPLES = path.join(__dirname, "../../examples/plugins");
const dockTab = (page: Page, name: string) =>
  page.locator(".dv-tab", { hasText: new RegExp(`^${name}$`) });
const panel = (page: Page) => page.getByRole("tabpanel", { name: "Plugins" });

async function openPlugins(page: Page) {
  const name = `Plugins ${crypto.randomUUID().slice(0, 8)}`;
  await page.request.post("/api/workspaces", { data: { name, preset: "custom" } });
  await page.goto("/");
  const tab = page.getByRole("navigation", { name: "Workspaces" }).getByRole("button", { name });
  await tab.click();
  await expect(tab).toHaveAttribute("aria-current", "page");
  await expect(dockTab(page, "Panels")).toBeVisible();
  await page.getByRole("checkbox", { name: "Plugins", exact: true }).check();
  await dockTab(page, "Plugins").click();
  return name;
}

async function installAndEnable(page: Page, folder: string, name: string) {
  await panel(page).getByLabel("Plugin folder").fill(path.join(EXAMPLES, folder));
  await panel(page).getByRole("button", { name: "Install", exact: true }).click();
  const row = panel(page).locator(".runtime-row", { hasText: name });
  await row.getByRole("button", { name: "Enable" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Enable" }).click();
  await expect(row).toContainText("enabled");
}

test("an example plugin adds a working panel that cannot reach the API", async ({ page }) => {
  await openPlugins(page);
  await installAndEnable(page, "clock-panel", "Session Clock");
  await panel(page).getByRole("button", { name: "Reload to apply changes" }).click();

  await page.getByRole("checkbox", { name: "Session Clock" }).check();
  await dockTab(page, "Session Clock").click();
  const frame = page.frameLocator('iframe[title="Session Clock"]');
  await expect(frame.locator("#workspace")).toContainText("Plugins ");
  await expect(frame.locator("#api")).toHaveText("API blocked");
  await frame.getByRole("button", { name: "Add one" }).click();
  await expect(frame.locator("#count")).toHaveText("1");
  await expect(page.getByTestId("save-status")).toHaveText("All changes saved");

  await page.reload();
  await dockTab(page, "Session Clock").click();
  await expect(page.frameLocator('iframe[title="Session Clock"]').locator("#count")).toHaveText("1");
});

test("an example plugin adds a node that runs in a workflow", async ({ page, request }) => {
  await openPlugins(page);
  await installAndEnable(page, "word-count", "Word Count");
  await panel(page).getByRole("button", { name: "Reload to apply changes" }).click();
  await expect(panel(page)).toBeVisible();

  const workflow = await (await request.post("/api/workflows", { data: { name: "Plugin run" } })).json();
  const at = { x: 0, y: 0 };
  await request.put(`/api/workflows/${workflow.id}`, {
    data: {
      name: "Plugin run",
      nodes: [
        { id: "in", type: "core.input", position: at },
        { id: "w", type: "com.nexus-examples.word-count.count", position: at },
        { id: "out", type: "core.output", position: at },
      ],
      edges: [
        { id: "a", source: "in", source_port: "out", target: "w", target_port: "in" },
        { id: "b", source: "w", source_port: "short", target: "out", target_port: "in" },
      ],
    },
  });
  await page.goto("/");
  await page.getByRole("navigation", { name: "Workspaces" }).getByRole("button", { name: "Workflow Builder" }).click();
  await page.getByRole("button", { name: "Reset layout" }).click();
  await dockTab(page, "Node Library").click();
  await page.getByLabel("Search node types").fill("Word Count");
  await expect(page.getByRole("button", { name: "Word Count", exact: true })).toBeVisible();
  await dockTab(page, "Workflows").click();
  await page.locator(".row-main", { hasText: "Plugin run" }).click();
  await expect(page.getByLabel("Workflow name")).toHaveValue("Plugin run");
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await page.getByLabel("Run input as JSON").fill('"one two three"');
  await page.getByRole("button", { name: "Start" }).click();
  const runs = page.getByRole("tabpanel", { name: "Executions" });
  await expect(runs.locator(".panel-heading .run-status")).toHaveText("COMPLETED", { timeout: 20_000 });
  await expect(runs.getByTestId("json-output")).toContainText('"count": 3');
});

test("permissions are shown before enabling, and bad folders are refused", async ({ page }) => {
  await openPlugins(page);
  await panel(page).getByLabel("Plugin folder").fill("/no/such/folder");
  await panel(page).getByRole("button", { name: "Install", exact: true }).click();
  await expect(panel(page).getByRole("alert")).toContainText("is not a folder");
  await panel(page).getByLabel("Plugin folder").fill(path.join(EXAMPLES, "openai-preset"));
  await panel(page).getByRole("button", { name: "Install", exact: true }).click();
  const row = panel(page).locator(".runtime-row", { hasText: "Local Gateway Preset" });
  await row.getByRole("button", { name: "Enable" }).click();
  await expect(page.getByRole("dialog")).toContainText("no permissions");
  await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
  await row.getByRole("button", { name: "Uninstall" }).click();
  await expect(row).toHaveCount(0);
});

test("a cross-origin caller with a null origin is refused by the proxy", async ({ request }) => {
  const response = await request.get("/api/workflows", { headers: { Origin: "null" } });
  expect(response.status()).toBe(403);
});
