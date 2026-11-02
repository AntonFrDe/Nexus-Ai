import { describe, expect, it, vi } from "vitest";

import { createExecutionStore, isTerminal } from "@/core/workflow/execution-store";
import type { ExecutionDetail, ExecutionEvent } from "@/core/workflow/execution-types";
import type { ApiClient, EventSourceFactory } from "@/lib/api";

const detail = (status: string, id = "e1"): ExecutionDetail => ({
  id,
  workflow_id: "w",
  workflow_name: "Flow",
  workflow_version: null,
  session_id: "s",
  status,
  mode: "full",
  allow_paid: false,
  step_mode: false,
  replay_of: null,
  entry_node: null,
  error: null,
  error_node: null,
  metrics: {},
  created_at: "",
  started_at: null,
  ended_at: null,
  input: null,
  output: null,
  nodes: [],
  pending_approvals: [],
});

const event = (seq: number, type = "log"): ExecutionEvent => ({
  seq,
  type,
  node_id: null,
  payload: {},
  created_at: "",
});

function setup(overrides: Partial<ApiClient> = {}) {
  let emit: (event: ExecutionEvent) => void = () => undefined;
  const close = vi.fn();
  const open = vi.fn<EventSourceFactory>((_id, onEvent) => {
    emit = onEvent;
    return close;
  });
  const client = {
    listExecutions: vi.fn(async () => []),
    getExecution: vi.fn(async () => detail("RUNNING")),
    startExecution: vi.fn(async () => detail("PENDING")),
    executionAction: vi.fn(async () => undefined),
    decideExecution: vi.fn(async () => undefined),
    retryExecution: vi.fn(async () => detail("PENDING", "e2")),
    ...overrides,
  } as unknown as ApiClient;
  return { store: createExecutionStore(client, open), client, open, close, send: (e: ExecutionEvent) => emit(e) };
}

describe("execution store", () => {
  it("starts a run and follows its events", async () => {
    const { store, open } = setup();
    await store.getState().run("w", { a: 1 });
    expect(store.getState().current?.id).toBe("e1");
    expect(open).toHaveBeenCalledOnce();
  });

  it("shows why a run was refused instead of pretending it started", async () => {
    const issues = [{ message: "Agent cannot run yet", node_id: "n" }];
    const { store, open } = setup({ startExecution: vi.fn(async () => ({ issues })) });
    await store.getState().run("w", null);
    expect(store.getState().current).toBeNull();
    expect(store.getState().refused).toEqual(issues);
    expect(open).not.toHaveBeenCalled();
  });

  it("ignores events replayed after a reconnect", async () => {
    const { store, send } = setup();
    await store.getState().run("w", null);
    send(event(1));
    send(event(1));
    send(event(2));
    expect(store.getState().events.map((e) => e.seq)).toEqual([1, 2]);
  });

  it("reloads the run when a node or status changes", async () => {
    const { store, client, send } = setup();
    await store.getState().run("w", null);
    send(event(1, "node_completed"));
    await vi.waitFor(() => expect(client.getExecution).toHaveBeenCalled());
    await vi.waitFor(() => expect(store.getState().current?.status).toBe("RUNNING"));
  });

  it("stops following the previous run when another is selected", async () => {
    const { store, close } = setup();
    await store.getState().run("w", null);
    await store.getState().select("e1");
    expect(close).toHaveBeenCalledOnce();
  });

  it("reports a failed action", async () => {
    const { store } = setup({
      executionAction: vi.fn(async () => Promise.reject(new Error("Cannot pause"))),
    });
    await store.getState().run("w", null);
    await store.getState().act("pause");
    expect(store.getState().error).toBe("Cannot pause");
  });

  it("classifies terminal statuses", () => {
    expect(isTerminal("FAILED")).toBe(true);
    expect(isTerminal("PAUSED")).toBe(false);
  });
});
