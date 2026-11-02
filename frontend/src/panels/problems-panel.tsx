"use client";

import { CircleAlert, TriangleAlert } from "lucide-react";

import { useStudio, useWorkflow } from "@/components/shell/providers";

export function ProblemsPanel() {
  const { workflows } = useStudio();
  const issues = useWorkflow((state) => state.issues);
  const hasDocument = useWorkflow((state) => state.meta !== null);

  if (!hasDocument) return <div className="panel muted">No workflow open.</div>;
  if (issues.length === 0) return <div className="panel muted">No problems found.</div>;

  const select = (id: string) => {
    const { nodes, onNodesChange } = workflows.getState();
    onNodesChange(
      nodes.map((node) => ({ id: node.id, type: "select", selected: node.id === id })),
    );
  };

  return (
    <ul className="panel rows-flat">
      {issues.map((issue, index) => (
        <li key={`${issue.code}-${issue.node_id ?? issue.edge_id}-${index}`}>
          <button
            type="button"
            className="row row-button"
            disabled={!issue.node_id}
            onClick={() => issue.node_id && select(issue.node_id)}
          >
            {issue.severity === "error" ? (
              <CircleAlert className="size-3.5 issue-error" aria-label="Error" />
            ) : (
              <TriangleAlert className="size-3.5 issue-warning" aria-label="Warning" />
            )}
            <span>{issue.message}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
