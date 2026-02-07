"""
Experience Card pipeline prompts.

Designed to take messy, informal, noisy, or incomplete human text and produce:
  rewrite -> cleanup -> extract-all (parents+children) -> validate-all.

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
# 2. Extract ALL parents + children (SINGLE PASS)
# -----------------------------------------------------------------------------

PROMPT_EXTRACT_ALL_CARDS = """You are a structured data extraction system.

Extract ALL ExperienceCard parents and their child dimension cards from the FULL cleaned text in ONE pass.

========================
NON-NEGOTIABLE OUTPUT RULE
========================
- Return ONLY valid JSON.
- NEVER omit keys defined below.
- If a field is missing from text, return null (or [] for arrays).
- Do NOT invent facts.

========================
PARENT SPLITTING (CRITICAL)
========================
Create MULTIPLE parents when the text contains multiple distinct experience blocks.
Strong split signals:
- multiple products/apps/projects (e.g., "first app", "second app", "third app")
- "then", "after that", "also", "another"
- two clearly different domains (e.g., quant research + product engineering)
- different time ranges or different employers

Rule: One parent = one dominant intent block. Do NOT merge unrelated blocks.

========================
PARENT OBJECT (matches ExperienceCard table + embedding needs)
========================
Each parent MUST include ALL keys:

{
  "title": null,
  "normalized_role": null,
  "domain": null,
  "sub_domain": null,
  "company_name": null,
  "company_type": null,
  "employment_type": null,

  "start_date": null,
  "end_date": null,
  "is_current": null,

  "location": null,
  "time_text": null,
  "city": null,
  "country": null,

  "seniority_level": null,

  "summary": "",
  "raw_text": "",

  "intent_primary": null,
  "intent_secondary": [],

  "confidence_score": 0.0,
  "visibility": true,

  "search_phrases": [],
  "search_document": ""
}

- intent_primary MUST be one of: {{INTENT_ENUM}}
- search_phrases: 5–15 concise, diverse phrases (role/domain/outcome/company/tools if present)
- search_document: a single text blob for embedding that includes ALL present fields:
  title + summary + role + company + time_text + dates + location + city/country +
  key tools/skills/metrics mentioned in this parent + search_phrases.

raw_text must be a verbatim supporting excerpt from CLEANED text for THIS parent only.

========================
CHILD OBJECT (matches ExperienceCardChild table)
========================
IMPORTANT: Your DB enforces UNIQUE child_type per parent.
So:
- You MUST NOT output multiple children with the same child_type.
- Instead, group all items for that type into ONE child.value container.

Allowed child_type values:
{{ALLOWED_CHILD_TYPES}}

Each child MUST include ALL keys:

{
  "child_type": "",
  "label": null,

  "value": {
    "headline": "",
    "summary": "",
    "raw_text": "",

    "time": { "start": null, "end": null, "ongoing": null, "text": null, "confidence": "low" },
    "location": { "city": null, "region": null, "country": null, "text": null, "confidence": "low" },

    "roles": [],
    "actions": [],
    "topics": [],
    "entities": [],
    "tooling": { "tools": [], "processes": [], "raw": null },
    "outcomes": [],
    "evidence": [],

    "privacy": { "visibility": "searchable", "sensitive": false },
    "quality": { "overall_confidence": "low", "claim_state": "self_claim", "needs_clarification": false, "clarifying_question": null },
    "index": { "search_phrases": [], "embedding_ref": null },

    "depth": 1,
    "parent_id": "__PARENT_INDEX__",     // temporary marker; validator will keep logical link
    "relation_type": null,
    "intent": null
  },

  "confidence_score": 0.0,
  "search_phrases": [],
  "search_document": ""
}

- value.intent MUST be one of: {{CHILD_INTENT_ENUM}} (or null if truly unclear)
- value.relation_type MUST be one of: {{CHILD_RELATION_TYPE_ENUM}} (or null if unclear)
- search_phrases: 5–15 phrases UNIQUE to this dimension
- search_document: include child_type + label + ALL items inside value + parent context (company/role/time/location)

Child.value should store grouped items like:
- skills: put skill names into value.topics as TopicItem(label=skill, confidence="medium"/"high")
- tools: put tools into value.tooling.tools
- metrics: put measurable results into value.outcomes (include metric if possible)
- achievements/responsibilities: put actions/outcomes
- collaborations/exposure: put entities (person/team/org) + topics

DO NOT create children that merely restate the parent.

========================
OUTPUT FORMAT
========================
{
  "parents": [
    {
      "parent": { ... },
      "children": [ ... ]
    }
  ]
}

INPUT:
Cleaned text:
{{USER_TEXT}}

Metadata:
person_id = {{PERSON_ID}}
created_by = {{PERSON_ID}}
"""

# -----------------------------------------------------------------------------
# 4. Validate + Normalize (FINAL GATE)
# -----------------------------------------------------------------------------

PROMPT_VALIDATE_ALL_CARDS = """You are a strict validator for our Experience Card output JSON.

MISSION:
Validate, normalize, de-duplicate, and finalize parents + children.

========================
INPUTS
========================
raw_text_original:
{{RAW_TEXT_ORIGINAL}}

raw_text_cleaned:
{{RAW_TEXT_CLEANED}}

extracted_json:
{{PARENT_AND_CHILDREN_JSON}}

========================
HALLUCINATION REMOVAL
========================
- Remove any claim not grounded in raw_text_cleaned.
- Tighten summaries to only what the text says.
- raw_text excerpts must be copied from raw_text_cleaned (not invented).

========================
SCHEMA ENFORCEMENT
========================
- NEVER omit required keys; fill missing with null/[].
- intent_primary must be one of: {{INTENT_ENUM}} (or "other" if unclear).
- child_type must be one of: {{ALLOWED_CHILD_TYPES}}
- For each parent: enforce UNIQUE child_type (merge if duplicates appear).
- Enforce confidence_score is a float in [0.0, 1.0].
- Enforce value.quality.overall_confidence is one of: high|medium|low.
- Enforce dates format: YYYY-MM-DD when possible; else keep in time_text or value.time.text.

========================
PARENT SPLIT CHECK (IMPORTANT)
========================
If the cleaned text clearly contains multiple projects/apps/blocks and extracted_json has only 1 parent,
split into multiple parents and reassign children accordingly.

========================
CHILD QUALITY
========================
- Remove children that add no new info vs parent.
- Merge duplicate items inside a child (e.g., repeated skills/tools).
- Ensure child.search_phrases are dimension-specific (no generic phrases).

========================
SEARCH DOCUMENTS
========================
- Ensure every parent.search_document exists and contains all present fields.
- Ensure every child.search_document exists and includes parent context.

========================
OUTPUT (JSON only)
========================
{
  "raw_text_original": "...",
  "raw_text_cleaned": "...",
  "parents": [
    {
      "parent": { ...validated parent... },
      "children": [ ...validated children... ]
    }
  ]
}
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

    return out
