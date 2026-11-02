export interface PresetPanel {
  panel: string;
  /** Placement relative to a panel listed earlier; the first entry fills the dock. */
  relativeTo?: string;
  direction?: "left" | "right" | "above" | "below" | "within";
  size?: number;
}

export type Preset = PresetPanel[];

export const PRESETS: Record<string, Preset> = {
  "workflow-builder": [
    { panel: "workflow-canvas" },
    { panel: "workflows", relativeTo: "workflow-canvas", direction: "left", size: 280 },
    { panel: "node-library", relativeTo: "workflows", direction: "within" },
    { panel: "workflow-versions", relativeTo: "workflow-canvas", direction: "right", size: 360 },
    { panel: "node-inspector", relativeTo: "workflow-versions", direction: "within" },
    { panel: "problems", relativeTo: "workflow-canvas", direction: "below", size: 280 },
    { panel: "execution-logs", relativeTo: "problems", direction: "within" },
    { panel: "execution-list", relativeTo: "problems", direction: "within" },
    { panel: "notes", relativeTo: "problems", direction: "within" },
  ],
  "agent-development": [
    { panel: "agent-registry" },
    { panel: "notes", relativeTo: "agent-registry", direction: "right" },
    { panel: "model-registry", relativeTo: "notes", direction: "right", size: 300 },
  ],
  "debug-studio": [
    { panel: "execution-trace" },
    { panel: "layout-inspector", relativeTo: "execution-trace", direction: "right", size: 340 },
    { panel: "system-status", relativeTo: "layout-inspector", direction: "within" },
    { panel: "execution-logs", relativeTo: "execution-trace", direction: "below", size: 220 },
  ],
  "execution-monitor": [
    { panel: "execution-list" },
    { panel: "execution-logs", relativeTo: "execution-list", direction: "right" },
    { panel: "system-status", relativeTo: "execution-list", direction: "below", size: 200 },
  ],
  analytics: [
    { panel: "cost-analytics" },
    { panel: "execution-list", relativeTo: "cost-analytics", direction: "right", size: 360 },
  ],
  custom: [
    { panel: "workspace-manager" },
    { panel: "panel-library", relativeTo: "workspace-manager", direction: "right", size: 300 },
  ],
};

export const FALLBACK_PRESET = "custom";

export const presetFor = (key: string | null): Preset =>
  PRESETS[key ?? FALLBACK_PRESET] ?? PRESETS[FALLBACK_PRESET];
