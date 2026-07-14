#!/bin/sh
if [ "$1" = "api" ]; then
  uvicorn app.main:app --proxy-headers --lifespan on --host 0.0.0.0 --port "${APP_PORT:-4004}"
elif [ "$1" = "migrate" ]; then
  alembic upgrade head
elif [ "$1" = "worker" ]; then
  celery --app app.celery_app worker --loglevel=INFO &
  uvicorn app.worker_healthcheck:app --host 0.0.0.0 --port "${APP_PORT:-4004}"
else
  exec "$@"
fi
