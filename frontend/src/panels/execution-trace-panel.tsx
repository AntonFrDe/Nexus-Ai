"use client";

import { useEffect, useState } from "react";

import { useExecution, useStudio } from "@/components/shell/providers";
import { Button } from "@/components/ui/button";
import type {
  Checkpoint,
  CheckpointState,
  Comparison,
  ExecutionTrace,
} from "@/core/workflow/trace-types";
import { apiClient } from "@/lib/api";

const money = (value: number | null) => (value === null ? "" : `$${value.toFixed(4)}`);

function Timeline({ trace, onSelect }: { trace: ExecutionTrace; onSelect(id: string): void }) {
  const total = Math.max(
    1,
    ...trace.spans.map((span) => span.start_ms + (span.duration_ms ?? 0)),
  );
  return (
    <ol className="timeline" aria-label="Node timeline">
      {trace.spans.map((span) => (
        <li key={span.id}>
          <button type="button" className="timeline-row" onClick={() => onSelect(span.id)}>
            <span className="timeline-label">{span.label}</span>
            <span className="timeline-track">
              <span
                className="timeline-bar"
                data-status={span.status}
                style={{
                  marginLeft: `${(span.start_ms / total) * 100}%`,
                  width: `${Math.max(0.5, ((span.duration_ms ?? 0) / total) * 100)}%`,
                }}
              />
            </span>
            <span className="timeline-meta">
              {span.duration_ms === null ? span.status : `${span.duration_ms} ms`}
              {span.attempt > 1 ? ` · attempt ${span.attempt}` : ""}
              {span.tokens ? ` · ${span.tokens} tokens` : ""}
              {span.cost_usd ? ` · ${money(span.cost_usd)}` : ""}
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}

function StateViewer({ executionId, version }: { executionId: string; version: string }) {
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [state, setState] = useState<CheckpointState | null>(null);

  useEffect(() => {
    let alive = true;
    void apiClient
      .listCheckpoints(executionId)
      .then((items) => alive && setCheckpoints(items.toReversed()))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [executionId, version]);

  return (
    <>
      <h2 className="section-label">State between nodes</h2>
      <select
        aria-label="Checkpoint"
        className="panel-search"
        defaultValue=""
        onChange={(event) =>
          event.target.value
            ? void apiClient.checkpointState(executionId, event.target.value).then(setState)
            : setState(null)
        }
      >
        <option value="">Choose a step</option>
        {checkpoints.map((item, index) => (
          <option key={item.checkpoint_id} value={item.checkpoint_id}>
            Step {index + 1}: {item.next.length ? `before ${item.next.join(", ")}` : "finished"}
          </option>
        ))}
      </select>
      {state && (
        <pre className="code-block" data-testid="checkpoint-state">
          {JSON.stringify(
            { variables: state.variables, outputs: state.outputs, errors: state.errors },
            null,
            2,
          )}
        </pre>
      )}
    </>
  );
}

function ReplayForm({ trace }: { trace: ExecutionTrace }) {
  const { executions } = useStudio();
  const [model, setModel] = useState("");
  const [temperature, setTemperature] = useState("");
  const [allowPaid, setAllowPaid] = useState(false);
  const agents = trace.spans.filter((span) => span.node_type === "core.llm_agent");

  const submit = () => {
    const changes: Record<string, unknown> = {};
    if (model.trim()) changes.model = model.trim();
    if (temperature !== "") changes.temperature = Number(temperature);
    const overrides = Object.fromEntries(agents.map((agent) => [agent.node_id, changes]));
    void executions.getState().replay(Object.keys(changes).length ? overrides : {}, allowPaid);
  };

  return (
    <>
      <h2 className="section-label">Replay</h2>
      <p className="field-help">
        Starts a new run from the recorded definition and input. This run stays as recorded.
      </p>
      {agents.length > 0 && (
        <div className="inline-form">
          <input
            aria-label="Replay model"
            placeholder="Model for LLM agents, such as Ollama/qwen3.8:27b"
            value={model}
            onChange={(event) => setModel(event.target.value)}
          />
          <input
            aria-label="Replay temperature"
            type="number"
            min={0}
            max={2}
            step={0.05}
            placeholder="Temperature"
            value={temperature}
            onChange={(event) => setTemperature(event.target.value)}
          />
        </div>
      )}
      <div className="registry-actions">
        <label className="run-paid">
          <input
            type="checkbox"
            checked={allowPaid}
            onChange={(event) => setAllowPaid(event.target.checked)}
          />
          Allow paid calls
        </label>
        <Button size="xs" variant="outline" onClick={submit}>
          Replay
        </Button>
      </div>
    </>
  );
}

function ComparisonTable({ report }: { report: Comparison }) {
  return (
    <table className="node-rows" aria-label="Run comparison">
      <thead>
        <tr>
          <th>Node</th>
          <th>This run</th>
          <th>Other run</th>
          <th>Difference</th>
        </tr>
      </thead>
      <tbody>
        {report.rows.map((row) => {
          const differences = [
            row.config_changed && "settings",
            !row.same_status && "status",
            !row.same_output && "output",
          ].filter(Boolean);
          return (
            <tr key={row.node_id} data-different={differences.length > 0}>
              <td>{row.label}</td>
              <td>
                {row.left.status ?? "not reached"} {row.left.duration_ms ?? ""}
              </td>
              <td>
                {row.right.status ?? "not reached"} {row.right.duration_ms ?? ""}
              </td>
              <td>{differences.join(", ") || "same"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Compare({ executionId }: { executionId: string }) {
  const runs = useExecution((state) => state.executions);
  const [report, setReport] = useState<Comparison | null>(null);
  const others = runs.filter((run) => run.id !== executionId);

  return (
    <>
      <h2 className="section-label">Compare with</h2>
      <select
        aria-label="Compare with"
        className="panel-search"
        defaultValue=""
        onChange={(event) =>
          event.target.value
            ? void apiClient.compareExecutions(executionId, event.target.value).then(setReport)
            : setReport(null)
        }
      >
        <option value="">Choose a run</option>
        {others.map((run) => (
          <option key={run.id} value={run.id}>
            {run.workflow_name} · {run.status} · {new Date(run.created_at).toLocaleTimeString()}
          </option>
        ))}
      </select>
      {report && <ComparisonTable report={report} />}
    </>
  );
}

export function ExecutionTracePanel() {
  const { executions } = useStudio();
  const current = useExecution((state) => state.current);
  const eventCount = useExecution((state) => state.events.length);
  const error = useExecution((state) => state.error);
  const [trace, setTrace] = useState<ExecutionTrace | null>(null);
  const id = current?.id;
  const version = `${current?.status}:${current?.nodes.length}:${eventCount}`;

  useEffect(() => {
    let alive = true;
    if (id) {
      void apiClient
        .executionTrace(id)
        .then((next) => alive && setTrace(next))
        .catch(() => undefined);
    }
    return () => {
      alive = false;
    };
  }, [id, version]);

  if (!current) return <div className="panel muted">Select or start a run.</div>;
  if (!trace || trace.execution_id !== current.id) return <div className="panel muted">Loading…</div>;

  return (
    <div className="panel">
      <p className="panel-heading">
        {current.workflow_name}{" "}
        <span className="run-status" data-status={trace.status}>
          {trace.status}
        </span>{" "}
        <span className="badge" data-testid="trace-kind">
          {trace.replay_of ? "replay" : trace.recorded ? "recorded" : "live"}
        </span>
      </p>
      {trace.replay_of && (
        <p className="field-help">
          Replay of an earlier run
          {trace.overrides ? `, with changes: ${JSON.stringify(trace.overrides)}` : ", unchanged"}.
        </p>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      {trace.failure && (
        <div className="failure" role="alert" data-testid="failure-summary">
          <strong>Failed at {trace.failure.label ?? "the run itself"}</strong>
          <span>{trace.failure.message}</span>
          {trace.failure.input !== null && trace.failure.input !== undefined && (
            <pre className="code-block">{JSON.stringify(trace.failure.input, null, 2)}</pre>
          )}
        </div>
      )}
      <Timeline
        trace={trace}
        onSelect={(spanId) => executions.getState().selectNode(spanId)}
      />
      <StateViewer executionId={current.id} version={version} />
      {trace.recorded && <ReplayForm trace={trace} />}
      <Compare executionId={current.id} />
    </div>
  );
}
