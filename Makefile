.PHONY: backend-install backend-dev backend-test frontend-install frontend-dev docker-up docker-down migrate test

backend-install:
	cd backend && python -m pip install -e ".[dev]"

backend-dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-test:
	cd backend && pytest tests -q

migrate:
	cd backend && alembic upgrade head

bootstrap-schema:
	cd backend && python scripts/bootstrap_schema.py

frontend-install:
	cd frontend && pnpm install

frontend-dev:
	cd frontend && pnpm dev

frontend-test:
	cd frontend && pnpm test

docker-up:
	docker compose up --build

docker-down:
	docker compose down

test: backend-test frontend-test
