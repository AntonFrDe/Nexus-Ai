# Technical decisions

Versions were checked against npm and PyPI on 2026-11-02.

## Verified stack

| Layer | Package | Version |
|---|---|---|
| Frontend | next / react | 16.4.3 / 19.3.0 |
| Frontend | dockview-react | 8.8.3 |
| Frontend | zustand / zod | 5.0.16 / 4.6.7 |
| Frontend | tailwindcss / shadcn (base-ui) | 4.x / 4.23 |
| Frontend | @xyflow/react / @dagrejs/dagre | 12.12 / 3.1 |
| Frontend | monaco-editor / @monaco-editor/react | 0.57 / 4.7 |
| Tests | vitest / playwright | 5.0.5 / 1.64.1 |
| Backend | fastapi / pydantic | 0.162.0 / 2.14.2 |
| Backend | sqlalchemy / alembic | 2.1.x / 1.20.x |
| Backend | langgraph / langgraph-checkpoint-sqlite | 1.2.x / 3.1.x |
| Backend | litellm (pinned) / cryptography / keyring | 1.106.5 / 50 / 25 |
| Future | langfuse | 5.1.0 |
| Future | claude-agent-sdk / google-antigravity | 0.2.176 / 0.1.23 |

The LangGraph, LiteLLM, Langfuse and Claude Agent SDK packages resolve together with the backend on
Python 3.12 (`uv pip compile`). They were resolved, not exercised. `google-antigravity` was checked
on PyPI only and was not part of that resolution.

## Decisions

**T-001: Standalone repository.** The starting folder held an unrelated project, so NEXUS lives in
`~/code/Nexus`.

**T-002: Python 3.12 managed by uv.** The system Python is 3.9, below every backend requirement.
SQLAlchemy 2.1 needs 3.11 or later; 3.12 has the broadest SDK support.

**T-003: Next rewrite instead of CORS.** A single browser origin keeps the API surface smaller and
needs no CORS policy. Tauri packaging will need to revisit this.

**T-004: Synchronous SQLAlchemy for CRUD.** Plain `def` routes run in FastAPI's threadpool and stay
simple. Long-running execution will use background workers (Milestone 3), not async database calls.

**T-005: Dockview JSON stored opaquely.** The backend validates only the envelope (`grid`, `panels`)
and size. Dockview owns that format; duplicating its schema would break on upgrades.

**T-006: Presets are declarative and live with the panels.** Hand-written Dockview JSON is brittle. A
preset is a list of placements resolved at load. The backend stores only the preset key.

**T-007: Export is a versioned envelope without IDs.** `format` plus `schema_version` lets foreign or
future files fail validation, and imports can never collide.

**T-008: Self-hosted fonts through Fontsource.** `next/font/google` needs network access on a
first build, which conflicts with local-first operation.

**T-009: Launch token, with the Next proxy as the only browser gateway.** Each backend launch writes
a random token to `~/.nexus/api-token` (mode 0600), required on every API route except health.
`src/proxy.ts` adds it to requests, but only for a local Host and a same-origin caller. Without that
check a rebinding domain could use the proxy, whose rewrite would pass the backend's Host filter.
Processes running as the same user can read the token, so this does not defend against them.
The frontend must bind to `127.0.0.1`: the Host check alone cannot stop a network client, which can
send any Host header.

**T-010: `cn` package.** shadcn's current scaffold depends on `cn` (published by shadcn-ui) instead of
clsx plus tailwind-merge. Kept.

**T-011: `@types/node` 22.** Next's scaffold pins 20, which Vitest 5 rejects. 22 matches the runtime.

**T-012: Vitest without `@vitejs/plugin-react`.** That plugin's peer range conflicted during install,
and the built-in JSX transform is enough.

**T-013: Field specs compile to Pydantic.** Config models are generated from declarative `FieldSpec`s
rather than written as classes. Plugins in another process can then declare nodes as JSON, and the
main process still validates with Pydantic.

**T-014: Drafts save without semantic validation.** Rejecting invalid graphs would make autosave lose
work in progress. Validity is a report, not a save condition.

**T-015: Whole-document saves.** The client sends the full document on each autosave. It is simple and
idempotent; documents are capped at 5 MB.

**T-016: Monaco bundled locally.** `@monaco-editor/react` loads Monaco from a CDN by default, which
breaks offline use. `loader.config({ monaco })` points it at the npm package, and an E2E test asserts
no external request is made.

**T-017: Node IDs on the client.** The editor creates IDs so undo and offline edits need no round
trip. The backend still rejects duplicates.

**T-018: Cycles need a bounding node.** A cycle is valid only through a node type with
`bounds_cycles`, currently Loop, so a graph cannot loop forever by accident.

**T-019: Pause at node entry.** Leaving the LangGraph stream cancels parallel tasks in the same step,
as a probe confirmed. Instead, each node checks for a pause before starting and raises an interrupt,
so running nodes finish.

