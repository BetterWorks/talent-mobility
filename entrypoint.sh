#!/bin/sh
if [ "$1" = "api" ]; then
  set -- uvicorn app.main:app --proxy-headers --lifespan on --host 0.0.0.0 --port "${APP_PORT:-4004}"
  if [ "${UVICORN_RELOAD:-false}" = "true" ]; then
    set -- "$@" --reload --reload-dir /code/app
  fi
  exec "$@"
elif [ "$1" = "migrate" ]; then
  alembic upgrade head
elif [ "$1" = "worker" ]; then
  if [ "${WORKER_RELOAD:-false}" = "true" ]; then
    exec python -m watchfiles --filter python "sh -c 'celery --app app.celery_app worker --loglevel=INFO & uvicorn app.worker_healthcheck:app --host 0.0.0.0 --port ${APP_PORT:-4004}; wait'" /code/app
  fi
  celery --app app.celery_app worker --loglevel=INFO &
  exec uvicorn app.worker_healthcheck:app --host 0.0.0.0 --port "${APP_PORT:-4004}"
else
  exec "$@"
fi
