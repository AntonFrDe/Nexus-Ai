"use client";

import { Layers, LayoutGrid, RotateCcw } from "lucide-react";

import { useStudio, useWorkspace } from "@/components/shell/providers";
import { useRevealPanel } from "@/components/shell/use-open-panels";

export function TitleBar() {
  const { registry, store } = useStudio();
  const workspaces = useWorkspace((state) => state.workspaces);
  const activeId = useWorkspace((state) => state.active?.id);
  const reveal = useRevealPanel();

  const revealById = (id: string) => {
    const definition = registry.get(id);
    if (definition) reveal(definition);
  };

  return (
    <header className="title-bar">
      <span className="brand">NEXUS</span>
      <nav className="workspace-tabs" aria-label="Workspaces">
        {workspaces.map((workspace) => (
          <button
            key={workspace.id}
            type="button"
            className="workspace-tab"
            aria-current={workspace.id === activeId ? "page" : undefined}
            onClick={() => void store.getState().open(workspace.id)}
          >
            {workspace.name}
          </button>
        ))}
      </nav>
      <div className="title-actions">
        <button type="button" className="text-button" onClick={() => revealById("panel-library")}>
          <LayoutGrid className="size-3.5" /> Panels
        </button>
        <button
          type="button"
          className="text-button"
          onClick={() => revealById("workspace-manager")}
        >
          <Layers className="size-3.5" /> Workspaces
        </button>
        <button
          type="button"
          className="text-button"
          onClick={() => void store.getState().resetLayout()}
        >
          <RotateCcw className="size-3.5" /> Reset layout
        </button>
      </div>
    </header>
  );
}
