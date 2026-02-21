"""
Prompts for search query parsing: cleanup → extract → validate.
Output is a single JSON stored in Search.filters (JSONB) for vector retrieval + structured filters + ranking.
"""

from src.prompts.experience_card_enums import INTENT_ENUM

PROMPT_SEARCH_CLEANUP = """
You are a search query cleanup engine.

Goal: Clean the user's search query for reliable structured extraction.

RULES:
1) Do NOT add facts or interpret beyond the text.
2) Keep names, companies, tools, numbers EXACTLY as written.
3) Fix typos/spacing. Preserve meaning.
4) Output ONLY cleaned text. No commentary. No JSON.

User query:
{{USER_TEXT}}
"""

def get_cleanup_prompt(user_text: str) -> str:
    return PROMPT_SEARCH_CLEANUP.replace("{{USER_TEXT}}", user_text)


# ---------------------------------------------------------------------------
# Single extraction prompt → JSON stored in Search.parsed_constraints_json
# Maps directly to DB columns: company_norm, team_norm, intent_primary, domain, etc. + person_profiles
# ---------------------------------------------------------------------------

PROMPT_SEARCH_SINGLE_EXTRACT = """You are a structured search-query parser for CONXA (intent-based people search).

Convert the user query into JSON constraints that map to our DB.

IMPORTANT:
- Return ONLY valid JSON.
- NEVER omit any key from the output schema (every key must be present; use null or [] when not applicable).
- Do NOT hallucinate; only extract what is explicitly present.
- Normalize company/team for exact match: lowercase + trim -> company_norm / team_norm.
- num_cards: MUST be an integer when the user asks for a specific number of results/cards; otherwise null.

Allowed values for intent_primary are:
{{INTENT_ENUM}}

OUTPUT SCHEMA (MUST match exactly):
{
  "query_original": "",
  "query_cleaned": "",
  "must": {
    "company_norm": [],
    "team_norm": [],
    "intent_primary": [],
    "domain": [],
    "sub_domain": [],
    "employment_type": [],
    "seniority_level": [],
    "location_text": null,
    "city": null,
    "country": null,
    "time_start": null,
    "time_end": null,
    "is_current": null,
    "open_to_work_only": null,
    "offer_salary_inr_per_year": null
  },
  "should": {
    "skills_or_tools": [],
    "keywords": [],
    "intent_secondary": []
  },
  "exclude": {
    "company_norm": [],
    "keywords": []
  },
  "search_phrases": [],
  "query_embedding_text": "",
  "confidence_score": 0.0,
  "num_cards": null
}

RULES:
1) num_cards (REQUIRED key; do not omit)
- If the user asks for a specific number of results/cards (e.g. "give me 2 cards", "show 5 results", "I need 3", "2 cards please"), set num_cards to that integer (1 to 24).
- If no number of results is requested, set num_cards to null.
- Always include the key "num_cards" in your JSON output.

2) MUST vs SHOULD
- MUST only if the query clearly requires it (e.g., "only", "must", exact city, exact company, salary, explicit open to work).
- Otherwise put it in SHOULD.

3) Salary
- If query contains "₹X/month", set offer_salary_inr_per_year = X*12
- If "₹X LPA" or "₹X/year", convert to per year
- If salary text is unclear, add it to should.keywords and leave offer_salary_inr_per_year null

4) Time
- If explicit years/dates exist, fill time_start/time_end as YYYY-MM-DD when possible (YYYY-01-01/ YYYY-12-31 ok).
- If relative ("last 2 years"), keep in should.keywords and leave dates null.

5) Location
- If city/country explicit, fill city/country and also location_text.
- Otherwise only location_text if present.

6) Query embedding text
Create query_embedding_text as a concise text blob for semantic search including:
must constraints + should terms + key nouns/verbs from query.
Do not add new facts.

7) search_phrases
Generate 5–15 concise phrases combining the key constraints.

INPUT:
query_original:
{{QUERY_ORIGINAL}}

query_cleaned:
{{QUERY_CLEANED}}
"""


def get_single_extract_prompt(query_original: str, query_cleaned: str) -> str:
    return (
        PROMPT_SEARCH_SINGLE_EXTRACT.replace("{{INTENT_ENUM}}", INTENT_ENUM)
        .replace("{{QUERY_ORIGINAL}}", query_original or "")
        .replace("{{QUERY_CLEANED}}", query_cleaned or query_original or "")
    )
