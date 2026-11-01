import { createStore, type StoreApi } from "zustand/vanilla";

import type {
  ApiClient,
  WorkspaceDetail,
  WorkspaceDraft,
  WorkspacePatch,
  WorkspaceSummary,
} from "@/lib/api";

export type SaveStatus = "idle" | "saving" | "saved" | "error";
export type Density = "compact" | "comfortable";

export interface Appearance {
  accent: string;
  density: Density;
}

export const DEFAULT_APPEARANCE: Appearance = { accent: "amber", density: "compact" };

const ACTIVE_WORKSPACE_KEY = "active_workspace";
const APPEARANCE_KEY = "appearance";

export interface WorkspaceState {
  phase: "loading" | "ready" | "failed";
  error: string | null;
  notice: string | null;
  workspaces: WorkspaceSummary[];
  active: WorkspaceDetail | null;
  /** Changes whenever the dock must reload the active workspace from `active.layout`. */
  layoutRevision: number;
  saveStatus: SaveStatus;
  appearance: Appearance;

  init(): Promise<void>;
  open(id: string): Promise<void>;
  create(draft: WorkspaceDraft): Promise<void>;
  duplicate(id: string): Promise<void>;
  remove(id: string): Promise<void>;
  rename(id: string, patch: Pick<WorkspacePatch, "name" | "description">): Promise<void>;
  importDocument(document: unknown): Promise<void>;
  resetLayout(): Promise<void>;
  saveLayout(layout: Record<string, unknown>): void;
  setPanelState(panelId: string, value: unknown): void;
  setAppearance(appearance: Appearance): Promise<void>;
  setNotice(notice: string | null): void;
  flush(options?: { keepalive?: boolean }): Promise<void>;
}

export type WorkspaceStore = StoreApi<WorkspaceState>;

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function createWorkspaceStore(client: ApiClient, debounceMs = 500): WorkspaceStore {
  let pending: { id: string; patch: WorkspacePatch } | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  // Writes run one at a time so an older layout can never land after a newer one.
  let queue: Promise<void> = Promise.resolve();

  return createStore<WorkspaceState>((set, get) => {
    const enqueueSave = (patch: WorkspacePatch) => {
      const id = get().active?.id;
      if (!id) return;
      pending = { id, patch: { ...pending?.patch, ...patch } };
      set({ saveStatus: "saving" });
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => void get().flush(), debounceMs);
    };

    const refreshList = async () => set({ workspaces: await client.listWorkspaces() });

    const show = (workspace: WorkspaceDetail) =>
      set((state) => ({
        active: workspace,
        layoutRevision: state.layoutRevision + 1,
        notice: null,
      }));

    const openWorkspace = async (id: string) => {
      await get().flush();
      show(await client.getWorkspace(id));
      await client.putSetting(ACTIVE_WORKSPACE_KEY, id);
    };

    return {
      phase: "loading",
      error: null,
      notice: null,
      workspaces: [],
      active: null,
      layoutRevision: 0,
      saveStatus: "idle",
      appearance: DEFAULT_APPEARANCE,

      async init() {
        set({ phase: "loading", error: null });
        try {
          const [workspaces, activeId, appearance] = await Promise.all([
            client.listWorkspaces(),
            client.getSetting(ACTIVE_WORKSPACE_KEY),
            client.getSetting(APPEARANCE_KEY),
          ]);
          const initial = workspaces.find((w) => w.id === activeId) ?? workspaces[0];
          set({
            workspaces,
            appearance: { ...DEFAULT_APPEARANCE, ...(appearance as Partial<Appearance> | null) },
          });
          show(await client.getWorkspace(initial.id));
          set({ phase: "ready" });
        } catch (error) {
          set({ phase: "failed", error: message(error) });
        }
      },

      open: openWorkspace,

      async create(draft) {
        const workspace = await client.createWorkspace(draft);
        await refreshList();
        await openWorkspace(workspace.id);
      },

      async duplicate(id) {
        await get().flush();
        const workspace = await client.duplicateWorkspace(id);
        await refreshList();
        await openWorkspace(workspace.id);
      },

      async remove(id) {
        const { active, workspaces } = get();
        if (active?.id === id) {
          const next = workspaces.find((w) => w.id !== id);
          if (next) await openWorkspace(next.id);
        }
        await client.deleteWorkspace(id);
        await refreshList();
      },

      async rename(id, patch) {
        const updated = await client.updateWorkspace(id, patch);
        set((state) => ({
          active: state.active?.id === id ? { ...state.active, ...patch } : state.active,
          workspaces: state.workspaces.map((w) => (w.id === id ? updated : w)),
        }));
      },

      async importDocument(document) {
        const workspace = await client.importWorkspace(document);
        await refreshList();
        await openWorkspace(workspace.id);
      },

      async resetLayout() {
        const { active } = get();
        if (!active) return;
        pending = null;
        show(await client.updateWorkspace(active.id, { layout: null }));
      },

      saveLayout(layout) {
        enqueueSave({ layout });
      },

      setPanelState(panelId, value) {
        const { active } = get();
        if (!active) return;
        const panel_states = { ...active.panel_states, [panelId]: value };
        set({ active: { ...active, panel_states } });
        enqueueSave({ panel_states });
      },

      async setAppearance(appearance) {
        set({ appearance });
        await client.putSetting(APPEARANCE_KEY, appearance);
      },

      setNotice(notice) {
        set({ notice });
      },

      flush({ keepalive = false } = {}) {
        if (timer) clearTimeout(timer);
        timer = null;
        const write = pending;
        pending = null;
        if (write) {
          queue = queue.then(async () => {
            try {
              await client.updateWorkspace(write.id, write.patch, keepalive);
              if (!pending) set({ saveStatus: "saved" });
            } catch (error) {
              // Keep the unsaved change so the next edit retries it.
              pending = { id: write.id, patch: { ...write.patch, ...pending?.patch } };
              set({ saveStatus: "error", notice: `Autosave failed: ${message(error)}` });
            }
          });
        }
        return queue;
      },
    };
  });
}
