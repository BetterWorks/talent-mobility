from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.db.run_ai_matches import RunAiMatchesStatus
from app.models.candidate_profile_data import Confidence, CostImpact, LLMCandidateInsights
from app.services import matching
from app.services.matching import _format_savings, _format_tenure, run_ai_match


ORG = uuid4()
REQUEST_ID = uuid4()
RUN_ID = uuid4()
USER_A, USER_B = uuid4(), uuid4()


def _insights():
    return LLMCandidateInsights(
        summary="Strong platform fit.",
        strengths=["Python", "ML"],
        gaps=["Vector DB"],
        career_signals=["Wants AI work"],
        evidence=["Built ML pipeline"],
        readiness_factors=[],
        confidence=Confidence.HIGH,
        ready_in="4-6 weeks",
        cost_impact=CostImpact.HIGH,
    )


def _make_daos(top_candidates, synth_side_effect):
    """Patch every collaborator run_ai_match touches and return recorders."""
    run_dao = SimpleNamespace(update=AsyncMock())
    request_dao = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(
            job_description="Build the AI platform.", max_salary=Decimal("80000"),
        )),
        update=AsyncMock(),
    )
    candidate_dao = SimpleNamespace(bulk_create=AsyncMock())
    embeddings_dao = SimpleNamespace(
        top_candidates=AsyncMock(return_value=top_candidates),
        top_rows_for_user=AsyncMock(return_value=[]),
    )
    hris_dao = SimpleNamespace(get_by_users=AsyncMock(return_value=[
        SimpleNamespace(
            user_uuid=USER_A, department="Engineering", location="Bangalore",
            start_date=date(2022, 1, 1), current_manager="Ramesh B.",
            job_level="L5 · Senior", current_salary=Decimal("62000"),
        ),
    ]))
    return run_dao, request_dao, candidate_dao, embeddings_dao, hris_dao


@pytest.mark.asyncio
async def test_run_ai_match_persists_merged_profiles():
    top = [(USER_A, ORG, 0.42), (USER_B, ORG, 0.31)]
    run_dao, request_dao, candidate_dao, embeddings_dao, hris_dao = _make_daos(top, None)

    with patch.object(matching, "sessionmaker"), \
         patch.object(matching, "RunAiMatchesDAO", return_value=run_dao), \
         patch.object(matching, "InternalMobilityRequestDAO", return_value=request_dao), \
         patch.object(matching, "CandidateProfileDAO", return_value=candidate_dao), \
         patch.object(matching, "DataEmbeddingsDAO", return_value=embeddings_dao), \
         patch.object(matching, "UsersHrisDetailsDAO", return_value=hris_dao), \
         patch.object(matching, "embed_queries", AsyncMock(return_value=[[0.1] * 768])), \
         patch.object(matching, "synthesize_candidate", AsyncMock(return_value=_insights())):
        # sessionmaker() -> factory -> async context manager yielding a session
        matching.sessionmaker.return_value.return_value.__aenter__ = AsyncMock()
        matching.sessionmaker.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        await run_ai_match(RUN_ID, REQUEST_ID)

    # Both users synthesized and persisted.
    candidate_dao.bulk_create.assert_awaited_once()
    persisted = candidate_dao.bulk_create.call_args.args[0]
    assert len(persisted) == 2

    prof_a = next(p for p in persisted if p.user_uuid == USER_A).profile_data
    assert prof_a["match_score"] == 42          # retrieval score, not LLM
    assert prof_a["department"] == "Engineering"  # HRIS fact
    assert prof_a["estimated_savings"] == "$18K"  # 80000 - 62000
    assert prof_a["summary"] == "Strong platform fit."  # LLM insight
    assert prof_a["confidence"] == "High"

    # User B has no HRIS row -> header fields null, savings null.
    prof_b = next(p for p in persisted if p.user_uuid == USER_B).profile_data
    assert prof_b["department"] is None
    assert prof_b["estimated_savings"] is None

    # Run + request marked completed / review.
    run_dao.update.assert_any_await(RUN_ID, status=RunAiMatchesStatus.COMPLETED.value)


@pytest.mark.asyncio
async def test_run_ai_match_skips_failed_synthesis():
    top = [(USER_A, ORG, 0.42), (USER_B, ORG, 0.31)]
    run_dao, request_dao, candidate_dao, embeddings_dao, hris_dao = _make_daos(top, None)

    # First user fails synthesis, second succeeds.
    synth = AsyncMock(side_effect=[RuntimeError("bad json"), _insights()])

    with patch.object(matching, "sessionmaker"), \
         patch.object(matching, "RunAiMatchesDAO", return_value=run_dao), \
         patch.object(matching, "InternalMobilityRequestDAO", return_value=request_dao), \
         patch.object(matching, "CandidateProfileDAO", return_value=candidate_dao), \
         patch.object(matching, "DataEmbeddingsDAO", return_value=embeddings_dao), \
         patch.object(matching, "UsersHrisDetailsDAO", return_value=hris_dao), \
         patch.object(matching, "embed_queries", AsyncMock(return_value=[[0.1] * 768])), \
         patch.object(matching, "synthesize_candidate", synth):
        matching.sessionmaker.return_value.return_value.__aenter__ = AsyncMock()
        matching.sessionmaker.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        await run_ai_match(RUN_ID, REQUEST_ID)

    persisted = candidate_dao.bulk_create.call_args.args[0]
    assert len(persisted) == 1                       # failed user skipped
    assert persisted[0].user_uuid == USER_B
    run_dao.update.assert_any_await(RUN_ID, status=RunAiMatchesStatus.COMPLETED.value)


def test_format_savings():
    assert _format_savings(Decimal("80000"), Decimal("62000")) == "$18K"
    assert _format_savings(Decimal("50000"), Decimal("60000")) == "$0"
    assert _format_savings(None, Decimal("60000")) is None


def test_format_tenure_none():
    assert _format_tenure(None) is None
