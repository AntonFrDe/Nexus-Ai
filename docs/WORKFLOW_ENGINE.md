# Workflow engine

**Status: the document format and validator exist. Execution is design only** and will be checked
against LangGraph itself in Milestone 3.

## Principles

- The frontend edits data. It never executes workflow logic.
- The backend validates, compiles and runs; Pydantic is authoritative.
- Graph compilation never evaluates code supplied by the frontend.
- Topology is separate from node implementation.

## Workflow document

```json
{
  "format": "nexus.workflow",
  "workflow": {
    "name": "Example",
    "description": "",
    "schema_version": 1,
    "nodes": [{
      "id": "n1",
      "type": "core.llm_agent",
      "position": { "x": 0, "y": 0 },
      "label": "",
      "config": {},
      "runtime": {},
      "permissions": [],
      "input_schema": null,
      "output_schema": null,
      "parent_id": null,
      "width": null,
      "height": null
    }],
    "edges": [{
      "id": "e1",
      "source": "n1",
      "source_port": "out",
      "target": "n2",
      "target_port": "in",
      "label": ""
    }],
    "variables": {},
    "config": {},
    "policies": {},
    "metadata": {}
  }
}
```

Secrets appear as `{"secret": "<name>"}`, never as values. `schema_version` upgrades run through
`workflows/migrations.py`: pure functions applied in order when a document is imported or read. No
real migration exists yet, because the schema is still at version 1.

## Validation rules

| Severity | Codes |
|---|---|
| Error | `unknown_node_type`, `duplicate_node_id`, `duplicate_edge_id`, `duplicate_edge`, `invalid_config`, `invalid_runtime`, `unknown_permission`, `invalid_parent`, `edge_unknown_node`, `edge_unknown_port`, `edge_to_self`, `edge_port_type`, `missing_required_input`, `input_accepts_one`, `unbounded_cycle` |
| Warning | `no_input`, `no_output`, `disconnected` |

## Pipeline

```mermaid
flowchart LR
  Doc[Workflow JSON] --> V[Validate schema, types, references]
  V --> C[Compile to LangGraph StateGraph]
  C --> R[Background runner]
  R --> E[Event stream to the UI]
  R --> K[(Checkpoints)]
  R --> H[(Execution records)]
```

## Lifecycle

```mermaid
stateDiagram-v2
  [*] --> PENDING
  PENDING --> VALIDATING
  VALIDATING --> RUNNING
  VALIDATING --> FAILED
  RUNNING --> PAUSED
  RUNNING --> WAITING_FOR_APPROVAL
  RUNNING --> COMPLETED
  RUNNING --> FAILED
  RUNNING --> CANCELLED
  PAUSED --> RUNNING
  PAUSED --> CANCELLED
  WAITING_FOR_APPROVAL --> RUNNING
  WAITING_FOR_APPROVAL --> CANCELLED
```

## Mapping onto LangGraph

| Requirement | Intended mechanism |
|---|---|
| Sequence, branching | Edges and conditional edges |
| Parallel, merge | Fan-out with state reducers |
| Loops | Cycles with an enforced recursion limit |
| Nested workflows | Subgraphs |
| Human approval, pause | Interrupts |
| Resume, checkpoint restore | SQLite checkpointer by thread |
| Retry | Node retry policies |

Each row needs confirmation against the LangGraph documentation during Milestone 3.

## Agent runtimes

Adapters declare capabilities. An operation a runtime lacks returns an explicit unsupported-capability
response and is never simulated.

Mock providers exist for development and tests only, and their output is always labeled as mocked.
