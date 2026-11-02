import { describe, expect, it, vi } from "vitest";

import { createPluginStore } from "@/core/models/plugin-store";
import type { ApiClient } from "@/lib/api";

function setup(overrides: Partial<ApiClient> = {}) {
  const client = {
    pluginStatus: vi.fn(async () => ({ api_version: "1.0.0", sandbox: true })),
    listPlugins: vi.fn(async () => []),
    installPlugin: vi.fn(async () => undefined),
    enablePlugin: vi.fn(async () => undefined),
    ...overrides,
  } as unknown as ApiClient;
  return { store: createPluginStore(client), client };
}

describe("plugin store", () => {
  it("installing changes nothing that needs a reload", async () => {
    const { store } = setup();
    await store.getState().install("/x");
    expect(store.getState().needsReload).toBe(false);
  });

  it("enabling asks for a reload and sends what was accepted", async () => {
    const { store, client } = setup();
    await store.getState().enable("a", ["network"]);
    expect(client.enablePlugin).toHaveBeenCalledWith("a", ["network"]);
    expect(store.getState().needsReload).toBe(true);
  });

  it("reports a refusal without asking for a reload", async () => {
    const { store } = setup({
      enablePlugin: vi.fn(async () => Promise.reject(new Error("refused"))),
    });
    await store.getState().enable("a", []);
    expect(store.getState().error).toBe("refused");
    expect(store.getState().needsReload).toBe(false);
  });
});
