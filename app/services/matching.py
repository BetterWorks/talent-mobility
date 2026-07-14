from uuid import UUID

from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import engine
from app.db.run_ai_matches import RunAiMatchesDAO, RunAiMatchesStatus
from app.utils.logs import agent


logger = agent.get_context_bound_logger()


async def run_ai_match(run_id: UUID, request_id: UUID) -> None:
    """Entry point invoked by the Celery task. Opens its own DB session,
    since Celery workers don't share the FastAPI request-scoped session.
    """
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        dao = RunAiMatchesDAO(session)
        await dao.update(run_id, status=RunAiMatchesStatus.RUNNING.value)

        try:
            # TODO: fetch internal_mobility_request + candidate pool, score via
            # embeddings/llm-proxy, and persist results as candidate_profile rows.
            logger.info("Running AI match", run_id=str(run_id), request_id=str(request_id))

            await dao.update(run_id, status=RunAiMatchesStatus.COMPLETED.value)
        except Exception:
            await dao.update(run_id, status=RunAiMatchesStatus.FAILED.value)
            raise
