"use client";

import { useWorkspace } from "@/components/shell/providers";
import type { PanelProps } from "@/core/panels/registry";

export function NotesPanel({ api }: PanelProps) {
  const text = useWorkspace((state) => {
    const value = state.active?.panel_states[api.id] as { text?: string } | undefined;
    return value?.text ?? "";
  });
  const setPanelState = useWorkspace((state) => state.setPanelState);

  return (
    <textarea
      className="notes"
      aria-label="Workspace notes"
      placeholder="Notes for this workspace"
      value={text}
      onChange={(event) => setPanelState(api.id, { text: event.target.value })}
    />
  );
}
