from typing import Optional
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.candidate_profile import CandidateProfile
from app.db.consent import ConsentBase, ConsentDAO, ConsentParticipantRole, ConsentType
from app.db.internal_mobility_request import InternalMobilityRequest
from app.routers.user_directory import get_user_details


async def seed_case_consents(
    session: AsyncSession,
    case_id: UUID,
    profile: CandidateProfile,
    role_request: Optional[InternalMobilityRequest],
) -> None:
    """Auto-create the 4 consent participants for a newly-approved case: candidate, current
    manager, hiring manager, HRBP. A real user reference only exists for the candidate (via
    user_directory) — neither role_request.hiring_manager nor the candidate's current_manager
    are real user ids, just denormalized display-name strings, so that's all we can store.
    There's no HRBP-per-case assignment anywhere yet, so that row's participant_name is left
    unset (the card still shows role/designation, just no person name) rather than inventing
    one."""
    details = get_user_details(profile.user_uuid)
    prof = details["profile"] if details else {}

    rows = [
        ConsentBase(
            case_id=case_id,
            participant_role=ConsentParticipantRole.CANDIDATE.value,
            participant_name=prof.get("name"),
            role_label="Candidate",
            designation=prof.get("role"),
            consent_type=ConsentType.CONSENT.value,
        ),
        ConsentBase(
            case_id=case_id,
            participant_role=ConsentParticipantRole.CURRENT_MANAGER.value,
            participant_name=prof.get("current_manager"),
            role_label="Current Manager",
            designation="Manager",
            consent_type=ConsentType.RELEASE.value,
        ),
        ConsentBase(
            case_id=case_id,
            participant_role=ConsentParticipantRole.HIRING_MANAGER.value,
            participant_name=role_request.hiring_manager if role_request else None,
            role_label="Hiring Manager",
            designation="Hiring Manager",
            consent_type=ConsentType.CONFIRMATION.value,
        ),
        ConsentBase(
            case_id=case_id,
            participant_role=ConsentParticipantRole.HRBP.value,
            participant_name=None,
            role_label="HRBP",
            designation="HR Business Partner",
            consent_type=ConsentType.POLICY.value,
        ),
    ]
    await ConsentDAO(session).bulk_create(rows)
