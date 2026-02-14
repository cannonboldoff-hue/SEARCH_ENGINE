import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from src.db.models import Person, ExperienceCard, ExperienceCardChild
from src.dependencies import (
    get_current_user,
    get_db,
    get_experience_card_or_404,
    get_experience_card_child_or_404,
)
from src.schemas import (
    RawExperienceCreate,
    RawExperienceResponse,
    RewriteTextResponse,
    DraftSetV1Response,
    FillFromTextRequest,
    FillFromTextResponse,
    CardFamilyV1Response,
    ExperienceCardCreate,
    ExperienceCardPatch,
    ExperienceCardResponse,
    ExperienceCardChildPatch,
    ExperienceCardChildResponse,
)
from src.providers import ChatServiceError, ChatRateLimitError, EmbeddingServiceError
from src.serializers import experience_card_to_response, experience_card_child_to_response
from src.services.experience_card import experience_card_service, apply_card_patch, apply_child_patch
from src.services.experience_card_pipeline import (
    rewrite_raw_text,
    run_draft_v1_pipeline,
    fill_missing_fields_from_text,
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
    """Run draft v1 pipeline: rewrite → extract-all → validate-all; persist cards as DRAFT."""
    try:
        draft_set_id, raw_experience_id, card_families = await run_draft_v1_pipeline(
            db, current_user.id, body
        )
        return DraftSetV1Response(
            draft_set_id=draft_set_id,
            raw_experience_id=raw_experience_id,
            card_families=[CardFamilyV1Response(parent=f["parent"], children=f["children"]) for f in card_families],
        )
    except (ChatServiceError, EmbeddingServiceError) as e:
        logger.exception("draft-v1 pipeline failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        logger.warning("draft-v1 pipeline config error: %s", e)
        raise HTTPException(status_code=503, detail=str(e))


def _is_empty(v) -> bool:
    """True if value is considered empty (for merge: only fill empty fields)."""
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, bool):
        return False  # never overwrite booleans from "empty"
    return False


def _merged_form(current: dict, filled: dict, string_only_keys: tuple) -> dict:
    """Merge filled into current: only set keys where current is empty. Returns new dict."""
    out = dict(current)
    for k in string_only_keys:
        if k not in filled:
            continue
        if _is_empty(out.get(k)):
            out[k] = filled[k]
    return out


def _parent_merged_to_patch(merged: dict) -> ExperienceCardPatch:
    """Build ExperienceCardPatch from frontend form dict (merged)."""
    intent_secondary = None
    if merged.get("intent_secondary_str") is not None:
        s = merged["intent_secondary_str"]
        if isinstance(s, str):
            intent_secondary = [x.strip() for x in s.split(",") if x.strip()]
        elif isinstance(s, list):
            intent_secondary = [str(x).strip() for x in s if str(x).strip()]
    start_date = None
    if merged.get("start_date"):
        try:
            start_date = date.fromisoformat(str(merged["start_date"]).strip()[:10])
        except (ValueError, TypeError):
            pass
    end_date = None
    if merged.get("end_date"):
        try:
            end_date = date.fromisoformat(str(merged["end_date"]).strip()[:10])
        except (ValueError, TypeError):
            pass
    confidence_score = None
    if merged.get("confidence_score") is not None and str(merged["confidence_score"]).strip():
        try:
            confidence_score = float(merged["confidence_score"])
        except (ValueError, TypeError):
            pass
    return ExperienceCardPatch(
        title=merged.get("title") or None,
        summary=merged.get("summary") or None,
        normalized_role=merged.get("normalized_role") or None,
        domain=merged.get("domain") or None,
        sub_domain=merged.get("sub_domain") or None,
        company_name=merged.get("company_name") or None,
        company_type=merged.get("company_type") or None,
        location=merged.get("location") or None,
        employment_type=merged.get("employment_type") or None,
        start_date=start_date,
        end_date=end_date,
        is_current=merged.get("is_current") if isinstance(merged.get("is_current"), bool) else None,
        intent_primary=merged.get("intent_primary") or None,
        intent_secondary=intent_secondary,
        seniority_level=merged.get("seniority_level") or None,
        confidence_score=confidence_score,
        experience_card_visibility=merged.get("experience_card_visibility") if isinstance(merged.get("experience_card_visibility"), bool) else None,
    )


def _child_merged_to_patch(merged: dict) -> ExperienceCardChildPatch:
    """Build ExperienceCardChildPatch from frontend form dict (merged)."""
    tags = None
    if merged.get("tagsStr") is not None:
        s = merged["tagsStr"]
        if isinstance(s, str):
            tags = [x.strip() for x in s.split(",") if x.strip()]
        elif isinstance(s, list):
            tags = [str(x).strip() for x in s if str(x).strip()]
    return ExperienceCardChildPatch(
        title=merged.get("title") or None,
        summary=merged.get("summary") or None,
        tags=tags,
        time_range=merged.get("time_range") or None,
        company=merged.get("company") or None,
        location=merged.get("location") or None,
    )


# Keys we merge for parent (string-like; booleans handled in _parent_merged_to_patch)
_PARENT_MERGE_KEYS = (
    "title", "summary", "normalized_role", "domain", "sub_domain", "company_name", "company_type",
    "location", "employment_type", "start_date", "end_date", "intent_primary", "intent_secondary_str",
    "seniority_level", "confidence_score",
)
_CHILD_MERGE_KEYS = ("title", "summary", "tagsStr", "time_range", "company", "location")


@router.post("/experience-cards/fill-missing-from-text", response_model=FillFromTextResponse)
async def fill_missing_from_text(
    body: FillFromTextRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rewrite + fill only missing fields from text. If card_id or child_id provided, persist to DB."""
    try:
        filled = await fill_missing_fields_from_text(
            raw_text=body.raw_text,
            current_card=body.current_card or {},
            card_type=body.card_type or "parent",
        )
    except HTTPException:
        raise

    current = body.current_card or {}
    if body.card_id and body.card_type == "parent":
        merged = _merged_form(current, filled, _PARENT_MERGE_KEYS)
        # Persist to DB
        card = await experience_card_service.get_card(db, body.card_id, current_user.id)
        if not card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
        patch = _parent_merged_to_patch(merged)
        apply_card_patch(card, patch)
        await db.flush()

    if body.child_id and body.card_type == "child":
        merged = _merged_form(current, filled, _CHILD_MERGE_KEYS)
        result = await db.execute(
            select(ExperienceCardChild).where(
                ExperienceCardChild.id == body.child_id,
                ExperienceCardChild.person_id == current_user.id,
            )
        )
        child = result.scalar_one_or_none()
        if not child:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child card not found")
        patch = _child_merged_to_patch(merged)
        apply_child_patch(child, patch)
        await db.flush()

    return FillFromTextResponse(filled=filled)


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


@router.delete("/experience-cards/{card_id}", response_model=ExperienceCardResponse)
async def delete_experience_card(
    card: ExperienceCard = Depends(get_experience_card_or_404),
    db: AsyncSession = Depends(get_db),
):
    # Delete all children first so they are removed when parent is deleted (explicit cascade)
    await db.execute(delete(ExperienceCardChild).where(ExperienceCardChild.parent_experience_id == card.id))
    response = experience_card_to_response(card)
    await db.delete(card)
    return response


@router.patch(
    "/experience-card-children/{child_id}",
    response_model=ExperienceCardChildResponse,
)
async def patch_experience_card_child(
    body: ExperienceCardChildPatch,
    child: ExperienceCardChild = Depends(get_experience_card_child_or_404),
    db: AsyncSession = Depends(get_db),
):
    apply_child_patch(child, body)
    return experience_card_child_to_response(child)


@router.delete(
    "/experience-card-children/{child_id}",
    response_model=ExperienceCardChildResponse,
)
async def delete_experience_card_child(
    child: ExperienceCardChild = Depends(get_experience_card_child_or_404),
    db: AsyncSession = Depends(get_db),
):
    response = experience_card_child_to_response(child)
    await db.delete(child)
    return response
