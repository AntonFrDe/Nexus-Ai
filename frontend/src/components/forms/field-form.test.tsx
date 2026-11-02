import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { FieldForm } from "@/components/forms/field-form";
import type { FieldSpec, Issue } from "@/core/workflow/types";

vi.mock("@/components/code-editor", () => ({
  CodeEditor: ({ label, value, onChange }: { label: string; value: string; onChange(v: string): void }) => (
    <textarea aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}));

const spec = (name: string, kind: FieldSpec["kind"], extra: Partial<FieldSpec> = {}): FieldSpec => ({
  name,
  label: name,
  kind,
  description: "",
  required: false,
  default: null,
  advanced: false,
  options: [],
  minimum: null,
  maximum: null,
  step: null,
  language: null,
  item: null,
  fields: [],
  visible_when: null,
  ...extra,
});

function Harness({
  fields,
  initial = {},
  issues,
  onChange,
}: {
  fields: FieldSpec[];
  initial?: Record<string, unknown>;
  issues?: Issue[];
  onChange?(values: Record<string, unknown>): void;
}) {
  const [values, setValues] = useState(initial);
  return (
    <FieldForm
      fields={fields}
      values={values}
      issues={issues}
      onChange={(next) => {
        setValues(next);
        onChange?.(next);
      }}
    />
  );
}

describe("FieldForm", () => {
  it("renders every field kind from its schema", () => {
    render(
      <Harness
        fields={[
          spec("t", "text"),
          spec("a", "textarea"),
          spec("n", "number"),
          spec("b", "boolean"),
          spec("s", "select", { options: ["x"] }),
          spec("m", "multi_select", { options: ["x"] }),
          spec("r", "slider", { minimum: 0, maximum: 1 }),
          spec("j", "json"),
          spec("c", "code"),
          spec("k", "secret"),
          spec("l", "array", { item: spec("item", "text") }),
          spec("o", "object", { fields: [spec("inner", "text")] }),
        ]}
      />,
    );
    for (const name of ["t", "a", "n", "b", "s", "m", "r", "j", "c", "k", "inner"]) {
      expect(screen.getByLabelText(name)).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: /add item/i })).toBeInTheDocument();
  });

  it("shows conditional fields only when their condition holds", async () => {
    render(
      <Harness
        fields={[
          spec("mode", "select", { options: ["a", "b"] }),
          spec("extra", "text", { visible_when: { field: "mode", equals: ["b"] } }),
        ]}
        initial={{ mode: "a" }}
      />,
    );
    expect(screen.queryByLabelText("extra")).toBeNull();
    await userEvent.selectOptions(screen.getByLabelText("mode"), "b");
    expect(screen.getByLabelText("extra")).toBeInTheDocument();
  });

  it("keeps advanced fields in their own section", () => {
    render(<Harness fields={[spec("t", "text", { advanced: true })]} />);
    expect(screen.getByText("Advanced").closest("details")).not.toHaveAttribute("open");
  });

  it("stores a secret as a reference, never as a bare string", async () => {
    const onChange = vi.fn();
    render(<Harness fields={[spec("key", "secret")]} onChange={onChange} />);
    await userEvent.type(screen.getByLabelText("key"), "a");
    expect(onChange).toHaveBeenLastCalledWith({ key: { secret: "a" } });
  });

  it("removes emptied numbers instead of storing a blank", async () => {
    const onChange = vi.fn();
    render(<Harness fields={[spec("n", "number")]} initial={{ n: 5 }} onChange={onChange} />);
    await userEvent.clear(screen.getByLabelText("n"));
    expect(onChange).toHaveBeenLastCalledWith({});
  });

  it("adds and removes array items", async () => {
    const onChange = vi.fn();
    render(
      <Harness fields={[spec("l", "array", { item: spec("item", "text") })]} onChange={onChange} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /add item/i }));
    await userEvent.type(screen.getByLabelText("item 1"), "x");
    expect(onChange).toHaveBeenLastCalledWith({ l: ["x"] });
    await userEvent.click(screen.getByRole("button", { name: "Remove item 1" }));
    expect(onChange).toHaveBeenLastCalledWith({ l: [] });
  });

  it("keeps the last valid value while JSON is being typed", async () => {
    const onChange = vi.fn();
    render(<Harness fields={[spec("j", "json")]} initial={{ j: { a: 1 } }} onChange={onChange} />);
    await userEvent.type(screen.getByLabelText("j"), "{{");
    expect(screen.getByText(/Not valid JSON/)).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("shows backend errors next to their field", () => {
    const issue: Issue = {
      severity: "error",
      code: "invalid_config",
      message: "t is required",
      node_id: "n",
      edge_id: null,
      field: "t",
    };
    render(<Harness fields={[spec("t", "text")]} issues={[issue]} />);
    expect(screen.getByText("t is required")).toBeInTheDocument();
  });
});
