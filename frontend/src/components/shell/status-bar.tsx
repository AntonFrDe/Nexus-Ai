"use client";

import { useWorkflow, useWorkspace } from "@/components/shell/providers";
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
  const workflowName = useWorkflow((state) => state.meta?.name);
  const workflowSave = useWorkflow((state) => state.saveStatus);
  const workflowNotice = useWorkflow((state) => state.notice);
  const clearWorkflowNotice = useWorkflow((state) => state.setNotice);

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
      {workflowNotice && (
        <button
          type="button"
          className="status-notice"
          onClick={() => clearWorkflowNotice(null)}
        >
          {workflowNotice} ✕
        </button>
      )}
      <span className="status-spacer" />
      {workflowName && (
        <span
          className="status-save"
          data-status={workflowSave}
          data-testid="workflow-save-status"
        >
          {workflowName}: {SAVE_LABELS[workflowSave]}
        </span>
      )}
      <span className="status-save" data-status={saveStatus} data-testid="save-status">
        {SAVE_LABELS[saveStatus]}
      </span>
    </footer>
  );
}
