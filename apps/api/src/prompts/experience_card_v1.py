"""
Experience Card v1 pipeline prompts.

Designed to take messy, informal, noisy, or incomplete human text and produce:
  atoms → parent card → child cards → validated JSON.

The input may contain slang, abbreviations, typos, run-on sentences, mixed
languages, exaggeration, or metaphorical language. Each stage normalizes
progressively while preserving the user's original intent.

Schemas: domain_schemas.ExperienceCardParentV1Schema (parent) and
domain_schemas.ExperienceCardChildV1Schema (children). Do NOT assume
the user is in tech — experiences span every domain.
"""

# ── Shared reference: allowed enum values (embedded in prompts for LLM context) ──
# Parent cards: full Intent. Children: ChildIntent only.
_INTENT_ENUM = (
    "education, work, project, achievement, certification, responsibility, "
    "skill_application, method_used, artifact_created, challenge, decision, "
    "learning, life_event, relocation, volunteering, community, finance, other, mixed"
)
_CHILD_INTENT_ENUM = (
    "responsibility, outcome, skill_application, method_used, challenge, "
    "decision, learning, artifact_created"
)
_CHILD_RELATION_ENUM = (
    "component_of, skill_applied, method_used, tool_used, artifact_created, "
    "challenge_faced, decision_made, outcome_detail, learning_from, example_of"
)
_ENTITY_TYPES = (
    "person, organization, company, school, team, community, place, event, "
    "program, domain, industry, product, service, artifact, document, "
    "portfolio_item, credential, award, tool, equipment, system, platform, "
    "instrument, method, process"
)
_TOOL_TYPES = "software, equipment, system, platform, instrument, other"

# -----------------------------------------------------------------------------
# 2.0  Rewrite (messy blob → clean English)
# -----------------------------------------------------------------------------
PROMPT_REWRITE = """You are a careful rewrite engine.

Goal: Rewrite the user's message into clear, grammatically correct English so that another model can extract structured information from it more reliably.

STRICT RULES:
1) Do NOT add new facts. Do NOT guess missing details. Do NOT change meaning.
2) Keep all proper nouns, names, company names, product names, and numbers EXACTLY as written.
3) Preserve ordering and intent. If the user lists items, keep them as a list.
4) Expand common abbreviations only when unambiguous (e.g., "mgr" → "manager").
5) Remove filler, repetition, and obvious typos, but keep all substantive content.
6) Output ONLY the rewritten text. No markdown fences, no commentary, no JSON.

User message:
{{USER_TEXT}}
"""

# -----------------------------------------------------------------------------
# 2.1  Atomizer  (messy text → atomic experiences)
# -----------------------------------------------------------------------------
PROMPT_ATOMIZER = """You are an information-extraction system that splits text into discrete atomic experiences.

─── CONTEXT ───
The input is text (possibly already normalized). Your job: identify every distinct experience described and emit one atom per experience.

─── RULES ───
1. Output ONLY a valid JSON array — no markdown fences, no commentary.
2. Each atom object must contain exactly these keys:
     atom_id        – sequential id ("a1", "a2", …)
     raw_text_span  – the EXACT substring(s) from the input that back this atom
                      (quote verbatim; may be non-contiguous — join with " … ")
     suggested_intent – one of: """ + _INTENT_ENUM + """
     why            – one-sentence justification for why this is a distinct atom

3. Splitting rules:
   • One atom = one experience (a role, project, achievement, event, learning, etc.).
   • If a sentence packs two experiences ("I managed QA and launched the mobile app"),
     split into two atoms.
   • Chronological or causal groups sharing the SAME scope (same role + same time)
     may stay as one atom if inseparable.

4. Filtering:
   • Do NOT create atoms for:
     – generic filler ("I worked at X" with no outcome or responsibility)
     – pure opinions or feelings with no concrete experience behind them
     – greetings, instructions to the AI, or meta-commentary
   • DO create atoms for partial or vague experiences — mark suggested_intent = "other"
     and note uncertainty in 'why'. The validator will handle them later.

─── INPUT ───
User message:
{{USER_TEXT}}

─── OUTPUT SHAPE ───
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
# 2.2  Parent + Children  (one atom → parent + 0–10 children)
# -----------------------------------------------------------------------------
PROMPT_PARENT_AND_CHILDREN = """You are a structured-data extraction system.
Given ONE atomic experience (which may be messy, informal, or incomplete),
produce exactly ONE parent Experience Card and 0–10 child Experience Cards.

