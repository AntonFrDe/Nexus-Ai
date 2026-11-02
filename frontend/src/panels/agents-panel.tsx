"use client";

import { Copy, Plus, Trash2 } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import { FieldForm, FieldSuggestions } from "@/components/forms/field-form";
import { useAgents, useModels, useStudio, useWorkspace } from "@/components/shell/providers";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { Agent, Runtime } from "@/core/models/agent-types";

function NewAgentDialog({ open, onClose }: { open: boolean; onClose(): void }) {
  const { agents } = useStudio();
  const templates = useAgents((state) => state.templates);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const template = String(form.get("template"));
    await agents.getState().create(String(form.get("name")).trim(), template || null);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New agent</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="dialog-form">
          <label>
            Name
            <Input name="name" required maxLength={120} autoFocus />
          </label>
          <label>
            Template
            <select name="template" defaultValue="">
              <option value="">Blank</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </label>
          <DialogFooter>
            <Button type="submit" size="sm">
              Create
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AgentEditor({ agent }: { agent: Agent }) {
  const { agents } = useStudio();
  const actions = agents.getState();
  const fields = useAgents((state) => state.fields);
  const versions = useAgents((state) => state.versions);
  const [draft, setDraft] = useState(agent.definition);
  const [name, setName] = useState(agent.name);
  const trimmedName = name.trim();
  const dirty =
    trimmedName !== agent.name || JSON.stringify(draft) !== JSON.stringify(agent.definition);

  return (
    <>
      <p className="panel-heading">
        {agent.name} <span className="badge">v{agent.version}</span>
      </p>
      <p className="muted inspector-summary" data-testid="agent-id">
        {agent.id}
      </p>
      <div className="registry-actions">
        <Button size="xs" variant="outline" onClick={() => void actions.clone(agent.id)}>
          <Copy /> Clone
        </Button>
        <Button
          size="xs"
          variant="ghost"
          aria-label="Delete agent"
          onClick={() => void actions.remove(agent.id)}
        >
          <Trash2 />
        </Button>
      </div>
      <div className="field">
        <span className="field-label">Name</span>
        <input
          aria-label="Agent name"
          value={name}
          maxLength={120}
          onChange={(event) => setName(event.target.value)}
        />
      </div>
      <FieldForm
        fields={fields}
        values={draft}
        onChange={(values) => setDraft(values)}
      />
      <div className="registry-actions">
        <Button
          size="xs"
          disabled={!dirty || !trimmedName}
          onClick={() => void actions.save(agent.id, trimmedName, draft)}
        >
          Save version
        </Button>
      </div>
      <h2 className="section-label">Versions</h2>
      <ul className="rows">
        {versions.map((version) => (
          <li key={version.number} className="row">
            <span className="row-main">v{version.number}</span>
            <span className="muted">{new Date(version.created_at).toLocaleString()}</span>
            {version.number !== agent.version && (
              <Button
                size="xs"
                variant="ghost"
                aria-label={`Restore agent version ${version.number}`}
                onClick={() => void actions.restore(agent.id, version.number)}
              >
                Restore
              </Button>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

function RuntimeRow({ runtime }: { runtime: Runtime }) {
  const { agents } = useStudio();
  const [key, setKey] = useState("");
  const enabled = Object.entries(runtime.capabilities)
    .filter(([, value]) => value)
    .map(([name]) => name.replace(/_/g, " "));

  return (
    <div className="runtime-row">
      <span className="runtime-title">
        {runtime.title}
        {runtime.paid && <span className="badge">paid</span>}
        <span className="badge">{runtime.health.ready ? "ready" : "not installed"}</span>
      </span>
      <span className="field-help">{runtime.description}</span>
      <span className="field-help">{enabled.length ? enabled.join(", ") : "No extra capabilities"}</span>
      {!runtime.health.ready && <span className="field-help">{runtime.health.message}</span>}
      {runtime.needs_secret && (
        <form
          className="inline-form"
          onSubmit={(event) => {
            event.preventDefault();
            void agents.getState().setRuntimeKey(runtime.id, key);
            setKey("");
          }}
        >
          <input
            type="password"
            aria-label={`${runtime.title} API key`}
            autoComplete="off"
            required
            placeholder={runtime.has_secret ? "Key stored; enter a new one to replace it" : "API key"}
            value={key}
            onChange={(event) => setKey(event.target.value)}
          />
          <Button type="submit" size="xs" variant="outline">
            Save key
          </Button>
        </form>
      )}
    </div>
  );
}

export function AgentsPanel() {
  const { agents } = useStudio();
  const list = useAgents((state) => state.agents);
  const selected = useAgents((state) => state.selected);
  const runtimes = useAgents((state) => state.runtimes);
  const error = useAgents((state) => state.error);
  const models = useModels((state) => state.models);
  const experimental = useWorkspace((state) => state.appearance.experimental);
  const [adding, setAdding] = useState(false);
  const agent = list.find((item) => item.id === selected);
  const suggestions = useMemo(
    () => ({
      model: models.map((item) => `${item.provider_name}/${item.model_id}`),
      runtime: runtimes.map((item) => item.id),
    }),
    [models, runtimes],
  );

  return (
    <div className="registry-layout">
      <div className="registry-list">
        <div className="toolbar">
          <Button size="xs" variant="outline" onClick={() => setAdding(true)}>
            <Plus /> Agent
          </Button>
        </div>
        {list.length === 0 && <p className="muted">No agents yet.</p>}
        <ul className="rows">
          {list.map((item) => (
            <li key={item.id} className="row workspace-row" data-active={item.id === selected}>
              <button
                type="button"
                className="row-main"
                onClick={() => void agents.getState().select(item.id)}
              >
                {item.name}
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div className="registry-main">
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        {agent ? (
          <FieldSuggestions.Provider value={suggestions}>
            <AgentEditor key={`${agent.id}:${agent.version}`} agent={agent} />
          </FieldSuggestions.Provider>
        ) : (
          <p className="muted">Create an agent, or select one to edit it.</p>
        )}
        {experimental && (
          <>
            <h2 className="section-label">Runtimes</h2>
            {runtimes.map((runtime) => (
              <RuntimeRow key={runtime.id} runtime={runtime} />
            ))}
          </>
        )}
      </div>
      <NewAgentDialog open={adding} onClose={() => setAdding(false)} />
    </div>
  );
}
