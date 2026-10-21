import sqlite3
from typing import Literal

from fastapi import APIRouter, HTTPException

from app.db.session import get_connection
from app.models.project import HumanMemberCreate
from app.models.team import TeamCreate, TeamMemberAssignment, TeamProjectAssignment
from app.repositories import team_repository as repository
from app.services.member_memory import refresh_member_memory

router = APIRouter(prefix="/teams", tags=["teams"])


def perform(action, *args):
    try:
        return action(*args)
    except ValueError as exc:
        raise HTTPException(status_code=404 if str(exc).endswith("not found") else 400, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("")
def teams():
    return repository.list_teams()


@router.post("", status_code=201)
def create(payload: TeamCreate):
    return perform(repository.create_team, payload)


@router.get("/available-humans")
def available_humans():
    with get_connection() as connection:
        return [dict(row) for row in connection.execute("""SELECT id, display_name AS name, username, role
            FROM humans WHERE status = 'active' ORDER BY display_name, id""")]


@router.get("/{team_id}")
def detail(team_id: int):
    return perform(repository.get_team, team_id)


@router.put("/{team_id}")
def update(team_id: int, payload: TeamCreate):
    def save():
        with get_connection() as connection:
            repository.require_team(connection, team_id)
            connection.execute("UPDATE teams SET name = ?, description = ?, updated_at = datetime('now') WHERE id = ?",
                               (payload.name, payload.description, team_id))
        return repository.get_team(team_id)
    return perform(save)


@router.post("/{team_id}/members")
def add_members(team_id: int, payload: TeamMemberAssignment):
    return perform(repository.add_team_members, team_id, payload.agent_ids, payload.human_ids)


@router.post("/{team_id}/members/humans", status_code=201)
def create_human(team_id: int, payload: HumanMemberCreate):
    return perform(repository.create_team_human, team_id, payload)


@router.delete("/{team_id}/members/{kind}/{member_id}")
def remove_member(team_id: int, kind: Literal['agents', 'humans'], member_id: int):
    return perform(repository.remove_team_member, team_id, member_id, kind)


@router.post("/{team_id}/projects")
def move_project(team_id: int, payload: TeamProjectAssignment):
    return perform(repository.move_project, team_id, payload.project_id, payload.include_existing_members)


@router.post("/{team_id}/projects/{project_id}/members")
def assign_project_members(team_id: int, project_id: int, payload: TeamMemberAssignment):
    def assign():
        with get_connection() as connection:
            repository.require_team(connection, team_id)
            if connection.execute("""SELECT 1 FROM projects WHERE id = ? AND team_id = ?
                AND code != '_agent-pool' AND status != 'removed' AND removed_at IS NULL""",
                                  (project_id, team_id)).fetchone() is None:
                raise ValueError('Project not found in this team')
            for agent_id in set(payload.agent_ids):
                agent = connection.execute("""SELECT r.name AS role FROM agents a
                    JOIN team_agents ta ON ta.agent_id = a.id JOIN agent_roles r ON r.id = a.role_id
                    WHERE a.id = ? AND ta.team_id = ? AND a.status = 'available' AND a.is_template = 0""",
                                           (agent_id, team_id)).fetchone()
                if agent is None:
                    raise ValueError('Choose an available coworker in this team')
                connection.execute("""INSERT INTO project_agents (project_id, agent_id, member_role)
                    VALUES (?, ?, ?) ON CONFLICT(project_id, agent_id) DO UPDATE SET status = 'active',
                    member_role = excluded.member_role, updated_at = datetime('now')""", (project_id, agent_id, agent['role']))
            for human_id in set(payload.human_ids):
                human = connection.execute("""SELECT h.role FROM humans h JOIN team_humans th ON th.human_id = h.id
                    WHERE h.id = ? AND th.team_id = ? AND h.status = 'active'""", (human_id, team_id)).fetchone()
                if human is None:
                    raise ValueError('Choose an active human in this team')
                connection.execute("""INSERT INTO project_members (project_id, human_id, member_role)
                    VALUES (?, ?, ?) ON CONFLICT(project_id, human_id) DO UPDATE SET status = 'active',
                    member_role = excluded.member_role, updated_at = datetime('now')""", (project_id, human_id, human['role']))
        return repository.get_team(team_id)
    return perform(assign)


@router.get("/{team_id}/members/agents/{agent_id}/memory")
def member_memory(team_id: int, agent_id: int):
    def load():
        with get_connection() as connection:
            repository.require_team(connection, team_id)
            if connection.execute("SELECT 1 FROM team_agents WHERE team_id = ? AND agent_id = ?", (team_id, agent_id)).fetchone() is None:
                raise ValueError('Team member not found')
        return [snapshot for snapshot in refresh_member_memory(agent_id) if snapshot['team_id'] == team_id]
    return perform(load)
