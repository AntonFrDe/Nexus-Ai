import {
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type EdgeChange,
  type NodeChange,
} from "@xyflow/react";
import { createStore, type StoreApi } from "zustand/vanilla";

import {
  autoLayout,
  connectionProblem,
  createEdge,
  createNode,
  duplicateSelection,
  fromFlow,
  groupSelection,
  toFlow,
  ungroupSelection,
  type StudioEdge,
  type StudioNode,
  type StudioNodeData,
} from "@/core/workflow/graph";
import type {
  Issue,
  NodeCatalog,
  VersionSummary,
  WorkflowContent,
  WorkflowDocument,
  WorkflowSummary,
} from "@/core/workflow/types";
import type { ApiClient } from "@/lib/api";
import type { SaveStatus } from "@/core/workspace/store";

const ACTIVE_WORKFLOW_KEY = "active_workflow";
const EDITOR_KEY = "workflow_editor";
const HISTORY_LIMIT = 100;
const COALESCE_MS = 800;

type Meta = Pick<
  WorkflowDocument,
  "id" | "name" | "description" | "schema_version" | "variables" | "config" | "policies" | "metadata"
>;
interface Snapshot {
  nodes: StudioNode[];
  edges: StudioEdge[];
}

export interface WorkflowState {
  phase: "loading" | "ready" | "failed";
  error: string | null;
  notice: string | null;
  catalog: NodeCatalog | null;
  workflows: WorkflowSummary[];
  meta: Meta | null;
  /** Changes when a different document enters the canvas, so it can refit the view. */
  documentRevision: number;
  nodes: StudioNode[];
  edges: StudioEdge[];
  canUndo: boolean;
  canRedo: boolean;
  issues: Issue[];
  saveStatus: SaveStatus;
  snapToGrid: boolean;
  versions: VersionSummary[];

  init(): Promise<void>;
  open(id: string): Promise<void>;
  create(name: string): Promise<void>;
  duplicate(id: string): Promise<void>;
  remove(id: string): Promise<void>;
  rename(name: string, description: string): void;
  importDocument(document: unknown): Promise<void>;
  onNodesChange(changes: NodeChange<StudioNode>[]): void;
  onEdgesChange(changes: EdgeChange<StudioEdge>[]): void;
  connect(connection: Connection): void;
  addNode(type: string, position?: { x: number; y: number }): void;
  updateNode(id: string, patch: Partial<StudioNodeData>, coalesceKey?: string): void;
  updateEdgeLabel(id: string, label: string): void;
  duplicateSelected(): void;
  groupSelected(): void;
  ungroupSelected(): void;
  applyAutoLayout(): void;
  undo(): void;
  redo(): void;
  setSnapToGrid(enabled: boolean): void;
  setNotice(notice: string | null): void;
  loadVersions(): Promise<void>;
  createVersion(label: string): Promise<void>;
  restoreVersion(number: number): Promise<void>;
  flush(options?: { keepalive?: boolean }): Promise<void>;
}

export type WorkflowStore = StoreApi<WorkflowState>;

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

/** What counts as a change to the document; selection and measurements do not. */
const fingerprint = ({ nodes, edges }: Snapshot) => JSON.stringify(fromFlow(nodes, edges));

const contentOf = (meta: Meta, nodes: StudioNode[], edges: StudioEdge[]): WorkflowContent => ({
  name: meta.name,
  description: meta.description,
  schema_version: meta.schema_version,
  variables: meta.variables,
  config: meta.config,
  policies: meta.policies,
  metadata: meta.metadata,
  ...fromFlow(nodes, edges),
});

