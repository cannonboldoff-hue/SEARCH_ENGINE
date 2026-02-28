import logging
from datetime import date
from typing import Any, Optional

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
    DraftSetResponse,
    DetectExperiencesResponse,
    DraftSingleRequest,
    FillFromTextRequest,
    FillFromTextResponse,
    ClarifyExperienceRequest,
    ClarifyExperienceResponse,
    DraftCardFamily,
    ExperienceCardCreate,
    ExperienceCardPatch,
    ExperienceCardResponse,
    ExperienceCardChildPatch,
    ExperienceCardChildResponse,
    FinalizeExperienceCardRequest,
)
from src.providers import (
    ChatServiceError,
    ChatRateLimitError,
    EmbeddingServiceError,
)
from src.serializers import experience_card_to_response, experience_card_child_to_response
from src.services.experience import (
    experience_card_service,
    apply_card_patch,
    apply_child_patch,
    embed_experience_cards,
    rewrite_raw_text,
    run_draft_single,
    fill_missing_fields_from_text,
    clarify_experience_interactive,
    detect_experiences,
    DEFAULT_MAX_PARENT_CLARIFY,
    DEFAULT_MAX_CHILD_CLARIFY,
    PipelineError,
)

router = APIRouter(tags=["builder"])


async def _reembed_cards_after_update(
    db: AsyncSession,
    *,
    parents: list[ExperienceCard] | None = None,
    children: list[ExperienceCardChild] | None = None,
    context: str = "update",
) -> None:
    """
    Re-run embedding for the given cards after a content update (patch / fill / clarify).
    On failure, logs and raises HTTP 503.
    """
    parents = parents or []
    children = children or []
    if not parents and not children:
        return
    try:
        await embed_experience_cards(db, parents, children)
    except PipelineError as e:
        logger.warning("Re-embed after %s failed: %s", context, e)
        raise HTTPException(status_code=503, detail=str(e)) from e


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


