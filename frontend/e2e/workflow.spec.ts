import fs from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const EXAMPLES = path.join(__dirname, "../../backend/examples");
const tabs = (page: Page) => page.getByRole("navigation", { name: "Workspaces" });
const dockTab = (page: Page, name: string) =>
  page.locator(".dv-tab", { hasText: new RegExp(`^${name}$`) });
const saved = (page: Page) =>
  expect(page.getByTestId("workflow-save-status")).toContainText("All changes saved");
const canvasNodes = (page: Page) => page.locator(".react-flow__node");

async function newWorkflow(page: Page, name: string) {
  await dockTab(page, "Workflows").click();
  await page.getByRole("button", { name: "New", exact: true }).first().click();
  const field = page.getByLabel("Workflow name");
  await expect(field).toHaveValue("Untitled workflow");
  await field.fill(name);
  await saved(page);
}

async function addNode(page: Page, title: string) {
  await dockTab(page, "Node Library").click();
  await page.getByLabel("Search node types").fill(title);
  await page.getByRole("button", { name: title, exact: true }).click();
  await page.getByLabel("Search node types").fill("");
}

async function connect(page: Page, source: string, sourcePort: string, target: string, targetPort: string) {
  const handle = (type: string, port: string, kind: string) =>
    page
      .locator(".react-flow__node", { has: page.getByTestId(`node-core.${type}`) })
      .locator(`.react-flow__handle[data-handleid="${port}"].${kind}`);
  await handle(source, sourcePort, "source").dragTo(handle(target, targetPort, "target"));
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await tabs(page).getByRole("button", { name: "Workflow Builder" }).click();
  await expect(dockTab(page, "Workflow Canvas")).toBeVisible();
});

test("build, configure, save, reload and export a workflow", async ({ page }) => {
  await newWorkflow(page, "My pipeline");
  await addNode(page, "Input");
  await addNode(page, "Delay");
  await addNode(page, "Output");
  await expect(canvasNodes(page)).toHaveCount(3);
  await page.getByRole("button", { name: "Auto layout" }).click();
  await saved(page);

  await connect(page, "input", "out", "delay", "in");
  await connect(page, "delay", "out", "output", "in");
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);

  await page.getByTestId("node-core.delay").locator(".flow-node-title").click();
  await dockTab(page, "Node Inspector").click();
  await page.getByRole("tab", { name: "Config" }).click();
  await page.getByLabel("Seconds", { exact: true }).fill("5");
  await page.getByLabel("Node label").fill("Cooldown");
  await saved(page);

  await dockTab(page, "Problems").click();
  await expect(page.getByText("No problems found.")).toBeVisible();

  await page.reload();
  await expect(canvasNodes(page)).toHaveCount(3);
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);
  await expect(canvasNodes(page).filter({ hasText: "Cooldown" })).toBeVisible();

  await dockTab(page, "Workflows").click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export workflow My pipeline" }).click({ force: true });
  const exported = JSON.parse(fs.readFileSync(await (await download).path(), "utf8"));
  expect(exported.format).toBe("nexus.workflow");
  expect(exported.workflow.nodes).toHaveLength(3);
  expect(exported.workflow.nodes.find((n: { label: string }) => n.label === "Cooldown").config)
    .toEqual({ seconds: 5 });
});

test("backend validation is shown and clears when fixed", async ({ page }) => {
  await newWorkflow(page, "Invalid");
  await addNode(page, "Delay");
  await dockTab(page, "Problems").click();
  const problems = page.getByRole("tabpanel", { name: "Problems" });
  await expect(problems.getByText("Delay: Seconds is required")).toBeVisible();
  await expect(problems.getByText("Delay: Input is not connected")).toBeVisible();

  await problems.getByText("Delay: Seconds is required").click();
  await dockTab(page, "Node Inspector").click();
  await page.getByLabel("Seconds", { exact: true }).fill("1");
  await dockTab(page, "Problems").click();
  await expect(problems.getByText("Delay: Seconds is required")).toHaveCount(0);
});

