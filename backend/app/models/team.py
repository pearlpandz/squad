from pydantic import BaseModel, Field, field_validator


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter a team name with at least two characters")
        return value


class TeamProjectAssignment(BaseModel):
    project_id: int = Field(gt=0)
    include_existing_members: bool = False


class TeamMemberAssignment(BaseModel):
    agent_ids: list[int] = Field(default_factory=list)
    human_ids: list[int] = Field(default_factory=list)
