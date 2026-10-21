from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    prompt: str = Field(min_length=1)
    requested_by: str | None = None


class TaskRoutingDecision(BaseModel):
    intent: str
    complexity: str
    selected_model: str
    reasoning: str
    confidence: float
    reason: str

