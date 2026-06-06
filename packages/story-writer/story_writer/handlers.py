from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

SYSTEM_PROMPT = (
    "You are a creative story writer. Write an engaging short story based on "
    "the topic description provided by the user."
)


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


def _resolve_topic(config: dict[str, Any], inputs: dict[str, Any]) -> str:
    topic = config.get("topic") or _find_value(
        inputs, "topic", "description", "answer", "question", "input"
    )
    if topic is None:
        raise ValueError(
            "story_writer requires config.topic or an upstream topic/description input"
        )
    return str(topic)


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)


def handle_story_writer(
    config: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    topic = _resolve_topic(config, inputs)
    model = str(config.get("model", "gpt-4o-mini"))
    openai_api_key = config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
    openai_base_url = config.get("openai_base_url") or os.environ.get("OPENAI_BASE_URL")

    if not openai_api_key:
        raise ValueError(
            "OpenAI key required: set config.openai_api_key or OPENAI_API_KEY"
        )

    llm = ChatOpenAI(
        model=model,
        api_key=openai_api_key,
        base_url=openai_base_url,
        temperature=float(config.get("temperature", 0.8)),
    )
    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Topic description: {topic}"),
        ]
    )

    return {**inputs, "topic": topic, "story": _extract_text(response.content)}
