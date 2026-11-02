import { z } from "zod";

import { fieldSpec } from "@/core/workflow/types";

export const providerType = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  default_endpoint: z.string().nullable(),
  endpoint_required: z.boolean(),
  auth: z.string(),
  discovery: z.string(),
  local: z.boolean(),
  paid: z.boolean(),
});

export const provider = z.object({
  id: z.string(),
  type: z.string(),
  name: z.string(),
  endpoint: z.string().nullable(),
  secret_name: z.string().nullable(),
  has_secret: z.boolean(),
  enabled: z.boolean(),
  timeout_seconds: z.number(),
  rate_limit_rpm: z.number().nullable(),
  paid: z.boolean(),
  created_at: z.string(),
});

export const connectionResult = z.object({
  ok: z.boolean(),
  message: z.string(),
  models_found: z.number().nullable(),
  latency_ms: z.number().nullable(),
});

export const registeredModel = z.object({
  id: z.string(),
  provider_id: z.string(),
  provider_name: z.string(),
  model_id: z.string(),
  context_window: z.number().nullable(),
  capabilities: z.record(z.string(), z.boolean()),
  capability_overrides: z.record(z.string(), z.boolean()),
  input_cost_per_mtok: z.number().nullable(),
  output_cost_per_mtok: z.number().nullable(),
  defaults: z.record(z.string(), z.unknown()),
  source: z.string(),
  last_test: z.record(z.string(), z.unknown()).nullable(),
  parameter_fields: z.array(fieldSpec),
});

export const modelTestResult = z.object({
  ok: z.boolean(),
  message: z.string(),
  text: z.string().nullable(),
  served_by: z.string().nullable(),
  input_tokens: z.number().nullable(),
  output_tokens: z.number().nullable(),
  latency_ms: z.number().nullable(),
  tested_at: z.string(),
});

export type ProviderType = z.infer<typeof providerType>;
export type Provider = z.infer<typeof provider>;
export type ConnectionResult = z.infer<typeof connectionResult>;
export type RegisteredModel = z.infer<typeof registeredModel>;
export type ModelTestResult = z.infer<typeof modelTestResult>;
export interface ProviderDraft {
  type: string;
  name: string;
  endpoint?: string;
  secret_name?: string;
}
