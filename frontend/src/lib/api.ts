import { z } from "zod";

import {
  agent,
  agentFields,
  agentTemplate,
  agentVersion,
  runtime,
} from "@/core/models/agent-types";
import { plugin, pluginPanel } from "@/core/models/plugin-types";
import { projectDetail, projectSummary } from "@/core/projects/types";
import {
  analytics,
  checkpoint,
  checkpointState,
  comparison,
  executionTrace,
  langfuseConfig,
  type LangfuseConfig,
} from "@/core/workflow/trace-types";
import {
  connectionResult,
  modelTestResult,
  provider,
  providerType,
  registeredModel,
  type ProviderDraft,
  type RegisteredModel,
} from "@/core/models/types";
import {
  execution,
  executionDetail,
  executionEvent,
  type ExecutionDetail,
  type ExecutionEvent,
} from "@/core/workflow/execution-types";
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
  listExecutions: async () => z.array(execution).parse(await request("/executions")),
  getExecution: async (id: string) =>
    executionDetail.parse(await request(`/executions/${id}`)),
  /** Refused runs are an expected outcome, returned as issues rather than thrown. */
  startExecution: async (
    workflowId: string,
    body: { input: unknown; mode?: string; node_id?: string; allow_paid?: boolean; step?: boolean },
  ): Promise<ExecutionDetail | { issues: StartIssue[] }> => {
    const response = await fetch(`/api/workflows/${workflowId}/executions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const content = await response.json();
    if (response.status === 422 && Array.isArray(content.issues)) {
      return { issues: content.issues };
    }
    if (!response.ok) throw new ApiError(response.status, String(content.detail));
    return executionDetail.parse(content);
  },
  executionAction: async (id: string, action: "pause" | "resume" | "cancel") => {
    await request(`/executions/${id}/${action}`, { method: "POST" });
  },
  runToEnd: async (id: string) => {
    await request(`/executions/${id}/resume`, send("POST", { run_to_end: true }));
  },
  executionTrace: async (id: string) =>
    executionTrace.parse(await request(`/executions/${id}/trace`)),
  listCheckpoints: async (id: string) =>
    z.array(checkpoint).parse(await request(`/executions/${id}/checkpoints`)),
  checkpointState: async (id: string, checkpointId: string) =>
    checkpointState.parse(await request(`/executions/${id}/checkpoints/${checkpointId}`)),
  compareExecutions: async (left: string, right: string) =>
    comparison.parse(await request(`/executions/compare?left=${left}&right=${right}`)),
  replayExecution: async (id: string, overrides: Record<string, unknown>, allowPaid: boolean) =>
    executionDetail.parse(
      await request(
        `/executions/${id}/replay`,
        send("POST", { overrides, allow_paid: allowPaid }),
      ),
    ),
  analytics: async (days: number) => analytics.parse(await request(`/analytics?days=${days}`)),
  langfuseConfig: async () => langfuseConfig.parse(await request("/observability/langfuse")),
  saveLangfuseConfig: async (config: LangfuseConfig) =>
    langfuseConfig.parse(await request("/observability/langfuse", send("PUT", config))),
  checkLangfuse: async () =>
    z
      .object({ ok: z.boolean(), message: z.string() })
      .parse(await request("/observability/langfuse/check", { method: "POST" })),
  decideExecution: async (id: string, decision: "approved" | "rejected") => {
    await request(`/executions/${id}/approval`, send("POST", { decision }));
  },
  retryExecution: async (id: string) =>
    executionDetail.parse(await request(`/executions/${id}/retry`, { method: "POST" })),
  providerTypes: async () => z.array(providerType).parse(await request("/provider-types")),
  secretStatus: async () =>
    z.object({ backend: z.string() }).parse(await request("/secrets/status")),
  storeSecret: async (name: string, value: string) => {
    await request(`/secrets/${name}`, send("PUT", { value }));
  },
  deleteSecret: async (name: string) => {
    await request(`/secrets/${name}`, { method: "DELETE" });
  },
  listProviders: async () => z.array(provider).parse(await request("/providers")),
  createProvider: async (draft: ProviderDraft) =>
    provider.parse(await request("/providers", send("POST", draft))),
  updateProvider: async (
    id: string,
    patch: { secret_name?: string; enabled?: boolean; endpoint?: string },
  ) => provider.parse(await request(`/providers/${id}`, send("PATCH", patch))),
  deleteProvider: async (id: string) => {
    await request(`/providers/${id}`, { method: "DELETE" });
  },
  testProvider: async (id: string) =>
    connectionResult.parse(await request(`/providers/${id}/test`, { method: "POST" })),
  discoverModels: async (id: string) =>
    z.array(registeredModel).parse(await request(`/providers/${id}/discover`, { method: "POST" })),
  addModel: async (providerId: string, modelId: string) =>
    registeredModel.parse(
      await request(`/providers/${providerId}/models`, send("POST", { model_id: modelId })),
    ),
  listModels: async () => z.array(registeredModel).parse(await request("/models")),
  updateModel: async (id: string, patch: Partial<RegisteredModel>) =>
    registeredModel.parse(await request(`/models/${id}`, send("PATCH", patch))),
  deleteModel: async (id: string) => {
    await request(`/models/${id}`, { method: "DELETE" });
  },
  testModel: async (id: string, confirmPaid: boolean) =>
    modelTestResult.parse(
      await request(`/models/${id}/test`, send("POST", { confirm_paid: confirmPaid })),
    ),
  agentTemplates: async () => z.array(agentTemplate).parse(await request("/agent-templates")),
  agentFields: async () => agentFields.parse(await request("/agent-fields")),
  listRuntimes: async () => z.array(runtime).parse(await request("/runtimes")),
  configureRuntime: async (id: string, patch: { secret_name?: string; enabled?: boolean }) =>
    runtime.parse(await request(`/runtimes/${id}`, send("PATCH", patch))),
  listAgents: async () => z.array(agent).parse(await request("/agents")),
  createAgent: async (name: string, template: string | null) =>
    agent.parse(await request("/agents", send("POST", { name, template }))),
  updateAgent: async (
    id: string,
    patch: { name?: string; definition?: Record<string, unknown> },
  ) => agent.parse(await request(`/agents/${id}`, send("PATCH", patch))),
  deleteAgent: async (id: string) => {
    await request(`/agents/${id}`, { method: "DELETE" });
  },
  cloneAgent: async (id: string) =>
    agent.parse(await request(`/agents/${id}/clone`, { method: "POST" })),
  listAgentVersions: async (id: string) =>
    z.array(agentVersion).parse(await request(`/agents/${id}/versions`)),
  restoreAgentVersion: async (id: string, number: number) =>
    agent.parse(await request(`/agents/${id}/versions/${number}/restore`, { method: "POST" })),
  pluginStatus: async () =>
    z
      .object({ api_version: z.string(), sandbox: z.boolean() })
      .parse(await request("/plugins/status")),
  listPlugins: async () => z.array(plugin).parse(await request("/plugins")),
  pluginPanels: async () => z.array(pluginPanel).parse(await request("/plugins/panels")),
  installPlugin: async (path: string) => {
    await request("/plugins/install", send("POST", { path }));
  },
  enablePlugin: async (id: string, granted: string[]) => {
    await request(`/plugins/${id}/enable`, send("POST", { granted }));
  },
  disablePlugin: async (id: string) => {
    await request(`/plugins/${id}/disable`, { method: "POST" });
  },
  uninstallPlugin: async (id: string) => {
    await request(`/plugins/${id}`, { method: "DELETE" });
  },
  configurePlugin: async (id: string, config: Record<string, unknown>) => {
    await request(`/plugins/${id}/config`, send("PUT", { config }));
  },
  listProjects: async () => z.array(projectSummary).parse(await request("/projects")),
  getProject: async (id: string) => projectDetail.parse(await request(`/projects/${id}`)),
  createProject: async (name: string, description: string) =>
    projectDetail.parse(await request("/projects", send("POST", { name, description }))),
  deleteProject: async (id: string) => {
    await request(`/projects/${id}`, { method: "DELETE" });
  },
  answerProposal: async (id: string, messageId: string, action: "approve" | "reject") =>
    projectDetail.parse(
      await request(`/projects/${id}/messages/${messageId}/${action}`, { method: "POST" }),
    ),
  chat: async (
    id: string,
    body: { content: string; model: string; allow_paid: boolean },
  ): Promise<Response> => {
    const response = await fetch(`/api/projects/${id}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const content = await response.json().catch(() => null);
      throw new ApiError(response.status, String(content?.detail ?? response.statusText));
    }
    return response;
  },
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

export interface StartIssue {
  message: string;
  node_id: string | null;
}

export type EventSourceFactory = (
  executionId: string,
  onEvent: (event: ExecutionEvent) => void,
  onEnd: () => void,
) => () => void;

/** Follows a run. The browser reconnects by itself and replays from the last event it saw. */
export const openExecutionEvents: EventSourceFactory = (executionId, onEvent, onEnd) => {
  const source = new EventSource(`/api/executions/${executionId}/events`);
  source.addEventListener("execution", (message) =>
    onEvent(executionEvent.parse(JSON.parse(message.data))),
  );
  source.addEventListener("end", () => {
    source.close();
    onEnd();
  });
  return () => source.close();
};
