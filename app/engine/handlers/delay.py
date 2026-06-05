import time
from typing import Any


def handle(config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    seconds = float(config.get("seconds", 0))
    if seconds > 0:
        time.sleep(seconds)
    return inputs
