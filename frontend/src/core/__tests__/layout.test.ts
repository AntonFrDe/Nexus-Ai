import type { DockviewApi } from "dockview-react";
import { describe, expect, it, vi } from "vitest";

import { loadLayout, MISSING_PANEL, sanitizeLayout } from "@/core/workspace/layout";
import { createPanelRegistry } from "@/panels";

const registry = createPanelRegistry();

function fakeDock(fromJSON = vi.fn()) {
  const added: string[] = [];
  const api = {
    clear: vi.fn(),
    fromJSON,
    getPanel: (id: string) => (added.includes(id) ? { id } : undefined),
    addPanel: (options: { id: string }) => added.push(options.id),
  };
  return { api: api as unknown as DockviewApi, added, fromJSON };
}

describe("sanitizeLayout", () => {
  it("keeps registered panels untouched", () => {
    const layout = { panels: { notes: { contentComponent: "notes" } } };
    expect(sanitizeLayout(layout, registry)).toEqual({ layout, missing: [] });
  });

  it("swaps unknown panels for a stand-in that remembers what was lost", () => {
    const { layout, missing } = sanitizeLayout(
      { panels: { p: { contentComponent: "gone-plugin" } } },
      registry,
    );
    expect(missing).toEqual(["gone-plugin"]);
    expect(layout.panels).toEqual({
      p: { contentComponent: MISSING_PANEL, params: { missingComponent: "gone-plugin" } },
    });
  });
});

describe("loadLayout", () => {
  it("builds the preset when nothing has been saved", () => {
    const { api, added } = fakeDock();
    expect(loadLayout(api, { layout: null, preset: "analytics" }, registry)).toBeNull();
    expect(added).toEqual(["cost-analytics", "execution-list"]);
  });

  it("falls back to the custom preset for an unknown key", () => {
    const { api, added } = fakeDock();
    loadLayout(api, { layout: null, preset: "nope" }, registry);
    expect(added).toContain("workspace-manager");
  });

  it("falls back to the preset and warns when a saved layout is corrupt", () => {
    const { api, added } = fakeDock(vi.fn(() => { throw new Error("bad grid"); }));
    const warning = loadLayout(api, { layout: { panels: {} }, preset: "analytics" }, registry);
    expect(warning).toMatch(/bad grid/);
    expect(added).toContain("cost-analytics");
  });
});
