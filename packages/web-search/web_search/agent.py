from __future__ import annotations

import os
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from serpapi import GoogleSearch


def _format_serp_results(data: dict[str, Any]) -> str:
    parts: list[str] = []

    answer_box = data.get("answer_box")
    if isinstance(answer_box, dict):
        snippet = answer_box.get("snippet") or answer_box.get("answer")
        if snippet:
            parts.append(f"Featured answer: {snippet}")

    for item in data.get("organic_results", [])[:5]:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")
        parts.append(f"{title}\n{snippet}\n{link}")

    return "\n\n".join(parts) if parts else "No results found."


def _run_serp_search(query: str, api_key: str) -> str:
    response = GoogleSearch(
        {
            "engine": "google",
            "q": query,
            "api_key": api_key,
        }
    ).get_dict()
    return _format_serp_results(response)


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    iteration: int


def build_web_search_agent(
    *,
    serp_api_key: str,
    openai_base_url: str,
    openai_api_key: str,
    model: str,
    max_iterations: int,
):
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")

    @tool
    def web_search(search_query: str) -> str:
        """Search the web via Google for current information on a topic."""
        return _run_serp_search(search_query, serp_api_key)

    llm = ChatOpenAI(
        model=model,
        base_url=openai_base_url,
        api_key=openai_api_key,
        temperature=0,
    )
    llm_with_tools = llm.bind_tools([web_search])

    def agent_node(state: AgentState) -> dict[str, Any]:
        if state["iteration"] >= max_iterations:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "Search iteration limit reached. "
                            "Summarizing from the information gathered so far."
                        )
                    )
                ],
            }

        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response], "iteration": state["iteration"] + 1}

    def search_node(state: AgentState) -> dict[str, Any]:
        if state["iteration"] >= max_iterations:
            return {"messages": []}

        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {"messages": []}

        tool_messages: list[ToolMessage] = []
        for tool_call in last.tool_calls:
            if tool_call["name"] != "web_search":
                continue
            args = tool_call.get("args") or {}
            search_query = args.get("search_query", "")
            result = web_search.invoke({"search_query": search_query})
            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_call["id"])
            )
        return {"messages": tool_messages}

    def route_after_agent(state: AgentState) -> Literal["search", "end"]:
        if state["iteration"] >= max_iterations:
            return "end"

        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "search"
        return "end"

    def route_after_search(state: AgentState) -> Literal["agent", "end"]:
        if state["iteration"] >= max_iterations:
            return "end"
        return "agent"

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("search", search_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent", route_after_agent, {"search": "search", "end": END}
    )
    graph.add_conditional_edges(
        "search", route_after_search, {"agent": "agent", "end": END}
    )
    return graph.compile()


def run_web_search_agent(
    query: str,
    *,
    serp_api_key: str | None = None,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    model: str = "gpt-4o-mini",
    max_iterations: int = 5,
) -> dict[str, Any]:
    resolved_serp_key = serp_api_key or os.environ.get("SERPAPI_API_KEY")
    resolved_openai_base_url = openai_base_url or os.environ.get("OPENAI_BASE_URL")
    resolved_openai_key = openai_api_key or os.environ.get("OPENAI_API_KEY")

    if not resolved_serp_key:
        raise ValueError(
            "SerpAPI key required: set config.serp_api_key or SERPAPI_API_KEY"
        )
    if not resolved_openai_key:
        raise ValueError(
            "OpenAI key required: set config.openai_api_key or OPENAI_API_KEY"
        )

    agent = build_web_search_agent(
        serp_api_key=resolved_serp_key,
        openai_base_url=resolved_openai_base_url,
        openai_api_key=resolved_openai_key,
        model=model,
        max_iterations=max_iterations,
    )

    system = SystemMessage(
        content=(
            "You are a research assistant. Use the web_search tool to gather information. "
            "Run additional searches when results are incomplete or conflicting. "
            "When you have enough evidence, reply with a clear final answer and do not call tools."
        )
    )
    result = agent.invoke(
        {
            "messages": [system, HumanMessage(content=query)],
            "iteration": 0,
        }
    )

    answer = _extract_final_answer(result["messages"])
    return {
        "query": query,
        "answer": answer,
        "iterations": result["iteration"],
    }


def _extract_final_answer(messages: list[AnyMessage]) -> str:
    for message in reversed(messages):
        if (
            isinstance(message, AIMessage)
            and message.content
            and not message.tool_calls
        ):
            content = message.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                return "".join(text_parts)
    return ""
