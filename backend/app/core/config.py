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

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")

    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL"
    )

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL"
    )

    dil_enabled: bool = Field(default=True, alias="DIL_ENABLED")
    # False = run deliberation in the API process (local uvicorn without celery-worker).
    dil_use_celery: bool = Field(default=False, alias="DIL_USE_CELERY")
    dil_exclude_models: str = Field(default="", alias="DIL_EXCLUDE_MODELS")
    dil_min_models: int = Field(default=2, alias="DIL_MIN_MODELS")
    dil_max_debate_rounds: int = Field(default=2, alias="DIL_MAX_DEBATE_ROUNDS")
    # DIL feature flags (PR2–PR10). Default ON in dev; flip OFF for safe rollouts.
    dil_use_challenge_routing: bool = Field(default=True, alias="DIL_USE_CHALLENGE_ROUTING")
    dil_use_novelty_gate: bool = Field(default=True, alias="DIL_USE_NOVELTY_GATE")
    dil_novelty_threshold: float = Field(default=0.7, alias="DIL_NOVELTY_THRESHOLD")
    dil_novelty_reprompt: bool = Field(default=False, alias="DIL_NOVELTY_REPROMPT")
    dil_use_risk_clustering: bool = Field(default=True, alias="DIL_USE_RISK_CLUSTERING")
    dil_use_llm_topic_tagging: bool = Field(default=False, alias="DIL_USE_LLM_TOPIC_TAGGING")
    dil_use_evidence_verification: bool = Field(default=False, alias="DIL_USE_EVIDENCE_VERIFICATION")
    dil_context_token_budget: int = Field(default=6000, alias="DIL_CONTEXT_TOKEN_BUDGET")
    dil_client_timeout_s: int = Field(default=60, alias="DIL_CLIENT_TIMEOUT_S")

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

    @property
    def dil_excluded_model_set(self) -> set[str]:
        return {m.strip().lower() for m in self.dil_exclude_models.split(",") if m.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
