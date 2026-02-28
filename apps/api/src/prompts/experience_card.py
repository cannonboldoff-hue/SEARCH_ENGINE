"""
Experience Card pipeline prompts.

Designed to take messy, informal, noisy, or incomplete human text and produce:
  rewrite -> detect experiences -> extract single (parent + children) -> validate -> clarify.

The system converts free-form text into structured Experience Cards
(parent + dimension-based children), with structured parent and child cards.

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
    SENIORITY_LEVEL_ENUM,
    EMPLOYMENT_TYPE_ENUM,
    COMPANY_TYPE_ENUM,
    EXPERIENCE_RELATION_TYPE_ENUM,
)

# -----------------------------------------------------------------------------
# 1. Rewrite + Cleanup (single pass)
# -----------------------------------------------------------------------------

PROMPT_REWRITE = """You are a rewrite and cleanup engine. Your only job is to make the input easier to parse — not to interpret, summarize, or enrich it.

GOAL:
Rewrite the input into clear, grammatically correct English. Remove noise. Preserve all meaning and facts exactly as given.

RULES:
1. Do NOT add facts, infer missing details, or change meaning in any way.
2. Keep all proper nouns, names, places, organizations, tools, numbers, and dates exactly as written.
3. Preserve structure — if the input has a list, keep it a list. If it has an order, keep that order.
4. Expand abbreviations only when the expansion is unambiguous.
5. Remove filler words, repetition, typos, and grammatical noise.
6. If the input is already clean, return it as-is. Do not rephrase for the sake of it.
7. Output ONLY the rewritten text. No explanations, no commentary, no JSON, no preamble.

INPUT:
{{USER_TEXT}}
"""


# -----------------------------------------------------------------------------
# 2. Detect distinct experiences (count + labels for "which one to process")
# -----------------------------------------------------------------------------

PROMPT_DETECT_EXPERIENCES = """You are an experience detection engine.

Read the cleaned text below and identify every DISTINCT experience block — any bounded period of activity tied to a role, project, organization, or pursuit. This includes jobs, freelance work, education, side projects, business ventures, research, or any other meaningful engagement.

RULES:
1. Each distinct role, organization, or project = one experience.
2. Split on: different employers or clients, different projects, "then", "after that", "also", "another role", "meanwhile", or different time ranges.
3. Do NOT merge experiences that happened in parallel if they are clearly distinct.
4. Do NOT split a single experience just because the person changed responsibilities within the same role/org.
5. If no experiences are found, return count 0 and an empty array.
6. Return ONLY valid JSON. No markdown, no commentary, no preamble.

OUTPUT FORMAT:
{
  "count": <number of distinct experiences>,
  "experiences": [
    {
      "index": 1,
      "label": "<short one-line summary: org/role/duration if available>",
      "suggested": false
    },
    {
      "index": 2,
      "label": "<short one-line summary>",
      "suggested": true
    }
  ]
}

LABEL RULES:
- Keep labels short and scannable (one line).
- Include whatever is available: org name, role, time range, or project name.
- Do not fabricate details not present in the text.

SUGGESTED RULES:
- Set "suggested": true for exactly ONE experience.
- Prefer the one with the most structured detail (clear dates, org name, role).
- If all are equally detailed, prefer the most recent.
- If only one experience exists, it is always suggested.

CLEANED TEXT:
{{CLEANED_TEXT}}

Return valid JSON only:
"""

# -----------------------------------------------------------------------------
# 3. Extract SINGLE experience by index (one at a time)
# -----------------------------------------------------------------------------

PROMPT_EXTRACT_SINGLE_CARDS = """You are a structured data extraction system.

The cleaned text below describes one or more distinct experiences. Your task is to extract ONLY ONE of them — the experience at position {{EXPERIENCE_INDEX}} of {{EXPERIENCE_COUNT}}.

Ignore all other experiences entirely.

---

OUTPUT STRUCTURE:
{
  "parents": [
    {
      "parent": { ...all required parent fields... },
      "children": [ ...child dimension cards... ]
    }
  ]
}

---

PARENT FIELDS:
Extract all fields you can from the text. Use null for anything not mentioned. Do not invent.

- title              : short descriptive title for this experience
- normalized_role    : standardized role name (e.g. "Software Engineer", "Freelance Plumber", "Family Business Owner")
- domain             : broad domain (e.g. "Engineering", "Finance", "Trades", "Education", "Informal Trade")
- sub_domain         : more specific area if present (e.g. "Backend", "Tax Law", "Electrical", "Street Vending")
- company_name       : organization, employer, client, institution, or family business name. null if independent/informal.
- company_type       : MUST be one of: {{COMPANY_TYPE_ENUM}}
- team               : team or department name if mentioned
- location           : object with fields:
    - city            : city name or null
    - region          : state/region or null
    - country         : country or null
    - text            : user's original location phrasing or null
    - is_remote       : true if explicitly remote, false if explicitly on-site, null if not mentioned
