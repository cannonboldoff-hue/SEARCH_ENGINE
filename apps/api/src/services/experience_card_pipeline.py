"""Experience Card pipeline: rewrite+cleanup → extract-all → validate-all."""

import json
import logging
import time
import uuid
from datetime import datetime, timezone, date

logger = logging.getLogger(__name__)

# #region agent log
_DEBUG_LOG_PATH = "c:\\Users\\Lenovo\\Desktop\\Search_Engine\\.cursor\\debug.log"
def _debug_log(location: str, message: str, data: dict, hypothesis_id: str = ""):
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"location": location, "message": message, "data": data, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "hypothesisId": hypothesis_id}, default=str) + "\n")
    except Exception:
        pass
# #endregion

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


def _strip_json_block(text: str) -> str:
    """Remove markdown code fence around JSON if present."""
    s = text.strip()
    if "```" in s:
        parts = s.split("```")
        for i, p in enumerate(parts):
            candidate = p.replace("json", "").strip()
            if candidate.startswith("{") or candidate.startswith("["):
                return candidate
        return parts[1].replace("json", "").strip() if len(parts) > 1 else s
    return s


def _best_effort_json_parse(text: str) -> object:
    """Try to decode JSON anywhere in the text if direct parsing fails."""
    s = text.strip()
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(s):
        if ch not in "[{":
            continue
        try:
            obj, _ = decoder.raw_decode(s[idx:])
            return obj
        except json.JSONDecodeError:
            continue
    raise json.JSONDecodeError("No JSON object found", s, 0)


