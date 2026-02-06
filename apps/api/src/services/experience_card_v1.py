"""Experience Card v1 pipeline: atomize → parent extract → child gen → validate."""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import RawExperience, ExperienceCard, ExperienceCardChild
from src.schemas import RawExperienceCreate
from src.providers import get_chat_provider, ChatServiceError
from src.prompts.experience_card_v1 import (
    PROMPT_REWRITE,
    PROMPT_ATOMIZER,
    PROMPT_PARENT_AND_CHILDREN,
    PROMPT_VALIDATOR,
    fill_prompt,
)


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


def _inject_child_metadata(child: dict, parent_id: str) -> dict:
    """Ensure child has id, parent_id, depth=1, timestamps."""
    now = datetime.now(timezone.utc).isoformat()
    child = dict(child)
    child.setdefault("id", str(uuid.uuid4()))
    child["parent_id"] = parent_id
    child["depth"] = 1
    child.setdefault("created_at", now)
    child.setdefault("updated_at", now)
    return child


def _v1_card_to_experience_card_fields(
    card: dict,
    person_id: str,
    raw_experience_id: str,
) -> dict:
    """Map a v1 parent card dict to ExperienceCard column values for persistence.
    Does not set id; DB generates it. Company: use only organization/company from model, not location.
    """
    time_obj = card.get("time") or {}
    if isinstance(time_obj, str):
        time_text = time_obj
    elif isinstance(time_obj, dict):
        time_text = time_obj.get("text")
        if not time_text and (time_obj.get("start") or time_obj.get("end")):
            time_text = f"{time_obj.get('start', '')}-{time_obj.get('end', '')}".strip("-")
    else:
        time_text = None
    location = card.get("location") or {}
    roles = card.get("roles") or []
    role_title = roles[0].get("label") if roles and isinstance(roles[0], dict) else None
    topics = card.get("topics") or []
    tags = [t.get("label") for t in topics if isinstance(t, dict) and t.get("label")]

    # Company: only from organization/company extracted by model; do NOT use location for company.
    company_raw = card.get("company") or card.get("organization")
    company = (company_raw or "")[:255].strip() or None if company_raw else None

    # Location: city/place from model's location object (separate from company).
    loc_obj = card.get("location") or {}
    if isinstance(loc_obj, dict):
        location_raw = loc_obj.get("city") or loc_obj.get("text") or loc_obj.get("name")
    else:
        location_raw = str(loc_obj) if loc_obj else None
    location = (location_raw or "")[:255].strip() or None if location_raw else None

    return {
        "person_id": person_id,
        "raw_experience_id": raw_experience_id,
        "status": ExperienceCard.DRAFT,
        "human_edited": False,
        "locked": False,
        "title": (card.get("headline") or "")[:500],
        "context": (card.get("summary") or card.get("raw_text") or "")[:10000],
        "constraints": None,
        "decisions": None,
        "outcome": None,
        "tags": tags[:50] if tags else [],
        "company": company,
        "team": None,
        "role_title": (role_title or "")[:255] if role_title else None,
        "time_range": (time_text or "")[:100] if time_text else None,
        "location": location,
        "embedding": None,
    }


def _v1_child_card_to_fields(
    card: dict,
    *,
    person_id: str,
    raw_experience_id: str,
    parent_id: str,
) -> dict:
    """Map a v1 child card dict to ExperienceCardChild column values for persistence."""
    time_obj = card.get("time") or {}
    if isinstance(time_obj, str):
        time_text = time_obj
    elif isinstance(time_obj, dict):
        time_text = time_obj.get("text")
        if not time_text and (time_obj.get("start") or time_obj.get("end")):
            time_text = f"{time_obj.get('start', '')}-{time_obj.get('end', '')}".strip("-")
    else:
        time_text = None

    roles = card.get("roles") or []
    role_title = roles[0].get("label") if roles and isinstance(roles[0], dict) else None
    topics = card.get("topics") or []
    tags = [t.get("label") for t in topics if isinstance(t, dict) and t.get("label")]

    company_raw = card.get("company") or card.get("organization")
    company = (company_raw or "")[:255].strip() or None if company_raw else None

    loc_obj = card.get("location") or {}
    if isinstance(loc_obj, dict):
        location_raw = loc_obj.get("city") or loc_obj.get("text") or loc_obj.get("name")
    else:
        location_raw = str(loc_obj) if loc_obj else None
    location = (location_raw or "")[:255].strip() or None if location_raw else None

    return {
        "parent_id": parent_id,
        "person_id": person_id,
        "raw_experience_id": raw_experience_id,
        "depth": card.get("depth") or 1,
        "relation_type": card.get("relation_type"),
        "status": ExperienceCard.DRAFT,
        "human_edited": False,
        "locked": False,
        "title": (card.get("headline") or "")[:500],
        "context": (card.get("summary") or card.get("raw_text") or "")[:10000],
        "constraints": None,
        "decisions": None,
        "outcome": None,
        "tags": tags[:50] if tags else [],
        "company": company,
        "team": None,
        "role_title": (role_title or "")[:255] if role_title else None,
        "time_range": (time_text or "")[:100] if time_text else None,
        "location": location,
        # Child-only rich fields (store raw JSON structures)
        "tooling": card.get("tooling"),
        "entities": card.get("entities"),
        "actions": card.get("actions"),
        "outcomes": card.get("outcomes"),
        "topics": card.get("topics"),
        "evidence": card.get("evidence"),
        "embedding": None,
    }


