# Search Flow Documentation (Current)

This document reflects the current search implementation in `apps/api`.

Scope:
- `POST /search` pipeline from request to response and persistence
- ranking and fallback behavior
- `why_matched` LLM explainability + deterministic fallback
- related endpoints (`GET /people/{id}`, unlock, discover, public profile)
- prompt and schema references

## 1) Quick Navigation

| Area | File | What to read |
|---|---|---|
| Search routes | `apps/api/src/routers/search.py` | `search`, `get_person`, `unlock_contact`, `list_people`, `get_person_public_profile` |
| Search pipeline | `apps/api/src/services/search.py` | `run_search`, `_apply_card_filters`, `_collapse_and_rank_persons`, `_generate_llm_why_matched` |
| Query parsing provider | `apps/api/src/providers/chat.py` | `parse_search_filters`, `_chat_json`, `chat` |
| Query prompts | `apps/api/src/prompts/search_filters.py` | `PROMPT_SEARCH_CLEANUP`, `PROMPT_SEARCH_SINGLE_EXTRACT` |
| Explainability prompt | `apps/api/src/prompts/search_why_matched.py` | `get_why_matched_prompt` |
| Filter normalization | `apps/api/src/services/filter_validator.py` | `validate_and_normalize` |
| Search schemas | `apps/api/src/schemas/search.py` | `SearchRequest`, `ParsedConstraintsPayload`, `SearchResponse` |
| DB entities | `apps/api/src/db/models.py` | `Search`, `SearchResult`, `UnlockContact`, `PersonProfile` |
| Config/constants | `apps/api/src/core/config.py`, `apps/api/src/core/constants.py` | rate limits, model settings, expiry |

## 2) API Surface

### 2.1 `POST /search`

- Route: `apps/api/src/routers/search.py` -> `search(...)`
- Body schema: `SearchRequest`
- Header: optional `Idempotency-Key`
- Requires auth (`current_user`)
- Rate limited using `search_rate_limit`

Response: `SearchResponse`

### 2.2 Related endpoints

- `GET /people/{person_id}?search_id=...` -> gated profile view for a valid search session
- `POST /people/{person_id}/unlock-contact` -> unlock contact details for that search
- `GET /people` -> discover list
- `GET /people/{person_id}/profile` -> public profile + card families

## 3) Main Search Pipeline (`run_search`)

File: `apps/api/src/services/search.py`

### Step 0: Idempotency read

If `Idempotency-Key` exists:
- check `get_idempotent_response(db, key, searcher_id, SEARCH_ENDPOINT)`
- if found, return stored `SearchResponse` immediately

### Step 1: Credit pre-check

- `balance = await get_balance(db, searcher_id)`
- if `balance < 1`, return `402 Insufficient credits`

### Step 2: Parse query with LLM

- `chat = get_chat_provider()`
- `filters_raw = await chat.parse_search_filters(body.query)`

`parse_search_filters` currently does:
1. cleanup prompt (plain text)
2. single extract prompt (JSON)

On parser failure (`ChatServiceError`), fallback payload is:

```json
{
  "query_original": "<raw_query>",
  "query_cleaned": "<raw_query>",
  "query_embedding_text": "<raw_query>"
}
```

### Step 3: Normalize parsed constraints

- `payload = ParsedConstraintsPayload.from_llm_dict(filters_raw)`
- `payload = validate_and_normalize(payload)`
- `filters_dict = payload.model_dump(mode="json")`

`validate_and_normalize` performs deterministic cleanup:
- dedupe/strip/lowercase where needed
- enforce valid `intent_primary`
- move weak MUST constraints into SHOULD for recall protection
- normalize dates into `YYYY-MM-DD`
- normalize salary to INR/year
- dedupe exclude and search phrases

### Step 4: Request-level overrides

- `open_to_work_only`: request body value overrides parsed value
- `offer_salary_inr_per_year`: `body.salary_max` overrides parsed `must.offer_salary_inr_per_year`

Note:
- `salary_min` is for recruiter-side display semantics and is not used in SQL filtering here.

### Step 5: Embed query text

