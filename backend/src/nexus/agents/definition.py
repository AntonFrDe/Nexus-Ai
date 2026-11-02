"""An agent keeps what it is apart from which model and runtime carry it out, so it can move
between compatible runtimes by changing those two fields."""

from nexus.nodes.catalog import field
from nexus.nodes.spec import Condition, FieldKind, FieldSpec

AGENT_FIELDS: list[FieldSpec] = [
    field("description", "Description", FieldKind.TEXTAREA),
    field("role", "Role"),
    field("system_prompt", "System prompt", FieldKind.TEXTAREA, required=True),
    field(
        "runtime",
        "Runtime",
        required=True,
        default="native",
        language="runtime",
        description="Any registered runtime; see the list below.",
    ),
    field("model", "Model", required=True, language="model"),
    field(
        "tools",
        "Tools",
        FieldKind.ARRAY,
        item=field("tool", "Tool"),
        description="Runtime tool names. The native runtime has none.",
    ),
    field("mcp_servers", "MCP servers", FieldKind.JSON, advanced=True),
    field("memory", "Memory", FieldKind.JSON, advanced=True),
    field("input_schema", "Input schema", FieldKind.JSON, advanced=True),
    field("output_schema", "Output schema", FieldKind.JSON, advanced=True),
    field("max_turns", "Max turns", FieldKind.NUMBER, minimum=1, advanced=True),
    field(
        "max_budget_usd",
        "Budget per call (USD)",
        FieldKind.NUMBER,
        minimum=0,
        advanced=True,
        visible_when=Condition(field="runtime", equals=["claude-agent-sdk"]),
    ),
    field("timeout_seconds", "Timeout (s)", FieldKind.NUMBER, minimum=0, advanced=True),
    field("max_retries", "Max retries", FieldKind.NUMBER, minimum=0, advanced=True),
    field(
        "permissions",
        "Permissions",
        FieldKind.MULTI_SELECT,
        options=["filesystem", "network", "shell"],
        advanced=True,
    ),
    field("session", "Session", FieldKind.JSON, advanced=True),
]
