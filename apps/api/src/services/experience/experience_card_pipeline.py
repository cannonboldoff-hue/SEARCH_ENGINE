"""
Experience Card Pipeline

Orchestrates: rewrite → extract → validate → persist → embed.

SECTIONS (in order):
  1. Rewrite cache    - In-process cache for rewritten raw text (avoids duplicate LLM calls).
  2. Models           - Pydantic models for LLM response validation (V1Card, V1Family, etc.).
  3. Parsing          - JSON extraction, parse_llm_response_to_families, parent/child normalization.
  4. Metadata         - inject_metadata_into_family.
  5. Field extraction - Date parsing, extract_time_fields, extract_location_fields, normalize_card_title.
  6. Persistence      - card_to_experience_card_fields, card_to_child_fields, persist_families.
  7. Serialization    - serialize_card_for_response.
  8. Fill missing     - fill_missing_fields_from_text (edit-form LLM fill).
  9. Clarify flow     - _run_clarify_flow, clarify_experience_interactive.
  10. Public API      - rewrite_raw_text, detect_experiences, next_draft_run_version, run_draft_v1_single.

Embedding: After persist_families(), embed_experience_cards() builds search-document text per card,
fetches vectors from the embedding provider, and flushes. Search-document text is defined in
experience_card_search_document; embedding logic lives in experience_card_embedding.

Public API (for routers):
  - rewrite_raw_text, detect_experiences, run_draft_v1_single
  - fill_missing_fields_from_text, clarify_experience_interactive
  - DEFAULT_MAX_PARENT_CLARIFY, DEFAULT_MAX_CHILD_CLARIFY (re-exported from experience_clarify)
"""

from __future__ import annotations

__all__ = [
    "rewrite_raw_text",
    "detect_experiences",
    "run_draft_v1_single",
    "fill_missing_fields_from_text",
    "clarify_experience_interactive",
    "DEFAULT_MAX_PARENT_CLARIFY",
    "DEFAULT_MAX_CHILD_CLARIFY",
]

import asyncio
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone, date
from typing import Optional, Any

from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.db.models import RawExperience, DraftSet, ExperienceCard, ExperienceCardChild
from src.domain import ALLOWED_CHILD_TYPES
from src.schemas import RawExperienceCreate
from src.providers import get_chat_provider, ChatServiceError
from src.prompts.experience_card import (
    PROMPT_REWRITE,
    PROMPT_DETECT_EXPERIENCES,
    PROMPT_EXTRACT_SINGLE_CARDS,
    PROMPT_FILL_MISSING_FIELDS,
    PROMPT_CLARIFY_PLANNER,
    PROMPT_CLARIFY_QUESTION_WRITER,
    PROMPT_CLARIFY_APPLY_ANSWER,
    fill_prompt,
)
from .experience_clarify import (
    ClarifyPlan,
    normalize_card_family_for_clarify,
    is_parent_good_enough,
    compute_missing_fields,
    validate_clarify_plan,
    fallback_clarify_plan,
    should_stop_clarify,
    merge_patch_into_card_family,
    normalize_after_patch,
    canonical_parent_to_flat_response,
    is_question_generic_onboarding,
    CHOOSE_FOCUS_MESSAGE,
    DEFAULT_MAX_PARENT_CLARIFY,
    DEFAULT_MAX_CHILD_CLARIFY,
    _parse_planner_json,
)
from .experience_card_embedding import embed_experience_cards
from .pipeline_errors import PipelineError, PipelineStage

logger = logging.getLogger(__name__)

# =============================================================================
# REWRITE CACHE
# =============================================================================
# In-process cache for rewritten raw text. Key = SHA-256 of stripped input;
# value = cleaned string. Capped at 256 entries (LRU eviction). Lock guards
# concurrent async access.
# =============================================================================

_REWRITE_CACHE: dict[str, str] = {}
_REWRITE_CACHE_MAX = 256
_rewrite_cache_lock = asyncio.Lock()


