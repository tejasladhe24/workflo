from typing import Any

from app.plugins.registry import registry
from app.schemas.workflow import Node


def execute_node(node: Node, parent_outputs: dict[str, Any]) -> dict[str, Any]:
    handler = registry.get(node.type)
    if handler is None:
        raise ValueError(f"Unknown node type: {node.type}")
    return handler(node.config, parent_outputs)
