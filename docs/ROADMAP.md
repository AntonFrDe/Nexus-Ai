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

## Milestone 2: Workflow editor (complete)

| Item | State |
|---|---|
| Node registry and catalog of 43 node types across six categories, plus Group and Annotation | Done; definitions and validation only, nothing executes |
| Schema-driven inspector: all 12 field kinds, conditional fields, advanced sections | Done |
| Per-node label, runtime settings, schema overrides, permissions | Done; permissions are stored, not enforced |
| Canvas: pan, zoom, grid, snap, minimap, multi-select, duplicate, delete, undo/redo, group, resize, annotations, auto layout, edge labels, search | Done |
| Typed ports, shapes and connection checks | Done |
| Versioned workflow JSON, backend validation, schema migration chain | Done; no real migration exists yet, the chain is tested with fixtures |
| Autosave, import/export, immutable versions with restore | Done |
| Example workflows in `backend/examples` | Done |

**Acceptance:** create, edit, save, reload and export a workflow. Verified end to end in Chromium.

Known limitations:

- Workflow `variables`, `config` and `policies` are stored and exported but have no editor yet.
- Secret fields hold references only, and nothing resolves them until the secrets service (M4).
- Model fields are free text until the model registry (M4); sub-workflow and agent fields are raw IDs.
- Condition fields are unparsed strings. Their expression language is designed in Milestone 3.
- Plugins cannot add canvas shapes yet; a node type picks one of the five built-in renderers.
- The canvas was not tested inside a floating group or popout window.
- Dragging a wire onto an incompatible port is refused without a message; the reason appears only in
  the unit-tested store path.
- Saved workspaces keep their old layout. Use Reset layout to get the new Workflow Builder preset.
- Monaco adds significant weight: `.next/static` is about 16 MB.

## Model routing

The routing policy in [MODEL_ROUTING.md](MODEL_ROUTING.md) adds requirements to Milestones 3 to 7.

## Milestone 3: Execution engine (next)

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