@router.post("/experience-cards/detect-experiences", response_model=DetectExperiencesResponse)
async def detect_experiences_endpoint(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
):
    """Analyze text and return count + list of distinct experiences (for user to choose one)."""
    try:
        result = await detect_experiences(body.raw_text or "")
        return DetectExperiencesResponse(
            count=result.get("count", 0),
            experiences=[{"index": e["index"], "label": e["label"], "suggested": e.get("suggested", False)} for e in result.get("experiences", [])],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("detect-experiences failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e))



@router.post("/experience-cards/draft-single", response_model=DraftSetResponse)
async def create_draft_single_experience(
    body: DraftSingleRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Extract and draft ONE experience by index (1-based). Process one experience at a time."""
    try:
        draft_set_id, raw_experience_id, card_families = await run_draft_single(
            db,
            current_user.id,
            body.raw_text or "",
            body.experience_index,
            body.experience_count or 1,
        )
        return DraftSetResponse(
            draft_set_id=draft_set_id,
            raw_experience_id=raw_experience_id,
            card_families=[DraftCardFamily(parent=f["parent"], children=f["children"]) for f in card_families],
        )
    except (ChatServiceError, EmbeddingServiceError, PipelineError) as e:
        logger.exception("draft-single pipeline failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        logger.warning("draft-single pipeline config error: %s", e)
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


def _parse_date_for_patch(value: Any) -> Optional[date]:
    """Parse date from merged form (YYYY-MM-DD or YYYY-MM). Clarify can return YYYY-MM."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s[:10]
    if len(s) == 7 and s[4] == "-":  # YYYY-MM
        s = f"{s}-01"
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _parent_merged_to_patch(merged: dict) -> ExperienceCardPatch:
    """Build ExperienceCardPatch from frontend form dict (merged)."""
    intent_secondary = None
    if merged.get("intent_secondary_str") is not None:
        s = merged["intent_secondary_str"]
        if isinstance(s, str):
            intent_secondary = [x.strip() for x in s.split(",") if x.strip()]
        elif isinstance(s, list):
            intent_secondary = [str(x).strip() for x in s if str(x).strip()]
    start_date = _parse_date_for_patch(merged.get("start_date"))
    end_date = _parse_date_for_patch(merged.get("end_date"))
    confidence_score = None
    if merged.get("confidence_score") is not None and str(merged["confidence_score"]).strip():
        try:
            confidence_score = float(merged["confidence_score"])
        except (ValueError, TypeError):
            pass
    location_val = merged.get("location")  # str or dict; schema normalizes to str
    return ExperienceCardPatch(
        title=merged.get("title") or None,
        summary=merged.get("summary") or None,
        normalized_role=merged.get("normalized_role") or None,
        domain=merged.get("domain") or None,
        sub_domain=merged.get("sub_domain") or None,
        company_name=merged.get("company_name") or None,
        company_type=merged.get("company_type") or None,
        location=location_val,
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
    items = None
    if merged.get("items") is not None and isinstance(merged["items"], list):
        items = []
        for x in merged["items"]:
            if not isinstance(x, dict):
                continue
            title = str(x.get("title", "") or x.get("subtitle", "") or "").strip()
            if not title:
                continue
            desc = (x.get("description") or x.get("sub_summary") or "").strip() or None
            items.append({"title": title, "description": desc})
        items = items if items else None
    return ExperienceCardChildPatch(items=items)


# Keys we merge for parent (string-like; booleans handled in _parent_merged_to_patch)
_PARENT_MERGE_KEYS = (
    "title", "summary", "normalized_role", "domain", "sub_domain", "company_name", "company_type",
    "location", "employment_type", "start_date", "end_date", "intent_primary", "intent_secondary_str",
    "seniority_level", "confidence_score",
)
_CHILD_MERGE_KEYS = ("items",)


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
        await _reembed_cards_after_update(db, parents=[card], context="fill-missing (parent)")

    # Do NOT persist for child cards: the merge only fills empty fields, so it would overwrite
    # with incomplete data (e.g. 1 item when user added a second via messy text). The actual
    # persist happens when the user clicks Done and PATCHes the full form.
    if body.child_id and body.card_type == "child":
        pass  # Skip persist; return filled for frontend merge only

    return FillFromTextResponse(filled=filled)


@router.post("/experience-cards/clarify-experience", response_model=ClarifyExperienceResponse)
async def clarify_experience(
    body: ClarifyExperienceRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Interactive clarification: planner -> validate -> question writer / answer applier. Optionally persist when filled."""
    conv = [{"role": m.role, "content": m.content} for m in body.conversation_history]
    max_parent = body.max_parent_questions if body.max_parent_questions is not None else DEFAULT_MAX_PARENT_CLARIFY
    max_child = body.max_child_questions if body.max_child_questions is not None else DEFAULT_MAX_CHILD_CLARIFY
    try:
        result = await clarify_experience_interactive(
            raw_text=body.raw_text,
            current_card=body.current_card or {},
            card_type=body.card_type or "parent",
            conversation_history=conv,
            card_family=body.card_family,
            asked_history_structured=body.asked_history,
            last_question_target=body.last_question_target,
            max_parent=max_parent,
            max_child=max_child,
            card_families=body.card_families,
            focus_parent_id=body.focus_parent_id,
            detected_experiences=body.detected_experiences,
        )
    except HTTPException:
        raise

    clarifying_question = result.get("clarifying_question") or None
    filled = result.get("filled") or {}
    action = result.get("action")
    message = result.get("message")
    options = result.get("options")
    focus_parent_id_resp = result.get("focus_parent_id")

    current = body.current_card or {}
    if filled and body.card_id and body.card_type == "parent":
        merged = _merged_form(current, filled, _PARENT_MERGE_KEYS)
        card = await experience_card_service.get_card(db, body.card_id, current_user.id)
        if card:
            patch = _parent_merged_to_patch(merged)
            apply_card_patch(card, patch)
            await db.flush()
            await _reembed_cards_after_update(db, parents=[card], context="clarify (parent)")

    if filled and body.child_id and body.card_type == "child":
        merged = _merged_form(current, filled, _CHILD_MERGE_KEYS)
        child_row = await db.execute(
            select(ExperienceCardChild).where(
                ExperienceCardChild.id == body.child_id,
                ExperienceCardChild.person_id == current_user.id,
            )
        )
        child = child_row.scalar_one_or_none()
        if child:
            patch = _child_merged_to_patch(merged)
            apply_child_patch(child, patch)
            await db.flush()
            await _reembed_cards_after_update(db, children=[child], context="clarify (child)")

    return ClarifyExperienceResponse(
        clarifying_question=clarifying_question,
        filled=filled,
        action=action,
        message=message,
        options=options,
        focus_parent_id=focus_parent_id_resp,
        should_stop=result.get("should_stop"),
        stop_reason=result.get("stop_reason"),
        target_type=result.get("target_type"),
        target_field=result.get("target_field"),
        target_child_type=result.get("target_child_type"),
        progress=result.get("progress"),
        missing_fields=result.get("missing_fields"),
        asked_history_entry=result.get("asked_history_entry"),
        canonical_family=result.get("canonical_family"),
    )


@router.post("/experience-cards/finalize", response_model=ExperienceCardResponse)
async def finalize_experience_card(
    body: FinalizeExperienceCardRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Finalize a drafted experience card:
    - Ensure it belongs to the current user
    - Mark it visible
    - Embed parent + children so it appears in search and \"Your Cards\".
    """
    card = await experience_card_service.get_card(db, body.card_id, current_user.id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    # Mark card as visible (was created as non-visible draft by the pipeline)
    card.experience_card_visibility = True

    # Load all children for this card so they are embedded together.
    children_result = await db.execute(
        select(ExperienceCardChild).where(
            ExperienceCardChild.parent_experience_id == card.id,
            ExperienceCardChild.person_id == current_user.id,
        )
    )
    children = children_result.scalars().all()

    await _reembed_cards_after_update(
        db,
        parents=[card],
        children=children,
        context="finalize",
    )

    return experience_card_to_response(card)


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
    await _reembed_cards_after_update(db, parents=[card], context="PATCH card")
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
    await _reembed_cards_after_update(db, children=[child], context="PATCH child")
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
