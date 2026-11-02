import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const FAKE = "http://127.0.0.1:11999";

async function ensureModel(request: APIRequestContext) {
  const models = await (await request.get("/api/models")).json();
  if (models.some((item: { provider_name: string }) => item.provider_name === "Chat local")) return;
  const provider = await (
    await request.post("/api/providers", {
      data: { type: "ollama", name: "Chat local", endpoint: FAKE },
    })
  ).json();
  await request.post(`/api/providers/${provider.id}/discover`);
  await request.put("/api/settings/chat_model", {
    data: { value: "Chat local/local-coder:latest" },
  });
}

async function createProject(page: Page, name: string) {
  await page.goto("/");
  await page.getByRole("button", { name: "Nouveau projet" }).click();
  await page.getByLabel("Nom").fill(name);
  await page.getByRole("button", { name: "Créer", exact: true }).click();
  await expect(page.getByRole("region", { name: "Conversation" })).toBeVisible();
}

test.beforeEach(async ({ request }) => {
  await ensureModel(request);
});

test("create a project and talk to the assistant", async ({ page }) => {
  await createProject(page, "Projet discussion");
  await page.getByLabel("Ton message").fill("Bonjour");
  await page.getByLabel("Ton message").press("Enter");
  await expect(page.getByText("Bonjour, je suis prêt.")).toBeVisible();

  await page.reload();
  await expect(page.getByText("Bonjour, je suis prêt.")).toBeVisible();
  await page.getByRole("link", { name: "Projets" }).click();
  await expect(page.getByRole("link", { name: /Projet discussion/ })).toContainText("2 messages");
});

test("a proposal becomes results and agents only after approval", async ({ page, request }) => {
  await createProject(page, "Projet roadmap");
  await page.getByRole("button", { name: "Fais-moi une roadmap pour ce projet" }).click();
  await expect(page.getByText("Plan e2e")).toBeVisible();
  await expect(page.getByText("nexus-proposal")).toHaveCount(0);
  const results = page.getByRole("complementary", { name: "Résultats" });
  await expect(results).toContainText("apparaîtra ici");

  await page.getByRole("button", { name: "Valider" }).click();
  await expect(results).toContainText("Plan e2e");
  await expect(results).toContainText("Agent e2e");
  await expect(page.getByText("Validée et ajoutée aux résultats")).toBeVisible();
  const agents = await (await request.get("/api/agents")).json();
  expect(agents.some((agent: { name: string }) => agent.name === "Agent e2e")).toBe(true);
});

test("a refused proposal creates nothing", async ({ page }) => {
  await createProject(page, "Projet refus");
  await page.getByLabel("Ton message").fill("Une roadmap stp");
  await page.getByRole("button", { name: "Envoyer" }).click();
  await page.getByRole("button", { name: "Refuser" }).click();
  await expect(page.getByText("Refusée")).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Résultats" })).toContainText("apparaîtra ici");
});

test("deleting a project asks first", async ({ page }) => {
  await createProject(page, "Projet à effacer");
  await page.goto("/");
  await page.getByRole("button", { name: "Supprimer Projet à effacer" }).click({ force: true });
  await page.getByRole("dialog").getByRole("button", { name: "Supprimer" }).click();
  await expect(page.getByRole("link", { name: /Projet à effacer/ })).toHaveCount(0);
});

test("settings show models, and experimental features stay hidden by default", async ({ page, request }) => {
  await request.put("/api/settings/appearance", {
    data: { value: { accent: "amber", density: "compact", experimental: false } },
  });
  await page.goto("/settings");
  await expect(page.getByRole("region", { name: "Modèles" })).toContainText("Chat local");
  await expect(page.getByRole("region", { name: "Agents" }).getByText("Runtimes")).toHaveCount(0);
  await page.goto("/advanced");
  await expect(page.getByRole("button", { name: "Panels" })).toBeVisible();
});
