from fastapi import APIRouter, HTTPException

from app.engine.dag import validate_dag
from app.plugins.registry import registry
from app.schemas.run import RunDetail, RunStatus, TriggerRunRequest, TriggerRunResponse
from app.schemas.workflow import WorkflowDefinition
from app.store.redis_store import get_store
from app.tasks import start_workflow_run

router = APIRouter()


@router.get("/health")
def health() -> dict:
    store = get_store()
    redis_ok = store.ping()
    return {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}


@router.get("/nodes")
def list_nodes() -> dict:
    return {"nodes": registry.list_types()}


@router.post("/workflows", response_model=WorkflowDefinition)
def register_workflow(workflow: WorkflowDefinition) -> WorkflowDefinition:
    try:
        validate_dag(workflow.nodes, workflow.edges)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    unknown = registry.validate_node_types([node.type for node in workflow.nodes])
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown node types: {', '.join(unknown)}",
        )

    store = get_store()
    store.save_workflow(workflow)
    return workflow


@router.get("/workflows/{workflow_id}", response_model=WorkflowDefinition)
def get_workflow(workflow_id: str) -> WorkflowDefinition:
    store = get_store()
    workflow = store.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.post("/workflows/{workflow_id}/runs", response_model=TriggerRunResponse)
def trigger_run(workflow_id: str, body: TriggerRunRequest) -> TriggerRunResponse:
    store = get_store()
    workflow = store.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    run = store.create_run(workflow_id, body.input)
    store.init_node_states(run.id, [node.id for node in workflow.nodes])
    start_workflow_run.delay(run.id)

    return TriggerRunResponse(run_id=run.id, status=RunStatus.QUEUED)


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str) -> RunDetail:
    store = get_store()
    detail = store.get_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return detail
