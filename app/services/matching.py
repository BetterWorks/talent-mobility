from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import engine
from app.db.candidate_profile import CandidateProfileBase, CandidateProfileDAO, CandidateProfileStatus
from app.db.data_embeddings import DataEmbeddingsDAO
from app.db.internal_mobility_request import InternalMobilityRequestDAO, InternalMobilityRequestStatus
from app.db.run_ai_matches import RunAiMatchesDAO, RunAiMatchesStatus
from app.db.users_hris_details import UsersHrisDetails, UsersHrisDetailsDAO
from app.models.candidate_profile_data import CandidateProfileData
from app.routers.user_directory import get_user_details
from app.services.synthesis import synthesize_candidate
from app.utils.common import get_utc_now
from app.utils.embedding import embed_queries
from app.utils.logs import agent


logger = agent.get_context_bound_logger()

# Number of top-ranked candidates to build profiles for. Everyone below this
# cutoff is dropped before the (expensive) per-candidate LLM synthesis.
SHORTLIST_SIZE = 5

# How many of each user's best-matching embedding rows feed into scoring and
# into the LLM synthesis prompt.
TOP_K_ROWS_PER_USER = 10


def _score_to_percent(raw_score: float) -> int:
    """Map a raw cosine similarity (~0.3-0.5) to a 0-100 integer.

    Display convenience for the UI match-score column; valid for *ranking*
    order only, not a calibrated match probability (calibration is deferred).
    """
    return max(0, min(100, round(raw_score * 100)))


def _format_tenure(start: Optional[date]) -> Optional[str]:
    if start is None:
        return None
    days = (get_utc_now(tz=False).date() - start).days
    if days < 0:
        return None
    return '%.1f yrs' % (days / 365.25)


def _format_savings(max_salary: Optional[Decimal], current_salary: Optional[Decimal]) -> Optional[str]:
    """Cost saving = role max budget - candidate's current salary."""
    if max_salary is None or current_salary is None:
        return None
    savings = Decimal(max_salary) - Decimal(current_salary)
    if savings <= 0:
        return '$0'
    return '$%dK' % round(savings / 1000)


def _cost_difference(max_salary: Optional[Decimal], current_salary: Optional[Decimal]) -> Optional[float]:
    """Numeric cost difference = role max budget - candidate current salary."""
    if max_salary is None or current_salary is None:
        return None
    return float(Decimal(str(max_salary)) - Decimal(str(current_salary)))


def _build_profile(
    insights,
    hris: Optional[UsersHrisDetails],
    max_salary: Optional[Decimal],
    fallback_name: str,
    current_salary: Optional[Decimal] = None,
) -> CandidateProfileData:
    # Prefer an explicitly-supplied salary (e.g. the user-directory stub) over
    # the HRIS row, which is often empty in local/dev data.
    salary = current_salary if current_salary is not None else (hris.current_salary if hris else None)
    return CandidateProfileData(
        name=fallback_name,
        current_role=(hris.job_level if hris else None) or '',
        department=hris.department if hris else None,
        location=hris.location if hris else None,
        tenure=_format_tenure(hris.start_date) if hris else None,
        current_manager=hris.current_manager if hris else None,
        match_score=max(0, min(100, insights.match_score)),
        ready_in=insights.ready_in,
        cost_impact=insights.cost_impact,
        estimated_savings=_format_savings(max_salary, salary),
        cost_difference=_cost_difference(max_salary, salary),
        confidence=insights.confidence,
        summary=insights.summary,
        strengths=insights.strengths,
        gaps=insights.gaps,
        career_signals=insights.career_signals,
        evidence=insights.evidence,
        readiness_factors=insights.readiness_factors,
    )


