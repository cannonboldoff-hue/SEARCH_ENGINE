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

PROMPT_EXTRACT_ALL_CARDS = f"""You are a structured data extraction system.

Your job is to extract ALL Experience Card parents and their dimension-based
children from cleaned user text.

========================
HARD GATES (CRITICAL)
========================
* Do NOT infer roles, skills, or responsibilities from industry or company.
* Do NOT invent facts.
* Do NOT split one experience into multiple parents unless clearly distinct.
* If content is vague, create a minimal parent with intent="other" and NO children. For such minimal parents, headline MUST be a short phrase derived from the raw text (e.g. first few words or "General experience"), never "Unspecified experience".

========================
PARENT CARD RULES
========================
* One parent = one dominant experience or intent block.
* intent MUST be one of:
  {INTENT_ENUM}
* headline: <=120 chars, outcome- or responsibility-focused. Never use "Unspecified experience"; use a brief phrase from the text or "General experience" for vague content.
* summary: 1–3 factual sentences.
* raw_text: verbatim supporting text.
* time/location: extract ONLY what is explicitly stated.
* index.search_phrases: 5–15 concise, diverse phrases.

========================
CHILD CARD RULES (VERY IMPORTANT)
========================
* You may create AT MOST 10 children per parent.
* Each child represents ONE dimension only.
* Allowed child_type values:
  {ALLOWED_CHILD_TYPES_STR}

* NEVER create multiple children of the same child_type.
* ALL items of the same type MUST be grouped inside one child.

CORRECT:
  skills → Python, statistics, modeling
WRONG:
  skill(Python), skill(statistics), skill(modeling)

* Each child MUST add searchable value beyond the parent.
* Child intent MUST be one of:
  {CHILD_INTENT_ENUM}
* relation_type (how child relates to parent) MUST be one of:
  {CHILD_RELATION_TYPE_ENUM}

========================
CHILD STORAGE MODEL
========================
Each child MUST contain:
- child_type (one of allowed types above)
- label (human readable, <=255 chars)
- value (JSON dimension container):
    - headline
    - summary
    - raw_text
    - time
    - location
    - roles
    - actions
    - topics
    - entities
    - tooling
    - outcomes
    - evidence
    - depth = 1
- search_phrases (5–15 phrases UNIQUE to this dimension)
- search_document (auto-generated text blob)

========================
ANTI-HALLUCINATION
========================
* Every child fact MUST be grounded in raw_text.
* Do NOT restate the parent in children.
* If no valid child dimensions exist, return children=[].

========================
OUTPUT FORMAT
========================
Return ONLY valid JSON.

{{
  "parents": [
    {{
      "parent": {{ <ExperienceCardParentV1Schema> }},
      "children": [ {{ <ExperienceCardChildV1Schema> }} ]
    }}
  ]
}}

========================
INPUT
========================
Cleaned text:
{{USER_TEXT}}

Metadata:
person_id = {{PERSON_ID}}
created_by = {{PERSON_ID}}
"""

# -----------------------------------------------------------------------------
# 4. Validate + Normalize (FINAL GATE)
# -----------------------------------------------------------------------------

PROMPT_VALIDATE_ALL_CARDS = f"""You are a strict validator for Experience Card v1 JSON.

MISSION:
Validate, normalize, prune, and finalize parents + children.

========================
SCHEMA ENFORCEMENT
========================
* Parent intent MUST be one of:
  {INTENT_ENUM}
* Child intent MUST be one of:
  {CHILD_INTENT_ENUM}
* Child relation_type MUST be one of:
  {CHILD_RELATION_TYPE_ENUM}
* child_type MUST be one of:
  {ALLOWED_CHILD_TYPES_STR}
* Max 10 children per parent.

========================
HALLUCINATION REMOVAL
========================
* Remove any skill, tool, metric, role, or claim not grounded in raw_text.
* Rewrite headlines/summaries to match raw_text exactly.
* Remove children that restate the parent or add no new value.

========================
NORMALIZATION
========================
* Merge duplicate topics and tools.
* Normalize verbs; keep verb_raw.
* Enforce confidence values: high | medium | low.
* Enforce date formats (YYYY-MM or YYYY-MM-DD).

========================
SEARCH QUALITY
========================
* Parent search_phrases: role + domain + outcome.
* Child search_phrases: ONLY dimension-specific terms.
* Remove generic or duplicate phrases.

========================
PRIVACY
========================
Default:
  visibility="searchable", sensitive=false

If medical, legal, salary, or personal identifiers appear:
  sensitive=true, visibility="private"

========================
OUTPUT
========================
Return ONLY valid JSON.

{{
  "raw_text_original": "...",
  "raw_text_cleaned": "...",
  "parents": [
    {{
      "parent": {{ <validated parent> }},
      "children": [ <validated children or []> ]
    }}
  ]
}}

INPUT:
{{PARENT_AND_CHILDREN_JSON}}
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
) -> str:
    out = template
    if user_text is not None:
        out = out.replace("{{USER_TEXT}}", user_text)
    if person_id is not None:
        out = out.replace("{{PERSON_ID}}", person_id)
    if parent_and_children_json is not None:
        out = out.replace("{{PARENT_AND_CHILDREN_JSON}}", parent_and_children_json)
    return out