- employment_type    : MUST be one of: {{EMPLOYMENT_TYPE_ENUM}}
- start_date         : YYYY-MM or YYYY-MM-DD only. No month names. null if unknown.
- end_date           : YYYY-MM or YYYY-MM-DD only. null if ongoing or unknown.
- is_current         : true if this is their current engagement, else false
- summary            : 2–4 sentence summary of what they did and why it mattered
- intent_primary     : MUST be one of: {{INTENT_ENUM}}
- intent_secondary   : list of additional intents from the same enum, or []
- seniority_level    : MUST be one of: {{SENIORITY_LEVEL_ENUM}}. null if unclear.
- raw_text           : verbatim excerpt from the cleaned text for THIS experience only
- confidence_score   : float 0.0–1.0 reflecting how complete and clear the extracted data is
- relations          : always [] — populated in a later step after all cards are extracted

---

COMPANY TYPE GUIDANCE:
- Person runs their own shop / street stall / informal trade → "informal"
- Person works in parent's or family's business → "family_business"
- Person learned a trade under a master or ustaad → "master_apprentice"
- Person is fully independent with no org → "self_employed"

---

CHILDREN:
Extract child dimension cards for every distinct dimension the experience mentions.
Allowed child_type values: {{ALLOWED_CHILD_TYPES}}

Child format — each child has: child_type, value: { raw_text, items[] }

Rules:
1. Create ONE child per child_type. Group all same-type evidence into ONE child with many items.
2. Do NOT create multiple children of the same child_type for the same parent.
3. value.items is an array. Each item: { "title": "short label", "description": "one line" or null }
4. Add as many items as needed per child. Example: metrics child can have "₹15 lakh sales" / "Generated in 2 months" AND "20 active partners" / "Built through collaborations."
5. value.raw_text: verbatim excerpt for this child only.
6. Prefer short, human-readable titles. Prefer one-line descriptions.
7. Do NOT output rigid nested schemas (actions, outcomes, tooling) inside value — use items[] only.
8. Do NOT invent facts. Use only grounded evidence.
9. Do NOT create children that merely restate the parent summary.
10. Do NOT include a top-level "label" field on children — it is not stored.

Examples:
{
  "child_type": "tools",
  "value": {
    "raw_text": "verbatim excerpt for this child only",
    "items": [
      { "title": "Python", "description": "Used for backend services." },
      { "title": "Bloomberg API", "description": null }
    ]
  }
}

- metrics: items: [
    { "title": "₹15 lakh sales", "description": "Generated in 2 months." },
    { "title": "20 active partners", "description": "Built through Mumbai studio collaborations." }
  ]
- collaborations: items: [{ "title": "Studio partnerships", "description": "Mediated across Mumbai." }]

---

GLOBAL RULES:
- Extract ONLY the {{EXPERIENCE_INDEX}}-th experience. Ignore all others.
- Do NOT invent facts. If a field is absent from the text, use null or [].
- Dates MUST be YYYY-MM or YYYY-MM-DD. Never use "Jan", "January", or natural language dates.
- raw_text in parent must be a verbatim excerpt from the cleaned text for this experience only.
- relations must always be [] — do not attempt to link cards during extraction.
- Return ONLY valid JSON. No markdown, no commentary, no preamble.

---

CLEANED TEXT:
{{USER_TEXT}}

Extract ONLY the {{EXPERIENCE_INDEX}}-th experience (of {{EXPERIENCE_COUNT}}). Return valid JSON only:
"""


# -----------------------------------------------------------------------------
# 4. Fill missing fields only (no full extract; for edit-form "Update from messy text")
# -----------------------------------------------------------------------------

PROMPT_FILL_MISSING_FIELDS = """You are a targeted field-filling extractor. Your only job is to find values for fields that are currently empty. You do not rewrite, summarize, or create new cards.

---

INPUTS:
1. Current card (JSON) — fields that are null, "", or [] are considered missing.
2. Cleaned text — the source you must extract from.
3. Allowed keys — the only keys you may return.

---

TASK:
Read the cleaned text and extract values ONLY for fields that are missing in the current card.
{{ITEMS_INSTRUCTION}}

---