Embedding text priority:
1. `payload.query_embedding_text`
2. `payload.query_original`
3. request `body.query`

Then:
- `embed_provider.embed([embedding_text])`
- `normalize_embedding(...)`

Failure:
- embedding failure => `503`
- empty vector => `_create_empty_search_response(...)` (creates `Search`, deducts 1 credit, returns empty `people`)

### Step 6: Lexical bonus candidates

`_lexical_candidates(...)` runs FTS on:
- `experience_cards.search_document`
- `experience_card_children.search_document` (joined to visible parent cards)

It calculates per-person rank from `ts_rank_cd(...)`, normalizes by max rank, and caps at `LEXICAL_BONUS_MAX`.

### Step 7: Candidate retrieval with fallback tiers

Loop starts at `fallback_tier = 0` and runs until enough unique people or tier 3.

Per-iteration queries:
- parent vector candidates (`ExperienceCard.embedding.cosine_distance(query_vec)`) with filters
- child min-distance per person with filters
- top child evidence rows per person (row_number window over distance)

Filters are applied by `_apply_card_filters` and include:
- MUST fields (company/team, intent, domain, sub-domain, employment type, seniority)
- location condition (`ILIKE`) when location filter active
- time overlap when time filter active:
  - must have at least one date bound
  - overlap condition using nullable bounds
- `is_current` when present
- EXCLUDE company list and EXCLUDE keyword overlap
- optional `PersonProfile` join for:
  - `open_to_work_only`
  - `preferred_locations` overlap
  - salary bound: `work_preferred_salary_min IS NULL OR <= offer`

Tier relax order:
- tier 0: strict
- tier 1: relax time
- tier 2: relax location
- tier 3: relax company/team

EXCLUDE is never relaxed.

### Step 8: Collapse and score persons

`_collapse_and_rank_persons(...)` builds per-person aggregate score.

Similarity transform:
- `sim = 1 / (1 + distance)`

Base components:
- `parent_best`
- `child_best`
- `avg_top3` over top similarities from parent+child evidence

Score:
- `base = 0.65*parent_best + 0.25*child_best + 0.10*avg_top3`
- `+ lexical bonus`
- `+ should bonus` (capped)
- `- penalties` (date/location penalties when corresponding filter tiers are relaxed)
- floor at `0`

Returns:
- parent card similarities by person
- child best similarity by person
- child evidence tuples by person
- best parent ids inferred from child evidence
- sorted `(person_id, score)`

Then top list is `TOP_PEOPLE` (currently 5).

### Step 9: Post-rank tie adjustments

After profiles are loaded for top list:
- if salary filter is active, candidates with known salary min are prioritized for equal score
- if query has explicit date range, candidates with full date overlap are prioritized for equal score

### Step 10: Persist search and deduct credit

- create `Search` row with:
  - `query_text`
  - `parsed_constraints_json`
  - `filters`
  - `extra = {"fallback_tier": <tier>}`
  - `expires_at`
- flush
- deduct 1 credit (`reason="search"`)

### Step 11: Build explainability (`why_matched`)

For each ranked person:
1. build deterministic fallback bullet list from parent and child evidence
2. build compact evidence payload (`_build_person_why_evidence`)

Then batch call once:
- `_generate_llm_why_matched(chat, payload, people_evidence)`
- prompt from `get_why_matched_prompt(...)`
- parse JSON and sanitize lines (`_sanitize_why_matched_lines`)

Final per-person reasons:
- use LLM reasons when present and valid
- else use deterministic fallback bullets

Persisted into `SearchResult.extra.why_matched` and returned in API `PersonSearchResult.why_matched`.

### Step 12: Build final response people list

`_build_search_people_list(...)` assembles `PersonSearchResult` entries with:
- person identity/headline/bio
- similarity percent
- `why_matched`
- open_to_work/open_to_contact
- work preference fields
- up to 3 matched cards

Special handling:
- people matched only via child embeddings get parent cards inferred from child evidence
- fallback to latest visible cards if needed

### Step 13: Idempotency write

If key was provided:
- save response with `save_idempotent_response(...)`

