"""Experience card and raw experience business logic."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models import RawExperience, ExperienceCard
from src.schemas import (
    RawExperienceCreate,
    RawExperienceResponse,
    ExperienceCardCreate,
    ExperienceCardPatch,
)
from src.providers import get_embedding_provider, EmbeddingServiceError
from src.utils import normalize_embedding


VALID_CARD_STATUSES = {ExperienceCard.DRAFT, ExperienceCard.APPROVED, ExperienceCard.HIDDEN}


def _card_searchable_text(card: ExperienceCard) -> str:
    """Build searchable text from card for embedding."""
    parts = [
        card.title or "",
        card.context or "",
        card.company or "",
        card.team or "",
        card.role_title or "",
        card.time_range or "",
        card.location or "",
        " ".join(card.tags or []),
    ]
    return " ".join(filter(None, parts))


async def create_raw_experience(
    db: AsyncSession,
    person_id: str,
    body: RawExperienceCreate,
) -> RawExperience:
    """Create a raw experience record."""
    raw = RawExperience(person_id=person_id, raw_text=body.raw_text)
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
        person_id=person_id,
        raw_experience_id=body.raw_experience_id,
        status=ExperienceCard.DRAFT,
        title=body.title,
        context=body.context,
        constraints=body.constraints,
        decisions=body.decisions,
        outcome=body.outcome,
        tags=body.tags or [],
        company=body.company,
        team=body.team,
        role_title=body.role_title,
        time_range=body.time_range,
        location=body.location,
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
            ExperienceCard.person_id == person_id,
        )
    )
    return result.scalar_one_or_none()


def apply_card_patch(card: ExperienceCard, body: ExperienceCardPatch) -> None:
    """Apply patch fields to card (in place)."""
    if body.title is not None:
        card.title = body.title
    if body.context is not None:
        card.context = body.context
    if body.constraints is not None:
        card.constraints = body.constraints
    if body.decisions is not None:
        card.decisions = body.decisions
    if body.outcome is not None:
        card.outcome = body.outcome
    if body.tags is not None:
        card.tags = body.tags
    if body.company is not None:
        card.company = body.company
    if body.team is not None:
        card.team = body.team
    if body.role_title is not None:
        card.role_title = body.role_title
    if body.time_range is not None:
        card.time_range = body.time_range
    if body.location is not None:
        card.location = body.location
    if body.locked is not None:
        card.locked = body.locked
    content_fields = (
        body.title, body.context, body.constraints, body.decisions, body.outcome,
        body.tags, body.company, body.team, body.role_title, body.time_range, body.location,
    )
    if any(f is not None for f in content_fields):
        card.human_edited = True


async def approve_experience_card(db: AsyncSession, card: ExperienceCard) -> ExperienceCard:
    """Set card to APPROVED and compute/store embedding. Raises EmbeddingServiceError on failure."""
    card.status = ExperienceCard.APPROVED
    text = _card_searchable_text(card)
    embed_provider = get_embedding_provider()
    vectors = await embed_provider.embed([text])
    if not vectors:
        raise EmbeddingServiceError("Embedding model returned no vector.")
    card.embedding = normalize_embedding(vectors[0])
    return card


async def list_my_cards(
    db: AsyncSession,
    person_id: str,
    status_filter: str | None,
) -> list[ExperienceCard]:
    """List experience cards for the user, optionally filtered by status."""
    q = select(ExperienceCard).where(ExperienceCard.person_id == person_id)
    if status_filter:
        q = q.where(ExperienceCard.status == status_filter)
    else:
        q = q.where(ExperienceCard.status != ExperienceCard.HIDDEN)
    q = q.order_by(ExperienceCard.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def list_draft_cards_by_raw_experience(
    db: AsyncSession,
    person_id: str,
    raw_experience_id: str,
    card_ids: list[str] | None = None,
) -> list[ExperienceCard]:
    """List DRAFT cards for the user for the given raw_experience_id (draft set). Optionally filter by card_ids."""
    q = (
        select(ExperienceCard)
        .where(ExperienceCard.person_id == person_id)
        .where(ExperienceCard.raw_experience_id == raw_experience_id)
        .where(ExperienceCard.status == ExperienceCard.DRAFT)
    )
    if card_ids:
        q = q.where(ExperienceCard.id.in_(card_ids))
    q = q.order_by(ExperienceCard.created_at.asc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def approve_cards_batch(
    db: AsyncSession,
    cards: list[ExperienceCard],
) -> list[ExperienceCard]:
    """Transition cards to APPROVED and compute/store embeddings (batch). Raises EmbeddingServiceError on failure."""
    if not cards:
        return []
    texts = [_card_searchable_text(c) for c in cards]
    embed_provider = get_embedding_provider()
    vectors = await embed_provider.embed(texts)
    if len(vectors) != len(cards):
        raise EmbeddingServiceError("Embedding model returned wrong number of vectors.")
    for card, vec in zip(cards, vectors):
        card.status = ExperienceCard.APPROVED
        card.embedding = normalize_embedding(vec)
    return cards


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
    async def approve(db: AsyncSession, card: ExperienceCard) -> ExperienceCard:
        return await approve_experience_card(db, card)

    @staticmethod
    async def list_cards(db: AsyncSession, person_id: str, status_filter: str | None) -> list[ExperienceCard]:
        return await list_my_cards(db, person_id, status_filter)

    @staticmethod
    async def list_drafts_by_raw_experience(
        db: AsyncSession,
        person_id: str,
        raw_experience_id: str,
        card_ids: list[str] | None = None,
    ) -> list[ExperienceCard]:
        return await list_draft_cards_by_raw_experience(db, person_id, raw_experience_id, card_ids)

    @staticmethod
    async def approve_batch(db: AsyncSession, cards: list[ExperienceCard]) -> list[ExperienceCard]:
        return await approve_cards_batch(db, cards)


experience_card_service = ExperienceCardService()
