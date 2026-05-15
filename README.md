# Financial News Research Platform (monorepo)

Enterprise refactor of the original `news_pipeline_v3.py` + `FinancialNewsAgent_v3.jsx` into:

- `backend/` — modular FastAPI (Pydantic v2, async SQLAlchemy, repositories, services, Alembic, Redis cache hooks, Celery worker, OpenTelemetry hooks, Prometheus `/metrics`, SlowAPI rate limits, WebSocket progress)
- `frontend/` — React 19 + TypeScript + Vite + Tailwind + TanStack Query + Zustand + Axios + Zod + RHF + Framer Motion + Sonner toasts + Vitest + Playwright

## Prerequisites

- Python 3.11+
- Node 22+ and `pnpm` 9+
- Docker Desktop (optional, for compose stack)

## 1) Backend (local)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
# Start Postgres + Redis + Qdrant (Docker) OR point DATABASE_URL to your instance
docker compose up -d postgres redis qdrant
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Metrics: `http://localhost:8000/metrics`

## 2) Frontend (local)

```powershell
cd frontend
pnpm install
copy .env.example .env
pnpm dev
```

`vite.config.ts` proxies `/api` → `http://localhost:8000` so the browser can call `/api/v1/...` without CORS pain during dev.

## 3) pnpm workspace (root)

```powershell
pnpm -C frontend dev
pnpm -C frontend test
pnpm -C frontend build
```

## 4) Docker (full stack)

```powershell
docker compose up --build
```

Services: `postgres`, `redis`, `qdrant`, `backend` (hot reload), `celery-worker`, `frontend` (nginx static on `http://localhost:8080`).

Set API keys by exporting env vars or editing compose `environment` for `FINNHUB_API_KEY`, `NEWSAPI_KEY`, `POLYGON_API_KEY`, `ANTHROPIC_API_KEY`.

## 5) Migrations

```powershell
cd backend
alembic upgrade head
```

Dev bootstrap (SQLAlchemy `create_all`, non-Alembic): `python scripts/bootstrap_schema.py`

## 6) Tests

Backend:

```powershell
cd backend
pytest -q
```

Frontend:

```powershell
cd frontend
pnpm test
pnpm test:e2e   # requires dev server + playwright install
```

## 7) Postman

Import:

- `postman/Financial_News_Research.postman_collection.json`
- `postman/Local.postman_environment.json`

WebSocket guide: `postman/WEBSOCKET.md`

## 8) Production deployment (outline)

- Build images: `docker compose build`
- Run migrations as a Job/init container: `alembic upgrade head`
- Put TLS termination at ingress (nginx/Traefik/ALB)
- Store secrets in a vault (not compose files)
- Scale `backend` (stateless) and `celery-worker` independently; use managed Postgres/Redis/Qdrant where possible
- Tune SlowAPI limits and add auth (JWT helpers exist in `app/core/security.py`)

## Legacy files

`news_pipeline_v3.py` remains as a reference; new development should target `backend/app`.
