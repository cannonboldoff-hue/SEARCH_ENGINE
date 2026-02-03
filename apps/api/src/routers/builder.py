from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Person, ExperienceCard
from src.dependencies import get_current_user, get_db
from src.schemas import (
    RawExperienceCreate,
    RawExperienceResponse,
    DraftSetResponse,
    ExperienceCardCreate,
    ExperienceCardPatch,
    ExperienceCardResponse,
)
from src.providers import ChatServiceError, EmbeddingServiceError
from src.serializers import experience_card_to_response
from src.services.experience_card import (
    experience_card_service,
    apply_card_patch,
    VALID_CARD_STATUSES,
)

router = APIRouter(tags=["builder"])


@router.post("/experiences/raw", response_model=RawExperienceResponse)
async def create_raw_experience(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await experience_card_service.create_raw(db, current_user.id, body)
    return RawExperienceResponse(id=raw.id, raw_text=raw.raw_text, created_at=raw.created_at)


@router.post("/experience-cards/draft", response_model=DraftSetResponse)
async def create_draft_cards(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        _, response = await experience_card_service.create_draft_set(db, current_user.id, body)
        return response
    except ChatServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/experience-cards", response_model=ExperienceCardResponse)
async def create_experience_card(
    body: ExperienceCardCreate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await experience_card_service.create_card(db, current_user.id, body)
    return experience_card_to_response(card)


@router.patch("/experience-cards/{card_id}", response_model=ExperienceCardResponse)
async def patch_experience_card(
    card_id: str,
    body: ExperienceCardPatch,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await experience_card_service.get_card(db, card_id, current_user.id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    apply_card_patch(card, body)
    return experience_card_to_response(card)


@router.post("/experience-cards/{card_id}/approve", response_model=ExperienceCardResponse)
async def approve_experience_card(
    card_id: str,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await experience_card_service.get_card(db, card_id, current_user.id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    try:
        card = await experience_card_service.approve(db, card)
    except EmbeddingServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return experience_card_to_response(card)


@router.post("/experience-cards/{card_id}/hide", response_model=ExperienceCardResponse)
async def hide_experience_card(
    card_id: str,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await experience_card_service.get_card(db, card_id, current_user.id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    card.status = ExperienceCard.HIDDEN
    return experience_card_to_response(card)


@router.get("/me/experience-cards", response_model=list[ExperienceCardResponse])
async def list_my_experience_cards(
    status_filter: str | None = Query(None, alias="status"),
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if status_filter is not None and status_filter not in VALID_CARD_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of: {', '.join(sorted(VALID_CARD_STATUSES))}",
        )
    cards = await experience_card_service.list_cards(db, current_user.id, status_filter)
    return [experience_card_to_response(c) for c in cards]
