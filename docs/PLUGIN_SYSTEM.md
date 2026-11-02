# Plugin system

A plugin is a folder with a `nexus-plugin.json` manifest. It can add workflow nodes, workspace panels,
agent runtimes and model provider presets, without changing NEXUS. Four working examples are in
[`examples/plugins`](../examples/plugins).

**API version:** 1.0.0. **Platform:** code plugins run on macOS only (see [Isolation](#isolation)).

## Quick start

1. Copy `examples/plugins/word-count` and change its `id`, `name` and contribution ids.
2. Open the **Plugins** panel, paste the folder path and click **Install**. Nothing runs yet.
3. Click **Enable**, read the permissions, and accept.
4. Click **Reload to apply changes**. Your node appears in the Node Library.

## Manifest

```json
{
  "id": "com.example.hello",
  "name": "Hello",
  "version": "1.0.0",
  "description": "What it does",
  "author": "You",
  "category": "node",
  "nexus_api": ">=1.0,<2",
  "entry_points": { "backend": "plugin.py" },
  "dependencies": { "com.example.other": ">=1.0" },
  "permissions": ["network"],
  "config": [],
  "contributions": { "nodes": [], "panels": [], "runtimes": [], "providers": [] }
}
```

- `category` is `panel`, `node`, `provider`, `tool`, `runtime` or `integration`.
- `nexus_api` and `dependencies` use version ranges such as `>=1.0,<2`.
- Every contributed id must start with `<plugin id>.`, so a plugin cannot replace core items.
- `config` holds field specs. NEXUS renders the form and validates the values.

## Nodes and tools

A node declares its ports and fields as data, in the same format as built-in nodes. A tool is a node
in the `Tools` category. Agents cannot call plugin tools yet.

```python
from nexus_plugin import node, route

@node("com.example.hello.greet")
def greet(request):
    # request: input, inputs, config, workflow_input, plugin_config
    return f"Hello {request['input']}"

@node("com.example.hello.check")
def check(request):
    # route() picks the output ports to follow; a plain return follows all of them.
    return route(request["input"], "good" if request["input"] else "bad")
```

Inputs and outputs must be JSON values. Each call starts a new process, so keep state in the private
folder, which needs the `filesystem` permission.

## Agent runtimes

```python
from nexus_plugin import runtime

@runtime("com.example.hello.echo")
def echo(request):
    # request: prompt, model, system_prompt, plugin_config
    return {"text": request["prompt"]}
```

Declare it under `contributions.runtimes`, then use its id as an agent's runtime.

## Model providers

A provider contribution is data only: a preset for an OpenAI-style server. Plugin code never handles
provider keys.

```json
{
  "id": "com.example.hello.gateway",
  "title": "My gateway",
  "default_endpoint": "http://127.0.0.1:4000/v1",
  "auth": "optional",
  "paid": false
}
```

## Panels

A panel is one self-contained HTML page. Styles and scripts must be inline. It loads in a sandboxed
iframe with no network, no access to the app, and an opaque origin. It talks to NEXUS only through
`postMessage`:

```js
parent.postMessage({ nexus: true, id: 1, method: "getState" }, "*");
addEventListener("message", ({ data }) => console.log(data.id, data.result));
```

| Method | Result |
|---|---|
| `getContext` | `{ workspace }` |
| `getState` | The panel's saved state, or `null` |
| `setState` | Saves `params` with the workspace, up to 100 KB |

## Permissions

The user accepts all requested permissions when enabling. Anything else stays blocked.

| Permission | Grants |
|---|---|
| none | A scratch folder deleted after the call |
| `filesystem` | A private folder that lasts between calls |
| `network` | Network access, including this machine |
| `shell` | Running other programs |
| `env:NAME` | One environment variable, by name |

`credentials` and `plugins` are refused: there is no broker for secrets or other plugins yet. A new
version that asks for more permissions is disabled until the user accepts again.

## Isolation

Plugin code never runs in the NEXUS process. Each call is a new process under macOS `sandbox-exec`,
with an empty environment. Without a permission it cannot read `/Users`, `/Volumes` or the NEXUS data
folder, write outside its folder, use the network or start programs. It has 30 seconds and 5 MB of
output.

Without the sandbox, code does not run: NEXUS refuses to enable the plugin. That covers Linux and
Windows today.

**Limits of this protection.** `sandbox-exec` is deprecated by Apple, though it works on the tested
macOS 26.6. System files stay readable. CPU and memory are not limited beyond the time limit, and
the block on keychain services is not verified. Treat plugins as code you chose to trust.

## Lifecycle

| Action | Behavior |
|---|---|
| Install | Copies the folder and validates the manifest. Runs nothing. Refuses symbolic links and more than 50 MB |
| Update | Install a newer version of the same id |
| Enable | Checks API version, dependencies, conflicts and permissions |
| Disable | Refused while another plugin depends on it, or a provider uses its type |
| Uninstall | Removes its files and private data |

A plugin that cannot load stays off and never stops NEXUS from starting. Enabling or disabling
applies to the browser after a reload.

## Not available yet

Storage adapters, themes, secrets access, inter-plugin calls, a marketplace, and installing from a
URL or an archive.
