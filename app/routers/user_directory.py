from uuid import UUID

from fastapi import APIRouter, HTTPException


# Dummy stub router for the Candidate Deep Dive screen's identity + HRIS blocks
# (Overview header, "Employment (HRIS)" and "Role & Eligibility (HRIS)" cards).
# Unblocks frontend work while the real core-profile / HRIS wiring is pending.
#
# Everything here is in-memory, canned data keyed by the user_uuids that exist
# in better_sense.data_embeddings. NOTHING is read from or written to the
# users_hris_details table — this is a read-only fixture.
#
# Names, employee IDs, roles, departments and managers were extracted from the
# embedding evidence so the Deep Dive identity matches the AI summary. Fields
# not present in the evidence (location, start_date, employment type/status,
# mobility eligibility) are representative stub values. Compensation is masked
# per the fairness policy and is never returned as a figure.
router = APIRouter(prefix="/users", tags=["UserDirectory"])


ORG_UUID = "b9b6d32b-e201-5da0-849a-7d841be48de7"

# Keyed by user_uuid. `profile` = identity/header fields (core-profile-owned),
# `hris` = the two HRIS cards. Compensation is intentionally masked.
_USERS: dict[str, dict] = {
    "7bda3137-c9fb-5f30-a1bc-128322c8f32c": {
        "profile": {
            "name": "Rachel Kim",
            "initials": "RK",
            "role": "Engineering Manager",
            "department": "Platform Services",
            "location": "San Francisco, CA, United States",
            "tenure": "4.1 yrs",
            "current_manager": "Marcus Webb",
        },
        "hris": {
            "employee_id": "EMP-006",
            "department": "Platform Services",
            "current_manager": "Marcus Webb",
            "location": "San Francisco, CA, United States",
            "employment_type": "Full-time",
            "employment_status": "Active",
            "job_level": "L6 · Manager",
            "tenure_in_role": "4.1 yrs",
            "start_date": "2022-05-16",
            "mobility_eligibility": "Eligible (18+ mo)",
            "compensation_band": "Masked",
            "budget_currency": "USD",
            "last_org_change": "—",
        },
    },
    "7f65f139-fb5c-56fe-b07d-67e7850bcc32": {
        "profile": {
            "name": "Noah Bennett",
            "initials": "NB",
            "role": "Senior Platform Engineer",
            "department": "Platform",
            "location": "Seattle, WA, United States",
            "tenure": "3.4 yrs",
            "current_manager": "Rachel Kim",
        },
        "hris": {
            "employee_id": "EMP-011",
            "department": "Platform",
            "current_manager": "Rachel Kim",
            "location": "Seattle, WA, United States",
            "employment_type": "Full-time",
            "employment_status": "Active",
            "job_level": "L5 · Senior",
            "tenure_in_role": "3.4 yrs",
            "start_date": "2023-01-09",
            "mobility_eligibility": "Eligible (18+ mo)",
            "compensation_band": "Masked",
            "budget_currency": "USD",
            "last_org_change": "—",
        },
    },
    "122da2d4-25c6-565b-80aa-797b9e9af862": {
        "profile": {
            "name": "Daniel Cho",
            "initials": "DC",
            "role": "Engineering Manager",
            "department": "Infrastructure",
            "location": "Austin, TX, United States",
            "tenure": "5.2 yrs",
            "current_manager": "Marcus Webb",
        },
        "hris": {
            "employee_id": "EMP-005",
            "department": "Infrastructure",
            "current_manager": "Marcus Webb",
            "location": "Austin, TX, United States",
            "employment_type": "Full-time",
            "employment_status": "Active",
            "job_level": "L6 · Manager",
            "tenure_in_role": "5.2 yrs",
            "start_date": "2021-04-12",
            "mobility_eligibility": "Eligible (18+ mo)",
            "compensation_band": "Masked",
            "budget_currency": "USD",
            "last_org_change": "—",
        },
    },
    "c8e5c2ad-bbee-5ecf-8dd9-0726f8af314e": {
        "profile": {
            "name": "Tyler Brooks",
            "initials": "TB",
            "role": "Senior Site Reliability Engineer",
            "department": "SRE / Reliability",
            "location": "New York, NY, United States",
            "tenure": "2.9 yrs",
            "current_manager": "Daniel Cho",
        },
        "hris": {
            "employee_id": "EMP-009",
            "department": "SRE / Reliability",
            "current_manager": "Daniel Cho",
            "location": "New York, NY, United States",
            "employment_type": "Full-time",
            "employment_status": "Active",
            "job_level": "L5 · Senior",
            "tenure_in_role": "2.9 yrs",
            "start_date": "2023-06-01",
            "mobility_eligibility": "Eligible (18+ mo)",
            "compensation_band": "Masked",
            "budget_currency": "USD",
            "last_org_change": "—",
        },
    },
    "ed458329-203f-5e5f-bf09-5796888459b0": {
        "profile": {
            "name": "Aisha Patel",
            "initials": "AP",
            "role": "Site Reliability Engineer",
            "department": "SRE / Reliability",
            "location": "Denver, CO, United States",
            "tenure": "2.1 yrs",
            "current_manager": "Daniel Cho",
        },
        "hris": {
            "employee_id": "EMP-010",
            "department": "SRE / Reliability",
            "current_manager": "Daniel Cho",
            "location": "Denver, CO, United States",
            "employment_type": "Full-time",
            "employment_status": "Active",
            "job_level": "L4 · Mid",
            "tenure_in_role": "2.1 yrs",
            "start_date": "2024-05-20",
            "mobility_eligibility": "Eligible (18+ mo)",
            "compensation_band": "Masked",
            "budget_currency": "USD",
            "last_org_change": "—",
        },
    },
}


def _serialize(user_uuid: str, record: dict) -> dict:
    return {
        "user_uuid": user_uuid,
        "org_uuid": ORG_UUID,
        "profile": record["profile"],
        "hris": record["hris"],
    }


def get_user_details(user_uuid) -> dict | None:
    """Lookup for other routers to enrich responses with stub identity + HRIS.

    Returns {"profile": {...}, "hris": {...}} for a known user_uuid, else None.
    """
    record = _USERS.get(str(user_uuid))
    if not record:
        return None
    return {"profile": record["profile"], "hris": record["hris"]}


@router.get("/")
async def list_users() -> dict:
    """Candidate directory: all stubbed users with profile + HRIS details."""
    return {"data": [_serialize(uid, rec) for uid, rec in _USERS.items()]}


@router.get("/{user_uuid}")
async def get_user(user_uuid: UUID) -> dict:
    """Candidate Deep Dive: one user's identity + HRIS blocks."""
    record = _USERS.get(str(user_uuid))
    if not record:
        raise HTTPException(status_code=404, detail="User not found")
    return {"data": _serialize(str(user_uuid), record)}
