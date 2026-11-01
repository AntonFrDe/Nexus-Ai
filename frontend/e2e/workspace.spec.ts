import { expect, test, type Page } from "@playwright/test";

const tabs = (page: Page) => page.getByRole("navigation", { name: "Workspaces" });
const dockTab = (page: Page, name: string) => page.locator(".dv-tab", { hasText: name });
const saved = (page: Page) =>
  expect(page.getByTestId("save-status")).toHaveText("All changes saved");

async function openWorkspace(page: Page, name: string) {
  await tabs(page).getByRole("button", { name, exact: true }).click();
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(tabs(page).getByRole("button")).not.toHaveCount(0);
});

test("default layouts render real panels", async ({ page }) => {
  await openWorkspace(page, "Workflow Builder");
  await expect(dockTab(page, "Workflow Canvas")).toBeVisible();
  await expect(dockTab(page, "Node Inspector")).toBeVisible();
  await openWorkspace(page, "Custom Workspace");
  await expect(dockTab(page, "Workspaces")).toBeVisible();
});

test("a closed panel stays closed after reload and reset brings it back", async ({ page }) => {
  await openWorkspace(page, "Analytics");
  const tab = dockTab(page, "Executions");
  await tab.hover();
  await tab.locator(".dv-default-tab-action").click();
  await saved(page);
  await page.reload();
  await expect(dockTab(page, "Cost Analytics")).toBeVisible();
  await expect(tab).toHaveCount(0);
  await page.getByRole("button", { name: "Reset layout" }).click();
  await expect(tab).toBeVisible();
});

test("dragged tab placement survives a reload", async ({ page }) => {
  await openWorkspace(page, "Agent Development");
  const source = await dockTab(page, "Notes").boundingBox();
  const target = await dockTab(page, "Agents").boundingBox();
  await page.mouse.move(source!.x + 10, source!.y + 10);
  await page.mouse.down();
  await page.mouse.move(target!.x + 40, target!.y + 10, { steps: 10 });
  await page.mouse.up();
  await saved(page);
  const group = () =>
    page.locator(".dv-groupview", { has: dockTab(page, "Agents") }).locator(".dv-tab");
  await expect(group()).toHaveCount(2);
  await page.reload();
  await expect(group()).toHaveCount(2);
});

test("floating groups persist", async ({ page }) => {
  await openWorkspace(page, "Execution Monitor");
  await page.getByRole("button", { name: "Float group" }).first().click();
  await expect(page.locator(".dv-resize-container")).toHaveCount(1);
  await saved(page);
  await page.reload();
  await expect(page.locator(".dv-resize-container")).toHaveCount(1);
  await page.getByRole("button", { name: "Dock back into the layout" }).click();
  await expect(page.locator(".dv-resize-container")).toHaveCount(0);
});

test("maximize and restore a group", async ({ page }) => {
  await openWorkspace(page, "Debug Studio");
  await page.getByRole("button", { name: "Maximize group" }).first().click();
  await page.getByRole("button", { name: "Restore group" }).first().click();
  await expect(page.getByRole("button", { name: "Maximize group" }).first()).toBeVisible();
});

test("a group opens in its own window", async ({ page, context }) => {
  await openWorkspace(page, "Debug Studio");
  const popup = context.waitForEvent("page");
  await page.getByRole("button", { name: "Open group in a new window" }).first().click();
  await expect((await popup).locator(".dv-tab").first()).toBeVisible();
  await (await popup).close();
});

test("panel library toggles panels", async ({ page }) => {
  await openWorkspace(page, "Custom Workspace");
  const status = page.getByRole("checkbox", { name: "System Status" });
  await status.check();
  await expect(dockTab(page, "System Status")).toBeVisible();
  await status.uncheck();
  await expect(dockTab(page, "System Status")).toHaveCount(0);
});

test("create, restart-restore, duplicate and delete a workspace", async ({ page }) => {
  await openWorkspace(page, "Custom Workspace");
  await page.getByRole("button", { name: "New", exact: true }).click();
  await page.getByLabel("Name").fill("Mine");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(tabs(page).getByRole("button", { name: "Mine", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );

  await page.getByRole("checkbox", { name: "Notes" }).check();
  await dockTab(page, "Notes").click();
  await page.getByLabel("Workspace notes").fill("remember this");
  await saved(page);
  await page.reload();
  await expect(tabs(page).getByRole("button", { name: "Mine", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await dockTab(page, "Notes").click();
  await expect(page.getByLabel("Workspace notes")).toHaveValue("remember this");

  await dockTab(page, "Workspaces").click();
  await page.getByRole("button", { name: "Duplicate Mine" }).click();
  await expect(tabs(page).getByRole("button", { name: "Mine copy" })).toBeVisible();
  await page.getByText("Mine copy", { exact: true }).last().hover();
  await page.getByRole("button", { name: "Delete Mine copy" }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(tabs(page).getByRole("button", { name: "Mine copy" })).toHaveCount(0);
});

test("export then import reproduces a workspace", async ({ page }) => {
  await openWorkspace(page, "Custom Workspace");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export Analytics" }).click({ force: true });
  const file = await (await download).path();
  await page.getByLabel("Import workspace file").setInputFiles({
    name: "analytics.nexus.json",
    mimeType: "application/json",
    buffer: (await import("node:fs")).readFileSync(file),
  });
  await expect(tabs(page).getByRole("button", { name: "Analytics" })).toHaveCount(2);
});

test("a new workspace can start from a preset", async ({ page }) => {
  await openWorkspace(page, "Custom Workspace");
  await page.getByRole("button", { name: "New", exact: true }).click();
  await page.getByLabel("Name").fill("Costs");
  await page.getByLabel("Starting layout").selectOption("analytics");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(dockTab(page, "Cost Analytics")).toBeVisible();
});

test("accent preference survives a reload", async ({ page }) => {
  await openWorkspace(page, "Custom Workspace");
  await page.getByRole("checkbox", { name: "Appearance" }).check();
  await page.getByRole("radio", { name: "teal" }).check();
  await expect(page.locator("html")).toHaveAttribute("data-accent", "teal");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-accent", "teal");
  await page.getByRole("checkbox", { name: "Appearance" }).uncheck();
});
