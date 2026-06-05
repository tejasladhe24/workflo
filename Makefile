.PHONY: default sync dev worker api redis docker down

default: sync

sync:
	uv sync

redis:
	docker compose up -d redis

worker:
	uv run celery -A app.celery_app worker --loglevel=info

api:
	uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev: redis
	@$(MAKE) -j2 worker api

docker:
	docker compose up --build

down:
	docker compose down
