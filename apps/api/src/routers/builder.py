import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from src.db.models import Person, ExperienceCard
from src.dependencies import get_current_user, get_db, get_experience_card_or_404
from src.schemas import (
    RawExperienceCreate,
    RawExperienceResponse,
    RewriteTextResponse,
    DraftSetV1Response,
    CardFamilyV1Response,
    CommitDraftSetRequest,
    ExperienceCardCreate,
    ExperienceCardPatch,
    ExperienceCardResponse,
)
from src.providers import ChatServiceError, ChatRateLimitError, EmbeddingServiceError
from src.serializers import experience_card_to_response
from src.services.experience_card import experience_card_service, apply_card_patch
from src.services.experience_card_v1 import run_draft_v1_pipeline, rewrite_raw_text

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


@router.post("/experience-cards/draft-v1", response_model=DraftSetV1Response)
async def create_draft_cards_v1(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run Experience Card v1 pipeline: atomize → parent extract → child gen → validate. Persists drafts with server-generated ids."""
    try:
        draft_set_id, raw_experience_id, card_families = await run_draft_v1_pipeline(
            db, current_user.id, body
        )
        return DraftSetV1Response(
            draft_set_id=draft_set_id,
            raw_experience_id=raw_experience_id,
            card_families=[CardFamilyV1Response(parent=f["parent"], children=f["children"]) for f in card_families],
        )
    except ChatRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ChatServiceError as e:
        logger.exception(
            "draft-v1 pipeline: chat/LLM error (503). "
            "Cloud may show success for one call; this can be a later step or invalid JSON from the model: %s",
            e,
        )
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/draft-sets/{draft_set_id}/commit", response_model=list[ExperienceCardResponse])
async def commit_draft_set(
    draft_set_id: str,
    body: CommitDraftSetRequest | None = None,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve (commit) draft cards in this set: DRAFT → APPROVED, compute embeddings. Optional card_ids for partial selection."""
    cards = await experience_card_service.list_drafts_by_raw_experience(
        db, current_user.id, draft_set_id, card_ids=(body.card_ids if body else None)
    )
    if not cards:
        raise HTTPException(status_code=404, detail="No draft cards found for this draft set.")
    try:
        cards = await experience_card_service.approve_batch(db, cards)
    except EmbeddingServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return [experience_card_to_response(c) for c in cards]


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


@router.delete("/experience-cards/{card_id}", status_code=204)
async def delete_experience_card(
    card: ExperienceCard = Depends(get_experience_card_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Delete a draft experience card. Only DRAFT cards can be deleted."""
    if card.status != ExperienceCard.DRAFT:
        raise HTTPException(
            status_code=400,
            detail="Only draft cards can be deleted.",
        )
    await db.delete(card)
    return None
