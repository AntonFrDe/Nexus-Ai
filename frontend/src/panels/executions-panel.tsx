"use client";

import { useEffect } from "react";

import { useExecution, useStudio, useWorkflow } from "@/components/shell/providers";
import { Button } from "@/components/ui/button";
import { isTerminal } from "@/core/workflow/execution-store";
import type { ExecutionDetail, NodeExecution } from "@/core/workflow/execution-types";
import { findType } from "@/core/workflow/graph";

const duration = (row: NodeExecution) =>
  row.ended_at
    ? `${Math.max(0, new Date(row.ended_at).getTime() - new Date(row.started_at).getTime())} ms`
    : "";

function usageText({ usage }: NodeExecution): string {
  if (!usage) return "";
  const tokens = Number(usage.input_tokens ?? 0) + Number(usage.output_tokens ?? 0);
  const fallbacks = Number(usage.fallbacks_used ?? 0);
  return [
    String(usage.model),
    tokens ? `${tokens} tokens` : "",
    usage.cost_usd ? `$${Number(usage.cost_usd).toFixed(4)}` : "",
    fallbacks ? `after ${fallbacks} fallback` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

function Json({ label, value }: { label: string; value: unknown }) {
  return (
    <>
      <h2 className="section-label">{label}</h2>
      <pre className="code-block" data-testid={`json-${label.toLowerCase()}`}>
        {value === null || value === undefined ? "null" : JSON.stringify(value, null, 2)}
      </pre>
    </>
  );
}

function Actions({ run }: { run: ExecutionDetail }) {
  const { executions } = useStudio();
  const actions = executions.getState();
  const live = run.status === "RUNNING" || run.status === "PENDING" || run.status === "VALIDATING";
  const stopped = run.status === "PAUSED" || run.status === "FAILED" || run.status === "CANCELLED";
  return (
    <div className="toolbar">
      {live && (
        <Button size="xs" variant="outline" onClick={() => void actions.act("pause")}>
          Pause
        </Button>
      )}
      {stopped && (
        <Button size="xs" variant="outline" onClick={() => void actions.act("resume")}>
          Resume
        </Button>
      )}
      {!isTerminal(run.status) && (
        <Button size="xs" variant="outline" onClick={() => void actions.act("cancel")}>
          Cancel
        </Button>
      )}
      {isTerminal(run.status) && (
        <Button size="xs" variant="outline" onClick={() => void actions.retry()}>
          Run again
        </Button>
      )}
    </div>
  );
}

function RunDetail({ run }: { run: ExecutionDetail }) {
  const { executions } = useStudio();
  const selectedNode = useExecution((state) => state.selectedNode);
  const catalog = useWorkflow((state) => state.catalog);
  const actions = executions.getState();
  const row = run.nodes.findLast((item) => item.id === selectedNode);

  return (
    <>
      <p className="panel-heading">
        {run.workflow_name} <span className="run-status" data-status={run.status}>{run.status}</span>
      </p>
      <Actions run={run} />
      {run.error && (
        <p className="field-error" role="alert">
          {run.error_node ? `${run.error_node}: ` : ""}
          {run.error}
        </p>
      )}
      {run.pending_approvals.map((approval) => (
        <div className="approval" key={String(approval.interrupt_id)}>
          <span>{String(approval.prompt)}</span>
          <div className="approval-actions">
            <Button size="xs" onClick={() => void actions.decide("approved")}>
              Approve
            </Button>
            <Button size="xs" variant="outline" onClick={() => void actions.decide("rejected")}>
              Reject
            </Button>
          </div>
        </div>
      ))}
      <table className="node-rows">
        <thead>
          <tr>
            <th>Node</th>
            <th>Status</th>
            <th>Attempt</th>
            <th>Time</th>
            <th>Model</th>
          </tr>
        </thead>
        <tbody>
          {run.nodes.map((item) => (
            <tr
              key={item.id}
              data-selected={item.id === selectedNode}
              onClick={() => actions.selectNode(item.id)}
            >
              <td>{findType(catalog, item.node_type)?.title ?? item.node_type}</td>
              <td>
                <span className="run-status" data-status={item.status}>
                  {item.status}
                </span>
              </td>
              <td>{item.attempt}</td>
              <td>{duration(item)}</td>
              <td>{usageText(item)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {row ? (
        <>
          {row.error && <p className="field-error">{row.error}</p>}
          <Json label="Input" value={row.input} />
          <Json label="Output" value={row.output} />
        </>
      ) : (
        isTerminal(run.status) && <Json label="Output" value={run.output} />
      )}
    </>
  );
}

export function ExecutionsPanel() {
  const { executions } = useStudio();
  const runs = useExecution((state) => state.executions);
  const current = useExecution((state) => state.current);
  const error = useExecution((state) => state.error);
  const refused = useExecution((state) => state.refused);
  const actions = executions.getState();

  useEffect(() => {
    void executions.getState().refresh().catch(() => undefined);
  }, [executions]);

  return (
    <div className="execution-layout">
      <div className="execution-list">
        {runs.length === 0 && <p className="muted">No runs yet.</p>}
        {runs.map((run) => (
          <button
            key={run.id}
            type="button"
            className="execution-row"
            aria-current={run.id === current?.id}
            onClick={() => void actions.select(run.id)}
          >
            <span>{run.workflow_name}</span>
            <span className="run-status" data-status={run.status}>
              {run.status}
            </span>
            <small>{new Date(run.created_at).toLocaleString()}</small>
          </button>
        ))}
      </div>
      <div className="execution-main">
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        {refused.map((issue) => (
          <p className="field-error" key={issue.message}>
            {issue.message}
          </p>
        ))}
        {current ? (
          <RunDetail run={current} />
        ) : (
          !error && <p className="muted">Select a run, or press Run on the canvas.</p>
        )}
      </div>
    </div>
  );
}
