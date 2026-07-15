from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from app.routers.ai_matches import router as ai_matches_router
from app.routers.candidate_profiles import router as candidate_profiles_router
from app.routers.internal_mobility_requests import router as internal_mobility_requests_router
from app.routers.sample_writing_assistant import router as sample_writing_assistant_router
from app.utils.exceptions import BaseServiceException
from app.utils.logs import add_common_context_args, agent


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    logger = agent.get_context_bound_logger()
    logger.info("Starting Internal Mobility Matching Service")
    yield
    logger.info("Shutting down Internal Mobility Matching Service")


app = FastAPI(
    title="Internal Mobility Matching Service",
    lifespan=lifespan
)

app.include_router(ai_matches_router)
app.include_router(candidate_profiles_router)
app.include_router(internal_mobility_requests_router)
app.include_router(sample_writing_assistant_router)


@app.exception_handler(BaseServiceException)
async def base_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.as_dict()}
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


@app.exception_handler(Exception)
async def validation_exception_handler(request, err):
    base_error_message = f"Failed to execute: {request.method}: {request.url}"
    logger = agent.get_context_bound_logger()
    logger.error(base_error_message, exc_info=err)
    return JSONResponse(status_code=400, content={"message": f"{base_error_message}. Detail: {err}"})


@app.middleware("http")
async def http_middleware(request: Request, call_next):
    return await add_logging_middleware(request, call_next)


async def add_logging_middleware(request: Request, call_next):
    logger = agent.get_context_bound_logger()
    try:
        add_common_context_args(
            method=request.method,
            url=str(request.url),
            org_id=request.headers.get("auth-org-id"),
            user_id=request.headers.get("auth-user-id"),
            request_id=request.headers.get("x-request-id"),
            client_ip=request.headers.get("auth-client-ip"),
        )
        return await call_next(request)

    except Exception as e:
        logger.error(
            'Exception caught at http middleware',
            exc_info=e,
            method=request.method,
            url=str(request.url),
            org_id=request.headers.get("auth-org-id"),
            user_id=request.headers.get("auth-user-id"),
            request_id=request.headers.get("x-request-id"),
            client_ip=request.headers.get("auth-client-ip"),
        )
        return JSONResponse(status_code=500, content={"error": {"message": "Internal server error"}})


@app.get("/api/health/")
async def health_check():
    return "ok"


@app.get("/api/ready/")
async def ready_check():
    return "ok"
