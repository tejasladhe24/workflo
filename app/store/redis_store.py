import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import redis

from app.config import settings
from app.schemas.run import NodeRunState, NodeStatus, RunDetail, RunRecord, RunStatus
from app.schemas.workflow import WorkflowDefinition


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RedisStore:
    def __init__(self, url: str | None = None) -> None:
        self._client = redis.Redis.from_url(url or settings.redis_url, decode_responses=True)

    def ping(self) -> bool:
        return bool(self._client.ping())

    def save_workflow(self, workflow: WorkflowDefinition) -> None:
        key = f"workflow:{workflow.id}"
        payload = workflow.model_dump(mode="json", by_alias=True)
        self._client.set(key, json.dumps(payload))

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        raw = self._client.get(f"workflow:{workflow_id}")
        if raw is None:
            return None
        return WorkflowDefinition.model_validate(json.loads(raw))

    def create_run(self, workflow_id: str, run_input: dict[str, Any]) -> RunRecord:
        run_id = str(uuid4())
        record = RunRecord(
            id=run_id,
            workflow_id=workflow_id,
            status=RunStatus.QUEUED,
            input=run_input,
            created_at=_utcnow(),
        )
        self._client.set(f"run:{run_id}", record.model_dump_json())
        return record

    def get_run(self, run_id: str) -> RunRecord | None:
        raw = self._client.get(f"run:{run_id}")
        if raw is None:
            return None
        return RunRecord.model_validate_json(raw)

    def update_run_status(self, run_id: str, status: RunStatus) -> None:
        record = self.get_run(run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")
        record.status = status
        self._client.set(f"run:{run_id}", record.model_dump_json())

    def init_node_states(self, run_id: str, node_ids: list[str]) -> None:
        key = f"run:{run_id}:nodes"
        pipe = self._client.pipeline()
        for node_id in node_ids:
            state = NodeRunState(status=NodeStatus.PENDING)
            pipe.hset(key, node_id, state.model_dump_json())
        pipe.execute()

    def get_node_state(self, run_id: str, node_id: str) -> NodeRunState | None:
        raw = self._client.hget(f"run:{run_id}:nodes", node_id)
        if raw is None:
            return None
        return NodeRunState.model_validate_json(raw)

    def get_all_node_states(self, run_id: str) -> dict[str, NodeRunState]:
        raw = self._client.hgetall(f"run:{run_id}:nodes")
        return {node_id: NodeRunState.model_validate_json(value) for node_id, value in raw.items()}

    def try_claim_node(self, run_id: str, node_id: str) -> bool:
        """Atomically claim a node for execution. Returns False if already running/succeeded."""
        key = f"run:{run_id}:nodes"
        current = self.get_node_state(run_id, node_id)
        if current is None:
            return False
        if current.status in (NodeStatus.RUNNING, NodeStatus.SUCCEEDED, NodeStatus.FAILED):
            return False
        state = NodeRunState(
            status=NodeStatus.RUNNING,
            started_at=_utcnow(),
        )
        self._client.hset(key, node_id, state.model_dump_json())
        return True

    def complete_node(
        self,
        run_id: str,
        node_id: str,
        *,
        status: NodeStatus,
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        current = self.get_node_state(run_id, node_id)
        if current is None:
            raise KeyError(f"Node state not found: {node_id}")
        current.status = status
        current.output = output
        current.error = error
        current.finished_at = _utcnow()
        self._client.hset(f"run:{run_id}:nodes", node_id, current.model_dump_json())

    def get_run_detail(self, run_id: str) -> RunDetail | None:
        record = self.get_run(run_id)
        if record is None:
            return None
        nodes = self.get_all_node_states(run_id)
        return RunDetail(
            id=record.id,
            workflow_id=record.workflow_id,
            status=record.status,
            input=record.input,
            created_at=record.created_at,
            nodes=nodes,
        )


_store: RedisStore | None = None


def get_store() -> RedisStore:
    global _store
    if _store is None:
        _store = RedisStore()
    return _store
