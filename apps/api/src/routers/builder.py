from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Person, ExperienceCard
from src.dependencies import get_current_user, get_db, get_experience_card_or_404
from src.schemas import (
    RawExperienceCreate,
    RawExperienceResponse,
    RewriteTextResponse,
    ExperienceCardCreate,
    ExperienceCardPatch,
    ExperienceCardResponse,
)
from src.providers import ChatServiceError, ChatRateLimitError
from src.serializers import experience_card_to_response
from src.services.experience_card import experience_card_service, apply_card_patch
from src.services.experience_card_pipeline import rewrite_raw_text

router = APIRouter(tags=["builder"])


@router.post("/experiences/raw", response_model=RawExperienceResponse)
async def create_raw_experience(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await experience_card_service.create_raw(db, current_user.id, body)
    return RawExperienceResponse(id=raw.id, raw_text=raw.raw_text, created_at=raw.created_at)


@router.post("/experiences/rewrite", response_model=RewriteTextResponse)
async def rewrite_experience_text(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
):
    """Rewrite messy input into clear English for easier extraction. No persistence."""
    try:
        rewritten = await rewrite_raw_text(body.raw_text)
        return RewriteTextResponse(rewritten_text=rewritten)
    except ChatRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
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
    body: ExperienceCardPatch,
    card: ExperienceCard = Depends(get_experience_card_or_404),
    db: AsyncSession = Depends(get_db),
):
    apply_card_patch(card, body)
    return experience_card_to_response(card)
