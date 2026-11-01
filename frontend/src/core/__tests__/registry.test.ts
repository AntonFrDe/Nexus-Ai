import { Square } from "lucide-react";
import { describe, expect, it } from "vitest";

import { PanelRegistry, type PanelDefinition } from "@/core/panels/registry";
import { PRESETS } from "@/core/workspace/presets";
import { createPanelRegistry } from "@/panels";

const panel = (id: string): PanelDefinition => ({
  id,
  title: id,
  description: "",
  category: "Test",
  icon: Square,
  component: () => null,
});

describe("PanelRegistry", () => {
  it("accepts new panels without touching the workspace engine", () => {
    const registry = new PanelRegistry();
    registry.register(panel("a"));
    expect(registry.get("a")?.id).toBe("a");
    expect(registry.list()).toHaveLength(1);
  });

  it("rejects duplicate ids", () => {
    const registry = new PanelRegistry();
    registry.register(panel("a"));
    expect(() => registry.register(panel("a"))).toThrow(/already registered/);
  });
});

describe("presets", () => {
  it("only reference registered panels, in placement order", () => {
    const registry = createPanelRegistry();
    for (const [name, preset] of Object.entries(PRESETS)) {
      const placed = new Set<string>();
      for (const entry of preset) {
        expect(registry.has(entry.panel), `${name}: ${entry.panel}`).toBe(true);
        if (entry.relativeTo) expect(placed.has(entry.relativeTo), name).toBe(true);
        placed.add(entry.panel);
      }
    }
  });

  it("covers the six default workspaces", () => {
    expect(Object.keys(PRESETS)).toEqual([
      "workflow-builder",
      "agent-development",
      "debug-studio",
      "execution-monitor",
      "analytics",
      "custom",
    ]);
  });
});