RULES:
1. Do NOT overwrite or modify fields that already have a value in the current card.
2. Only return keys listed in allowed_keys. Ignore everything else.
3. Only return keys you can confidently fill from the text. Omit keys you cannot infer.
4. Do NOT invent or guess. If the text doesn't say it, leave the key out.
5. Dates MUST be YYYY-MM or YYYY-MM-DD only. Never use month names or natural language.
6. For array fields (e.g. intent_secondary), return a JSON array of strings.
7. Return a single flat JSON object. No markdown, no commentary, no array wrapper, no nesting.

---

ALLOWED KEYS (return only these):
{{ALLOWED_KEYS}}

---

CURRENT CARD (do not touch fields that already have values):
{{CURRENT_CARD_JSON}}

---

CLEANED TEXT (extract from this only):
{{CLEANED_TEXT}}

Return valid JSON only:
"""

# Instruction injected into PROMPT_FILL_MISSING_FIELDS when card_type=child (for items append).
FILL_MISSING_ITEMS_APPEND_INSTRUCTION = (
    "For items: extract achievements, metrics, or details from the cleaned text. "
    "If the current card already has items, also extract any ADDITIONAL achievements from the text "
    "and return them as new items to append. Return items as: "
    '[{"subtitle": "short title", "sub_summary": "description"}] or [{"title": "...", "description": "..."}]. '
    "Return ONLY the new items to add (not existing ones), so the frontend can append them."
)

# -----------------------------------------------------------------------------
# 5. Clarify flow: Planner (JSON only)
# -----------------------------------------------------------------------------
PROMPT_CLARIFY_PLANNER = """You are a curious clarification planner. A card has already been extracted. Your job is to decide the single best next action: ask, autofill, or stop.

Be curious and thorough. You want to extract as much rich information as possible. Keep asking relevant questions until you truly cannot get more.

---

ACTIONS:
"ask"      → a field is missing, applicable, and not yet asked — PREFER asking over stopping
"autofill" → the text explicitly and unambiguously contains the value
"stop"     → nothing more worth extracting, all applicable fields resolved, OR limits reached

---

STOP CONDITION:
Stop ONLY when ALL of the following are true:
- Every applicable field has a value, OR has already been asked, OR has been set to null as inapplicable
- No high-value child dimensions remain unasked within limits
- Limits are reached

Do NOT stop early. Stay curious. If there is any valuable field you haven't asked about and it applies to this experience, choose "ask". Extract as much relevant and applicable data as possible.

---

INAPPLICABILITY RULES:
When a field does not apply given the nature of the experience, set it to null silently. Never ask about it.

Examples:
- company_name, team      → null when person is freelance, self-employed, or independent
- end_date                → null when experience is explicitly ongoing
- location.city/region    → null when experience is explicitly fully remote with no base
- seniority_level         → null when experience is non-hierarchical (volunteer, hobbyist, student)
- employment_type         → null when context makes categorization meaningless
- relations               → NEVER ask — handled separately after all cards exist

General rule: if asking would be confusing or irrelevant given what the text already tells
you about the nature of this experience → inapplicable → null.

---

PRIORITY ORDER:
1. Parent fields: title/role → summary → company_name → employment_type → company_type →
                  time → location.city → location.is_remote → domain → intent_primary →
                  seniority_level
2. Child fields (if limits allow): metrics → tools → achievements → responsibilities →
                  collaborations → domain_knowledge → exposure → education → certifications

---

RULES:
1. Ask at most ONE thing per turn. Never combine questions.
2. Never ask about a field in asked_history.
3. Never ask about a field already filled in the card.
4. Never ask about an inapplicable field — set it to null instead.
5. Never ask about relations — handled after all cards exist.
6. Never ask generic or open-ended questions ("tell me more", "what did you build").
7. AUTOFILL only when text explicitly and unambiguously states the value:
   - Company name verbatim → autofill
   - Specific dates ("Jan 2020 to March 2022") → autofill
   - "fully remote" or "work from home" explicitly stated → autofill is_remote: true
   - Duration only ("2 months", "a couple of years") → ask instead
   - Do not infer, guess, or hallucinate
8. autofill_patch must contain ONLY the target field.
9. Never propose choose_focus or discovery actions — handled upstream.

---

ALLOWED VALUES:

action: "ask" | "autofill" | "stop"
target_type: "parent" | "child" | null

parent target_field:
  title, role, summary, company_name, team, time, location,
  location.is_remote, domain, sub_domain, intent_primary,
  seniority_level, employment_type, company_type

target_child_type:
  metrics, tools, achievements, responsibilities, collaborations,
  domain_knowledge, exposure, education, certifications

---

