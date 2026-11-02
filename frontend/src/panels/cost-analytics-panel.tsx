"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useStudio, useWorkspace } from "@/components/shell/providers";
import type { Analytics, LangfuseConfig } from "@/core/workflow/trace-types";
import { apiClient } from "@/lib/api";

const PERIODS = [7, 30, 90];

const cost = ({ cost_usd, unpriced }: { cost_usd: number; unpriced: number }) =>
  unpriced ? `$${cost_usd.toFixed(4)} + ${unpriced} unpriced` : `$${cost_usd.toFixed(4)}`;

function UsageTable({
  title,
  rows,
}: {
  title: string;
  rows: { name: string; calls: number; tokens: number; cost: string }[];
}) {
  if (rows.length === 0) return null;
  return (
    <>
      <h2 className="section-label">{title}</h2>
      <table className="node-rows data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Calls</th>
            <th>Tokens</th>
            <th>Cost</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name}>
              <td>{row.name}</td>
              <td>{row.calls}</td>
              <td>{row.tokens.toLocaleString()}</td>
              <td>{row.cost}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function LangfuseSettings() {
  const [config, setConfig] = useState<LangfuseConfig | null>(null);
  const [secret, setSecret] = useState("");
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    void apiClient.langfuseConfig().then(setConfig).catch(() => undefined);
  }, []);

  if (!config) return null;

  const save = async () => {
    setResult(null);
    const next = { ...config };
    if (secret) {
      await apiClient.storeSecret("langfuse.secret-key", secret);
      next.secret_name = "langfuse.secret-key";
      setSecret("");
    }
    setConfig(await apiClient.saveLangfuseConfig(next));
    const check = await apiClient.checkLangfuse();
    setResult(check.message);
  };

  return (
    <>
      <h2 className="section-label">Langfuse export</h2>
      <p className="field-help">
        Off by default. When on, finished runs are sent to this host. Prompts and outputs stay
        local unless you include them.
      </p>
      <div className="check-list">
        <label>
          <input
            type="checkbox"
            checked={config.enabled}
            onChange={(event) => setConfig({ ...config, enabled: event.target.checked })}
          />
          Export finished runs
        </label>
        <label>
          <input
            type="checkbox"
            checked={config.include_content}
            onChange={(event) => setConfig({ ...config, include_content: event.target.checked })}
          />
          Include prompts and outputs
        </label>
      </div>
      <div className="inline-form">
        <input
          aria-label="Langfuse host"
          value={config.host}
          onChange={(event) => setConfig({ ...config, host: event.target.value })}
        />
        <input
          aria-label="Langfuse public key"
          placeholder="Public key"
          value={config.public_key}
          onChange={(event) => setConfig({ ...config, public_key: event.target.value })}
        />
        <input
          aria-label="Langfuse secret key"
          type="password"
          autoComplete="off"
          placeholder={config.secret_name ? "Key stored" : "Secret key"}
          value={secret}
          onChange={(event) => setSecret(event.target.value)}
        />
      </div>
      <div className="registry-actions">
        <Button size="xs" variant="outline" onClick={() => void save().catch((e) => setResult(String(e)))}>
          Save and check
        </Button>
      </div>
      {result && <p role="status">{result}</p>}
    </>
  );
}

export function CostAnalyticsPanel() {
  const { executions } = useStudio();
  const experimental = useWorkspace((state) => state.appearance.experimental);
  const [days, setDays] = useState(30);
  const [report, setReport] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      apiClient
        .analytics(days)
        .then(setReport)
        .catch((cause) => setError(String(cause)));
    void load();
    let last = executions.getState().executions;
    return executions.subscribe((state) => {
      if (state.executions !== last) {
        last = state.executions;
        void load();
      }
    });
  }, [days, executions]);

  if (error) return <div className="panel field-error">{error}</div>;
  if (!report) return <div className="panel muted">Loading…</div>;
  const { totals } = report;
  const tokens = (row: { input_tokens: number; output_tokens: number }) =>
    row.input_tokens + row.output_tokens;

  return (
    <div className="panel">
      <div className="toolbar" role="group" aria-label="Period">
        {PERIODS.map((period) => (
          <Button
            key={period}
            size="xs"
            variant={period === days ? "default" : "outline"}
            onClick={() => setDays(period)}
          >
            {period} days
          </Button>
        ))}
      </div>
      <dl className="stat-row">
        <div>
          <dt>Runs</dt>
          <dd>{report.runs}</dd>
        </div>
        <div>
          <dt>Failed</dt>
          <dd>{report.statuses.FAILED ?? 0}</dd>
        </div>
        <div>
          <dt>Model calls</dt>
          <dd>{totals.calls}</dd>
        </div>
        <div>
          <dt>Tokens</dt>
          <dd>{tokens(totals).toLocaleString()}</dd>
        </div>
        <div>
          <dt>Cost</dt>
          <dd data-testid="total-cost">{cost(totals)}</dd>
        </div>
      </dl>
      <UsageTable
        title="By model"
        rows={report.by_model.map((row) => ({
          name: row.model,
          calls: row.calls,
          tokens: tokens(row),
          cost: cost(row),
        }))}
      />
      <UsageTable
        title="By workflow"
        rows={report.by_workflow.map((row) => ({
          name: row.workflow,
          calls: row.calls,
          tokens: tokens(row),
          cost: cost(row),
        }))}
      />
      <UsageTable
        title="By day"
        rows={report.by_day.map((row) => ({
          name: row.day,
          calls: row.calls,
          tokens: tokens(row),
          cost: cost(row),
        }))}
      />
      {report.top_errors.length > 0 && (
        <>
          <h2 className="section-label">Most frequent errors</h2>
          <ul className="rows-flat error-list">
            {report.top_errors.map((item) => (
              <li key={item.error}>
                {item.count} × {item.error}
              </li>
            ))}
          </ul>
        </>
      )}
      {experimental && <LangfuseSettings />}
    </div>
  );
}
