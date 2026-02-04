"""
Experience Card pipeline prompts.

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
- Output ONLY valid JSON array.
- Each item must include: atom_id, raw_text_span, suggested_intent, why.
- Do not assume the user is in tech.
- Do not invent facts.
- If multiple experiences appear in one message, split them.

User message:
{{USER_TEXT}}


Expected output shape

[
  {"atom_id":"a1","raw_text_span":"...","suggested_intent":"work","why":"Describes a role/responsibility"}
]"""

# -----------------------------------------------------------------------------
# 2.2 Parent extractor (atom → Experience Card)
# -----------------------------------------------------------------------------
PROMPT_PARENT_EXTRACTOR = """Convert ONE atom into a universal Experience Card.

Hard rules:
- Set: parent_id=null, depth=0, relation_type=null
- Fill: intent, headline, summary, raw_text
- Extract where possible: actions (canonical verb + verb_raw), roles, topics, entities, time, location, outcomes
- Extract universal tooling:
  - tools: software/equipment/system/platform/instrument/other
  - processes: repeatable workflows/methods
  - NEVER guess tools/processes not explicitly mentioned; if uncertain, put in tooling.raw and set low confidence
- Language: detect raw_text language (e.g., en/hi/mr) if possible; else null with low confidence
- Privacy:
  - If health/legal/sexual/private family details appear, set privacy.sensitive=true and default visibility="profile_only" unless user explicitly wants searchable
- Clarification:
  - If ambiguity blocks correct indexing, set quality.needs_clarification=true and propose AT MOST ONE short clarifying_question
- Create index.search_phrases (5–15 short phrases)

Return ONLY JSON matching the schema.

Atom:
{{ATOM_TEXT}}

Metadata:
person_id={{PERSON_ID}}
created_by={{PERSON_ID}}"""

# -----------------------------------------------------------------------------
# 2.3 Child generator (parent → 0–10 child cards)
# -----------------------------------------------------------------------------
PROMPT_CHILD_GENERATOR = """Generate 0–10 child Experience Cards under this parent.

Rules:
- Children must be grounded in the parent's raw_text or summary.
- Use the SAME schema, but:
  - parent_id = {{PARENT_ID}}
  - depth = 1
  - relation_type must be one of the allowed values
- Prefer child intents:
  skill_application, method_used, artifact_created, challenge, decision, learning, responsibility
- Extract universal tooling for children too (tools + processes). Do not guess.
- Keep children specific and searchable.

Return ONLY a JSON array of child cards.

Parent card JSON:
{{PARENT_CARD_JSON}}"""

# -----------------------------------------------------------------------------
# 2.4 Validator / Critic (parent+children → corrected final)
# -----------------------------------------------------------------------------
PROMPT_VALIDATOR = """You are a validator for universal Experience Card.

Input: one parent card + its child cards.

Goals:
- Ensure schema validity
- Remove hallucinations (anything not grounded in raw_text/summary)
- Normalize verbs (keep verb_raw)
- Ensure relation_type is valid for children
- Make privacy conservative if sensitive
- Fix obvious inconsistencies (time/location/confidence)
- Decide at most ONE clarification question total (prefer parent; clear it from children if duplicated)

Return ONLY JSON:
{ "parent": { ... }, "children": [ ... ] }

Input JSON:
{{PARENT_AND_CHILDREN_JSON}}"""


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
