"""Experience card and raw experience business logic."""

import asyncio
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models import RawExperience, ExperienceCard, ExperienceCardChild
from src.schemas import (
    RawExperienceCreate,
    ExperienceCardCreate,
    ExperienceCardPatch,
    ExperienceCardChildPatch,
)


def _format_date_range(card: ExperienceCard) -> str:
    if card.start_date and card.end_date:
        return f"{card.start_date} - {card.end_date}"
    if card.start_date:
        return str(card.start_date)
    if card.end_date:
        return str(card.end_date)
    return ""


def _experience_card_search_document(card: ExperienceCard) -> str:
    """Build searchable text for an experience card."""
    parts = [
        card.title or "",
        card.normalized_role or "",
        card.domain or "",
        card.sub_domain or "",
        card.company_name or "",
        card.company_type or "",
        card.location or "",
        card.employment_type or "",
        card.summary or "",
        card.raw_text or "",
        card.intent_primary or "",
        " ".join(card.intent_secondary or []),
        card.seniority_level or "",
        _format_date_range(card),
        "current" if card.is_current else "",
    ]
    return " ".join(filter(None, parts))


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


async def create_experience_card(
    db: AsyncSession,
    person_id: str,
    body: ExperienceCardCreate,
) -> ExperienceCard:
    """Create an experience card."""
    card = ExperienceCard(
        user_id=person_id,
        title=body.title,
        normalized_role=body.normalized_role,
        domain=body.domain,
        sub_domain=body.sub_domain,
        company_name=body.company_name,
        company_type=body.company_type,
        start_date=body.start_date,
        end_date=body.end_date,
        is_current=body.is_current,
        location=body.location,
        employment_type=body.employment_type,
        summary=body.summary,
        raw_text=body.raw_text,
        intent_primary=body.intent_primary,
        intent_secondary=body.intent_secondary or [],
        seniority_level=body.seniority_level,
        confidence_score=body.confidence_score,
        experience_card_visibility=body.experience_card_visibility if body.experience_card_visibility is not None else True,
    )
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


def apply_card_patch(card: ExperienceCard, body: ExperienceCardPatch) -> None:
    """Apply patch fields to card (in place)."""
    if body.title is not None:
        card.title = body.title
    if body.normalized_role is not None:
        card.normalized_role = body.normalized_role
    if body.domain is not None:
        card.domain = body.domain
    if body.sub_domain is not None:
        card.sub_domain = body.sub_domain
    if body.company_name is not None:
        card.company_name = body.company_name
    if body.company_type is not None:
        card.company_type = body.company_type
    if body.start_date is not None:
        card.start_date = body.start_date
    if body.end_date is not None:
        card.end_date = body.end_date
    if body.is_current is not None:
        card.is_current = body.is_current
    if body.location is not None:
        card.location = body.location
    if body.employment_type is not None:
        card.employment_type = body.employment_type
    if body.summary is not None:
        card.summary = body.summary
    if body.raw_text is not None:
        card.raw_text = body.raw_text
    if body.intent_primary is not None:
        card.intent_primary = body.intent_primary
    if body.intent_secondary is not None:
        card.intent_secondary = body.intent_secondary
    if body.seniority_level is not None:
        card.seniority_level = body.seniority_level
    if body.confidence_score is not None:
        card.confidence_score = body.confidence_score
    if body.experience_card_visibility is not None:
        card.experience_card_visibility = body.experience_card_visibility


def _child_search_document_from_value(label: str | None, value: dict) -> str | None:
    """Best-effort search_document update for child cards after edits."""
    if not isinstance(value, dict):
        return None
    time_text = None
    if isinstance(value.get("time"), dict):
        time_text = value["time"].get("text")
    location_text = None
    if isinstance(value.get("location"), dict):
        location_text = value["location"].get("text")
    tags = value.get("tags") if isinstance(value.get("tags"), list) else []
    tags_str = " ".join(str(t).strip() for t in tags[:10] if str(t).strip())
    parts = [
        label or "",
        str(value.get("headline") or ""),
        str(value.get("summary") or ""),
        str(value.get("company") or ""),
        str(location_text or ""),
        str(time_text or ""),
        tags_str,
    ]
    doc = " ".join(p.strip() for p in parts if p and str(p).strip()).strip()
    return doc or None


def apply_child_patch(child: ExperienceCardChild, body: ExperienceCardChildPatch) -> None:
    """
    Apply patch fields to ExperienceCardChild (in place).

    Edits are applied into both:
    - child.label (for title/headline)
    - child.value (dimension container used by the draft-v1 child DTO)
    """
    value = child.value if isinstance(child.value, dict) else {}

    if body.title is not None:
        child.label = body.title
        value["headline"] = body.title

    if body.summary is not None:
        value["summary"] = body.summary

    if body.tags is not None:
        tags = [str(t).strip() for t in body.tags if str(t).strip()][:50]
        value["tags"] = tags
        # Keep topics in sync for UI rendering convenience
        value["topics"] = [{"label": t} for t in tags]

    if body.time_range is not None:
        time_obj = value.get("time")
        if not isinstance(time_obj, dict):
            time_obj = {}
        time_obj["text"] = body.time_range
        value["time"] = time_obj

    if body.location is not None:
        loc_obj = value.get("location")
        if not isinstance(loc_obj, dict):
            loc_obj = {}
        loc_obj["text"] = body.location
        value["location"] = loc_obj

    if body.company is not None:
        value["company"] = body.company

    child.value = value
    child.search_document = _child_search_document_from_value(child.label, value)


async def list_my_cards(
    db: AsyncSession,
    person_id: str,
) -> list[ExperienceCard]:
    """List experience cards for the user."""
    q = select(ExperienceCard).where(ExperienceCard.user_id == person_id)
    q = q.order_by(ExperienceCard.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def list_my_children(
    db: AsyncSession,
    person_id: str,
) -> list[ExperienceCardChild]:
    """List all experience card children for the user."""
    q = select(ExperienceCardChild).where(ExperienceCardChild.person_id == person_id)
    result = await db.execute(q)
    return list(result.scalars().all())


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


class ExperienceCardService:
    """Facade for experience card operations (for dependency injection if needed)."""

    @staticmethod
    async def create_raw(db: AsyncSession, person_id: str, body: RawExperienceCreate) -> RawExperience:
        return await create_raw_experience(db, person_id, body)

    @staticmethod
    async def create_card(db: AsyncSession, person_id: str, body: ExperienceCardCreate) -> ExperienceCard:
        return await create_experience_card(db, person_id, body)

    @staticmethod
    async def get_card(db: AsyncSession, card_id: str, person_id: str) -> ExperienceCard | None:
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
