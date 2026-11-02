"use client";

import { Copy, Download, Pencil, Plus, Trash2, Upload } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { useStudio, useWorkspace } from "@/components/shell/providers";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { FALLBACK_PRESET, PRESETS } from "@/core/workspace/presets";
import { apiClient, type WorkspaceSummary } from "@/lib/api";
import { downloadJson } from "@/lib/download";

type Editing = { mode: "create" } | { mode: "rename"; workspace: WorkspaceSummary } | null;

function WorkspaceDialog({ editing, onClose }: { editing: Editing; onClose(): void }) {
  const { store } = useStudio();
  const [error, setError] = useState<string | null>(null);
  const current = editing?.mode === "rename" ? editing.workspace : null;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const draft = {
      name: String(form.get("name")).trim(),
      description: String(form.get("description")).trim(),
    };
    try {
      if (current) await store.getState().rename(current.id, draft);
      else await store.getState().create({ ...draft, preset: String(form.get("preset")) });
      onClose();
    } catch (cause) {
      setError(String(cause));
    }
  };

  return (
    <Dialog open={editing !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{current ? "Edit workspace" : "New workspace"}</DialogTitle>
        </DialogHeader>
        <form key={current?.id ?? "new"} onSubmit={submit} className="dialog-form">
          <label>
            Name
            <Input name="name" required maxLength={120} defaultValue={current?.name} autoFocus />
          </label>
          <label>
            Description
            <Input name="description" maxLength={2000} defaultValue={current?.description} />
          </label>
          {!current && (
            <label>
              Starting layout
              <select name="preset" defaultValue={FALLBACK_PRESET}>
                {Object.keys(PRESETS).map((preset) => (
                  <option key={preset} value={preset}>
                    {preset.replace(/-/g, " ")}
                  </option>
                ))}
              </select>
            </label>
          )}
          {error && <p role="alert">{error}</p>}
          <DialogFooter>
            <Button type="submit" size="sm">
              {current ? "Save" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DeleteDialog({
  workspace,
  onClose,
}: {
  workspace: WorkspaceSummary | null;
  onClose(): void;
}) {
  const { store } = useStudio();
  return (
    <Dialog open={workspace !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete “{workspace?.name}”?</DialogTitle>
        </DialogHeader>
        <p className="muted">Its layout and notes are removed permanently.</p>
        <DialogFooter>
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => {
              if (workspace) void store.getState().remove(workspace.id);
              onClose();
            }}
          >
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function WorkspaceManagerPanel() {
  const { store } = useStudio();
  const workspaces = useWorkspace((state) => state.workspaces);
  const activeId = useWorkspace((state) => state.active?.id);
  const [editing, setEditing] = useState<Editing>(null);
  const [deleting, setDeleting] = useState<WorkspaceSummary | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const report = (error: unknown) => store.getState().setNotice(String(error));

  const exportWorkspace = async (workspace: WorkspaceSummary) => {
    await store.getState().flush();
    await downloadJson(await apiClient.exportWorkspace(workspace.id), workspace.name, "workspace");
  };

  const importFile = async (file: File) => {
    try {
      await store.getState().importDocument(JSON.parse(await file.text()));
    } catch (error) {
      report(`Import failed: ${String(error)}`);
    }
  };

  return (
    <div className="panel">
      <div className="toolbar">
        <Button size="xs" variant="outline" onClick={() => setEditing({ mode: "create" })}>
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
          aria-label="Import workspace file"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void importFile(file);
            event.target.value = "";
          }}
        />
      </div>
      <ul className="rows">
        {workspaces.map((workspace) => (
          <li key={workspace.id} className="row workspace-row" data-active={workspace.id === activeId}>
            <button
              type="button"
              className="row-main"
              title={workspace.description}
              onClick={() => void store.getState().open(workspace.id)}
            >
              {workspace.name}
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`Edit ${workspace.name}`}
              title="Edit"
              onClick={() => setEditing({ mode: "rename", workspace })}
            >
              <Pencil className="size-3.5" />
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`Duplicate ${workspace.name}`}
              title="Duplicate"
              onClick={() => void store.getState().duplicate(workspace.id).catch(report)}
            >
              <Copy className="size-3.5" />
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`Export ${workspace.name}`}
              title="Export"
              onClick={() => void exportWorkspace(workspace).catch(report)}
            >
              <Download className="size-3.5" />
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`Delete ${workspace.name}`}
              title="Delete"
              disabled={workspaces.length === 1}
              onClick={() => setDeleting(workspace)}
            >
              <Trash2 className="size-3.5" />
            </button>
          </li>
        ))}
      </ul>
      <WorkspaceDialog editing={editing} onClose={() => setEditing(null)} />
      <DeleteDialog workspace={deleting} onClose={() => setDeleting(null)} />
    </div>
  );
}
