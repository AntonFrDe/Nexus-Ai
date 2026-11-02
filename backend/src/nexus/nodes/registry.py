from nexus.nodes.spec import NodeType

ANY = "any"

# Port type -> types it may feed, beyond itself and "any".
PORT_COMPATIBILITY: dict[str, list[str]] = {
    "text": ["messages"],
    "messages": ["text"],
    "json": ["text"],
}


def ports_compatible(source: str, target: str) -> bool:
    if ANY in (source, target) or source == target:
        return True
    return target in PORT_COMPATIBILITY.get(source, [])


class NodeRegistry:
    """Every node type, built-in or from a plugin, is known only through this registry."""

    def __init__(self) -> None:
        self._types: dict[str, NodeType] = {}

    def register(self, node_type: NodeType) -> None:
        if node_type.type in self._types:
            raise ValueError(f"Node type already registered: {node_type.type}")
        self._types[node_type.type] = node_type

    def get(self, type_name: str) -> NodeType | None:
        return self._types.get(type_name)

    def list(self) -> list[NodeType]:
        return list(self._types.values())
