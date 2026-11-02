"use client";

import { useExecution } from "@/components/shell/providers";
import type { ExecutionEvent } from "@/core/workflow/execution-types";

function describe(event: ExecutionEvent): string {
  const { payload } = event;
  switch (event.type) {
    case "status":
      return `Run is ${payload.status}`;
    case "log":
      return String(payload.message);
    case "node_failed":
      return `Failed: ${payload.error}`;
    case "node_retrying":
      return `Attempt ${payload.attempt} failed, retrying: ${payload.error}`;
    case "approval":
      return `Decision: ${payload.decision}`;
    default:
      return event.type.replace(/_/g, " ");
  }
}

export function ExecutionLogsPanel() {
  const events = useExecution((state) => state.events);
  const hasRun = useExecution((state) => state.current !== null);

  if (!hasRun) return <div className="panel muted">Select or start a run.</div>;
  return (
    <ol className="log-lines fill-scroll">
      {events.map((event) => (
        <li key={event.seq} data-tone={event.type === "node_failed" ? "error" : undefined}>
          <time>{new Date(event.created_at).toLocaleTimeString()}</time>
          {event.node_id && <span className="log-node">{event.node_id}</span>}
          <span>{describe(event)}</span>
        </li>
      ))}
    </ol>
  );
}
