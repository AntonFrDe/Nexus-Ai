"use client";

import { Copy, Download, Plus, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { useStudio, useWorkflow } from "@/components/shell/providers";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { WorkflowSummary } from "@/core/workflow/types";
import { apiClient } from "@/lib/api";
import { downloadJson } from "@/lib/download";

export function WorkflowsPanel() {
  const { workflows: store } = useStudio();
  const workflows = useWorkflow((state) => state.workflows);
  const meta = useWorkflow((state) => state.meta);
  const [deleting, setDeleting] = useState<WorkflowSummary | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const actions = store.getState();
  const report = (error: unknown) => actions.setNotice(String(error));

  const importFile = async (file: File) => {
    try {
      await actions.importDocument(JSON.parse(await file.text()));
    } catch (error) {
      report(`Import failed: ${String(error)}`);
    }
  };

  const exportWorkflow = async (workflow: WorkflowSummary) => {
    await actions.flush();
    await downloadJson(await apiClient.exportWorkflow(workflow.id), workflow.name, "workflow");
  };

  return (
    <div className="panel">
      <div className="toolbar">
        <Button
          size="xs"
          variant="outline"
          onClick={() => void actions.create("Untitled workflow").catch(report)}
        >
          <Plus /> New
        </Button>
        <Button size="xs" variant="outline" onClick={() => fileInput.current?.click()}>
          <Upload /> Import
        </Button>
        <input
          ref={fileInput}
          type="file"
          accept=".json,application/json"
          hidden
          aria-label="Import workflow file"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void importFile(file);
            event.target.value = "";
          }}
        />
      </div>
      {meta && (
        <div className="field">
          <span className="field-label">Name</span>
          <input
            aria-label="Workflow name"
            value={meta.name}
            maxLength={120}
            onChange={(event) => actions.rename(event.target.value, meta.description)}
          />
        </div>
      )}
      {workflows.length === 0 && <p className="muted">No workflows yet.</p>}
      <ul className="rows">
        {workflows.map((workflow) => (
          <li key={workflow.id} className="row workspace-row" data-active={workflow.id === meta?.id}>
            <button
              type="button"
              className="row-main"
              title={workflow.description}
              onClick={() => void actions.open(workflow.id).catch(report)}
            >
              {workflow.name}
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`Duplicate workflow ${workflow.name}`}
              title="Duplicate"
              onClick={() => void actions.duplicate(workflow.id).catch(report)}
            >
              <Copy className="size-3.5" />
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`Export workflow ${workflow.name}`}
              title="Export"
              onClick={() => void exportWorkflow(workflow).catch(report)}
            >
              <Download className="size-3.5" />
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`Delete workflow ${workflow.name}`}
              title="Delete"
              onClick={() => setDeleting(workflow)}
            >
              <Trash2 className="size-3.5" />
            </button>
          </li>
        ))}
      </ul>
      <Dialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete “{deleting?.name}”?</DialogTitle>
          </DialogHeader>
          <p className="muted">The workflow and all its saved versions are removed permanently.</p>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setDeleting(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                if (deleting) void actions.remove(deleting.id).catch(report);
                setDeleting(null);
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
