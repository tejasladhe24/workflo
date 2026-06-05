.PHONY: default sync dev worker api redis minio docker down publish-plugins plugin-workflow

default: sync

sync:
	uv sync

redis:
	docker compose up -d redis

worker:
	uv run celery -A app.celery_app worker --loglevel=info

api:
	uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

minio:
	docker compose up -d minio

dev: redis minio publish-plugins
	@$(MAKE) -j2 worker api

docker:
	docker compose up --build

down:
	docker compose down

publish-plugins:
	docker compose run --rm registry-init

plugin-workflow:
	curl -s -X POST http://localhost:8000/workflows -H 'Content-Type: application/json' -d @sample_plugin_workflow.json