def _rewrite_cache_key(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


async def _rewrite_cache_get(text: str) -> Optional[str]:
    key = _rewrite_cache_key(text)
    async with _rewrite_cache_lock:
        return _REWRITE_CACHE.get(key)


async def _rewrite_cache_set(text: str, cleaned: str) -> None:
    key = _rewrite_cache_key(text)
    async with _rewrite_cache_lock:
        if len(_REWRITE_CACHE) >= _REWRITE_CACHE_MAX:
            oldest = next(iter(_REWRITE_CACHE))
            del _REWRITE_CACHE[oldest]
        _REWRITE_CACHE[key] = cleaned


# =============================================================================
# MODELS — LLM response validation (Pydantic)
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

    @model_validator(mode="before")
    @classmethod
    def normalize_prompt_style_fields(cls, data: Any) -> Any:
        """Accept both prompt-style parent keys and legacy V1 keys."""
        if not isinstance(data, dict):
            return data

        data = dict(data)

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

        if data.get("intent_secondary") is None:
            data["intent_secondary"] = []
        elif isinstance(data.get("intent_secondary"), str):
            data["intent_secondary"] = [s.strip() for s in data["intent_secondary"].split(",") if s.strip()]

        if data.get("search_phrases") is None:
            data["search_phrases"] = []
        elif isinstance(data.get("search_phrases"), str):
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

    @field_validator("time", mode="before")
    @classmethod
    def normalize_time(cls, v: Any) -> Any:
        """Convert string to TimeInfo dict."""
        if isinstance(v, str):
            return {"text": v}
        return v

    @field_validator("location", mode="before")
    @classmethod
    def normalize_location(cls, v: Any) -> Any:
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


# =============================================================================
# PARSING & VALIDATION
# =============================================================================
# JSON extraction from LLM output, normalization of family/child dicts,
# and parse_llm_response_to_families.
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


def _is_time_empty(t: Any) -> bool:
    """True if time is missing or has no meaningful value."""
    if t is None:
        return True
    if isinstance(t, str):
        return not (t or "").strip()
    if isinstance(t, dict):
        return not (
            (t.get("text") or "").strip()
            or t.get("start")
            or t.get("end")
        )
    return True


def _is_location_empty(loc: Any) -> bool:
    """True if location is missing or has no meaningful value."""
    if loc is None:
        return True
    if isinstance(loc, str):
        return not (loc or "").strip()
    if isinstance(loc, dict):
        return not (
            (loc.get("text") or "").strip()
            or loc.get("city")
            or loc.get("country")
        )
    return True


def _get_parent_time(parent: dict) -> Optional[dict]:
    """Extract time dict from parent (time object or start_date/end_date/time_text)."""
    t = parent.get("time")
    if isinstance(t, dict) and (t.get("text") or t.get("start") or t.get("end")):
        return t
    start = parent.get("start_date")
    end = parent.get("end_date")
    text = parent.get("time_text")
    ongoing = parent.get("is_current")
    if start or end or text or isinstance(ongoing, bool):
        return {"start": start, "end": end, "text": text, "ongoing": ongoing}
    return None


def _get_parent_location(parent: dict) -> Any:
    """Extract location (str or dict) from parent."""
    loc = parent.get("location")
    if loc is None:
        return None
    if isinstance(loc, str) and (loc or "").strip():
        return loc
    if isinstance(loc, dict) and (
        (loc.get("text") or "").strip() or loc.get("city") or loc.get("country")
    ):
        return loc
    return None


def _get_parent_company(parent: dict) -> Optional[str]:
    """Extract company name from parent."""
    c = parent.get("company") or parent.get("company_name") or parent.get("organization")
    if c and str(c).strip():
        return str(c).strip()
    return None


def _inherit_parent_context_into_children(
    parent_dict: Optional[dict], children_list: list[dict]
) -> list[dict]:
    """
    Fill each child's missing time_range, location, and company from the parent.
    Only fills when the child has no explicit value—so user-stated values are preserved.
    """
    if not parent_dict or not isinstance(parent_dict, dict) or not children_list:
        return children_list
    p_time = _get_parent_time(parent_dict)
    p_location = _get_parent_location(parent_dict)
    p_company = _get_parent_company(parent_dict)
    if not p_time and not p_location and not p_company:
        return children_list
    result = []
    for child in children_list:
        if not isinstance(child, dict):
            result.append(child)
            continue
        c = dict(child)
        if p_time and _is_time_empty(c.get("time")):
            c["time"] = dict(p_time) if isinstance(p_time, dict) else p_time
            val = c.get("value")
            if isinstance(val, dict):
                val = dict(val)
                val["time"] = c["time"]
                c["value"] = val
        if p_location is not None and _is_location_empty(c.get("location")):
            loc = (
                p_location
                if isinstance(p_location, dict)
                else {"text": p_location}
                if isinstance(p_location, str)
                else p_location
            )
            c["location"] = loc
            val = c.get("value")
            if isinstance(val, dict):
                val = dict(val)
                val["location"] = c["location"]
                c["value"] = val
        if p_company and not (c.get("company") or "").strip():
            c["company"] = p_company
            val = c.get("value")
            if isinstance(val, dict):
                val = dict(val)
                val["company"] = p_company
                c["value"] = val
        result.append(c)
    return result


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
            # Inherit parent's time_range, location, company into children when child has no explicit value
            parent_dict = normalized_family_dict.get("parent") or family_dict.get("parent")
            normalized_family_dict["children"] = _inherit_parent_context_into_children(
                parent_dict, normalized_family_dict["children"]
            )

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
# Inject person_id, ids, timestamps into parent and children (no overwrite of
# existing values from LLM).
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
# Date parsing, extract_time_fields, extract_location_fields, extract_company,
# extract_team, extract_role_info, extract_search_phrases, normalize_card_title.
# =============================================================================

# ISO date pattern: YYYY-MM-DD or YYYY-MM (used to find dates in free text).
# We rely on the LLM to output only ISO dates; this is a fallback for time_text.
_DATE_ISO_IN_TEXT = re.compile(r"\d{4}-\d{2}(?:-\d{2})?")


def parse_date_field(value: Optional[str]) -> Optional[date]:
    """
    Parse date from string. Expects ISO format only (YYYY-MM-DD or YYYY-MM).
    The LLM is instructed to output dates in this format; we do not hardcode
    month names or locale-dependent formats.
    """
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = (
        text.replace("/", "-").replace(".", "-").replace("–", "-").replace("—", "-").strip()
    )
    normalized = re.sub(r"[,\s]+", " ", normalized).strip().replace(" ", "-")
    if len(normalized) == 7 and normalized[4] == "-":  # YYYY-MM
        normalized = f"{normalized}-01"
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def _extract_dates_from_text(text: str) -> tuple[Optional[date], Optional[date]]:
    """Extract up to two ISO-format dates from a string (e.g. time_text)."""
    if not text:
        return None, None
    haystack = str(text).replace("–", "-").replace("—", "-")
    matches = _DATE_ISO_IN_TEXT.findall(haystack)
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
# V1Card/V1Family → ORM fields; persist_families (parents + children, then embed).
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
        "topics": [t.model_dump() for t in card.topics],
        "entities": [e.model_dump() for e in card.entities],
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
            await asyncio.gather(*[db.refresh(child_ec) for child_ec in all_children])

        return all_parents, all_children
    
    except Exception as e:
        raise PipelineError(
            PipelineStage.PERSIST,
            f"Database persistence failed: {str(e)}",
            cause=e,
        )


# =============================================================================
# RESPONSE SERIALIZATION
# =============================================================================
# Persisted ExperienceCard / ExperienceCardChild → API response dict.
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
# FILL MISSING FIELDS (edit form)
# =============================================================================
# Rewrite → LLM fill missing fields only; return dict to merge into form.
# Allowed keys must match frontend form keys.
# =============================================================================

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


def _parse_date_field_for_clarify(val: Any) -> Optional[str]:
    """Parse date for clarify response; return ISO string or None."""
    if val is None:
        return None
    parsed = parse_date_field(str(val))
    return parsed.isoformat() if parsed else None


# =============================================================================
# CLARIFY FLOW
# =============================================================================
# Structured history, LLM planner → question writer / answer applier.
# _run_clarify_flow, clarify_experience_interactive, and helpers.
# =============================================================================

def _clarify_result(
    *,
    clarifying_question: Optional[str] = None,
    filled: Optional[dict] = None,
    should_stop: bool = False,
    stop_reason: Optional[str] = None,
    target_type: Optional[str] = None,
    target_field: Optional[str] = None,
    target_child_type: Optional[str] = None,
    progress: Optional[dict] = None,
    missing_fields: Optional[list] = None,
    asked_history_entry: Optional[dict] = None,
    canonical_family: Optional[dict] = None,
) -> dict:
    """Build a standard clarify-flow return dict. Omitted keys default to None/false."""
    return {
        "clarifying_question": clarifying_question,
        "filled": filled or {},
        "should_stop": should_stop,
        "stop_reason": stop_reason,
        "target_type": target_type,
        "target_field": target_field,
        "target_child_type": target_child_type,
        "progress": progress,
        "missing_fields": missing_fields,
        "asked_history_entry": asked_history_entry,
        "canonical_family": canonical_family,
    }


def _build_asked_history_and_counts(
    conversation_history: list[dict],
    asked_history_structured: Optional[list[dict]] = None,
) -> tuple[list[dict], int, int]:
    """
    Build structured asked_history and parent_asked_count, child_asked_count.
    If asked_history_structured is provided, use it and derive counts. Else derive from conversation_history (legacy).
    """
    if asked_history_structured:
        history = list(asked_history_structured)
        parent_count = sum(1 for m in history if m.get("role") == "assistant" and m.get("kind") == "clarify_question" and m.get("target_type") == "parent")
        child_count = sum(1 for m in history if m.get("role") == "assistant" and m.get("kind") == "clarify_question" and m.get("target_type") == "child")
        return history, parent_count, child_count
    # Legacy: conversation_history is list of { role, content }. Count assistant messages as parent asks.
    history = []
    parent_count = 0
    for msg in conversation_history or []:
        role = (msg.get("role") or "user").strip().lower()
        content = (msg.get("content") or "").strip()
        if role == "assistant" and content:
            history.append({
                "role": "assistant",
                "kind": "clarify_question",
                "target_type": "parent",
                "target_field": None,
                "target_child_type": None,
                "text": content,
            })
            parent_count += 1
        elif role == "user" and content:
            history.append({
                "role": "user",
                "kind": "clarify_answer",
                "text": content,
            })
    return history, parent_count, 0


async def _plan_next_clarify_step_llm(
    cleaned_text: str,
    canonical_family: dict,
    asked_history: list[dict],
    parent_asked_count: int,
    child_asked_count: int,
    max_parent: int = DEFAULT_MAX_PARENT_CLARIFY,
    max_child: int = DEFAULT_MAX_CHILD_CLARIFY,
) -> Optional[ClarifyPlan]:
    """Call LLM planner; return ClarifyPlan or None on parse failure."""
    prompt = fill_prompt(
        PROMPT_CLARIFY_PLANNER,
        cleaned_text=cleaned_text,
        canonical_card_json=json.dumps(canonical_family, indent=2),
        asked_history_json=json.dumps(asked_history, indent=2),
        max_parent=max_parent,
        max_child=max_child,
        parent_asked_count=parent_asked_count,
        child_asked_count=child_asked_count,
    )
    chat = get_chat_provider()
    try:
        response = await chat.chat(prompt, max_tokens=512)
    except ChatServiceError as e:
        logger.warning("clarify planner LLM failed: %s", e)
        return None
    if not response or not response.strip():
        return None
    try:
        json_str = _extract_json_from_text(response)
        data = json.loads(json_str)
        return _parse_planner_json(data)
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("clarify planner parse failed: %s", e)
        return None


async def _generate_clarify_question_llm(plan: ClarifyPlan, canonical_family: dict) -> Optional[str]:
    """Generate one short question for the validated plan. Returns question text or None."""
    plan_json = json.dumps({
        "action": plan.action,
        "target_type": plan.target_type,
        "target_field": plan.target_field,
        "target_child_type": plan.target_child_type,
        "reason": plan.reason,
    })
    card_context = json.dumps(canonical_family.get("parent") or {}, indent=2)
    prompt = fill_prompt(
        PROMPT_CLARIFY_QUESTION_WRITER,
        validated_plan_json=plan_json,
        card_context_json=card_context,
    )
    chat = get_chat_provider()
    try:
        response = await chat.chat(prompt, max_tokens=256)
    except ChatServiceError as e:
        logger.warning("clarify question writer LLM failed: %s", e)
        return None
    if not response or not response.strip():
        return None
    try:
        json_str = _extract_json_from_text(response)
        data = json.loads(json_str)
        if isinstance(data, dict) and data.get("question"):
            return str(data["question"]).strip()
    except (ValueError, json.JSONDecodeError):
        pass
    return None


async def _apply_clarify_answer_patch_llm(
    plan: ClarifyPlan,
    user_answer: str,
    canonical_family: dict,
) -> tuple[Optional[dict], bool, Optional[str]]:
    """
    Convert user answer to patch. Returns (patch_dict, needs_retry, retry_question).
    Patch may be None if needs_retry or parse failure.
    """
    plan_json = json.dumps({
        "action": plan.action,
        "target_type": plan.target_type,
        "target_field": plan.target_field,
        "target_child_type": plan.target_child_type,
    })
    card_json = json.dumps(canonical_family, indent=2)
    prompt = fill_prompt(
        PROMPT_CLARIFY_APPLY_ANSWER,
        validated_plan_json=plan_json,
        user_answer=user_answer,
        canonical_card_json=card_json,
    )
    chat = get_chat_provider()
    try:
        response = await chat.chat(prompt, max_tokens=512)
    except ChatServiceError as e:
        logger.warning("clarify apply answer LLM failed: %s", e)
        return None, True, "Could you rephrase that? I want to capture it correctly."
    if not response or not response.strip():
        return None, True, "Can you say a bit more?"
    try:
        json_str = _extract_json_from_text(response)
        data = json.loads(json_str)
        if not isinstance(data, dict):
            return None, True, "Can you say a bit more?"
        patch = data.get("patch") if isinstance(data.get("patch"), dict) else None
        needs_retry = bool(data.get("needs_retry"))
        retry_q = str(data.get("retry_question") or "").strip() or None
        return patch, needs_retry, retry_q
    except (ValueError, json.JSONDecodeError):
        return None, True, "Can you say a bit more?"



async def _run_clarify_flow(
    raw_text: str,
    card_family: dict,
    conversation_history: list[dict],
    asked_history_structured: Optional[list[dict]] = None,
    last_question_target: Optional[dict] = None,
    max_parent: int = DEFAULT_MAX_PARENT_CLARIFY,
    max_child: int = DEFAULT_MAX_CHILD_CLARIFY,
    card_families: Optional[list[dict]] = None,
    focus_parent_id: Optional[str] = None,
) -> dict:
    """
    Clarify flow: normalize -> plan -> validate -> question writer or apply answer.
    Returns dict with: action?, clarifying_question?, message?, options?, focus_parent_id?, filled?, should_stop?, ...
    """
    # Resolve to single family when focus is set (e.g. from detected_experiences choose_focus)
    if card_families and focus_parent_id:
        for f in card_families:
            p = f.get("parent") or {}
            if str(p.get("id")) == str(focus_parent_id):
                card_family = f
                break

    # 1) Canonical normalizer
    canonical = normalize_card_family_for_clarify(card_family)
    asked_history, parent_asked_count, child_asked_count = _build_asked_history_and_counts(
        conversation_history, asked_history_structured
    )

    last_is_user = bool(asked_history and asked_history[-1].get("role") == "user")

    # 2) Resolve plan_for_apply (synchronous — no LLM needed yet)
    plan_for_apply: Optional[ClarifyPlan] = None
    if last_is_user and len(asked_history) >= 1:
        if last_question_target:
            tt = last_question_target.get("target_type")
            tf = last_question_target.get("target_field")
            tct = last_question_target.get("target_child_type")
            if tt in ("parent", "child"):
                plan_for_apply = ClarifyPlan(action="ask", target_type=tt, target_field=tf, target_child_type=tct)
        if not plan_for_apply:
            for i in range(len(asked_history) - 1, -1, -1):
                m = asked_history[i]
                if m.get("role") == "assistant" and m.get("kind") == "clarify_question":
                    plan_for_apply = ClarifyPlan(
                        action="ask",
                        target_type=m.get("target_type"),
                        target_field=m.get("target_field"),
                        target_child_type=m.get("target_child_type"),
                    )
                    break

    # 3) Run rewrite + (optionally) apply_answer concurrently.
    #    rewrite_raw_text is cached so subsequent calls within the same request
    #    (e.g. after detect_experiences already ran it) are free.
    if plan_for_apply and last_is_user:
        user_answer = asked_history[-1].get("text") or ""
        cleaned_text, (patch, needs_retry, retry_question) = await asyncio.gather(
            rewrite_raw_text(raw_text),
            _apply_clarify_answer_patch_llm(plan_for_apply, user_answer, canonical),
        )
        logger.info("clarify_flow apply_answer: patch=%s needs_retry=%s", bool(patch), needs_retry)
        if needs_retry and retry_question:
            new_entry = {
                "role": "assistant",
                "kind": "clarify_question",
                "target_type": plan_for_apply.target_type,
                "target_field": plan_for_apply.target_field,
                "target_child_type": plan_for_apply.target_child_type,
                "text": retry_question,
            }
            return _clarify_result(
                clarifying_question=retry_question,
                should_stop=False,
                target_type=plan_for_apply.target_type,
                target_field=plan_for_apply.target_field,
                target_child_type=plan_for_apply.target_child_type,
                progress={"parent_asked": parent_asked_count, "child_asked": child_asked_count, "max_parent": max_parent, "max_child": max_child},
                missing_fields=compute_missing_fields(canonical),
                asked_history_entry=new_entry,
                canonical_family=canonical,
            )
        if patch:
            canonical = merge_patch_into_card_family(canonical, patch, plan_for_apply)
            canonical = normalize_after_patch(canonical)
            logger.debug(
                "clarify_flow apply_answer: patch applied to canonical time_after=%s",
                canonical.get("parent", {}).get("time"),
            )
    else:
        cleaned_text = await rewrite_raw_text(raw_text)

    # 4) Plan -> validate -> ask or autofill or stop
    plan = None
    for _ in range(5):  # cap autofill loop
        raw_plan = await _plan_next_clarify_step_llm(
            cleaned_text, canonical, asked_history,
            parent_asked_count, child_asked_count, max_parent, max_child,
        )
        validated_plan, used_fallback = validate_clarify_plan(
            raw_plan, canonical, asked_history,
            parent_asked_count=parent_asked_count,
            child_asked_count=child_asked_count,
            max_parent=max_parent,
            max_child=max_child,
        )
        logger.info(
            "clarify_flow planner: raw_action=%s validated_action=%s used_fallback=%s target_type=%s target_field=%s",
            raw_plan.action if raw_plan else None,
            validated_plan.action,
            used_fallback,
            validated_plan.target_type,
            validated_plan.target_field or validated_plan.target_child_type,
        )
        plan = validated_plan

        if validated_plan.action == "stop":
            stop_reason = validated_plan.reason or "Done"
            logger.info("clarify_flow stop: %s", stop_reason)
            flat_parent = canonical_parent_to_flat_response(canonical.get("parent") or {})
            logger.debug(
                "clarify_flow stop filled: start_date=%s end_date=%s time_text=%s",
                flat_parent.get("start_date"), flat_parent.get("end_date"), flat_parent.get("time_text"),
            )
            return _clarify_result(
                filled=flat_parent,
                should_stop=True,
                stop_reason=stop_reason,
                progress={"parent_asked": parent_asked_count, "child_asked": child_asked_count, "max_parent": max_parent, "max_child": max_child},
                missing_fields=compute_missing_fields(canonical),
                canonical_family=canonical,
            )
        if validated_plan.action == "autofill" and validated_plan.autofill_patch:
            canonical = merge_patch_into_card_family(canonical, validated_plan.autofill_patch, validated_plan)
            canonical = normalize_after_patch(canonical)
            logger.info("clarify_flow autofill applied for %s", validated_plan.target_field or validated_plan.target_child_type)
            continue
        if validated_plan.action == "ask":
            question = await _generate_clarify_question_llm(validated_plan, canonical)
            if not question:
                question = _fallback_question_for_plan(validated_plan)
            # Ban generic onboarding/discovery questions in post-extraction clarify
            if question and is_question_generic_onboarding(question):
                logger.warning("clarify_flow: rejected generic question, using fallback: %s", question[:60])
                question = _fallback_question_for_plan(validated_plan)
            logger.info("clarify_flow ask: target=%s question=%s", validated_plan.target_field or validated_plan.target_child_type, question[:50] if question else "")
            new_entry = {
                "role": "assistant",
                "kind": "clarify_question",
                "target_type": validated_plan.target_type,
                "target_field": validated_plan.target_field,
                "target_child_type": validated_plan.target_child_type,
                "text": question,
            }
            return _clarify_result(
                clarifying_question=question,
                should_stop=False,
                target_type=validated_plan.target_type,
                target_field=validated_plan.target_field,
                target_child_type=validated_plan.target_child_type,
                progress={"parent_asked": parent_asked_count, "child_asked": child_asked_count, "max_parent": max_parent, "max_child": max_child},
                missing_fields=compute_missing_fields(canonical),
                asked_history_entry=new_entry,
                canonical_family=canonical,
            )
    # Loop exhausted (autofill only)
    flat_parent = canonical_parent_to_flat_response(canonical.get("parent") or {})
    return _clarify_result(
        filled=flat_parent,
        should_stop=True,
        stop_reason="Max autofill iterations",
        progress={"parent_asked": parent_asked_count, "child_asked": child_asked_count, "max_parent": max_parent, "max_child": max_child},
        missing_fields=compute_missing_fields(canonical),
        canonical_family=canonical,
    )


def _fallback_question_for_plan(plan: ClarifyPlan) -> str:
    """Deterministic fallback when LLM question writer fails. Field-targeted, not generic."""
    _PARENT_QUESTIONS = {
        "headline": "What would you call this role or experience in one line?",
        "role": "What was your job title or role?",
        "summary": "Can you summarize what you did there in a sentence or two?",
        "company_name": "Which company or organization was this at?",
        "team": "Which team or group were you in?",
        "time": "Roughly when did you do this? (e.g. 2020–2022 or Jan 2021)",
        "location": "Where was this based? (city or country)",
        "domain": "What domain or industry was this in?",
        "sub_domain": "Any specific sub-domain or focus?",
        "intent_primary": "What best describes this experience—work, project, education, or something else?",
    }
    if plan.target_type == "parent":
        return _PARENT_QUESTIONS.get(
            plan.target_field or "", "Which of these can you add: company name, time period, or location?"
        )
    if plan.target_type == "child":
        return f"What specific {plan.target_child_type or 'detail'} do you want to add?"
    return "Which detail can you add—company, time, or location?"


def _build_choose_focus_options_from_detected(detected_experiences: list[dict]) -> list[dict]:
    """Build options for choose_focus from detect-experiences response (index + label)."""
    options = []
    for item in detected_experiences:
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        label = (item.get("label") or "").strip() or f"Experience {idx}"
        if idx is not None:
            options.append({"parent_id": str(idx), "label": label[:80]})
    return options


async def clarify_experience_interactive(
    raw_text: str,
    current_card: dict,
    card_type: str,
    conversation_history: list[dict],
    *,
    card_family: Optional[dict] = None,
    asked_history_structured: Optional[list[dict]] = None,
    last_question_target: Optional[dict] = None,
    max_parent: int = DEFAULT_MAX_PARENT_CLARIFY,
    max_child: int = DEFAULT_MAX_CHILD_CLARIFY,
    card_families: Optional[list[dict]] = None,
    focus_parent_id: Optional[str] = None,
    detected_experiences: Optional[list[dict]] = None,
) -> dict:
    """
    Interactive clarification: opening question when raw_text empty; when multiple
    experiences detected (no focus) return choose_focus so user picks one to extract; otherwise 4-part flow.
    """
    # Multiple experiences detected (before extraction): return choose_focus so user picks one first
    if detected_experiences and len(detected_experiences) > 1 and not focus_parent_id:
        options = _build_choose_focus_options_from_detected(detected_experiences)
        logger.info("clarify_flow choose_focus: detected_experiences (%s), no focus", len(detected_experiences))
        return {
            "action": "choose_focus",
            "message": CHOOSE_FOCUS_MESSAGE,
            "options": options,
            "focus_parent_id": None,
            **_clarify_result(),
        }
    if not raw_text or not raw_text.strip():
        return _clarify_result(
            clarifying_question="What's one experience you'd like to add? Tell me in your own words.",
        )

    family = card_family if isinstance(card_family, dict) and (card_family.get("parent") is not None or (card_family.get("children") is not None)) else None
    if not family:
        family = {"parent": current_card or {}, "children": []}
    elif not family.get("parent"):
        family = {**family, "parent": current_card or {}}
    if focus_parent_id and card_families:
        for f in card_families:
            p = f.get("parent") or {}
            if str(p.get("id")) == str(focus_parent_id):
                family = f
                break
    result = await _run_clarify_flow(
        raw_text=raw_text,
        card_family=family,
        conversation_history=conversation_history,
        asked_history_structured=asked_history_structured,
        last_question_target=last_question_target,
        max_parent=max_parent,
        max_child=max_child,
        card_families=card_families,
        focus_parent_id=focus_parent_id,
    )
    filled = result.get("filled") or {}
    if filled:
        for key in ("start_date", "end_date"):
            if key in filled and filled[key] is not None:
                parsed = _parse_date_field_for_clarify(filled[key])
                if parsed:
                    filled[key] = parsed
        result["filled"] = filled
    return result


# =============================================================================
# PUBLIC API — Rewrite, detect, draft, run pipeline
# =============================================================================

async def rewrite_raw_text(raw_text: str) -> str:
    """
    Clean and rewrite raw input text. Cached in-process by SHA-256 of input so
    repeated calls (e.g. detect → draft → clarify on same message) hit the LLM once.

    Raises:
        HTTPException: If input is empty.
        PipelineError: If LLM fails.
    """
    if not raw_text or not raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="raw_text is required and cannot be empty",
        )

    cached = await _rewrite_cache_get(raw_text)
    if cached:
        logger.debug("rewrite_raw_text: cache hit")
        return cached

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

        await _rewrite_cache_set(raw_text, cleaned)
        return cleaned

    except ChatServiceError as e:
        raise PipelineError(
            PipelineStage.REWRITE,
            f"Chat service failed: {str(e)}",
            cause=e,
        )


