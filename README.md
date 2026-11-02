# NEXUS

A local-first studio for designing, running and debugging AI agent workflows.

**Status: Milestone 4 of 8.** Workflows run with live status, pause, resume and approval, and the
Model Registry manages providers, encrypted keys and models. Workflows do not call models yet:
agents arrive in Milestone 5, and only logic and data nodes run today. See
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

Open http://localhost:3000. Data lives in `~/.nexus` (override with `NEXUS_DATA_DIR`). On first start
the backend adds a `nexus-studio` entry to your system keychain, holding the key that encrypts your
API keys.

For local models, install [Ollama](https://ollama.com), pull a model, then add an Ollama provider in
the Model Registry panel.

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
