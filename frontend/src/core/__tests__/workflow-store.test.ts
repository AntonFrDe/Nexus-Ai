import { beforeEach, describe, expect, it, vi } from "vitest";

import { catalog, doc, workflowNode } from "@/core/__tests__/workflow-fixtures";
import { createWorkflowStore } from "@/core/workflow/store";
import type { ApiClient } from "@/lib/api";

function fakeClient(overrides: Partial<ApiClient> = {}) {
  return {
    nodeCatalog: vi.fn(async () => catalog),
    listWorkflows: vi.fn(async () => [doc(), doc([], [], "w2")]),
    getWorkflow: vi.fn(async (id: string) => doc([], [], id)),
    saveWorkflow: vi.fn(async (id: string) => doc([], [], id)),
    validateWorkflow: vi.fn(async () => ({ valid: true, issues: [] })),
    deleteWorkflow: vi.fn(async () => undefined),
    createVersion: vi.fn(async () => ({ number: 1, label: "", created_at: "" })),
    listVersions: vi.fn(async () => []),
    getSetting: vi.fn(async () => null),
    putSetting: vi.fn(async () => undefined),
    ...overrides,
  } as unknown as ApiClient;
}

async function ready(client = fakeClient(), now?: () => number) {
  const store = createWorkflowStore(client, { saveDelayMs: 100, now });
  await store.getState().init();
  return { store, client };
}

