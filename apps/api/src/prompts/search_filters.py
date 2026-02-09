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

PROMPT_SEARCH_EXTRACT_FILTERS = """
You are a structured search-query parser for CONXA (intent-based people search).

Your job: Convert a messy recruiter query into JSON filters + an embedding text.

NON-NEGOTIABLE:
- Return ONLY valid JSON.
- NEVER omit any keys from the output schema.
- Do NOT hallucinate. Only extract constraints explicitly present.
- If a field is not present, set it to null or [].

Allowed intent values (reuse experience intents):
{{INTENT_ENUM}}

OUTPUT SCHEMA (must match exactly):
{
  "query_original": "...",
  "query_cleaned": "...",

  "must": {
    "intents": [],
    "domains": [],
    "sub_domains": [],
    "company_names": [],
    "company_types": [],
    "employment_types": [],
    "seniority_levels": [],
    "skills": [],
    "tools": [],
    "keywords": [],
    "location": { "city": null, "country": null, "location_text": null },
    "time": { "start_date": null, "end_date": null, "is_ongoing": null, "time_text": null },
    "min_years_experience": null,
    "max_salary_inr_per_month": null,
    "open_to_work_only": null
  },

  "should": {
    "intents": [],
    "domains": [],
    "skills": [],
    "tools": [],
    "keywords": []
  },

  "exclude": {
    "company_names": [],
    "skills": [],
    "tools": [],
    "keywords": []
  },

  "search_phrases": [],
  "query_embedding_text": "",
  "confidence_score": 0.0
}

EXTRACTION RULES:
1) MUST (strict filters — only these; embeddings do candidate generation):
   - Put in must ONLY: explicit company/team names, explicit city (location), explicit time window (dates), explicit open_to_work_only, explicit salary cap/offer.
   - must.company_names: only when user names specific company/team.
   - must.location: only when user names specific city/country/place.
   - must.time (start_date/end_date): only when user gives explicit date range.
   - must.open_to_work_only: only when user explicitly says open to work / seeking / ready for job.
   - must.max_salary_inr_per_month: only when user gives explicit salary/offer (e.g. "₹20,000/month").
2) SHOULD (rerank bonus only — everything else):
   - Put in should: skills, tools, keywords, intents, domains, sub_domains, company_types, employment_types, seniority_levels, and any "X years experience" or similar. These do NOT filter out candidates; they boost ranking when present.
   - min_years_experience → put in should.keywords or leave null; do NOT use must.min_years_experience.
3) TIME:
   - If explicit dates: fill must.time start_date/end_date (YYYY-MM-DD best; else YYYY-MM).
   - If relative only: put in time.time_text and keep dates null; do not put in must.
   - Backend: cards with both dates must overlap query range; cards with missing start/end are kept but downranked.
4) LOCATION:
   - If explicit city/country: fill must.location.
   - If vague: put in should.keywords, not must.location.
5) SALARY (recruiter offer budget):
   - If "₹20,000/month" → must.max_salary_inr_per_month = 20000. Interpreted as offer_salary_inr_per_year = 20000*12.
   - If salary mentioned but unit unclear, put in should.keywords and leave salary null.
6) OPEN TO WORK:
   - Set must.open_to_work_only=true ONLY when explicit (e.g. "open to work", "seeking").
7) KEYWORDS (in should):
   - Put leftover meaningful terms into should.keywords (e.g. "fund managers", "research-heavy", "3 years experience").

SEARCH PHRASES:
- Generate 5–15 concise phrases combining the main constraints.

QUERY EMBEDDING TEXT:
- Make a single text string optimized for semantic search:
  include must + should constraints + key context words,
  but do not add new facts.

INPUT:
Original query:
{{USER_TEXT}}

Cleaned query:
{{CLEANED_TEXT}}
"""

PROMPT_SEARCH_VALIDATE_FILTERS = """
You are a strict validator for search filter JSON.

INPUTS:
query_original:
{{QUERY_ORIGINAL}}

query_cleaned:
{{QUERY_CLEANED}}

extracted_json:
{{EXTRACTED_JSON}}

RULES:
- Return ONLY valid JSON in the same schema.
- NEVER omit keys.
- Remove hallucinated constraints not grounded in query_cleaned.
- De-duplicate arrays, lowercase-normalize skills/tools where safe (keep original casing for company names).
- confidence_score must be float in [0.0, 1.0].
- Ensure query_embedding_text exists and includes all must/should terms.

OUTPUT: same JSON schema as extraction.
"""


def get_cleanup_prompt(user_text: str) -> str:
    return PROMPT_SEARCH_CLEANUP.replace("{{USER_TEXT}}", user_text)


def get_extract_prompt(user_text: str, cleaned_text: str) -> str:
    return (
        PROMPT_SEARCH_EXTRACT_FILTERS.replace("{{INTENT_ENUM}}", INTENT_ENUM)
        .replace("{{USER_TEXT}}", user_text)
        .replace("{{CLEANED_TEXT}}", cleaned_text)
    )


def get_validate_prompt(query_original: str, query_cleaned: str, extracted_json: str) -> str:
    return (
        PROMPT_SEARCH_VALIDATE_FILTERS.replace("{{QUERY_ORIGINAL}}", query_original)
        .replace("{{QUERY_CLEANED}}", query_cleaned)
        .replace("{{EXTRACTED_JSON}}", extracted_json)
    )


# ---------------------------------------------------------------------------
# Single extraction prompt → JSON stored in Search.parsed_constraints_json
# Maps directly to DB columns: company_norm, team_norm, intent_primary, domain, etc. + person_profiles
# ---------------------------------------------------------------------------

PROMPT_SEARCH_SINGLE_EXTRACT = """You are a structured search-query parser for CONXA (intent-based people search).

Convert the user query into JSON constraints that map to our DB.

IMPORTANT:
- Return ONLY valid JSON.
- NEVER omit any key from the output schema.
- Do NOT hallucinate; only extract what is explicitly present.
- If not present, use null or [].
- Normalize company/team for exact match: lowercase + trim -> company_norm / team_norm.

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
  "confidence_score": 0.0
}

RULES:
1) MUST vs SHOULD
- MUST only if the query clearly requires it (e.g., "only", "must", exact city, exact company, salary, explicit open to work).
- Otherwise put it in SHOULD.

2) Salary
- If query contains "₹X/month", set offer_salary_inr_per_year = X*12
- If "₹X LPA" or "₹X/year", convert to per year
- If salary text is unclear, add it to should.keywords and leave offer_salary_inr_per_year null

3) Time
- If explicit years/dates exist, fill time_start/time_end as YYYY-MM-DD when possible (YYYY-01-01/ YYYY-12-31 ok).
- If relative ("last 2 years"), keep in should.keywords and leave dates null.

4) Location
- If city/country explicit, fill city/country and also location_text.
- Otherwise only location_text if present.

5) Query embedding text
Create query_embedding_text as a concise text blob for semantic search including:
must constraints + should terms + key nouns/verbs from query.
Do not add new facts.

6) search_phrases
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
