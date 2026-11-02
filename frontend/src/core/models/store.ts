import { createStore, type StoreApi } from "zustand/vanilla";

import type {
  ConnectionResult,
  ModelTestResult,
  Provider,
  ProviderType,
  RegisteredModel,
} from "@/core/models/types";
import type { ApiClient } from "@/lib/api";

export interface ModelState {
  types: ProviderType[];
  providers: Provider[];
  models: RegisteredModel[];
  secretBackend: string | null;
  selectedProvider: string | null;
  selectedModel: string | null;
  connection: ConnectionResult | null;
  modelTest: ModelTestResult | null;
  busy: boolean;
  error: string | null;

  load(): Promise<void>;
  selectProvider(id: string | null): void;
  selectModel(id: string | null): void;
  addProvider(draft: {
    type: string;
    name: string;
    endpoint: string;
    apiKey: string;
  }): Promise<boolean>;
  setKey(providerId: string, value: string): Promise<void>;
  setEnabled(providerId: string, enabled: boolean): Promise<void>;
  removeProvider(id: string): Promise<void>;
  testConnection(id: string): Promise<void>;
  discover(id: string): Promise<void>;
  addModel(providerId: string, modelId: string): Promise<void>;
  updateModel(id: string, patch: Partial<RegisteredModel>): Promise<void>;
  removeModel(id: string): Promise<void>;
  testModel(id: string, confirmPaid: boolean): Promise<void>;
}

export type ModelStore = StoreApi<ModelState>;

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));
const secretNameFor = (providerId: string) => `provider.${providerId}`;

export function createModelStore(client: ApiClient): ModelStore {
  return createStore<ModelState>((set, get) => {
    const guarded = async (work: () => Promise<void>) => {
      set({ busy: true, error: null });
      try {
        await work();
      } catch (error) {
        set({ error: message(error) });
      } finally {
        set({ busy: false });
      }
    };

    const refresh = async () => {
      const [providers, models] = await Promise.all([client.listProviders(), client.listModels()]);
      set({ providers, models });
    };

    return {
      types: [],
      providers: [],
      models: [],
      secretBackend: null,
      selectedProvider: null,
      selectedModel: null,
      connection: null,
      modelTest: null,
      busy: false,
      error: null,

      async load() {
        await guarded(async () => {
          const [types, status] = await Promise.all([
            client.providerTypes(),
            client.secretStatus(),
          ]);
          set({ types, secretBackend: status.backend });
          await refresh();
        });
      },

      selectProvider(id) {
        set({ selectedProvider: id, selectedModel: null, connection: null, modelTest: null });
      },

      selectModel(id) {
        set({ selectedModel: id, modelTest: null });
      },

      async addProvider({ type, name, endpoint, apiKey }) {
        let added = false;
        await guarded(async () => {
          const provider = await client.createProvider({
            type,
            name,
            ...(endpoint ? { endpoint } : {}),
          });
          // The key goes to the secrets service; the provider keeps only its name.
          if (apiKey) {
            await client.storeSecret(secretNameFor(provider.id), apiKey);
            await client.updateProvider(provider.id, { secret_name: secretNameFor(provider.id) });
          }
          await refresh();
          get().selectProvider(provider.id);
          added = true;
        });
        return added;
      },

      async setKey(providerId, value) {
        await guarded(async () => {
          await client.storeSecret(secretNameFor(providerId), value);
          await client.updateProvider(providerId, { secret_name: secretNameFor(providerId) });
          await refresh();
        });
      },

      async setEnabled(providerId, enabled) {
        await guarded(async () => {
          await client.updateProvider(providerId, { enabled });
          await refresh();
        });
      },

      async removeProvider(id) {
        await guarded(async () => {
          const provider = get().providers.find((item) => item.id === id);
          await client.deleteProvider(id);
          if (provider?.secret_name === secretNameFor(id)) {
            await client.deleteSecret(secretNameFor(id));
          }
          get().selectProvider(null);
          await refresh();
        });
      },

      async testConnection(id) {
        await guarded(async () => {
          set({ connection: await client.testProvider(id) });
        });
      },

      async discover(id) {
        await guarded(async () => {
          await client.discoverModels(id);
          await refresh();
        });
      },

      async addModel(providerId, modelId) {
        await guarded(async () => {
          await client.addModel(providerId, modelId);
          await refresh();
        });
      },

      async updateModel(id, patch) {
        await guarded(async () => {
          await client.updateModel(id, patch);
          await refresh();
        });
      },

      async removeModel(id) {
        await guarded(async () => {
          await client.deleteModel(id);
          set({ selectedModel: null, modelTest: null });
          await refresh();
        });
      },

      async testModel(id, confirmPaid) {
        await guarded(async () => {
          set({ modelTest: null });
          set({ modelTest: await client.testModel(id, confirmPaid) });
          await refresh();
        });
      },
    };
  });
}
