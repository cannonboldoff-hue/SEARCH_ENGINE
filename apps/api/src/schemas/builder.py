from datetime import datetime, date
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class RawExperienceCreate(BaseModel):
    raw_text: str


class RawExperienceResponse(BaseModel):
    id: str
    raw_text: str
    created_at: Optional[datetime] = None


class RewriteTextResponse(BaseModel):
    """Result of POST /experiences/rewrite: cleaned English text."""

    rewritten_text: str


class DraftCardFamily(BaseModel):
    """One parent experience card + its child cards (from draft pipeline)."""

    parent: dict
    children: list[dict] = []


class DraftSetResponse(BaseModel):
    """Result of single-experience pipeline: rewrite → extract one → validate → persist."""

    draft_set_id: str
    raw_experience_id: str
    card_families: list[DraftCardFamily]


class DetectedExperienceItem(BaseModel):
    """One detected experience for user to choose."""

    index: int
    label: str
    suggested: bool = False


class DetectExperiencesResponse(BaseModel):
    """Result of POST /experience-cards/detect-experiences."""

    count: int = 0
    experiences: list[DetectedExperienceItem] = []


class DraftSingleRequest(BaseModel):
    """Request to extract and draft a single experience by index (1-based)."""

    raw_text: str
    experience_index: int = 1
    experience_count: int = 1  # total from detect-experiences; used so LLM knows context


class FillFromTextRequest(BaseModel):
    """Request for fill-missing-from-text: rewrite + fill only missing fields. Optionally persist to DB."""

    raw_text: str
    card_type: str = "parent"  # "parent" | "child"
    current_card: dict = {}  # current form/card state (frontend shape)
    card_id: Optional[str] = None  # if set, merge and PATCH this parent card (persist to DB)
    child_id: Optional[str] = None  # if set, merge and PATCH this child card (persist to DB)


class FillFromTextResponse(BaseModel):
    """Response: only the fields the LLM filled (merge into form on frontend)."""

    filled: dict = {}  # key -> value for fields that were extracted


class ClarifyMessage(BaseModel):
    """One message in the clarification conversation."""

    role: str  # "assistant" | "user"
    content: str


class ClarifyHistoryMessage(BaseModel):
    """Structured clarify history entry (target-aware)."""

    role: str  # "assistant" | "user"
    kind: str  # "clarify_question" | "clarify_answer"
    target_type: Optional[str] = None  # "parent" | "child"
    target_field: Optional[str] = None
    target_child_type: Optional[str] = None
    text: str = ""


class LastQuestionTarget(BaseModel):
    """Target of the last asked question (so backend can apply user answer correctly)."""

    target_type: Optional[str] = None  # "parent" | "child"
    target_field: Optional[str] = None
    target_child_type: Optional[str] = None


class ClarifyExperienceRequest(BaseModel):
    """Request for interactive clarification: LLM asks questions or returns filled fields."""

    raw_text: str
    card_type: str = "parent"  # "parent" | "child"
    current_card: dict = {}
    conversation_history: list[ClarifyMessage] = []  # past Q&A (legacy)
    card_id: Optional[str] = None  # if set and filled returned, merge and PATCH parent
    child_id: Optional[str] = None  # if set and filled returned, merge and PATCH child
    # Full card family (parent + children) for canonical normalizer
    card_family: Optional[dict] = None
    card_families: Optional[list[dict]] = None  # optional; single-experience flow typically has one family
    # When multiple experiences detected (detect-experiences), pass here to get choose_focus before extraction
    detected_experiences: Optional[list[dict]] = None  # [{ "index": int, "label": str }, ...]
    # When user picked one experience from choose_focus, send experience index as string (e.g. "1")
    focus_parent_id: Optional[str] = None
    # Structured history so planner does not repeat questions
    asked_history: Optional[list[dict]] = None  # list of ClarifyHistoryMessage-like dicts
    # When last message is user answer, send the target of the question we asked
    last_question_target: Optional[dict] = None  # { target_type, target_field, target_child_type }
    max_parent_questions: Optional[int] = None
    max_child_questions: Optional[int] = None


class ClarifyProgress(BaseModel):
    """Progress counters for clarify loop."""

    parent_asked: int = 0
    child_asked: int = 0
    max_parent: int = 2
    max_child: int = 2


class ClarifyOption(BaseModel):
    """One option for choose_focus action."""

    parent_id: str
    label: str


