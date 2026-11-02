import { z } from "zod";

import {
  nodeCatalog,
  validationReport,
  versionSummary,
  workflowDocument,
  workflowSummary,
  type WorkflowContent,
  type WorkflowGraphContent,
} from "@/core/workflow/types";

const workspaceSummary = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  preset: z.string().nullable(),
  position: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});

const workspaceDetail = workspaceSummary.extend({
  layout: z.record(z.string(), z.unknown()).nullable(),
  panel_states: z.record(z.string(), z.unknown()),
  preferences: z.record(z.string(), z.unknown()),
});

const health = z.object({ status: z.string(), version: z.string(), database: z.string() });

export type WorkspaceSummary = z.infer<typeof workspaceSummary>;
export type WorkspaceDetail = z.infer<typeof workspaceDetail>;
export type Health = z.infer<typeof health>;
export type WorkspacePatch = Partial<
  Pick<WorkspaceDetail, "name" | "description" | "layout" | "panel_states" | "preferences">
>;
export type WorkspaceDraft = Pick<WorkspaceDetail, "name" | "description"> & {
  preset?: string | null;
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(response.status, detail || `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

const send = (method: string, body: unknown, extra?: RequestInit): RequestInit => ({
  method,
  body: JSON.stringify(body),
  ...extra,
});

export const apiClient = {
  health: async () => health.parse(await request("/health")),
  listWorkspaces: async () =>
    z.array(workspaceSummary).parse(await request("/workspaces")),
  getWorkspace: async (id: string) =>
    workspaceDetail.parse(await request(`/workspaces/${id}`)),
  createWorkspace: async (draft: WorkspaceDraft) =>
    workspaceDetail.parse(await request("/workspaces", send("POST", draft))),
  // keepalive lets the final autosave outlive the page during unload.
  updateWorkspace: async (id: string, patch: WorkspacePatch, keepalive = false) =>
    workspaceDetail.parse(
      await request(`/workspaces/${id}`, send("PATCH", patch, { keepalive })),
    ),
  deleteWorkspace: async (id: string) => {
    await request(`/workspaces/${id}`, { method: "DELETE" });
  },
  duplicateWorkspace: async (id: string) =>
    workspaceDetail.parse(await request(`/workspaces/${id}/duplicate`, send("POST", {}))),
  exportWorkspace: (id: string) => request(`/workspaces/${id}/export`),
  importWorkspace: async (document: unknown) =>
    workspaceDetail.parse(await request("/workspaces/import", send("POST", document))),
  nodeCatalog: async () => nodeCatalog.parse(await request("/node-types")),
  listWorkflows: async () => z.array(workflowSummary).parse(await request("/workflows")),
  getWorkflow: async (id: string) => workflowDocument.parse(await request(`/workflows/${id}`)),
  createWorkflow: async (draft: { name: string; description: string }) =>
    workflowDocument.parse(await request("/workflows", send("POST", draft))),
  saveWorkflow: async (id: string, content: WorkflowContent, keepalive = false) =>
    workflowDocument.parse(
      await request(`/workflows/${id}`, send("PUT", content, { keepalive })),
    ),
  deleteWorkflow: async (id: string) => {
    await request(`/workflows/${id}`, { method: "DELETE" });
  },
  duplicateWorkflow: async (id: string) =>
    workflowDocument.parse(await request(`/workflows/${id}/duplicate`, { method: "POST" })),
  exportWorkflow: (id: string) => request(`/workflows/${id}/export`),
  importWorkflow: async (document: unknown) =>
    workflowDocument.parse(await request("/workflows/import", send("POST", document))),
  validateWorkflow: async (graph: WorkflowGraphContent) =>
    validationReport.parse(await request("/workflows/validate", send("POST", graph))),
  listVersions: async (id: string) =>
    z.array(versionSummary).parse(await request(`/workflows/${id}/versions`)),
  createVersion: async (id: string, label: string) =>
    versionSummary.parse(await request(`/workflows/${id}/versions`, send("POST", { label }))),
  restoreVersion: async (id: string, number: number) =>
    workflowDocument.parse(
      await request(`/workflows/${id}/versions/${number}/restore`, { method: "POST" }),
    ),
  getSetting: async (key: string): Promise<unknown> => {
    try {
      return z.object({ value: z.unknown() }).parse(await request(`/settings/${key}`)).value;
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },
  putSetting: async (key: string, value: unknown) => {
    await request(`/settings/${key}`, send("PUT", { value }));
  },
};

export type ApiClient = typeof apiClient;
