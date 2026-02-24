"""Experience card and raw experience business logic."""

import asyncio
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ExperienceCard, ExperienceCardChild, RawExperience
from src.schemas import (
    ExperienceCardChildPatch,
    ExperienceCardCreate,
    ExperienceCardPatch,
    RawExperienceCreate,
)
from .experience_card_search_document import (
    build_child_search_document_from_value,
    build_parent_search_document,
)

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

MAX_CHILD_TAGS = 50

# Patch field names that map 1:1 from ExperienceCardPatch to ExperienceCard.
_CARD_PATCH_FIELDS = (
    "title",
    "normalized_role",
    "domain",
    "sub_domain",
    "company_name",
    "company_type",
    "start_date",
    "end_date",
    "is_current",
    "location",
    "employment_type",
    "summary",
    "raw_text",
    "intent_primary",
    "intent_secondary",
    "seniority_level",
    "confidence_score",
    "experience_card_visibility",
)


# -----------------------------------------------------------------------------
# Raw experience
# -----------------------------------------------------------------------------


async def create_raw_experience(
    db: AsyncSession,
    person_id: str,
    body: RawExperienceCreate,
) -> RawExperience:
    """Create a raw experience record."""
    raw = RawExperience(
        person_id=person_id,
        raw_text=body.raw_text,
        raw_text_original=body.raw_text,
        raw_text_cleaned=body.raw_text,
    )
    db.add(raw)
    await db.flush()
    await db.refresh(raw)
    return raw


# -----------------------------------------------------------------------------
# Experience card CRUD
# -----------------------------------------------------------------------------


async def create_experience_card(
    db: AsyncSession,
    person_id: str,
    body: ExperienceCardCreate,
) -> ExperienceCard:
    """Create an experience card from schema (schema-driven)."""
    data = body.model_dump()
    data["user_id"] = person_id
    data["intent_secondary"] = data.get("intent_secondary") or []
    if data.get("experience_card_visibility") is None:
        data["experience_card_visibility"] = True
    card = ExperienceCard(**data)
    db.add(card)
    await db.flush()
    await db.refresh(card)
    return card


async def get_card_for_user(
    db: AsyncSession,
    card_id: str,
    person_id: str,
) -> ExperienceCard | None:
    """Fetch an experience card by id if it belongs to the user."""
    result = await db.execute(
        select(ExperienceCard).where(
            ExperienceCard.id == card_id,
            ExperienceCard.user_id == person_id,
        )
    )
    return result.scalar_one_or_none()


# -----------------------------------------------------------------------------
# Patch application (in-place; keeps search_document in sync)
# -----------------------------------------------------------------------------


def _apply_nested_text(value: dict, key: str, text: str) -> None:
    """Ensure value[key] is a dict and set value[key]['text'] = text."""
    obj = value.get(key)
    if not isinstance(obj, dict):
        obj = {}
    obj["text"] = text
    value[key] = obj


def apply_card_patch(card: ExperienceCard, body: ExperienceCardPatch) -> None:
    """Apply patch fields to card in place. Rebuilds search_document only when something changed."""
    changed = False
    for field in _CARD_PATCH_FIELDS:
        new_val = getattr(body, field, None)
        if new_val is not None:
            setattr(card, field, new_val)
            changed = True
    if changed:
        card.search_document = build_parent_search_document(card)


def apply_child_patch(
    child: ExperienceCardChild,
    body: ExperienceCardChildPatch,
) -> None:
    """
    Apply patch fields to ExperienceCardChild in place.

    Updates both child.label (title/headline) and child.value (dimension container
    used by the draft-v1 child DTO). Rebuilds search_document only when something changed.
    """
    value = child.value if isinstance(child.value, dict) else {}
    changed = False

    if body.title is not None:
        child.label = body.title
        value["headline"] = body.title
        changed = True

    if body.summary is not None:
        value["summary"] = body.summary
        changed = True

    if body.tags is not None:
        tags = [str(t).strip() for t in body.tags if str(t).strip()][:MAX_CHILD_TAGS]
        value["tags"] = tags
        value["topics"] = [{"label": t} for t in tags]
        changed = True

    if body.time_range is not None:
        _apply_nested_text(value, "time", body.time_range)
        changed = True

    if body.location is not None:
        _apply_nested_text(value, "location", body.location)
        changed = True

    child.value = value
    if changed:
        child.search_document = build_child_search_document_from_value(child.label, value)


# -----------------------------------------------------------------------------
# Listing
# -----------------------------------------------------------------------------


async def list_my_cards(
    db: AsyncSession,
    person_id: str,
) -> list[ExperienceCard]:
    """List experience cards for the user, newest first."""
    q = (
        select(ExperienceCard)
        .where(
            ExperienceCard.user_id == person_id,
            ExperienceCard.experience_card_visibility.is_(True),
        )
        .order_by(ExperienceCard.created_at.desc())
    )
    result = await db.execute(q)
    return result.scalars().all()


async def list_my_children(
    db: AsyncSession,
    person_id: str,
) -> list[ExperienceCardChild]:
    """List all experience card children for the user."""
    q = select(ExperienceCardChild).where(ExperienceCardChild.person_id == person_id)
    result = await db.execute(q)
    return result.scalars().all()


async def list_my_card_families(
    db: AsyncSession,
    person_id: str,
) -> list[tuple[ExperienceCard, list[ExperienceCardChild]]]:
    """List experience cards with their children grouped by parent."""
    parents, children = await asyncio.gather(
        list_my_cards(db, person_id),
        list_my_children(db, person_id),
    )
    by_parent: dict[str, list[ExperienceCardChild]] = defaultdict(list)
    for c in children:
        by_parent[c.parent_experience_id].append(c)
    return [(p, by_parent.get(p.id, [])) for p in parents]


# -----------------------------------------------------------------------------
# Service facade (for dependency injection)
# -----------------------------------------------------------------------------


class ExperienceCardService:
    """Facade for experience card operations."""

    @staticmethod
    async def create_raw(
        db: AsyncSession, person_id: str, body: RawExperienceCreate
    ) -> RawExperience:
        return await create_raw_experience(db, person_id, body)

    @staticmethod
    async def create_card(
        db: AsyncSession, person_id: str, body: ExperienceCardCreate
    ) -> ExperienceCard:
        return await create_experience_card(db, person_id, body)

    @staticmethod
    async def get_card(
        db: AsyncSession, card_id: str, person_id: str
    ) -> ExperienceCard | None:
        return await get_card_for_user(db, card_id, person_id)

    @staticmethod
    async def list_cards(db: AsyncSession, person_id: str) -> list[ExperienceCard]:
        return await list_my_cards(db, person_id)

    @staticmethod
    async def list_card_families(
        db: AsyncSession, person_id: str
    ) -> list[tuple[ExperienceCard, list[ExperienceCardChild]]]:
        return await list_my_card_families(db, person_id)


experience_card_service = ExperienceCardService()
