# Roadmap

## Milestone 1: Application foundation (complete)

| Item | State |
|---|---|
| FastAPI backend, SQLite, Alembic migrations | Done |
| Dark design system, accent and density settings | Done |
| Dockview: tabs, drag docking, resize, floating groups, popout windows, maximize and restore | Done |
| Panel registry and panel visibility management | Done |
| Workspace CRUD, duplication, import/export, presets, reset | Done |
| Six default layouts | Done; most panels in them are labeled placeholders for later milestones |
| Autosave and restoration of layout, active workspace and panel state | Done |

**Acceptance:** open the app, move panels, create layouts, save them, restore after restart. Verified
by E2E tests with page reloads, and by restarting the backend process manually.

Known limitations:

- Popout windows do not reliably survive a reload. In testing, the group returned to the main window
  and no panel was lost. Browsers may block windows opened without a user gesture.
- Saving is last-write-wins: two browser tabs on one workspace overwrite each other.
- Light theme, typography and panel appearance settings are not started.
- Panels are single-instance per workspace.
- The title bar is built for desktop widths.

## Milestone 2: Workflow editor (next)

React Flow canvas, node registry and library, schema-driven inspector, versioned workflow JSON schema
with backend validation, autosave. Replaces the Workflow Canvas, Node Library, Node Inspector and
Workflow Versions placeholders.

Acceptance: create, edit, save, reload and export a workflow.

## Milestone 3: Execution engine

LangGraph integration, graph compiler, node adapters, execution lifecycle, SSE or WebSocket events,
checkpointing. Local API authentication (T-009) is a prerequisite.

Acceptance: a real multi-node workflow executes, fails visibly and resumes after an interruption.

## Milestone 4: Model Manager

LiteLLM, Ollama, registry, provider configuration, encrypted secrets, connection tests, capabilities.

Acceptance: configure and test one local and one external model.

## Milestone 5: Agent Manager

Agent definitions and templates, runtime registry, Claude Agent SDK and Antigravity SDK adapters,
sessions.

Acceptance: compatible agents execute in workflows through native adapters.

## Milestone 6: Plugin SDK

Manifests, registry, node, panel and runtime registration, permissions, process isolation.

Acceptance: a separately developed plugin installs and registers a working node and panel.

## Milestone 7: Debugging and observability

Execution inspector, logs, Langfuse, cost monitoring, replay, comparison.

Acceptance: identify which node failed and why from the full lifecycle of an execution.

## Milestone 8: Hardening

Security review, performance, error handling, backup and restore, documentation, Tauri preparation.
