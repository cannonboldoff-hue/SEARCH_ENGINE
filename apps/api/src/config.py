from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://localhost/search_engine"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Chat (OpenAI-compatible open-source)
    chat_api_base_url: str | None = None
    chat_api_key: str | None = None
    chat_model: str = "Qwen/Qwen2.5-7B-Instruct"

    # Embeddings (OpenAI-compatible)
    embed_api_base_url: str | None = None
    embed_api_key: str | None = None
    embed_model: str = "bge-base-en-v1.5"

    openai_api_key: str | None = None

    # Rate limiting
    search_rate_limit: str = "10/minute"
    unlock_rate_limit: str = "20/minute"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