export function createWorkflowStore(
  client: ApiClient,
  { saveDelayMs = 500, now = Date.now }: { saveDelayMs?: number; now?: () => number } = {},
): WorkflowStore {
  let past: Snapshot[] = [];
  let future: Snapshot[] = [];
  let committed: Snapshot = { nodes: [], edges: [] };
  let committedPrint = fingerprint(committed);
  let lastCoalesce: { key: string; at: number } | null = null;
  let dirty: { id: string; content: WorkflowContent } | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let queue: Promise<void> = Promise.resolve();
  let validation = 0;

  return createStore<WorkflowState>((set, get) => {
    const validate = async () => {
      const { meta, nodes, edges } = get();
      if (!meta) return;
      const token = ++validation;
      const graph = {
        schema_version: meta.schema_version,
        variables: meta.variables,
        config: meta.config,
        policies: meta.policies,
        metadata: meta.metadata,
        ...fromFlow(nodes, edges),
      };
      try {
        const report = await client.validateWorkflow(graph);
        if (token === validation) set({ issues: report.issues });
      } catch (error) {
        if (token === validation) set({ notice: `Validation failed: ${message(error)}` });
      }
    };

    const scheduleSave = () => {
      const { meta, nodes, edges } = get();
      if (!meta) return;
      dirty = { id: meta.id, content: contentOf(meta, nodes, edges) };
      set({ saveStatus: "saving" });
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => void get().flush(), saveDelayMs);
    };

    const syncHistory = () => set({ canUndo: past.length > 0, canRedo: future.length > 0 });

    /** Records the current graph as an undo step and saves it, if it really changed. */
    const commit = (coalesceKey?: string) => {
      const { nodes, edges } = get();
      const print = fingerprint({ nodes, edges });
      if (print === committedPrint) return;
      const merge =
        coalesceKey !== undefined &&
        lastCoalesce?.key === coalesceKey &&
        now() - lastCoalesce.at < COALESCE_MS;
      if (!merge) past = [...past, committed].slice(-HISTORY_LIMIT);
      lastCoalesce = coalesceKey === undefined ? null : { key: coalesceKey, at: now() };
      future = [];
      committed = { nodes, edges };
      committedPrint = print;
      syncHistory();
      scheduleSave();
      void validate();
    };

    const apply = (snapshot: Snapshot) => {
      set(snapshot);
      commit();
    };

    const restore = (snapshot: Snapshot) => {
      committed = snapshot;
      committedPrint = fingerprint(snapshot);
      lastCoalesce = null;
      set(snapshot);
      syncHistory();
      scheduleSave();
      void validate();
    };

    const show = (document: WorkflowDocument) => {
      const { catalog } = get();
      const flow = toFlow(document, catalog);
      past = [];
      future = [];
      committed = flow;
      committedPrint = fingerprint(flow);
      lastCoalesce = null;
      const { id, name, description, schema_version, variables, config, policies, metadata } =
        document;
      set((state) => ({
        ...flow,
        meta: { id, name, description, schema_version, variables, config, policies, metadata },
        documentRevision: state.documentRevision + 1,
        issues: [],
        versions: [],
        notice: null,
        canUndo: false,
        canRedo: false,
      }));
      void validate();
    };

    const refreshList = async () => set({ workflows: await client.listWorkflows() });

    const clearCanvas = () => {
      committed = { nodes: [], edges: [] };
      committedPrint = fingerprint(committed);
      past = [];
      future = [];
      set({ meta: null, nodes: [], edges: [], issues: [], versions: [] });
      syncHistory();
    };

    const openDocument = async (id: string) => {
      await get().flush();
      show(await client.getWorkflow(id));
      await client.putSetting(ACTIVE_WORKFLOW_KEY, id);
    };

    return {
      phase: "loading",
      error: null,
      notice: null,
      catalog: null,
      workflows: [],
      meta: null,
      documentRevision: 0,
      nodes: [],
      edges: [],
      canUndo: false,
      canRedo: false,
      issues: [],
      saveStatus: "idle",
      snapToGrid: true,
      versions: [],

      async init() {
        set({ phase: "loading", error: null });
        try {
          const [catalog, workflows, activeId, editor] = await Promise.all([
            client.nodeCatalog(),
            client.listWorkflows(),
            client.getSetting(ACTIVE_WORKFLOW_KEY),
            client.getSetting(EDITOR_KEY),
          ]);
          set({
            catalog,
            workflows,
            snapToGrid: (editor as { snapToGrid?: boolean } | null)?.snapToGrid ?? true,
          });
          const initial = workflows.find((w) => w.id === activeId) ?? workflows[0];
          if (initial) show(await client.getWorkflow(initial.id));
          set({ phase: "ready" });
        } catch (error) {
          set({ phase: "failed", error: message(error) });
        }
      },

      open: openDocument,

      async create(name) {
        const document = await client.createWorkflow({ name, description: "" });
        await refreshList();
        await openDocument(document.id);
      },

      async duplicate(id) {
        await get().flush();
        const document = await client.duplicateWorkflow(id);
        await refreshList();
        await openDocument(document.id);
      },

      async remove(id) {
        await get().flush();
        const { meta, workflows } = get();
        await client.deleteWorkflow(id);
        if (meta?.id === id) {
          const next = workflows.find((workflow) => workflow.id !== id);
          if (next) await openDocument(next.id);
          else clearCanvas();
        }
        await refreshList();
      },

      rename(name, description) {
        const { meta } = get();
        if (!meta) return;
        set((state) => ({
          meta: { ...meta, name, description },
          workflows: state.workflows.map((workflow) =>
            workflow.id === meta.id ? { ...workflow, name, description } : workflow,
          ),
        }));
        scheduleSave();
      },

      async importDocument(document) {
        const imported = await client.importWorkflow(document);
        await refreshList();
        await openDocument(imported.id);
      },

      onNodesChange(changes) {
        set((state) => ({ nodes: applyNodeChanges(changes, state.nodes) }));
        const settled = changes.some(
          (change) =>
            change.type === "remove" ||
            change.type === "add" ||
            (change.type === "position" && change.dragging === false) ||
            (change.type === "dimensions" && change.resizing === false),
        );
        if (settled) commit();
      },

      onEdgesChange(changes) {
        set((state) => ({ edges: applyEdgeChanges(changes, state.edges) }));
        if (changes.some((change) => change.type === "remove")) commit();
      },

      connect(connection) {
        const { catalog, nodes, edges } = get();
        if (!catalog) return;
        const problem = connectionProblem(connection, nodes, edges, catalog);
        if (problem) {
          set({ notice: problem });
          return;
        }
        apply({ nodes, edges: [...edges, createEdge(connection, catalog, nodes)] });
      },

      addNode(type, position) {
        const { catalog, nodes, edges, meta } = get();
        if (!catalog || !meta) return;
        const offset = (nodes.length % 10) * 32;
        const node = createNode(type, position ?? { x: 96 + offset, y: 96 + offset }, catalog);
        apply({
          nodes: [...nodes.map((other) => ({ ...other, selected: false })), { ...node, selected: true }],
          edges,
        });
      },

      updateNode(id, patch, coalesceKey) {
        const { nodes, edges } = get();
        set({
          nodes: nodes.map((node) =>
            node.id === id ? { ...node, data: { ...node.data, ...patch } } : node,
          ),
          edges,
        });
        commit(coalesceKey);
      },

      updateEdgeLabel(id, label) {
        const { edges } = get();
        set({
          edges: edges.map((edge) =>
            edge.id === id ? { ...edge, label: label || undefined } : edge,
          ),
        });
        commit(`edge-label:${id}`);
      },

      duplicateSelected() {
        const { nodes, edges } = get();
        apply(duplicateSelection(nodes, edges));
      },

      groupSelected() {
        const { nodes, edges, catalog } = get();
        if (catalog) apply({ nodes: groupSelection(nodes, catalog), edges });
      },

      ungroupSelected() {
        const { nodes, edges } = get();
        apply({ nodes: ungroupSelection(nodes), edges });
      },

      applyAutoLayout() {
        const { nodes, edges } = get();
        apply({ nodes: autoLayout(nodes, edges), edges });
      },

      undo() {
        const previous = past.at(-1);
        if (!previous) return;
        past = past.slice(0, -1);
        future = [...future, committed];
        restore(previous);
      },

      redo() {
        const next = future.at(-1);
        if (!next) return;
        future = future.slice(0, -1);
        past = [...past, committed];
        restore(next);
      },

      setSnapToGrid(enabled) {
        set({ snapToGrid: enabled });
        void client.putSetting(EDITOR_KEY, { snapToGrid: enabled });
      },

      setNotice(notice) {
        set({ notice });
      },

      async loadVersions() {
        const { meta } = get();
        if (meta) set({ versions: await client.listVersions(meta.id) });
      },

      async createVersion(label) {
        const { meta } = get();
        if (!meta) return;
        await get().flush();
        await client.createVersion(meta.id, label);
        await get().loadVersions();
      },

      async restoreVersion(number) {
        const { meta } = get();
        if (!meta) return;
        await get().flush();
        show(await client.restoreVersion(meta.id, number));
        await refreshList();
        await get().loadVersions();
      },

      flush({ keepalive = false } = {}) {
        if (timer) clearTimeout(timer);
        timer = null;
        const write = dirty;
        dirty = null;
        if (write) {
          queue = queue.then(async () => {
            try {
              await client.saveWorkflow(write.id, write.content, keepalive);
              if (!dirty) set({ saveStatus: "saved" });
            } catch (error) {
              dirty ??= write;
              set({ saveStatus: "error", notice: `Autosave failed: ${message(error)}` });
            }
          });
        }
        return queue;
      },
    };
  });
}