def _draft_card_to_family_item(card: ExperienceCard | ExperienceCardChild) -> dict:
    """Serialize a persisted draft ExperienceCard/Child for API response (id, title, context, tags + UI fields)."""
    tags = card.tags or []
    return {
        "id": card.id,
        "title": card.title,
        "context": card.context,
        "tags": tags,
        "headline": card.title,
        "summary": card.context,
        "topics": [{"label": t} for t in tags],
        "time_range": card.time_range,
        "role_title": card.role_title,
        "company": card.company,
        "location": card.location,
    }


async def _persist_v1_family(
    db: AsyncSession,
    person_id: str,
    raw_experience_id: str,
    family: dict,
) -> tuple[ExperienceCard, list[ExperienceCardChild]]:
    """Persist one v1 card family (parent + children) as DRAFT; return (parent, children) with server-generated ids."""
    parent = family.get("parent") or {}
    children = family.get("children") or []
    parent_kw = _v1_card_to_experience_card_fields(parent, person_id, raw_experience_id)
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
    Rewrite messy input into clear English for easier extraction.
    Raises ChatServiceError on LLM failure.
    """
    if not raw_text or not raw_text.strip():
        return raw_text
    chat = get_chat_provider()
    prompt = fill_prompt(PROMPT_REWRITE, user_text=raw_text)
    rewritten = await chat.chat(prompt, max_tokens=2048)
    return rewritten.strip() or raw_text


async def run_draft_v1_pipeline(
    db: AsyncSession,
    person_id: str,
    body: RawExperienceCreate,
) -> tuple[str, str, list[dict]]:
    """
    Run atomizer → parent extractor → child generator → validator per atom.
    Returns (draft_set_id, raw_experience_id, card_families) where each
    card_family is {"parent": {...}, "children": [...]}.
    Raises ChatServiceError on LLM/parse errors.
    """
    raw = RawExperience(person_id=person_id, raw_text=body.raw_text)
    db.add(raw)
    await db.flush()
    raw_experience_id = str(raw.id)
    draft_set_id = raw_experience_id  # one raw experience = one draft set for commit

    chat = get_chat_provider()

    # 0. Rewrite (global normalization before atomizing)
    # Keep the raw experience as the original user input for persistence/auditing,
    # but feed the rewritten version into the atomizer to improve splitting.
    rewritten_text = body.raw_text
    try:
        rewrite_prompt = fill_prompt(PROMPT_REWRITE, user_text=body.raw_text)
        rewritten = await chat.chat(rewrite_prompt, max_tokens=2048)
        rewritten_text = rewritten.strip() or body.raw_text
    except Exception:
        # Best effort: if rewrite fails for any reason, continue with raw text.
        rewritten_text = body.raw_text

    # 1. Atomize
    prompt = fill_prompt(PROMPT_ATOMIZER, user_text=rewritten_text)
    try:
        response = await chat.chat(prompt, max_tokens=1024)
        atoms = _parse_json_array(response)
    except (ValueError, json.JSONDecodeError) as e:
        raise ChatServiceError("Atomizer returned invalid JSON.") from e

    if not atoms:
        return draft_set_id, raw_experience_id, []

    card_families: list[dict] = []

    for atom in atoms:
        raw_span = atom.get("raw_text_span") or atom.get("raw_text") or ""
        if not raw_span:
            continue
        # Prefer cleaned_text from atomizer (normalized); fall back to raw_span
        atom_text = atom.get("cleaned_text") or raw_span

        # 2. Parent + children in one prompt
        prompt = fill_prompt(
            PROMPT_PARENT_AND_CHILDREN,
            atom_text=atom_text,
            person_id=person_id,
        )
        try:
            response = await chat.chat(prompt, max_tokens=4096)
            combined = _parse_json_object(response)
        except (ValueError, json.JSONDecodeError) as e:
            raise ChatServiceError("Parent+children extractor returned invalid JSON.") from e

        parent = combined.get("parent") or {}
        children = combined.get("children") or []
        if not isinstance(children, list):
            children = []
        parent = _inject_parent_metadata(parent, person_id)
        parent_id = parent["id"]
        children = [_inject_child_metadata(c, parent_id) for c in children]

        # 3. Validator
        combined = {"parent": parent, "children": children}
        prompt = fill_prompt(
            PROMPT_VALIDATOR,
            parent_and_children_json=json.dumps(combined),
        )
        try:
            response = await chat.chat(prompt, max_tokens=4096)
            validated = _parse_json_object(response)
        except (ValueError, json.JSONDecodeError) as e:
            raise ChatServiceError("Validator returned invalid JSON.") from e

        v_parent = validated.get("parent") or parent
        v_children = validated.get("children") or children
        family = {"parent": v_parent, "children": v_children}
        parent_ec, child_ecs = await _persist_v1_family(db, person_id, raw_experience_id, family)
        card_families.append({
            "parent": _draft_card_to_family_item(parent_ec),
            "children": [_draft_card_to_family_item(c) for c in child_ecs],
        })

    return draft_set_id, raw_experience_id, card_families