**T-020: Approval loops until it has a decision.** LangGraph re-enters an interrupted node and matches
resume values by position, so a pause released on a node would otherwise answer its approval.

**T-021: Merge nodes use `defer=True`.** A deferred node waits for every active branch, whatever the
branch lengths, and also works when a conditional branch was not taken.

**T-022: Runs keep a copy of their graph.** Editing or deleting a workflow cannot change what a paused
run resumes.

**T-023: Unimplemented nodes are refused, never simulated.** A missing handler stops the run before it
starts and names the milestone. Mock handlers may exist only inside tests.

**T-024: Checkpoints in a separate SQLite file.** LangGraph owns `checkpoints.db`; relational records
stay in `nexus.db`, behind `ExecutionStore`.

**T-025: LiteLLM pinned to exactly 1.106.5.** LiteLLM had malicious PyPI releases in March 2026 and
on 21 October 2026 (1.107.0, [MAL-2026-2144](https://osv.dev/vulnerability/MAL-2026-2144)). It runs
inside the process that holds API keys. The version is exact, locked by hash in `uv.lock`, and must
be raised only by hand, after checking advisories. Before upgrading, look for `cook.pth`, `cook.py`
and an unexpected `sitecustomize.py` in site-packages. Isolating LiteLLM in its own process is worth
revisiting with the plugin sandbox.

**T-026: Master key outside the database.** A stolen `nexus.db` alone reveals no secret. A process
running as the same user can still reach the keychain entry or key file.

**T-027: Parameters reuse the field system.** Allowed parameters are `FieldSpec`s filtered by
capabilities, so an unsupported parameter has no control and fails validation.

**T-028: Capability overrides are stored apart.** Rediscovery refreshes detected values without
erasing manual corrections.

**T-029: LiteLLM loads late, with its local price table.** Importing it takes seconds, and by default
it fetches prices online, which local-first operation cannot rely on.

**T-030: Subscriptions are not providers.** The registry holds API credentials only. Claude and
Google subscriptions belong to runtime adapters in Milestone 5.

**T-031: The Claude runtime uses an API key only.** Anthropic's legal page tells developers using the
Agent SDK to use API keys, and allows plan logins for the unmodified Claude Code binary. It does not
address one person's own SDK script, so NEXUS takes the clear path. The SDK child process inherits
the environment, so the adapter passes the key, blanks `CLAUDE_CODE_OAUTH_TOKEN` and loads no user
settings. Otherwise it could fall back to a personal login, or run someone's hooks. Whether to add a
runtime that drives the unmodified `claude` binary with a personal login is open, and is the
owner's decision to make after reading the current terms.

**T-032: The Antigravity runtime uses a Gemini API key, and stays read-only.** The SDK documents only
a Gemini key or Vertex credentials. Nothing confirms that a Google AI subscription works. Write
access stays off until permissions are enforced.

**T-033: Agent SDKs are an optional extra.** They add about 430 MB of binaries and are not needed for
local models. Versions are exact, for the reasons in T-025.

**T-034: Runtimes come from the registry.** An agent's `runtime` is free text checked against
registered runtimes, so a new runtime needs no schema change.

**T-035: Every runtime error is scrubbed.** SDK exceptions can quote their configuration, so the
registry removes the key from any error, whatever its type.

**T-036: Paid calls need a decision per run.** `allow_paid` defaults to false, and retries keep the
original run's choice.

**T-037: One sandboxed process per plugin call.** Without a long-lived process there is no protocol
state to protect. It is simple and contains crashes, at the cost of a process start per call.

**T-038: No sandbox, no code.** A plain subprocess could read the master key, so platforms without
`sandbox-exec` refuse code plugins instead of running them with weaker protection.

**T-039: Read access is denied by area.** The profile starts from allow-all, denies `/Users`,
`/Volumes` and the NEXUS folder, then opens exact paths. This passed every escape test. System files
stay readable. A stricter deny-all profile was not tried.

**T-040: Panels are single files with no route to the API.** A sandboxed iframe has an opaque origin,
so the proxy refuses its requests, and the page policy sets `connect-src 'none'`.

**T-041: Provider contributions are data.** A preset cannot touch keys, because no plugin code runs
for it.

## External integrations checked

| Integration | Finding | Consequence |
|---|---|---|
| Antigravity | The [official SDK](https://antigravity.google/docs/sdk/overview/) is the Python package `google-antigravity`, an async `Agent` around a bundled runtime binary, separate from the IDE and from the managed Gemini API | Adapter targets the SDK only; never drives the IDE. A similarly named third-party GitHub repository exists and must not be used |
| OpenCode | [`opencode serve`](https://opencode.ai/docs/server/) is a headless HTTP server with an OpenAPI 3.1 spec at `/doc`, defaulting to `127.0.0.1:4096`, with optional basic auth | Integrate over HTTP from the spec, in a later milestone. Endpoint details not yet reviewed |
| Claude Agent SDK | `query()` with `ClaudeAgentOptions`; the child process inherits the environment | Adapter built from the installed package; no real call made |
