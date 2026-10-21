import importlib.util
from pathlib import Path

from app.models.task import TaskRequest, TaskRoutingDecision

_ROUTER_PATH = Path(__file__).with_name("intelligent-model-router.py")
_ROUTER_SPEC = importlib.util.spec_from_file_location("intelligent_model_router", _ROUTER_PATH)

if _ROUTER_SPEC is None or _ROUTER_SPEC.loader is None:
    raise ImportError(f"Unable to load router from {_ROUTER_PATH}")

_ROUTER_MODULE = importlib.util.module_from_spec(_ROUTER_SPEC)
_ROUTER_SPEC.loader.exec_module(_ROUTER_MODULE)


def route_task(request: TaskRequest) -> TaskRoutingDecision:
    return _ROUTER_MODULE.route_task(request)
