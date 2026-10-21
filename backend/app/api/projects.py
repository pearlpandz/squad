from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, Request
from pathlib import Path

from app.models.project import (
    AiMemberCreate,
    AiMemberUpdate,
    HumanMemberCreate,
    HumanMemberUpdate,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdate,
)
from app.repositories.project_repository import (
    add_ai_member,
    add_human_member,
    create_project,
    get_project,
    list_projects,
    remove_ai_member,
    remove_human_member,
    remove_project,
    update_ai_member,
    update_human_member,
    update_project,
)
from app.services.knowledge_storage import save_agent_knowledge_files
from app.services.agent_training import MAX_SOURCE_BYTES, SUPPORTED_EXTENSIONS
from app.db.session import get_connection

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/{project_id}/members/agents/{agent_id}", response_model=ProjectDetail)
def assign_existing_ai_member(project_id: int, agent_id: int) -> ProjectDetail:
    project = get_project(project_id)
    if project is None or project.status == "removed" or project.removed_at is not None:
        raise HTTPException(status_code=404, detail="Project not found")
    with get_connection() as connection:
        agent = connection.execute(
            """SELECT a.id, r.name AS role FROM agents a
               JOIN agent_roles r ON r.id = a.role_id
               JOIN projects p ON p.id = ? AND p.client_id = a.client_id
               JOIN team_agents ta ON ta.team_id = p.team_id AND ta.agent_id = a.id
               WHERE a.id = ? AND a.status = 'available' AND a.is_template = 0""",
            (project_id, agent_id),
        ).fetchone()
        if agent is None:
            raise HTTPException(status_code=404, detail="Add this available coworker to the project team first")
        connection.execute(
            """INSERT INTO project_agents (project_id, agent_id, member_role, status)
               VALUES (?, ?, ?, 'active')
               ON CONFLICT(project_id, agent_id) DO UPDATE SET
                 member_role = excluded.member_role, status = 'active', updated_at = datetime('now')""",
            (project_id, agent_id, agent["role"]),
        )
    return get_project(project_id)


@router.get("", response_model=list[ProjectSummary])
def projects(include_removed: bool = Query(default=False)) -> list[ProjectSummary]:
    return list_projects(include_removed=include_removed)


@router.post("", response_model=ProjectDetail, status_code=201)
def create(payload: ProjectCreate, request: Request) -> ProjectDetail:
    payload.created_by_human_id = request.state.user["human_id"]
    try:
        return create_project(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{project_id}", response_model=ProjectDetail)
def detail(project_id: int) -> ProjectDetail:
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectDetail)
def update(project_id: int, payload: ProjectUpdate, request: Request) -> ProjectDetail:
    payload.updated_by_human_id = request.state.user["human_id"]
    try:
        project = update_project(project_id, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", response_model=ProjectDetail)
def remove(project_id: int, request: Request) -> ProjectDetail:
    project = remove_project(project_id, request.state.user["human_id"])
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/members/humans", response_model=ProjectDetail)
def create_human_member(project_id: int, payload: HumanMemberCreate) -> ProjectDetail:
    project = add_human_member(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}/members/humans/{human_id}", response_model=ProjectDetail)
def update_human_project_member(
    project_id: int, human_id: int, payload: HumanMemberUpdate
) -> ProjectDetail:
    project = update_human_member(project_id, human_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project member not found")
    return project


@router.delete("/{project_id}/members/humans/{human_id}", response_model=ProjectDetail)
def delete_human_member(project_id: int, human_id: int) -> ProjectDetail:
    project = remove_human_member(project_id, human_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/members/agents", response_model=ProjectDetail)
async def create_ai_member(
    project_id: int,
    name: str = Form(...),
    username: str = Form(...),
    role: str = Form(...),
    agent_description: str = Form(default=""),
    knowledge_resources: list[UploadFile] | None = File(default=None),
) -> ProjectDetail:
    if get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    normalized_username = username.strip().lstrip("@").lower()
    with get_connection() as connection:
        existing_agent = connection.execute(
            "SELECT id FROM agents WHERE username = ?", (normalized_username,)
        ).fetchone()
    if existing_agent is not None:
        raise HTTPException(status_code=409, detail="Coworker already exists; assign it from the project member picker")
    for file in knowledge_resources or []:
        if Path(file.filename or "").suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file: {file.filename}")
        if file.size is not None and file.size > MAX_SOURCE_BYTES:
            raise HTTPException(status_code=400, detail=f"File exceeds 50 MB: {file.filename}")
    try:
        uploaded_paths = await save_agent_knowledge_files(username, knowledge_resources or [], project_id=project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = AiMemberCreate(
        name=name,
        username=username,
        role=role,
        agent_description=agent_description,
        knowledge_resources=uploaded_paths,
    )
    try:
        project = add_ai_member(project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if uploaded_paths:
        agent = next((member for member in project.ai_members if member.username == username.strip().lstrip("@").lower()), None)
        if agent is not None:
            with get_connection() as connection:
                connection.executemany(
                    """INSERT INTO agent_sources (agent_id, title, source_type, relative_path, approval_status)
                    VALUES (?, ?, 'file', ?, 'approved')
                    ON CONFLICT(agent_id, relative_path) DO UPDATE SET title = excluded.title,
                        approval_status = 'approved', updated_at = datetime('now')""",
                    [(agent.id, Path(file.filename or "knowledge-source").name, path)
                     for file, path in zip(knowledge_resources or [], uploaded_paths)],
                )
    return project


@router.put("/{project_id}/members/agents/{agent_id}", response_model=ProjectDetail)
def update_ai_project_member(
    project_id: int, agent_id: int, payload: AiMemberUpdate
) -> ProjectDetail:
    project = update_ai_member(project_id, agent_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project member not found")
    return project


@router.delete("/{project_id}/members/agents/{agent_id}", response_model=ProjectDetail)
def delete_ai_member(project_id: int, agent_id: int) -> ProjectDetail:
    project = remove_ai_member(project_id, agent_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
