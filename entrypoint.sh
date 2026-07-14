#!/bin/sh
if [ "$1" = "api" ]; then
  uvicorn app.main:app --proxy-headers --lifespan on --host 0.0.0.0 --port "${APP_PORT:-4004}"
else
  exec "$@"
fi
