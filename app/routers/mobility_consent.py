from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.consent import Consent, ConsentDAO, ConsentStatus
from app.models.consent import ConsentDeadlineRequest, ConsentMarkReceivedRequest, NotifyCreateRequest
from app.utils.common import get_utc_now
from app.utils.exceptions import MobilityApiError


# Router for the Consent screen. Participants (candidate/current_manager/hiring_manager) are
# auto-created as `consent` rows when a case is approved (see services/consent_seed.py) — there's
# no "add participant" flow, so `participantId` in these routes is just the consent row's own id.
router = APIRouter(prefix="/cases", tags=["Consent"])


def _serialize(consent: Consent) -> dict[str, Any]:
    return {
        "type": "mobility_consent",
        "id": str(consent.id),
        "attributes": {
            "participant": {"id": str(consent.id), "name": consent.participant_name, "role": consent.role_label},
            "role_label": consent.role_label,
            "designation": consent.designation,
            "consent_type": consent.consent_type,
            "status": consent.status,
            "deadline": consent.deadline.isoformat() if consent.deadline else None,
            "requested_on": consent.requested_on.isoformat() if consent.requested_on else None,
            "last_reminder_on": consent.last_reminder_on.isoformat() if consent.last_reminder_on else None,
            "received_on": consent.received_on.isoformat() if consent.received_on else None,
            "received_by_hr": consent.received_by_hr,
            "escalated": consent.escalated,
            "reason_code": consent.reason_code,
        },
    }


async def _get_consent_or_404(session: AsyncSession, participant_id: UUID) -> Consent:
    consent = await ConsentDAO(session).get_by_id(participant_id)
    if not consent:
        raise MobilityApiError(404, "Consent participant not found")
    return consent


@router.get("/{case_id}/consents")
async def list_consents(case_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    rows: List[Consent] = await ConsentDAO(session).list_by_case(case_id)
    total = len(rows)
    received = sum(1 for r in rows if r.status == ConsentStatus.RECEIVED.value)
    return {
        "data": [_serialize(r) for r in rows],
        "included": [],
        "meta": {
            "received": received,
            "total": total,
            "can_proceed": total > 0 and received == total,
        },
    }


@router.post("/{case_id}/consents/{participant_id}/request")
async def request_consent(
    case_id: UUID, participant_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    await _get_consent_or_404(session, participant_id)
    consent = await ConsentDAO(session).update(
        participant_id, status=ConsentStatus.REQUESTED.value, requested_on=get_utc_now(tz=False)
    )
    return {"data": _serialize(consent)}


@router.post("/{case_id}/consents/{participant_id}/remind")
async def remind_consent(
    case_id: UUID, participant_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    await _get_consent_or_404(session, participant_id)
    consent = await ConsentDAO(session).update(participant_id, last_reminder_on=get_utc_now(tz=False))
    return {"data": _serialize(consent)}


@router.post("/{case_id}/consents/{participant_id}/mark-received")
async def mark_consent_received(
    case_id: UUID,
    participant_id: UUID,
    body: ConsentMarkReceivedRequest = ConsentMarkReceivedRequest(),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _get_consent_or_404(session, participant_id)
    by_hr = bool(body.data.attributes.by_hr) if body.data and body.data.attributes else False
    consent = await ConsentDAO(session).update(
        participant_id,
        status=ConsentStatus.RECEIVED.value,
        received_on=get_utc_now(tz=False),
        received_by_hr=by_hr,
    )
    return {"data": _serialize(consent)}


@router.post("/{case_id}/consents/{participant_id}/escalate")
async def escalate_consent(
    case_id: UUID, participant_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    await _get_consent_or_404(session, participant_id)
    consent = await ConsentDAO(session).update(participant_id, escalated=True)
    return {"data": _serialize(consent)}


@router.patch("/{case_id}/consents/{participant_id}/deadline")
async def set_consent_deadline(
    case_id: UUID, participant_id: UUID, body: ConsentDeadlineRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    await _get_consent_or_404(session, participant_id)
    consent = await ConsentDAO(session).update(participant_id, deadline=body.data.attributes.deadline)
    return {"data": _serialize(consent)}


@router.post("/{case_id}/notify")
async def notify_participants(
    case_id: UUID,
    body: NotifyCreateRequest = NotifyCreateRequest(),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """No real email/Slack/in-app notification integration exists — this always reports success
    for every requested recipient rather than actually sending anything."""
    recipient_ids = (body.data.attributes.recipient_ids if body.data and body.data.attributes else None) or []
    if not recipient_ids:
        rows = await ConsentDAO(session).list_by_case(case_id)
        recipient_ids = [str(r.id) for r in rows]
    return {"data": {"type": "mobility_notification", "attributes": {"sent": len(recipient_ids), "failed": []}}}
