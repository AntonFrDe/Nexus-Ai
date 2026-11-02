from collections import Counter, defaultdict

from nexus.execution.expressions import ExpressionError, check_syntax
from nexus.nodes.catalog import RUNTIME_FIELDS
from nexus.nodes.config_model import validate_config
from nexus.nodes.registry import NodeRegistry, ports_compatible
from nexus.nodes.spec import NodeType
from nexus.workflows.schemas import Issue, ValidationReport, WorkflowGraph, WorkflowNode


def _error(code: str, message: str, **where) -> Issue:
    return Issue(severity="error", code=code, message=message, **where)


def _warning(code: str, message: str, **where) -> Issue:
    return Issue(severity="warning", code=code, message=message, **where)


def _name(node: WorkflowNode, node_type: NodeType | None) -> str:
    return node.label or (node_type.title if node_type else node.id)


def _check_nodes(graph: WorkflowGraph, types: dict[str, NodeType | None]) -> list[Issue]:
    issues: list[Issue] = []
    by_id = {node.id: node for node in graph.nodes}
    for node_id, count in Counter(node.id for node in graph.nodes).items():
        if count > 1:
            issues.append(_error("duplicate_node_id", f"Duplicate node id {node_id}"))

    for node in graph.nodes:
        node_type = types[node.id]
        if node_type is None:
            issues.append(
                _error("unknown_node_type", f"Unknown node type {node.type}", node_id=node.id)
            )
            continue
        name = _name(node, node_type)
        for field, message in validate_config(node_type.type, node_type.fields, node.config):
            issues.append(
                _error("invalid_config", f"{name}: {message}", node_id=node.id, field=field)
            )
        for spec in node_type.fields:
            value = node.config.get(spec.name)
            if spec.language != "expression" or not isinstance(value, str) or not value:
                continue
            try:
                check_syntax(value)
            except ExpressionError as error:
                issues.append(
                    _error(
                        "invalid_expression",
                        f"{name}: {spec.label}: {error}",
                        node_id=node.id,
                        field=spec.name,
                    )
                )
        for field, message in validate_config("runtime", RUNTIME_FIELDS, node.runtime):
            issues.append(
                _error("invalid_runtime", f"{name}: {message}", node_id=node.id, field=field)
            )
        for permission in node.permissions:
            if permission not in node_type.permissions:
                issues.append(
                    _error(
                        "unknown_permission",
                        f"{name} cannot request {permission}",
                        node_id=node.id,
                    )
                )
        if node.parent_id is not None:
            parent = by_id.get(node.parent_id)
            if parent is None or parent.type != "core.group":
                issues.append(
                    _error("invalid_parent", f"{name} has an invalid group", node_id=node.id)
                )
    return issues


def _check_edges(graph: WorkflowGraph, types: dict[str, NodeType | None]) -> list[Issue]:
    issues: list[Issue] = []
    seen: set[tuple[str, str, str, str]] = set()
    edge_ids = Counter(edge.id for edge in graph.edges)
    for edge in graph.edges:
        where = {"edge_id": edge.id}
        if edge_ids[edge.id] > 1:
            issues.append(_error("duplicate_edge_id", f"Duplicate edge id {edge.id}", **where))
        key = (edge.source, edge.source_port, edge.target, edge.target_port)
        if key in seen:
            issues.append(_error("duplicate_edge", "These ports are already connected", **where))
        seen.add(key)

        if edge.source not in types or edge.target not in types:
            issues.append(_error("edge_unknown_node", "Edge references a missing node", **where))
            continue
        if edge.source == edge.target:
            issues.append(_error("edge_to_self", "A node cannot connect to itself", **where))
        source_type, target_type = types[edge.source], types[edge.target]
        if source_type is None or target_type is None:
            continue
        output = next((p for p in source_type.outputs if p.id == edge.source_port), None)
        input_ = next((p for p in target_type.inputs if p.id == edge.target_port), None)
        if output is None or input_ is None:
            issues.append(_error("edge_unknown_port", "Edge references a missing port", **where))
        elif not ports_compatible(output.type, input_.type):
            issues.append(
                _error(
                    "edge_port_type",
                    f"{source_type.title} outputs {output.type}, "
                    f"but {target_type.title} expects {input_.type}",
                    **where,
                )
            )
    return issues


def _check_ports(graph: WorkflowGraph, types: dict[str, NodeType | None]) -> list[Issue]:
    issues: list[Issue] = []
    incoming = Counter((edge.target, edge.target_port) for edge in graph.edges)
    for node in graph.nodes:
        node_type = types[node.id]
        if node_type is None:
            continue
        name = _name(node, node_type)
        for port in node_type.inputs:
            count = incoming[(node.id, port.id)]
            if port.required and count == 0:
                issues.append(
                    _error(
                        "missing_required_input",
                        f"{name}: {port.label} is not connected",
                        node_id=node.id,
                    )
                )
            if count > 1 and not port.multiple:
                issues.append(
                    _error(
                        "input_accepts_one",
                        f"{name}: {port.label} accepts one connection",
                        node_id=node.id,
                    )
                )
    return issues


def _unbounded_cycle(graph: WorkflowGraph, types: dict[str, NodeType | None]) -> list[str]:
    """Kahn's algorithm over nodes that do not bound cycles: leftovers lie on a free cycle."""
    bounded = {
        node_id for node_id, node_type in types.items() if node_type and node_type.bounds_cycles
    }
    successors: dict[str, set[str]] = defaultdict(set)
    degree = {node_id: 0 for node_id in types if node_id not in bounded}
    for edge in graph.edges:
        if edge.source not in degree or edge.target not in degree:
            continue
        if edge.target not in successors[edge.source]:
            successors[edge.source].add(edge.target)
            degree[edge.target] += 1
    ready = [node_id for node_id, count in degree.items() if count == 0]
    while ready:
        for successor in successors[ready.pop()]:
            degree[successor] -= 1
            if degree[successor] == 0:
                ready.append(successor)
    return [node_id for node_id, count in degree.items() if count > 0]


def _check_structure(graph: WorkflowGraph, types: dict[str, NodeType | None]) -> list[Issue]:
    executable = [n for n in graph.nodes if (t := types[n.id]) is not None and t.executable]
    if not executable:
        return []
    issues = [
        _error(
            "unbounded_cycle",
            "This node is on a cycle with no Loop node to bound it",
            node_id=node_id,
        )
        for node_id in _unbounded_cycle(graph, types)
    ]
    if not any(node.type == "core.input" for node in executable):
        issues.append(_warning("no_input", "The workflow has no Input node"))
    if not any(node.type == "core.output" for node in executable):
        issues.append(_warning("no_output", "The workflow has no Output node"))
    connected = {edge.source for edge in graph.edges} | {edge.target for edge in graph.edges}
    for node in executable:
        if node.id not in connected and len(executable) > 1:
            issues.append(
                _warning(
                    "disconnected", f"{_name(node, types[node.id])} is unconnected", node_id=node.id
                )
            )
    return issues


def validate_workflow(graph: WorkflowGraph, registry: NodeRegistry) -> ValidationReport:
    types = {node.id: registry.get(node.type) for node in graph.nodes}
    issues = [
        *_check_nodes(graph, types),
        *_check_edges(graph, types),
        *_check_ports(graph, types),
        *_check_structure(graph, types),
    ]
    return ValidationReport(
        valid=not any(issue.severity == "error" for issue in issues), issues=issues
    )
