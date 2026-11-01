"use client";

import {
  DockviewReact,
  themeDark,
  type DockviewReadyEvent,
  type IDockviewPanelProps,
} from "dockview-react";
import { useEffect, useMemo, useRef, type FunctionComponent } from "react";

import { GroupActions } from "@/components/shell/group-actions";
import { PanelBoundary } from "@/components/shell/panel-boundary";
import { useStudio, useWorkspace } from "@/components/shell/providers";
import type { PanelRegistry } from "@/core/panels/registry";
import { loadLayout, MISSING_PANEL } from "@/core/workspace/layout";
import { MissingPanel } from "@/panels/missing-panel";

function dockComponents(registry: PanelRegistry) {
  const components: Record<string, FunctionComponent<IDockviewPanelProps>> = {
    [MISSING_PANEL]: MissingPanel,
  };
  for (const { id, component: Panel } of registry.list()) {
    const Wrapped: FunctionComponent<IDockviewPanelProps> = (props) => (
      <PanelBoundary title={props.api.title ?? id}>
        <Panel {...props} />
      </PanelBoundary>
    );
    components[id] = Wrapped;
  }
  return components;
}

function EmptyDock() {
  return (
    <div className="dock-empty">
      <p>No panels open</p>
      <p>Use Panels in the title bar to add one, or reset the layout.</p>
    </div>
  );
}

export function DockHost() {
  const { registry, dock, setDock, store } = useStudio();
  const layoutRevision = useWorkspace((state) => state.layoutRevision);
  const components = useMemo(() => dockComponents(registry), [registry]);
  // Serialized form of what the store already knows; lets us ignore no-op layout events.
  const knownLayout = useRef<string | null>(null);

  useEffect(() => {
    const { active, setNotice } = store.getState();
    if (!dock || !active) return;
    knownLayout.current = null;
    const warning = loadLayout(dock, active, registry);
    knownLayout.current = JSON.stringify(dock.toJSON());
    if (warning) setNotice(warning);
  }, [dock, layoutRevision, registry, store]);

  useEffect(() => {
    if (!dock) return;
    const subscription = dock.onDidLayoutChange(() => {
      if (knownLayout.current === null) return;
      const layout = dock.toJSON();
      const serialized = JSON.stringify(layout);
      if (serialized === knownLayout.current) return;
      knownLayout.current = serialized;
      store.getState().saveLayout(layout as unknown as Record<string, unknown>);
    });
    return () => subscription.dispose();
  }, [dock, store]);

  useEffect(() => {
    const flush = () => void store.getState().flush({ keepalive: true });
    window.addEventListener("pagehide", flush);
    return () => window.removeEventListener("pagehide", flush);
  }, [store]);

  return (
    <DockviewReact
      components={components}
      theme={themeDark}
      rightHeaderActionsComponent={GroupActions}
      watermarkComponent={EmptyDock}
      onReady={(event: DockviewReadyEvent) => setDock(event.api)}
    />
  );
}
