from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Person, ExperienceCard
from src.dependencies import get_current_user, get_db, get_experience_card_or_404
from src.schemas import (
    RawExperienceCreate,
    RawExperienceResponse,
    DraftSetResponse,
    DraftSetV1Response,
    CardFamilyV1Response,
    ExperienceCardCreate,
    ExperienceCardPatch,
    ExperienceCardResponse,
)
from src.providers import ChatServiceError, EmbeddingServiceError
from src.serializers import experience_card_to_response
from src.services.experience_card import experience_card_service, apply_card_patch
from src.services.experience_card_v1 import run_draft_v1_pipeline

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


@router.post("/experience-cards/draft-v1", response_model=DraftSetV1Response)
async def create_draft_cards_v1(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run Experience Card v1 pipeline: atomize → parent extract → child gen → validate."""
    try:
        draft_set_id, raw_experience_id, card_families = await run_draft_v1_pipeline(
            db, current_user.id, body
        )
        return DraftSetV1Response(
            draft_set_id=draft_set_id,
            raw_experience_id=raw_experience_id,
            card_families=[CardFamilyV1Response(parent=f["parent"], children=f["children"]) for f in card_families],
        )
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
    card: ExperienceCard = Depends(get_experience_card_or_404),
    body: ExperienceCardPatch,
    db: AsyncSession = Depends(get_db),
):
    apply_card_patch(card, body)
    return experience_card_to_response(card)


@router.post("/experience-cards/{card_id}/approve", response_model=ExperienceCardResponse)
async def approve_experience_card(
    card: ExperienceCard = Depends(get_experience_card_or_404),
    db: AsyncSession = Depends(get_db),
):
    try:
        card = await experience_card_service.approve(db, card)
    except EmbeddingServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return experience_card_to_response(card)


@router.post("/experience-cards/{card_id}/hide", response_model=ExperienceCardResponse)
async def hide_experience_card(
    card: ExperienceCard = Depends(get_experience_card_or_404),
):
    card.status = ExperienceCard.HIDDEN
    return experience_card_to_response(card)
