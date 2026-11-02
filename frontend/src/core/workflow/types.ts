import { z } from "zod";

export interface FieldSpec {
  name: string;
  label: string;
  kind:
    | "text"
    | "textarea"
    | "number"
    | "boolean"
    | "select"
    | "multi_select"
    | "slider"
    | "json"
    | "code"
    | "secret"
    | "array"
    | "object";
  description: string;
  required: boolean;
  default: unknown;
  advanced: boolean;
  options: string[];
  minimum: number | null;
  maximum: number | null;
  step: number | null;
  language: string | null;
  item: FieldSpec | null;
  fields: FieldSpec[];
  visible_when: { field: string; equals: unknown[] } | null;
}

export const fieldSpec: z.ZodType<FieldSpec> = z.lazy(() =>
  z.object({
    name: z.string(),
    label: z.string(),
    kind: z.enum([
      "text",
      "textarea",
      "number",
      "boolean",
      "select",
      "multi_select",
      "slider",
      "json",
      "code",
      "secret",
      "array",
      "object",
    ]),
    description: z.string(),
    required: z.boolean(),
    default: z.unknown(),
    advanced: z.boolean(),
    options: z.array(z.string()),
    minimum: z.number().nullable(),
    maximum: z.number().nullable(),
    step: z.number().nullable(),
    language: z.string().nullable(),
    item: fieldSpec.nullable(),
    fields: z.array(fieldSpec),
    visible_when: z.object({ field: z.string(), equals: z.array(z.unknown()) }).nullable(),
  }),
);

const portSpec = z.object({
  id: z.string(),
  label: z.string(),
  type: z.string(),
  required: z.boolean(),
  multiple: z.boolean(),
});

const nodeType = z.object({
  type: z.string(),
  title: z.string(),
  category: z.string(),
  description: z.string(),
  icon: z.string(),
  shape: z.string(),
  inputs: z.array(portSpec),
  outputs: z.array(portSpec),
  fields: z.array(fieldSpec),
  permissions: z.array(z.string()),
  executable: z.boolean(),
  bounds_cycles: z.boolean(),
});

export const nodeCatalog = z.object({
  schema_version: z.number(),
  node_types: z.array(nodeType),
  runtime_fields: z.array(fieldSpec),
  port_compatibility: z.record(z.string(), z.array(z.string())),
});

const jsonObject = z.record(z.string(), z.unknown());

const workflowNode = z.object({
  id: z.string(),
  type: z.string(),
  position: z.object({ x: z.number(), y: z.number() }),
  label: z.string(),
  config: jsonObject,
  runtime: jsonObject,
  permissions: z.array(z.string()),
  input_schema: jsonObject.nullable(),
  output_schema: jsonObject.nullable(),
  parent_id: z.string().nullable(),
  width: z.number().nullable(),
  height: z.number().nullable(),
});

const workflowEdge = z.object({
  id: z.string(),
  source: z.string(),
  source_port: z.string(),
  target: z.string(),
  target_port: z.string(),
  label: z.string(),
});

export const workflowSummary = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const workflowDocument = workflowSummary.extend({
  schema_version: z.number(),
  nodes: z.array(workflowNode),
  edges: z.array(workflowEdge),
  variables: jsonObject,
  config: jsonObject,
  policies: jsonObject,
  metadata: jsonObject,
});

export const versionSummary = z.object({
  number: z.number(),
  label: z.string(),
  created_at: z.string(),
});

const issue = z.object({
  severity: z.enum(["error", "warning"]),
  code: z.string(),
  message: z.string(),
  node_id: z.string().nullable(),
  edge_id: z.string().nullable(),
  field: z.string().nullable(),
});

export const validationReport = z.object({ valid: z.boolean(), issues: z.array(issue) });

export type NodeType = z.infer<typeof nodeType>;
export type PortSpec = z.infer<typeof portSpec>;
export type NodeCatalog = z.infer<typeof nodeCatalog>;
export type WorkflowNode = z.infer<typeof workflowNode>;
export type WorkflowEdge = z.infer<typeof workflowEdge>;
export type WorkflowSummary = z.infer<typeof workflowSummary>;
export type WorkflowDocument = z.infer<typeof workflowDocument>;
export type VersionSummary = z.infer<typeof versionSummary>;
export type Issue = z.infer<typeof issue>;
export type ValidationReport = z.infer<typeof validationReport>;
/** A complete document without its server-managed identity and timestamps. */
export type WorkflowContent = Omit<WorkflowDocument, "id" | "created_at" | "updated_at">;
export type WorkflowGraphContent = Omit<WorkflowContent, "name" | "description">;
