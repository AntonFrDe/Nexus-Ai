"use client";

import { useWorkspace } from "@/components/shell/providers";
import { useOpenPanels } from "@/components/shell/use-open-panels";
import type { SaveStatus } from "@/core/workspace/store";

const SAVE_LABELS: Record<SaveStatus, string> = {
  idle: "No changes",
  saving: "Saving…",
  saved: "All changes saved",
  error: "Not saved",
};

export function StatusBar() {
  const saveStatus = useWorkspace((state) => state.saveStatus);
  const name = useWorkspace((state) => state.active?.name);
  const notice = useWorkspace((state) => state.notice);
  const setNotice = useWorkspace((state) => state.setNotice);
  const panelCount = useOpenPanels().size;

  return (
    <footer className="status-bar">
      <span>{name}</span>
      <span>
        {panelCount} {panelCount === 1 ? "panel" : "panels"}
      </span>
      {notice && (
        <button type="button" className="status-notice" onClick={() => setNotice(null)}>
          {notice} ✕
        </button>
      )}
      <span className="status-save" data-status={saveStatus} data-testid="save-status">
        {SAVE_LABELS[saveStatus]}
      </span>
    </footer>
  );
}
