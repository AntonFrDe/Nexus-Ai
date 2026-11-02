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

**Acceptance: local verified, external not.** Real Ollama models were discovered and answered on
2026-11-02. No external provider has been tried, because no key was used; that path has only run
against a local test server.

Known limitations:

- Anthropic, OpenAI, Gemini, Mistral, OpenRouter and LM Studio are untested. Discovery
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

## Milestone 5: Agent Manager (complete, real runtimes unverified)

| Item | State |
|---|---|
| Agent definitions separate from model and runtime | Done |
| Templates, cloning, immutable versions, restore | Done |
| Runtime registry with declared capabilities | Done |
| Native runtime (one turn through the Model Registry) | Done |
| Claude Agent SDK and Antigravity SDK adapters | Written, **never run for real** |
| LLM Agent, Custom Agent, Model Selector and Model Fallback nodes | Done |
| Recording the model that answered, tokens and cost | Done |
| Paid calls refused unless the run allows them | Done |
| Per-resource limits (one call at a time per local provider, Claude and Antigravity) | Done |
| Agents panel | Done |

**Acceptance: native verified, cloud runtimes not.** A two-agent workflow produced a real roadmap
with `qwen3.8:27b` through Ollama. The Claude and Antigravity adapters were checked only against the
installed SDKs' option names, because no key was available.

Known limitations:

- Session management is minimal: a session ID is recorded, but runs do not continue an agent session
  yet. The `session` and `memory` fields are stored and unused.
- Agent `tools`, `mcp_servers`, `permissions`, input and output schemas are stored. Only the Claude
  adapter receives `tools`, and permissions are still not enforced by NEXUS.
- The native runtime has no tools, so it is one model turn, not an agent loop.
- Coding, Multi-Agent, Supervisor and Evaluator Agent nodes, Model Router, Embedding and Reranker
  do not run yet.
- Automatic routing, escalation and profiles are not built, and neither are the six reference
  workflows.
- Budget control is a yes or no on the run, plus a per-call budget on the Claude runtime.
- An agent node interrupted by a crash runs again on resume, which can bill twice.
- `custom_agent` picks agents by raw ID in the inspector.
- Claude cost comes from the SDK. Native runs record tokens, but no cost yet.
- `filelock` 3.32.7 has 13 published CVEs fixed in 4.2.1. LiteLLM requires `filelock<4`, so the fix
  waits for LiteLLM. NEXUS does not use it directly.

## Milestone 6: Plugin SDK (complete)

| Item | State |
|---|---|
| Manifests, version and dependency checks, conflict detection | Done |
| Install, enable, disable, update, uninstall, plugin configuration | Done, from a local folder |
| Custom nodes, panels, runtimes, provider presets, tools as nodes | Done |
| Permissions for files, network, shell and environment | Enforced by the sandbox |
| Backend isolation | Done on macOS, one sandboxed process per call |
| Frontend isolation | Done: sandboxed iframe, no network, `postMessage` bridge only |
| Four example plugins and SDK documentation | Done |

**Acceptance:** a separately developed example plugin installs and registers a working node and
workspace panel. Verified in the browser with plugins from `examples/plugins`. A hostile test plugin
could not read keys or the database, reach the network or start programs.

Known limitations:

- Code plugins run on macOS only; elsewhere they are refused. `sandbox-exec` is deprecated by Apple.
- The block on keychain services is not verified, and CPU and memory are not limited.
- Plugins cannot use secrets or call each other, and agents cannot call plugin tools.
- Storage adapters and themes are not plugin contributions yet.
- Each call starts a process, so plugins keep no memory between calls.
- Enabling or disabling needs a page reload.
- Panels are single HTML files.

## Milestone 7: Debugging and observability (complete, Langfuse unverified)

| Item | State |
|---|---|
| Execution Trace: timeline, failure cause, state between nodes | Done |
| Step-through runs | Done |
| Replay with changes, marked apart from recorded runs | Done |
| Run comparison | Done |
| Cost and token analytics, with unknown prices shown as unpriced | Done |
| Structured JSON logs in `~/.nexus/logs`, without prompts or outputs | Done |
| Langfuse export over OTLP, off by default | Written, tested against a local stand-in only |

**Acceptance:** a user can inspect a run's lifecycle and see which node failed and why.

Known limitations:

- No real Langfuse server has received an export, and OTLP attribute names are unconfirmed.
- Replay in the interface changes LLM Agent model and temperature only; the API accepts any setting.
- Restoring a checkpoint has no interface yet.

## Milestone 8: Hardening

Security review, performance, error handling, backup and restore, documentation, Tauri preparation.
