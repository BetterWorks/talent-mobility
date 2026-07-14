#!/bin/sh
if [ "$1" = "api" ]; then
  uvicorn app.main:app --proxy-headers --lifespan on --host 0.0.0.0 --port 8000
else
  exec "$@"
fi
