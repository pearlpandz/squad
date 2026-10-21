from typing import Any

from pydantic import BaseModel, Field


class ChatThread(BaseModel):
    id: int
    project_id: int
    title: str
    status: str
    created_at: str
    updated_at: str


class ChatMessage(BaseModel):
    id: int
    thread_id: int
    sender_type: str
    sender_human_id: int | None = None
    sender_agent_id: int | None = None
    sender_name: str
    sender_role: str | None = None
    sender_handle: str | None = None
    content: str
    metadata: dict[str, Any]
    created_at: str


class CoworkerActivity(BaseModel):
    agent_id: int
    name: str
    run_id: int
    status: str


class ProjectChat(BaseModel):
    thread: ChatThread
    messages: list[ChatMessage]
    active_coworkers: list[CoworkerActivity] = Field(default_factory=list)
    cleanup_mode: bool = False


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=50000)
    sender_human_id: int | None = None
    sender_agent_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessageActor(BaseModel):
    sender_human_id: int = Field(gt=0)


class ChatMessageEdit(ChatMessageActor):
    content: str = Field(min_length=1, max_length=8000)
