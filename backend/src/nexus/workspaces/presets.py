# Workspaces seeded on first launch. Their layouts live with the panels, in the frontend.
DEFAULT_WORKSPACES: tuple[tuple[str, str, str], ...] = (
    ("Workflow Builder", "workflow-builder", "Design workflows on the canvas."),
    ("Agent Development", "agent-development", "Author and test agent definitions."),
    ("Debug Studio", "debug-studio", "Inspect traces, state and failures."),
    ("Execution Monitor", "execution-monitor", "Follow running workflows."),
    ("Analytics", "analytics", "Review tokens, cost and model usage."),
    ("Custom Workspace", "custom", "A minimal starting point to arrange freely."),
)
