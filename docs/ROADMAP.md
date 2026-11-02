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

## Milestone 3: Execution engine (complete)

| Item | State |
|---|---|
| Local API authentication (T-009) | Done |
| LangGraph compiler, execution lifecycle, background runs | Done |
| Sequence, branching, parallel and merge, loops, sub-workflows, shared state | Done |
| Retry, timeout, continue on error, Error Handler | Done, as node runtime settings |
| Pause, resume, cancel, human approval | Done |
| Checkpoints, restoration, resume after failure or restart | Done; the restore API has no UI yet |
| Full, single-node and from-node runs | Done in the API; the UI starts full runs only |
| Live events over SSE, Executions and Execution Logs panels, status on the canvas | Done |
| Safe expression language and templates | Done |

**Acceptance:** a real multi-node workflow executes, produces outputs, fails visibly and resumes
after an interruption. Verified by API and browser tests, including a backend restart during a run.

Known limitations:

- **16 of 43 node types run.** Input, Output, IF/ELSE, Switch, Loop, Parallel, Merge, Delay, Stop,
  Error Handler, Sub-workflow, JSON Parser, Data Transform, Variable, Logger and Human Approval.
  Everything else is refused before start with a reason, including every agent and model node.
- Tool nodes with side effects stay unrunnable until permissions are enforced. Permissions stored on
  nodes therefore have no effect yet.
- The Retry node itself does not run; retries use each node's runtime settings.
- Pause takes effect when the next node starts. Running nodes finish first.
- A node interrupted by a crash runs again on resume, so it must tolerate running twice.
- One decision answers every pending approval in a run with parallel approvals.
- Sub-workflows report as one step, and cannot contain Human Approval.
- Stored node inputs and outputs live in SQLite, with no size limit or separate artifact store yet.
- Concurrency is one global limit (4 runs); per-resource limits arrive with Milestone 4.
- Execution comparison and modified replay are Milestone 7.

## Milestone 4: Model Manager (complete, real providers unverified)

| Item | State |
|---|---|
| Encrypted secrets service, write-only over the API | Done, master key in the system keychain or a private file |
| Provider registry with nine provider types | Done |
| Model registry, discovery, manual entry | Done |
| Capability detection, manual overrides, parameters limited to capabilities | Done |
| Connection and model tests, with confirmation before any paid call | Done |
| Model Registry panel, model suggestions in the inspector | Done |

**Acceptance: not fully verified.** "Configure and test a local model and an external model" works
through the real adapter, real LiteLLM and real HTTP, but against local test servers. Ollama is not
installed on the development machine and no provider key was used, so **no real model has answered
yet**.

Known limitations:

- Anthropic, OpenAI, Gemini, Mistral, OpenRouter, LM Studio and real Ollama are untested. Discovery
  formats come from documentation.
- Capabilities come from LiteLLM's tables by provider, so a local model may be listed with a feature
  it lacks. Testing a capability for real, and correcting it with an override, is manual.
- Rate limits are stored but not enforced, and the per-resource concurrency limits planned here move
  to Milestone 5, where calls happen during runs.
- Paid confirmation covers test calls. The budget rules for runs are Milestone 5.
- Streaming is detected, but tests use one non-streaming call.
- Changing a provider's endpoint keeps its key, which is then sent to the new endpoint.
- Secrets cannot be rotated in bulk, and a lost master key means entering every key again.
- Backup of the database does not include the keychain entry.

**Also fixed in this milestone:** starting twice, as React does in development, could reset the dock
after the first user action. This is the likely cause of the unexplained Milestone 3 test failure.

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