async def run_ai_match(run_id: UUID, request_id: UUID) -> None:
    """Entry point invoked by the Celery task. Opens its own DB session,
    since Celery workers don't share the FastAPI request-scoped session.

    Pipeline: fetch the role request -> embed its job description -> rank all
    embedded users -> take the top N -> for each, retrieve their top evidence
    rows, run one LLM synthesis call, merge with HRIS facts and the retrieval
    score -> persist one candidate profile per shortlisted user.
    """
    run_id = UUID(str(run_id))
    request_id = UUID(str(request_id))

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        run_dao = RunAiMatchesDAO(session)
        request_dao = InternalMobilityRequestDAO(session)
        candidate_dao = CandidateProfileDAO(session)
        embeddings_dao = DataEmbeddingsDAO(session)
        hris_dao = UsersHrisDetailsDAO(session)

        await run_dao.update(run_id, status=RunAiMatchesStatus.RUNNING.value)
        await request_dao.update(request_id, status=InternalMobilityRequestStatus.IN_PROGRESS.value)

        try:
            request = await request_dao.get_by_id(request_id)
            if request is None:
                raise ValueError("Role request %s not found" % request_id)
            if not request.job_description:
                raise ValueError("Role request %s has no job description to match against" % request_id)

            logger.info("Running AI match", run_id=str(run_id), request_id=str(request_id))

            # Stage 1: embed the job description as a query vector.
            jd_vec = (await embed_queries([request.job_description], prompt_name="query"))[0]

            # Stages 2-3: rank all embedded users, keep the top N.
            top_candidates = await embeddings_dao.top_candidates(
                jd_vec, limit=SHORTLIST_SIZE, top_k=TOP_K_ROWS_PER_USER
            )
            ranking = [
                {
                    "user_uuid": str(user_uuid),
                    "raw_score": round(raw_score, 4),
                    "match_pct": _score_to_percent(raw_score),
                }
                for user_uuid, _, raw_score in top_candidates
            ]
            logger.info(
                "Ranked candidates",
                run_id=str(run_id),
                shortlisted=len(top_candidates),
                top_k_rows_per_user=TOP_K_ROWS_PER_USER,
                ranking=ranking,
            )

            # Batch-fetch HRIS for all shortlisted users (single org assumed per run).
            hris_by_user = {}
            if top_candidates:
                org_uuid = top_candidates[0][1]
                user_uuids = [uid for uid, _, _ in top_candidates]
                hris_rows = await hris_dao.get_by_users(user_uuids, org_uuid)
                hris_by_user = {row.user_uuid: row for row in hris_rows}

            # Stage 4: one LLM synthesis call per shortlisted user. A failed call
            # skips that user rather than failing the whole run.
            profiles = []
            for user_uuid, user_org_uuid, _ in top_candidates:
                try:
                    rows = await embeddings_dao.top_rows_for_user(
                        user_uuid, user_org_uuid, jd_vec, k=TOP_K_ROWS_PER_USER
                    )
                    insights = await synthesize_candidate(
                        request.job_description, rows, request.required_skills
                    )
                except Exception as exc:
                    logger.warning(
                        "Candidate synthesis failed; skipping",
                        run_id=str(run_id), user_uuid=str(user_uuid), error=str(exc),
                    )
                    continue

                hris = hris_by_user.get(user_uuid)
                # HRIS salary is typically empty in local data; fall back to the
                # user-directory stub so cost_difference is populated.
                stub = get_user_details(user_uuid)
                stub_salary = stub["hris"].get("current_salary") if stub else None
                profile_data = _build_profile(
                    insights, hris, request.max_salary, fallback_name=str(user_uuid),
                    current_salary=stub_salary,
                )
                profiles.append(
                    CandidateProfileBase(
                        user_uuid=user_uuid,
                        org_uuid=user_org_uuid,
                        run_ai_match=run_id,
                        profile_data=profile_data.model_dump(mode='json'),
                        status=CandidateProfileStatus.MATCHED.value,
                    )
                )

            if profiles:
                await candidate_dao.bulk_create(profiles)
            logger.info("Persisted candidate profiles", run_id=str(run_id), count=len(profiles))

            await run_dao.update(run_id, status=RunAiMatchesStatus.COMPLETED.value)
            await request_dao.update(request_id, status=InternalMobilityRequestStatus.REVIEW.value)
        except Exception:
            await run_dao.update(run_id, status=RunAiMatchesStatus.FAILED.value)
            raise
