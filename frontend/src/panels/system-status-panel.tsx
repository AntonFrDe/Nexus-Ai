"use client";

import { useEffect, useState } from "react";

import { apiClient, type Health } from "@/lib/api";

const POLL_MS = 5000;

type Probe = { health: Health; latency: number } | { error: string } | null;

export function SystemStatusPanel() {
  const [probe, setProbe] = useState<Probe>(null);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      const started = performance.now();
      try {
        const health = await apiClient.health();
        if (alive) setProbe({ health, latency: Math.round(performance.now() - started) });
      } catch (error) {
        if (alive) setProbe({ error: String(error) });
      }
    };
    void check();
    const interval = setInterval(check, POLL_MS);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, []);

  if (!probe) return <div className="panel muted">Checking…</div>;
  if ("error" in probe) {
    return (
      <div className="panel" role="alert">
        <p className="panel-heading">Backend unreachable</p>
        <pre className="code-block">{probe.error}</pre>
      </div>
    );
  }
  return (
    <dl className="panel facts">
      <dt>Backend</dt>
      <dd>{probe.health.status}</dd>
      <dt>Version</dt>
      <dd>{probe.health.version}</dd>
      <dt>Database</dt>
      <dd>{probe.health.database}</dd>
      <dt>Latency</dt>
      <dd>{probe.latency} ms</dd>
    </dl>
  );
}
