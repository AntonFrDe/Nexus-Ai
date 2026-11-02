import { createStore, type StoreApi } from "zustand/vanilla";

import type { Agent, AgentTemplate, AgentVersion, Runtime } from "@/core/models/agent-types";
import type { FieldSpec } from "@/core/workflow/types";
import type { ApiClient } from "@/lib/api";

export interface AgentState {
  agents: Agent[];
  templates: AgentTemplate[];
  fields: FieldSpec[];
  runtimes: Runtime[];
  selected: string | null;
  versions: AgentVersion[];
  error: string | null;

  load(): Promise<void>;
  select(id: string | null): Promise<void>;
  create(name: string, template: string | null): Promise<void>;
  save(id: string, name: string, definition: Record<string, unknown>): Promise<void>;
  clone(id: string): Promise<void>;
  remove(id: string): Promise<void>;
  restore(id: string, number: number): Promise<void>;
  setRuntimeKey(runtimeId: string, value: string): Promise<void>;
}

export type AgentStore = StoreApi<AgentState>;

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function createAgentStore(client: ApiClient): AgentStore {
  return createStore<AgentState>((set, get) => {
    const guarded = async (work: () => Promise<void>) => {
      set({ error: null });
      try {
        await work();
      } catch (error) {
        set({ error: message(error) });
      }
    };
    const refresh = async () => set({ agents: await client.listAgents() });
    const refreshVersions = async (id: string) =>
      set({ versions: await client.listAgentVersions(id) });

    return {
      agents: [],
      templates: [],
      fields: [],
      runtimes: [],
      selected: null,
      versions: [],
      error: null,

      async load() {
        await guarded(async () => {
          const [templates, fields, runtimes] = await Promise.all([
            client.agentTemplates(),
            client.agentFields(),
            client.listRuntimes(),
          ]);
          set({ templates, fields, runtimes });
          await refresh();
        });
      },

      async select(id) {
        await guarded(async () => {
          set({ selected: id, versions: [] });
          if (id) await refreshVersions(id);
        });
      },

      async create(name, template) {
        await guarded(async () => {
          const agent = await client.createAgent(name, template);
          await refresh();
          await get().select(agent.id);
        });
      },

      async save(id, name, definition) {
        await guarded(async () => {
          await client.updateAgent(id, { name, definition });
          await refresh();
          await refreshVersions(id);
        });
      },

      async clone(id) {
        await guarded(async () => {
          const agent = await client.cloneAgent(id);
          await refresh();
          await get().select(agent.id);
        });
      },

      async remove(id) {
        await guarded(async () => {
          await client.deleteAgent(id);
          set({ selected: null, versions: [] });
          await refresh();
        });
      },

      async restore(id, number) {
        await guarded(async () => {
          await client.restoreAgentVersion(id, number);
          await refresh();
          await refreshVersions(id);
        });
      },

      async setRuntimeKey(runtimeId, value) {
        await guarded(async () => {
          const name = `runtime.${runtimeId}`;
          await client.storeSecret(name, value);
          await client.configureRuntime(runtimeId, { secret_name: name });
          set({ runtimes: await client.listRuntimes() });
        });
      },
    };
  });
}
