import { expect, test, type Page } from "@playwright/test";

const FAKE = "http://127.0.0.1:11999";
const panel = (page: Page) => page.getByRole("tabpanel", { name: "Model Registry" });

async function openRegistry(page: Page) {
  // Each test gets its own workspace, so the layout it changes cannot reach other tests.
  const name = `Models ${crypto.randomUUID().slice(0, 8)}`;
  await page.request.post("/api/workspaces", { data: { name, preset: "custom" } });
  await page.goto("/");
  const tab = page.getByRole("navigation", { name: "Workspaces" }).getByRole("button", { name });
  await tab.click();
  await expect(tab).toHaveAttribute("aria-current", "page");
  await expect(page.locator(".dv-tab", { hasText: /^Panels$/ })).toBeVisible();
  await page.getByRole("checkbox", { name: "Model Registry" }).check();
  await page.locator(".dv-tab", { hasText: /^Model Registry$/ }).click();
}

async function addProvider(page: Page, type: string, name: string, endpoint: string, key?: string) {
  await panel(page).getByRole("button", { name: "Provider", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Type").selectOption(type);
  await dialog.getByLabel("Name").fill(name);
  await dialog.getByRole("textbox", { name: "Endpoint" }).fill(endpoint);
  if (key) await dialog.getByLabel("API key").fill(key);
  await dialog.getByRole("button", { name: "Add" }).click();
  await expect(panel(page).locator(".panel-heading", { hasText: name })).toBeVisible();
}

test("configure and test a local model", async ({ page }) => {
  await openRegistry(page);
  await addProvider(page, "ollama", "Local e2e", FAKE);
  await panel(page).getByRole("button", { name: "Test connection" }).click();
  await expect(panel(page).getByRole("status")).toContainText("1 models found");
  await panel(page).getByRole("button", { name: "Discover models" }).click();
  await panel(page).getByRole("button", { name: "local-coder:latest" }).click();
  await expect(panel(page).getByLabel("Tool calling")).toBeChecked();

  await panel(page).getByRole("button", { name: "Test model" }).click();
  await expect(panel(page).getByRole("status").last()).toContainText("ready", { timeout: 20_000 });
});

test("an external model needs a key, then confirmation before each paid call", async ({ page }) => {
  const key = "e2e-test-key";
  const leaked: string[] = [];
  page.on("response", async (response) => {
    if (!response.url().includes("/api/")) return;
    if (response.headers()["content-type"]?.includes("event-stream")) return;
    const text = await response.text().catch(() => "");
    if (text.includes(key)) leaked.push(response.url());
  });
  await openRegistry(page);
  await addProvider(page, "openai_compatible", "Hosted e2e", `${FAKE}/v1`, key);
  await panel(page).getByRole("button", { name: "Discover models" }).click();
  await panel(page).getByRole("button", { name: "hosted-model" }).click();

  await panel(page).getByRole("button", { name: "Test model" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("billed");
  await dialog.getByRole("button", { name: "Send" }).click();
  await expect(panel(page).getByRole("status").last()).toContainText("ready", { timeout: 20_000 });

  await page.reload();
  await page.locator(".dv-tab", { hasText: /^Model Registry$/ }).click();
  await panel(page).getByRole("button", { name: "Hosted e2e" }).click();
  await expect(panel(page).getByLabel("API key")).toHaveValue("");
  expect(leaked).toEqual([]);
});

test("a wrong key is reported, and an unreachable local server leaves the app usable", async ({ page }) => {
  await openRegistry(page);
  await addProvider(page, "openai_compatible", "Wrong key", `${FAKE}/v1`, "not-the-key");
  await panel(page).getByRole("button", { name: "Test connection" }).click();
  await expect(panel(page).getByRole("status")).toContainText("401");

  await addProvider(page, "ollama", "Stopped", "http://127.0.0.1:1");
  await panel(page).getByRole("button", { name: "Test connection" }).click();
  await expect(panel(page).getByRole("status")).toContainText("Cannot reach");
});

test("registered models are suggested in the node inspector", async ({ page, request }) => {
  const created = await (await request.post("/api/workflows", { data: { name: "Picker" } })).json();
  await request.put(`/api/workflows/${created.id}`, {
    data: {
      name: "Picker",
      nodes: [{ id: "m", type: "core.model_selector", position: { x: 0, y: 0 }, config: {} }],
      edges: [],
    },
  });
  const provider = await (
    await request.post("/api/providers", { data: { type: "ollama", name: "Picker local", endpoint: FAKE } })
  ).json();
  await request.post(`/api/providers/${provider.id}/discover`);

  await page.goto("/");
  await page.getByRole("navigation", { name: "Workspaces" }).getByRole("button", { name: "Workflow Builder" }).click();
  await page.getByRole("button", { name: "Reset layout" }).click();
  await page.locator(".dv-tab", { hasText: /^Workflows$/ }).click();
  await page.locator(".row-main", { hasText: "Picker" }).click();
  await page.getByTestId("node-core.model_selector").locator(".flow-node-title").click();
  await page.locator(".dv-tab", { hasText: /^Node Inspector$/ }).click();
  await expect(page.locator('datalist option[value="Picker local/local-coder:latest"]')).toHaveCount(1);
});
