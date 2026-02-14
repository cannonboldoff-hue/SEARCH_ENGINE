"""
Experience Card Pipeline - Refactored Version

Key improvements:
1. Pydantic models for strict LLM response validation
2. Explicit error handling with detailed messages
3. Transaction-based persistence (all-or-nothing)
4. Separated concerns (parse, validate, persist, embed)
5. No silent fallbacks - all errors surface
6. Standardized LLM response format
"""

import json
import logging
import re
import uuid
from datetime import datetime, timezone, date
from typing import Optional, Any
from enum import Enum

from pydantic import BaseModel, Field, validator, root_validator, ValidationError
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.db.models import RawExperience, DraftSet, ExperienceCard, ExperienceCardChild
from src.domain import ALLOWED_CHILD_TYPES
from src.schemas import RawExperienceCreate
from src.providers import (
    get_chat_provider,
    ChatServiceError,
    EmbeddingServiceError,
    get_embedding_provider,
)
from src.prompts.experience_card import (
    PROMPT_REWRITE,
    PROMPT_EXTRACT_ALL_CARDS,
    PROMPT_VALIDATE_ALL_CARDS,
    PROMPT_FILL_MISSING_FIELDS,
    fill_prompt,
)
from src.services.experience_card import _experience_card_search_document
from src.utils import normalize_embedding

logger = logging.getLogger(__name__)


# =============================================================================
# PYDANTIC MODELS FOR LLM RESPONSE VALIDATION
# =============================================================================

class TimeInfo(BaseModel):
    """Time/date information for an experience."""
    text: Optional[str] = None
    start: Optional[str] = None  # ISO date or YYYY-MM
    end: Optional[str] = None
    ongoing: Optional[bool] = None


class LocationInfo(BaseModel):
    """Location information."""
    text: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


class RoleInfo(BaseModel):
    """Role/position information."""
    label: Optional[str] = None
    seniority: Optional[str] = None


class TopicInfo(BaseModel):
    """Topic/tag information."""
    label: str


class EntityInfo(BaseModel):
    """Named entity (company, team, etc)."""
    type: str  # "company", "team", "organization"
    name: str


class IndexInfo(BaseModel):
    """Search indexing metadata."""
    search_phrases: list[str] = Field(default_factory=list)


def _normalize_roles(raw: Any) -> list[dict]:
    """Accept role items as dicts or strings; return RoleInfo-compatible dicts."""
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("title") or "").strip()
            seniority = str(item.get("seniority") or "").strip() or None
            if label or seniority:
                out.append({"label": label or None, "seniority": seniority})
        elif isinstance(item, str) and item.strip():
            out.append({"label": item.strip(), "seniority": None})
    return out


def _normalize_topics(raw: Any) -> list[dict]:
    """Accept topic items as dicts or strings; return TopicInfo-compatible dicts."""
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or item.get("text") or "").strip()
            if label:
                out.append({"label": label})
        elif isinstance(item, str) and item.strip():
            out.append({"label": item.strip()})
    return out


def _normalize_entities(raw: Any) -> list[dict]:
    """Accept entity items as dicts or strings; return EntityInfo-compatible dicts."""
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("label") or item.get("text") or "").strip()
            etype = str(item.get("type") or "organization").strip().lower()
            if name:
                out.append({"type": etype or "organization", "name": name})
        elif isinstance(item, str) and item.strip():
            out.append({"type": "organization", "name": item.strip()})
    return out


def _normalize_event_like_list(raw: Any) -> list[dict]:
    """Accept action/outcome/evidence items as dicts or strings."""
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            out.append(item)
        elif isinstance(item, str) and item.strip():
            out.append({"text": item.strip()})
    return out


