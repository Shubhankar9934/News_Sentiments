# DIL Resilience Migration Notes

## Overview

The DIL production resilience layer adds concurrency control, 429-aware retry,
provider health tracking, circuit breakers, config-driven routing, degraded quorum
modes, and the `/api/v1/dil/health` observability endpoint.

## Backward Compatibility

- **No database migration required.** New fields (`degraded`, `quorum_meta`) are
  additive on existing deliberation JSON payloads.
- Set `DIL_RESILIENCE_ENABLED=false` to restore pre-resilience behavior exactly.
- Existing env vars (`DIL_DESK_FALLBACKS`, `DIL_ASSESSMENT_MIN_MEMBERS`,
  `DIL_COUNCIL_MIN_MEMBERS`) continue to work unchanged.
- `ASSESSMENT_MIN_VALID_MEMBERS` and `COUNCIL_MIN_VALID_MEMBERS` are optional
  aliases for the existing quorum settings.

## Rollout Stages

1. Deploy with defaults (`DIL_RESILIENCE_ENABLED=true`, `DIL_MAX_CONCURRENT_LLM_REQUESTS=5`).
2. Monitor `/api/v1/dil/health` for provider states and concurrency waits.
3. Optionally enable `DIL_DESK_ROUTING` to reduce GPT concentration (see `.env.example`).
4. Tune cooldown/breaker thresholds in staging if providers are skipped aggressively.

## Multi-Worker Limitation

Health, circuit breaker, and metrics state is **process-local** (in-memory).
In multi-worker deployments each process maintains independent state. A future
Redis-backed `HealthStore` interface is stubbed for v2.

## Assessment / Council Behavior Change

When valid members meet quorum but are fewer than the full panel, runs now
continue with `degraded=true` instead of silently appearing fully healthy.
Below quorum still returns `None` and uses existing dashboard fallbacks.
