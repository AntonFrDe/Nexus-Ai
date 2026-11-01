"use client";

import type { DockviewApi } from "dockview-react";
import { createContext, useContext, useState, type ReactNode } from "react";
import { useStore } from "zustand";

import type { PanelRegistry } from "@/core/panels/registry";
import { createWorkspaceStore, type WorkspaceState, type WorkspaceStore } from "@/core/workspace/store";
import { apiClient } from "@/lib/api";

interface Studio {
  store: WorkspaceStore;
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
  const [dock, setDock] = useState<DockviewApi | null>(null);
  return (
    <StudioContext.Provider value={{ store, registry, dock, setDock }}>
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
