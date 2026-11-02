"use client";

import { useStudio, useWorkspace } from "@/components/shell/providers";
import { useOpenPanels, useRevealPanel } from "@/components/shell/use-open-panels";
import type { PanelProps } from "@/core/panels/registry";

export function PanelLibraryPanel({ api }: PanelProps) {
  const { registry, dock } = useStudio();
  const open = useOpenPanels();
  const reveal = useRevealPanel();
  const experimental = useWorkspace((state) => state.appearance.experimental);
  const panels = registry.list().filter((panel) => experimental || !panel.experimental);
  const categories = [...new Set(panels.map((panel) => panel.category))];

  return (
    <div className="panel">
      {categories.map((category) => (
        <section key={category}>
          <h2 className="section-label">{category}</h2>
          <ul className="rows">
            {panels
              .filter((panel) => panel.category === category)
              .map((panel) => (
                <li key={panel.id}>
                  <label className="row" title={panel.description}>
                    <input
                      type="checkbox"
                      checked={open.has(panel.id)}
                      onChange={(event) => {
                        if (event.target.checked) reveal(panel, { besidePanel: api.id });
                        else {
                          const existing = dock?.getPanel(panel.id);
                          if (existing) dock?.removePanel(existing);
                        }
                      }}
                    />
                    <panel.icon className="size-3.5 muted" />
                    <span>{panel.title}</span>
                  </label>
                </li>
              ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
