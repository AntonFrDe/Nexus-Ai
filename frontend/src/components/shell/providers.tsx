"use client";

import type { DockviewApi } from "dockview-react";
import { createContext, useContext, useState, type ReactNode } from "react";
import { useStore } from "zustand";

import type { PanelRegistry } from "@/core/panels/registry";
import { createWorkflowStore, type WorkflowState, type WorkflowStore } from "@/core/workflow/store";
import { createWorkspaceStore, type WorkspaceState, type WorkspaceStore } from "@/core/workspace/store";
import { apiClient } from "@/lib/api";

interface Studio {
  store: WorkspaceStore;
  workflows: WorkflowStore;
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
  const [dock, setDock] = useState<DockviewApi | null>(null);
  return (
    <StudioContext.Provider value={{ store, workflows, registry, dock, setDock }}>
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
