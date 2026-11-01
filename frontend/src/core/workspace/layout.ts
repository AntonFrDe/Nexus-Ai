import type { DockviewApi, SerializedDockview } from "dockview-react";

import type { PanelRegistry } from "@/core/panels/registry";
import { presetFor, type Preset } from "@/core/workspace/presets";

export const MISSING_PANEL = "missing-panel";

interface SerializedPanel {
  contentComponent?: string;
  params?: Record<string, unknown>;
}

/**
 * Swaps panels whose component is no longer registered for a visible stand-in, so an
 * imported layout or a removed plugin never prevents a workspace from opening.
 */
export function sanitizeLayout(
  layout: Record<string, unknown>,
  registry: PanelRegistry,
): { layout: Record<string, unknown>; missing: string[] } {
  const panels = (layout.panels ?? {}) as Record<string, SerializedPanel>;
  const missing: string[] = [];
  const sanitized = Object.fromEntries(
    Object.entries(panels).map(([id, panel]) => {
      const component = panel.contentComponent ?? "";
      if (registry.has(component) || component === MISSING_PANEL) return [id, panel];
      missing.push(component);
      return [
        id,
        {
          ...panel,
          contentComponent: MISSING_PANEL,
          params: { ...panel.params, missingComponent: component },
        },
      ];
    }),
  );
  return { layout: { ...layout, panels: sanitized }, missing };
}

export function applyPreset(api: DockviewApi, preset: Preset, registry: PanelRegistry): void {
  for (const entry of preset) {
    const definition = registry.get(entry.panel);
    if (!definition) continue;
    const reference = entry.relativeTo && api.getPanel(entry.relativeTo);
    const horizontal = entry.direction === "left" || entry.direction === "right";
    api.addPanel({
      id: definition.id,
      component: definition.id,
      title: definition.title,
      position:
        reference && entry.direction
          ? { referencePanel: reference, direction: entry.direction }
          : undefined,
      ...(entry.size && horizontal ? { initialWidth: entry.size } : {}),
      ...(entry.size && !horizontal ? { initialHeight: entry.size } : {}),
    });
  }
}

/** Replaces the dock contents with a workspace; returns a warning if the layout was unusable. */
export function loadLayout(
  api: DockviewApi,
  workspace: { layout: Record<string, unknown> | null; preset: string | null },
  registry: PanelRegistry,
): string | null {
  api.clear();
  if (!workspace.layout) {
    applyPreset(api, presetFor(workspace.preset), registry);
    return null;
  }
  const { layout, missing } = sanitizeLayout(workspace.layout, registry);
  try {
    api.fromJSON(layout as unknown as SerializedDockview);
  } catch (error) {
    api.clear();
    applyPreset(api, presetFor(workspace.preset), registry);
    return `Saved layout could not be restored (${String(error)}); showing the preset instead.`;
  }
  return missing.length ? `Unavailable panels: ${[...new Set(missing)].join(", ")}` : null;
}
