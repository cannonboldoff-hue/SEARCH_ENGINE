"""
Experience Card pipeline prompts.

Designed to take messy, informal, noisy, or incomplete human text and produce:
  rewrite -> detect experiences -> extract single (parent + children) -> validate -> clarify.

The system converts free-form text into structured Experience Cards
(parent + dimension-based children), strictly aligned to Schema V1.

Domains supported: tech + non-tech + mixed.

Enum strings are fetched from this package's experience_card_enums module
(which derives them from src.domain).
"""

from src.prompts.experience_card_enums import (
    INTENT_ENUM,
    CHILD_INTENT_ENUM,
    CHILD_RELATION_TYPE_ENUM,
    ENTITY_TYPES,
    ALLOWED_CHILD_TYPES_STR,
)

# -----------------------------------------------------------------------------
# 1. Rewrite + Cleanup (single pass)
# -----------------------------------------------------------------------------

PROMPT_REWRITE = """You are a careful rewrite + cleanup engine.

Goal: Rewrite the user's message into clear, grammatically correct English AND
clean it to make structured extraction reliable.

STRICT RULES:
1) Do NOT add new facts. Do NOT guess missing details. Do NOT change meaning.
2) Keep all proper nouns, names, company names, tools, and numbers EXACTLY as written.
3) Preserve ordering and intent. Lists must remain lists.
4) Expand abbreviations ONLY when unambiguous.
5) Remove filler, repetition, and obvious typos.
6) Output ONLY the rewritten, cleaned text. No commentary. No JSON.

User message:
{{USER_TEXT}}
"""


# -----------------------------------------------------------------------------
# 1b. Detect distinct experiences (count + labels for "which one to process")
# -----------------------------------------------------------------------------

PROMPT_DETECT_EXPERIENCES = """You are an experience detection engine.

Read the cleaned text below and identify every DISTINCT experience block (job, role, project, company, or time-bound work experience).

Rules:
- Each distinct role, company, or project = one experience. Split on: different employers, "then", "after that", "also", "another role", different time ranges.
- Return ONLY valid JSON. No markdown, no commentary.

Output format:
{
  "count": <number of distinct experiences found, 0 if none>,
  "experiences": [
    { "index": 1, "label": "<short label, e.g. 'Razorpay, backend, 2 years'>", "suggested": false },
    { "index": 2, "label": "<short label>", "suggested": true }
  ]
}

- "label" must be a short one-line summary (company/role/duration) so the user can choose.
- Set "suggested": true for exactly ONE experience: the one that is most structured or has the most detail (e.g. has clear dates, company, role). If only one experience, set suggested: true for it. If none, return count 0 and empty experiences array.

Cleaned text:
{{CLEANED_TEXT}}

Return valid JSON only:
"""

# -----------------------------------------------------------------------------
# 2. Extract SINGLE experience by index (one at a time)
# -----------------------------------------------------------------------------

PROMPT_EXTRACT_SINGLE_CARDS = """You are a structured data extraction system.

The cleaned text below contains MULTIPLE distinct experience blocks. Your task is to extract ONLY ONE of them.

CRITICAL: Extract ONLY the experience at position {{EXPERIENCE_INDEX}} (1 = first experience in the text, 2 = second, etc.). There are {{EXPERIENCE_COUNT}} distinct experiences total. Ignore all others.

Return exactly ONE parent and its child dimension cards. Use the schema below (parent with all keys, children with allowed child_type). Output format:

{
  "parents": [
    {
      "parent": { ... single parent with all required keys ... },
      "children": [ ... ]
    }
  ]
}

- parent: all required keys (title, normalized_role, domain, company_name, start_date, end_date, summary, intent_primary, etc.). intent_primary MUST be one of: {{INTENT_ENUM}}
- children: YOU MUST EXTRACT CHILD DIMENSION CARDS when the experience mentions them. Allowed child_type: {{ALLOWED_CHILD_TYPES}}. Create one child per dimension present (e.g. project, outcome, skill, tool). Each child must have child_type, value (headline, summary, raw_text, time, location, company, topics, tooling, outcomes, etc.). Do NOT output multiple children with the same child_type—merge into one child per type. Do NOT create children that merely restate the parent.
- MANDATORY INHERIT FROM PARENT: Every child's value MUST include time and location (and company when parent has it). If the user did NOT explicitly state a different time range or location for that specific child, you MUST copy them from the parent into the child's value: set value.time from the parent's time/start_date/end_date/time_text, and value.location from the parent's location. Set value.company from the parent's company_name when the user did not state a different company for that child. So in your JSON output, each child must have value.time and value.location populated (from parent when not explicit); only use a different or empty value when the text explicitly says so for that child.
- raw_text in parent must be a verbatim excerpt from the cleaned text for THIS experience only.
- Do NOT invent facts. Use null for missing fields.
- Dates: start_date, end_date, and time.start/time.end MUST be YYYY-MM-DD or YYYY-MM only (e.g. 2020-01, 2022-06). Do NOT use month names (Jan, January) or natural language.

Cleaned text:
{{USER_TEXT}}

Extract ONLY the {{EXPERIENCE_INDEX}}-th experience (of {{EXPERIENCE_COUNT}}). Return valid JSON only:
"""

