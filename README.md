# NEXUS

A local-first studio for designing, running and debugging AI agent workflows.

**Status: Milestone 3 of 8.** Workflows now really run, with live status, pause, resume, human
approval and recovery after a restart. Only logic and data nodes can run so far: agents, models and
side-effect tools are refused with a reason until their milestones. See
[the roadmap](docs/ROADMAP.md).

## Run it

Requires [uv](https://docs.astral.sh/uv/) and Node 22.

```bash
make install
```

In two terminals:

```bash
make backend
```

```bash
make frontend
```

Open http://localhost:3000. Data lives in `~/.nexus` (override with `NEXUS_DATA_DIR`).

## Test

```bash
make test
```

```bash
make test-e2e
```

```bash
make lint
```

End-to-end tests need Chromium once (`cd frontend && npx playwright install chromium`) and use a
temporary data directory, never `~/.nexus`.

Example workflows are in `backend/examples`; import them from the Workflows panel.
`triage-with-approval` runs today, while the others need agents.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Technical decisions](docs/TECHNICAL_DECISIONS.md)
- [Plugin system](docs/PLUGIN_SYSTEM.md) (design)
- [Workflow engine](docs/WORKFLOW_ENGINE.md) (design)
- [Model routing](docs/MODEL_ROUTING.md) (design)