═══ HARD GATES (STRICT — violating any of these is a critical error) ═══
• Do NOT infer job roles, skills, or duties from a company's industry.
• Do NOT invent responsibilities the user did not explicitly state.
• Do NOT create cards for generic employment context with no outcome or duty.
• If the atom is too vague for classification, output a minimal parent with
  intent="other" and an EMPTY children array.

═══ INPUT NORMALIZATION (apply before extraction) ═══
The atom text may contain typos, slang, abbreviations, metaphors, or grammar
errors. You MUST:
1. Fix typos and expand abbreviations when unambiguous.
2. Convert colloquial/slang phrasing into professional, factual language.
3. Rewrite exaggerated or metaphorical claims into measured statements.
4. Preserve all proper nouns, numbers, dates, and named tools exactly.
5. Record the original phrasing in raw_text; put the cleaned version in summary.

═══ PARENT CARD RULES ═══
• parent_id = null, depth = 0, relation_type = null.
• intent: pick the BEST match from the allowed values:
    """ + _INTENT_ENUM + """
• headline: a concise (<120 char) descriptor of the outcome or responsibility.
    NEVER use filler headlines ("Worked at a company", "Employment experience").
    Good: "Reduced API latency by 40% through caching layer redesign"
    Good: "Managed a 12-person kitchen team at downtown restaurant"
• summary: 1–3 sentence professional rewrite capturing the full atom meaning.
• raw_text: the ORIGINAL atom text, verbatim (before your normalization).
• language: { "raw_text": detected language code or null, "confidence": "high"|"medium"|"low" }
• time: extract ONLY what is explicitly stated.
    { "start": "YYYY-MM" or null, "end": "YYYY-MM" or null,
      "ongoing": bool or null, "text": free-text timespan or null,
      "confidence": "high"|"medium"|"low" }
    – If the user says "last year" or "a few months", put it in "text" and set confidence="low".
    – Do NOT guess specific dates.
• location: extract ONLY what is explicitly stated.
    { "city": str|null, "region": str|null, "country": str|null,
      "text": free-text or null, "confidence": "high"|"medium"|"low" }
• roles: list of { "label": str, "seniority": str|null, "confidence": "high"|"medium"|"low" }
    – Extract ONLY if the user names a role. Do NOT infer from context.
• actions: list of { "verb": normalized_verb, "verb_raw": original_verb|null, "confidence": ... }
    – Normalize verbs to base professional form ("managed", "built", "designed", …).
    – Keep verb_raw as the user's original word ("ran" → verb="managed", verb_raw="ran").
• topics: list of { "label": normalized_topic, "raw": original_phrasing|null, "confidence": ... }
    – Normalize topic labels to standard professional terms.
    – Eliminate low-signal or overly abstract topics ("stuff", "things", "work").
• entities: list of { "type": one of (""" + _ENTITY_TYPES + """), "name": str, "entity_id": null, "confidence": ... }
    – Extract companies, schools, products, named projects, etc.
• tooling: { "tools": [{"name":str,"type": one of (""" + _TOOL_TYPES + """),"confidence":...}],
             "processes": [{"name":str,"confidence":...}], "raw": original text or null }
    – Extract tools/processes ONLY if the user explicitly names them. NEVER guess.
