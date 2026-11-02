import { z } from "zod";

export const projectSummary = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  updated_at: z.string(),
  messages: z.number(),
  results: z.number(),
});

const proposal = z.object({
  roadmap: z
    .object({
      title: z.string(),
      steps: z.array(z.object({ title: z.string(), detail: z.string() })),
    })
    .nullable(),
  agents: z.array(
    z.object({ name: z.string(), role: z.string(), system_prompt: z.string() }),
  ),
});

const message = z.object({
  id: z.string(),
  role: z.string(),
  content: z.string(),
  model: z.string().nullable(),
  proposal: proposal.nullable(),
  proposal_status: z.string().nullable(),
  created_at: z.string(),
});

const result = z.object({
  id: z.string(),
  kind: z.string(),
  title: z.string(),
  content: z.record(z.string(), z.unknown()),
  created_at: z.string(),
});

export const projectDetail = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  updated_at: z.string(),
  messages: z.array(message),
  results: z.array(result),
});

export type ProjectSummary = z.infer<typeof projectSummary>;
export type ProjectDetail = z.infer<typeof projectDetail>;
export type ProjectMessage = z.infer<typeof message>;
export type ProjectResult = z.infer<typeof result>;
export type Proposal = z.infer<typeof proposal>;