describe("workflow store", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("stays usable when there are no workflows", async () => {
    const { store } = await ready(fakeClient({ listWorkflows: vi.fn(async () => []) }));
    expect(store.getState().phase).toBe("ready");
    expect(store.getState().meta).toBeNull();
    store.getState().addNode("core.text");
    expect(store.getState().nodes).toHaveLength(0);
  });

  it("undoes and redoes edits", async () => {
    const { store } = await ready();
    store.getState().addNode("core.text");
    store.getState().addNode("core.text");
    expect(store.getState().nodes).toHaveLength(2);
    store.getState().undo();
    expect(store.getState().nodes).toHaveLength(1);
    store.getState().undo();
    expect(store.getState().nodes).toHaveLength(0);
    expect(store.getState().canUndo).toBe(false);
    store.getState().redo();
    store.getState().redo();
    expect(store.getState().nodes).toHaveLength(2);
    expect(store.getState().canRedo).toBe(false);
  });

  it("a new edit clears redo history", async () => {
    const { store } = await ready();
    store.getState().addNode("core.text");
    store.getState().undo();
    store.getState().addNode("core.merge");
    expect(store.getState().canRedo).toBe(false);
  });

  it("coalesces typing into one undo step, but not separate fields", async () => {
    let clock = 0;
    const { store } = await ready(fakeClient(), () => clock);
    store.getState().addNode("core.text");
    const id = store.getState().nodes[0].id;
    store.getState().updateNode(id, { label: "a" }, "label");
    clock += 100;
    store.getState().updateNode(id, { label: "ab" }, "label");
    store.getState().undo();
    expect(store.getState().nodes[0].data.label).toBe("");

    store.getState().redo();
    clock += 2000;
    store.getState().updateNode(id, { label: "abc" }, "label");
    store.getState().undo();
    expect(store.getState().nodes[0].data.label).toBe("ab");
  });

  it("selection never dirties the document", async () => {
    const client = fakeClient({
      getWorkflow: vi.fn(async () => doc([workflowNode("a", "core.text")])),
    });
    const { store } = await ready(client);
    store.getState().onNodesChange([{ id: "a", type: "select", selected: true }]);
    await vi.advanceTimersByTimeAsync(500);
    expect(client.saveWorkflow).not.toHaveBeenCalled();
    expect(store.getState().canUndo).toBe(false);
  });

  it("commits a drag only when it ends", async () => {
    const client = fakeClient({
      getWorkflow: vi.fn(async () => doc([workflowNode("a", "core.text")])),
    });
    const { store } = await ready(client);
    const move = (x: number, dragging: boolean) =>
      store.getState().onNodesChange([
        { id: "a", type: "position", position: { x, y: 0 }, dragging },
      ]);
    move(10, true);
    move(20, true);
    expect(store.getState().canUndo).toBe(false);
    move(20, false);
    expect(store.getState().canUndo).toBe(true);
    store.getState().undo();
    expect(store.getState().nodes[0].position.x).toBe(0);
  });

  it("autosaves one debounced write and revalidates", async () => {
    const { store, client } = await ready();
    store.getState().addNode("core.text");
    store.getState().addNode("core.text");
    expect(store.getState().saveStatus).toBe("saving");
    await vi.advanceTimersByTimeAsync(100);
    expect(client.saveWorkflow).toHaveBeenCalledTimes(1);
    expect(store.getState().saveStatus).toBe("saved");
    expect(vi.mocked(client.validateWorkflow).mock.calls.length).toBeGreaterThanOrEqual(3);
  });

  it("ignores a stale validation result", async () => {
    const pending: ((value: { valid: boolean; issues: never[] }) => void)[] = [];
    const validateWorkflow = vi.fn(
      () => new Promise<{ valid: boolean; issues: never[] }>((resolve) => pending.push(resolve)),
    );
    const { store } = await ready(fakeClient({ validateWorkflow }));
    store.getState().addNode("core.text");
    const stale = { severity: "error", code: "x", message: "", node_id: null, edge_id: null, field: null };
    pending.at(-1)!({ valid: true, issues: [] });
    pending[0]({ valid: false, issues: [stale] as never[] });
    await vi.advanceTimersByTimeAsync(0);
    expect(store.getState().issues).toEqual([]);
  });

  it("saves before switching and resets history for the next document", async () => {
    const { store, client } = await ready();
    store.getState().addNode("core.text");
    await store.getState().open("w2");
    expect(client.saveWorkflow).toHaveBeenCalledWith("w1", expect.anything(), false);
    expect(store.getState().meta?.id).toBe("w2");
    expect(store.getState().canUndo).toBe(false);
  });

  it("keeps a failed save for retry and reports it", async () => {
    const saveWorkflow = vi
      .fn()
      .mockRejectedValueOnce(new Error("disk full"))
      .mockResolvedValue(doc());
    const { store } = await ready(fakeClient({ saveWorkflow }));
    store.getState().addNode("core.text");
    await store.getState().flush();
    expect(store.getState().saveStatus).toBe("error");
    expect(store.getState().notice).toMatch(/disk full/);
    await store.getState().flush();
    expect(saveWorkflow).toHaveBeenCalledTimes(2);
    expect(store.getState().saveStatus).toBe("saved");
  });

  it("refuses an invalid connection with a reason", async () => {
    const client = fakeClient({
      getWorkflow: vi.fn(async () =>
        doc([workflowNode("m", "core.memory"), workflowNode("t", "core.text")]),
      ),
    });
    const { store } = await ready(client);
    store.getState().connect({
      source: "m",
      sourceHandle: "memory",
      target: "t",
      targetHandle: "in",
    });
    expect(store.getState().edges).toHaveLength(0);
    expect(store.getState().notice).toMatch(/memory to text/);
  });

  it("deleting the last workflow leaves an empty, working editor", async () => {
    const client = fakeClient({ listWorkflows: vi.fn(async () => [doc()]) });
    const { store } = await ready(client);
    vi.mocked(client.listWorkflows).mockResolvedValue([]);
    await store.getState().remove("w1");
    expect(store.getState().meta).toBeNull();
    expect(store.getState().nodes).toEqual([]);
  });

  it("saves pending edits before snapshotting a version", async () => {
    const { store, client } = await ready();
    store.getState().addNode("core.text");
    await store.getState().createVersion("first");
    const saved = vi.mocked(client.saveWorkflow).mock.invocationCallOrder[0];
    const versioned = vi.mocked(client.createVersion).mock.invocationCallOrder[0];
    expect(saved).toBeLessThan(versioned);
  });
});
