from typing import Any

from web_search.agent import run_web_search_agent


def _find_value(data: dict[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if key in data:
            return data[key]
    for value in data.values():
        if isinstance(value, dict):
            found = _find_value(value, *keys)
            if found is not None:
                return found
    return None


def _resolve_query(config: dict[str, Any], inputs: dict[str, Any]) -> str:
    query = config.get("query") or _find_value(
        inputs, "query", "question", "prompt", "input"
    )
    if query is None:
        raise ValueError(
            "web_search requires config.query or an upstream query/question input"
        )
    return str(query)


def handle_web_search(config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    query = _resolve_query(config, inputs)
    max_iterations = int(config.get("max_iterations", 5))
    model = str(config.get("model", "gpt-4o-mini"))

    result = run_web_search_agent(
        query,
        serp_api_key=config.get("serp_api_key"),
        openai_base_url=config.get("openai_base_url"),
        openai_api_key=config.get("openai_api_key"),
        model=model,
        max_iterations=max_iterations,
    )

    return {**inputs, **result}
