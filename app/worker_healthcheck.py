from fastapi import FastAPI
from kombu import Connection

from app import settings


app = FastAPI()


@app.get("/api/health/")
def liveness():
    return {"status": "alive"}


@app.get("/api/ready/")
def readiness():
    try:
        with Connection(settings.REDIS_BROKER_URL, connect_timeout=2) as conn:
            conn.connect()
        return {"status": "ready"}
    except Exception as e:
        return {"status": "not-ready", "error": str(e)}