• outcomes: list of { "type": str, "label": str, "value_text": str|null,
                       "metric": {"name":str|null,"value":float|null,"unit":str|null},
                       "confidence": ... }
    – Extract measurable results only when stated.
• evidence: [] (empty unless the user provides URLs or file references).
• privacy: { "visibility": "searchable", "sensitive": false }
    – Default. If the text mentions anything personal/medical/legal, set sensitive=true
      and visibility="private".
• quality: { "overall_confidence": "high"|"medium"|"low",
             "claim_state": "self_claim",
             "needs_clarification": bool,
             "clarifying_question": str|null }
    – Set needs_clarification=true if critical info is missing (e.g., no clear outcome
      AND no clear responsibility). Provide ONE concise clarifying question.
• index: { "search_phrases": [...], "embedding_ref": null }
    – Generate 5–15 concise, diverse search phrases someone might use to find this card.
    – Include synonyms, related industry terms, and both specific and general phrases.

═══ CHILDREN CARD RULES (ExperienceCardChildV1Schema) ═══
• If the parent fully captures a single Outcome or single Responsibility,
  return "children": [] — do NOT pad with filler children.
• Children MUST be grounded in the parent's raw_text. Do NOT invent facts.
• Each child MUST conform to ExperienceCardChildV1Schema:
  – parent_id = "parent", depth = 1 (literal).
  – relation_type: REQUIRED, one of """ + _CHILD_RELATION_ENUM + """
  – intent: REQUIRED, one of """ + _CHILD_INTENT_ENUM + """ (no education, work, project, etc.)
• Each child must add NEW, distinct, searchable value. No restating the parent.
• Children inherit the parent's person_id, created_by, and privacy settings.
• Same content fields as parent (headline, summary, raw_text, time, location, topics, …).

═══ OUTPUT FORMAT ═══
Return ONLY valid JSON — no markdown fences, no commentary.
• "parent" MUST follow ExperienceCardParentV1Schema:
  parent_id=null, depth=0, relation_type=null, intent=any of """ + _INTENT_ENUM + """
• Each item in "children" MUST follow ExperienceCardChildV1Schema:
  parent_id="parent", depth=1, relation_type=one of """ + _CHILD_RELATION_ENUM + """,
  intent=one of """ + _CHILD_INTENT_ENUM + """ (child intents only)
{
  "parent": { <ExperienceCardParentV1Schema> },
  "children": [ { <ExperienceCardChildV1Schema> }, ... ]
}

═══ INPUT ═══
Atom:
{{ATOM_TEXT}}

Metadata:
person_id = {{PERSON_ID}}
created_by = {{PERSON_ID}}
"""

# -----------------------------------------------------------------------------
# 2.4  Validator / Critic  (parent+children → corrected final)
# -----------------------------------------------------------------------------
PROMPT_VALIDATOR = """You are a strict validator and editor for Experience Card v1 JSON.

─── MISSION ───
Review the parent + children cards produced by the extraction step.
Fix schema errors, remove hallucinations, tighten language, and ensure the
output is backend-ready. Preserve the user's original intent at all costs.

─── SCHEMA VALIDITY ───
• Parent MUST follow ExperienceCardParentV1Schema:
  parent_id=null, depth=0, relation_type=null, intent=one of """ + _INTENT_ENUM + """
