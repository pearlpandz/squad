from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pydantic import SecretStr


class Settings(BaseSettings):
    app_name: str = "multi-agent-team"
    default_router_model: str = "gpt-6-luna"
    project_run_max_seconds: int = Field(default=900, ge=120, le=1800)
    chat_cleanup_mode: bool = False
    admin_username: str = "collab-admin"
    admin_password_hash: SecretStr = SecretStr("")
    admin_cookie_secure: bool = False
    sqlite_database_path: str = ".runtime/multi-agent-team.db"
    context_window_tokens: int | None = None
    context_response_reserve_tokens: int = 8192
    context_harness_reserve_tokens: int = 24000
    context_summary_tokens: int = 4096
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3004",
        "http://localhost:3005",
        "http://localhost:3006",
        "http://localhost:3007",
        "http://localhost:3008",
        "http://localhost:3009",
        "http://localhost:3010",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
        "http://127.0.0.1:3003",
        "http://127.0.0.1:3004",
        "http://127.0.0.1:3005",
        "http://127.0.0.1:3006",
        "http://127.0.0.1:3007",
        "http://127.0.0.1:3008",
        "http://127.0.0.1:3009",
        "http://127.0.0.1:3010",
    ]

    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8")


settings = Settings()