## 4) Explainability Flow in Detail

### 4.1 Input evidence schema (internal)

Produced by `_build_person_why_evidence`:

```json
{
  "person_id": "uuid",
  "open_to_work": true,
  "open_to_contact": false,
  "matched_parent_cards": [
    {
      "title": "...",
      "company_name": "...",
      "location": "...",
      "summary": "...",
      "search_phrases": ["..."],
      "similarity": 0.8123,
      "start_date": "2024-01-01",
      "end_date": null
    }
  ],
  "matched_child_cards": [
    {
      "title": "...",
      "headline": "...",
      "summary": "...",
      "context": "...",
      "tags": ["..."],
      "search_phrases": ["..."],
      "similarity": 0.7441
    }
  ]
}
```

### 4.2 LLM output schema

Expected output for `_generate_llm_why_matched`:

```json
{
  "people": [
    {
      "person_id": "uuid",
      "why_matched": ["reason 1", "reason 2", "reason 3"]
    }
  ]
}
```

Sanitization rules:
- max 3 reasons/person
- dedupe case-insensitively
- each reason trimmed and length-limited

### 4.3 Frontend usage

`apps/web/src/components/search/person-result-card.tsx`:
- first tries `person.why_matched`
- fallback display uses matched card titles/summaries
- label shown to user: `Why this card was shown:`

## 5) Ranking and Fallback Constants

Source: `apps/api/src/services/search.py`

```text
OVERFETCH_CARDS = 50
TOP_PEOPLE = 5
MATCHED_CARDS_PER_PERSON = 3
MIN_RESULTS = 15
TOP_K_CARDS = 5

WEIGHT_PARENT_BEST = 0.65
WEIGHT_CHILD_BEST = 0.25
WEIGHT_AVG_TOP3 = 0.10

LEXICAL_BONUS_MAX = 0.25
SHOULD_BOOST = 0.02
SHOULD_CAP = 10
SHOULD_BONUS_MAX = 0.25

MISSING_DATE_PENALTY = 0.12
LOCATION_MISMATCH_PENALTY = 0.10

FALLBACK_TIER_STRICT = 0
FALLBACK_TIER_TIME_SOFT = 1
FALLBACK_TIER_LOCATION_SOFT = 2
FALLBACK_TIER_COMPANY_TEAM_SOFT = 3
```

## 6) Prompt Reference

### 6.1 Active prompts in search flow

#### A) Cleanup prompt

Source: `apps/api/src/prompts/search_filters.py` -> `PROMPT_SEARCH_CLEANUP`

```text
You are a search query cleanup engine.

Goal: Clean the user's search query for reliable structured extraction.

RULES:
1) Do NOT add facts or interpret beyond the text.
2) Keep names, companies, tools, numbers EXACTLY as written.
3) Fix typos/spacing. Preserve meaning.
4) Output ONLY cleaned text. No commentary. No JSON.

User query:
{{USER_TEXT}}
```

#### B) Single extract prompt

Source: `apps/api/src/prompts/search_filters.py` -> `PROMPT_SEARCH_SINGLE_EXTRACT`

```text
You are a structured search-query parser for CONXA (intent-based people search).

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
- If query contains "INR X/month", set offer_salary_inr_per_year = X*12
- If "INR X LPA" or "INR X/year", convert to per year
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
Generate 5-15 concise phrases combining the key constraints.

INPUT:
query_original:
{{QUERY_ORIGINAL}}

query_cleaned:
{{QUERY_CLEANED}}
```

#### C) Why-matched prompt

Source: `apps/api/src/prompts/search_why_matched.py` -> `get_why_matched_prompt`

```text
You are a search result explanation engine.

Task:
- Explain why each person was shown for the query.
- Use only the provided evidence.

Return ONLY valid JSON with this exact schema:
{
  "people": [
    {
      "person_id": "string",
      "why_matched": ["string", "string", "string"]
    }
  ]
}

Rules:
1) Keep each reason short (max 120 chars).
2) Return 1-3 reasons per person.
3) Mention concrete overlap with query constraints when possible (skills, domain, company, time, location, availability).
4) Do not invent facts not present in input.
5) Do not include markdown, bullets, or prose outside JSON.
```

