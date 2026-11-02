"use client";

import { useEffect, useState } from "react";

import { useStudio, useWorkflow } from "@/components/shell/providers";
import { Button } from "@/components/ui/button";

export function WorkflowVersionsPanel() {
  const { workflows } = useStudio();
  const id = useWorkflow((state) => state.meta?.id);
  const versions = useWorkflow((state) => state.versions);
  const [label, setLabel] = useState("");
  const actions = workflows.getState();
  const report = (error: unknown) => actions.setNotice(String(error));

  useEffect(() => {
    if (id) void workflows.getState().loadVersions().catch(report);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, workflows]);

  if (!id) return <div className="panel muted">No workflow open.</div>;

  return (
    <div className="panel">
      <form
        className="toolbar"
        onSubmit={(event) => {
          event.preventDefault();
          void actions.createVersion(label).catch(report);
          setLabel("");
        }}
      >
        <input
          className="panel-search"
          aria-label="Version label"
          placeholder="Version label"
          value={label}
          onChange={(event) => setLabel(event.target.value)}
        />
        <Button type="submit" size="xs" variant="outline">
          Save version
        </Button>
      </form>
      {versions.length === 0 && <p className="muted">No saved versions.</p>}
      <ul className="rows">
        {versions.map((version) => (
          <li key={version.number} className="row">
            <span className="row-main">
              v{version.number}
              {version.label && ` · ${version.label}`}
            </span>
            <span className="muted">{new Date(version.created_at).toLocaleString()}</span>
            <Button
              size="xs"
              variant="ghost"
              aria-label={`Restore version ${version.number}`}
              onClick={() => void actions.restoreVersion(version.number).catch(report)}
            >
              Restore
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
