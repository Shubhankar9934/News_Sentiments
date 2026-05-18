"""Application configuration (Pydantic Settings v2)."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Financial News Research API"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = Field(
        default="http://localhost:5173",
        validation_alias="CORS_ORIGINS",
    )

    jwt_secret_key: str = Field(default="dev-secret-change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    database_url: str = Field(
        default="postgresql+asyncpg://finresearch:finresearch_dev_local@localhost:5433/finresearch",
        alias="DATABASE_URL",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2",
        alias="CELERY_RESULT_BACKEND",
    )

    finnhub_api_key: str = Field(default="", alias="FINNHUB_API_KEY")
    newsapi_key: str = Field(default="", alias="NEWSAPI_KEY")
    polygon_api_key: str = Field(default="", alias="POLYGON_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_MODEL")
    anthropic_base_url: str = Field(default="https://api.anthropic.com", alias="ANTHROPIC_BASE_URL")

    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_collection: str = Field(default="article_embeddings", alias="QDRANT_COLLECTION")

    embed_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBED_MODEL")
    finbert_model: str = Field(default="ProsusAI/finbert", alias="FINBERT_MODEL")
    hf_token: str = Field(default="", alias="HF_TOKEN")

    dedupe_threshold: float = 0.92
    max_articles_claude: int = 15

    rate_limit_research: str = Field(default="10/minute", alias="RATE_LIMIT_RESEARCH")
    rate_limit_default: str = Field(default="120/minute", alias="RATE_LIMIT_DEFAULT")

    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_service_name: str = Field(default="finresearch-api", alias="OTEL_SERVICE_NAME")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def join_cors(cls, v: str | list[str]) -> str:
        if isinstance(v, list):
            return ",".join(v)
        return str(v)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
