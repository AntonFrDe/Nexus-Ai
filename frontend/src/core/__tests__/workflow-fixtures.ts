import type {
  NodeCatalog,
  PortSpec,
  WorkflowDocument,
  WorkflowEdge,
  WorkflowNode,
} from "@/core/workflow/types";

const port = (id: string, type: string, multiple = false): PortSpec => ({
  id,
  label: id,
  type,
  required: false,
  multiple,
});

const base = { description: "", icon: "box", shape: "card", permissions: [], executable: true };
const noFields = { fields: [], bounds_cycles: false };

export const catalog: NodeCatalog = {
  schema_version: 1,
  runtime_fields: [],
  port_compatibility: { text: ["messages"] },
  node_types: [
    {
      ...base,
      type: "core.text",
      title: "Text node",
      category: "Data",
      inputs: [port("in", "text")],
      outputs: [port("out", "text")],
      bounds_cycles: false,
      fields: [
        {
          name: "mode",
          label: "Mode",
          kind: "select",
          description: "",
          required: false,
          default: "a",
          advanced: false,
          options: ["a", "b"],
          minimum: null,
          maximum: null,
          step: null,
          language: null,
          item: null,
          fields: [],
          visible_when: null,
        },
      ],
    },
    {
      ...base,
      ...noFields,
      type: "core.memory",
      title: "Memory",
      category: "Data",
      inputs: [],
      outputs: [port("memory", "memory")],
    },
    {
      ...base,
      ...noFields,
      type: "core.merge",
      title: "Merge",
      category: "Control",
      inputs: [port("in", "any", true)],
      outputs: [port("out", "any")],
    },
    {
      ...base,
      ...noFields,
      type: "core.group",
      title: "Group",
      category: "Canvas",
      shape: "group",
      executable: false,
      inputs: [],
      outputs: [],
    },
  ],
};

export const workflowNode = (
  id: string,
  type: string,
  overrides: Partial<WorkflowNode> = {},
): WorkflowNode => ({
  id,
  type,
  position: { x: 0, y: 0 },
  label: "",
  config: {},
  runtime: {},
  permissions: [],
  input_schema: null,
  output_schema: null,
  parent_id: null,
  width: null,
  height: null,
  ...overrides,
});

export const wire = (source: string, target: string): WorkflowEdge => ({
  id: `${source}-${target}`,
  source,
  source_port: "out",
  target,
  target_port: "in",
  label: "",
});

export const doc = (
  nodes: WorkflowNode[] = [],
  edges: WorkflowEdge[] = [],
  id = "w1",
): WorkflowDocument => ({
  id,
  name: id,
  description: "",
  schema_version: 1,
  nodes,
  edges,
  variables: {},
  config: {},
  policies: {},
  metadata: {},
  created_at: "",
  updated_at: "",
});