async def detect_experiences(raw_text: str) -> dict:
    """
    Analyze cleaned text and return count + list of distinct experiences (labels + suggested).
    Returns {"count": int, "experiences": [{"index": int, "label": str, "suggested": bool}]}.
    """
    if not raw_text or not raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="raw_text is required and cannot be empty",
        )
    cleaned = await rewrite_raw_text(raw_text)
    prompt = fill_prompt(PROMPT_DETECT_EXPERIENCES, cleaned_text=cleaned)
    chat = get_chat_provider()
    try:
        response = await chat.chat(prompt, max_tokens=1024)
    except ChatServiceError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    if not response or not response.strip():
        return {"count": 0, "experiences": []}
    try:
        json_str = _extract_json_from_text(response)
        data = json.loads(json_str)
        if not isinstance(data, dict):
            return {"count": 0, "experiences": []}
        count = int(data.get("count", 0)) if data.get("count") is not None else 0
        experiences = data.get("experiences") if isinstance(data.get("experiences"), list) else []
        out = []
        for i, item in enumerate(experiences):
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            if idx is None and i + 1 <= count:
                idx = i + 1
            elif isinstance(idx, (int, float)):
                idx = int(idx)
            else:
                continue
            label = (item.get("label") or "").strip() or f"Experience {idx}"
            suggested = bool(item.get("suggested"))
            out.append({"index": idx, "label": label, "suggested": suggested})
        if out and not any(e.get("suggested") for e in out):
            out[0]["suggested"] = True
        return {"count": count, "experiences": out}
    except (ValueError, json.JSONDecodeError):
        logger.warning("detect_experiences: could not parse LLM response")
        return {"count": 0, "experiences": []}


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


