"use client";

import type { DockviewApi } from "dockview-react";
import { createContext, useContext, useState, type ReactNode } from "react";
import { useStore } from "zustand";

import { createAgentStore, type AgentState, type AgentStore } from "@/core/models/agent-store";
import { createPluginStore, type PluginState, type PluginStore } from "@/core/models/plugin-store";
import { createModelStore, type ModelState, type ModelStore } from "@/core/models/store";
import type { PanelRegistry } from "@/core/panels/registry";
import {
  createExecutionStore,
  type ExecutionState,
  type ExecutionStore,
} from "@/core/workflow/execution-store";
import { createWorkflowStore, type WorkflowState, type WorkflowStore } from "@/core/workflow/store";
import { createWorkspaceStore, type WorkspaceState, type WorkspaceStore } from "@/core/workspace/store";
import { apiClient, openExecutionEvents } from "@/lib/api";

interface Studio {
  store: WorkspaceStore;
  workflows: WorkflowStore;
  executions: ExecutionStore;
  models: ModelStore;
  agents: AgentStore;
  plugins: PluginStore;
  registry: PanelRegistry;
  dock: DockviewApi | null;
  setDock(api: DockviewApi): void;
}

const StudioContext = createContext<Studio | null>(null);

export function StudioProvider({
  registry,
  children,
}: {
  registry: PanelRegistry;
  children: ReactNode;
}) {
  const [store] = useState(() => createWorkspaceStore(apiClient));
  const [workflows] = useState(() => createWorkflowStore(apiClient));
  const [executions] = useState(() => createExecutionStore(apiClient, openExecutionEvents));
  const [models] = useState(() => createModelStore(apiClient));
  const [agents] = useState(() => createAgentStore(apiClient));
  const [plugins] = useState(() => createPluginStore(apiClient));
  const [dock, setDock] = useState<DockviewApi | null>(null);
  return (
    <StudioContext.Provider value={{ store, workflows, executions, models, agents, plugins, registry, dock, setDock }}>
      {children}
    </StudioContext.Provider>
  );
}

export function useStudio(): Studio {
  const studio = useContext(StudioContext);
  if (!studio) throw new Error("useStudio must be used inside StudioProvider");
  return studio;
}

export function useWorkspace<T>(selector: (state: WorkspaceState) => T): T {
  return useStore(useStudio().store, selector);
}

export function useWorkflow<T>(selector: (state: WorkflowState) => T): T {
  return useStore(useStudio().workflows, selector);
}

export function useExecution<T>(selector: (state: ExecutionState) => T): T {
  return useStore(useStudio().executions, selector);
}

export function useModels<T>(selector: (state: ModelState) => T): T {
  return useStore(useStudio().models, selector);
}

export function useAgents<T>(selector: (state: AgentState) => T): T {
  return useStore(useStudio().agents, selector);
}

export function usePlugins<T>(selector: (state: PluginState) => T): T {
  return useStore(useStudio().plugins, selector);
}
