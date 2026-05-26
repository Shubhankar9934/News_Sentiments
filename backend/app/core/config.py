"""Application configuration (Pydantic Settings v2)."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Financial News Research API"
    app_env: str = "development"
    debug: bool = False
    log_to_file: bool = Field(default=True, alias="LOG_TO_FILE")
    log_dir: str = Field(default="logs", alias="LOG_DIR")
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
    dil_use_role_specialization: bool = Field(
        default=True, alias="DIL_USE_ROLE_SPECIALIZATION"
    )
    # Comma-separated desk keys to run (empty = all registered desks).
    dil_active_desks: str = Field(default="", alias="DIL_ACTIVE_DESKS")
    # Per-desk fallback overrides: "macro_desk=claude,gemini,deepseek,groq;options_desk=..."
    dil_desk_fallbacks_raw: str = Field(default="", alias="DIL_DESK_FALLBACKS")
    dil_desk_debate_enabled: bool = Field(default=False, alias="DIL_DESK_DEBATE_ENABLED")
    dil_council_enabled: bool = Field(default=True, alias="DIL_COUNCIL_ENABLED")
    dil_council_min_members: int = Field(default=3, alias="DIL_COUNCIL_MIN_MEMBERS")
    dil_council_triggers: str = Field(default="reverse_bwb", alias="DIL_COUNCIL_TRIGGERS")
    dil_council_fallbacks_raw: str = Field(default="", alias="DIL_COUNCIL_FALLBACKS")
    # Reverse BWB Assessment Team (3 LLMs x 4 rounds) — owns every card
    # field except the Decision Council's Enter/Wait/Avoid verdict.
    dil_assessment_enabled: bool = Field(default=True, alias="DIL_ASSESSMENT_ENABLED")
    dil_assessment_min_members: int = Field(default=2, alias="DIL_ASSESSMENT_MIN_MEMBERS")
    dil_assessment_fallbacks_raw: str = Field(
        default="", alias="DIL_ASSESSMENT_FALLBACKS"
    )

    # DIL production resilience (concurrency, 429 retry, health, circuit breakers)
    dil_resilience_enabled: bool = Field(default=True, alias="DIL_RESILIENCE_ENABLED")
    dil_max_concurrent_llm_requests: int = Field(
        default=5, alias="DIL_MAX_CONCURRENT_LLM_REQUESTS"
    )
    dil_429_max_retries: int = Field(default=1, alias="DIL_429_MAX_RETRIES")
    dil_429_max_wait_s: int = Field(default=60, alias="DIL_429_MAX_WAIT_S")
    dil_provider_cooldown_s: int = Field(default=300, alias="DIL_PROVIDER_COOLDOWN_S")
    dil_health_degraded_429_threshold: int = Field(
        default=3, alias="DIL_HEALTH_DEGRADED_429_THRESHOLD"
    )
    dil_health_unhealthy_failure_threshold: int = Field(
        default=5, alias="DIL_HEALTH_UNHEALTHY_FAILURE_THRESHOLD"
    )
    dil_cb_open_duration_s: int = Field(default=300, alias="DIL_CB_OPEN_DURATION_S")
    dil_cb_probe_interval_s: int = Field(default=30, alias="DIL_CB_PROBE_INTERVAL_S")
    # Full provider chains: role=primary,fallback1,fallback2;...
    dil_desk_routing_raw: str = Field(default="", alias="DIL_DESK_ROUTING")
    dil_assessment_routing_raw: str = Field(default="", alias="DIL_ASSESSMENT_ROUTING")
    dil_council_routing_raw: str = Field(default="", alias="DIL_COUNCIL_ROUTING")
    # Aliases for quorum thresholds (same underlying fields)
    assessment_min_valid_members: int | None = Field(
        default=None, alias="ASSESSMENT_MIN_VALID_MEMBERS"
    )
    council_min_valid_members: int | None = Field(
        default=None, alias="COUNCIL_MIN_VALID_MEMBERS"
    )

    options_enabled: bool = Field(default=True, alias="OPTIONS_ENABLED")
    options_default_horizon_days: int = Field(default=3, alias="OPTIONS_DEFAULT_HORIZON_DAYS")
    options_credit_safety_weights: dict[str, float] = Field(default_factory=dict)
    options_use_live_iv: bool = Field(default=False, alias="OPTIONS_USE_LIVE_IV")
    options_chain_provider: str = Field(default="polygon", alias="OPTIONS_CHAIN_PROVIDER")
    polygon_options_api_key: str = Field(default="", alias="POLYGON_OPTIONS_API_KEY")
    tradier_api_key: str = Field(default="", alias="TRADIER_API_KEY")
    tradier_base_url: str = Field(
        default="https://api.tradier.com/v1", alias="TRADIER_BASE_URL"
    )

    relevance_filter_enabled: bool = Field(default=True, alias="RELEVANCE_FILTER_ENABLED")
    relevance_include_macro_in_narrative: bool = Field(
        default=True, alias="INCLUDE_MACRO_IN_NARRATIVE"
    )

    analog_semantic_enabled: bool = Field(default=True, alias="ANALOG_SEMANTIC_ENABLED")
    analog_pattern_enabled: bool = Field(default=True, alias="ANALOG_PATTERN_ENABLED")

    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_collection: str = Field(default="article_embeddings", alias="QDRANT_COLLECTION")

    embed_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBED_MODEL")
    finbert_model: str = Field(default="ProsusAI/finbert", alias="FINBERT_MODEL")
    hf_token: str = Field(default="", alias="HF_TOKEN")

    dedupe_threshold: float = 0.92
    max_articles_claude: int = 15

    # Run All sequentially fires up to 12 /research calls per dashboard load.
    # The watchlist grid lifts the floor on this limit; individual users
    # generally take seconds-to-minutes between runs so the per-IP budget is
    # still safe.
    rate_limit_research: str = Field(default="30/minute", alias="RATE_LIMIT_RESEARCH")
    rate_limit_default: str = Field(default="120/minute", alias="RATE_LIMIT_DEFAULT")
    # /summaries is a slim per-user dashboard projection that competes with up
    # to 12 deliberation polls in the same minute, so it gets a roomier budget.
    rate_limit_summaries: str = Field(default="600/minute", alias="RATE_LIMIT_SUMMARIES")

    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_service_name: str = Field(default="finresearch-api", alias="OTEL_SERVICE_NAME")

    # Reverse BWB Intelligence Dashboard — sequential watchlist batch runner.
    # Auto-run is OFF by default so local dev restarts don't burn LLM budget;
    # flip on in production deploys where the cards must be warm on first load.
    watchlist_auto_run_on_startup: bool = Field(
        default=False, alias="WATCHLIST_AUTO_RUN_ON_STARTUP"
    )
    watchlist_run_days: int = Field(default=7, alias="WATCHLIST_RUN_DAYS")
    reverse_bwb_summary_enabled: bool = Field(
        default=True, alias="REVERSE_BWB_SUMMARY_ENABLED"
    )
    reverse_bwb_summary_model: str = Field(
        default="claude-sonnet-4-6", alias="REVERSE_BWB_SUMMARY_MODEL"
    )
    reverse_bwb_summary_max_tokens: int = Field(
        default=1500, alias="REVERSE_BWB_SUMMARY_MAX_TOKENS"
    )

    # Explainability layer (Phase 0..10 from the explainability plan).
    # Gates the assembly of ``report_json.explainability`` so the whole
    # reasoning layer can be disabled with one switch without affecting
    # the frozen card schema.
    explainability_enabled: bool = Field(default=True, alias="EXPLAINABILITY_ENABLED")

    # ----------------------------------------------------------------------
    # IBKR Live Market Data (Phase 1-7 of the IBKR integration plan).
    #
    # Two strictly separate data domains:
    #   - ANALYSIS SNAPSHOT (existing, frozen) — only updates on Re-Run
    #     Analysis; lives in ticker_reverse_bwb_summary / ticker_reports.
    #   - LIVE MARKET DATA (new, continuous) — streamed from a single IBKR
    #     Gateway client; lives in ticker_market_data and
    #     ticker_live_option_opportunities.
    # ``IBKR_ENABLED=false`` keeps the live worker dormant so the dashboard
    # still serves the frozen snapshot exactly as before.
    # ----------------------------------------------------------------------
    ibkr_enabled: bool = Field(default=False, alias="IBKR_ENABLED")
    ibkr_host: str = Field(default="127.0.0.1", alias="IBKR_HOST")
    ibkr_port: int = Field(default=4001, alias="IBKR_PORT")
    ibkr_client_id: int = Field(default=17, alias="IBKR_CLIENT_ID")
    ibkr_paper: bool = Field(default=True, alias="IBKR_PAPER")
    ibkr_connect_timeout_s: float = Field(default=10.0, alias="IBKR_CONNECT_TIMEOUT_S")

    # Quote stream batches DB writes every PRICE_FLUSH_MS to avoid one UPSERT
    # per tick — IBKR can push 5-20 ticks/sec on liquid names.
    market_data_price_flush_ms: int = Field(
        default=1000, alias="MARKET_DATA_PRICE_FLUSH_MS"
    )
    market_data_opp_interval_s: int = Field(
        default=45, alias="MARKET_DATA_OPP_INTERVAL_S"
    )
    market_data_stale_threshold_s: int = Field(
        default=10, alias="MARKET_DATA_STALE_THRESHOLD_S"
    )

    # Reverse BWB candidate filters
    opp_target_dte_min: int = Field(default=7, alias="OPP_TARGET_DTE_MIN")
    opp_target_dte_max: int = Field(default=21, alias="OPP_TARGET_DTE_MAX")
    # Legacy top-N cap, kept for backward compatibility. The new
    # full-enumeration generator stores ALL valid candidates; this knob
    # now only controls how many rows per side get refined via WhatIf.
    opp_rank_top_n_per_side: int = Field(default=2, alias="OPP_RANK_TOP_N_PER_SIDE")

    # ----------------------------------------------------------------------
    # Reverse BWB Trading Workstation (full opportunity enumeration).
    # The generator enumerates every (long_wing_a, short_body, long_wing_b)
    # triplet within these bounds, computes deterministic margin for all,
    # and only burns IBKR WhatIf quota on the top ``OPP_WHATIF_TOP_N`` per
    # side per ticker.
    # ----------------------------------------------------------------------
    opp_dte_min: int = Field(default=0, alias="OPP_DTE_MIN")
    opp_dte_max: int = Field(default=5, alias="OPP_DTE_MAX")
    opp_wing_min_strikes: int = Field(default=1, alias="OPP_WING_MIN_STRIKES")
    opp_wing_max_strikes: int = Field(default=20, alias="OPP_WING_MAX_STRIKES")
    opp_min_leg_oi: int = Field(default=10, alias="OPP_MIN_LEG_OI")
    opp_max_distinct_legs: int = Field(default=300, alias="OPP_MAX_DISTINCT_LEGS")
    # Only consider strikes within ±N% of the current underlying price.
    # Reduces candidate explosion from deep-OTM strikes that have no real premium.
    opp_max_strike_dist_pct: float = Field(default=10.0, alias="OPP_MAX_STRIKE_DIST_PCT")
    # Discard combos whose credit is smaller than this (dollars per lot).
    # 0 = keep all credits; negative values allow debits through.
    opp_min_credit_usd: float = Field(default=20.0, alias="OPP_MIN_CREDIT_USD")
    opp_whatif_top_n: int = Field(default=25, alias="OPP_WHATIF_TOP_N")
    opp_whatif_max_per_min: int = Field(default=12, alias="OPP_WHATIF_MAX_PER_MIN")
    # Event-driven recalc thresholds. Recalc fires when ANY of these is true.
    opp_recalc_price_pct: float = Field(default=0.25, alias="OPP_RECALC_PRICE_PCT")
    opp_recalc_iv_pct: float = Field(default=3.0, alias="OPP_RECALC_IV_PCT")
    opp_recalc_max_age_s: int = Field(default=900, alias="OPP_RECALC_MAX_AGE_S")
    # WebSocket tick fan-out batching window (ms). Higher = less noise,
    # lower = more responsive ticker tape.
    ws_tick_batch_ms: int = Field(default=250, alias="WS_TICK_BATCH_MS")

    # Quote cache: how often to flush in-memory quotes to PostgreSQL.
    # Decouples the DB write from the WebSocket publish path.
    market_data_db_flush_s: int = Field(default=5, alias="MARKET_DATA_DB_FLUSH_S")
    # TTL for quote:{TICKER} keys in Redis.
    quote_cache_ttl_s: int = Field(default=30, alias="QUOTE_CACHE_TTL_S")

    # Redis Pub/Sub fanout — enables multi-process WebSocket delivery.
    # Off by default; set REDIS_PUBSUB_ENABLED=true for horizontal scaling.
    redis_pubsub_enabled: bool = Field(default=False, alias="REDIS_PUBSUB_ENABLED")

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

    @property
    def dil_active_desk_set(self) -> set[str]:
        if not self.dil_active_desks.strip():
            return set()
        return {d.strip().lower() for d in self.dil_active_desks.split(",") if d.strip()}

    @property
    def dil_desk_fallbacks(self) -> dict[str, str]:
        """Parse ``DIL_DESK_FALLBACKS`` as ``desk_key=prov1,prov2;...``."""
        out: dict[str, str] = {}
        raw = self.dil_desk_fallbacks_raw.strip()
        if not raw:
            return out
        for segment in raw.split(";"):
            segment = segment.strip()
            if not segment or "=" not in segment:
                continue
            desk, providers = segment.split("=", 1)
            out[desk.strip().lower()] = providers.strip()
        return out

    @property
    def dil_council_trigger_set(self) -> set[str]:
        if not self.dil_council_triggers.strip():
            return {"reverse_bwb"}
        return {t.strip().lower() for t in self.dil_council_triggers.split(",") if t.strip()}

    @property
    def dil_council_fallbacks(self) -> dict[str, str]:
        """Parse ``DIL_COUNCIL_FALLBACKS`` as ``role_key=prov1,prov2;...``."""
        out: dict[str, str] = {}
        raw = self.dil_council_fallbacks_raw.strip()
        if not raw:
            return out
        for segment in raw.split(";"):
            segment = segment.strip()
            if not segment or "=" not in segment:
                continue
            role, providers = segment.split("=", 1)
            out[role.strip().lower()] = providers.strip()
        return out

    @property
    def dil_assessment_fallbacks(self) -> dict[str, str]:
        """Parse ``DIL_ASSESSMENT_FALLBACKS`` as ``role_key=prov1,prov2;...``."""
        out: dict[str, str] = {}
        raw = self.dil_assessment_fallbacks_raw.strip()
        if not raw:
            return out
        for segment in raw.split(";"):
            segment = segment.strip()
            if not segment or "=" not in segment:
                continue
            role, providers = segment.split("=", 1)
            out[role.strip().lower()] = providers.strip()
        return out

    @property
    def effective_assessment_min_members(self) -> int:
        if self.assessment_min_valid_members is not None:
            return self.assessment_min_valid_members
        return self.dil_assessment_min_members

    @property
    def effective_council_min_members(self) -> int:
        if self.council_min_valid_members is not None:
            return self.council_min_valid_members
        return self.dil_council_min_members


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