async def run_draft_v1_single(
    db: AsyncSession,
    person_id: str,
    raw_text: str,
    experience_index: int,
    experience_count: int,
) -> tuple[str, str, list[dict]]:
    """
    Run draft pipeline for ONE experience only (by 1-based index).
    Returns (draft_set_id, raw_experience_id, card_families) with at most one family.
    """
    raw_text_original = (raw_text or "").strip()
    if not raw_text_original:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="raw_text is required and cannot be empty",
        )
    idx = max(1, min(experience_index, experience_count or 1))
    total = max(1, experience_count)

    logger.info(f"Starting single-experience pipeline person_id={person_id}, index={idx}/{total}")

    raw_text_cleaned = await rewrite_raw_text(raw_text_original)
    raw = RawExperience(
        person_id=person_id,
        raw_text=raw_text_original,
        raw_text_original=raw_text_original,
        raw_text_cleaned=raw_text_cleaned,
    )
    db.add(raw)
    await db.flush()
    raw_experience_id = str(raw.id)
    run_version = await next_draft_run_version(db, raw_experience_id, person_id)
    draft_set = DraftSet(
        person_id=person_id,
        raw_experience_id=raw.id,
        run_version=run_version,
    )
    db.add(draft_set)
    await db.flush()
    draft_set_id = str(draft_set.id)

    chat = get_chat_provider()
    extract_prompt = fill_prompt(
        PROMPT_EXTRACT_SINGLE_CARDS,
        user_text=raw_text_cleaned,
        person_id=person_id,
        experience_index=idx,
        experience_count=total,
    )
    try:
        extract_response = await chat.chat(extract_prompt, max_tokens=8192)
        # Run CPU-bound parsing in thread pool to avoid blocking the event loop
        extracted_families = await asyncio.to_thread(
            parse_llm_response_to_families,
            extract_response,
            PipelineStage.EXTRACT,
        )
    except (ChatServiceError, PipelineError):
        raise
    # Keep only the first family (single-experience extract)
    extracted_families = extracted_families[:1]
    for family in extracted_families:
        inject_metadata_into_family(family, person_id)

    parents, children = await persist_families(
        db,
        extracted_families,
        person_id=person_id,
        raw_experience_id=raw_experience_id,
        draft_set_id=draft_set_id,
    )
    # Embedding: build search-document text per card, fetch vectors, assign and flush
    await embed_experience_cards(db, parents, children)

    # Group children by parent_id once (O(n)) instead of per-parent scan (O(n*m))
    children_by_parent_id: dict[str, list] = {}
    for c in children:
        children_by_parent_id.setdefault(c.parent_experience_id, []).append(c)
    card_families = [
        {
            "parent": serialize_card_for_response(parent),
            "children": [serialize_card_for_response(c) for c in children_by_parent_id.get(parent.id, [])],
        }
        for parent in parents
    ]
    return draft_set_id, raw_experience_id, card_families
