import { describe, expect, it, vi } from "vitest";

import { createAgentStore } from "@/core/models/agent-store";
import type { ApiClient } from "@/lib/api";

const agent = { id: "a", name: "A", version: 1, template: null, definition: {}, created_at: "", updated_at: "" };

function setup(overrides: Partial<ApiClient> = {}) {
  const client = {
    agentTemplates: vi.fn(async () => []),
    agentFields: vi.fn(async () => []),
    listRuntimes: vi.fn(async () => []),
    listAgents: vi.fn(async () => [agent]),
    createAgent: vi.fn(async () => agent),
    updateAgent: vi.fn(async () => agent),
    listAgentVersions: vi.fn(async () => []),
    storeSecret: vi.fn(async () => undefined),
    configureRuntime: vi.fn(async () => undefined),
    ...overrides,
  } as unknown as ApiClient;
  return { store: createAgentStore(client), client };
}

describe("agent store", () => {
  it("selects a newly created agent", async () => {
    const { store } = setup();
    await store.getState().create("A", "planner");
    expect(store.getState().selected).toBe("a");
  });

  it("stores a runtime key under its own name and keeps it out of state", async () => {
    const { store, client } = setup();
    await store.getState().setRuntimeKey("claude-agent-sdk", "sk-secret");
    expect(client.storeSecret).toHaveBeenCalledWith("runtime.claude-agent-sdk", "sk-secret");
    expect(client.configureRuntime).toHaveBeenCalledWith("claude-agent-sdk", {
      secret_name: "runtime.claude-agent-sdk",
    });
    expect(JSON.stringify(store.getState())).not.toContain("sk-secret");
  });

  it("reports a failure", async () => {
    const { store } = setup({ listAgents: vi.fn(async () => Promise.reject(new Error("down"))) });
    await store.getState().load();
    expect(store.getState().error).toBe("down");
  });
});
