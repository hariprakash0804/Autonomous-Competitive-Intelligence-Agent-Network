from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/competitive_intel"

    # JWT
    SECRET_KEY: str = "change-me-to-a-random-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 30

    # LLM
    LLM_PROVIDER: Optional[str] = None
    LLM_API_KEY: Optional[str] = None

    # HuggingFace Inference API (free tier for embeddings)
    HF_API_TOKEN: Optional[str] = None

    # Vector Store: "auto" | "hash" | "hf_api"
    VECTOR_STORE_MODE: Optional[str] = "auto"

    # LangSmith (optional)
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: Optional[str] = "competitive-intel"

    # Internal API Key (for n8n / service-to-service auth without JWT)
    INTERNAL_API_KEY: Optional[str] = None

    # Webhook Notifications
    SLACK_WEBHOOK_URL: Optional[str] = None
    WEBHOOK_URL: Optional[str] = None

    # Backend public URL (for Slack/email report links)
    BACKEND_URL: Optional[str] = "http://localhost:8000"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