OUTPUT FORMAT (return this JSON object only):
{
  "action": "ask | autofill | stop",
  "target_type": "parent | child | null",
  "target_field": "<field name> | null",
  "target_child_type": "<child type> | null",
  "reason": "<one short sentence explaining why>",
  "confidence": "high | medium | low",
  "autofill_patch": null
}

When action=autofill:
  autofill_patch is a flat object with only the target field.
  Examples:
    {"company_name": "ABC Inc"}
    {"company_type": "family_business"}
    {"location": {"is_remote": true, "city": null}}
    {"company_name": null}  <- inapplicable field

When action=ask or stop:
  autofill_patch must be null.

---

CANONICAL CARD FAMILY:
{{CANONICAL_CARD_JSON}}

CLEANED TEXT:
{{CLEANED_TEXT}}

ASKED HISTORY:
{{ASKED_HISTORY_JSON}}

LIMITS:
Max parent questions: {{MAX_PARENT}} | Asked so far: {{PARENT_ASKED_COUNT}}
Max child questions: {{MAX_CHILD}}  | Asked so far: {{CHILD_ASKED_COUNT}}

Return valid JSON only:
"""

# -----------------------------------------------------------------------------
# 6. Clarify flow: Question writer (phrasing only)
# -----------------------------------------------------------------------------

PROMPT_CLARIFY_QUESTION_WRITER = """You are a curious clarification question writer. A planner has decided what to ask next. Your job is to write exactly one natural, conversational question that sounds genuinely curious and interested.

---

TONE:
Sound curious and engaged—as if you genuinely want to learn more. Ask questions that invite the user to share, not to fill a form. Use phrasing like "I'm curious…", "I'd love to know…", "What was that like?", "How did that work?" when it fits naturally.

---

RULES:
1. Write ONE question only. Never combine multiple questions.
2. Be conversational and brief — this is a chat interface, not a form.
3. The question must target ONLY the field or child type specified in the plan.
4. Never ask generic questions ("tell me more", "anything else?").
5. For parent fields: ask directly and specifically about that field, with a curious tone.
6. For child dimensions: invite the user to share naturally—make them want to add details.
   - Good: "I'm curious—which tools or technologies did you use in this role?"
   - Good: "What kinds of results did you see? I'd love to capture those."
   - Bad:  "Please list your tools."
   - Bad:  "What tools did you use, and what were your responsibilities?"
7. Reference card context naturally to make the question feel informed, not robotic.
8. Do NOT explain why you are asking. Just ask, with genuine curiosity.
9. Output the question as plain text only. No JSON, no preamble, no formatting.

---

PLAN:
{{CLARIFY_PLAN_JSON}}

CANONICAL CARD FAMILY (for context):
{{CANONICAL_CARD_JSON}}

Write the question now:
"""

# -----------------------------------------------------------------------------
# 7. Clarify flow: Apply answer (patch only)
# -----------------------------------------------------------------------------

PROMPT_CLARIFY_APPLY_ANSWER = """You are a clarification answer processor. Convert the user's answer into a minimal patch for the experience card. You ONLY update the target field — nothing else.

---

INPUTS:
- Validated plan: what field or child dimension was asked about
- User's answer: raw text from the user
- Current canonical card: for context only — do not modify fields not in the plan

---

RULES:
1. Patch ONLY the target field specified in the plan. Never touch other fields.
2. For nested fields, patch only the relevant sub-fields:
   - time     → time.start, time.end, time.ongoing, time.text
   - location → location.city, location.country, location.is_remote, location.text
3. Preserve the user's original wording where appropriate. Do not paraphrase.
4. Do NOT hallucinate. If the user's answer does not contain the value, do not invent it.
5. If the user indicates the field is not applicable → set field to null.
6. If the answer is unclear, off-topic, or unusable → set needs_retry: true. Write one short retry_question that sounds curious and helpful—e.g. "I'd love to capture that—do you remember roughly when that was?" rather than "Please provide more details."
7. Dates MUST be YYYY-MM or YYYY-MM-DD only:
   - "Jan 2020" → "2020-01"
   - "March 2022" → "2022-03"
   - "2 years ago" → do not guess → set needs_retry: true
8. Return valid JSON only. No markdown, no commentary, no preamble.

---

OUTPUT FORMAT:
{
  "patch": { ... only target field updates ... },
  "confidence": "high | medium | low",
  "needs_retry": false,
  "retry_question": null
}

When needs_retry=true:
{
  "patch": {},
  "confidence": "low",
  "needs_retry": true,
  "retry_question": "<one short clarifying question>"
}

Examples:

