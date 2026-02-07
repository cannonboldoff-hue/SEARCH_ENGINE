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
import uuid
from datetime import datetime, timezone, date
from typing import Optional, Any
from enum import Enum

from pydantic import BaseModel, Field, validator, ValidationError
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


class V1Card(BaseModel):
    """Base card structure returned by LLM."""
    id: Optional[str] = None
    headline: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    raw_text: Optional[str] = None
    time: Optional[TimeInfo | str] = None
    location: Optional[LocationInfo | str] = None
    roles: list[RoleInfo] = Field(default_factory=list)
    topics: list[TopicInfo] = Field(default_factory=list)
    entities: list[EntityInfo] = Field(default_factory=list)
    actions: list[dict] = Field(default_factory=list)
    outcomes: list[dict] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    tooling: Optional[Any] = None
    company: Optional[str] = None
    organization: Optional[str] = None
    team: Optional[str] = None
    index: Optional[IndexInfo] = None
    intent: Optional[str] = None
    
    # Metadata fields
    person_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    parent_id: Optional[str] = None
    depth: Optional[int] = None
    relation_type: Optional[str] = None
    child_type: Optional[str] = None

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
        
        try:
            family = V1Family(**family_dict)
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

def parse_date_field(value: Optional[str]) -> Optional[date]:
    """Parse ISO date string, returning None on failure."""
    if not value:
        return None
    
    text = value.strip()
    
    # Handle YYYY-MM format
    if len(text) == 7 and text[4] == "-":
        text = f"{text}-01"
    
    try:
        return date.fromisoformat(text)
    except ValueError as e:
        logger.warning(f"Failed to parse date '{value}': {e}")
        return None


def extract_time_fields(card: V1Card) -> tuple[Optional[str], Optional[date], Optional[date], Optional[bool]]:
    """Extract time fields from card."""
    time_obj = card.time
    
    if isinstance(time_obj, str):
        return time_obj, None, None, None
    
    if not isinstance(time_obj, TimeInfo):
        return None, None, None, None
    
    return (
        time_obj.text,
        parse_date_field(time_obj.start),
        parse_date_field(time_obj.end),
        time_obj.ongoing,
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
    company = card.company or card.organization
    
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
    if not card.roles:
        return None, None
    
    first_role = card.roles[0]
    title = first_role.label[:255].strip() if first_role.label else None
    seniority = first_role.seniority[:255].strip() if first_role.seniority else None
    
    return title, seniority


def extract_search_phrases(card: V1Card) -> list[str]:
    """Extract search phrases from card index."""
    if not card.index:
        return []
    
    return [p.strip() for p in card.index.search_phrases if p.strip()][:50]


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
        "domain": None,
        "sub_domain": None,
        "company_name": company,
        "company_type": None,
        "start_date": start_date,
        "end_date": end_date,
        "is_current": is_ongoing if isinstance(is_ongoing, bool) else None,
        "location": location_text[:255] if location_text else None,
        "employment_type": None,
        "summary": summary,
        "intent_primary": card.intent,
        "intent_secondary": [],
        "seniority_level": role_seniority,
        "confidence_score": None,
        "visibility": False,
        "search_phrases": search_phrases,
        "search_document": search_document,
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
        
        return {
            "id": card.id,
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
        return {
            "id": card.id,
            "title": card.title,
            "context": card.summary,
            "tags": [],
            "headline": card.title,
            "summary": card.summary,
            "topics": [],
            "time_range": None,
            "role_title": card.normalized_role,
            "company": card.company_name,
            "location": card.location,
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

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