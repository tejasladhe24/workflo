from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NodeRunState(BaseModel):
    status: NodeStatus = NodeStatus.PENDING
    output: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunRecord(BaseModel):
    id: str
    workflow_id: str
    status: RunStatus = RunStatus.QUEUED
    input: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class RunDetail(BaseModel):
    id: str
    workflow_id: str
    status: RunStatus
    input: dict[str, Any]
    created_at: datetime
    nodes: dict[str, NodeRunState]


class TriggerRunRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


class TriggerRunResponse(BaseModel):
    run_id: str
    status: RunStatus