• Each child MUST follow ExperienceCardChildV1Schema:
  parent_id=(parent's id), depth=1, relation_type=one of """ + _CHILD_RELATION_ENUM + """,
  intent=one of """ + _CHILD_INTENT_ENUM + """ (child intents only)

Shared content fields (both parent and children):
  id (str), person_id (str), created_by (str), version (1),
  headline (str, ≤120 chars), summary (str), raw_text (str),
  language ({raw_text, confidence}),
  time ({start, end, ongoing, text, confidence}),
  location ({city, region, country, text, confidence}),
  roles ([{label, seniority, confidence}]),
  actions ([{verb, verb_raw, confidence}]),
  topics ([{label, raw, confidence}]),
  entities ([{type, name, entity_id, confidence}]),
  tooling ({tools:[{name,type,confidence}], processes:[{name,confidence}], raw}),
  outcomes ([{type, label, value_text, metric:{name,value,unit}, confidence}]),
  evidence ([{type, url, note, visibility}]),
  privacy ({visibility, sensitive}),
  quality ({overall_confidence, claim_state, needs_clarification, clarifying_question}),
  index ({search_phrases, embedding_ref}),
  created_at (ISO datetime str), updated_at (ISO datetime str)

If any field is missing, add it with its correct default/null value.
If any field has the wrong type, coerce it. Ensure children use ChildIntent and relation_type.

─── HALLUCINATION REMOVAL ───
• Remove any role, skill, tool, or responsibility NOT grounded in raw_text.
• If a headline or summary contains information not present in raw_text,
  rewrite it using ONLY what raw_text supports.
• Remove children that are pure restatements of the parent or add no new facts.

─── NORMALIZATION ───
• Verbs: normalize to professional base form; keep verb_raw intact.
• Topics: merge near-duplicates (e.g., "ML" and "machine learning" → keep one).
    Remove vague topics ("stuff", "things", "general work").
• Entities: ensure entity type is from the allowed taxonomy:
    """ + _ENTITY_TYPES + """
• Outcomes: if a metric is claimed but no number is given, set value=null, keep label.
• Headline: must be ≤120 characters. Trim or rephrase if longer.
• Summary: must be factual, professional. Rewrite any remaining slang or metaphor.

─── CLASSIFICATION CHECK ───
• Parent: intent is any Intent (education, work, project, achievement, …).
• Children: intent MUST be one of """ + _CHILD_INTENT_ENUM + """ only.
    – Measurable result with numbers → "outcome"
    – Ongoing duty described → "responsibility"
    – Skill demonstrated → "skill_application"
    – Use "other" only on the parent for genuinely unclassifiable content; children use child intents.
• relation_type for each child must match what the child actually describes (""" + _CHILD_RELATION_ENUM + """).

─── CHILDREN PRUNING ───
• Remove children that:
    – Restate the parent headline or summary.
    – Contain no concrete, searchable information.
    – Were hallucinated (not grounded in raw_text).
• If ALL children fail these checks, return "children": [].

─── PRIVACY ───
• Default: visibility="searchable", sensitive=false.
• If raw_text mentions medical conditions, legal issues, salary figures,
  or personal identifiers → set sensitive=true, visibility="private".

─── CONSISTENCY ───
• Dates in time.start / time.end must be "YYYY-MM" or "YYYY-MM-DD" format, or null.
• Location fields must be properly split (city vs region vs country).
• Confidence levels must be "high", "medium", or "low" — no other values.
• claim_state must be "self_claim" (default for user-submitted text).

─── SEARCH INDEX ───
• index.search_phrases must contain 5–15 diverse, concise phrases.
• Include: role titles, skills, tools, company names, outcome keywords,
  industry terms, and reasonable synonyms.
• Remove any phrase that is too generic to be useful in search.

─── CLARIFICATION ───
• Allow AT MOST ONE clarifying question across the entire family.
• Prefer setting it on the parent card.
• Only ask if critical information is truly missing AND would materially
  change the card's usefulness.

─── OUTPUT ───
Return ONLY valid JSON — no markdown fences, no commentary.
{
  "parent": { <corrected parent card> },
  "children": [ <corrected child cards or empty array> ]
}

─── INPUT ───
{{PARENT_AND_CHILDREN_JSON}}
"""


def fill_prompt(
    template: str,
    *,
    user_text: str | None = None,
    atom_text: str | None = None,
    person_id: str | None = None,
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
    if parent_and_children_json is not None:
        out = out.replace("{{PARENT_AND_CHILDREN_JSON}}", parent_and_children_json)
    return out
