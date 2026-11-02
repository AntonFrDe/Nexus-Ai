"use client";

import { useEffect, useState } from "react";

import { DockHost } from "@/components/shell/dock-host";
import { StudioProvider, useStudio, useWorkspace } from "@/components/shell/providers";
import { StatusBar } from "@/components/shell/status-bar";
import { TitleBar } from "@/components/shell/title-bar";
import { apiClient } from "@/lib/api";
import { createPanelRegistry } from "@/panels";
import { pluginPanelDefinition } from "@/panels/plugin-panel";

function Shell() {
  const { store, workflows, executions, models, agents, plugins, registry } = useStudio();
  const [panelsReady, setPanelsReady] = useState(false);
  const phase = useWorkspace((state) => state.phase);
  const error = useWorkspace((state) => state.error);
  const appearance = useWorkspace((state) => state.appearance);

  useEffect(() => {
    // Plugin panels must be registered before the dock restores a layout that uses them.
    let alive = true;
    void apiClient
      .pluginPanels()
      .then((panels) =>
        panels.forEach((panel) => {
          if (!registry.has(panel.id)) registry.register(pluginPanelDefinition(panel));
        }),
      )
      .catch(() => undefined)
      .finally(() => alive && setPanelsReady(true));
    return () => {
      alive = false;
    };
  }, [registry]);

  useEffect(() => {
    void store.getState().init();
    void workflows.getState().init();
    void executions.getState().refresh().catch(() => undefined);
    void models.getState().load();
    void agents.getState().load();
    void plugins.getState().load();
  }, [store, workflows, executions, models, agents, plugins]);

  useEffect(() => {
    document.documentElement.dataset.accent = appearance.accent;
    document.documentElement.dataset.density = appearance.density;
  }, [appearance]);

  if (phase === "failed") {
    return (
      <main className="boot-screen" role="alert">
        <h1>Cannot reach the NEXUS backend</h1>
        <p>{error}</p>
        <p>
          Start it with <code>make backend</code>, then retry.
        </p>
        <button type="button" className="text-button" onClick={() => void store.getState().init()}>
          Retry
        </button>
      </main>
    );
  }

  return (
    <div className="studio">
      <TitleBar />
      <main className="dock">{phase === "ready" && panelsReady && <DockHost />}</main>
      <StatusBar />
    </div>
  );
}

export function Studio() {
  const [registry] = useState(createPanelRegistry);
  return (
    <StudioProvider registry={registry}>
      <Shell />
    </StudioProvider>
  );
}
