from fastapi import APIRouter

from app.agents.registry import list_agent_profiles
from app.models.task import TaskRequest, TaskRoutingDecision
from app.services.model_router import route_task

router = APIRouter(prefix="/team", tags=["team"])


@router.get("/agents")
def agents() -> list[dict[str, str]]:
    return list_agent_profiles()


@router.post("/route", response_model=TaskRoutingDecision)
def route(request: TaskRequest) -> TaskRoutingDecision:
    return route_task(request)

