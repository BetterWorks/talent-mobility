# Internal Mobility Matching Service

A production-ready FastAPI service scaffold for internal mobility matching. This repository provides the complete engineering setup — dependency management, containerization, linting, testing, and CI — ready for developers to begin implementing business functionality.

## Current Scope

This repository contains the service scaffold only. Business APIs are **not implemented**.

The service exposes two operational endpoints:
- `GET /api/health/` — liveness check
- `GET /api/ready/` — readiness check

No employee matching, profile, job, skill, recommendation, or mobility endpoints exist yet.

## Prerequisites

- Python 3.12
- [Poetry](https://python-poetry.org/) 1.8.0
- Docker and Docker Compose (Docker Desktop or equivalent)
- GNU Make

## Repository Structure

```
internal-mobility-matching/
├── .github/
│   └── workflows/
│       └── ci.yml                  # GitHub Actions CI
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app, lifespan, middleware, endpoints
│   ├── settings.py                 # Environment-based configuration
│   └── utils/
│       ├── __init__.py
│       ├── exceptions.py           # Base exception classes
│       └── logs.py                 # Structlog setup
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   └── test_health.py              # Health and readiness endpoint tests
├── .dockerignore
├── .env                            # Local dev environment (git-ignored)
├── .gitignore
├── .pre-commit-config.yaml
├── .python-version
├── Dockerfile
├── Makefile
├── README.md
├── compose.yaml
├── entrypoint.sh
├── pyproject.toml
├── pytest.ini
├── sample.env
└── setup.cfg
```

## Local Installation

```bash
cd internal-mobility-matching
make dev-setup
```

This installs all dependencies via Poetry and sets up pre-commit hooks.

## Environment Setup

Copy `sample.env` to `.env` and adjust as needed:

```bash
cp sample.env .env
```

Default local values work out of the box:

```env
APP_NAME=internal-mobility-matching
APP_ENV=local
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
```

The `.env` file is git-ignored. Never commit real secrets.

## How to Run Locally

```bash
make dev-server
```

The service starts with hot reload at `http://localhost:8000`.

Interactive API docs are available at `http://localhost:8000/docs`.

## How to Run with Docker

```bash
make docker-build
docker run --env-file .env -p 8000:8000 internal-mobility-matching:local api
```

## How to Run with Docker Compose

```bash
docker compose up --build
```

Stop services:

```bash
docker compose down
```

The service is available at `http://localhost:8000`.

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

Run tests:

```bash
make test
```

Run with coverage:

```bash
make test-cov
```

Tests use `pytest` with `pytest-asyncio`. The test client is `httpx.AsyncClient` with `ASGITransport` — no live server is required.

Tests do not call external services.

## Linting and Formatting

Run the linter (flake8 + isort check):

```bash
make run-linter
```

Auto-format code:

```bash
make pretty
```

Fix import order:

```bash
make fix-imports
```

Configuration is in `setup.cfg`:
- Max line length: 120
- Max complexity: 15

## Pre-commit Setup

Install hooks:

```bash
make pre-commit-install
```

Run manually on all files:

```bash
make pre-commit-run
```

Pre-commit runs linting, formatting, and import sorting before each commit.

## Health and Readiness Endpoints

| Endpoint | Method | Response | Use |
|---|---|---|---|
| `/api/health/` | GET | `"ok"` (200) | Liveness — container orchestration |
| `/api/ready/` | GET | `"ok"` (200) | Readiness — load balancer routing |

Both endpoints are excluded from any authentication middleware.

```bash
curl http://localhost:8000/api/health/
curl http://localhost:8000/api/ready/
```

## Configuration Reference

All configuration is loaded from environment variables. Defaults are set in `app/settings.py`.

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `internal-mobility-matching` | Service name |
| `APP_ENV` | `local` | Environment (local, staging, production) |
| `APP_HOST` | `0.0.0.0` | Bind host |
| `APP_PORT` | `8000` | Bind port |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |

## Development Guidelines

### Logging

Use the shared `LoggingAgent` from `app/utils/logs.py`:

```python
from app.utils.logs import agent

logger = agent.get_context_bound_logger()
logger.info("something happened", key="value")
```

Logs are structured JSON in non-TTY environments (Docker, CI) and pretty-printed in TTY (local terminal).

### Exceptions

Inherit from `BaseServiceException` in `app/utils/exceptions.py`:

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

## How to Add Future API Routes

1. Create a router module, e.g. `app/routers/my_feature.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])

@router.get("/")
async def my_endpoint():
    ...
```

2. Register it in `app/main.py`:

```python
from app.routers import my_feature
app.include_router(my_feature.router)
```

3. Add corresponding tests in `tests/`.

## Security Notes

- The `.env` file is git-ignored. Never commit real credentials.
- Do not add secrets to `sample.env` — it is committed to version control.
- The `Dockerfile` does not copy `.env` into the image.
- No authentication middleware is configured in this scaffold. Add it before exposing any protected endpoints.

## Troubleshooting

**`poetry install` fails — Python version mismatch**
Ensure Python 3.12 is active: `python --version`. Use pyenv if needed: `pyenv install 3.12 && pyenv local 3.12`.

**`make run-linter` fails on import order**
Run `make fix-imports` to auto-fix, then re-run the linter.

**Docker build fails — `poetry.lock` not found**
Run `poetry lock` locally to generate it, then rebuild.

**Port 8000 already in use**
Change the host port mapping in `compose.yaml` (e.g., `"8001:8000"`) or stop the conflicting process.

**Tests fail with `asyncio` errors**
Ensure `pytest-asyncio` is installed and `asyncio_mode=auto` is set in `pytest.ini` (it is by default).
