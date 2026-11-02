import { describe, expect, it, vi } from "vitest";

import { createModelStore } from "@/core/models/store";
import type { Provider } from "@/core/models/types";
import type { ApiClient } from "@/lib/api";

const provider = (overrides: Partial<Provider> = {}): Provider => ({
  id: "p1",
  type: "openai",
  name: "OpenAI",
  endpoint: null,
  secret_name: null,
  has_secret: false,
  enabled: true,
  timeout_seconds: 60,
  rate_limit_rpm: null,
  paid: true,
  created_at: "",
  ...overrides,
});

function setup(overrides: Partial<ApiClient> = {}) {
  const client = {
    providerTypes: vi.fn(async () => []),
    secretStatus: vi.fn(async () => ({ backend: "keychain" })),
    listProviders: vi.fn(async () => [provider()]),
    listModels: vi.fn(async () => []),
    createProvider: vi.fn(async () => provider()),
    updateProvider: vi.fn(async () => provider()),
    deleteProvider: vi.fn(async () => undefined),
    storeSecret: vi.fn(async () => undefined),
    deleteSecret: vi.fn(async () => undefined),
    testModel: vi.fn(async () => ({ ok: true })),
    ...overrides,
  } as unknown as ApiClient;
  return { store: createModelStore(client), client };
}

describe("model store", () => {
  it("keeps the key out of the provider and clears it from state", async () => {
    const { store, client } = setup();
    await store.getState().addProvider({
      type: "openai",
      name: "OpenAI",
      endpoint: "",
      apiKey: "sk-secret",
    });
    expect(client.createProvider).toHaveBeenCalledWith({ type: "openai", name: "OpenAI" });
    expect(client.storeSecret).toHaveBeenCalledWith("provider.p1", "sk-secret");
    expect(client.updateProvider).toHaveBeenCalledWith("p1", { secret_name: "provider.p1" });
    expect(JSON.stringify(store.getState())).not.toContain("sk-secret");
  });

  it("stores nothing for a provider without a key", async () => {
    const { store, client } = setup();
    await store.getState().addProvider({ type: "ollama", name: "L", endpoint: "", apiKey: "" });
    expect(client.storeSecret).not.toHaveBeenCalled();
  });

  it("reports a refused provider and stays open", async () => {
    const { store } = setup({
      createProvider: vi.fn(async () => Promise.reject(new Error("name taken"))),
    });
    const added = await store
      .getState()
      .addProvider({ type: "ollama", name: "L", endpoint: "", apiKey: "" });
    expect(added).toBe(false);
    expect(store.getState().error).toBe("name taken");
  });

  it("removes the provider's own key with it", async () => {
    const { store, client } = setup({
      listProviders: vi.fn(async () => [provider({ secret_name: "provider.p1" })]),
    });
    await store.getState().load();
    await store.getState().removeProvider("p1");
    expect(client.deleteSecret).toHaveBeenCalledWith("provider.p1");
  });

  it("does not delete a shared key it does not own", async () => {
    const { store, client } = setup({
      listProviders: vi.fn(async () => [provider({ secret_name: "team.key" })]),
    });
    await store.getState().load();
    await store.getState().removeProvider("p1");
    expect(client.deleteSecret).not.toHaveBeenCalled();
  });

  it("forwards paid confirmation only when given", async () => {
    const { store, client } = setup();
    await store.getState().testModel("m", false);
    expect(client.testModel).toHaveBeenLastCalledWith("m", false);
  });
});