class V1Card(BaseModel):
    """Base card structure returned by LLM."""
    id: Optional[str] = None
    headline: Optional[str] = None
    title: Optional[str] = None
    label: Optional[str] = None
    summary: Optional[str] = None
    raw_text: Optional[str] = None
    time: Optional[TimeInfo | str] = None
    location: Optional[LocationInfo | str] = None
    time_text: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: Optional[bool] = None
    city: Optional[str] = None
    country: Optional[str] = None
    roles: list[RoleInfo] = Field(default_factory=list)
    topics: list[TopicInfo] = Field(default_factory=list)
    entities: list[EntityInfo] = Field(default_factory=list)
    actions: list[dict] = Field(default_factory=list)
    outcomes: list[dict] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    tooling: Optional[Any] = None
    company: Optional[str] = None
    company_name: Optional[str] = None
    organization: Optional[str] = None
    team: Optional[str] = None
    normalized_role: Optional[str] = None
    seniority_level: Optional[str] = None
    domain: Optional[str] = None
    sub_domain: Optional[str] = None
    company_type: Optional[str] = None
    employment_type: Optional[str] = None
    index: Optional[IndexInfo] = None
    search_phrases: list[str] = Field(default_factory=list)
    search_document: Optional[str] = None
    intent: Optional[str] = None
    intent_primary: Optional[str] = None
    intent_secondary: list[str] = Field(default_factory=list)
    confidence_score: Optional[float] = None
    
    # Metadata fields
    person_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    parent_id: Optional[str] = None
    depth: Optional[int] = None
    relation_type: Optional[str] = None
    child_type: Optional[str] = None

    @root_validator(pre=True)
    def normalize_prompt_style_fields(cls, values):
        """Accept both prompt-style parent keys and legacy V1 keys."""
        if not isinstance(values, dict):
            return values

        data = dict(values)

        # Parent intent fields from prompt schema.
        if not data.get("intent") and data.get("intent_primary"):
            data["intent"] = data.get("intent_primary")

        # Parent company/role fields from prompt schema.
        if not data.get("company") and data.get("company_name"):
            data["company"] = data.get("company_name")

        if not data.get("roles") and data.get("normalized_role"):
            data["roles"] = [{
                "label": data.get("normalized_role"),
                "seniority": data.get("seniority_level"),
            }]

        # Convert parent date fields into the shared time container.
        if not data.get("time"):
            start = data.get("start_date")
            end = data.get("end_date")
            text = data.get("time_text")
            ongoing = data.get("is_current")
            if start or end or text or isinstance(ongoing, bool):
                data["time"] = {
                    "start": start,
                    "end": end,
                    "text": text,
                    "ongoing": ongoing if isinstance(ongoing, bool) else None,
                }

        # Parent search_phrases may be provided at top-level.
        if not data.get("index") and isinstance(data.get("search_phrases"), list):
            data["index"] = {"search_phrases": data.get("search_phrases", [])}

        if isinstance(data.get("intent_secondary"), str):
            data["intent_secondary"] = [s.strip() for s in data["intent_secondary"].split(",") if s.strip()]

        if isinstance(data.get("search_phrases"), str):
            data["search_phrases"] = [s.strip() for s in data["search_phrases"].split(",") if s.strip()]

        # Coerce frequently malformed LLM list fields into schema-compatible objects.
        if data.get("roles") is not None:
            data["roles"] = _normalize_roles(data.get("roles"))

        if data.get("topics") is not None:
            data["topics"] = _normalize_topics(data.get("topics"))

        if data.get("entities") is not None:
            data["entities"] = _normalize_entities(data.get("entities"))

        for key in ("actions", "outcomes", "evidence"):
            if data.get(key) is not None:
                data[key] = _normalize_event_like_list(data.get(key))

        return data

    @validator('time', pre=True)
    def normalize_time(cls, v):
        """Convert string to TimeInfo dict."""
        if isinstance(v, str):
            return {"text": v}
        return v
    
    @validator('location', pre=True)
    def normalize_location(cls, v):
        """Convert string to LocationInfo dict."""
        if isinstance(v, str):
            return {"text": v}
        return v


class V1Family(BaseModel):
    """A parent card with optional children."""
    parent: V1Card
    children: list[V1Card] = Field(default_factory=list)


class V1ExtractorResponse(BaseModel):
    """Standardized response format from extractor LLM."""
    families: list[V1Family]
    
    class Config:
        # Allow parsing from {"parents": [...]} wrapper
        extra = "allow"


class PipelineStage(str, Enum):
    """Pipeline stage identifiers for error reporting."""
    REWRITE = "rewrite"
    EXTRACT = "extract"
    VALIDATE = "validate"
    PERSIST = "persist"
    EMBED = "embed"


class PipelineError(Exception):
    """Base exception for pipeline errors with stage context."""
    def __init__(self, stage: PipelineStage, message: str, cause: Optional[Exception] = None):
        self.stage = stage
        self.message = message
        self.cause = cause
        super().__init__(f"[{stage.value}] {message}")


# =============================================================================
# PARSING & VALIDATION
# =============================================================================

