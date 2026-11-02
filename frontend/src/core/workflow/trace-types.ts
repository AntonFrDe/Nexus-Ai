import { z } from "zod";

const span = z.object({
  id: z.string(),
  node_id: z.string(),
  label: z.string(),
  node_type: z.string(),
  status: z.string(),
  attempt: z.number(),
  start_ms: z.number(),
  duration_ms: z.number().nullable(),
  model: z.string().nullable(),
  tokens: z.number().nullable(),
  cost_usd: z.number().nullable(),
  error: z.string().nullable(),
});

export const executionTrace = z.object({
  execution_id: z.string(),
  status: z.string(),
  recorded: z.boolean(),
  replay_of: z.string().nullable(),
  overrides: z.record(z.string(), z.unknown()).nullable(),
  duration_ms: z.number().nullable(),
  spans: z.array(span),
  failure: z
    .object({
      node_id: z.string().nullable(),
      label: z.string().nullable(),
      message: z.string(),
      input: z.unknown(),
    })
    .nullable(),
});

export const checkpoint = z.object({
  checkpoint_id: z.string(),
  next: z.array(z.string()),
  created_at: z.string().nullable(),
});

export const checkpointState = z.object({
  checkpoint_id: z.string(),
  next: z.array(z.string()),
  outputs: z.record(z.string(), z.unknown()),
  variables: z.record(z.string(), z.unknown()),
  errors: z.record(z.string(), z.unknown()),
});

const compareSide = z.object({
  status: z.string().nullable(),
  duration_ms: z.number().nullable(),
  model: z.string().nullable(),
  tokens: z.number().nullable(),
  cost_usd: z.number().nullable(),
  output: z.unknown(),
});

export const comparison = z.object({
  left_id: z.string(),
  right_id: z.string(),
  left_status: z.string(),
  right_status: z.string(),
  rows: z.array(
    z.object({
      node_id: z.string(),
      label: z.string(),
      left: compareSide,
      right: compareSide,
      same_status: z.boolean(),
      same_output: z.boolean(),
      config_changed: z.boolean(),
    }),
  ),
});

const usageBucket = z.object({
  calls: z.number(),
  input_tokens: z.number(),
  output_tokens: z.number(),
  cost_usd: z.number(),
  unpriced: z.number(),
});

export const analytics = z.object({
  days: z.number(),
  runs: z.number(),
  statuses: z.record(z.string(), z.number()),
  totals: usageBucket,
  by_model: z.array(usageBucket.extend({ model: z.string() })),
  by_workflow: z.array(usageBucket.extend({ workflow: z.string() })),
  by_day: z.array(usageBucket.extend({ day: z.string() })),
  top_errors: z.array(z.object({ error: z.string(), count: z.number() })),
});

export const langfuseConfig = z.object({
  enabled: z.boolean(),
  host: z.string(),
  public_key: z.string(),
  secret_name: z.string().nullable(),
  include_content: z.boolean(),
});

export type ExecutionTrace = z.infer<typeof executionTrace>;
export type Checkpoint = z.infer<typeof checkpoint>;
export type CheckpointState = z.infer<typeof checkpointState>;
export type Comparison = z.infer<typeof comparison>;
export type Analytics = z.infer<typeof analytics>;
export type LangfuseConfig = z.infer<typeof langfuseConfig>;