Target = time, user says "Jan 2020 to March 2022":
{ "patch": { "time": { "start": "2020-01", "end": "2022-03", "ongoing": false, "text": "Jan 2020 to March 2022" } }, "confidence": "high", "needs_retry": false, "retry_question": null }

Target = company_name, user says "I was freelancing, no company":
{ "patch": { "company_name": null }, "confidence": "high", "needs_retry": false, "retry_question": null }

Target = time, user says "about 2 years":
{ "patch": {}, "confidence": "low", "needs_retry": true, "retry_question": "I'm curious—do you remember roughly when you started and when it ended? Even approximate dates help." }

For target_child_type (child dimension), patch adds items to that child. Append to value.items[]:
Target = tools, user says "I used Python and SQL for analytics":
{
  "patch": {
    "value": {
      "items": [
        { "title": "Python", "description": "Used for analytics" },
        { "title": "SQL", "description": "Used for analytics" }
      ]
    }
  },
  "confidence": "high",
  "needs_retry": false,
  "retry_question": null
}

Target = metrics, user says "15 lakh in 2 months":
{
  "patch": {
    "value": {
      "items": [
        { "title": "₹15 lakh", "description": "Generated in 2 months." }
      ]
    }
  },
  "confidence": "high",
  "needs_retry": false,
  "retry_question": null
}

---

VALIDATED PLAN:
{{VALIDATED_PLAN_JSON}}

USER'S ANSWER:
{{USER_ANSWER}}

CANONICAL CARD (for context):
{{CANONICAL_CARD_JSON}}

Return valid JSON only:
"""

# -----------------------------------------------------------------------------
# 8. Helper: fill_prompt
# -----------------------------------------------------------------------------

_DEFAULT_REPLACEMENTS: dict[str, str] = {
    "{{INTENT_ENUM}}": INTENT_ENUM,
    "{{CHILD_INTENT_ENUM}}": CHILD_INTENT_ENUM,
    "{{CHILD_RELATION_TYPE_ENUM}}": CHILD_RELATION_TYPE_ENUM,
    "{{ALLOWED_CHILD_TYPES}}": ALLOWED_CHILD_TYPES_STR,
    "{{COMPANY_TYPE_ENUM}}": COMPANY_TYPE_ENUM,
    "{{EMPLOYMENT_TYPE_ENUM}}": EMPLOYMENT_TYPE_ENUM,
    "{{SENIORITY_LEVEL_ENUM}}": SENIORITY_LEVEL_ENUM,
    "{{EXPERIENCE_RELATION_TYPE_ENUM}}": EXPERIENCE_RELATION_TYPE_ENUM,
}

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
    items_instruction: str | None = None,
) -> str:
    kwargs_map = {
        "{{USER_TEXT}}": user_text,
        "{{PERSON_ID}}": person_id,
        "{{PARENT_AND_CHILDREN_JSON}}": parent_and_children_json,
        "{{RAW_TEXT_ORIGINAL}}": raw_text_original,
        "{{RAW_TEXT_CLEANED}}": raw_text_cleaned,
        "{{CLEANED_TEXT}}": cleaned_text,
        "{{CURRENT_CARD_JSON}}": current_card_json,
        "{{ALLOWED_KEYS}}": allowed_keys,
        "{{CONVERSATION_HISTORY}}": conversation_history,
        "{{EXPERIENCE_INDEX}}": experience_index,
        "{{EXPERIENCE_COUNT}}": experience_count,
        "{{CANONICAL_CARD_JSON}}": canonical_card_json or card_context_json,
        "{{ASKED_HISTORY_JSON}}": asked_history_json,
        "{{MAX_PARENT}}": max_parent,
        "{{MAX_CHILD}}": max_child,
        "{{PARENT_ASKED_COUNT}}": parent_asked_count,
        "{{CHILD_ASKED_COUNT}}": child_asked_count,
        "{{VALIDATED_PLAN_JSON}}": validated_plan_json,
        "{{CLARIFY_PLAN_JSON}}": validated_plan_json,
        "{{CARD_CONTEXT_JSON}}": card_context_json,
        "{{USER_ANSWER}}": user_answer,
        "{{ITEMS_INSTRUCTION}}": items_instruction or "",
    }
    out = template
    for placeholder, value in _DEFAULT_REPLACEMENTS.items():
        out = out.replace(placeholder, value)
    for placeholder, value in kwargs_map.items():
        if value is not None:
            out = out.replace(placeholder, value if isinstance(value, str) else str(value))
        elif placeholder == "{{CONVERSATION_HISTORY}}" and placeholder in out:
            out = out.replace(placeholder, "(No messages yet)")
    return out
