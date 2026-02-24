from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RawExperienceCreate(BaseModel):
    raw_text: str


class RawExperienceResponse(BaseModel):
    id: str
    raw_text: str
    created_at: Optional[datetime] = None


class RewriteTextResponse(BaseModel):
    """Result of POST /experiences/rewrite: cleaned English text."""

    rewritten_text: str


class TranslateTextResponse(BaseModel):
    """Result of POST /experiences/translate: translated English text."""

    translated_text: str
    source_language_code: Optional[str] = None


class TextToSpeechRequest(BaseModel):
    """Body for POST /experiences/tts: text to speak (Sarvam TTS)."""

    text: str


class TextToSpeechResponse(BaseModel):
    """Result of POST /experiences/tts: base64-encoded WAV audio."""

    audio_base64: str


class CardFamilyV1Response(BaseModel):
    """One parent Experience Card v1 + its child cards (validated)."""

    parent: dict  # Experience Card v1 parent (depth=0)
    children: list[dict] = []  # Experience Card v1 children (depth=1)


class DraftSetV1Response(BaseModel):
    """Result of single-experience pipeline: rewrite → extract one → validate → persist."""

    draft_set_id: str
    raw_experience_id: str
    card_families: list[CardFamilyV1Response]


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
    location: Optional[str] = None
    employment_type: Optional[str] = None
    summary: Optional[str] = None
    raw_text: Optional[str] = None
    intent_primary: Optional[str] = None
    intent_secondary: Optional[list[str]] = None
    seniority_level: Optional[str] = None
    confidence_score: Optional[float] = None
    experience_card_visibility: Optional[bool] = None


class ExperienceCardCreate(_ExperienceCardFields):
    pass


class ExperienceCardPatch(_ExperienceCardFields):
    pass


class ExperienceCardResponse(BaseModel):
    id: str
    user_id: str
    title: Optional[str] = None
    normalized_role: Optional[str] = None
    domain: Optional[str] = None
    sub_domain: Optional[str] = None
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None
    location: Optional[str] = None
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
    Updates are applied into ExperienceCardChild.label and ExperienceCardChild.value (dimension container).
    """

    title: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[list[str]] = None
    time_range: Optional[str] = None
    location: Optional[str] = None


class ExperienceCardChildResponse(BaseModel):
    """Response DTO for ExperienceCardChild."""

    id: str
    relation_type: Optional[str] = None
    title: str = ""
    context: str = ""
    tags: list[str] = []
    headline: str = ""
    summary: str = ""
    topics: list[dict] = []
    time_range: Optional[str] = None
    role_title: Optional[str] = None
    location: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CardFamilyResponse(BaseModel):
    """One parent experience card and its child cards (for saved cards list)."""

    parent: ExperienceCardResponse
    children: list[ExperienceCardChildResponse] = []
