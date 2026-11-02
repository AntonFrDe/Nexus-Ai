from nexus.nodes.registry import NodeRegistry
from nexus.nodes.spec import Condition, FieldKind, FieldSpec, NodeType, PortSpec

AGENTS = "Agents"
MODELS = "Models"
CONTROL = "Control flow"
DATA = "Data"
TOOLS = "Tools"
MONITORING = "Monitoring"
CANVAS = "Canvas"


def field(name: str, label: str, kind: FieldKind = FieldKind.TEXT, **options) -> FieldSpec:
    return FieldSpec(name=name, label=label, kind=kind, **options)


def port(id_: str, label: str | None = None, type_: str = "any", **options) -> PortSpec:
    return PortSpec(id=id_, label=label or id_.replace("_", " ").title(), type=type_, **options)


IN = port("in", "Input", required=True)
OUT = port("out", "Output")
TEXT_IN = port("in", "Input", "text", required=True)
TEXT_OUT = port("out", "Output", "text")
JSON_OUT = port("out", "Output", "json")
MODEL_IN = port("model", "Model", "model")
MODEL_OUT = port("model", "Model", "model")
TOOLS_IN = port("tools", "Tools", "tool", multiple=True)
MEMORY_IN = port("memory", "Memory", "memory")
TOOL_OUT = port("tool", "Tool", "tool")

MODEL_ID = field(
    "model",
    "Model",
    required=True,
    language="model",
    description="Provider and model, such as Ollama/llama3",
)
SYSTEM_PROMPT = field("system_prompt", "System prompt", FieldKind.TEXTAREA)
TEMPERATURE = field(
    "temperature", "Temperature", FieldKind.SLIDER, minimum=0, maximum=2, step=0.05, advanced=True
)
MAX_TOKENS = field("max_tokens", "Max output tokens", FieldKind.NUMBER, minimum=1, advanced=True)
MAX_ITERATIONS = field(
    "max_iterations", "Max iterations", FieldKind.NUMBER, minimum=1, default=10, advanced=True
)
EXPRESSION = field(
    "expression",
    "Condition",
    required=True,
    language="expression",
    description="Declarative expression on state, such as score > 0.8. Never run as Python.",
)
HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]


def agent(type_: str, title: str, description: str, icon: str, *extra: FieldSpec, **kw) -> NodeType:
    return NodeType(
        type=f"core.{type_}",
        title=title,
        category=AGENTS,
        description=description,
        icon=icon,
        inputs=kw.pop("inputs", [TEXT_IN, MODEL_IN, TOOLS_IN, MEMORY_IN]),
        outputs=kw.pop("outputs", [TEXT_OUT]),
        fields=[MODEL_ID, SYSTEM_PROMPT, *extra, TEMPERATURE, MAX_TOKENS, MAX_ITERATIONS],
        **kw,
    )


def node(type_: str, title: str, category: str, description: str, icon: str, **kw) -> NodeType:
    return NodeType(
        type=f"core.{type_}",
        title=title,
        category=category,
        description=description,
        icon=icon,
        **kw,
    )


