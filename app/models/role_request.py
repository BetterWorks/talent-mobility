from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class RoleRequestCreatePlainRequest(BaseModel):
    """Live request body for POST /services/mobility/role-requests/.

    Flat fields, no `data` wrapper, no ai_policy/save_as_draft — matches
    openapi.yaml's RoleRequestCreatePlainRequest schema exactly. Excludes
    server-controlled fields (id, created, modified, status) so the client
    can't set them.
    """
    title: str
    job_description: Optional[str] = None
    seniority_level: Optional[str] = None
    business_unit: Optional[str] = None
    hiring_manager: Optional[str] = None
    min_salary: Optional[Decimal] = None
    max_salary: Optional[Decimal] = None
    budget_currency: Optional[str] = None
    required_skills: Optional[List[str]] = None
    number_of_candidates_to_hire: Optional[int] = None
    hiring_estimate_in_days: Optional[int] = None
    external_hiring_cost: Optional[Decimal] = None
    start_date_target: Optional[date] = None
