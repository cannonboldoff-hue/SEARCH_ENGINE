from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from src.schemas.contact import ContactDetailsResponse
from src.schemas.builder import ExperienceCardResponse


class SearchRequest(BaseModel):
    query: str
    open_to_work_only: Optional[bool] = None
    preferred_locations: Optional[list[str]] = None
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None


class PersonSearchResult(BaseModel):
    id: str
    display_name: Optional[str] = None
    open_to_work: bool
    open_to_contact: bool


class SearchResponse(BaseModel):
    search_id: str
    people: list[PersonSearchResult]


class PersonProfileResponse(BaseModel):
    """Profile for search results; visibility fields match db.models.VisibilitySettings."""

    id: str
    display_name: Optional[str] = None
    open_to_work: bool
    open_to_contact: bool
    work_preferred_locations: list[str]
    work_preferred_salary_min: Optional[Decimal] = None
    work_preferred_salary_max: Optional[Decimal] = None
    experience_cards: list[ExperienceCardResponse]
    contact: Optional[ContactDetailsResponse] = None  # only if unlocked


class UnlockContactResponse(BaseModel):
    unlocked: bool
    contact: ContactDetailsResponse
