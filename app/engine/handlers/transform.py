from typing import Any


def handle(config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    result = dict(inputs)
    overrides = config.get("set", {})
    if not isinstance(overrides, dict):
        raise ValueError("transform config.set must be a dict")
    result.update(overrides)
    return result
