# Architecture

Sections marked *planned* describe intent and contain no code yet.

## Overview

```mermaid
flowchart LR
  subgraph Browser
    Shell[Studio shell] --> Dock[Dockview host]
    Dock --> Registry[Panel registry]
    Shell --> Store[Workspace store]
  end
  Store -->|/api via Next rewrite| API[FastAPI]
  API --> WS[workspaces]
  API --> ST[settings_store]
  API --> WF[workflows]
  API --> NR[Node registry]
  WF --> NR
  WS --> DB[(SQLite ~/.nexus/nexus.db)]
  ST --> DB
  WF --> DB
  API --> Engine[Execution manager and LangGraph]
  Engine --> CK[(checkpoints.db)]
  Engine --> DB
  Engine -.planned.-> Adapters[Model, runtime, tool, storage adapters]
  API -.planned.-> Plugins[Isolated plugin processes]
```

## Repository

```
backend/    FastAPI application (src/nexus), Alembic migrations, pytest suite
frontend/   Next.js application, Vitest unit tests (src/**), Playwright tests (e2e/)
docs/       Design documents
```

## Frontend

| Module | Responsibility |
|---|---|
| `core/panels/registry.ts` | `PanelRegistry`: the only way the workspace knows a panel exists |
| `core/workspace/presets.ts` | Declarative default layouts: data, not code |
| `core/workspace/layout.ts` | Loads presets and saved layouts into Dockview; handles unknown panels |
| `core/workspace/store.ts` | Workspace state, debounced ordered autosave, created by a factory with an injected API client |
| `components/shell/` | Title bar, status bar, Dock host, group actions, panel error boundary |
| `panels/` | Panel implementations and the built-in panel list (`panels/index.ts`) |
| `core/workflow/types.ts` | Zod schemas for the catalog and workflow documents |
| `core/workflow/graph.ts` | Pure graph operations: conversion, connection rules, duplicate, group, layout |
| `core/workflow/store.ts` | Open document, undo history, debounced autosave, latest-wins validation |
| `components/forms/field-form.tsx` | Renders any `FieldSpec` list; knows no node type |
| `components/workflow/` | Canvas node renderers, selected by the catalog's `shape` |
| `components/code-editor.tsx` | Monaco, bundled locally |
| `lib/api.ts` | Typed API client; responses are parsed with Zod at the boundary |

Dependencies are passed through `StudioProvider`; there are no module-level singletons.

**Autosave.** Dockview emits `onDidLayoutChange`; `DockHost` compares the serialized layout with the
last known one and forwards real changes. The store coalesces them for 500 ms, writes one at a time,
flushes before switching workspace and on `pagehide`, and keeps a failed write for retry. The status
bar reports the true save state.

**Resilience.** A layout that references an unregistered panel opens with a visible stand-in; a
corrupt layout falls back to the preset with a notice; a throwing panel is contained by
`PanelBoundary`; an unreachable backend shows a retry screen.

## Backend

Modules are grouped by domain, each with `models`, `schemas`, `service`, `routes`. Routes hold no
business logic. `create_app(settings)` builds the app from explicit settings, which is how tests get
an isolated database. Sessions commit on success and roll back on error (`session_scope`).

Migrations run at startup through Alembic. SQLite uses WAL and foreign keys.

**Node catalog.** `nodes/catalog.py` declares every node as data: ports, `FieldSpec`s, permissions.
`nodes/config_model.py` compiles fields into strict Pydantic models. The same definition reaches the
browser through `/api/node-types` and drives the inspector, so validation rules live in one place.
Required fields are enforced after visibility is resolved, so a hidden field never blocks a workflow.

**Drafts versus validity.** Saving accepts any structurally well-formed document, so autosave works
on unfinished graphs. `/api/workflows/validate` reports semantic issues separately, and the UI shows
them on nodes, in the Inspector and in Problems. Execution (M3) must refuse an invalid document.

**Execution.** `execution/compiler.py` turns a validated graph into LangGraph nodes built from
registered handlers. `execution/manager.py` runs each graph as a background task, and owns status
transitions, pause, approval, recovery and shutdown. `execution/store.py` holds all persistence.
Events go to the database first, then SSE reads them, so a reconnecting client replays from its last
position.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness and version |
| GET, POST | `/api/workspaces` | List, create |
| GET, PATCH, DELETE | `/api/workspaces/{id}` | Read, partial update, delete (last one protected) |
| POST | `/api/workspaces/{id}/duplicate` | Copy under a new identity |
| GET | `/api/workspaces/{id}/export` | Portable document |
| POST | `/api/workspaces/import` | Create from a portable document |
| GET, PUT | `/api/settings/{key}` | Application settings |
| GET | `/api/node-types` | Node catalog, runtime fields, port compatibility |
| GET, POST | `/api/workflows` | List, create |
| GET, PUT, DELETE | `/api/workflows/{id}` | Read, save whole document, delete |
| POST | `/api/workflows/validate` | Semantic validation |
| POST | `/api/workflows/{id}/duplicate` | Copy |
| GET | `/api/workflows/{id}/export` | Portable document |
| POST | `/api/workflows/import` | Migrate, parse and create |
| GET, POST | `/api/workflows/{id}/versions` | List, snapshot |
| POST | `/api/workflows/{id}/versions/{n}/restore` | Restore a snapshot |
| POST | `/api/workflows/{id}/executions` | Start a run (full, node or from_node) |
| GET | `/api/executions`, `/api/executions/{id}` | List, read with node records |
| GET | `/api/executions/{id}/events` | Live SSE, with replay |
| GET | `/api/executions/{id}/log` | Stored events |
| POST | `/api/executions/{id}/pause`, `resume`, `cancel`, `retry` | Control a run |
| POST | `/api/executions/{id}/approval` | Answer a human approval |
| GET, POST | `/api/executions/{id}/checkpoints`, `restore` | List, restore a checkpoint |

## Data model

| Table | Status | Contents |
|---|---|---|
| `workspaces` | built | id, name, description, preset, layout (Dockview JSON), panel_states, preferences, position, timestamps |
| `app_settings` | built | key, JSON value, timestamp |
| `workflows` | built | id, name, description, graph JSON, timestamps |
| `workflow_versions` | built | Immutable snapshots, numbered per workflow, cascade on delete |
| `executions`, `node_executions`, `execution_events` | built | Runs with their own graph copy, per-node records, ordered events |
| `providers`, `models`, `secrets` | *planned, M4* | Registry; secrets encrypted and never returned to the browser |
| `agents`, `agent_versions`, `runtimes` | *planned, M5* | Definitions, kept separate from models and runtimes |
| `plugins` | *planned, M6* | Installed plugin metadata |

LangGraph checkpoints get their own SQLite file, owned by `langgraph-checkpoint-sqlite`.

## Security (current)

- The API binds to `127.0.0.1` by default.
- `TrustedHostMiddleware` rejects unknown `Host` headers, which blocks DNS rebinding.
- The browser uses one origin through a Next rewrite, so CORS stays disabled.
- Request bodies are validated with `extra="forbid"`; stored documents are capped at 2 MB.
- The data directory is created with mode `0700`.
- Secret fields only accept `{"secret": "<name>"}`, so raw values fail validation. Autosave stores
  drafts before validation, and free-text fields cannot be inspected for pasted keys.
- Code fields are stored as text. Nothing evaluates them.

The API requires a per-launch token, added by the Next proxy for local same-origin callers only
([T-009](TECHNICAL_DECISIONS.md)). Processes running as the same user are not defended against.

Workflow conditions and templates use a parsed expression language with no `eval`, and paths read
dictionaries and lists only.
