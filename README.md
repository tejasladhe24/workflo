# DAG Workflow Engine

Minimal n8n-style DAG workflow executor using FastAPI, Celery, and Redis.

## Architecture

- **FastAPI** exposes workflow registration and run APIs
- **Redis** stores workflow definitions and run state
- **Celery workers** execute DAG nodes in parallel as dependencies complete

## Quick start

```bash
cd workflow-engine
docker compose up --build
```

## API usage

The API is exposed on **port 8000** (host) to avoid clashing with other services on 8000.

Register the sample fork-join workflow:

```bash
curl -X POST http://localhost:8000/workflows \
  -H 'Content-Type: application/json' \
  -d @sample_workflow.json
```

Trigger a run:

```bash
curl -X POST http://localhost:8000/workflows/demo-flow/runs \
  -H 'Content-Type: application/json' \
  -d '{"input": {"seed": 1}}'
```

Poll run status (replace `{run_id}` with the returned id):

```bash
curl http://localhost:8000/runs/{run_id}
```

Health check:

```bash
curl http://localhost:8000/health
```

## Node types (built-in)

| Type        | Config                      | Behavior                          |
| ----------- | --------------------------- | --------------------------------- |
| `noop`      | `{}`                        | Passes parent outputs through     |
| `delay`     | `{"seconds": 1}`            | Sleeps then passes inputs through |
| `transform` | `{"set": {"key": "value"}}` | Merges `set` onto parent outputs  |

## Plugin registry (MinIO S3)

Community nodes are published as Python wheels in a MinIO bucket (`plugins`):

- `s3://plugins/index.json` — catalog of available plugins
- `s3://plugins/<plugin-name>/<version>/<wheel>.whl` — plugin artifact

On startup, **API** and **Celery workers** fetch `index.json`, download wheels, install them under `PLUGINS_DIR` (default `/app/plugins`), and register handlers via the `starboard.nodes` entry-point group.

List loaded node types:

```bash
curl http://localhost:8000/nodes
```

Example plugin workflow (`constant` → `uppercase` → `concat`):

```bash
curl -X POST http://localhost:8000/workflows \
  -H 'Content-Type: application/json' \
  -d @sample_plugin_workflow.json
```

Publish/re-publish the example plugin to MinIO:

```bash
make publish-plugins
```

MinIO console: http://localhost:9001 (minioadmin / minioadmin)

### Example plugin nodes (`example-nodes`)

| Type        | Config                                      | Behavior                    |
| ----------- | ------------------------------------------- | --------------------------- |
| `constant`  | `{"key": "msg", "value": "hello"}`          | Adds a constant to output   |
| `uppercase` | `{}`                                        | Uppercases string values    |
| `concat`    | `{"separator": " ", "fields": ["msg"]}`     | Joins field values          |

## Local development (without Docker)

```bash
make          # uv sync
make dev      # start redis + celery worker + uvicorn (parallel)
```

Other targets: `make worker`, `make api`, `make redis`, `make minio`, `make publish-plugins`, `make docker`, `make down`.

Set env vars from `.env.example` if not using defaults.

To add a dependency: `uv add <package>`. Lockfile updates are committed via `uv.lock`.
