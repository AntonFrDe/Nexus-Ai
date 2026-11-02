import { createStore, type StoreApi } from "zustand/vanilla";

import type { ApiClient, EventSourceFactory } from "@/lib/api";
import type { Execution, ExecutionDetail, ExecutionEvent } from "@/core/workflow/execution-types";

const TERMINAL = new Set(["COMPLETED", "FAILED", "CANCELLED"]);
export const isTerminal = (status: string) => TERMINAL.has(status);

export interface ExecutionState {
  executions: Execution[];
  current: ExecutionDetail | null;
  events: ExecutionEvent[];
  /** Node to inspect in the Executions panel. */
  selectedNode: string | null;
  error: string | null;
  refused: { message: string; node_id: string | null }[];

  refresh(): Promise<void>;
  run(
    workflowId: string,
    input: unknown,
    options?: { mode?: string; node_id?: string; allow_paid?: boolean; step?: boolean },
  ): Promise<void>;
  select(id: string): Promise<void>;
  clear(): void;
  selectNode(id: string | null): void;
  act(action: "pause" | "resume" | "cancel"): Promise<void>;
  decide(decision: "approved" | "rejected"): Promise<void>;
  retry(): Promise<void>;
  runToEnd(): Promise<void>;
  replay(overrides: Record<string, unknown>, allowPaid: boolean): Promise<void>;
}

export type ExecutionStore = StoreApi<ExecutionState>;

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function createExecutionStore(
  client: ApiClient,
  openEvents: EventSourceFactory,
): ExecutionStore {
  let closeStream: (() => void) | null = null;

  return createStore<ExecutionState>((set, get) => {
    const reload = async (id: string) => {
      const detail = await client.getExecution(id);
      if (get().current?.id === id || get().current === null) set({ current: detail });
    };

    const follow = (id: string) => {
      closeStream?.();
      closeStream = openEvents(
        id,
        (event) => {
          set((state) =>
            state.events.some((known) => known.seq === event.seq)
              ? state
              : { events: [...state.events, event] },
          );
          if (event.type === "status" || event.type.startsWith("node_")) {
            void reload(id).catch(() => undefined);
          }
          if (event.type === "status") void get().refresh().catch(() => undefined);
        },
        () => void reload(id).catch(() => undefined),
      );
    };

    const show = (detail: ExecutionDetail) => {
      set({ current: detail, events: [], selectedNode: null, error: null, refused: [] });
      follow(detail.id);
    };

    const guarded = async (work: () => Promise<void>) => {
      try {
        set({ error: null });
        await work();
      } catch (error) {
        set({ error: message(error) });
      }
    };

    return {
      executions: [],
      current: null,
      events: [],
      selectedNode: null,
      error: null,
      refused: [],

      async refresh() {
        set({ executions: await client.listExecutions() });
      },

      async run(workflowId, input, options) {
        await guarded(async () => {
          const outcome = await client.startExecution(workflowId, { input, ...options });
          if ("issues" in outcome) {
            set({ refused: outcome.issues, error: "The workflow cannot run yet." });
            return;
          }
          show(outcome);
          await get().refresh();
        });
      },

      async select(id) {
        await guarded(async () => show(await client.getExecution(id)));
      },

      clear() {
        closeStream?.();
        closeStream = null;
        set({ current: null, events: [], selectedNode: null });
      },

      selectNode(id) {
        set({ selectedNode: id });
      },

      async act(action) {
        const id = get().current?.id;
        if (!id) return;
        await guarded(async () => {
          await client.executionAction(id, action);
          follow(id);
          await reload(id);
        });
      },

      async decide(decision) {
        const id = get().current?.id;
        if (!id) return;
        await guarded(async () => {
          await client.decideExecution(id, decision);
          follow(id);
          await reload(id);
        });
      },

      async runToEnd() {
        const id = get().current?.id;
        if (!id) return;
        await guarded(async () => {
          await client.runToEnd(id);
          follow(id);
          await reload(id);
        });
      },

      async replay(overrides, allowPaid) {
        const id = get().current?.id;
        if (!id) return;
        await guarded(async () => {
          show(await client.replayExecution(id, overrides, allowPaid));
          await get().refresh();
        });
      },

      async retry() {
        const id = get().current?.id;
        if (!id) return;
        await guarded(async () => {
          show(await client.retryExecution(id));
          await get().refresh();
        });
      },
    };
  });
}
