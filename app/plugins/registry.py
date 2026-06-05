from __future__ import annotations

import logging
from typing import Any, Callable

from app.engine.handlers import delay, noop, transform

logger = logging.getLogger(__name__)

HandlerFn = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]

BUILTIN_HANDLERS: dict[str, HandlerFn] = {
    "noop": noop.handle,
    "delay": delay.handle,
    "transform": transform.handle,
}


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, HandlerFn] = dict(BUILTIN_HANDLERS)
        self._synced = False

    def sync(self) -> None:
        from app.plugins.loader import sync_plugins

        plugin_handlers = sync_plugins()
        self._handlers = dict(BUILTIN_HANDLERS)
        self._handlers.update(plugin_handlers)
        self._synced = True
        logger.info("Handler registry ready with types: %s", sorted(self._handlers.keys()))

    def ensure_synced(self) -> None:
        if not self._synced:
            self.sync()

    def get(self, node_type: str) -> HandlerFn | None:
        self.ensure_synced()
        return self._handlers.get(node_type)

    def list_types(self) -> list[str]:
        self.ensure_synced()
        return sorted(self._handlers.keys())

    def validate_node_types(self, node_types: list[str]) -> list[str]:
        self.ensure_synced()
        known = set(self._handlers.keys())
        return [node_type for node_type in node_types if node_type not in known]


registry = HandlerRegistry()
