# Technical decisions

Versions were checked against npm and PyPI on 2026-11-02.

## Verified stack

| Layer | Package | Version |
|---|---|---|
| Frontend | next / react | 16.4.3 / 19.3.0 |
| Frontend | dockview-react | 8.8.3 |
| Frontend | zustand / zod | 5.0.16 / 4.6.7 |
| Frontend | tailwindcss / shadcn (base-ui) | 4.x / 4.23 |
| Tests | vitest / playwright | 5.0.5 / 1.64.1 |
| Backend | fastapi / pydantic | 0.162.0 / 2.14.2 |
| Backend | sqlalchemy / alembic | 2.1.x / 1.20.x |
| Future | langgraph / langgraph-checkpoint-sqlite | 1.2.19 / 3.1.3 |
| Future | litellm / langfuse | 1.106.6 / 5.1.0 |
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

**T-009 (open): Local API authentication.** Binding to loopback does not stop other local processes.
A per-launch token is needed before the API can run workflows. Blocks Milestone 3.

**T-010: `cn` package.** shadcn's current scaffold depends on `cn` (published by shadcn-ui) instead of
clsx plus tailwind-merge. Kept.

**T-011: `@types/node` 22.** Next's scaffold pins 20, which Vitest 5 rejects. 22 matches the runtime.

**T-012: Vitest without `@vitejs/plugin-react`.** That plugin's peer range conflicted during install,
and the built-in JSX transform is enough.

## External integrations checked

| Integration | Finding | Consequence |
|---|---|---|
| Antigravity | The [official SDK](https://antigravity.google/docs/sdk/overview/) is the Python package `google-antigravity`, an async `Agent` around a bundled runtime binary, separate from the IDE and from the managed Gemini API | Adapter targets the SDK only; never drives the IDE. A similarly named third-party GitHub repository exists and must not be used |
| OpenCode | [`opencode serve`](https://opencode.ai/docs/server/) is a headless HTTP server with an OpenAPI 3.1 spec at `/doc`, defaulting to `127.0.0.1:4096`, with optional basic auth | Integrate over HTTP from the spec, in a later milestone. Endpoint details not yet reviewed |
| Claude Agent SDK | Installable, Python 3.10+ | API surface still to be reviewed at Milestone 5 |
