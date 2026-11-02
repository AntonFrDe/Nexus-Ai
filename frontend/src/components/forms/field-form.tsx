"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";

import { CodeEditor } from "@/components/code-editor";
import type { FieldSpec, Issue } from "@/core/workflow/types";

type Values = Record<string, unknown>;

interface Props {
  fields: FieldSpec[];
  values: Values;
  issues?: Issue[];
  onChange(values: Values, field: string): void;
}

const isVisible = (field: FieldSpec, values: Values) =>
  !field.visible_when || field.visible_when.equals.includes(values[field.visible_when.field]);

function emptyValue(field: FieldSpec): unknown {
  if (field.default !== null && field.default !== undefined) return structuredClone(field.default);
  return field.kind === "object" ? {} : "";
}

function JsonField({ field, value, onChange }: FieldProps) {
  const [text, setText] = useState(() =>
    value === undefined || value === null ? "" : JSON.stringify(value, null, 2),
  );
  const [invalid, setInvalid] = useState(false);
  return (
    <>
      <CodeEditor
        value={text}
        language="json"
        label={field.label}
        onChange={(next) => {
          setText(next);
          try {
            onChange(next.trim() ? JSON.parse(next) : undefined);
            setInvalid(false);
          } catch {
            setInvalid(true);
          }
        }}
      />
      {invalid && <span className="field-error">Not valid JSON; the last valid value is kept.</span>}
    </>
  );
}

function ArrayField({ field, value, onChange }: FieldProps) {
  const items = Array.isArray(value) ? value : [];
  const item = field.item!;
  return (
    <div className="array-field">
      {items.map((entry, index) => (
        <div className="array-item" key={index}>
          <div className="array-item-body">
            <Control
              field={{ ...item, label: `${item.label} ${index + 1}` }}
              value={entry}
              onChange={(next) => onChange(items.map((old, i) => (i === index ? next : old)))}
            />
          </div>
          <button
            type="button"
            className="icon-button"
            aria-label={`Remove ${item.label} ${index + 1}`}
            onClick={() => onChange(items.filter((_, i) => i !== index))}
          >
            <X className="size-3.5" />
          </button>
        </div>
      ))}
      <button
        type="button"
        className="text-button"
        onClick={() => onChange([...items, emptyValue(item)])}
      >
        <Plus className="size-3.5" /> Add {item.label.toLowerCase()}
      </button>
    </div>
  );
}

interface FieldProps {
  field: FieldSpec;
  value: unknown;
  onChange(value: unknown): void;
}

function Control({ field, value, onChange }: FieldProps) {
  const id = `field-${field.name}`;
  const text = (value as string | undefined) ?? "";
  switch (field.kind) {
    case "text":
      return <input id={id} aria-label={field.label} value={text} onChange={(e) => onChange(e.target.value)} />;
    case "textarea":
      return (
        <textarea
          id={id}
          aria-label={field.label}
          rows={4}
          value={text}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "number":
      return (
        <input
          id={id}
          aria-label={field.label}
          type="number"
          min={field.minimum ?? undefined}
          max={field.maximum ?? undefined}
          step={field.step ?? "any"}
          value={(value as number | undefined) ?? ""}
          onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
        />
      );
    case "slider": {
      const current = (value as number | undefined) ?? field.minimum!;
      return (
        <div className="slider-field">
          <input
            id={id}
            aria-label={field.label}
            type="range"
            min={field.minimum!}
            max={field.maximum!}
            step={field.step ?? 0.01}
            value={current}
            onChange={(e) => onChange(Number(e.target.value))}
          />
          <output>{value === undefined ? "default" : current}</output>
        </div>
      );
    }
    case "boolean":
      return (
        <input
          id={id}
          aria-label={field.label}
          type="checkbox"
          checked={value === true}
          onChange={(e) => onChange(e.target.checked)}
        />
      );
    case "select":
      return (
        <select
          id={id}
          aria-label={field.label}
          value={text}
          onChange={(e) => onChange(e.target.value || undefined)}
        >
          <option value="">Not set</option>
          {field.options.map((option) => (
            <option key={option} value={option}>
              {option.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      );
    case "multi_select": {
      const chosen = Array.isArray(value) ? (value as string[]) : [];
      return (
        <div role="group" aria-label={field.label} className="check-list">
          {field.options.map((option) => (
            <label key={option}>
              <input
                type="checkbox"
                checked={chosen.includes(option)}
                onChange={(e) =>
                  onChange(
                    e.target.checked ? [...chosen, option] : chosen.filter((o) => o !== option),
                  )
                }
              />
              {option.replace(/_/g, " ")}
            </label>
          ))}
        </div>
      );
    }
    case "json":
      return <JsonField field={field} value={value} onChange={onChange} />;
    case "code":
      return (
        <CodeEditor
          value={text}
          language={field.language ?? "plaintext"}
          label={field.label}
          onChange={onChange}
        />
      );
    case "secret": {
      const reference = (value as { secret?: string } | undefined)?.secret ?? "";
      return (
        <input
          id={id}
          aria-label={field.label}
          autoComplete="off"
          placeholder="Secret name, never its value"
          value={reference}
          onChange={(e) => onChange(e.target.value ? { secret: e.target.value } : undefined)}
        />
      );
    }
    case "array":
      return <ArrayField field={field} value={value} onChange={onChange} />;
    case "object":
      return (
        <div className="object-field">
          <FieldList
            fields={field.fields}
            values={(value as Values | undefined) ?? {}}
            onChange={onChange}
          />
        </div>
      );
  }
}

function FieldList({ fields, values, issues = [], onChange }: Props) {
  return fields
    .filter((field) => isVisible(field, values))
    .map((field) => {
      const problem = issues.find((issue) => issue.field === field.name);
      return (
        <div className="field" key={field.name} data-kind={field.kind}>
          <span className="field-label">
            {field.label}
            {field.required && <span aria-hidden> *</span>}
          </span>
          <Control
            field={field}
            value={values[field.name]}
            onChange={(next) => {
              const updated = { ...values };
              if (next === undefined) delete updated[field.name];
              else updated[field.name] = next;
              onChange(updated, field.name);
            }}
          />
          {field.description && <span className="field-help">{field.description}</span>}
          {problem && <span className="field-error">{problem.message}</span>}
        </div>
      );
    });
}

/** Renders any node's configuration from its schema; no control here knows a node type. */
export function FieldForm({ fields, values, issues, onChange }: Props) {
  const basic = fields.filter((field) => !field.advanced);
  const advanced = fields.filter((field) => field.advanced);
  return (
    <div className="field-form">
      <FieldList fields={basic} values={values} issues={issues} onChange={onChange} />
      {advanced.length > 0 && (
        <details className="advanced">
          <summary>Advanced</summary>
          <FieldList fields={advanced} values={values} issues={issues} onChange={onChange} />
        </details>
      )}
    </div>
  );
}
