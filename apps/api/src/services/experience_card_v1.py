"""Experience Card v1 pipeline: atomize → parent extract → child gen → validate."""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import RawExperience, ExperienceCard
from src.schemas import RawExperienceCreate
from src.providers import get_chat_provider, ChatServiceError
from src.prompts.experience_card_v1 import (
    PROMPT_ATOMIZER,
    PROMPT_PARENT_EXTRACTOR,
    PROMPT_CHILD_GENERATOR,
    PROMPT_VALIDATOR,
    fill_prompt,
)

_DEBUG_LOG_PATH = r"c:\Users\Lenovo\Desktop\Search_Engine\.cursor\debug.log"


def _debug_log(payload: dict) -> None:
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as _f:
            _f.write(json.dumps(payload) + "\n")
    except Exception:
        pass
    try:
        print(json.dumps(payload))
    except Exception:
        pass


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
    """Map a v1 card dict (parent or child) to ExperienceCard column values for persistence."""
    # region agent log
    _debug_log(
        {
            "sessionId": "debug-session",
            "runId": "pre-fix",
            "hypothesisId": "H1",
            "location": "experience_card_v1.py:_v1_card_to_experience_card_fields:entry",
            "message": "card shape and time field type",
            "data": {
                "card_keys": list(card.keys()) if isinstance(card, dict) else None,
                "time_type": type(card.get("time")).__name__ if isinstance(card, dict) else None,
            },
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
    )
    # endregion agent log
    time_obj = card.get("time") or {}
    # region agent log
    _debug_log(
        {
            "sessionId": "debug-session",
            "runId": "pre-fix",
            "hypothesisId": "H2",
            "location": "experience_card_v1.py:_v1_card_to_experience_card_fields:time_obj",
            "message": "time_obj type and value shape",
            "data": {
                "time_obj_type": type(time_obj).__name__,
                "time_obj_is_list": isinstance(time_obj, list),
                "time_obj_keys": list(time_obj.keys()) if isinstance(time_obj, dict) else None,
                "time_obj_len": len(time_obj) if isinstance(time_obj, list) else None,
            },
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
    )
    # endregion agent log
    time_text = time_obj.get("text")
    if not time_text and (time_obj.get("start") or time_obj.get("end")):
        time_text = f"{time_obj.get('start', '')}-{time_obj.get('end', '')}".strip("-")
    location = card.get("location") or {}
    roles = card.get("roles") or []
    # region agent log
    _debug_log(
        {
            "sessionId": "debug-session",
            "runId": "pre-fix",
            "hypothesisId": "H3",
            "location": "experience_card_v1.py:_v1_card_to_experience_card_fields:roles_topics",
            "message": "roles/topics types",
            "data": {
                "roles_type": type(roles).__name__,
                "topics_type": type((card.get("topics") or [])).__name__,
            },
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
    )
    # endregion agent log
    role_title = roles[0].get("label") if roles and isinstance(roles[0], dict) else None
    topics = card.get("topics") or []
    tags = [t.get("label") for t in topics if isinstance(t, dict) and t.get("label")]

    return {
        # Always generate fresh IDs for persistence to avoid LLM collisions.
        "id": str(uuid.uuid4()),
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
        "company": (location.get("city") or "")[:255] if location else None,
        "team": None,
        "role_title": (role_title or "")[:255] if role_title else None,
        "time_range": (time_text or "")[:100] if time_text else None,
        "embedding": None,
    }


async def _persist_v1_family(
    db: AsyncSession,
    person_id: str,
    raw_experience_id: str,
    family: dict,
) -> None:
    """Persist one v1 card family (parent + children) as ExperienceCard rows with status DRAFT."""
    parent = family.get("parent") or {}
    children = family.get("children") or []
    for card in [parent] + children:
        if not card:
            continue
        kwargs = _v1_card_to_experience_card_fields(card, person_id, raw_experience_id)
        ec = ExperienceCard(**kwargs)
        db.add(ec)
    await db.flush()


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
    raw_experience_id = raw.id
    draft_set_id = str(uuid.uuid4())

    chat = get_chat_provider()

    # 1. Atomize
    # region agent log
    _debug_log(
        {
            "sessionId": "debug-session",
            "runId": "pre-fix",
            "hypothesisId": "H6",
            "location": "experience_card_v1.py:run_draft_v1_pipeline:atomize_start",
            "message": "atomize step start",
            "data": {"raw_text_len": len(body.raw_text or "")},
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
    )
    # endregion agent log
    prompt = fill_prompt(PROMPT_ATOMIZER, user_text=body.raw_text)
    try:
        response = await chat.chat(prompt, max_tokens=1024)
        atoms = _parse_json_array(response)
    except (ValueError, json.JSONDecodeError) as e:
        # region agent log
        _debug_log(
            {
                "sessionId": "debug-session",
                "runId": "pre-fix",
                "hypothesisId": "H6",
                "location": "experience_card_v1.py:run_draft_v1_pipeline:atomize_error",
                "message": "atomize parse error",
                "data": {"error": type(e).__name__},
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
        )
        # endregion agent log
        raise ChatServiceError("Atomizer returned invalid JSON.") from e

    if not atoms:
        return draft_set_id, raw_experience_id, []

    card_families: list[dict] = []

    for atom in atoms:
        raw_span = atom.get("raw_text_span") or atom.get("raw_text") or ""
        if not raw_span:
            continue

        # 2. Parent extractor
        # region agent log
        _debug_log(
            {
                "sessionId": "debug-session",
                "runId": "pre-fix",
                "hypothesisId": "H6",
                "location": "experience_card_v1.py:run_draft_v1_pipeline:parent_start",
                "message": "parent extractor start",
                "data": {"raw_span_len": len(raw_span)},
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
        )
        # endregion agent log
        prompt = fill_prompt(
            PROMPT_PARENT_EXTRACTOR,
            atom_text=raw_span,
            person_id=person_id,
        )
        try:
            response = await chat.chat(prompt, max_tokens=2048)
            parent = _parse_json_object(response)
        except (ValueError, json.JSONDecodeError) as e:
            # region agent log
            _debug_log(
                {
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "H6",
                    "location": "experience_card_v1.py:run_draft_v1_pipeline:parent_error",
                    "message": "parent parse error",
                    "data": {"error": type(e).__name__},
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                }
            )
            # endregion agent log
            raise ChatServiceError("Parent extractor returned invalid JSON.") from e

        parent = _inject_parent_metadata(parent, person_id)
        parent_id = parent["id"]

        # 3. Child generator
        # region agent log
        _debug_log(
            {
                "sessionId": "debug-session",
                "runId": "pre-fix",
                "hypothesisId": "H6",
                "location": "experience_card_v1.py:run_draft_v1_pipeline:child_start",
                "message": "child generator start",
                "data": {"parent_id_present": bool(parent_id)},
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
        )
        # endregion agent log
        prompt = fill_prompt(
            PROMPT_CHILD_GENERATOR,
            parent_id=parent_id,
            parent_card_json=json.dumps(parent),
        )
        try:
            response = await chat.chat(prompt, max_tokens=2048)
            children = _parse_json_array(response)
        except (ValueError, json.JSONDecodeError) as e:
            # region agent log
            _debug_log(
                {
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "H6",
                    "location": "experience_card_v1.py:run_draft_v1_pipeline:child_error",
                    "message": "child parse error",
                    "data": {"error": type(e).__name__},
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                }
            )
            # endregion agent log
            raise ChatServiceError("Child generator returned invalid JSON.") from e

        children = [_inject_child_metadata(c, parent_id) for c in children]

        # 4. Validator
        # region agent log
        _debug_log(
            {
                "sessionId": "debug-session",
                "runId": "pre-fix",
                "hypothesisId": "H6",
                "location": "experience_card_v1.py:run_draft_v1_pipeline:validator_start",
                "message": "validator start",
                "data": {"children_count": len(children)},
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
        )
        # endregion agent log
        combined = {"parent": parent, "children": children}
        prompt = fill_prompt(
            PROMPT_VALIDATOR,
            parent_and_children_json=json.dumps(combined),
        )
        try:
            response = await chat.chat(prompt, max_tokens=4096)
            validated = _parse_json_object(response)
        except (ValueError, json.JSONDecodeError) as e:
            # region agent log
            _debug_log(
                {
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "H6",
                    "location": "experience_card_v1.py:run_draft_v1_pipeline:validator_error",
                    "message": "validator parse error",
                    "data": {"error": type(e).__name__},
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                }
            )
            # endregion agent log
            raise ChatServiceError("Validator returned invalid JSON.") from e

        v_parent = validated.get("parent") or parent
        v_children = validated.get("children") or children
        family = {"parent": v_parent, "children": v_children}
        card_families.append(family)
        await _persist_v1_family(db, person_id, raw_experience_id, family)

    return draft_set_id, raw_experience_id, card_families
