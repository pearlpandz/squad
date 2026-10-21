from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents import router as agents_router
from app.api.admin import router as admin_router
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.team import router as team_router
from app.api.teams import router as teams_router
from app.core.config import settings
from app.core.admin import require_session
from app.db.session import initialize_database
from app.services.agent_templates import bootstrap_business_analyst_template
from app.services.agent_jobs import fail_interrupted_jobs
from app.services.runtime_storage import relocate_runtime_files

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(agents_router, prefix="/api", dependencies=[Depends(require_session)])
app.include_router(projects_router, prefix="/api", dependencies=[Depends(require_session)])
app.include_router(chat_router, prefix="/api", dependencies=[Depends(require_session)])
app.include_router(team_router, prefix="/api", dependencies=[Depends(require_session)])
app.include_router(teams_router, prefix="/api", dependencies=[Depends(require_session)])


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    relocate_runtime_files()
    bootstrap_business_analyst_template()
    fail_interrupted_jobs()
