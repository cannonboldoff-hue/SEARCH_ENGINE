from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, field_serializer, model_validator

from src.schemas.contact import ContactDetailsResponse
from src.schemas.builder import ExperienceCardResponse, CardFamilyResponse
from src.schemas.bio import BioResponse


def _list(d: dict, key: str) -> list:
    v = d.get(key)
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else []


# ---------------------------------------------------------------------------
# Search.parsed_constraints_json shape (single extraction -> execute on columns + person_profiles)
# ---------------------------------------------------------------------------

class ParsedConstraintsMust(BaseModel):
    company_norm: list[str] = []
    team_norm: list[str] = []
    intent_primary: list[str] = []
    domain: list[str] = []
    sub_domain: list[str] = []
    employment_type: list[str] = []
    seniority_level: list[str] = []
    location_text: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    is_current: Optional[bool] = None
    open_to_work_only: Optional[bool] = None
    offer_salary_inr_per_year: Optional[float] = None


class ParsedConstraintsShould(BaseModel):
    skills_or_tools: list[str] = []
    keywords: list[str] = []
    intent_secondary: list[str] = []


class ParsedConstraintsExclude(BaseModel):
    company_norm: list[str] = []
    keywords: list[str] = []


def _int_or_none(v: Any, min_val: int | None = None, max_val: int | None = None) -> Optional[int]:
    if v is None:
        return None
    try:
        n = int(v)
        if min_val is not None and n < min_val:
            return min_val
        if max_val is not None and n > max_val:
            return max_val
        return n
    except (TypeError, ValueError):
        return None


class ParsedConstraintsPayload(BaseModel):
    """Single extraction output stored in Search.parsed_constraints_json. Executed against experience_cards + person_profiles."""
    query_original: str = ""
    query_cleaned: str = ""
    must: ParsedConstraintsMust = ParsedConstraintsMust()
    should: ParsedConstraintsShould = ParsedConstraintsShould()
    exclude: ParsedConstraintsExclude = ParsedConstraintsExclude()
    search_phrases: list[str] = []
    query_embedding_text: str = ""
    confidence_score: float = 0.0
    num_cards: Optional[int] = None  # number of result cards to return (1-24); null = use default 6

    @classmethod
    def from_llm_dict(cls, data: dict[str, Any]) -> "ParsedConstraintsPayload":
        """Normalize LLM output to full schema (fill missing keys)."""
        must = data.get("must") or {}
        should = data.get("should") or {}
        exclude = data.get("exclude") or {}
        return cls(
            query_original=data.get("query_original") or "",
            query_cleaned=data.get("query_cleaned") or "",
            must=ParsedConstraintsMust(
                company_norm=_list(must, "company_norm"),
                team_norm=_list(must, "team_norm"),
                intent_primary=_list(must, "intent_primary"),
                domain=_list(must, "domain"),
                sub_domain=_list(must, "sub_domain"),
                employment_type=_list(must, "employment_type"),
                seniority_level=_list(must, "seniority_level"),
                location_text=must.get("location_text"),
                city=must.get("city"),
                country=must.get("country"),
                time_start=must.get("time_start"),
                time_end=must.get("time_end"),
                is_current=must.get("is_current"),
                open_to_work_only=must.get("open_to_work_only"),
                offer_salary_inr_per_year=_float_or_none(must.get("offer_salary_inr_per_year")),
            ),
            should=ParsedConstraintsShould(
                skills_or_tools=_list(should, "skills_or_tools"),
                keywords=_list(should, "keywords"),
                intent_secondary=_list(should, "intent_secondary"),
            ),
            exclude=ParsedConstraintsExclude(
                company_norm=_list(exclude, "company_norm"),
                keywords=_list(exclude, "keywords"),
            ),
            search_phrases=_list(data, "search_phrases"),
            query_embedding_text=data.get("query_embedding_text") or "",
            confidence_score=float(data.get("confidence_score") or 0.0),
            num_cards=_int_or_none(data.get("num_cards"), min_val=1, max_val=24),
        )


def _float_or_none(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _serialize_decimal(v: Optional[Decimal]) -> Optional[float]:
    """Serialize Decimal for JSON (idempotency storage, API response)."""
    return float(v) if v is not None else None


class SearchRequest(BaseModel):
    query: str
    open_to_work_only: Optional[bool] = None
    preferred_locations: Optional[list[str]] = None  # preferred_locations_any when open_to_work_only
    salary_min: Optional[Decimal] = None  # recruiter min (INR/year), for display only
    salary_max: Optional[Decimal] = None  # recruiter offer budget INR/year; candidates matched where work_preferred_salary_min <= salary_max (NULL = keep but downrank)
    num_cards: Optional[int] = None  # result count (1-24); if set, overrides query parsing; else derived from query or default 6

    @model_validator(mode="after")
    def _validate_salary_bounds(self) -> "SearchRequest":
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError("salary_min must be <= salary_max")
        return self

    @model_validator(mode="after")
    def _validate_num_cards(self) -> "SearchRequest":
        if self.num_cards is not None and (self.num_cards < 1 or self.num_cards > 1000):
            raise ValueError("num_cards must be between 1 and 24")
        return self

class PersonSearchResult(BaseModel):
    id: str
    name: Optional[str] = None  # display_name
    headline: Optional[str] = None
    bio: Optional[str] = None
    similarity_percent: Optional[int] = None
    why_matched: list[str] = []
    open_to_work: bool
    open_to_contact: bool
    work_preferred_locations: list[str] = []
    work_preferred_salary_min: Optional[Decimal] = None
    matched_cards: list[ExperienceCardResponse] = []  # 1-3 best matching cards

    @field_serializer("work_preferred_salary_min")
    def _ser_salary(self, v: Optional[Decimal]) -> Optional[float]:
        return _serialize_decimal(v)


class SearchResponse(BaseModel):
    search_id: str
    people: list[PersonSearchResult]
    num_cards: Optional[int] = None  # limit applied for this search (1-24); credits charged = num_cards when non-empty


class PersonProfileResponse(BaseModel):
    """Profile for search results; visibility fields from PersonProfile. Includes full card families and bio like public profile."""

    id: str
    display_name: Optional[str] = None
    open_to_work: bool
    open_to_contact: bool
    work_preferred_locations: list[str]
    work_preferred_salary_min: Optional[Decimal] = None  # minimum salary needed (INR/year)
    experience_cards: list[ExperienceCardResponse]  # kept for backward compatibility
    card_families: list[CardFamilyResponse] = []  # parent + children for full experience view
    bio: Optional[BioResponse] = None
    contact: Optional[ContactDetailsResponse] = None  # only if unlocked

    @field_serializer("work_preferred_salary_min")
    def _ser_salary(self, v: Optional[Decimal]) -> Optional[float]:
        return _serialize_decimal(v)


class SavedSearchItem(BaseModel):
    id: str
    query_text: str
    created_at: str
    expires_at: str
    expired: bool
    result_count: int


class SavedSearchesResponse(BaseModel):
    searches: list[SavedSearchItem]


class UnlockContactRequest(BaseModel):
    search_id: Optional[str] = None


class UnlockContactResponse(BaseModel):
    unlocked: bool
    contact: ContactDetailsResponse
