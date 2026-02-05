"""
Experience Card v1 pipeline prompts.

Designed to take messy human text and produce: atoms → parent card → child cards → validated JSON.
Schema aligns with domain_schemas.ExperienceCardV1Schema. Do not assume the user is in tech.
"""

# -----------------------------------------------------------------------------
# 2.1 Atomizer (messy text → atomic experiences)
# -----------------------------------------------------------------------------
PROMPT_ATOMIZER = """You are an information extraction system.

Task:
Split the user's messy message into atomic experiences (one experience per atom).

Rules:
- Output ONLY a valid JSON array.
- Each item must include: atom_id, raw_text_span, suggested_intent, why.
- Do not assume the user is in tech.
- Do not invent facts.
- If multiple experiences appear in one message, split them.
- Normalize exaggerated or metaphorical phrases into factual descriptions
  without adding new information.
  Example:
  - "conquered the city" → "expanded presence across the city"

IMPORTANT:
- Do NOT create atoms for generic employment context.
- Only extract atoms that describe a concrete outcome or responsibility.

User message:
{{USER_TEXT}}

Expected output shape:
[
  {
    "atom_id": "a1",
    "raw_text_span": "...",
    "suggested_intent": "work",
    "why": "Describes a specific outcome or responsibility"
  }
]
"""

# -----------------------------------------------------------------------------
# 2.2 Parent extractor (atom → Experience Card v1)
# -----------------------------------------------------------------------------
PROMPT_PARENT_EXTRACTOR = """Convert ONE atom into a universal Experience Card v1.

HARD GATES (STRICT):
- Do NOT infer job roles, skills, or duties based on the company’s industry.
- Do NOT invent responsibilities the user did not explicitly state.
- Do NOT create cards for generic employment context.
- If the atom does NOT clearly represent:
  (a) a measurable Outcome, or
  (b) a concrete Responsibility,
  then DO NOT create an Experience Card.

Schema rules:
- Set: parent_id = null, depth = 0, relation_type = null
- Treat each atom as an INDEPENDENT parent Experience Card.
- Never merge atoms at this stage.

Classification (MANDATORY):
- Classify the atom as either:
  - Outcome (measurable result, growth, achievement), OR
  - Responsibility (ongoing duty, ownership, accountability).
- Headlines and summaries MUST reflect this classification.

Headline rules:
- Headline must describe the outcome or responsibility.
- NEVER use generic headlines such as:
  - "Worked at a company"
  - "Employment experience"
  - "Provided services"

Language normalization:
- Rewrite exaggerated or metaphorical language into factual,
  professional phrasing.
- Never preserve violent, military, or absolute metaphors.
  Examples:
  - "conquered a city" → "expanded operations across the city"
  - "handled everything" → "managed multiple responsibilities"

Extraction rules:
- Fill: intent, headline, summary, raw_text
- Extract ONLY what is explicitly stated:
  - actions (canonical verb + verb_raw)
  - responsibilities OR outcomes
  - roles (ONLY if explicitly mentioned)
  - time
  - location
- Extract topics that are high-signal and professional.
- Remove low-signal topics (e.g., "company", "places").

Tooling:
- Extract tools or processes ONLY if explicitly named.
- NEVER guess tools, software, or workflows.
- If unclear, leave tooling empty.

Language:
- Detect raw_text language if possible.
- If uncertain, set language=null with low confidence.

Privacy:
- If sensitive personal data appears:
  - privacy.sensitive = true
  - visibility = "profile_only"

Clarification:
- If ambiguity blocks correct classification:
  - quality.needs_clarification = true
  - ask AT MOST ONE short clarifying_question.

Indexing:
- Create 5–15 concise, searchable index.search_phrases.

Return ONLY valid JSON matching ExperienceCardV1Schema.

Atom:
{{ATOM_TEXT}}

Metadata:
person_id = {{PERSON_ID}}
created_by = {{PERSON_ID}}
"""

# -----------------------------------------------------------------------------
# 2.3 Child generator (parent → 0–10 child cards)
# -----------------------------------------------------------------------------
PROMPT_CHILD_GENERATOR = """Generate 0–10 child Experience Cards under this parent.

STRICT RULE:
- If the parent Experience Card fully captures a single
  Outcome or Responsibility, RETURN AN EMPTY ARRAY.

Grounding:
- Children MUST be directly grounded in the parent's raw_text or summary.
- Do NOT invent facts or infer duties.

Schema rules:
- Use the SAME schema.
- Set:
  - parent_id = {{PARENT_ID}}
  - depth = 1
  - relation_type MUST be valid and meaningful.

Allowed child intents:
- responsibility
- outcome
- skill_application
- method_used
- challenge
- decision
- learning
- artifact_created

Tooling:
- Extract tools or processes ONLY if explicitly mentioned.
- NEVER guess.

Searchability:
- Children must add NEW, distinct, searchable value.
- Avoid generic or restated content.

Return ONLY a JSON array.

Parent card JSON:
{{PARENT_CARD_JSON}}
"""

# -----------------------------------------------------------------------------
# 2.4 Validator / Critic (parent+children → corrected final)
# -----------------------------------------------------------------------------
PROMPT_VALIDATOR = """You are a validator for universal Experience Card v1.

Input:
- One parent Experience Card
- Its child Experience Cards (if any)

Goals:
- Ensure strict schema validity.
- Remove hallucinated roles, skills, or duties.
- Remove employment-context cards with no outcome or responsibility.
- Normalize verbs while preserving verb_raw.
- Ensure Outcome vs Responsibility classification is correct.
- Rewrite or remove any remaining metaphorical language.
- Eliminate low-signal or abstract topics.

Children rules:
- If children add no new information, REMOVE ALL children.

Privacy:
- Enforce conservative defaults for sensitive data.

Consistency:
- Fix inconsistencies in time, location, numbers, or confidence.

Clarification:
- Allow AT MOST ONE clarification question total.
- Prefer parent-level clarification.

Return ONLY valid JSON in this structure:
{
  "parent": { ... },
  "children": [ ... ]
}

Input JSON:
{{PARENT_AND_CHILDREN_JSON}}
"""


def fill_prompt(
    template: str,
    *,
    user_text: str | None = None,
    atom_text: str | None = None,
    person_id: str | None = None,
    parent_id: str | None = None,
    parent_card_json: str | None = None,
    parent_and_children_json: str | None = None,
) -> str:
    """Replace placeholders in a prompt template. Keys match {{PLACEHOLDER}} names (lowercase with underscores)."""
    out = template
    if user_text is not None:
        out = out.replace("{{USER_TEXT}}", user_text)
    if atom_text is not None:
        out = out.replace("{{ATOM_TEXT}}", atom_text)
    if person_id is not None:
        out = out.replace("{{PERSON_ID}}", person_id)
    if parent_id is not None:
        out = out.replace("{{PARENT_ID}}", parent_id)
    if parent_card_json is not None:
        out = out.replace("{{PARENT_CARD_JSON}}", parent_card_json)
    if parent_and_children_json is not None:
        out = out.replace("{{PARENT_AND_CHILDREN_JSON}}", parent_and_children_json)
    return out
