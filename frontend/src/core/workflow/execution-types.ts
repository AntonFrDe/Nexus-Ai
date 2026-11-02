import { z } from "zod";

export const execution = z.object({
  id: z.string(),
  workflow_id: z.string().nullable(),
  workflow_name: z.string(),
  workflow_version: z.number().nullable(),
  session_id: z.string(),
  status: z.string(),
  mode: z.string(),
  allow_paid: z.boolean(),
  entry_node: z.string().nullable(),
  error: z.string().nullable(),
  error_node: z.string().nullable(),
  metrics: z.record(z.string(), z.unknown()),
  created_at: z.string(),
  started_at: z.string().nullable(),
  ended_at: z.string().nullable(),
});

const nodeExecution = z.object({
  id: z.string(),
  node_id: z.string(),
  node_type: z.string(),
  attempt: z.number(),
  status: z.string(),
  input: z.unknown(),
  output: z.unknown(),
  error: z.string().nullable(),
  usage: z.record(z.string(), z.unknown()).nullable(),
  started_at: z.string(),
  ended_at: z.string().nullable(),
});

export const executionDetail = execution.extend({
  input: z.unknown(),
  output: z.unknown(),
  nodes: z.array(nodeExecution),
  pending_approvals: z.array(z.record(z.string(), z.unknown())),
});

export const executionEvent = z.object({
  seq: z.number(),
  type: z.string(),
  node_id: z.string().nullable(),
  payload: z.record(z.string(), z.unknown()),
  created_at: z.string(),
});

export type Execution = z.infer<typeof execution>;
export type NodeExecution = z.infer<typeof nodeExecution>;
export type ExecutionDetail = z.infer<typeof executionDetail>;
export type ExecutionEvent = z.infer<typeof executionEvent>;
