import pytest
from pydantic import ValidationError

from nexus.nodes.catalog import BUILT_IN_NODES, CANVAS, create_node_registry
from nexus.nodes.config_model import validate_config
from nexus.nodes.registry import NodeRegistry, ports_compatible
from nexus.nodes.spec import Condition, FieldKind, FieldSpec, NodeType


def spec(name: str, kind: FieldKind, **options) -> FieldSpec:
    return FieldSpec(name=name, label=name.title(), kind=kind, **options)


def errors(fields: list[FieldSpec], config: dict) -> list[str]:
    return [path for path, _ in validate_config(str(id(fields)), fields, config)]


def test_catalog_covers_every_specified_node():
    titles = {node.title for node in BUILT_IN_NODES if node.category != CANVAS}
    assert titles >= {
        "LLM Agent", "Coding Agent", "Multi-Agent", "Supervisor Agent", "Evaluator Agent",
        "Human Approval", "Custom Agent",
        "Model Selector", "Model Router", "Embedding Model", "Reranker", "Model Fallback",
        "IF / ELSE", "Switch", "Loop", "Parallel", "Merge", "Retry", "Delay", "Sub-workflow",
        "Stop", "Error Handler",
        "Input", "Output", "JSON Parser", "Data Transform", "Variable", "Memory", "Database",
        "File Reader", "File Writer",
        "HTTP Request", "MCP Tool", "Python Executor", "Terminal", "Browser", "File System",
        "Custom Tool",
        "Logger", "Cost Tracker", "Evaluator", "Guardrail", "Performance Monitor",
    }  # fmt: skip


def test_registry_rejects_duplicates_and_accepts_new_types():
    registry = NodeRegistry()
    node = NodeType(type="plugin.x", title="X", category="Plugin", description="", icon="box")
    registry.register(node)
    assert registry.get("plugin.x") is node
    with pytest.raises(ValueError, match="already registered"):
        registry.register(node)
    assert len(create_node_registry().list()) == len(BUILT_IN_NODES)


def test_port_compatibility():
    assert ports_compatible("any", "tool")
    assert ports_compatible("text", "text")
    assert ports_compatible("text", "messages")
    assert not ports_compatible("tool", "text")


def test_field_spec_rejects_incomplete_definitions():
    with pytest.raises(ValidationError):
        spec("a", FieldKind.SELECT)
    with pytest.raises(ValidationError):
        spec("a", FieldKind.SLIDER)
    with pytest.raises(ValidationError):
        spec("a", FieldKind.ARRAY)


def test_bounds_options_and_unknown_fields():
    fields = [
        spec("n", FieldKind.NUMBER, minimum=0, maximum=1),
        spec("s", FieldKind.SELECT, options=["a", "b"]),
        spec("m", FieldKind.MULTI_SELECT, options=["a", "b"]),
    ]
    assert errors(fields, {"n": 0.5, "s": "a", "m": ["a", "b"]}) == []
    assert errors(fields, {"n": 2}) == ["n"]
    assert errors(fields, {"s": "c"}) == ["s"]
    assert errors(fields, {"m": ["c"]}) == ["m.0"]
    assert errors(fields, {"nope": 1}) == ["nope"]


def test_required_applies_only_to_visible_fields():
    fields = [
        spec("mode", FieldKind.SELECT, options=["a", "b"]),
        spec(
            "extra",
            FieldKind.TEXT,
            required=True,
            visible_when=Condition(field="mode", equals=["b"]),
        ),
    ]
    assert errors(fields, {"mode": "a"}) == []
    assert errors(fields, {"mode": "b"}) == ["extra"]


def test_nested_objects_and_arrays():
    item = spec("i", FieldKind.OBJECT, fields=[spec("name", FieldKind.TEXT)])
    fields = [
        spec("o", FieldKind.OBJECT, fields=[spec("x", FieldKind.TEXT, required=True)]),
        spec("list", FieldKind.ARRAY, item=item),
    ]
    assert errors(fields, {"o": {"x": "ok"}, "list": [{"name": "a"}]}) == []
    assert errors(fields, {"o": {}}) == ["o.x"]
    assert errors(fields, {"list": [{"bad": 1}]}) == ["list.0.bad"]


def test_secret_fields_accept_references_and_refuse_raw_values():
    fields = [spec("key", FieldKind.SECRET)]
    assert errors(fields, {"key": {"secret": "openai.default"}}) == []
    assert errors(fields, {"key": "sk-live-abc"}) == ["key"]
    assert errors(fields, {"key": {"secret": "has spaces and sk-live"}}) == ["key.secret"]