# -----------------------------------------------------------------------------
# 4. Fill missing fields only (no full extract; for edit-form "Update from messy text")
# -----------------------------------------------------------------------------

PROMPT_FILL_MISSING_FIELDS = """You are a fill-missing-fields extractor. You do NOT create full cards.

Input:
1) Cleaned text (user-provided snippet).
2) Current card as JSON. Some fields are empty ("" or null). Only those are "missing".

Task: From the cleaned text, extract values ONLY for fields that are currently missing or empty in the current card. Do NOT overwrite or change fields that already have a value.

Allowed keys for this card type (return ONLY these keys when you have a value; omit any key you cannot infer):
{{ALLOWED_KEYS}}

Rules:
- Return a single JSON object. No markdown, no commentary, no array wrapper.
- Include only keys you can fill from the text. Omit keys that are already set in current_card or that you cannot infer.
- Dates: MUST use YYYY-MM-DD or YYYY-MM only (e.g. 2020-01). Do NOT use month names (Jan, January) or natural language.
- For intent_secondary use a comma-separated string or array of strings.
- For tags use a comma-separated string.

Current card (missing/empty fields should be filled from text below):
{{CURRENT_CARD_JSON}}

Cleaned text:
{{CLEANED_TEXT}}

Return valid JSON only:
"""

# -----------------------------------------------------------------------------
# 4b. Opening question when user has not shared anything yet (LLM-generated)
# -----------------------------------------------------------------------------

PROMPT_OPENING_QUESTION = """You are having a friendly conversation to help someone add an experience (e.g. a job, project, or something they're proud of). They have not shared anything yet.

Your task: Ask ONE short, natural question to invite them to share. Be curious and human—like a colleague or coach. Do NOT sound like a form or instructions (e.g. no "Please describe", "Please provide", or listing fields like "role, company, dates"). Just ask a single, conversational question.

Return ONLY valid JSON with this exact shape, nothing else:
{"clarifying_question": "Your one short question here?"}
"""

# -----------------------------------------------------------------------------
# 6. Clarify flow: Planner (JSON only)
# -----------------------------------------------------------------------------

