from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.candidate_profile import CandidateProfileDAO
from app.db.run_ai_matches import RunAiMatches, RunAiMatchesBase, RunAiMatchesDAO
from app.worker.tasks import run_ai_match_task


router = APIRouter(prefix="/api/ai-matches", tags=["ai-matches"])


@router.post("/", response_model=RunAiMatches)
async def start_ai_match_run(
    request_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    dao = RunAiMatchesDAO(session)
    run = await dao.create(RunAiMatchesBase(request_id=request_id))
    run_ai_match_task.delay(run_id=str(run.id), request_id=str(request_id))
    return run


@router.get("/{run_id}", response_model=RunAiMatches)
async def get_ai_match_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    dao = RunAiMatchesDAO(session)
    run = await dao.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{run_id}/candidates")
async def list_ai_match_candidates(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    dao = CandidateProfileDAO(session)
    return await dao.get_by_run(run_id)
