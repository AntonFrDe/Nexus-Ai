import { z } from "zod";

import { fieldSpec } from "@/core/workflow/types";

export const plugin = z.object({
  id: z.string(),
  name: z.string(),
  version: z.string(),
  description: z.string(),
  author: z.string(),
  category: z.string(),
  nexus_api: z.string(),
  compatible: z.boolean(),
  enabled: z.boolean(),
  permissions: z.array(z.string()),
  granted: z.array(z.string()),
  dependencies: z.record(z.string(), z.string()),
  contributions: z.record(z.string(), z.array(z.string())),
  config_fields: z.array(fieldSpec),
  config: z.record(z.string(), z.unknown()),
  problem: z.string().nullable(),
});

export const pluginPanel = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  category: z.string(),
  page: z.string(),
  plugin_id: z.string(),
});

export type Plugin = z.infer<typeof plugin>;
export type PluginPanel = z.infer<typeof pluginPanel>;