PROMPT_CLARIFY_PLANNER = """You are a clarification planner for experience cards. This is POST-EXTRACTION: we already have an extracted card. You decide the NEXT step only: ask one TARGETED field question, autofill from text, or stop.

Inputs:
- Cleaned experience text
- Current card family (canonical JSON): parent + children
- Asked history: which questions were already asked (do NOT repeat)
- Limits: max parent questions, max child questions
- Policy: parent-first until parent is "good enough", then optional child questions

Good enough parent = has headline or role, summary, and at least one of: company_name, time, location.

Output: ONE JSON object only. No markdown, no commentary.

Allowed action: "ask" | "autofill" | "stop" (do NOT use choose_focus; backend handles multiple experiences.)
Allowed target_type: "parent" | "child" | null
Allowed parent target_field: headline, role, summary, company_name, team, time, location, domain, sub_domain, intent_primary
Allowed target_child_type (when target_type=child): metrics, tools, achievements, responsibilities, collaborations, domain_knowledge, exposure, education, certifications

Rules:
- You are in post-extraction phase. Only field-targeted actions. Never suggest discovery or onboarding (e.g. "what did you build", "tell me more about your experience").
- Ask at most ONE thing at a time. The question will be written separately and must be specific to the target field only.
- Prefer parent until parent is good enough, then optionally 1–2 child questions.
- AUTOFILL RULES: Only autofill when the text EXPLICITLY provides the exact value (e.g., company name stated verbatim, or specific dates like "Jan 2020 to March 2022"). DO NOT autofill time with made-up or inferred dates — if only duration is mentioned (e.g., "2 months") without specific start/end dates or years, choose "ask" instead. DO NOT hallucinate or guess missing information.
- NO-REPEAT: Never propose a field already asked (check asked_history). Never propose a field already filled in the card.
- For autofill: set action=autofill, target_type, target_field (or target_child_type for child), and autofill_patch with ONLY the field(s) to add.
- For stop: set action=stop when parent is good enough and no high-value ask remains, or limits reached.

Output format (JSON only):
{
  "action": "ask|autofill|stop",
  "target_type": "parent|child|null",
  "target_field": "company_name|time|location|summary|...|null",
  "target_child_type": "metrics|tools|...|null",
  "reason": "short reason",
  "confidence": "high|medium|low",
  "autofill_patch": null
}

When action=autofill, autofill_patch must be an object that only updates the target field (e.g. {"company_name": "ABC Inc"} or {"time": {"start": "2020-01", "end": "2022-06"}}). For time: only autofill if text has explicit start/end dates or years; if only duration is given, use action=ask instead.

Canonical card family:
{{CANONICAL_CARD_JSON}}

Cleaned experience text:
{{CLEANED_TEXT}}

Asked history (do not repeat these):
{{ASKED_HISTORY_JSON}}

Limits: max parent questions = {{MAX_PARENT}}, max child questions = {{MAX_CHILD}}. Parent asked so far: {{PARENT_ASKED_COUNT}}, child asked: {{CHILD_ASKED_COUNT}}.

Priority hints - parent: headline, role, summary, company_name, time, location, domain, intent_primary. Child: metrics, tools, achievements, responsibilities, collaborations.

Return valid JSON only:
"""

# -----------------------------------------------------------------------------
# 7. Clarify flow: Question writer (phrasing only)
# -----------------------------------------------------------------------------

PROMPT_CLARIFY_QUESTION_WRITER = """You write exactly ONE short, natural clarification question for a SPECIFIC field on an experience card.

Phase: POST_EXTRACTION. We already have an extracted experience. You are ONLY asking for one missing field.

You are given the validated plan: target_type (parent or child), target_field (e.g. company_name, time, location), and optionally target_child_type for child cards.

STRICT RULES:
- Ask exactly one question. Be specific to the target_field ONLY (e.g. company_name → "Which company was this at?", time → "Roughly when was this?", location → "Where was this based?").
- Sound human and curious, like a colleague. Do NOT sound like a form.
- FORBIDDEN in post-extraction (never use): "What's something cool you've built", "Tell me more about your experience", "What did you work on?", "Can you share more?", "What would you like to add?", "Describe your experience", "Tell me about a...", "What's one experience...". These are onboarding/discovery prompts, not field clarifications.
- Do not ask for things already present in the card context.
- Keep it short (one sentence). Be concrete: name the field implicitly (e.g. company, time period, location, metric).

Good examples:
- company_name → "What was the name of the company?" or "Which organization was this at?"
- time → "Which year or time period was this?" or "Roughly when did you do this?"
- location → "Where was this based—city or country?"
- metrics → "What was the main metric here—e.g. revenue, bookings, or something else?"

Output: JSON only. No markdown, no commentary.

{
  "question": "Your one short, field-specific question?",
  "reason_short": "Why this question (one phrase)"
}

Validated plan:
{{VALIDATED_PLAN_JSON}}

Minimal card context (for reference only; do not ask for what is already set):
{{CARD_CONTEXT_JSON}}

Return valid JSON only:
"""

# -----------------------------------------------------------------------------
# 8. Clarify flow: Apply answer (patch only)
# -----------------------------------------------------------------------------

PROMPT_CLARIFY_APPLY_ANSWER = """You convert the user's answer into a small patch for the experience card. You ONLY update the target field (and tightly related nested fields like time.start/time.end or location.city/country).

Inputs:
- Validated plan: target_type, target_field (or target_child_type for child)
- User's answer (raw text)
- Current canonical card (for context)

Rules:
- Output a patch that ONLY modifies the target field. For time: patch may include time.start, time.end, time.ongoing, time.text. For location: location.city, location.country, location.text.
- No hallucinations. Use the user's words when uncertain.
- If the answer is unclear or unusable, set needs_retry=true and provide a short retry_question to ask for clarification.
- Preserve original wording when appropriate.
- Dates: MUST use YYYY-MM or YYYY-MM-DD only (e.g. 2020-01). Do NOT use month names; convert user phrases like "Jan 2020" to 2020-01.

Output: JSON only. No markdown, no commentary.

{
  "patch": { ... only target field updates ... },
  "confidence": "high|medium|low",
  "needs_retry": false,
  "retry_question": null
}

When needs_retry is true, retry_question should be one short question. Patch may be empty in that case.

Validated plan:
{{VALIDATED_PLAN_JSON}}

User answer:
{{USER_ANSWER}}

Current canonical card (relevant part):
{{CANONICAL_CARD_JSON}}

Return valid JSON only:
"""