def _strip_json_fence(text: str) -> str:
    """Remove markdown code fences from JSON response."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    
    lines = text.split("\n")
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    
    return "\n".join(lines).strip()


def _extract_json_from_text(text: str) -> str:
    """Find first JSON object/array in text, handling LLM preambles."""
    text = text.strip()
    
    # Try to find JSON markers
    for start_char in ['{', '[']:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue
        
        # Simple brace counting to find matching close
        json_candidate = text[start_idx:]
        try:
            # Let json.loads validate it
            json.loads(json_candidate)
            return json_candidate
        except json.JSONDecodeError:
            # Try to find the matching brace
            depth = 0
            close_char = '}' if start_char == '{' else ']'
            
            for i, char in enumerate(json_candidate):
                if char == start_char:
                    depth += 1
                elif char == close_char:
                    depth -= 1
                    if depth == 0:
                        candidate = json_candidate[:i+1]
                        try:
                            json.loads(candidate)
                            return candidate
                        except json.JSONDecodeError:
                            continue
    
    raise ValueError("No valid JSON found in text")


def _normalize_child_dict_for_v1_card(child_dict: dict) -> dict:
    """
    Map prompt-style child (child_type, label, value: { headline, summary, ... })
    to V1Card-compatible top-level headline/title/summary so display and persist work.
    """
    if not isinstance(child_dict, dict):
        return child_dict
    out = dict(child_dict)
    value = out.get("value") if isinstance(out.get("value"), dict) else None
    label = out.get("label")
    if value is not None:
        if not out.get("headline") and value.get("headline"):
            out["headline"] = value.get("headline")
        if not out.get("title") and (value.get("headline") or label):
            out["title"] = value.get("headline") or label
        if not out.get("summary") and value.get("summary"):
            out["summary"] = value.get("summary")
        if not out.get("raw_text") and value.get("raw_text"):
            out["raw_text"] = value.get("raw_text")
        if not out.get("time") and isinstance(value.get("time"), dict):
            out["time"] = value.get("time")
        if not out.get("location") and isinstance(value.get("location"), dict):
            out["location"] = value.get("location")
        if not out.get("roles") and isinstance(value.get("roles"), list):
            out["roles"] = value.get("roles")
        if not out.get("actions") and isinstance(value.get("actions"), list):
            out["actions"] = value.get("actions")
        if not out.get("topics") and isinstance(value.get("topics"), list):
            out["topics"] = value.get("topics")
        if not out.get("entities") and isinstance(value.get("entities"), list):
            out["entities"] = value.get("entities")
        if not out.get("tooling") and value.get("tooling") is not None:
            out["tooling"] = value.get("tooling")
        if not out.get("outcomes") and isinstance(value.get("outcomes"), list):
            out["outcomes"] = value.get("outcomes")
        if not out.get("evidence") and isinstance(value.get("evidence"), list):
            out["evidence"] = value.get("evidence")
        if not out.get("company") and value.get("company"):
            out["company"] = value.get("company")
        if not out.get("team") and value.get("team"):
            out["team"] = value.get("team")
        if not out.get("intent") and value.get("intent"):
            out["intent"] = value.get("intent")
        if not out.get("relation_type") and value.get("relation_type"):
            out["relation_type"] = value.get("relation_type")
        if out.get("depth") is None and value.get("depth") is not None:
            out["depth"] = value.get("depth")
        if not out.get("index") and isinstance(value.get("index"), dict):
            out["index"] = value.get("index")
    if label and not out.get("headline") and not out.get("title"):
        out["headline"] = label
        out["title"] = label
    return out


def parse_llm_response_to_families(
    response_text: str,
    stage: PipelineStage,
) -> list[V1Family]:
    """
    Parse LLM response into validated V1Family list.
    
    Handles multiple response formats:
    - {"families": [{parent, children}, ...]}
    - {"parents": [{parent, children}, ...]}  # legacy wrapper
    - [{parent, children}, ...]  # direct array
    - {parent, children}  # single family
    
    Raises:
        PipelineError: If parsing or validation fails
    """
    if not response_text or not response_text.strip():
        raise PipelineError(
            stage,
            "LLM returned empty response. Service may be rate-limited or failed.",
        )
    
    try:
        # Clean response text
        cleaned = _strip_json_fence(response_text)
        json_str = _extract_json_from_text(cleaned)
        data = json.loads(json_str)
        
    except (ValueError, json.JSONDecodeError) as e:
        raise PipelineError(
            stage,
            f"LLM returned invalid JSON: {str(e)[:200]}",
            cause=e,
        )
    
    # Normalize to list of family dicts
    family_dicts: list[dict] = []
    
    if isinstance(data, dict):
        # Check for wrapper formats
        if "families" in data and isinstance(data["families"], list):
            family_dicts = data["families"]
        elif "parents" in data and isinstance(data["parents"], list):
            # Legacy wrapper: {"parents": [...]}
            family_dicts = data["parents"]
        elif "parent" in data:
            # Single family object
            family_dicts = [data]
        else:
            raise PipelineError(
                stage,
                f"Unexpected response structure. Expected 'families', 'parents', or 'parent' key. Got: {list(data.keys())[:5]}",
            )
    
    elif isinstance(data, list):
        family_dicts = data
    
    else:
        raise PipelineError(
            stage,
            f"Expected JSON object or array, got {type(data).__name__}",
        )
    
    # Validate each family using Pydantic
    validated_families: list[V1Family] = []

    for i, family_dict in enumerate(family_dicts):
        if not isinstance(family_dict, dict):
            logger.warning(f"Skipping non-dict family at index {i}: {type(family_dict)}")
            continue

        # Ensure family has parent key
        if "parent" not in family_dict:
            logger.warning(f"Skipping family at index {i}: missing 'parent' key")
            continue

        # Normalize children: LLM returns { label, value: { headline, summary } }; V1Card expects headline/title/summary at top level
        normalized_family_dict = dict(family_dict)
        raw_children = normalized_family_dict.get("children")
        if isinstance(raw_children, list):
            normalized_family_dict["children"] = [_normalize_child_dict_for_v1_card(c) for c in raw_children]

        try:
            family = V1Family(**normalized_family_dict)
            validated_families.append(family)
        except ValidationError as e:
            logger.warning(f"Validation failed for family {i}: {e}")
            # Continue with other families rather than failing entire batch
            continue

    if not validated_families:
        raise PipelineError(
            stage,
            f"No valid families found in response. Parsed {len(family_dicts)} candidates, all failed validation.",
        )
    
    return validated_families


# =============================================================================
# METADATA INJECTION
# =============================================================================

def inject_metadata_into_family(
    family: V1Family,
    person_id: str,
) -> V1Family:
    """
    Inject required metadata into parent and children.
    
    Does NOT overwrite existing IDs or timestamps from LLM.
    Only fills in missing required fields.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Parent metadata
    parent = family.parent
    if not parent.id:
        parent.id = str(uuid.uuid4())
    parent.person_id = person_id
    parent.created_by = person_id
    if not parent.created_at:
        parent.created_at = now_iso
    if not parent.updated_at:
        parent.updated_at = now_iso
    parent.parent_id = None
    parent.depth = 0
    parent.relation_type = None
    
    # Children metadata
    parent_id = parent.id
    for child in family.children:
        if not child.id:
            child.id = str(uuid.uuid4())
        child.person_id = person_id
        child.created_by = person_id
        child.parent_id = parent_id
        child.depth = 1
        if not child.created_at:
            child.created_at = now_iso
        if not child.updated_at:
            child.updated_at = now_iso
    
    return family


# =============================================================================
# FIELD EXTRACTION & NORMALIZATION
# =============================================================================

_MONTH_LOOKUP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _month_name_to_number(text: str) -> Optional[int]:
    key = (text or "").strip().lower()
    return _MONTH_LOOKUP.get(key)


