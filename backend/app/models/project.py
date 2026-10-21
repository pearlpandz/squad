from typing import Any

from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    team_id: int = Field(default=1, gt=0)
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    description: str | None = None
    status: str = "active"
    business_domain: str = ""
    repository_url: str = ""
    delivery_stage: str = "discovery"
    priority: str = "medium"
    tech_stack: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_member_ids: list[int] = Field(default_factory=list)


class ProjectCreate(ProjectBase):
    code: str | None = Field(default=None, min_length=2, max_length=80)
    agent_member_ids: list[int] = Field(default_factory=list)
    created_by_human_id: int | None = None


class ProjectUpdate(BaseModel):
    team_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=2, max_length=80)
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = None
    status: str | None = None
    business_domain: str | None = None
    repository_url: str | None = None
    delivery_stage: str | None = None
    priority: str | None = None
    tech_stack: list[str] | None = None
    metadata: dict[str, Any] | None = None
    human_member_ids: list[int] | None = None
    updated_by_human_id: int | None = None


class HumanMember(BaseModel):
    id: int
    display_name: str
    username: str
    email: str | None = None
    role: str
    member_role: str
    status: str


class AiMember(BaseModel):
    id: int
    name: str
    username: str
    handle: str
    role: str
    status: str
    agent_description: str
    knowledge_scope: str


class ProjectSummary(BaseModel):
    id: int
    team_id: int
    team_name: str
    code: str
    name: str
    description: str | None
    status: str
    business_domain: str
    delivery_stage: str
    priority: str
    tech_stack: list[str]
    created_at: str
    updated_at: str
    created_by: str | None = None
    updated_by: str | None = None
    human_member_count: int
    ai_member_count: int


class ProjectDetail(ProjectSummary):
    repository_url: str
    metadata: dict[str, Any]
    removed_at: str | None = None
    human_members: list[HumanMember]
    ai_members: list[AiMember]


class HumanMemberCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    username: str = Field(min_length=2, max_length=80)
    email: str | None = None
    role: str = Field(min_length=2, max_length=120)


class HumanMemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    username: str | None = Field(default=None, min_length=2, max_length=80)
    email: str | None = None
    role: str | None = Field(default=None, min_length=2, max_length=120)


class AiMemberCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    username: str = Field(min_length=2, max_length=80)
    role: str = Field(min_length=2, max_length=120)
    agent_description: str = Field(default="", max_length=300)
    knowledge_resources: list[str] = Field(default_factory=list)


class AiMemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    username: str | None = Field(default=None, min_length=2, max_length=80)
    role: str | None = Field(default=None, min_length=2, max_length=120)
    agent_description: str | None = Field(default=None, max_length=300)
