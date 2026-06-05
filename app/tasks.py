from app.celery_app import celery_app
from app.engine.dag import get_entry_nodes, get_parent_map, get_ready_nodes
from app.engine.executor import execute_node as run_node_handler
from app.schemas.run import NodeStatus, RunStatus
from app.schemas.workflow import Node
from app.store.redis_store import get_store


def _gather_parent_outputs(run_id: str, node_id: str, edges) -> dict:
    parents = get_parent_map(edges).get(node_id, [])
    store = get_store()
    outputs = {}
    for parent_id in parents:
        parent_state = store.get_node_state(run_id, parent_id)
        if parent_state and parent_state.output is not None:
            outputs[parent_id] = parent_state.output
    return outputs


def _finalize_run_if_done(run_id: str, node_ids: list[str]) -> None:
    store = get_store()
    states = store.get_all_node_states(run_id)
    if len(states) != len(node_ids):
        return

    if any(state.status == NodeStatus.FAILED for state in states.values()):
        store.update_run_status(run_id, RunStatus.FAILED)
        return

    if all(state.status == NodeStatus.SUCCEEDED for state in states.values()):
        store.update_run_status(run_id, RunStatus.SUCCEEDED)


def _schedule_ready_nodes(run_id: str, workflow, completed: set[str]) -> None:
    node_ids = [node.id for node in workflow.nodes]
    ready = get_ready_nodes(node_ids, workflow.edges, completed)
    for node_id in ready:
        execute_node.delay(run_id, node_id)


@celery_app.task(name="start_workflow_run")
def start_workflow_run(run_id: str) -> None:
    store = get_store()
    run = store.get_run(run_id)
    if run is None:
        raise KeyError(f"Run not found: {run_id}")

    workflow = store.get_workflow(run.workflow_id)
    if workflow is None:
        raise KeyError(f"Workflow not found: {run.workflow_id}")

    store.update_run_status(run_id, RunStatus.RUNNING)

    entry_nodes = get_entry_nodes(workflow.nodes, workflow.edges)
    for node_id in entry_nodes:
        execute_node.delay(run_id, node_id)


@celery_app.task(name="execute_node")
def execute_node(run_id: str, node_id: str) -> None:
    store = get_store()
    run = store.get_run(run_id)
    if run is None:
        raise KeyError(f"Run not found: {run_id}")

    if run.status == RunStatus.FAILED:
        return

    workflow = store.get_workflow(run.workflow_id)
    if workflow is None:
        raise KeyError(f"Workflow not found: {run.workflow_id}")

    node_map = {node.id: node for node in workflow.nodes}
    node = node_map.get(node_id)
    if node is None:
        raise KeyError(f"Node not found: {node_id}")

    existing = store.get_node_state(run_id, node_id)
    if existing and existing.status in (NodeStatus.RUNNING, NodeStatus.SUCCEEDED, NodeStatus.FAILED):
        return

    if not store.try_claim_node(run_id, node_id):
        return

    try:
        parent_outputs = _gather_parent_outputs(run_id, node_id, workflow.edges)
        if not parent_outputs and run.input:
            parent_outputs = {"__run_input__": run.input}

        output = run_node_handler(node, parent_outputs)
        store.complete_node(run_id, node_id, status=NodeStatus.SUCCEEDED, output=output)
    except Exception as exc:
        store.complete_node(run_id, node_id, status=NodeStatus.FAILED, error=str(exc))
        store.update_run_status(run_id, RunStatus.FAILED)
        return

    node_ids = [n.id for n in workflow.nodes]
    states = store.get_all_node_states(run_id)
    completed = {nid for nid, state in states.items() if state.status == NodeStatus.SUCCEEDED}
    _schedule_ready_nodes(run_id, workflow, completed)
    _finalize_run_if_done(run_id, node_ids)
