"use client";

import { useMemo, useState } from "react";

import { CodeEditor } from "@/components/code-editor";
import { FieldForm, FieldSuggestions } from "@/components/forms/field-form";
import { useModels, useStudio, useWorkflow } from "@/components/shell/providers";
import { findType, type StudioNode } from "@/core/workflow/graph";
import type { PortSpec } from "@/core/workflow/types";

const TABS = ["Config", "Schema", "Runtime", "Permissions"] as const;
type Tab = (typeof TABS)[number];

function PortList({ title, ports }: { title: string; ports: PortSpec[] }) {
  if (ports.length === 0) return null;
  return (
    <>
      <h2 className="section-label">{title}</h2>
      <dl className="facts">
        {ports.map((port) => (
          <div key={port.id} className="contents">
            <dt>
              {port.label}
              {port.required ? " *" : ""}
            </dt>
            <dd>{port.multiple ? `${port.type}, many` : port.type}</dd>
          </div>
        ))}
      </dl>
    </>
  );
}

function SchemaOverride({
  label,
  value,
  onChange,
}: {
  label: string;
  value: Record<string, unknown> | null;
  onChange(value: Record<string, unknown> | null): void;
}) {
  const [text, setText] = useState(value ? JSON.stringify(value, null, 2) : "");
  const [invalid, setInvalid] = useState(false);
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <CodeEditor
        value={text}
        language="json"
        label={label}
        onChange={(next) => {
          setText(next);
          try {
            const parsed = next.trim() ? JSON.parse(next) : null;
            if (parsed !== null && (typeof parsed !== "object" || Array.isArray(parsed))) {
              throw new Error("not an object");
            }
            setInvalid(false);
            onChange(parsed);
          } catch {
            setInvalid(true);
          }
        }}
      />
      {invalid && <span className="field-error">Must be a JSON object.</span>}
    </div>
  );
}

function NodeInspector({ node }: { node: StudioNode }) {
  const { workflows } = useStudio();
  const catalog = useWorkflow((state) => state.catalog);
  const allIssues = useWorkflow((state) => state.issues);
  const [tab, setTab] = useState<Tab>("Config");
  const type = findType(catalog, node.data.nodeType);
  const { updateNode } = workflows.getState();

  if (!type) {
    return <p className="muted">Unknown node type: {node.data.nodeType}</p>;
  }
  const issues = allIssues.filter((issue) => issue.node_id === node.id);
  const configIssues = issues.filter((issue) => issue.code === "invalid_config");
  const runtimeIssues = issues.filter((issue) => issue.code === "invalid_runtime");
  const general = issues.filter((issue) => !issue.field);

  return (
    <>
      <p className="panel-heading">{type.title}</p>
      <p className="muted inspector-summary">{type.description}</p>
      <div className="field">
        <span className="field-label">Label</span>
        <input
          aria-label="Node label"
          value={node.data.label}
          placeholder={type.title}
          onChange={(event) =>
            updateNode(node.id, { label: event.target.value }, `${node.id}:label`)
          }
        />
      </div>
      {general.map((issue) => (
        <p key={issue.code + issue.message} className="field-error" data-severity={issue.severity}>
          {issue.message}
        </p>
      ))}
      <div className="inspector-tabs" role="tablist">
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </div>
      {tab === "Config" &&
        (type.fields.length ? (
          <FieldForm
            key={node.id}
            fields={type.fields}
            values={node.data.config}
            issues={configIssues}
            onChange={(config, field) => updateNode(node.id, { config }, `${node.id}:${field}`)}
          />
        ) : (
          <p className="muted">This node has no configuration.</p>
        ))}
      {tab === "Schema" && (
        <div key={node.id}>
          <PortList title="Inputs" ports={type.inputs} />
          <PortList title="Outputs" ports={type.outputs} />
          {type.executable && (
            <>
              <SchemaOverride
                label="Input schema override"
                value={node.data.input_schema}
                onChange={(input_schema) =>
                  updateNode(node.id, { input_schema }, `${node.id}:input_schema`)
                }
              />
              <SchemaOverride
                label="Output schema override"
                value={node.data.output_schema}
                onChange={(output_schema) =>
                  updateNode(node.id, { output_schema }, `${node.id}:output_schema`)
                }
              />
            </>
          )}
        </div>
      )}
      {tab === "Runtime" && (
        <FieldForm
          key={node.id}
          fields={catalog?.runtime_fields ?? []}
          values={node.data.runtime}
          issues={runtimeIssues}
          onChange={(runtime, field) =>
            updateNode(node.id, { runtime }, `${node.id}:runtime:${field}`)
          }
        />
      )}
      {tab === "Permissions" &&
        (type.permissions.length ? (
          <div className="check-list">
            <p className="muted">Stored with the node. Enforcement arrives with execution.</p>
            {type.permissions.map((permission) => (
              <label key={permission}>
                <input
                  type="checkbox"
                  checked={node.data.permissions.includes(permission)}
                  onChange={(event) =>
                    updateNode(node.id, {
                      permissions: event.target.checked
                        ? [...node.data.permissions, permission]
                        : node.data.permissions.filter((item) => item !== permission),
                    })
                  }
                />
                {permission}
              </label>
            ))}
          </div>
        ) : (
          <p className="muted">This node needs no permissions.</p>
        ))}
    </>
  );
}

export function NodeInspectorPanel() {
  const { workflows } = useStudio();
  const selectedNodes = useWorkflow((state) => state.nodes.filter((node) => node.selected).length);
  const node = useWorkflow((state) => {
    const selected = state.nodes.filter((candidate) => candidate.selected);
    return selected.length === 1 ? selected[0] : null;
  });
  const edge = useWorkflow((state) => state.edges.find((candidate) => candidate.selected) ?? null);
  const models = useModels((state) => state.models);
  const suggestions = useMemo(
    () => ({ model: models.map((item) => `${item.provider_name}/${item.model_id}`) }),
    [models],
  );

  if (node) {
    return (
      <div className="panel">
        <FieldSuggestions.Provider value={suggestions}>
          <NodeInspector key={node.id} node={node} />
        </FieldSuggestions.Provider>
      </div>
    );
  }
  if (edge) {
    return (
      <div className="panel">
        <p className="panel-heading">Connection</p>
        <p className="muted inspector-summary">{edge.data?.portType ?? "any"}</p>
        <div className="field">
          <span className="field-label">Label</span>
          <input
            aria-label="Edge label"
            value={typeof edge.label === "string" ? edge.label : ""}
            onChange={(event) => workflows.getState().updateEdgeLabel(edge.id, event.target.value)}
          />
        </div>
      </div>
    );
  }
  return (
    <div className="panel muted">
      {selectedNodes > 1 ? `${selectedNodes} nodes selected` : "Select a node or connection."}
    </div>
  );
}
