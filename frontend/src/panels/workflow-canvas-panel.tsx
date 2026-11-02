"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type IsValidConnection,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Copy,
  Grid3x3,
  Group,
  Network,
  Play,
  Redo2,
  Search,
  Undo2,
  Ungroup,
} from "lucide-react";
import { useEffect, useState, type ComponentType, type DragEvent, type KeyboardEvent } from "react";

import { useExecution, useStudio, useWorkflow } from "@/components/shell/providers";
import { NODE_RENDERERS } from "@/components/workflow/nodes";
import { isTerminal } from "@/core/workflow/execution-store";
import { connectionProblem, matchesSearch, type StudioEdge } from "@/core/workflow/graph";

export const NODE_DRAG_TYPE = "application/x-nexus-node";
const GRID = 16;

function ToolButton({
  label,
  icon: Icon,
  onClick,
  disabled,
  pressed,
}: {
  label: string;
  icon: ComponentType<{ className?: string }>;
  onClick(): void;
  disabled?: boolean;
  pressed?: boolean;
}) {
  return (
    <button
      type="button"
      className="icon-button"
      title={label}
      aria-label={label}
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onClick}
    >
      <Icon className="size-3.5" />
    </button>
  );
}

function RunControls() {
  const { workflows, executions, dock, registry } = useStudio();
  const running = useExecution(
    (state) => !!state.current && !isTerminal(state.current.status),
  );
  const canRun = useWorkflow((state) => state.meta !== null);
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [invalid, setInvalid] = useState(false);

  const start = async () => {
    let input: unknown = null;
    if (text.trim()) {
      try {
        input = JSON.parse(text);
      } catch {
        setInvalid(true);
        return;
      }
    }
    setInvalid(false);
    setOpen(false);
    const state = workflows.getState();
    await state.flush();
    if (!state.meta) return;
    await executions.getState().run(state.meta.id, input);
    const panel = registry.get("execution-list");
    if (panel && dock) {
      const existing = dock.getPanel(panel.id);
      if (existing) existing.api.setActive();
      else dock.addPanel({ id: panel.id, component: panel.id, title: panel.title });
    }
  };

  return (
    <>
      <span className="toolbar-divider" />
      <button
        type="button"
        className="text-button"
        disabled={!canRun || running}
        onClick={() => setOpen((value) => !value)}
      >
        <Play className="size-3.5" /> Run
      </button>
      {open && (
        <form
          className="run-form"
          onSubmit={(event) => {
            event.preventDefault();
            void start();
          }}
        >
          <input
            aria-label="Run input as JSON"
            placeholder="Input as JSON (optional)"
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => event.stopPropagation()}
          />
          <button type="submit" className="text-button">
            Start
          </button>
          {invalid && <span className="field-error">Not valid JSON</span>}
        </form>
      )}
    </>
  );
}

function Toolbar() {
  const { workflows } = useStudio();
  const { fitView } = useReactFlow();
  const actions = workflows.getState();
  const canUndo = useWorkflow((state) => state.canUndo);
  const canRedo = useWorkflow((state) => state.canRedo);
  const snapToGrid = useWorkflow((state) => state.snapToGrid);
  const nodes = useWorkflow((state) => state.nodes);
  const catalog = useWorkflow((state) => state.catalog);
  const [query, setQuery] = useState("");

  const selected = nodes.filter((node) => node.selected);
  const groupSelected = selected.some((node) => node.data.nodeType === "core.group");

  const find = () => {
    const matches = nodes.filter((node) => matchesSearch(node, query, catalog));
    if (!query.trim() || matches.length === 0) {
      if (query.trim()) actions.setNotice(`No node matches “${query}”`);
      return;
    }
    void fitView({ nodes: matches, duration: 200, maxZoom: 1.2, padding: 0.3 });
    actions.onNodesChange(
      nodes.map((node) => ({
        id: node.id,
        type: "select",
        selected: matches.includes(node),
      })),
    );
  };

  return (
    <div className="canvas-toolbar">
      <ToolButton label="Undo" icon={Undo2} disabled={!canUndo} onClick={actions.undo} />
      <ToolButton label="Redo" icon={Redo2} disabled={!canRedo} onClick={actions.redo} />
      <span className="toolbar-divider" />
      <ToolButton
        label="Snap to grid"
        icon={Grid3x3}
        pressed={snapToGrid}
        onClick={() => actions.setSnapToGrid(!snapToGrid)}
      />
      <ToolButton
        label="Auto layout"
        icon={Network}
        disabled={nodes.length === 0}
        onClick={() => {
          actions.applyAutoLayout();
          requestAnimationFrame(() => void fitView({ duration: 200 }));
        }}
      />
      <span className="toolbar-divider" />
      <ToolButton
        label="Duplicate selection"
        icon={Copy}
        disabled={selected.length === 0}
        onClick={actions.duplicateSelected}
      />
      <ToolButton
        label="Group selection"
        icon={Group}
        disabled={selected.length < 2}
        onClick={actions.groupSelected}
      />
      <ToolButton
        label="Ungroup"
        icon={Ungroup}
        disabled={!groupSelected}
        onClick={actions.ungroupSelected}
      />
      <span className="toolbar-divider" />
      <label className="canvas-search">
        <Search className="size-3.5" />
        <input
          aria-label="Search nodes"
          placeholder="Find node"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            event.stopPropagation();
            if (event.key === "Enter") find();
          }}
        />
      </label>
      <RunControls />
    </div>
  );
}

