# Talent Mobility Matching Service

A FastAPI service for internal mobility and candidate matching. Requests for open
roles are stored in Postgres (`better_sense` schema, shared warehouse DB with
`llm-engine`), AI matching runs are executed asynchronously via a Celery worker,
and the UI polls for run status/results.

## Prerequisites

- Python 3.12
- [Poetry](https://python-poetry.org/) 1.8.0
- Docker and Docker Compose (Docker Desktop or equivalent)
- GNU Make
- Access to the shared warehouse Postgres instance and the llm-proxy service

## Repository Structure

```
talent-mobility/
├── .github/workflows/ci.yml
├── alembic.ini
├── better_sense_schema.sql             # canonical DDL reference for the better_sense schema
├── migrations/
│   ├── env.py                          # Alembic env — targets better_sense schema
│   ├── script.py.mako
│   └── versions/                       # empty until the next schema change is migrated
├── app/
│   ├── main.py                         # FastAPI app, lifespan, middleware, router wiring
│   ├── settings.py                     # Environment-based configuration
│   ├── celery_app.py                   # Celery app (Redis broker, DB result backend)
│   ├── worker_healthcheck.py           # Liveness/readiness app served alongside the worker
│   ├── db/                             # SQLModel models + DAOs (one file per table)
│   │   ├── __init__.py                 # engine, session, schema-scoped metadata
│   │   ├── internal_mobility_request.py
│   │   ├── users_hris_details.py
│   │   ├── data_embeddings.py
│   │   ├── run_ai_matches.py
│   │   └── candidate_profile.py
│   ├── models/
│   │   └── candidate_profile_data.py   # Pydantic shape for candidate_profile.profile_data
│   ├── routers/
│   │   ├── internal_mobility_requests.py   # CRUD for role requests
│   │   ├── ai_matches.py                   # kick off + poll AI matching runs
│   │   ├── candidate_profiles.py           # shortlist, deep dive, status updates
│   │   └── sample_writing_assistant.py     # standalone llm-proxy connectivity check
│   ├── services/
│   │   └── matching.py                 # business logic invoked by the Celery task
│   ├── worker/
│   │   └── tasks.py                    # Celery task definitions
│   └── utils/
│       ├── common.py                   # get_utc_now, run_async_session_task
│       ├── llm_proxy.py                 # exec_llm_proxy (AsyncOpenAI -> llm-proxy)
│       ├── exceptions.py
│       └── logs.py
├── tests/
├── compose.yaml
├── Dockerfile
├── entrypoint.sh
├── Makefile
├── pyproject.toml
├── sample.env
└── setup.cfg
```

## Environment Setup

Copy `sample.env` to `.env` and fill in real credentials (DB host/port, llm-proxy
token) — `.env` is git-ignored, `sample.env` is committed and must never contain
real secrets.

```bash
cp sample.env .env
```

Key variables (see `app/settings.py` for all defaults):

| Variable | Purpose |
|---|---|
| `APP_PORT` | API bind port (also used for the worker healthcheck app) |
| `DATABASE_URL` / `SYNC_DATABASE_URL` | Warehouse Postgres connection (async/sync) |
| `DATABASE_SCHEMA` | Schema for this service's tables (`better_sense`) |
| `CELERY_DATABASE_BACKEND_URL` | Celery result backend (same warehouse DB) |
| `REDIS_BROKER_URL` | Celery broker |
| `LLM_PROXY_URL` / `LLM_PROXY_TOKEN` | llm-proxy connection |
| `OPENAI_API_KEY` | Passed through to the OpenAI SDK client (proxy-routed) |
| `PRIVATE_LLM_MODEL` | Default model string sent to llm-proxy |

## Local Installation

```bash
make dev-setup
```

## Database Migrations

`better_sense_schema.sql` at the repo root is the canonical DDL reference for
the `better_sense` schema — apply it directly (`psql -f better_sense_schema.sql`)
against a fresh warehouse DB to get all current tables/indexes/columns in one
shot. It is hand-maintained: when you change the schema, update it alongside
any migration.

Alembic (`migrations/`) is still wired up for versioned, incremental changes
going forward — `migrations/versions/` starts empty. The schema is created
automatically by `migrations/env.py` if missing.

Run migrations manually (not part of `docker compose up` — see below):

```bash
docker compose run --rm migration
```

If the tables already exist in the target DB (e.g. created manually) and you
just need Alembic to record that state without re-running DDL:

```bash
docker compose run --rm migration alembic stamp <revision>
```

## How to Run Locally (without Docker)

```bash
make dev-server
```

Starts the API with hot reload at `http://localhost:4004` (`/docs` for
interactive API docs). This only runs the API — DB/Redis/worker must be
reachable separately (see Docker Compose below for the full stack).

## How to Run with Docker Compose

```bash
docker compose up --build
```

This starts `api`, `worker`, and `redis`. The `migration` service is **not**
included in `up` — it only runs when invoked explicitly:

```bash
docker compose run --rm migration
```

For local development, `api` mounts the repo as a bind volume (`./:/code`) and
runs Uvicorn with reload enabled (`UVICORN_RELOAD=true` in `compose.yaml`), so
changes under `app/` automatically restart the API process.

`worker` also mounts `./:/code` and enables `WORKER_RELOAD=true`; it uses
`watchfiles` to restart both Celery and the worker healthcheck app when Python
files under `app/` change.

Stop services:

```bash
docker compose down
```

The API is available at `http://localhost:4004` (or whatever `APP_PORT` is set
to in `.env`).

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health/` | GET | Liveness check |
| `/api/ready/` | GET | Readiness check |
| `/api/internal-mobility-requests/` | POST | Create a role request |
| `/api/internal-mobility-requests/` | GET | List role requests (filter by business_unit/hiring_manager/seniority_level/status) |
| `/api/internal-mobility-requests/{id}` | GET | Fetch a role request |
| `/api/internal-mobility-requests/{id}/status` | PATCH | Update request status (open/in_progress/review/approved/closed) |
| `/api/internal-mobility-requests/{id}/summary` | GET | Dashboard row: request + latest run + candidate count |
| `/api/ai-matches/` | POST | Start an AI matching run for a request |
| `/api/ai-matches/{run_id}` | GET | Poll run status (pending/running/completed/failed) |
| `/api/ai-matches/{run_id}/candidates` | GET | List matched candidate profiles for a run |
| `/api/candidate-profiles/by-run/{run_id}` | GET | List candidates for a run (filter by cost_impact, sort by match_score/cost_impact) |
| `/api/candidate-profiles/{id}` | GET | Candidate deep-dive (full `profile_data`) |
| `/api/candidate-profiles/{id}/status` | PATCH | Update candidate status (pending/matched/approved/hold/rejected) |
| `/api/sample/writing-assistant/` | POST | Standalone llm-proxy connectivity smoke test |

### Example: create a role request

```bash
curl -s -X POST http://localhost:4004/api/internal-mobility-requests/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "AI Platform Engineer",
    "business_unit": "Engineering — Platform",
    "hiring_manager": "Ramesh B.",
    "seniority_level": "Senior / Staff",
    "number_of_candidates_to_hire": 2,
    "hiring_estimate_in_days": 120,
    "min_salary": 60000,
    "max_salary": 80000,
    "external_hiring_cost": 92000,
    "required_skills": ["Python", "ML Platform", "LLMOps"],
    "job_description": "About the role..."
  }'
