import { z } from "zod";

import { fieldSpec } from "@/core/workflow/types";

export const agent = z.object({
  id: z.string(),
  name: z.string(),
  version: z.number(),
  template: z.string().nullable(),
  definition: z.record(z.string(), z.unknown()),
  created_at: z.string(),
  updated_at: z.string(),
});

export const agentVersion = z.object({
  number: z.number(),
  name: z.string(),
  definition: z.record(z.string(), z.unknown()),
  created_at: z.string(),
});

export const agentTemplate = z.object({
  id: z.string(),
  name: z.string(),
  definition: z.record(z.string(), z.unknown()),
});

export const runtime = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  paid: z.boolean(),
  needs_secret: z.boolean(),
  enabled: z.boolean(),
  secret_name: z.string().nullable(),
  has_secret: z.boolean(),
  capabilities: z.record(z.string(), z.boolean()),
  health: z.object({ ready: z.boolean(), message: z.string() }),
});

export const agentFields = z.array(fieldSpec);

export type Agent = z.infer<typeof agent>;
export type AgentVersion = z.infer<typeof agentVersion>;
export type AgentTemplate = z.infer<typeof agentTemplate>;
export type Runtime = z.infer<typeof runtime>;