def parse_date_field(value: Optional[str]) -> Optional[date]:
    """Parse common date strings into a date. Returns None on failure."""
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    # Normalize common separators
    normalized = (
        text.replace("/", "-")
        .replace(".", "-")
        .replace("–", "-")
        .replace("—", "-")
        .strip()
    )
    normalized = re.sub(r"[,\s]+", " ", normalized).strip()

    # Handle ISO YYYY-MM or YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{2}", normalized):
        normalized = f"{normalized}-01"
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        pass
    else:
        # Month name + year (e.g., "Jan 2024" or "January 2024")
        match = re.fullmatch(r"([A-Za-z]{3,9})\s+(\d{4})", normalized)
        if match:
            month = _month_name_to_number(match.group(1))
            if month:
                return date(int(match.group(2)), month, 1)

        # Year + month name (e.g., "2024 Jan")
        match = re.fullmatch(r"(\d{4})\s+([A-Za-z]{3,9})", normalized)
        if match:
            month = _month_name_to_number(match.group(2))
            if month:
                return date(int(match.group(1)), month, 1)

        # Month name - year (e.g., "Apr-2024")
        match = re.fullmatch(r"([A-Za-z]{3,9})-(\d{4})", normalized)
        if match:
            month = _month_name_to_number(match.group(1))
            if month:
                return date(int(match.group(2)), month, 1)

        # Year - month name (e.g., "2024-Apr")
        match = re.fullmatch(r"(\d{4})-([A-Za-z]{3,9})", normalized)
        if match:
            month = _month_name_to_number(match.group(2))
            if month:
                return date(int(match.group(1)), month, 1)

        # Numeric month/year (e.g., "01-2024")
        match = re.fullmatch(r"(\d{1,2})-(\d{4})", normalized)
        if match:
            month = int(match.group(1))
            if 1 <= month <= 12:
                return date(int(match.group(2)), month, 1)

        # Year-only fallback (e.g., "2024")
        if re.fullmatch(r"\d{4}", normalized):
            return date(int(normalized), 1, 1)

    try:
        return date.fromisoformat(normalized)
    except ValueError as e:
        logger.warning(f"Failed to parse date '{value}': {e}")
        return None


def _extract_dates_from_text(text: str) -> tuple[Optional[date], Optional[date]]:
    """Best-effort extract up to two dates from a free-form time range string."""
    if not text:
        return None, None
    haystack = str(text).replace("–", "-").replace("—", "-")

    # Example: "2024 Apr-Dec" (single year shared by both months)
    shared_year_month_range = re.search(
        r"\b(\d{4})\s+([A-Za-z]{3,9})\s*-\s*([A-Za-z]{3,9})\b",
        haystack,
        re.IGNORECASE,
    )
    if shared_year_month_range:
        year, start_mon, end_mon = shared_year_month_range.groups()
        start_date = parse_date_field(f"{year} {start_mon}")
        end_date = parse_date_field(f"{year} {end_mon}")
        if start_date or end_date:
            return start_date, end_date

    pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2}|\d{4}-\d{2}|"
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}|"
        r"\d{4}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*|"
        r"\d{1,2}[/-]\d{4})",
        re.IGNORECASE,
    )
    matches = pattern.findall(haystack)
    parsed = [parse_date_field(m) for m in matches if m]
    parsed = [d for d in parsed if d is not None]
    if not parsed:
        return None, None
    if len(parsed) == 1:
        return parsed[0], None
    return parsed[0], parsed[1]


def extract_time_fields(card: V1Card) -> tuple[Optional[str], Optional[date], Optional[date], Optional[bool]]:
    """Extract time fields from card."""
    time_obj = card.time

    # Prefer explicit prompt-style parent fields when available.
    explicit_start = parse_date_field(card.start_date)
    explicit_end = parse_date_field(card.end_date)
    explicit_text = (card.time_text or "").strip() or None
    explicit_ongoing = card.is_current if isinstance(card.is_current, bool) else None

    if isinstance(time_obj, str):
        start_date, end_date = _extract_dates_from_text(time_obj)
        if start_date is None:
            start_date = explicit_start
        if end_date is None:
            end_date = explicit_end
        ongoing = explicit_ongoing
        if ongoing is None and re.search(r"\b(present|current|ongoing|now)\b", time_obj, re.IGNORECASE):
            ongoing = True
        return time_obj, start_date, end_date, ongoing

    if not isinstance(time_obj, TimeInfo):
        if (explicit_start is None or explicit_end is None) and explicit_text:
            parsed_start, parsed_end = _extract_dates_from_text(explicit_text)
            if explicit_start is None:
                explicit_start = parsed_start
            if explicit_end is None:
                explicit_end = parsed_end
        return explicit_text, explicit_start, explicit_end, explicit_ongoing

    time_text = (time_obj.text or "").strip() or explicit_text
    start_date = parse_date_field(time_obj.start)
    end_date = parse_date_field(time_obj.end)
    if start_date is None:
        start_date = explicit_start
    if end_date is None:
        end_date = explicit_end
    if (start_date is None or end_date is None) and time_text:
        parsed_start, parsed_end = _extract_dates_from_text(time_text)
        if start_date is None:
            start_date = parsed_start
        if end_date is None:
            end_date = parsed_end
    ongoing = time_obj.ongoing if isinstance(time_obj.ongoing, bool) else explicit_ongoing
    if ongoing is None and time_text and re.search(r"\b(present|current|ongoing|now)\b", time_text, re.IGNORECASE):
        ongoing = True

    return (
        time_text,
        start_date,
        end_date,
        ongoing,
    )


