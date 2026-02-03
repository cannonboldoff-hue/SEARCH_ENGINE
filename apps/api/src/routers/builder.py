from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models import Person, RawExperience, ExperienceCard
from src.dependencies import get_current_user, get_db
from src.schemas import (
    RawExperienceCreate,
    RawExperienceResponse,
    DraftSetResponse,
    DraftCardResponse,
    ExperienceCardCreate,
    ExperienceCardPatch,
    ExperienceCardResponse,
)
from src.providers import get_chat_provider, get_embedding_provider

router = APIRouter(tags=["builder"])


@router.post("/experiences/raw", response_model=RawExperienceResponse)
async def create_raw_experience(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = RawExperience(person_id=current_user.id, raw_text=body.raw_text)
    db.add(raw)
    await db.commit()
    await db.refresh(raw)
    return RawExperienceResponse(id=raw.id, raw_text=raw.raw_text, created_at=raw.created_at)


@router.post("/experience-cards/draft", response_model=DraftSetResponse)
async def create_draft_cards(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = RawExperience(person_id=current_user.id, raw_text=body.raw_text)
    db.add(raw)
    await db.flush()
    chat = get_chat_provider()
    draft_set = await chat.extract_experience_cards(body.raw_text, raw.id)
    await db.commit()
    await db.refresh(raw)
    return DraftSetResponse(
        draft_set_id=draft_set.draft_set_id,
        raw_experience_id=raw.id,
        cards=[
            DraftCardResponse(
                draft_card_id=c.draft_card_id,
                title=c.title,
                context=c.context,
                constraints=c.constraints,
                decisions=c.decisions,
                outcome=c.outcome,
                tags=c.tags or [],
                company=c.company,
                team=c.team,
                role_title=c.role_title,
                time_range=c.time_range,
                source_span=c.source_span,
            )
            for c in draft_set.cards
        ],
    )


def _card_to_response(c: ExperienceCard) -> ExperienceCardResponse:
    return ExperienceCardResponse(
        id=c.id,
        person_id=c.person_id,
        raw_experience_id=c.raw_experience_id,
        status=c.status,
        human_edited=c.human_edited,
        locked=c.locked,
        title=c.title,
        context=c.context,
        constraints=c.constraints,
        decisions=c.decisions,
        outcome=c.outcome,
        tags=c.tags or [],
        company=c.company,
        team=c.team,
        role_title=c.role_title,
        time_range=c.time_range,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.post("/experience-cards", response_model=ExperienceCardResponse)
async def create_experience_card(
    body: ExperienceCardCreate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = ExperienceCard(
        person_id=current_user.id,
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
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return _card_to_response(card)


@router.patch("/experience-cards/{card_id}", response_model=ExperienceCardResponse)
async def patch_experience_card(
    card_id: str,
    body: ExperienceCardPatch,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExperienceCard).where(
            ExperienceCard.id == card_id,
            ExperienceCard.person_id == current_user.id,
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
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
    if body.locked is not None:
        card.locked = body.locked
    content_fields = (
        body.title, body.context, body.constraints, body.decisions, body.outcome,
        body.tags, body.company, body.team, body.role_title, body.time_range,
    )
    if any(f is not None for f in content_fields):
        card.human_edited = True
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return _card_to_response(card)


@router.post("/experience-cards/{card_id}/approve", response_model=ExperienceCardResponse)
async def approve_experience_card(
    card_id: str,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExperienceCard).where(
            ExperienceCard.id == card_id,
            ExperienceCard.person_id == current_user.id,
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    card.status = ExperienceCard.APPROVED
    text_parts = [
        card.title or "",
        card.context or "",
        card.company or "",
        card.team or "",
        card.role_title or "",
        card.time_range or "",
        " ".join(card.tags or []),
    ]
    text = " ".join(filter(None, text_parts))
    embed_provider = get_embedding_provider()
    vectors = await embed_provider.embed([text])
    if not vectors:
        raise HTTPException(
            status_code=503,
            detail="Embedding model returned no vector. Ensure the embedding service is running.",
        )
    vec = vectors[0]
    # ExperienceCard.embedding is Vector(384); truncate or pad to match
    dim = 384
    card.embedding = (vec[:dim] + [0.0] * (dim - len(vec))) if len(vec) < dim else vec[:dim]
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return _card_to_response(card)


@router.post("/experience-cards/{card_id}/hide", response_model=ExperienceCardResponse)
async def hide_experience_card(
    card_id: str,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExperienceCard).where(
            ExperienceCard.id == card_id,
            ExperienceCard.person_id == current_user.id,
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    card.status = ExperienceCard.HIDDEN
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return _card_to_response(card)


@router.get("/me/experience-cards", response_model=list[ExperienceCardResponse])
async def list_my_experience_cards(
    status_filter: str | None = Query(None, alias="status"),
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(ExperienceCard).where(ExperienceCard.person_id == current_user.id)
    if status_filter:
        q = q.where(ExperienceCard.status == status_filter)
    else:
        q = q.where(ExperienceCard.status != ExperienceCard.HIDDEN)
    q = q.order_by(ExperienceCard.created_at.desc())
    result = await db.execute(q)
    cards = result.scalars().all()
    return [_card_to_response(c) for c in cards]
