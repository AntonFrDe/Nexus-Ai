"use client";

import { useState } from "react";

import { useStudio, useWorkflow } from "@/components/shell/providers";
import { NodeIcon } from "@/components/workflow/node-icon";
import { NODE_DRAG_TYPE } from "@/panels/workflow-canvas-panel";

export function NodeLibraryPanel() {
  const { workflows } = useStudio();
  const catalog = useWorkflow((state) => state.catalog);
  const hasDocument = useWorkflow((state) => state.meta !== null);
  const [query, setQuery] = useState("");

  const needle = query.trim().toLowerCase();
  const types = (catalog?.node_types ?? []).filter((type) =>
    `${type.title} ${type.description} ${type.category}`.toLowerCase().includes(needle),
  );
  const categories = [...new Set(types.map((type) => type.category))];

  return (
    <div className="panel">
      <input
        className="panel-search"
        aria-label="Search node types"
        placeholder="Search nodes"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {!hasDocument && <p className="muted">Open a workflow to add nodes.</p>}
      {types.length === 0 && <p className="muted">No node matches.</p>}
      {categories.map((category) => (
        <section key={category}>
          <h2 className="section-label">{category}</h2>
          <ul className="rows">
            {types
              .filter((type) => type.category === category)
              .map((type) => (
                <li key={type.type}>
                  <button
                    type="button"
                    className="row row-button"
                    draggable={hasDocument}
                    disabled={!hasDocument}
                    title={type.description}
                    onClick={() => workflows.getState().addNode(type.type)}
                    onDragStart={(event) =>
                      event.dataTransfer.setData(NODE_DRAG_TYPE, type.type)
                    }
                  >
                    <NodeIcon name={type.icon} className="size-3.5 muted" />
                    <span>{type.title}</span>
                  </button>
                </li>
              ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