def _parse_json_array(text: str) -> list:
    if not text or not text.strip():
        raise json.JSONDecodeError(
            "Empty response (LLM may have failed or been rate-limited).",
            text or "",
            0,
        )
    raw = _strip_json_block(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = _best_effort_json_parse(text)
    return data if isinstance(data, list) else [data]


def _parse_json_object(text: str) -> dict:
    raw = _strip_json_block(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = _best_effort_json_parse(text)
    if isinstance(data, list) and data:
        candidate = data[0]
        if isinstance(candidate, dict):
            return candidate
    if not isinstance(data, dict):
        raise json.JSONDecodeError("Expected JSON object", raw, 0)
    return data


def _parse_families_from_response(text: str) -> list[dict]:
    """Parse LLM response into a list of family dicts (each {parent, children}).
    Handles: wrapper {"parents": [...]}, single family {parent, children}, or top-level array of families.
    """
    # #region agent log
    _debug_log("experience_card_pipeline:_parse_families_from_response:entry", "parse_families_entry", {"text_len": len(text or ""), "text_prefix": (text or "")[:200], "text_empty": not (text or "").strip()}, "H1")
    # #endregion
    raw = _strip_json_block(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = _best_effort_json_parse(text)
    if isinstance(data, list):
        out = [f for f in data if isinstance(f, dict) and "parent" in f]
    elif isinstance(data, dict):
        if "parents" in data and isinstance(data["parents"], list):
            out = data["parents"]
        elif "parent" in data:
            out = [data]
        else:
            out = []
    else:
        out = []
    # #region agent log
    _debug_log("experience_card_pipeline:_parse_families_from_response:exit", "parse_families_exit", {"families_count": len(out), "root_type": type(data).__name__, "has_parents_key": isinstance(data, dict) and "parents" in data}, "H1")
    # #endregion
    return out


def _inject_parent_metadata(parent: dict, person_id: str) -> dict:
    """Ensure parent has id, person_id, created_by, created_at, updated_at."""
    now = datetime.now(timezone.utc).isoformat()
    parent = dict(parent)
    parent.setdefault("id", str(uuid.uuid4()))
    parent["person_id"] = person_id
    parent["created_by"] = person_id
    parent.setdefault("created_at", now)
    parent.setdefault("updated_at", now)
    parent["parent_id"] = None
    parent["depth"] = 0
    parent["relation_type"] = None
    return parent


def _inject_child_metadata(child: dict, parent_id: str, person_id: str) -> dict:
    """Ensure child has id, parent_id, depth=1, timestamps, and ownership."""
    now = datetime.now(timezone.utc).isoformat()
    child = dict(child)
    child.setdefault("id", str(uuid.uuid4()))
    child["person_id"] = person_id
    child["created_by"] = person_id
    child["parent_id"] = parent_id
    child["depth"] = 1
    child.setdefault("created_at", now)
    child.setdefault("updated_at", now)
    return child


def _normalize_whitespace(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    if len(text) == 7 and text[4] == "-":
        text = f"{text}-01"
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _extract_time_fields(card: dict) -> tuple[str | None, date | None, date | None, bool | None]:
    time_obj = card.get("time") or {}
    if isinstance(time_obj, str):
        return time_obj, None, None, None
    if not isinstance(time_obj, dict):
        return None, None, None, None
    time_text = time_obj.get("text")
    start_date = _parse_date(time_obj.get("start"))
    end_date = _parse_date(time_obj.get("end"))
    is_ongoing = time_obj.get("ongoing")
    return time_text, start_date, end_date, is_ongoing


def _extract_location_fields(card: dict) -> tuple[str | None, str | None, str | None]:
    loc_obj = card.get("location") or {}
    if isinstance(loc_obj, str):
        return loc_obj, None, None
    if not isinstance(loc_obj, dict):
        return None, None, None
    location_text = loc_obj.get("text") or loc_obj.get("city") or loc_obj.get("name")
    city = loc_obj.get("city")
    country = loc_obj.get("country")
    return location_text, city, country


def _extract_search_phrases(card: dict) -> list[str]:
    index_obj = card.get("index") or {}
    phrases = index_obj.get("search_phrases") if isinstance(index_obj, dict) else None
    if not phrases:
        return []
    return [p for p in phrases if isinstance(p, str) and p.strip()]


def _extract_company(card: dict) -> str | None:
    company_raw = card.get("company") or card.get("organization")
    if not company_raw:
        entities = card.get("entities") or []
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            if entity.get("type") in {"company", "organization"} and entity.get("name"):
                company_raw = entity.get("name")
                break
    company = (company_raw or "")[:255].strip()
    return company or None


def _extract_team(card: dict) -> str | None:
    team_raw = card.get("team")
    if not team_raw:
        entities = card.get("entities") or []
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            if entity.get("type") == "team" and entity.get("name"):
                team_raw = entity.get("name")
                break
    team = (team_raw or "")[:255].strip()
    return team or None


def _extract_role_title(card: dict) -> str | None:
    roles = card.get("roles") or []
    if roles and isinstance(roles[0], dict):
        role_title = roles[0].get("label")
    else:
        role_title = None
    return (role_title or "")[:255].strip() or None


def _extract_role_seniority(card: dict) -> str | None:
    roles = card.get("roles") or []
    if roles and isinstance(roles[0], dict):
        seniority = roles[0].get("seniority")
    else:
        seniority = None
    return (seniority or "")[:255].strip() or None


def _normalize_card_title(headline: str | None, raw_text: str | None, summary: str | None) -> str:
    """Return a user-friendly title; avoid empty or generic 'Unspecified experience'."""
    h = (headline or "").strip()
    if h and h.lower() != "unspecified experience":
        return h[:500]
    for src in (summary, raw_text):
        if src and src.strip():
            first_line = src.strip().split("\n")[0].strip()[:80]
            if first_line:
                return first_line
    return "Experience"


def _v1_card_to_experience_card_fields(
    card: dict,
    *,
    person_id: str,
    raw_experience_id: str,
    draft_set_id: str,
) -> dict:
    """Map a v1 parent card dict to ExperienceCard column values for persistence."""
    time_text, start_date, end_date, is_ongoing = _extract_time_fields(card)
    location_text, city, country = _extract_location_fields(card)
    company = _extract_company(card)
    role_title = _extract_role_title(card)
    role_seniority = _extract_role_seniority(card)
    raw_text = (card.get("raw_text") or "").strip() or None
    summary = (card.get("summary") or "")[:10000]
    title = _normalize_card_title(card.get("headline"), raw_text, summary)

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
        "location": (location_text or "")[:255] if location_text else None,
        "employment_type": None,
        "summary": summary,
        "intent_primary": card.get("intent"),
        "intent_secondary": [],
        "seniority_level": role_seniority,
        "confidence_score": None,
        "visibility": False,
    }


def _v1_child_card_to_fields(
    card: dict,
    *,
    person_id: str,
    raw_experience_id: str,
    draft_set_id: str,
    parent_id: str,
) -> dict:
    """Map a v1 child card dict to ExperienceCardChild column values for persistence.

    Aligns with domain: child_type must be one of ALLOWED_CHILD_TYPES;
    relation_type (ChildRelationType) is stored in value/extra for schema alignment.
    - child_type: from card, validated against domain.ALLOWED_CHILD_TYPES
    - label: optional label (e.g., headline or summary)
    - value: JSON dimension container with rich fields + relation_type
    - search_phrases: array of search phrases
    """
    time_text, start_date, end_date, is_ongoing = _extract_time_fields(card)
    location_text, city, country = _extract_location_fields(card)
    topics = card.get("topics") or []
    tags = [t.get("label") for t in topics if isinstance(t, dict) and t.get("label")]
    search_phrases = _extract_search_phrases(card)
    company = _extract_company(card)
    team = _extract_team(card)
    role_title = _extract_role_title(card)
    raw_text = (card.get("raw_text") or "").strip() or None
    summary = (card.get("summary") or "")[:10000]

    # child_type must be one of ALLOWED_CHILD_TYPES (domain); relation_type is ChildRelationType (schema)
    child_type = card.get("child_type") if isinstance(card.get("child_type"), str) else None
    if not child_type or child_type not in ALLOWED_CHILD_TYPES or len(child_type) > 50:
        child_type = ALLOWED_CHILD_TYPES[0]  # "skills"

    # Use headline as label, or summary if no headline; avoid "Unspecified experience"
    label = _normalize_card_title(card.get("headline"), raw_text, summary)[:255]

    # Build the dimension container (value JSON) with all rich fields
    dimension_container = {
        "headline": card.get("headline"),
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
        "roles": [{"label": role_title, "seniority": None}] if role_title else [],
        "topics": topics,
        "entities": card.get("entities", []),
        "actions": card.get("actions", []),
        "outcomes": card.get("outcomes", []),
        "tooling": card.get("tooling"),
        "evidence": card.get("evidence", []),
        "company": company,
        "team": team,
        "tags": tags[:50] if tags else [],
        "depth": card.get("depth") or 1,
        "relation_type": card.get("relation_type"),
    }

    # Build search document from key fields for embedding/search
    search_doc_parts = [
        card.get("headline") or "",
        summary or "",
        role_title or "",
        company or "",
        team or "",
        location_text or "",
        " ".join(tags[:10]) if tags else "",
    ]
    search_document = " ".join(filter(None, search_doc_parts)).strip() or None

    return {
        "parent_experience_id": parent_id,
        "person_id": person_id,
        "raw_experience_id": raw_experience_id,
        "draft_set_id": draft_set_id,
        "child_type": child_type,
        "label": label,
        "value": dimension_container,
        "confidence_score": None,  # Can be extracted from card if available
        "search_phrases": search_phrases[:50] if search_phrases else [],
        "search_document": search_document,
        "embedding": None,  # Will be populated later during embedding step
        "extra": {
            "intent": card.get("intent"),
            "created_by": card.get("created_by"),
        } if card.get("intent") or card.get("created_by") else None,
    }


def _draft_card_to_family_item(card: ExperienceCard | ExperienceCardChild) -> dict:
    """Serialize a persisted draft ExperienceCard/Child for API response (id, title, context, tags + UI fields)."""
    if isinstance(card, ExperienceCardChild):
        # Extract from new ExperienceCardChild structure
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
        # ExperienceCard structure (unchanged)
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


async def _persist_v1_family(
    db: AsyncSession,
    person_id: str,
    raw_experience_id: str,
    draft_set_id: str,
    family: dict,
) -> tuple[ExperienceCard, list[ExperienceCardChild]]:
    """Persist one v1 card family (parent + children) as DRAFT; return (parent, children) with server-generated ids."""
    parent = family.get("parent") or {}
    children = family.get("children") or []
    parent_kw = _v1_card_to_experience_card_fields(
        parent,
        person_id=person_id,
        raw_experience_id=raw_experience_id,
        draft_set_id=draft_set_id,
    )
    parent_ec = ExperienceCard(**parent_kw)
    db.add(parent_ec)
    await db.flush()
    await db.refresh(parent_ec)

    child_ecs: list[ExperienceCardChild] = []
    for card in children:
        if not card:
            continue
        kwargs = _v1_child_card_to_fields(
            card,
            person_id=person_id,
            raw_experience_id=raw_experience_id,
            draft_set_id=draft_set_id,
            parent_id=parent_ec.id,
        )
        ec = ExperienceCardChild(**kwargs)
        db.add(ec)
        child_ecs.append(ec)
    if child_ecs:
        await db.flush()
        for ec in child_ecs:
            await db.refresh(ec)
    return parent_ec, child_ecs


async def rewrite_raw_text(raw_text: str) -> str:
    """
    Rewrite + cleanup messy input into clear English for easier extraction.
    Raises HTTP 400 on empty input and ChatServiceError on LLM failure.
    """
    if not raw_text or not raw_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="raw_text is required")
    chat = get_chat_provider()
    prompt = fill_prompt(PROMPT_REWRITE, user_text=raw_text)
    rewritten = await chat.chat(prompt, max_tokens=2048)
    cleaned = _normalize_whitespace(rewritten.strip() or raw_text)
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="raw_text is required")
    return cleaned


async def _next_draft_run_version(db: AsyncSession, raw_experience_id: str, person_id: str) -> int:
    result = await db.execute(
        select(func.max(DraftSet.run_version)).where(
            DraftSet.raw_experience_id == raw_experience_id,
            DraftSet.person_id == person_id,
        )
    )
    max_version = result.scalar_one_or_none()
    return (max_version or 0) + 1


async def run_draft_v1_pipeline(
    db: AsyncSession,
    person_id: str,
    body: RawExperienceCreate,
) -> tuple[str, str, list[dict]]:
    """
    Run rewrite+cleanup → extract-all → validate-all (single pass each).
    Returns (draft_set_id, raw_experience_id, card_families) where each
    card_family is {"parent": {...}, "children": [...]}.
    Raises ChatServiceError on LLM/parse errors.
    """
    raw_text_original = body.raw_text or ""
    # #region agent log
    _debug_log("experience_card_pipeline:run_draft_v1:entry", "pipeline_entry", {"raw_len": len(raw_text_original), "raw_prefix": raw_text_original[:80]}, "H2")
    # #endregion
    raw_text_cleaned = await rewrite_raw_text(raw_text_original)
    # #region agent log
    _debug_log("experience_card_pipeline:run_draft_v1:after_rewrite", "after_rewrite", {"cleaned_len": len(raw_text_cleaned), "cleaned_prefix": raw_text_cleaned[:80]}, "H2")
    # #endregion
    raw = RawExperience(
        person_id=person_id,
        raw_text=raw_text_original,
        raw_text_original=raw_text_original,
        raw_text_cleaned=raw_text_cleaned,
    )
    db.add(raw)
    await db.flush()
    raw_experience_id = str(raw.id)
    run_version = await _next_draft_run_version(db, raw_experience_id, person_id)
    draft_set = DraftSet(
        person_id=person_id,
        raw_experience_id=raw.id,
        run_version=run_version,
    )
    db.add(draft_set)
    await db.flush()
    draft_set_id = str(draft_set.id)

    chat = get_chat_provider()

    # 2. Extraction (single pass)
    prompt = fill_prompt(
        PROMPT_EXTRACT_ALL_CARDS,
        user_text=raw_text_cleaned,
        person_id=person_id,
    )
    try:
        response = await chat.chat(prompt, max_tokens=8192)
        # #region agent log
        _debug_log("experience_card_pipeline:run_draft_v1:extractor_response", "extractor_response", {"response_len": len(response or ""), "response_empty": not (response or "").strip(), "response_prefix": (response or "")[:150]}, "H2")
        # #endregion
        families = _parse_families_from_response(response)
    except ChatServiceError:
        raise
    except (ValueError, json.JSONDecodeError) as e:
        # #region agent log
        _debug_log("experience_card_pipeline:run_draft_v1:extractor_parse_error", "extractor_parse_error", {"error": str(e)}, "H2")
        # #endregion
        msg = "Extractor returned invalid JSON (empty or non-JSON response). LLM may have failed or been rate-limited."
        raise ChatServiceError(msg) from e

    # #region agent log
    _debug_log("experience_card_pipeline:run_draft_v1:after_parse", "after_parse", {"families_count": len(families), "first_family_keys": list(families[0].keys()) if families else []}, "H3")
    # #endregion
    normalized_families: list[dict] = []
    for family in families:
        if not isinstance(family, dict):
            continue
        parent = family.get("parent") or {}
        children = family.get("children") or []
        if not isinstance(children, list):
            children = []
        parent = _inject_parent_metadata(parent, person_id)
        parent_id = parent["id"]
        children = [_inject_child_metadata(c, parent_id, person_id) for c in children if isinstance(c, dict)]
        normalized_families.append({"parent": parent, "children": children})

    # #region agent log
    _debug_log("experience_card_pipeline:run_draft_v1:after_normalize", "after_normalize", {"normalized_count": len(normalized_families)}, "H3")
    # #endregion
    if not normalized_families:
        # #region agent log
        _debug_log("experience_card_pipeline:run_draft_v1:early_return_empty", "early_return_no_families", {"draft_set_id": draft_set_id}, "H3")
        # #endregion
        return draft_set_id, raw_experience_id, []

    # 3. Validator (single pass over the entire set)
    prompt = fill_prompt(
        PROMPT_VALIDATE_ALL_CARDS,
        parent_and_children_json=json.dumps(
            {
                "raw_text_original": raw_text_original,
                "raw_text_cleaned": raw_text_cleaned,
                "parents": normalized_families,
            }
        ),
    )
    validator_used_fallback = False
    try:
        response = await chat.chat(prompt, max_tokens=8192)
        # #region agent log
        _debug_log("experience_card_pipeline:run_draft_v1:validator_response", "validator_response", {"response_len": len(response or ""), "response_empty": not (response or "").strip()}, "H4")
        # #endregion
        validated_families = _parse_families_from_response(response)
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("Validator returned invalid or empty JSON, using extractor output: %s", e)
        validator_used_fallback = True
        validated_families = normalized_families
        # #region agent log
        _debug_log("experience_card_pipeline:run_draft_v1:validator_fallback", "validator_fallback", {"error": str(e)}, "H4")
        # #endregion

    if not validated_families:
        validated_families = normalized_families
        # #region agent log
        _debug_log("experience_card_pipeline:run_draft_v1:validator_empty_use_normalized", "validator_empty", {}, "H4")
        # #endregion

    card_families: list[dict] = []
    parents_to_embed: list[ExperienceCard] = []
    children_to_embed: list[ExperienceCardChild] = []
    for family in validated_families:
        if not isinstance(family, dict):
            continue
        v_parent = family.get("parent") or {}
        v_children = family.get("children") or []
        if not isinstance(v_children, list):
            v_children = []
        parent_ec, child_ecs = await _persist_v1_family(
            db,
            person_id,
            raw_experience_id,
            draft_set_id,
            {"parent": v_parent, "children": v_children},
        )
        parents_to_embed.append(parent_ec)
        children_to_embed.extend(child_ecs)
        card_families.append({
            "parent": _draft_card_to_family_item(parent_ec),
            "children": [_draft_card_to_family_item(c) for c in child_ecs],
        })

    # #region agent log
    _debug_log("experience_card_pipeline:run_draft_v1:after_persist", "after_persist", {"card_families_count": len(card_families), "validator_used_fallback": validator_used_fallback}, "H5")
    # #endregion

    # 4. Embedding (parents + children)
    embed_texts: list[str] = []
    embed_targets: list[tuple[str, ExperienceCard | ExperienceCardChild]] = []

    for parent in parents_to_embed:
        parent_doc = _experience_card_search_document(parent)
        if parent_doc:
            embed_texts.append(parent_doc)
            embed_targets.append(("parent", parent))

    for child in children_to_embed:
        child_doc = child.search_document or ""
        if child_doc.strip():
            embed_texts.append(child_doc.strip())
            embed_targets.append(("child", child))

    if embed_texts:
        provider = get_embedding_provider()
        try:
            vectors = await provider.embed(embed_texts)
        except EmbeddingServiceError:
            raise
        if len(vectors) != len(embed_targets):
            raise EmbeddingServiceError("Embedding API returned unexpected number of vectors.")
        for (kind, obj), vec in zip(embed_targets, vectors):
            normalized = normalize_embedding(vec, dim=provider.dimension)
            if kind == "parent":
                obj.embedding = normalized
            else:
                obj.embedding = normalized
        await db.flush()

    # #region agent log
    _debug_log("experience_card_pipeline:run_draft_v1:exit", "pipeline_exit", {"card_families_count": len(card_families), "draft_set_id": draft_set_id}, "H6")
    # #endregion
    return draft_set_id, raw_experience_id, card_families