# -----------------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------------

def fill_prompt(
    template: str,
    *,
    user_text: str | None = None,
    person_id: str | None = None,
    parent_and_children_json: str | None = None,
    raw_text_original: str | None = None,
    raw_text_cleaned: str | None = None,
    cleaned_text: str | None = None,
    current_card_json: str | None = None,
    allowed_keys: str | None = None,
    conversation_history: str | None = None,
    experience_index: int | None = None,
    experience_count: int | None = None,
    canonical_card_json: str | None = None,
    asked_history_json: str | None = None,
    max_parent: int | None = None,
    max_child: int | None = None,
    parent_asked_count: int | None = None,
    child_asked_count: int | None = None,
    validated_plan_json: str | None = None,
    card_context_json: str | None = None,
    user_answer: str | None = None,
) -> str:
    out = template
    out = out.replace("{{INTENT_ENUM}}", INTENT_ENUM)
    out = out.replace("{{CHILD_INTENT_ENUM}}", CHILD_INTENT_ENUM)
    out = out.replace("{{CHILD_RELATION_TYPE_ENUM}}", CHILD_RELATION_TYPE_ENUM)
    out = out.replace("{{ALLOWED_CHILD_TYPES}}", ALLOWED_CHILD_TYPES_STR)

    if user_text is not None:
        out = out.replace("{{USER_TEXT}}", user_text)
    if person_id is not None:
        out = out.replace("{{PERSON_ID}}", person_id)
    if parent_and_children_json is not None:
        out = out.replace("{{PARENT_AND_CHILDREN_JSON}}", parent_and_children_json)
    if raw_text_original is not None:
        out = out.replace("{{RAW_TEXT_ORIGINAL}}", raw_text_original)
    if raw_text_cleaned is not None:
        out = out.replace("{{RAW_TEXT_CLEANED}}", raw_text_cleaned)
    if cleaned_text is not None:
        out = out.replace("{{CLEANED_TEXT}}", cleaned_text)
    if current_card_json is not None:
        out = out.replace("{{CURRENT_CARD_JSON}}", current_card_json)
    if allowed_keys is not None:
        out = out.replace("{{ALLOWED_KEYS}}", allowed_keys)
    if conversation_history is not None:
        out = out.replace("{{CONVERSATION_HISTORY}}", conversation_history)
    elif "{{CONVERSATION_HISTORY}}" in out:
        out = out.replace("{{CONVERSATION_HISTORY}}", "(No messages yet)")
    if experience_index is not None:
        out = out.replace("{{EXPERIENCE_INDEX}}", str(experience_index))
    if experience_count is not None:
        out = out.replace("{{EXPERIENCE_COUNT}}", str(experience_count))
    if canonical_card_json is not None:
        out = out.replace("{{CANONICAL_CARD_JSON}}", canonical_card_json)
    if asked_history_json is not None:
        out = out.replace("{{ASKED_HISTORY_JSON}}", asked_history_json)
    if max_parent is not None:
        out = out.replace("{{MAX_PARENT}}", str(max_parent))
    if max_child is not None:
        out = out.replace("{{MAX_CHILD}}", str(max_child))
    if parent_asked_count is not None:
        out = out.replace("{{PARENT_ASKED_COUNT}}", str(parent_asked_count))
    if child_asked_count is not None:
        out = out.replace("{{CHILD_ASKED_COUNT}}", str(child_asked_count))
    if validated_plan_json is not None:
        out = out.replace("{{VALIDATED_PLAN_JSON}}", validated_plan_json)
    if card_context_json is not None:
        out = out.replace("{{CARD_CONTEXT_JSON}}", card_context_json)
    if user_answer is not None:
        out = out.replace("{{USER_ANSWER}}", user_answer)

    return out