function Canvas() {
  const { workflows } = useStudio();
  const { fitView, screenToFlowPosition } = useReactFlow();
  const nodes = useWorkflow((state) => state.nodes);
  const edges = useWorkflow((state) => state.edges);
  const snapToGrid = useWorkflow((state) => state.snapToGrid);
  const documentRevision = useWorkflow((state) => state.documentRevision);
  const actions = workflows.getState();

  useEffect(() => {
    const frame = requestAnimationFrame(() => void fitView({ maxZoom: 1, padding: 0.2 }));
    return () => cancelAnimationFrame(frame);
  }, [documentRevision, fitView]);

  const isValidConnection: IsValidConnection<StudioEdge> = (connection) => {
    const { catalog, nodes: current, edges: currentEdges } = workflows.getState();
    return !!catalog && connectionProblem(connection, current, currentEdges, catalog) === null;
  };

  const onDrop = (event: DragEvent) => {
    const type = event.dataTransfer.getData(NODE_DRAG_TYPE);
    if (!type) return;
    event.preventDefault();
    actions.addNode(type, screenToFlowPosition({ x: event.clientX, y: event.clientY }));
  };

  const onKeyDown = (event: KeyboardEvent) => {
    if (!(event.metaKey || event.ctrlKey)) return;
    const key = event.key.toLowerCase();
    if (key === "z") {
      event.preventDefault();
      if (event.shiftKey) actions.redo();
      else actions.undo();
    } else if (key === "d") {
      event.preventDefault();
      actions.duplicateSelected();
    }
  };

  return (
    <div className="canvas" onKeyDown={onKeyDown} tabIndex={-1}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_RENDERERS}
        onNodesChange={actions.onNodesChange}
        onEdgesChange={actions.onEdgesChange}
        onConnect={actions.connect}
        isValidConnection={isValidConnection}
        onDragOver={(event) => event.preventDefault()}
        onDrop={onDrop}
        snapToGrid={snapToGrid}
        snapGrid={[GRID, GRID]}
        colorMode="dark"
        deleteKeyCode={["Backspace", "Delete"]}
        multiSelectionKeyCode={["Meta", "Control", "Shift"]}
        selectionKeyCode="Shift"
        minZoom={0.1}
        maxZoom={2}
      >
        <Background variant={BackgroundVariant.Dots} gap={GRID} size={1} />
        <MiniMap pannable zoomable />
        <Controls showInteractive={false} />
        <Panel position="top-left">
          <Toolbar />
        </Panel>
      </ReactFlow>
    </div>
  );
}

export function WorkflowCanvasPanel() {
  const hasDocument = useWorkflow((state) => state.meta !== null);
  const phase = useWorkflow((state) => state.phase);
  const error = useWorkflow((state) => state.error);
  const { workflows } = useStudio();

  if (phase === "failed") {
    return (
      <div className="panel" role="alert">
        <p className="panel-heading">Workflows could not be loaded</p>
        <pre className="code-block">{error}</pre>
      </div>
    );
  }
  if (!hasDocument) {
    return (
      <div className="dock-empty">
        <p>No workflow open</p>
        <button
          type="button"
          className="text-button"
          onClick={() => void workflows.getState().create("Untitled workflow")}
        >
          Create a workflow
        </button>
      </div>
    );
  }
  return (
    <ReactFlowProvider>
      <Canvas />
    </ReactFlowProvider>
  );
}
