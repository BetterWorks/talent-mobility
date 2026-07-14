SHELL := /bin/bash

POETRY := poetry
CONFIGURATION_FILE := setup.cfg
PACKAGE := app
TEST_PACKAGE := tests

default:
	@echo "Known make targets:"
	@echo "  dev-setup          - install dependencies and pre-commit hooks"
	@echo "  pretty             - lint/format source files"
	@echo "  fix-imports        - fix import order"
	@echo "  run-linter         - run flake8 and isort check"
	@echo "  dev-server         - run local development server (with hot reload)"
	@echo "  test               - run all tests"
	@echo "  test-unit          - run unit tests"
	@echo "  test-cov           - run tests with coverage report"
	@echo "  check              - run lint, format check, and tests"
	@echo "  pre-commit-install - install pre-commit hooks"
	@echo "  pre-commit-run     - run pre-commit on all files"
	@echo "  docker-build       - build Docker image"
	@echo "  docker-up          - start services with Docker Compose"
	@echo "  docker-down        - stop Docker Compose services"
	@echo "  docker-logs        - tail Docker Compose logs"
	@echo "  clean              - remove build artifacts and caches"

# have all shell commands executed in a single shell
.ONESHELL:

run-linter:
	@echo "💫 Running linter..."
	@set -e; \
	${POETRY} run flake8 ${PACKAGE}/ ${TEST_PACKAGE}/ --config=${CONFIGURATION_FILE}; \
	isort -c --diff ${PACKAGE}/ ${TEST_PACKAGE}/

dev-setup:
	@${POETRY} install --quiet
	@if [ -e .git/hooks/pre-commit ]; then \
		echo "Pre-commit hook already exists, skipping install"; \
	else \
		echo "Installing git pre-commit hook"; \
		pre-commit install; \
	fi

pretty: dev-setup
	@${POETRY} run autopep8 --aggressive --in-place ${PACKAGE}/**/*.py ${TEST_PACKAGE}/**/*.py

fix-imports:
	@${POETRY} run isort ${PACKAGE} ${TEST_PACKAGE}

dev-server: dev-setup
	@echo "💫 Starting server..."
	@$(POETRY) run uvicorn app.main:app --port 8000 --reload

test: dev-setup test-unit
	@:

test-unit:
	@echo "💫 Running unit tests (excluding benchmarks)..."
	@(${POETRY} run pytest -m "not benchmark" ${TEST_PACKAGE})

test-cov: dev-setup
	@echo "💫 Running tests with coverage..."
	@${POETRY} run pytest --cov=${PACKAGE} --cov-report=term-missing ${TEST_PACKAGE}

check: run-linter test
	@echo "✅ All checks passed"

pre-commit-install:
	@pre-commit install

pre-commit-run:
	@pre-commit run --all-files

docker-build:
	@echo "🐳 Building Docker image..."
	@docker build -t internal-mobility-matching:local .

docker-up:
	@echo "🐳 Starting Docker Compose services..."
	@docker compose up --build

docker-down:
	@echo "🐳 Stopping Docker Compose services..."
	@docker compose down

docker-logs:
	@docker compose logs -f

clean:
	@echo "🧹 Cleaning build artifacts..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .coverage coverage.xml htmlcov/ .pytest_cache/ .mypy_cache/

.PHONY: dev-setup pretty fix-imports run-linter dev-server test test-unit test-cov check \
        pre-commit-install pre-commit-run docker-build docker-up docker-down docker-logs clean
