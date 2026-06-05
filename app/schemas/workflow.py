from typing import Any

from pydantic import BaseModel, Field


class Node(BaseModel):
    id: str
    type: str
    config: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    from_: str = Field(alias="from")
    to: str

    model_config = {"populate_by_name": True}


class WorkflowDefinition(BaseModel):
    id: str
    nodes: list[Node]
    edges: list[Edge]