```

### Example: start and poll an AI matching run

```bash
curl -s -X POST "http://localhost:4004/api/ai-matches/?request_id=<request-uuid>"
curl -s http://localhost:4004/api/ai-matches/<run-id>
curl -s http://localhost:4004/api/ai-matches/<run-id>/candidates
```

### Example: candidate shortlist and deep dive

```bash
curl -s "http://localhost:4004/api/candidate-profiles/by-run/<run-id>?sort_by=match_score&sort_desc=true"
curl -s http://localhost:4004/api/candidate-profiles/<profile-id>
curl -s -X PATCH "http://localhost:4004/api/candidate-profiles/<profile-id>/status?status=2"
```

### Example: sample writing assistant (llm-proxy smoke test)

```bash
curl -s -X POST http://localhost:4004/api/sample/writing-assistant/ \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Say hello in one short sentence."}'
```

## Async Worker

Matching runs are processed by a Celery worker (`app/worker/tasks.py`), backed
by Redis (broker) and Postgres (result backend). The worker container also
serves a small FastAPI healthcheck app (`app/worker_healthcheck.py`) on the
same port for liveness/readiness probing.

The UI is expected to poll `GET /api/ai-matches/{run_id}` until `status` is
`completed` or `failed`, rather than relying on a push/websocket mechanism.

## Available Makefile Commands

| Command | Description |
|---|---|
| `make dev-setup` | Install dependencies and pre-commit hooks |
| `make dev-server` | Start local development server with hot reload |
| `make test` | Install dependencies and run unit tests |
| `make test-unit` | Run unit tests only |
| `make test-cov` | Run tests with coverage report |
| `make run-linter` | Run flake8 and isort check |
| `make pretty` | Format code with autopep8 and isort |
| `make fix-imports` | Fix import order with isort |
| `make check` | Run lint and tests (full local verification) |
| `make pre-commit-install` | Install pre-commit hooks |
| `make pre-commit-run` | Run pre-commit on all files |
| `make docker-build` | Build Docker image |
| `make docker-up` | Start Docker Compose services |
| `make docker-down` | Stop Docker Compose services |
| `make docker-logs` | Tail Docker Compose logs |
| `make clean` | Remove build artifacts and caches |

## Testing

```bash
make test
make test-cov
```

Tests use `pytest` with `pytest-asyncio` and `httpx.AsyncClient` — no live
server, database, or external service is required for the existing test
suite.

## Linting and Formatting

```bash
make run-linter   # flake8 + isort check
make pretty        # autopep8 + isort, in place
make fix-imports   # isort only
```

Configuration is in `setup.cfg` (max line length: 120, max complexity: 15).

## Development Guidelines

### Adding a new DB-backed table

Follow the existing pattern in `app/db/*.py`: one file per table containing a
`*Base(SQLModel)` class (shared fields), a `*(Base, table=True)` subclass
(`metadata = meta`, schema-scoped), and a plain `*DAO` class holding an
`AsyncSession` with `create`/`get`/`list`/`update` methods. Datetime columns
that map to Postgres `timestamptz` must use
`sa_column=Column(DateTime(timezone=True))` — plain `datetime` fields default
to a naive column type and will fail to bind tz-aware values from
`get_utc_now()`.

Then add a migration in `migrations/versions/` (or `alembic revision
--autogenerate` once wired against a real DB), register the model import in
`migrations/env.py`, and update `better_sense_schema.sql` to match.

### Adding a new async task

Add the task function to `app/worker/tasks.py`, the business logic to
`app/services/`, and trigger it from a router via `<task>.delay(...)`. Each
task opens its own DB session (see `app/services/matching.py`) since Celery
workers don't share the FastAPI request-scoped session.

### Logging

```python
from app.utils.logs import agent

logger = agent.get_context_bound_logger()
logger.info("something happened", key="value")
```

### Exceptions

```python
from app.utils.exceptions import BaseServiceException

class MyFeatureException(BaseServiceException):
    error_code = 2001
    message = "Something went wrong"
    status_code = 400
```

The exception handler in `app/main.py` will serialize it automatically.

### Configuration

Add new environment variables to `app/settings.py` using `os.environ.get()`, then document them in `sample.env`.

## Security Notes

- `.env` is git-ignored and must never be committed. `sample.env` is
  committed and must contain placeholders only.
- The `Dockerfile` does not copy `.env` into the image.
- No authentication middleware is configured. Add it before exposing any
  endpoint outside a trusted network.

## Troubleshooting

**`ModuleNotFoundError` inside a running container after adding a dependency**
The Docker image caches the `poetry install` layer keyed on
`pyproject.toml`/`poetry.lock`. If a rebuild doesn't pick up new deps, force
it: `docker compose build --no-cache <service>`.

**`alembic upgrade head` fails with "relation already exists"**
The target table was created outside Alembic (e.g. manual DDL) before this
project's migration ran. Reconcile with `docker compose run --rm migration
alembic stamp <revision>` instead of `upgrade`.

**`No 'script_location' key found in configuration`**
`alembic.ini`/`migrations/` aren't present in the container — check the
Dockerfile copies both into the image.

**Port already in use**
Change `APP_PORT` in `.env`, or stop the conflicting process.
