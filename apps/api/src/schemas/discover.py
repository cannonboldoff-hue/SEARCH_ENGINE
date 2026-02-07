from typing import Optional

from pydantic import BaseModel

from src.schemas.bio import BioResponse
from src.schemas.builder import CardFamilyResponse


class PersonListItem(BaseModel):
    """One person in the discover grid: name, location, top 5 parent experience summaries."""

    id: str
    display_name: Optional[str] = None
    current_location: Optional[str] = None
    experience_summaries: list[str] = []


class PersonListResponse(BaseModel):
    people: list[PersonListItem]


class PersonPublicProfileResponse(BaseModel):
    """Public profile for person detail page: full bio + all experience card families (parent → children)."""

    id: str
    display_name: Optional[str] = None
    bio: Optional[BioResponse] = None
    card_families: list[CardFamilyResponse] = []
