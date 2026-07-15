from uuid import UUID, uuid4

from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import engine
from app.db.candidate_profile import CandidateProfileBase, CandidateProfileDAO, CandidateProfileStatus
from app.db.internal_mobility_request import InternalMobilityRequestDAO, InternalMobilityRequestStatus
from app.db.run_ai_matches import RunAiMatchesDAO, RunAiMatchesStatus
from app.models.candidate_profile_data import CandidateProfileData, ReadinessFactor
from app.utils.logs import agent


logger = agent.get_context_bound_logger()

# Placeholder candidate pool used until a real HRIS-backed eligible-employee
# lookup replaces it. Keeps the run_ai_matches -> candidate_profile pipeline
# demonstrably wired end-to-end for the UI.
STUB_CANDIDATES = [
    CandidateProfileData(
        name="Arjun Kumar", current_role="Senior Software Engineer",
        department="Engineering Platform", location="Bangalore, India",
        tenure="3.2 yrs", current_manager="Ramesh B.",
        match_score=92, ready_in="4-6 weeks", cost_impact="High", estimated_savings="$62K",
        summary="Strong internal match based on platform experience and execution track record.",
        strengths=["Python, ML, MLOps", "Strong problem solving", "High ownership"],
        gaps=["Vector DB experience", "Evaluation framework knowledge"],
        career_signals=["Interested in AI/ML roles", "Open to lateral move"],
        evidence=["Built ML pipeline reducing data latency by 40%"],
        readiness_factors=[
            ReadinessFactor(label="Skill Match", level="high"),
            ReadinessFactor(label="Performance", level="high"),
        ],
    ),
    CandidateProfileData(
        name="Priya Nair", current_role="ML Engineer",
        department="Data Science", location="Bangalore, India",
        tenure="2.5 yrs", current_manager="Sunita M.",
        match_score=86, ready_in="6 weeks", cost_impact="High", estimated_savings="$65K",
        summary="Close match with deep LLM and data engineering experience.",
        strengths=["LLM, NLP", "Data engineering", "Strong collaboration"],
        gaps=["Platform infra at scale", "Vector DB tuning"],
        career_signals=["Interested in AI platform work", "Open to lateral move"],
        evidence=["Built LLM evaluation harness used org-wide"],
        readiness_factors=[
            ReadinessFactor(label="Skill Match", level="high"),
            ReadinessFactor(label="Performance", level="high"),
        ],
    ),
]


async def run_ai_match(run_id: UUID, request_id: UUID) -> None:
    """Entry point invoked by the Celery task. Opens its own DB session,
    since Celery workers don't share the FastAPI request-scoped session.
    """
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        run_dao = RunAiMatchesDAO(session)
        request_dao = InternalMobilityRequestDAO(session)
        candidate_dao = CandidateProfileDAO(session)

        await run_dao.update(run_id, status=RunAiMatchesStatus.RUNNING.value)
        await request_dao.update(request_id, status=InternalMobilityRequestStatus.IN_PROGRESS.value)

        try:
            # TODO: replace the stub pool with a real HRIS-backed eligible-employee
            # lookup, and score candidates via embeddings/llm-proxy.
            logger.info("Running AI match", run_id=str(run_id), request_id=str(request_id))

            await candidate_dao.bulk_create([
                CandidateProfileBase(
                    user_uuid=uuid4(),
                    org_uuid=uuid4(),
                    run_ai_match=run_id,
                    profile_data=candidate.model_dump(mode='json'),
                    status=CandidateProfileStatus.MATCHED.value,
                )
                for candidate in STUB_CANDIDATES
            ])

            await run_dao.update(run_id, status=RunAiMatchesStatus.COMPLETED.value)
            await request_dao.update(request_id, status=InternalMobilityRequestStatus.REVIEW.value)
        except Exception:
            await run_dao.update(run_id, status=RunAiMatchesStatus.FAILED.value)
            raise
