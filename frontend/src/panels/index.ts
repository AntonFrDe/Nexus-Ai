import {
  Activity,
  Blocks,
  Bot,
  BrainCircuit,
  Braces,
  CircleAlert,
  Coins,
  Files,
  GitBranch,
  LayoutGrid,
  Layers,
  ListTree,
  Logs,
  NotebookPen,
  Palette,
  Route,
  SlidersHorizontal,
  Workflow,
} from "lucide-react";

import { PanelRegistry, type PanelDefinition } from "@/core/panels/registry";
import { AppearancePanel } from "@/panels/appearance-panel";
import { ExecutionLogsPanel } from "@/panels/execution-logs-panel";
import { ExecutionsPanel } from "@/panels/executions-panel";
import { LayoutInspectorPanel } from "@/panels/layout-inspector-panel";
import { NodeInspectorPanel } from "@/panels/node-inspector-panel";
import { NodeLibraryPanel } from "@/panels/node-library-panel";
import { NotesPanel } from "@/panels/notes-panel";
import { PanelLibraryPanel } from "@/panels/panel-library-panel";
import { plannedPanel } from "@/panels/planned-panel";
import { ProblemsPanel } from "@/panels/problems-panel";
import { SystemStatusPanel } from "@/panels/system-status-panel";
import { WorkflowCanvasPanel } from "@/panels/workflow-canvas-panel";
import { WorkflowVersionsPanel } from "@/panels/workflow-versions-panel";
import { WorkflowsPanel } from "@/panels/workflows-panel";
import { WorkspaceManagerPanel } from "@/panels/workspace-manager-panel";

const WORKSPACE = "Workspace";
const SYSTEM = "System";
const WORKFLOW = "Workflow";
const EXECUTION = "Execution";
const AI = "Agents & models";

const BUILT_IN_PANELS: PanelDefinition[] = [
  {
    id: "workspace-manager",
    title: "Workspaces",
    description: "Create, edit, duplicate, import and export workspaces.",
    category: WORKSPACE,
    icon: Layers,
    component: WorkspaceManagerPanel,
  },
  {
    id: "panel-library",
    title: "Panels",
    description: "Show or hide any registered panel.",
    category: WORKSPACE,
    icon: LayoutGrid,
    component: PanelLibraryPanel,
  },
  {
    id: "notes",
    title: "Notes",
    description: "Free-form notes saved with the workspace.",
    category: WORKSPACE,
    icon: NotebookPen,
    component: NotesPanel,
  },
  {
    id: "appearance",
    title: "Appearance",
    description: "Accent color and interface density.",
    category: SYSTEM,
    icon: Palette,
    component: AppearancePanel,
  },
  {
    id: "system-status",
    title: "System Status",
    description: "Live backend health.",
    category: SYSTEM,
    icon: Activity,
    component: SystemStatusPanel,
  },
  {
    id: "layout-inspector",
    title: "Layout Inspector",
    description: "The live serialized layout of this workspace.",
    category: SYSTEM,
    icon: Braces,
    component: LayoutInspectorPanel,
  },
  {
    id: "workflows",
    title: "Workflows",
    description: "Create, open, duplicate, import and export workflows.",
    category: WORKFLOW,
    icon: Files,
    component: WorkflowsPanel,
  },
  {
    id: "workflow-canvas",
    title: "Workflow Canvas",
    description: "Visual node editor for designing workflows.",
    category: WORKFLOW,
    icon: Workflow,
    component: WorkflowCanvasPanel,
  },
  {
    id: "node-library",
    title: "Node Library",
    description: "Searchable catalog of registered workflow nodes.",
    category: WORKFLOW,
    icon: Blocks,
    component: NodeLibraryPanel,
  },
  {
    id: "node-inspector",
    title: "Node Inspector",
    description: "Schema-driven configuration of the selected node.",
    category: WORKFLOW,
    icon: SlidersHorizontal,
    component: NodeInspectorPanel,
  },
  {
    id: "problems",
    title: "Problems",
    description: "Validation results from the backend.",
    category: WORKFLOW,
    icon: CircleAlert,
    component: ProblemsPanel,
  },
  {
    id: "workflow-versions",
    title: "Workflow Versions",
    description: "Save and restore versions of the open workflow.",
    category: WORKFLOW,
    icon: GitBranch,
    component: WorkflowVersionsPanel,
  },
  {
    id: "execution-list",
    title: "Executions",
    description: "Run history, live status, approvals and node inputs and outputs.",
    category: EXECUTION,
    icon: ListTree,
    component: ExecutionsPanel,
  },
  {
    id: "execution-logs",
    title: "Execution Logs",
    description: "Live event log of the selected run.",
    category: EXECUTION,
    icon: Logs,
    component: ExecutionLogsPanel,
  },
  plannedPanel({
    id: "execution-trace",
    title: "Execution Trace",
    description: "Node-by-node trace with state inspection.",
    category: EXECUTION,
    icon: Route,
    milestone: 7,
  }),
  plannedPanel({
    id: "cost-analytics",
    title: "Cost Analytics",
    description: "Tokens, cost and model usage over time.",
    category: EXECUTION,
    icon: Coins,
    milestone: 7,
  }),
  plannedPanel({
    id: "model-registry",
    title: "Model Registry",
    description: "Providers, models and connection tests.",
    category: AI,
    icon: BrainCircuit,
    milestone: 4,
  }),
  plannedPanel({
    id: "agent-registry",
    title: "Agents",
    description: "Agent definitions, templates and runtimes.",
    category: AI,
    icon: Bot,
    milestone: 5,
  }),
];

export function createPanelRegistry(): PanelRegistry {
  const registry = new PanelRegistry();
  BUILT_IN_PANELS.forEach((panel) => registry.register(panel));
  return registry;
}
