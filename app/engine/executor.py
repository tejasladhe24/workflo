from collections.abc import Callable
from typing import Any

from app.engine.handlers import delay, noop, transform
from app.schemas.workflow import Node

HandlerFn = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]

HANDLERS: dict[str, HandlerFn] = {
    "noop": noop.handle,
    "delay": delay.handle,
    "transform": transform.handle,
}


def execute_node(node: Node, parent_outputs: dict[str, Any]) -> dict[str, Any]:
    handler = HANDLERS.get(node.type)
    if handler is None:
        raise ValueError(f"Unknown node type: {node.type}")
    return handler(node.config, parent_outputs)