### 6.2 Prompt notes

`PROMPT_SEARCH_EXTRACT_FILTERS` and `PROMPT_SEARCH_VALIDATE_FILTERS` exist in `search_filters.py` but are not used by `parse_search_filters` in the current runtime path.

## 7) Schema Reference

### 7.1 Request schema: `SearchRequest`

```json
{
  "query": "string",
  "open_to_work_only": "boolean|null",
  "preferred_locations": ["string"],
  "salary_min": "number|null",
  "salary_max": "number|null"
}
```

### 7.2 Parsed constraint schema: `ParsedConstraintsPayload`

```json
{
  "query_original": "string",
  "query_cleaned": "string",
  "must": {
    "company_norm": ["string"],
    "team_norm": ["string"],
    "intent_primary": ["string"],
    "domain": ["string"],
    "sub_domain": ["string"],
    "employment_type": ["string"],
    "seniority_level": ["string"],
    "location_text": "string|null",
    "city": "string|null",
    "country": "string|null",
    "time_start": "string|null",
    "time_end": "string|null",
    "is_current": "boolean|null",
    "open_to_work_only": "boolean|null",
    "offer_salary_inr_per_year": "number|null"
  },
  "should": {
    "skills_or_tools": ["string"],
    "keywords": ["string"],
    "intent_secondary": ["string"]
  },
  "exclude": {
    "company_norm": ["string"],
    "keywords": ["string"]
  },
  "search_phrases": ["string"],
  "query_embedding_text": "string",
  "confidence_score": "number"
}
```

### 7.3 Response schema: `SearchResponse`

```json
{
  "search_id": "uuid",
  "people": [
    {
      "id": "uuid",
      "name": "string|null",
      "headline": "string|null",
      "bio": "string|null",
      "similarity_percent": "integer|null",
      "why_matched": ["string"],
      "open_to_work": true,
      "open_to_contact": false,
      "work_preferred_locations": ["string"],
      "work_preferred_salary_min": "number|null",
      "matched_cards": ["ExperienceCardResponse"]
    }
  ]
}
```

### 7.4 Persisted metadata

`Search.extra`:

```json
{
  "fallback_tier": 0
}
```

`SearchResult.extra`:

```json
{
  "matched_parent_ids": ["uuid"],
  "matched_child_ids": ["uuid"],
  "why_matched": ["string"]
}
```

## 8) Search Session Validation and Expiry

Used by profile/unlock flows (`_validate_search_session`):

- search must exist and belong to caller
- search must not be expired
- optional person must belong to that search result set

Expiry check:
- primary: `search.expires_at`
- fallback behavior if needed: compare `created_at` against `SEARCH_RESULT_EXPIRY_HOURS`

## 9) Related Flows

### 9.1 `get_person_profile`

- validates search session and person membership
- loads person, profile, visible cards, unlock row
- contact returned only if:
  - user is open_to_work or open_to_contact
  - and requester has unlocked contact for this search
- returns card families and bio payload

### 9.2 `unlock_contact`

- idempotent by endpoint `POST /people/{id}/unlock-contact`
- validates session and target
- blocks if target not open to contact/work
- charges 1 credit only on first unlock row creation

### 9.3 `list_people_for_discover`

- shows people with at least one visible experience card
- returns display name, current city, top summaries

### 9.4 `get_public_profile_impl`

- returns public bio + visible card families for a person
- no search session requirement

## 10) Operational Notes

- Search still works if explanation LLM fails; deterministic reasons are used.
- If chat parser fails, search still runs from raw query fallback.
- If embedding fails, request fails with `503`.
- Search and result rows are persisted with the same transaction context used for credit deduction.

## 11) Change Checklist (When Updating Search)

When changing search behavior, update this document and verify:

1. `run_search` pipeline step ordering
2. filter semantics in `_apply_card_filters`
3. score formula / constants
4. explainability prompt/output schema
5. request/response schemas in `src/schemas/search.py`
6. frontend usage of `why_matched` display
