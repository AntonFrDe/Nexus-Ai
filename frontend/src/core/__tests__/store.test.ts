import { beforeEach, describe, expect, it, vi } from "vitest";

import { createWorkspaceStore } from "@/core/workspace/store";
import type { ApiClient, WorkspaceDetail } from "@/lib/api";

const LAYOUT = { grid: {}, panels: {} };

const workspace = (id: string, overrides: Partial<WorkspaceDetail> = {}): WorkspaceDetail => ({
  id,
  name: id,
  description: "",
  preset: "custom",
  position: 0,
  created_at: "",
  updated_at: "",
  layout: null,
  panel_states: {},
  preferences: {},
  ...overrides,
});

function fakeClient(overrides: Partial<ApiClient> = {}) {
  return {
    listWorkspaces: vi.fn(async () => [workspace("a"), workspace("b")]),
    getWorkspace: vi.fn(async (id: string) => workspace(id)),
    updateWorkspace: vi.fn(async (id: string) => workspace(id)),
    deleteWorkspace: vi.fn(async () => undefined),
    getSetting: vi.fn(async () => null),
    putSetting: vi.fn(async () => undefined),
    ...overrides,
  } as unknown as ApiClient;
}

describe("workspace store", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("restores the last active workspace", async () => {
    const client = fakeClient({ getSetting: vi.fn(async () => "b") });
    const store = createWorkspaceStore(client);
    await store.getState().init();
    expect(store.getState().active?.id).toBe("b");
    expect(store.getState().phase).toBe("ready");
  });

  it("starting twice loads once, so a late start cannot undo what the user did", async () => {
    const client = fakeClient();
    const store = createWorkspaceStore(client);
    const first = store.getState().init();
    const second = store.getState().init();
    await Promise.all([first, second]);
    expect(client.listWorkspaces).toHaveBeenCalledTimes(1);
    expect(store.getState().layoutRevision).toBe(1);
  });

  it("can start again after a failure, which the retry button relies on", async () => {
    const listWorkspaces = vi
      .fn()
      .mockRejectedValueOnce(new Error("down"))
      .mockResolvedValue([workspace("a")]);
    const store = createWorkspaceStore(fakeClient({ listWorkspaces }));
    await store.getState().init();
    expect(store.getState().phase).toBe("failed");
    await store.getState().init();
    expect(store.getState().phase).toBe("ready");
  });

  it("a slow response never replaces a workspace opened after it", async () => {
    let finishSlow: (value: WorkspaceDetail) => void = () => undefined;
    const getWorkspace = vi.fn(async (id: string) =>
      id === "slow"
        ? new Promise<WorkspaceDetail>((resolve) => (finishSlow = resolve))
        : workspace(id),
    );
    const store = createWorkspaceStore(fakeClient({ getWorkspace }));
    await store.getState().init();
    const slow = store.getState().open("slow");
    await vi.advanceTimersByTimeAsync(0);
    await store.getState().open("b");
    finishSlow(workspace("slow"));
    await slow;
    expect(store.getState().active?.id).toBe("b");
  });

  it("falls back to the first workspace when the remembered one is gone", async () => {
    const store = createWorkspaceStore(fakeClient({ getSetting: vi.fn(async () => "deleted") }));
    await store.getState().init();
    expect(store.getState().active?.id).toBe("a");
  });

  it("surfaces an unreachable backend instead of an empty app", async () => {
    const store = createWorkspaceStore(
      fakeClient({ listWorkspaces: vi.fn(async () => Promise.reject(new Error("down"))) }),
    );
    await store.getState().init();
    expect(store.getState().phase).toBe("failed");
    expect(store.getState().error).toBe("down");
  });

  it("coalesces rapid layout changes into one autosave", async () => {
    const client = fakeClient();
    const store = createWorkspaceStore(client, 100);
    await store.getState().init();
    store.getState().saveLayout({ ...LAYOUT, n: 1 });
    store.getState().saveLayout({ ...LAYOUT, n: 2 });
    expect(store.getState().saveStatus).toBe("saving");
    await vi.advanceTimersByTimeAsync(100);
    expect(client.updateWorkspace).toHaveBeenCalledTimes(1);
    expect(client.updateWorkspace).toHaveBeenCalledWith("a", { layout: { ...LAYOUT, n: 2 } }, false);
    expect(store.getState().saveStatus).toBe("saved");
  });

  it("saves pending changes to the old workspace before switching", async () => {
    const client = fakeClient();
    const store = createWorkspaceStore(client, 10_000);
    await store.getState().init();
    store.getState().saveLayout(LAYOUT);
    await store.getState().open("b");
    expect(client.updateWorkspace).toHaveBeenCalledWith("a", { layout: LAYOUT }, false);
    expect(store.getState().active?.id).toBe("b");
  });

  it("keeps the change and reports it when autosave fails, then retries", async () => {
    const updateWorkspace = vi
      .fn()
      .mockRejectedValueOnce(new Error("disk full"))
      .mockResolvedValue(workspace("a"));
    const client = fakeClient({ updateWorkspace });
    const store = createWorkspaceStore(client);
    await store.getState().init();
    store.getState().saveLayout(LAYOUT);
    await store.getState().flush();
    expect(store.getState().saveStatus).toBe("error");
    expect(store.getState().notice).toMatch(/disk full/);
    await store.getState().flush();
    expect(updateWorkspace).toHaveBeenCalledTimes(2);
    expect(store.getState().saveStatus).toBe("saved");
  });

  it("merges panel state with layout in the same save", async () => {
    const client = fakeClient();
    const store = createWorkspaceStore(client);
    await store.getState().init();
    store.getState().saveLayout(LAYOUT);
    store.getState().setPanelState("notes", { text: "hi" });
    await store.getState().flush();
    expect(client.updateWorkspace).toHaveBeenCalledWith(
      "a",
      { layout: LAYOUT, panel_states: { notes: { text: "hi" } } },
      false,
    );
  });

  it("moves to another workspace before deleting the active one", async () => {
    const client = fakeClient();
    const store = createWorkspaceStore(client);
    await store.getState().init();
    await store.getState().remove("a");
    expect(store.getState().active?.id).toBe("b");
    expect(client.deleteWorkspace).toHaveBeenCalledWith("a");
  });

  it("reset clears the saved layout and asks the dock to reload", async () => {
    const client = fakeClient();
    const store = createWorkspaceStore(client);
    await store.getState().init();
    const revision = store.getState().layoutRevision;
    await store.getState().resetLayout();
    expect(client.updateWorkspace).toHaveBeenCalledWith("a", { layout: null });
    expect(store.getState().layoutRevision).toBe(revision + 1);
  });
});