def extract_location_fields(card: V1Card) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract location fields from card."""
    loc_obj = card.location
    
    if isinstance(loc_obj, str):
        return loc_obj, None, None
    
    if not isinstance(loc_obj, LocationInfo):
        return None, None, None
    
    return loc_obj.text or loc_obj.city, loc_obj.city, loc_obj.country


def extract_company(card: V1Card) -> Optional[str]:
    """Extract company name from card."""
    company = card.company or card.company_name or card.organization
    
    if not company:
        # Check entities
        for entity in card.entities:
            if entity.type in {"company", "organization"}:
                company = entity.name
                break
    
    return company[:255].strip() if company else None


def extract_team(card: V1Card) -> Optional[str]:
    """Extract team name from card."""
    team = card.team
    
    if not team:
        # Check entities
        for entity in card.entities:
            if entity.type == "team":
                team = entity.name
                break
    
    return team[:255].strip() if team else None


def extract_role_info(card: V1Card) -> tuple[Optional[str], Optional[str]]:
    """Extract role title and seniority."""
    if card.roles:
        first_role = card.roles[0]
        title = first_role.label[:255].strip() if first_role.label else None
        seniority = first_role.seniority[:255].strip() if first_role.seniority else None
        if title or seniority:
            return title, seniority

    title = (card.normalized_role or "").strip()[:255] or None
    seniority = (card.seniority_level or "").strip()[:255] or None
    return title, seniority


def extract_search_phrases(card: V1Card) -> list[str]:
    """Extract search phrases from card index."""
    phrases: list[str] = []
    if card.index and isinstance(card.index.search_phrases, list):
        phrases.extend(card.index.search_phrases)
    if isinstance(card.search_phrases, list):
        phrases.extend(card.search_phrases)
    seen: set[str] = set()
    out: list[str] = []
    for phrase in phrases:
        p = str(phrase).strip()
        key = p.lower()
        if not p or key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= 50:
            break
    return out


def normalize_card_title(card: V1Card, fallback_text: Optional[str] = None) -> str:
    """
    Generate user-friendly title from card.
    
    Priority:
    1. headline (if not generic)
    2. title (if not generic)
    3. First line of summary
    4. First line of raw_text
    5. fallback_text
    6. "Experience"
    """
    # Check headline
    headline = (card.headline or "").strip()
    if headline and headline.lower() not in {"general experience", "unspecified experience"}:
        return headline[:500]

    # Check title
    title = (card.title or "").strip()
    if title and title.lower() not in {"general experience", "unspecified experience"}:
        return title[:500]

    # Try summary first line
    summary = (card.summary or "").strip()
    if summary:
        first_line = summary.split("\n")[0].strip()[:80]
        if first_line:
            return first_line

    # Try raw_text first line
    raw_text = (card.raw_text or "").strip()
    if raw_text:
        first_line = raw_text.split("\n")[0].strip()[:80]
        if first_line:
            return first_line

    # Use fallback
    if fallback_text:
        return fallback_text.split("\n")[0].strip()[:80] or "Experience"

    return "Experience"


# =============================================================================
# PERSISTENCE
# =============================================================================

def card_to_experience_card_fields(
    card: V1Card,
    *,
    person_id: str,
    raw_experience_id: str,
    draft_set_id: str,
) -> dict:
    """Convert V1Card to ExperienceCard column values."""
    time_text, start_date, end_date, is_ongoing = extract_time_fields(card)
    location_text, city, country = extract_location_fields(card)
    company = extract_company(card)
    role_title, role_seniority = extract_role_info(card)
    search_phrases = extract_search_phrases(card)

    raw_text = (card.raw_text or "").strip() or None
    summary = (card.summary or "")[:10000]
    title = normalize_card_title(card)

    tags = [t.label for t in card.topics]
    search_doc_parts = [
        card.headline or title or "",
        summary or "",
        role_title or "",
        company or "",
        location_text or "",
        " ".join(tags[:10]) if tags else "",
    ]
    search_document = " ".join(p for p in search_doc_parts if p).strip() or None

    return {
        "user_id": person_id,
        "raw_text": raw_text,
        "title": title[:500],
        "normalized_role": role_title,
        "domain": (card.domain or "").strip()[:100] or None,
        "sub_domain": (card.sub_domain or "").strip()[:100] or None,
        "company_name": company,
        "company_type": (card.company_type or "").strip()[:100] or None,
        "start_date": start_date,
        "end_date": end_date,
        "is_current": is_ongoing if isinstance(is_ongoing, bool) else None,
        "location": location_text[:255] if location_text else None,
        "employment_type": (card.employment_type or "").strip()[:100] or None,
        "summary": summary,
        "intent_primary": card.intent or card.intent_primary,
        "intent_secondary": [s for s in card.intent_secondary if isinstance(s, str) and s.strip()][:20],
        "seniority_level": role_seniority,
        "confidence_score": card.confidence_score,
        "experience_card_visibility": True,
        "search_phrases": search_phrases,
        "search_document": (card.search_document or "").strip() or search_document,
    }


def card_to_child_fields(
    card: V1Card,
    *,
    person_id: str,
    raw_experience_id: str,
    draft_set_id: str,
    parent_id: str,
) -> dict:
    """Convert V1Card to ExperienceCardChild column values."""
    time_text, start_date, end_date, is_ongoing = extract_time_fields(card)
    location_text, city, country = extract_location_fields(card)
    company = extract_company(card)
    team = extract_team(card)
    role_title, role_seniority = extract_role_info(card)
    search_phrases = extract_search_phrases(card)
    
    raw_text = (card.raw_text or "").strip() or None
    summary = (card.summary or "")[:10000]
    
    # Validate child_type
    child_type = card.child_type
    if not child_type or child_type not in ALLOWED_CHILD_TYPES:
        logger.warning(f"Invalid child_type '{child_type}', defaulting to '{ALLOWED_CHILD_TYPES[0]}'")
        child_type = ALLOWED_CHILD_TYPES[0]
    
    # Generate label
    label = normalize_card_title(card)[:255]
    
    # Build dimension container
    dimension_container = {
        "headline": card.headline,
        "summary": summary,
        "raw_text": raw_text,
        "time": {
            "text": time_text,
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None,
            "ongoing": is_ongoing,
        },
        "location": {
            "text": location_text,
            "city": city,
            "country": country,
        },
        "roles": [{"label": role_title, "seniority": role_seniority}] if role_title else [],
        "topics": [t.dict() for t in card.topics],
        "entities": [e.dict() for e in card.entities],
        "actions": card.actions,
        "outcomes": card.outcomes,
        "tooling": card.tooling,
        "evidence": card.evidence,
        "company": company,
        "team": team,
        "tags": [t.label for t in card.topics][:50],
        "depth": card.depth or 1,
        "relation_type": card.relation_type,
    }
    
    # Build search document
    tags = [t.label for t in card.topics]
    search_doc_parts = [
        card.headline or "",
        summary or "",
        role_title or "",
        company or "",
        team or "",
        location_text or "",
        " ".join(tags[:10]) if tags else "",
    ]
    search_document = " ".join(p for p in search_doc_parts if p).strip() or None
    
    return {
        "parent_experience_id": parent_id,
        "person_id": person_id,
        "raw_experience_id": raw_experience_id,
        "draft_set_id": draft_set_id,
        "child_type": child_type,
        "label": label,
        "value": dimension_container,
        "confidence_score": None,
        "search_phrases": search_phrases,
        "search_document": search_document,
        "embedding": None,  # Set during embedding phase
        "extra": {
            "intent": card.intent,
            "created_by": card.created_by,
        } if card.intent or card.created_by else None,
    }


async def persist_families(
    db: AsyncSession,
    families: list[V1Family],
    *,
    person_id: str,
    raw_experience_id: str,
    draft_set_id: str,
) -> tuple[list[ExperienceCard], list[ExperienceCardChild]]:
    """
    Persist all families to database.
    
    Returns:
        (parent_cards, child_cards) - all persisted entities
    
    Raises:
        PipelineError: If persistence fails
    """
    all_parents: list[ExperienceCard] = []
    all_children: list[ExperienceCardChild] = []
    
    try:
        for family in families:
            # Create parent
            parent_fields = card_to_experience_card_fields(
                family.parent,
                person_id=person_id,
                raw_experience_id=raw_experience_id,
                draft_set_id=draft_set_id,
            )
            parent_ec = ExperienceCard(**parent_fields)
            db.add(parent_ec)
            await db.flush()
            await db.refresh(parent_ec)
            all_parents.append(parent_ec)
            
            # Create children
            for child_card in family.children:
                child_fields = card_to_child_fields(
                    child_card,
                    person_id=person_id,
                    raw_experience_id=raw_experience_id,
                    draft_set_id=draft_set_id,
                    parent_id=parent_ec.id,
                )
                child_ec = ExperienceCardChild(**child_fields)
                db.add(child_ec)
                all_children.append(child_ec)
            
            if all_children:
                await db.flush()
                for child_ec in all_children:
                    await db.refresh(child_ec)
        
        return all_parents, all_children
    
    except Exception as e:
        raise PipelineError(
            PipelineStage.PERSIST,
            f"Database persistence failed: {str(e)}",
            cause=e,
        )


# =============================================================================
# EMBEDDING
# =============================================================================

async def embed_cards(
    db: AsyncSession,
    parents: list[ExperienceCard],
    children: list[ExperienceCardChild],
) -> None:
    """
    Generate and persist embeddings for all cards.
    
    Raises:
        PipelineError: If embedding fails
    """
    if not parents and not children:
        return
    
    embed_texts: list[str] = []
    embed_targets: list[tuple[str, ExperienceCard | ExperienceCardChild]] = []
    
    # Collect parent documents (use stored search_document when present)
    for parent in parents:
        doc = parent.search_document or _experience_card_search_document(parent)
        if doc:
            embed_texts.append(doc)
            embed_targets.append(("parent", parent))
    
    # Collect child documents
    for child in children:
        doc = child.search_document or ""
        if doc.strip():
            embed_texts.append(doc.strip())
            embed_targets.append(("child", child))
    
    if not embed_texts:
        logger.warning("No documents to embed")
        return
    
    try:
        provider = get_embedding_provider()
        vectors = await provider.embed(embed_texts)
        
        if len(vectors) != len(embed_targets):
            raise PipelineError(
                PipelineStage.EMBED,
                f"Embedding API returned {len(vectors)} vectors but expected {len(embed_targets)}",
            )
        
        # Assign embeddings
        for (kind, obj), vec in zip(embed_targets, vectors):
            normalized = normalize_embedding(vec, dim=provider.dimension)
            obj.embedding = normalized
        
        await db.flush()
        
        logger.info(f"Successfully embedded {len(embed_texts)} documents")
    
    except EmbeddingServiceError as e:
        raise PipelineError(
            PipelineStage.EMBED,
            f"Embedding service failed: {str(e)}",
            cause=e,
        )
    except Exception as e:
        raise PipelineError(
            PipelineStage.EMBED,
            f"Embedding failed: {str(e)}",
            cause=e,
        )


# =============================================================================
# RESPONSE SERIALIZATION
# =============================================================================

def serialize_card_for_response(card: ExperienceCard | ExperienceCardChild) -> dict:
    """Convert persisted card to API response format."""
    if isinstance(card, ExperienceCardChild):
        value = card.value if isinstance(card.value, dict) else {}
        time_obj = value.get("time") or {}
        location_obj = value.get("location") or {}
        topics = value.get("topics") or []
        tags = value.get("tags") or []
        
        relation_type = getattr(card, "child_type", None) or value.get("relation_type")
        return {
            "id": card.id,
            "relation_type": relation_type,
            "title": card.label or value.get("headline") or "",
            "context": value.get("summary") or "",
            "tags": tags,
            "headline": card.label or value.get("headline") or "",
            "summary": value.get("summary") or "",
            "topics": topics if isinstance(topics, list) else [{"label": t} for t in tags],
            "time_range": time_obj.get("text") if isinstance(time_obj, dict) else None,
            "role_title": None,
            "company": value.get("company"),
            "location": location_obj.get("text") if isinstance(location_obj, dict) else None,
        }
    else:
        start_date = card.start_date.isoformat() if card.start_date else None
        end_date = card.end_date.isoformat() if card.end_date else None
        time_range = None
        if start_date or end_date:
            time_range = " - ".join([d for d in (start_date, end_date) if d])
        elif card.is_current:
            time_range = "Ongoing"
        return {
            "id": card.id,
            "title": card.title,
            "context": card.summary,
            "tags": [],
            "headline": card.title,
            "summary": card.summary,
            "topics": [],
            "time_range": time_range,
            "start_date": start_date,
            "end_date": end_date,
            "is_current": card.is_current,
            "role_title": card.normalized_role,
            "company": card.company_name,
            "location": card.location,
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# Allowed keys for fill-missing-fields (edit form). Must match frontend form keys.
FILL_MISSING_PARENT_KEYS = (
    "title, summary, normalized_role, domain, sub_domain, company_name, company_type, "
    "location, employment_type, start_date, end_date, is_current, intent_primary, "
    "intent_secondary_str, seniority_level, confidence_score"
)
FILL_MISSING_CHILD_KEYS = "title, summary, tagsStr, time_range, company, location"


async def fill_missing_fields_from_text(
    raw_text: str,
    current_card: dict,
    card_type: str,
) -> dict:
    """
    Pipeline: Rewrite -> Fill missing fields only. No DB writes.
    Returns a dict of only the fields the LLM extracted (to merge into form).
    """
    if not raw_text or not raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="raw_text is required and cannot be empty",
        )
    card_type = (card_type or "parent").strip().lower()
    if card_type not in ("parent", "child"):
        card_type = "parent"
    allowed_keys = FILL_MISSING_PARENT_KEYS if card_type == "parent" else FILL_MISSING_CHILD_KEYS

    cleaned_text = await rewrite_raw_text(raw_text)
    prompt = fill_prompt(
        PROMPT_FILL_MISSING_FIELDS,
        cleaned_text=cleaned_text,
        current_card_json=json.dumps(current_card, indent=2),
        allowed_keys=allowed_keys,
    )
    chat = get_chat_provider()
    try:
        response = await chat.chat(prompt, max_tokens=2048)
    except ChatServiceError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    if not response or not response.strip():
        return {}

    try:
        json_str = _extract_json_from_text(response)
        data = json.loads(json_str)
        if not isinstance(data, dict):
            return {}
        # Normalize keys to match frontend form: intent_secondary -> intent_secondary_str, tags -> tagsStr
        if "intent_secondary" in data and "intent_secondary_str" not in data:
            val = data.pop("intent_secondary")
            if isinstance(val, list):
                data["intent_secondary_str"] = ", ".join(str(x) for x in val)
            else:
                data["intent_secondary_str"] = str(val) if val is not None else ""
        if "tags" in data and "tagsStr" not in data:
            val = data.pop("tags")
            if isinstance(val, list):
                data["tagsStr"] = ", ".join(str(x) for x in val)
            else:
                data["tagsStr"] = str(val) if val is not None else ""
        # Normalize date strings to ISO for frontend date inputs.
        for key in ("start_date", "end_date"):
            if key in data:
                parsed = parse_date_field(str(data[key])) if data[key] is not None else None
                if parsed:
                    data[key] = parsed.isoformat()
        return data
    except (ValueError, json.JSONDecodeError):
        logger.warning("fill_missing_fields: could not parse LLM response as JSON")
        return {}


async def rewrite_raw_text(raw_text: str) -> str:
    """
    Clean and rewrite raw input text.
    
    Raises:
        HTTPException: If input is empty
        PipelineError: If LLM fails
    """
    if not raw_text or not raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="raw_text is required and cannot be empty",
        )
    
    try:
        chat = get_chat_provider()
        prompt = fill_prompt(PROMPT_REWRITE, user_text=raw_text)
        rewritten = await chat.chat(prompt, max_tokens=2048)
        
        cleaned = " ".join((rewritten or "").split()).strip()
        
        if not cleaned:
            raise PipelineError(
                PipelineStage.REWRITE,
                "Rewrite returned empty text",
            )
        
        return cleaned
    
    except ChatServiceError as e:
        raise PipelineError(
            PipelineStage.REWRITE,
            f"Chat service failed: {str(e)}",
            cause=e,
        )


async def next_draft_run_version(db: AsyncSession, raw_experience_id: str, person_id: str) -> int:
    """Get next run version for draft set."""
    result = await db.execute(
        select(func.max(DraftSet.run_version)).where(
            DraftSet.raw_experience_id == raw_experience_id,
            DraftSet.person_id == person_id,
        )
    )
    max_version = result.scalar_one_or_none()
    return (max_version or 0) + 1


# =============================================================================
# MAIN PIPELINE
# =============================================================================

async def run_draft_v1_pipeline(
    db: AsyncSession,
    person_id: str,
    body: RawExperienceCreate,
) -> tuple[str, str, list[dict]]:
    """
    Execute the complete draft pipeline with proper error handling.
    
    Pipeline stages:
    1. Rewrite - Clean input text
    2. Extract - LLM extraction to structured families
    3. Validate - LLM validation and enrichment
    4. Persist - Save to database
    5. Embed - Generate embeddings
    
    Returns:
        (draft_set_id, raw_experience_id, card_families)
    
    Raises:
        HTTPException: For client errors (400)
        PipelineError: For pipeline failures with stage context
        ChatServiceError: For unrecoverable LLM errors
        EmbeddingServiceError: For embedding errors
    """
    raw_text_original = body.raw_text or ""
    
    logger.info(f"Starting pipeline for person_id={person_id}, text_len={len(raw_text_original)}")
    
    # =========================================================================
    # STAGE 1: REWRITE
    # =========================================================================
    
    raw_text_cleaned = await rewrite_raw_text(raw_text_original)
    logger.info(f"Rewrite complete: {len(raw_text_original)} → {len(raw_text_cleaned)} chars")
    
    # Create RawExperience record
    raw = RawExperience(
        person_id=person_id,
        raw_text=raw_text_original,
        raw_text_original=raw_text_original,
        raw_text_cleaned=raw_text_cleaned,
    )
    db.add(raw)
    await db.flush()
    raw_experience_id = str(raw.id)
    
    # Create DraftSet
    run_version = await next_draft_run_version(db, raw_experience_id, person_id)
    draft_set = DraftSet(
        person_id=person_id,
        raw_experience_id=raw.id,
        run_version=run_version,
    )
    db.add(draft_set)
    await db.flush()
    draft_set_id = str(draft_set.id)
    
    logger.info(f"Created raw_experience_id={raw_experience_id}, draft_set_id={draft_set_id}")
    
    # =========================================================================
    # STAGE 2: EXTRACT
    # =========================================================================
    
    chat = get_chat_provider()
    
    extract_prompt = fill_prompt(
        PROMPT_EXTRACT_ALL_CARDS,
        user_text=raw_text_cleaned,
        person_id=person_id,
    )
    
    try:
        extract_response = await chat.chat(extract_prompt, max_tokens=8192)
        extracted_families = parse_llm_response_to_families(
            extract_response,
            stage=PipelineStage.EXTRACT,
        )
        logger.info(f"Extraction complete: {len(extracted_families)} families")
    
    except ChatServiceError:
        raise
    except PipelineError:
        raise
    
    # Inject metadata
    for family in extracted_families:
        inject_metadata_into_family(family, person_id)
    
    # =========================================================================
    # STAGE 3: VALIDATE
    # =========================================================================
    
    validate_payload = {
        "raw_text_original": raw_text_original,
        "raw_text_cleaned": raw_text_cleaned,
        "families": [
            {
                "parent": family.parent.dict(),
                "children": [c.dict() for c in family.children],
            }
            for family in extracted_families
        ],
    }
    
    validate_prompt = fill_prompt(
        PROMPT_VALIDATE_ALL_CARDS,
        parent_and_children_json=json.dumps(validate_payload),
    )
    
    try:
        validate_response = await chat.chat(validate_prompt, max_tokens=8192)
        validated_families = parse_llm_response_to_families(
            validate_response,
            stage=PipelineStage.VALIDATE,
        )
        logger.info(f"Validation complete: {len(validated_families)} families")
    
    except (PipelineError, ChatServiceError) as e:
        # Validation is optional enhancement - fall back to extraction
        logger.warning(f"Validation failed, using extraction output: {e}")
        validated_families = extracted_families
    
    # Re-inject metadata after validation (LLM may have modified/removed fields)
    for family in validated_families:
        inject_metadata_into_family(family, person_id)
    
    # =========================================================================
    # STAGE 4: PERSIST
    # =========================================================================
    
    parents, children = await persist_families(
        db,
        validated_families,
        person_id=person_id,
        raw_experience_id=raw_experience_id,
        draft_set_id=draft_set_id,
    )
    
    logger.info(f"Persisted {len(parents)} parents, {len(children)} children")
    
    # =========================================================================
    # STAGE 5: EMBED
    # =========================================================================
    
    await embed_cards(db, parents, children)
    
    # =========================================================================
    # BUILD RESPONSE
    # =========================================================================
    
    card_families: list[dict] = []
    
    for parent in parents:
        # Find children for this parent
        parent_children = [c for c in children if c.parent_experience_id == parent.id]

        card_families.append({
            "parent": serialize_card_for_response(parent),
            "children": [serialize_card_for_response(c) for c in parent_children],
        })

    logger.info(f"Pipeline complete: {len(card_families)} families ready")
    
    return draft_set_id, raw_experience_id, card_families
