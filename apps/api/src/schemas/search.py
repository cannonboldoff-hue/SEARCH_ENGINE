from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, field_serializer

from src.schemas.contact import ContactDetailsResponse
from src.schemas.builder import ExperienceCardResponse


# ---------------------------------------------------------------------------
# Search.filters JSON shape (cleanup → extract → validate pipeline)
# ---------------------------------------------------------------------------

class SearchFiltersLocation(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None
    location_text: Optional[str] = None


class SearchFiltersTime(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_ongoing: Optional[bool] = None
    time_text: Optional[str] = None


class SearchFiltersMust(BaseModel):
    intents: list[str] = []
    domains: list[str] = []
    sub_domains: list[str] = []
    company_names: list[str] = []
    company_types: list[str] = []
    employment_types: list[str] = []
    seniority_levels: list[str] = []
    skills: list[str] = []
    tools: list[str] = []
    keywords: list[str] = []
    location: SearchFiltersLocation = SearchFiltersLocation()
    time: SearchFiltersTime = SearchFiltersTime()
    min_years_experience: Optional[int] = None
    # Recruiter offer budget: ₹/month from query (e.g. "₹20,000/month" → 20000). Interpreted as offer_salary_inr_per_year = value * 12 for matching.
    max_salary_inr_per_month: Optional[int] = None
    open_to_work_only: Optional[bool] = None


class SearchFiltersShould(BaseModel):
    intents: list[str] = []
    domains: list[str] = []
    skills: list[str] = []
    tools: list[str] = []
    keywords: list[str] = []


class SearchFiltersExclude(BaseModel):
    company_names: list[str] = []
    skills: list[str] = []
    tools: list[str] = []
    keywords: list[str] = []


class SearchFiltersPayload(BaseModel):
    """Parsed search filters stored in Search.filters (JSONB)."""
    query_original: str = ""
    query_cleaned: str = ""
    must: SearchFiltersMust = SearchFiltersMust()
    should: SearchFiltersShould = SearchFiltersShould()
    exclude: SearchFiltersExclude = SearchFiltersExclude()
    search_phrases: list[str] = []
    query_embedding_text: str = ""
    confidence_score: float = 0.0

    @classmethod
    def from_llm_dict(cls, data: dict[str, Any]) -> "SearchFiltersPayload":
        """Normalize LLM output to full schema (fill missing keys)."""
        must = data.get("must") or {}
        should = data.get("should") or {}
        exclude = data.get("exclude") or {}
        loc = must.get("location") or {}
        time_ = must.get("time") or {}
        return cls(
            query_original=data.get("query_original") or "",
            query_cleaned=data.get("query_cleaned") or "",
            must=SearchFiltersMust(
                intents=_list(must, "intents"),
                domains=_list(must, "domains"),
                sub_domains=_list(must, "sub_domains"),
                company_names=_list(must, "company_names"),
                company_types=_list(must, "company_types"),
                employment_types=_list(must, "employment_types"),
                seniority_levels=_list(must, "seniority_levels"),
                skills=_list(must, "skills"),
                tools=_list(must, "tools"),
                keywords=_list(must, "keywords"),
                location=SearchFiltersLocation(
                    city=loc.get("city"),
                    country=loc.get("country"),
                    location_text=loc.get("location_text"),
                ),
                time=SearchFiltersTime(
                    start_date=time_.get("start_date"),
                    end_date=time_.get("end_date"),
                    is_ongoing=time_.get("is_ongoing"),
                    time_text=time_.get("time_text"),
                ),
                min_years_experience=must.get("min_years_experience"),
                max_salary_inr_per_month=must.get("max_salary_inr_per_month"),
                open_to_work_only=must.get("open_to_work_only"),
            ),
            should=SearchFiltersShould(
                intents=_list(should, "intents"),
                domains=_list(should, "domains"),
                skills=_list(should, "skills"),
                tools=_list(should, "tools"),
                keywords=_list(should, "keywords"),
            ),
            exclude=SearchFiltersExclude(
                company_names=_list(exclude, "company_names"),
                skills=_list(exclude, "skills"),
                tools=_list(exclude, "tools"),
                keywords=_list(exclude, "keywords"),
            ),
            search_phrases=_list(data, "search_phrases"),
            query_embedding_text=data.get("query_embedding_text") or "",
            confidence_score=float(data.get("confidence_score") or 0.0),
        )


def _list(d: dict, key: str) -> list:
    v = d.get(key)
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else []


# ---------------------------------------------------------------------------
# Search.parsed_constraints_json shape (single extraction → execute on columns + person_profiles)
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
    salary_min: Optional[Decimal] = None  # recruiter min (₹/year), for display only
    salary_max: Optional[Decimal] = None  # recruiter offer budget ₹/year; candidates matched where work_preferred_salary_min <= salary_max (NULL = keep but downrank)


class PersonSearchResult(BaseModel):
    id: str
    name: Optional[str] = None  # display_name
    headline: Optional[str] = None
    bio: Optional[str] = None
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


class PersonProfileResponse(BaseModel):
    """Profile for search results; visibility fields from PersonProfile."""

    id: str
    display_name: Optional[str] = None
    open_to_work: bool
    open_to_contact: bool
    work_preferred_locations: list[str]
    work_preferred_salary_min: Optional[Decimal] = None  # minimum salary needed (₹/year)
    experience_cards: list[ExperienceCardResponse]
    contact: Optional[ContactDetailsResponse] = None  # only if unlocked

    @field_serializer("work_preferred_salary_min")
    def _ser_salary(self, v: Optional[Decimal]) -> Optional[float]:
        return _serialize_decimal(v)


class UnlockContactRequest(BaseModel):
    search_id: str


class UnlockContactResponse(BaseModel):
    unlocked: bool
    contact: ContactDetailsResponse
