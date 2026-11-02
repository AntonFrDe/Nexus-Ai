"use client";

import { Plus, Trash2 } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import { FieldForm } from "@/components/forms/field-form";
import { useModels, useStudio } from "@/components/shell/providers";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { Provider, RegisteredModel } from "@/core/models/types";

const CAPABILITY_LABELS: Record<string, string> = {
  temperature: "Temperature",
  top_p: "Top P",
  top_k: "Top K",
  max_tokens: "Max tokens",
  reasoning_effort: "Reasoning effort",
  streaming: "Streaming",
  tool_calling: "Tool calling",
  structured_output: "Structured output",
};

function AddProviderDialog({ open, onClose }: { open: boolean; onClose(): void }) {
  const { models } = useStudio();
  const types = useModels((state) => state.types);
  const [typeId, setTypeId] = useState("ollama");
  const type = types.find((item) => item.id === typeId);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const added = await models.getState().addProvider({
      type: typeId,
      name: String(form.get("name")).trim(),
      endpoint: String(form.get("endpoint") ?? "").trim(),
      apiKey: String(form.get("apiKey") ?? ""),
    });
    if (added) onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add provider</DialogTitle>
        </DialogHeader>
        <form key={typeId} onSubmit={submit} className="dialog-form">
          <label>
            Type
            <select value={typeId} onChange={(event) => setTypeId(event.target.value)}>
              {types.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
          {type && <p className="muted">{type.description}</p>}
          <label>
            Name
            <Input name="name" required maxLength={120} defaultValue={type?.title} />
          </label>
          <label>
            Endpoint
            <Input
              name="endpoint"
              required={type?.endpoint_required}
              placeholder={type?.default_endpoint ?? "https://…"}
            />
          </label>
          {type && type.auth !== "none" && (
            <label>
              API key
              <Input
                name="apiKey"
                type="password"
                autoComplete="off"
                required={type.auth === "api_key"}
              />
            </label>
          )}
          <DialogFooter>
            <Button type="submit" size="sm">
              Add
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ModelDetail({ model, provider }: { model: RegisteredModel; provider: Provider }) {
  const { models } = useStudio();
  const actions = models.getState();
  const result = useModels((state) => state.modelTest);
  const busy = useModels((state) => state.busy);
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="model-detail">
      <p className="panel-heading">{model.model_id}</p>
      <p className="muted">
        {model.context_window ? `${model.context_window.toLocaleString()} tokens context` : "Context unknown"}
        {model.input_cost_per_mtok !== null &&
          ` · $${model.input_cost_per_mtok} in, $${model.output_cost_per_mtok} out per million tokens`}
      </p>
      <h2 className="section-label">Capabilities</h2>
      <div className="capability-grid">
        {Object.entries(CAPABILITY_LABELS).map(([name, label]) => (
          <label key={name}>
            <input
              type="checkbox"
              checked={model.capabilities[name] ?? false}
              onChange={(event) =>
                void actions.updateModel(model.id, {
                  capability_overrides: {
                    ...model.capability_overrides,
                    [name]: event.target.checked,
                  },
                })
              }
            />
            {label}
          </label>
        ))}
      </div>
      {model.parameter_fields.length > 0 && (
        <>
          <h2 className="section-label">Default parameters</h2>
          <FieldForm
            key={model.id + model.parameter_fields.length}
            fields={model.parameter_fields}
            values={model.defaults}
            onChange={(defaults) => void actions.updateModel(model.id, { defaults })}
          />
        </>
      )}
      <div className="registry-actions">
        <Button
          size="xs"
          variant="outline"
          disabled={busy}
          onClick={() =>
            provider.paid ? setConfirming(true) : void actions.testModel(model.id, false)
          }
        >
          Test model
        </Button>
        <Button size="xs" variant="ghost" onClick={() => void actions.removeModel(model.id)}>
          Remove
        </Button>
      </div>
      {result && (
        <p className={result.ok ? "result-ok" : "result-bad"} role="status">
          {result.ok
            ? `${result.served_by} answered in ${result.latency_ms} ms: ${result.text}`
            : result.message}
        </p>
      )}
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send a paid request?</DialogTitle>
          </DialogHeader>
          <p className="muted">
            This makes one short real call to {provider.name}, which may be billed to your account.
          </p>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setConfirming(false);
                void actions.testModel(model.id, true);
              }}
            >
              Send
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ProviderDetail({ provider }: { provider: Provider }) {
  const { models } = useStudio();
  const actions = models.getState();
  const all = useModels((state) => state.models);
  const selectedModel = useModels((state) => state.selectedModel);
  const connection = useModels((state) => state.connection);
  const types = useModels((state) => state.types);
  const busy = useModels((state) => state.busy);
  const backend = useModels((state) => state.secretBackend);
  const [key, setKey] = useState("");
  const [manualModel, setManualModel] = useState("");
  const [deleting, setDeleting] = useState(false);

  const type = types.find((item) => item.id === provider.type);
  const owned = useMemo(
    () => all.filter((model) => model.provider_id === provider.id),
    [all, provider.id],
  );
  const selected = owned.find((model) => model.id === selectedModel);

  return (
    <>
      <p className="panel-heading">{provider.name}</p>
      <p className="muted">
        {type?.title} · {provider.endpoint ?? "default endpoint"}
      </p>
      <div className="registry-actions">
        <Button
          size="xs"
          variant="outline"
          disabled={busy}
          onClick={() => void actions.testConnection(provider.id)}
        >
          Test connection
        </Button>
        {type?.discovery !== "manual" && (
          <Button
            size="xs"
            variant="outline"
            disabled={busy}
            onClick={() => void actions.discover(provider.id)}
          >
            Discover models
          </Button>
        )}
        <Button
          size="xs"
          variant="ghost"
          onClick={() => void actions.setEnabled(provider.id, !provider.enabled)}
        >
          {provider.enabled ? "Disable" : "Enable"}
        </Button>
        <Button size="xs" variant="ghost" aria-label="Delete provider" onClick={() => setDeleting(true)}>
          <Trash2 />
        </Button>
      </div>
      {connection && (
        <p className={connection.ok ? "result-ok" : "result-bad"} role="status">
          {connection.ok
            ? `Connected in ${connection.latency_ms} ms, ${connection.models_found} models found`
            : connection.message}
        </p>
      )}
      {type?.auth !== "none" && (
        <form
          className="inline-form"
          onSubmit={(event) => {
            event.preventDefault();
            void actions.setKey(provider.id, key);
            setKey("");
          }}
        >
          <input
            type="password"
            aria-label="API key"
            autoComplete="off"
            required
            placeholder={provider.has_secret ? "Key stored; enter a new one to replace it" : "API key"}
            value={key}
            onChange={(event) => setKey(event.target.value)}
          />
          <Button type="submit" size="xs" variant="outline">
            Save key
          </Button>
        </form>
      )}
      {type?.auth !== "none" && (
        <p className="field-help">
          Keys are encrypted, with the master key in{" "}
          {backend === "keychain" ? "your system keychain" : "a private file"}. They are never shown
          again.
        </p>
      )}
      <h2 className="section-label">Models</h2>
      <form
        className="inline-form"
        onSubmit={(event) => {
          event.preventDefault();
          void actions.addModel(provider.id, manualModel.trim());
          setManualModel("");
        }}
      >
        <input
          aria-label="Model identifier"
          required
          placeholder="Add a model by identifier"
          value={manualModel}
          onChange={(event) => setManualModel(event.target.value)}
        />
        <Button type="submit" size="xs" variant="outline" aria-label="Add model">
          <Plus />
        </Button>
      </form>
      {owned.length === 0 && <p className="muted">No models registered.</p>}
      <ul className="rows">
        {owned.map((model) => (
          <li key={model.id} className="row workspace-row" data-active={model.id === selectedModel}>
            <button
              type="button"
              className="row-main"
              onClick={() => actions.selectModel(model.id)}
            >
              {model.model_id}
            </button>
          </li>
        ))}
      </ul>
      {selected && <ModelDetail key={selected.id} model={selected} provider={provider} />}
      <Dialog open={deleting} onOpenChange={setDeleting}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete “{provider.name}”?</DialogTitle>
          </DialogHeader>
          <p className="muted">Its models and stored API key are removed.</p>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setDeleting(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                setDeleting(false);
                void actions.removeProvider(provider.id);
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function ModelRegistryPanel() {
  const { models } = useStudio();
  const providers = useModels((state) => state.providers);
  const selectedProvider = useModels((state) => state.selectedProvider);
  const error = useModels((state) => state.error);
  const [adding, setAdding] = useState(false);
  const actions = models.getState();
  const provider = providers.find((item) => item.id === selectedProvider);

  return (
    <div className="registry-layout">
      <div className="registry-list">
        <div className="toolbar">
          <Button size="xs" variant="outline" onClick={() => setAdding(true)}>
            <Plus /> Provider
          </Button>
        </div>
        {providers.length === 0 && <p className="muted">No providers yet.</p>}
        <ul className="rows">
          {providers.map((item) => (
            <li key={item.id} className="row workspace-row" data-active={item.id === selectedProvider}>
              <button
                type="button"
                className="row-main"
                onClick={() => actions.selectProvider(item.id)}
              >
                {item.name}
              </button>
              {!item.enabled && <span className="badge">off</span>}
              {item.paid && <span className="badge">paid</span>}
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
        {provider ? (
          <ProviderDetail key={provider.id} provider={provider} />
        ) : (
          <p className="muted">Add a provider, or select one to manage its models.</p>
        )}
      </div>
      <AddProviderDialog open={adding} onClose={() => setAdding(false)} />
    </div>
  );
}
