# Plugin system

**Status: design only.** What exists today is `PanelRegistry` in the frontend and `NodeRegistry` in
the backend, both used only by built-ins. Everything else here is planned for Milestone 6 and may change once the node and provider contracts stabilize.

## Principles

1. Core features use the same registries that plugins will use.
2. Backend plugins never run in the main process.
3. Frontend plugins get a restricted API, not application internals.
4. Permissions are declared in the manifest, granted by the user and enforced by the host.
5. A missing plugin degrades visibly and never prevents a workspace from opening. This already
   works: `sanitizeLayout` replaces unknown panels with a stand-in.

## Manifest (draft)

```json
{
  "id": "com.example.hello",
  "name": "Hello",
  "version": "1.0.0",
  "description": "Example plugin",
  "author": "Example",
  "nexusApi": "^1.0.0",
  "category": "tool",
  "entryPoints": { "backend": "backend/main.py", "frontend": "frontend/index.js" },
  "dependencies": {},
  "permissions": ["network:api.example.com"]
}
```

## Contribution points

| Point | Registry | State |
|---|---|---|
| Workspace panels | `PanelRegistry` | Exists, built-in only |
| Workflow nodes | `NodeRegistry` | Exists, built-in only. Types are plain data, so they can cross a process boundary |
| Model providers | Provider registry | Milestone 4 |
| Agent runtimes | Runtime registry | Milestone 5 |
| Tools, storage, themes, integrations | To define | Milestone 6 |

## Isolation

- **Backend:** one subprocess per plugin, speaking JSON-RPC over stdio, with no inherited environment
  or credentials. The host brokers files, network, shell, environment, credentials and inter-plugin
  access. A subprocess alone is not a sandbox, so macOS, Linux and Windows confinement must each be
  evaluated before untrusted plugins are supported.
- **Frontend:** sandboxed iframes on a separate origin, communicating by `postMessage` through a
  versioned API. Dockview panels host the iframe.

## Lifecycle

Discovery, installation, enable and disable, uninstallation, version and dependency checks, conflict
detection and configuration. No marketplace until the plugin API has proven itself.