test("incompatible ports cannot be wired", async ({ page }) => {
  await newWorkflow(page, "Ports");
  await addNode(page, "Memory");
  await addNode(page, "JSON Parser");
  await page.getByRole("button", { name: "Auto layout" }).click();
  await saved(page);
  await connect(page, "memory", "memory", "json_parser", "in");
  await expect(page.locator(".react-flow__edge")).toHaveCount(0);
});

test("undo, redo, duplicate, group and delete", async ({ page }) => {
  await newWorkflow(page, "Editing");
  await addNode(page, "Logger");
  await expect(canvasNodes(page)).toHaveCount(1);
  await page.getByRole("button", { name: "Duplicate selection" }).click();
  await expect(canvasNodes(page)).toHaveCount(2);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(canvasNodes(page)).toHaveCount(1);
  await page.getByRole("button", { name: "Redo" }).click();
  await expect(canvasNodes(page)).toHaveCount(2);

  await canvasNodes(page).first().click();
  await canvasNodes(page).nth(1).click({ modifiers: ["Shift"], force: true });
  await page.getByRole("button", { name: "Group selection" }).click();
  await expect(canvasNodes(page)).toHaveCount(3);
  await saved(page);
  await page.reload();
  await expect(canvasNodes(page)).toHaveCount(3);

  await canvasNodes(page).filter({ hasText: "Group" }).first().click({ position: { x: 4, y: 4 } });
  await page.getByRole("button", { name: "Ungroup" }).click();
  await expect(canvasNodes(page)).toHaveCount(2);

  await canvasNodes(page).first().click();
  await page.keyboard.press("Delete");
  await expect(canvasNodes(page)).toHaveCount(1);
});

test("nodes can be dragged in from the library", async ({ page }) => {
  await newWorkflow(page, "Dragged");
  await dockTab(page, "Node Library").click();
  await page
    .getByRole("button", { name: "Logger", exact: true })
    .dragTo(page.locator(".react-flow__pane"), { targetPosition: { x: 300, y: 200 } });
  await expect(canvasNodes(page)).toHaveCount(1);
});

test("versions restore an earlier state", async ({ page }) => {
  await newWorkflow(page, "Versioned");
  await addNode(page, "Logger");
  await saved(page);
  await dockTab(page, "Workflow Versions").click();
  await page.getByLabel("Version label").fill("one node");
  await page.getByRole("button", { name: "Save version" }).click();
  await expect(page.getByText("v1 · one node")).toBeVisible();

  await addNode(page, "Logger");
  await expect(canvasNodes(page)).toHaveCount(2);
  await saved(page);
  await dockTab(page, "Workflow Versions").click();
  await page.getByRole("button", { name: "Restore version 1" }).click();
  await expect(canvasNodes(page)).toHaveCount(1);
});

test("example workflows import cleanly", async ({ page }) => {
  await dockTab(page, "Workflows").click();
  await page.getByLabel("Import workflow file").setInputFiles(
    path.join(EXAMPLES, "research-summary.nexus.json"),
  );
  await expect(canvasNodes(page)).toHaveCount(6);
  await expect(page.locator(".react-flow__edge")).toHaveCount(5);
  await dockTab(page, "Problems").click();
  await expect(page.getByText("No problems found.")).toBeVisible();
});

test("the code editor runs from the local bundle", async ({ page }) => {
  const external: string[] = [];
  page.on("request", (request) => {
    if (!request.url().startsWith("http://localhost")) external.push(request.url());
  });
  await newWorkflow(page, "Code");
  await addNode(page, "Data Transform");
  await dockTab(page, "Node Inspector").click();
  await expect(page.locator(".monaco-editor")).toBeVisible({ timeout: 20_000 });
  expect(external.filter((url) => url.startsWith("http"))).toEqual([]);
});