BUILT_IN_NODES: list[NodeType] = [
    agent("llm_agent", "LLM Agent", "Single model turn with optional tools.", "bot"),
    agent(
        "coding_agent",
        "Coding Agent",
        "Agent specialized in reading and changing code.",
        "code",
        field("workspace_path", "Workspace path", required=True),
        permissions=["filesystem", "shell"],
    ),
    agent(
        "multi_agent",
        "Multi-Agent",
        "Several agents collaborating on one task.",
        "users",
        field(
            "strategy",
            "Strategy",
            FieldKind.SELECT,
            options=["round_robin", "debate", "swarm"],
            default="round_robin",
        ),
        field(
            "agents",
            "Agents",
            FieldKind.ARRAY,
            required=True,
            item=field(
                "agent",
                "Agent",
                FieldKind.OBJECT,
                fields=[
                    field("name", "Name", required=True),
                    field("role", "Role", FieldKind.TEXTAREA),
                ],
            ),
        ),
    ),
    agent(
        "supervisor_agent",
        "Supervisor Agent",
        "Delegates work to connected agents and decides when to stop.",
        "crown",
        field("max_delegations", "Max delegations", FieldKind.NUMBER, minimum=1, default=5),
    ),
    agent(
        "evaluator_agent",
        "Evaluator Agent",
        "Scores an output against criteria.",
        "gauge",
        field("criteria", "Criteria", FieldKind.TEXTAREA, required=True),
        outputs=[port("pass"), port("fail")],
    ),
    node(
        "human_approval",
        "Human Approval",
        AGENTS,
        "Pauses the workflow until a person decides.",
        "user-check",
        shape="diamond",
        inputs=[IN],
        outputs=[port("approved"), port("rejected")],
        fields=[
            field("prompt", "Prompt", FieldKind.TEXTAREA, required=True),
            field("timeout_hours", "Timeout (hours)", FieldKind.NUMBER, minimum=0, advanced=True),
        ],
    ),
    agent(
        "custom_agent",
        "Custom Agent",
        "Agent from a registered definition and runtime.",
        "bot-message-square",
        field("agent_id", "Agent definition", required=True),
    ),
    node(
        "model_selector",
        "Model Selector",
        MODELS,
        "Picks a model and its parameters.",
        "brain",
        outputs=[MODEL_OUT],
        fields=[MODEL_ID, TEMPERATURE, MAX_TOKENS],
    ),
    node(
        "model_router",
        "Model Router",
        MODELS,
        "Chooses a model for each request by rule.",
        "route",
        inputs=[IN],
        outputs=[MODEL_OUT],
        fields=[
            field(
                "routes",
                "Routes",
                FieldKind.ARRAY,
                required=True,
                item=field(
                    "route",
                    "Route",
                    FieldKind.OBJECT,
                    fields=[
                        field("when", "When", required=True),
                        field("model", "Model", required=True),
                    ],
                ),
            ),
            field("default_model", "Default model", required=True),
        ],
    ),
    node(
        "embedding_model",
        "Embedding Model",
        MODELS,
        "Turns text into vectors.",
        "binary",
        inputs=[TEXT_IN],
        outputs=[port("out", "Vectors", "embedding")],
        fields=[MODEL_ID, field("dimensions", "Dimensions", FieldKind.NUMBER, minimum=1)],
    ),
    node(
        "reranker",
        "Reranker",
        MODELS,
        "Reorders candidates by relevance.",
        "list-ordered",
        inputs=[port("query", "Query", "text", required=True), port("documents", required=True)],
        outputs=[JSON_OUT],
        fields=[MODEL_ID, field("top_k", "Top K", FieldKind.NUMBER, minimum=1, default=5)],
    ),
    node(
        "model_fallback",
        "Model Fallback",
        MODELS,
        "Tries models in order until one succeeds.",
        "life-buoy",
        outputs=[MODEL_OUT],
        fields=[
            field(
                "models",
                "Models, in order",
                FieldKind.ARRAY,
                required=True,
                item=field("model", "Model"),
            )
        ],
    ),
    node(
        "if_else",
        "IF / ELSE",
        CONTROL,
        "Branches on a condition.",
        "split",
        shape="diamond",
        inputs=[IN],
        outputs=[port("true"), port("false")],
        fields=[EXPRESSION],
    ),
    node(
        "switch",
        "Switch",
        CONTROL,
        "Branches on a value.",
        "git-fork",
        shape="diamond",
        inputs=[IN],
        outputs=[port("case_1", "Case 1"), port("case_2", "Case 2"), port("default")],
        fields=[
            field("value", "Value", required=True, language="expression"),
            field("case_1", "Case 1 equals", required=True),
            field("case_2", "Case 2 equals"),
        ],
    ),
    node(
        "loop",
        "Loop",
        CONTROL,
        "Repeats a body until a condition or limit.",
        "repeat",
        inputs=[IN, port("repeat", "Repeat", multiple=True)],
        outputs=[port("body"), port("done")],
        bounds_cycles=True,
        fields=[
            field(
                "mode",
                "Mode",
                FieldKind.SELECT,
                options=["count", "while", "for_each"],
                default="count",
                required=True,
            ),
            field(
                "count",
                "Iterations",
                FieldKind.NUMBER,
                minimum=1,
                required=True,
                visible_when=Condition(field="mode", equals=["count"]),
            ),
            field(
                "condition",
                "While",
                required=True,
                language="expression",
                visible_when=Condition(field="mode", equals=["while"]),
            ),
            field("max_iterations", "Hard limit", FieldKind.NUMBER, minimum=1, default=100),
        ],
    ),
    node(
        "parallel",
        "Parallel",
        CONTROL,
        "Runs every outgoing branch at once.",
        "columns-3",
        inputs=[IN],
        outputs=[port("branches", "Branches")],
        fields=[field("max_concurrency", "Max concurrency", FieldKind.NUMBER, minimum=1)],
    ),
    node(
        "merge",
        "Merge",
        CONTROL,
        "Joins branches into one result.",
        "merge",
        inputs=[port("in", "Inputs", required=True, multiple=True)],
        outputs=[OUT],
        fields=[
            field(
                "strategy",
                "Strategy",
                FieldKind.SELECT,
                options=["wait_all", "first", "concatenate"],
                default="wait_all",
            )
        ],
    ),
    node(
        "retry",
        "Retry",
        CONTROL,
        "Retries the connected branch on failure.",
        "rotate-cw",
        inputs=[IN],
        outputs=[port("attempt"), port("exhausted")],
        fields=[
            field("attempts", "Attempts", FieldKind.NUMBER, minimum=1, default=3, required=True),
            field("backoff_seconds", "Backoff (s)", FieldKind.NUMBER, minimum=0, default=1),
        ],
    ),
    node(
        "delay",
        "Delay",
        CONTROL,
        "Waits before continuing.",
        "timer",
        inputs=[IN],
        outputs=[OUT],
        fields=[field("seconds", "Seconds", FieldKind.NUMBER, minimum=0, required=True)],
    ),
    node(
        "sub_workflow",
        "Sub-workflow",
        CONTROL,
        "Runs another workflow as one step.",
        "workflow",
        inputs=[IN],
        outputs=[OUT],
        fields=[field("workflow_id", "Workflow", required=True)],
    ),
    node(
        "stop",
        "Stop",
        CONTROL,
        "Ends the workflow.",
        "octagon",
        shape="pill",
        inputs=[IN],
        fields=[
            field(
                "status",
                "Status",
                FieldKind.SELECT,
                options=["completed", "failed"],
                default="completed",
            )
        ],
    ),
    node(
        "error_handler",
        "Error Handler",
        CONTROL,
        "Receives failures from nodes set to continue on error.",
        "shield-alert",
        outputs=[port("error", "Error", "json")],
        fields=[field("scope", "Node filter", description="Empty handles every node")],
    ),
    node(
        "input",
        "Input",
        DATA,
        "Entry point; defines the workflow's inputs.",
        "log-in",
        shape="pill",
        outputs=[OUT],
        fields=[field("data_schema", "Input schema", FieldKind.JSON, default={"type": "object"})],
    ),
    node(
        "output",
        "Output",
        DATA,
        "Final result of the workflow.",
        "log-out",
        shape="pill",
        inputs=[IN],
        fields=[field("name", "Output name", default="result")],
    ),
    node(
        "json_parser",
        "JSON Parser",
        DATA,
        "Parses text into JSON.",
        "braces",
        inputs=[TEXT_IN],
        outputs=[JSON_OUT],
        fields=[field("data_schema", "Expected schema", FieldKind.JSON, advanced=True)],
    ),
    node(
        "data_transform",
        "Data Transform",
        DATA,
        "Reshapes data with a declarative template.",
        "shuffle",
        inputs=[IN],
        outputs=[OUT],
        fields=[
            field("template", "Template", FieldKind.CODE, language="json", required=True),
        ],
    ),
    node(
        "variable",
        "Variable",
        DATA,
        "Reads or writes a workflow variable.",
        "variable",
        inputs=[port("in", "Value")],
        outputs=[OUT],
        fields=[
            field("name", "Name", required=True),
            field(
                "operation",
                "Operation",
                FieldKind.SELECT,
                options=["read", "write"],
                default="read",
                required=True,
            ),
        ],
    ),
    node(
        "memory",
        "Memory",
        DATA,
        "Conversation or long-term memory store.",
        "database-zap",
        outputs=[port("memory", "Memory", "memory")],
        fields=[
            field(
                "kind",
                "Kind",
                FieldKind.SELECT,
                options=["buffer", "summary", "vector"],
                default="buffer",
            ),
            field("namespace", "Namespace", required=True),
        ],
    ),
    node(
        "database",
        "Database",
        DATA,
        "Runs a query on a configured database.",
        "database",
        inputs=[port("in", "Parameters")],
        outputs=[JSON_OUT],
        permissions=["network"],
        fields=[
            field("connection", "Connection", FieldKind.SECRET, required=True),
            field("query", "Query", FieldKind.CODE, language="sql", required=True),
        ],
    ),
    node(
        "file_reader",
        "File Reader",
        DATA,
        "Reads a file inside an allowed directory.",
        "file-input",
        inputs=[port("in", "Path")],
        outputs=[TEXT_OUT],
        permissions=["filesystem"],
        fields=[field("path", "Path", required=True)],
    ),
    node(
        "file_writer",
        "File Writer",
        DATA,
        "Writes a file inside an allowed directory.",
        "file-output",
        inputs=[IN],
        outputs=[port("path", "Path", "text")],
        permissions=["filesystem"],
        fields=[
            field("path", "Path", required=True),
            field("overwrite", "Overwrite", FieldKind.BOOLEAN, default=False),
        ],
    ),
    node(
        "http_request",
        "HTTP Request",
        TOOLS,
        "Calls an HTTP endpoint.",
        "globe",
        inputs=[port("in", "Input")],
        outputs=[JSON_OUT, TOOL_OUT],
        permissions=["network"],
        fields=[
            field("method", "Method", FieldKind.SELECT, options=HTTP_METHODS, default="GET"),
            field("url", "URL", required=True),
            field("headers", "Headers", FieldKind.JSON, advanced=True),
            field(
                "body",
                "Body",
                FieldKind.CODE,
                language="json",
                visible_when=Condition(field="method", equals=["POST", "PUT", "PATCH"]),
            ),
            field("auth", "Auth secret", FieldKind.SECRET, advanced=True),
        ],
    ),
    node(
        "mcp_tool",
        "MCP Tool",
        TOOLS,
        "Exposes a tool from an MCP server.",
        "plug",
        outputs=[TOOL_OUT],
        permissions=["network"],
        fields=[
            field("server", "MCP server", required=True),
            field("tool", "Tool name", required=True),
        ],
    ),
    node(
        "python_executor",
        "Python Executor",
        TOOLS,
        "Runs Python in a sandbox. Always requires approval.",
        "terminal-square",
        inputs=[IN],
        outputs=[OUT, TOOL_OUT],
        permissions=["shell", "filesystem", "network"],
        fields=[field("code", "Code", FieldKind.CODE, language="python", required=True)],
    ),
    node(
        "terminal",
        "Terminal",
        TOOLS,
        "Runs an allowlisted command. Always requires approval.",
        "square-terminal",
        inputs=[IN],
        outputs=[TEXT_OUT, TOOL_OUT],
        permissions=["shell"],
        fields=[
            field("command", "Command", required=True),
            field("working_directory", "Working directory", advanced=True),
        ],
    ),
    node(
        "browser",
        "Browser",
        TOOLS,
        "Automates a browser session.",
        "app-window",
        inputs=[IN],
        outputs=[JSON_OUT, TOOL_OUT],
        permissions=["network"],
        fields=[field("start_url", "Start URL", required=True)],
    ),
    node(
        "file_system",
        "File System",
        TOOLS,
        "Gives agents access to allowed directories.",
        "folder-tree",
        outputs=[TOOL_OUT],
        permissions=["filesystem"],
        fields=[
            field(
                "allowed_paths",
                "Allowed paths",
                FieldKind.ARRAY,
                required=True,
                item=field("path", "Path"),
            ),
            field("read_only", "Read only", FieldKind.BOOLEAN, default=True),
        ],
    ),
    node(
        "custom_tool",
        "Custom Tool",
        TOOLS,
        "Tool from a registered definition.",
        "wrench",
        outputs=[TOOL_OUT],
        fields=[
            field("tool_id", "Tool", required=True),
            field(
                "operations",
                "Allowed operations",
                FieldKind.MULTI_SELECT,
                options=["read", "write", "execute"],
                advanced=True,
            ),
        ],
    ),
    node(
        "logger",
        "Logger",
        MONITORING,
        "Records the value that passes through.",
        "scroll-text",
        inputs=[IN],
        outputs=[OUT],
        fields=[
            field(
                "level",
                "Level",
                FieldKind.SELECT,
                options=["debug", "info", "warning", "error"],
                default="info",
            )
        ],
    ),
    node(
        "cost_tracker",
        "Cost Tracker",
        MONITORING,
        "Stops the branch past a budget.",
        "coins",
        inputs=[IN],
        outputs=[OUT, port("over_budget", "Over budget")],
        fields=[field("budget_usd", "Budget (USD)", FieldKind.NUMBER, minimum=0, required=True)],
    ),
    node(
        "evaluator",
        "Evaluator",
        MONITORING,
        "Computes a metric on an output.",
        "chart-no-axes-column",
        inputs=[IN],
        outputs=[OUT, port("score", "Score", "json")],
        fields=[
            field(
                "metric",
                "Metric",
                FieldKind.SELECT,
                options=["exact_match", "contains", "json_valid", "length"],
                default="json_valid",
            )
        ],
    ),
    node(
        "guardrail",
        "Guardrail",
        MONITORING,
        "Blocks content that breaks a rule.",
        "shield-check",
        inputs=[IN],
        outputs=[port("allowed"), port("blocked")],
        fields=[
            field(
                "rules",
                "Rules",
                FieldKind.ARRAY,
                required=True,
                item=field("rule", "Rule"),
            )
        ],
    ),
    node(
        "performance_monitor",
        "Performance Monitor",
        MONITORING,
        "Warns when a branch is slower than expected.",
        "activity",
        inputs=[IN],
        outputs=[OUT],
        fields=[field("warn_after_ms", "Warn after (ms)", FieldKind.NUMBER, minimum=0)],
    ),
    node(
        "group",
        "Group",
        CANVAS,
        "Frames related nodes.",
        "group",
        shape="group",
        executable=False,
    ),
    node(
        "annotation",
        "Annotation",
        CANVAS,
        "A note on the canvas.",
        "sticky-note",
        shape="annotation",
        executable=False,
        fields=[field("text", "Text", FieldKind.TEXTAREA)],
    ),
]

RUNTIME_FIELDS: list[FieldSpec] = [
    field("timeout_seconds", "Timeout (s)", FieldKind.NUMBER, minimum=0),
    field("max_retries", "Max retries", FieldKind.NUMBER, minimum=0),
    field("retry_backoff_seconds", "Retry backoff (s)", FieldKind.NUMBER, minimum=0),
    field(
        "on_error",
        "On error",
        FieldKind.SELECT,
        options=["fail", "continue"],
        default="fail",
    ),
]


def create_node_registry() -> NodeRegistry:
    registry = NodeRegistry()
    for node_type in BUILT_IN_NODES:
        registry.register(node_type)
    return registry