class ClarifyExperienceResponse(BaseModel):
    """Response: either a clarifying question or filled fields (or both empty when done)."""

    clarifying_question: Optional[str] = None
    filled: dict = {}  # when LLM has enough info, fields to merge into form
    # choose_focus: when multiple experiences and no focus
    action: Optional[str] = None  # "choose_focus" | null (ask/stop implied by other fields)
    message: Optional[str] = None  # e.g. "We found multiple experiences..."
    options: Optional[list[dict]] = None  # [{ parent_id, label }] for choose_focus
    focus_parent_id: Optional[str] = None  # set after user picks (echo back or for state)
    # New flow: target-aware and stop control
    should_stop: Optional[bool] = None
    stop_reason: Optional[str] = None
    target_type: Optional[str] = None  # "parent" | "child"
    target_field: Optional[str] = None
    target_child_type: Optional[str] = None
    progress: Optional[dict] = None  # { parent_asked, child_asked, max_parent, max_child }
    missing_fields: Optional[dict] = None  # { parent: [...], child: [...] } (debug)
    asked_history_entry: Optional[dict] = None  # structured entry to append to frontend history
    canonical_family: Optional[dict] = None  # optional: updated canonical family for state


class CommitDraftSetRequest(BaseModel):
    """Optional body for commit: approve only selected card ids, or all if omitted."""

    card_ids: Optional[list[str]] = None


class FinalizeExperienceCardRequest(BaseModel):
    """Request body to finalize a drafted experience card (make visible + embed)."""

    card_id: str


def _location_to_str(v: Any) -> Optional[str]:
    """Convert location (str or dict) to stored string for DB."""
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, dict):
        text = v.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        parts = [x for x in (v.get("city"), v.get("region"), v.get("country")) if isinstance(x, str) and x.strip()]
        return ", ".join(parts) if parts else None
    return None


class _ExperienceCardFields(BaseModel):
    """Shared optional fields for create/patch."""

    title: Optional[str] = None
    normalized_role: Optional[str] = None
    domain: Optional[str] = None
    sub_domain: Optional[str] = None
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None
    location: Optional[str] = None  # accepts str or dict; normalized to str for DB storage
    is_remote: Optional[bool] = None
    employment_type: Optional[str] = None
    summary: Optional[str] = None
    raw_text: Optional[str] = None
    intent_primary: Optional[str] = None
    intent_secondary: Optional[list[str]] = None
    seniority_level: Optional[str] = None
    confidence_score: Optional[float] = None
    experience_card_visibility: Optional[bool] = None


class ExperienceCardCreate(_ExperienceCardFields):
    @field_validator("location", mode="before")
    @classmethod
    def _normalize_location(cls, v: Any) -> Optional[str]:
        return _location_to_str(v)


class ExperienceCardPatch(_ExperienceCardFields):
    @field_validator("location", mode="before")
    @classmethod
    def _normalize_location(cls, v: Any) -> Optional[str]:
        return _location_to_str(v)


class ExperienceCardResponse(BaseModel):
    id: str
    user_id: str
    title: Optional[str] = None
    normalized_role: Optional[str] = None
    domain: Optional[str] = None
    sub_domain: Optional[str] = None
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    team: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None
    location: Optional[str] = None
    is_remote: Optional[bool] = None
    employment_type: Optional[str] = None
    summary: Optional[str] = None
    raw_text: Optional[str] = None
    intent_primary: Optional[str] = None
    intent_secondary: list[str] = []
    seniority_level: Optional[str] = None
    confidence_score: Optional[float] = None
    experience_card_visibility: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# Experience Card Children (dimension cards stored in experience_card_children)
# -----------------------------------------------------------------------------


class ExperienceCardChildPatch(BaseModel):
    """
    Patch payload for ExperienceCardChild.
    Updates are applied into child.value (dimension container).
    Value.items uses ChildValueItem shape: { title, description }.
    """

    items: Optional[list[dict]] = None  # [{ title: str, description: str | None }]


class ChildValueItem(BaseModel):
    """One item in a child card value.items[]."""

    title: str
    description: Optional[str] = None


class ExperienceCardChildResponse(BaseModel):
    """Response DTO for ExperienceCardChild. Just child_type and items."""

    id: str
    parent_experience_id: Optional[str] = None
    child_type: str = ""  # e.g. "metrics", "tools"
    items: list[ChildValueItem] = []

    model_config = ConfigDict(from_attributes=True)


class CardFamilyResponse(BaseModel):
    """One parent experience card and its child cards (for saved cards list)."""

    parent: ExperienceCardResponse
    children: list[ExperienceCardChildResponse] = []
