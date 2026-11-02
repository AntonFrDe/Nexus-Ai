import { createStore, type StoreApi } from "zustand/vanilla";

import type { Plugin } from "@/core/models/plugin-types";
import type { ApiClient } from "@/lib/api";

export interface PluginState {
  plugins: Plugin[];
  sandbox: boolean;
  /** Panels and nodes load at startup, so a change takes effect after a reload. */
  needsReload: boolean;
  error: string | null;

  load(): Promise<void>;
  install(path: string): Promise<void>;
  enable(id: string, granted: string[]): Promise<void>;
  disable(id: string): Promise<void>;
  uninstall(id: string): Promise<void>;
  configure(id: string, config: Record<string, unknown>): Promise<void>;
}

export type PluginStore = StoreApi<PluginState>;

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function createPluginStore(client: ApiClient): PluginStore {
  return createStore<PluginState>((set) => {
    const refresh = async () => set({ plugins: await client.listPlugins() });
    const guarded = async (work: () => Promise<void>, changesApp = false) => {
      set({ error: null });
      try {
        await work();
        await refresh();
        if (changesApp) set({ needsReload: true });
      } catch (error) {
        set({ error: message(error) });
      }
    };

    return {
      plugins: [],
      sandbox: false,
      needsReload: false,
      error: null,

      async load() {
        await guarded(async () => {
          set({ sandbox: (await client.pluginStatus()).sandbox });
        });
      },

      async install(path) {
        await guarded(async () => {
          await client.installPlugin(path);
        });
      },

      async enable(id, granted) {
        await guarded(() => client.enablePlugin(id, granted), true);
      },

      async disable(id) {
        await guarded(() => client.disablePlugin(id), true);
      },

      async uninstall(id) {
        await guarded(() => client.uninstallPlugin(id), true);
      },

      async configure(id, config) {
        await guarded(() => client.configurePlugin(id, config));
      },
    };
  });
}
