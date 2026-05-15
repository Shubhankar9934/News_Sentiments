# Financial News Research — Backend

Modular FastAPI service: collectors, FinBERT, Qdrant, Claude synthesis, PostgreSQL persistence.

## Quick start

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: `http://localhost:8000/docs` (Swagger) and `http://localhost:8000/redoc` (ReDoc).

Legacy monolith reference: `../news_pipeline_v3.py` (logic ported into `app/services`).
