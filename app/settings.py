from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration object for all service credentials, model parameters, and runtime settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Tavily
    tavily_api_key: str = Field(alias="TAVILY_API_KEY")

    # OpenRouter
    openrouter_api_key: str = Field(alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    openrouter_model: str = Field(
        default="google/gemma-4-31b-it",
        alias="OPENROUTER_MODEL",
    )
    openrouter_fallback_model: str = Field(
        default="google/gemma-4-31b-it:free",
        alias="OPENROUTER_FALLBACK_MODEL",
    )
    max_tokens: int = Field(default=4096, alias="MAX_TOKENS")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # LangSmith
    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="", alias="LANGSMITH_PROJECT")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        alias="LANGSMITH_ENDPOINT",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
