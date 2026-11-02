# NEXUS

A local-first studio for designing, running and debugging AI agent workflows.

**Status: Milestone 6 of 8.** Workflows run with live status, approval and recovery, call local
models through Ollama, and can be extended by sandboxed plugins. Cloud runtimes have never made a
real call, and agents have no tools yet. See [the roadmap](docs/ROADMAP.md).

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

To use the Claude Agent SDK or Antigravity runtimes, install them (about 430 MB) and add an API key in
the Agents panel:

```bash
cd backend && ~/.local/bin/uv sync --extra agents
```

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
- [Plugin system](docs/PLUGIN_SYSTEM.md)
- [Workflow engine](docs/WORKFLOW_ENGINE.md) (design)
- [Model routing](docs/MODEL_ROUTING.md) (design)
