from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_keys: str = "demo-key"
    database_url: str = "postgresql://triage:triage@localhost:5433/triage"
    redis_url: str = "redis://localhost:6380/0"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout_seconds: float = 45
    rate_limit_per_minute: int = 30
    max_request_chars: int = 5000

    @property
    def accepted_api_keys(self) -> set[str]:
        """Parse configured keys without logging their values."""
        return {value.strip() for value in self.api_keys.split(",") if value.strip()}


@lru_cache
def get_settings() -> Settings:
    """Return one immutable settings instance per process."""
    return Settings()
