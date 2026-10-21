from app.db.session import initialize_database
from app.repositories.agent_repository import list_agent_profiles as list_agent_profiles_from_db


def list_agent_profiles() -> list[dict[str, str]]:
    initialize_database()
    return list_agent_profiles_from_db()
