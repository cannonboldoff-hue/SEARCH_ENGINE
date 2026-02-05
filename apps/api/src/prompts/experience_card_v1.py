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
  when selecting raw_text_span, without adding new information.
  (Example: "conquered the city" → "expanded presence across the city")

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

Hard rules:
- Set: parent_id = null, depth = 0, relation_type = null
- Treat each atom as an INDEPENDENT parent Experience Card unless
  explicit hierarchical dependency is stated in the text.
- Do NOT merge atoms at this stage.

Classification:
- Determine whether the atom primarily represents:
  (a) an Outcome (measurable result or achievement), OR
  (b) a Responsibility (ongoing duty or role).
- Headlines and summaries MUST reflect this classification.

Headline rules:
- Headline must describe the specific outcome or responsibility.
- Do NOT use generic employment headlines
  (e.g., "Worked at a company", "Job experience").

Language normalization:
- Rewrite metaphorical, exaggerated, or absolute language into
  professional, factual phrasing.
- Never preserve violent, military, or absolute metaphors.
  Examples:
  - "conquered a city" → "expanded operations across the city"
  - "handled everything" → "managed multiple responsibilities"

Extraction rules:
- Fill: intent, headline, summary, raw_text
- Extract where possible:
  - actions (canonical verb + verb_raw)
  - roles
  - topics
  - entities
  - time
  - location
  - outcomes or responsibilities
- Extract universal tooling ONLY if explicitly mentioned:
  - tools: software / equipment / system / platform / instrument / other
  - processes: repeatable workflows or methods
- NEVER guess tools or processes.
  If uncertain, place text in tooling.raw with low confidence.

Language:
- Detect raw_text language (e.g., en / hi / mr) if possible.
- If uncertain, set language=null and confidence=low.

Privacy:
- If health, legal, sexual, or private family data appears:
  - privacy.sensitive = true
  - default visibility = "profile_only"

Clarification:
- If ambiguity blocks correct indexing:
  - quality.needs_clarification = true
  - propose AT MOST ONE short clarifying_question.

Indexing:
- Create index.search_phrases (5–15 short, professional phrases).
- Remove low-signal topics (e.g., "company", "places").

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

Rules:
- Do NOT generate children if the parent Experience Card is already
  atomic and complete as an Outcome or Responsibility.
- Only generate children if they add meaningful, distinct information.

Grounding:
- Children MUST be directly grounded in the parent's raw_text or summary.
- Do NOT invent new facts.

Schema rules:
- Use the SAME schema.
- Set:
  - parent_id = {{PARENT_ID}}
  - depth = 1
  - relation_type MUST be valid and meaningful.

Preferred child intents:
- responsibility
- outcome
- skill_application
- method_used
- challenge
- decision
- learning
- artifact_created

Tooling:
- Extract tools and processes ONLY if explicitly stated.
- Do NOT guess tools or workflows.

Searchability:
- Keep children specific, factual, and professionally phrased.
- Avoid vague or low-signal topics.

Return ONLY a JSON array of child Experience Cards.

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
- Ensure full schema validity.
- Remove hallucinations or ungrounded claims.
- Normalize verbs while preserving verb_raw.
- Ensure relation_type is valid and meaningful for children.
- Remove literal interpretations of metaphorical language.
- Enforce professional, factual phrasing throughout.
- Eliminate low-signal or noisy topics
  (e.g., "company", "places", "conquest").

Privacy:
- If sensitive data exists, enforce conservative privacy defaults.

Consistency:
- Fix inconsistencies in time, location, outcomes, or confidence.
- Ensure Outcome vs Responsibility classification is correct.

Clarification:
- Allow AT MOST ONE clarification question total.
- Prefer assigning it to the parent.
- Remove duplicates from children.

Return ONLY valid JSON in this shape:
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
