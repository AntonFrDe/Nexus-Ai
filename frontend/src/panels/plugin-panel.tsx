"use client";

import { Puzzle } from "lucide-react";
import { useEffect, useRef } from "react";

import { useStudio } from "@/components/shell/providers";
import type { PanelDefinition } from "@/core/panels/registry";
import type { PluginPanel as Contribution } from "@/core/models/plugin-types";

const MAX_STATE_BYTES = 100_000;

/** The whole API a plugin page gets. It has no route to the app, the backend or other plugins. */
function PluginFrame({ contribution }: { contribution: Contribution }) {
  const { store } = useStudio();
  const frame = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const respond = async (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow) return;
      const { nexus, id, method, params } = event.data ?? {};
      if (!nexus) return;
      const state = store.getState();
      const key = contribution.id;
      let result: unknown = null;
      if (method === "getContext") {
        result = { workspace: state.active?.name ?? "" };
      } else if (method === "getState") {
        result = state.active?.panel_states[key] ?? null;
      } else if (method === "setState" && JSON.stringify(params ?? null).length <= MAX_STATE_BYTES) {
        state.setPanelState(key, params);
        result = true;
      }
      // An opaque origin cannot be addressed by name, and the reply holds nothing private.
      frame.current?.contentWindow?.postMessage({ id, result }, "*");
    };
    window.addEventListener("message", respond);
    return () => window.removeEventListener("message", respond);
  }, [contribution.id, store]);

  return (
    <iframe
      ref={frame}
      className="plugin-frame"
      title={contribution.title}
      sandbox="allow-scripts"
      src={`/api/plugins/${contribution.plugin_id}/panels/${contribution.id}`}
    />
  );
}

export function pluginPanelDefinition(contribution: Contribution): PanelDefinition {
  return {
    id: contribution.id,
    title: contribution.title,
    description: contribution.description,
    category: contribution.category,
    icon: Puzzle,
    component: function PluginPanelHost() {
      return <PluginFrame contribution={contribution} />;
    },
  };
}
