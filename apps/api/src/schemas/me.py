from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: Optional[str] = None
    created_at: Optional[datetime] = None


class PatchMeRequest(BaseModel):
    display_name: Optional[str] = None


class VisibilitySettingsResponse(BaseModel):
    """Matches db.models.VisibilitySettings."""

    open_to_work: bool
    work_preferred_locations: list[str]
    work_preferred_salary_min: Optional[Decimal] = None
    work_preferred_salary_max: Optional[Decimal] = None
    open_to_contact: bool


class PatchVisibilityRequest(BaseModel):
    """Optional fields for patching VisibilitySettings (matches DB columns)."""

    open_to_work: Optional[bool] = None
    work_preferred_locations: Optional[list[str]] = None
    work_preferred_salary_min: Optional[Decimal] = None
    work_preferred_salary_max: Optional[Decimal] = None
    open_to_contact: Optional[bool] = None
