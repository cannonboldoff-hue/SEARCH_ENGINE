# Search Flow — Step-by-Step Documentation

This document describes the **search flow** end-to-end: from the HTTP request through query parsing, embedding, hybrid filtering, vector similarity, ranking, and response building. Every major function and decision point is explained in detail.

---

## Table of Contents

1. [Overview](#overview)
2. [Entry Point: Router](#entry-point-router)
3. [Search Service Facade](#search-service-facade)
4. [Main Search Pipeline: `run_search`](#main-search-pipeline-run_search)
5. [Query Parsing (LLM Pipeline)](#query-parsing-llm-pipeline)
6. [Filter Payload and Request Overrides](#filter-payload-and-request-overrides)
7. [Embedding the Query](#embedding-the-query)
8. [SQL: Base Query and MUST/EXCLUDE Filters](#sql-base-query-and-mustexclude-filters)
9. [Child Embedding Search](#child-embedding-search)
10. [Ranking, Collapse, and Top N](#ranking-collapse-and-top-n)
11. [Building the Response](#building-the-response)
12. [Supporting Functions](#supporting-functions)
13. [Profile View and Unlock](#profile-view-and-unlock)
14. [Discover List](#discover-list)
15. [Constants and Configuration](#constants-and-configuration)
16. [Prompts (Full Text and Usage)](#prompts-full-text-and-usage)
17. [Schemas (Full Reference)](#schemas-full-reference)

---

## Overview

**Flow in one sentence:** The client sends a natural-language search query; the API parses it into structured constraints (LLM: cleanup → single extract → validate/normalize), embeds the query for semantic search, runs a hybrid SQL query (structured MUST/EXCLUDE filters + vector similarity on `experience_cards` and `experience_card_children`), collapses results by person, reranks with “should” bonuses, optionally downranks by salary/date clarity, returns top 5 people with 1–3 matched cards each, and persists the search for profile view/unlock.

**Key components:**

| Component | Role |
|-----------|------|
| **Router** | `POST /search` → rate limit, auth, delegate to service |
| **Search service** | `run_search()` orchestrates parsing, embedding, SQL, ranking, downrank, response |
| **Chat provider** | `parse_search_filters()` — cleanup (plain text) → single extract (JSON) → validate/normalize (deterministic post-process) |
| **Embedding provider** | Embeds `query_embedding_text` (or raw query) into a vector |
| **Database** | `ExperienceCard` and `ExperienceCardChild` with `Vector(324)`; pgvector cosine distance for similarity |
| **Credits** | 1 credit per search; idempotency key returns cached response |

---

## Entry Point: Router

**File:** `src/routers/search.py`

### `POST /search` — `search()`

```python
@router.post("/search", response_model=SearchResponse)
@limiter.limit(_settings.search_rate_limit)
async def search(
    request: Request,
    body: SearchRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await search_service.search(db, current_user.id, body, idempotency_key)
```

**What it does:**

- **Rate limit:** Applied via `@limiter.limit(_settings.search_rate_limit)` (e.g. `"10/minute"`).
- **Auth:** `get_current_user` ensures the caller is authenticated; `current_user.id` is the `searcher_id`.
- **Body:** `SearchRequest` — `query` (required), optional `open_to_work_only`, `preferred_locations`, `salary_min` (recruiter min ₹/year, display only), `salary_max` (recruiter offer budget ₹/year).
- **Idempotency:** Optional header `Idempotency-Key`; if present, duplicate requests can return the same cached response without charging again.
- **Delegate:** Calls `search_service.search(db, searcher_id, body, idempotency_key)` and returns `SearchResponse`.

---

## Search Service Facade

**File:** `src/services/search.py`

### `SearchService` class

Static facade that delegates to the real implementations:

| Method | Delegates to | Purpose |
|--------|--------------|---------|
| `search(db, searcher_id, body, idempotency_key)` | `run_search(...)` | Full search pipeline |
| `get_profile(db, searcher_id, person_id, search_id)` | `get_person_profile(...)` | Profile for a person in a search result |
| `unlock(db, searcher_id, person_id, search_id, idempotency_key)` | `unlock_contact(...)` | Unlock contact for a person in a search |
| `list_people(db)` | `list_people_for_discover(db)` | Discover grid: people + top 5 experience titles |
| `get_public_profile(db, person_id)` | `get_public_profile_impl(...)` | Public profile (bio + card families) |

---

## Main Search Pipeline: `run_search`

**Function:** `run_search(db, searcher_id, body, idempotency_key) -> SearchResponse`

**File:** `src/services/search.py`

This is the core search implementation. Steps in order:

### Step 1: Idempotency

- If `idempotency_key` is set:
  - Call `get_idempotent_response(db, idempotency_key, searcher_id, SEARCH_ENDPOINT)` where `SEARCH_ENDPOINT = "POST /search"`.
  - If a stored response exists (`existing.response_body`), return `SearchResponse(**existing.response_body)` immediately (no credits, no LLM/embedding).

### Step 2: Credit check

- `balance = await get_balance(db, searcher_id)` (from `PersonProfile.balance`).
- If `balance < 1`, raise `HTTPException(402, "Insufficient credits")`.

### Step 3: Parse query into constraints (LLM)

- `chat = get_chat_provider()`.
- `filters_raw = await chat.parse_search_filters(body.query)` (cleanup → single extract; see [Query Parsing](#query-parsing-llm-pipeline)).
- On `ChatServiceError`: fallback to raw query only:
  - `filters_raw = { "query_original": raw_q, "query_cleaned": raw_q, "query_embedding_text": raw_q }`.

### Step 4: Normalize and validate parsed constraints

- `payload = ParsedConstraintsPayload.from_llm_dict(filters_raw)`.
- `payload = validate_and_normalize(payload)` (see [Validate/Normalize step](#validate-normalize-step)).
- `filters_dict = payload.model_dump(mode="json")` (stored in `Search.filters` and `Search.parsed_constraints_json`).
- `must = payload.must`, `exclude = payload.exclude`.

### Step 5: Embedding text and request overrides

- **Embedding text:** `embedding_text = (payload.query_embedding_text or payload.query_original or body.query or "").strip()`, else `body.query`.
- **Request overrides:**
  - `open_to_work_only`: `body.open_to_work_only` if not None, else `must.open_to_work_only or False`.
  - **Offer salary (₹/year):** `offer_salary_inr_per_year = body.salary_max` if set, else `must.offer_salary_inr_per_year`. Used to match candidates where `work_preferred_salary_min <= offer_salary_inr_per_year` or NULL (NULL candidates are kept but downranked).

### Step 6: Embed query

- `embed_provider = get_embedding_provider()`.
- `texts = [embedding_text]` (or `[body.query or ""]` if no embedding text).
- `vecs = await embed_provider.embed(texts)`.
- `query_vec = normalize_embedding(vecs[0], embed_provider.dimension)`.
- On embedding failure: raise `HTTPException(503, detail=str(e))`.
- If `query_vec` is empty: create a `Search` record, deduct 1 credit, return `SearchResponse(search_id=..., people=[])` (and save idempotent response if key provided).

### Step 7: Build base SQL + MUST/EXCLUDE filters

- Build a query that:
  - Selects `ExperienceCard` and a **distance** expression: `(experience_cards.embedding <=> CAST(:qvec AS vector))` (pgvector cosine distance).
  - Restricts to `experience_card_visibility == True` and `embedding IS NOT NULL`.
- Apply all **MUST** and **EXCLUDE** filters (see [SQL: Base Query and MUST/EXCLUDE Filters](#sql-base-query-and-mustexclude-filters)).
- Order by distance, limit `OVERFETCH_CARDS` (50).
- Execute with `execute_params` including `qvec`.

### Step 8: Child embedding search

- Run a separate query on `experience_card_children`: for each **person_id**, compute **minimum** distance over all visible child cards (joined to visible parent `ExperienceCard`).
- Build `child_best_sim: dict[person_id, similarity]` where similarity = `1 - distance` (and take max if multiple rows per person).
- Run an **evidence** query (same filters): for each person, return the top 1–3 child rows by distance (using `ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY distance)`). From that, build `child_best_parent_ids: dict[person_id, list[parent_experience_id]]` — the parent card(s) that actually matched the child embedding, in best-match order.

### Step 9: Collapse by person and rerank

- From the parent-card rows, group by `person_id`; for each card compute `sim = 1 - distance` and add a **should bonus** (see `_should_bonus`).
- Per person: **best parent score** = max of (sim + bonus) over their cards.
- **Final person score** = max(best parent score, child_best_sim for that person).
- Persons who **only** matched via children (no parent in `person_cards`) are added with their child similarity.
- Sort by score descending; take **top 5** (`TOP_PEOPLE`).
- **Downranking (tie-breaks):** When `offer_salary_inr_per_year` is set, re-sort so candidates with a stated `work_preferred_salary_min` rank above those with NULL. When the query has a date range (`time_start`/`time_end`), re-sort so persons whose matched cards have full date overlap rank above those with missing card dates.

### Step 10: Persist search and results

- Create `Search(searcher_id, query_text=body.query, parsed_constraints_json=filters_dict, filters=filters_dict, expires_at=now + SEARCH_RESULT_EXPIRY_HOURS)`.
- `db.add(search_rec)`, `db.flush()`.
- Deduct 1 credit: `deduct_credits(db, searcher_id, 1, "search", "search_id", search_rec.id)`; on failure raise 402.
- For each of the top 5: create `SearchResult(search_id, person_id, rank, score)`.

### Step 11: Build response

- If the top-N list is empty: return `SearchResponse(search_id, people=[])`, optionally save idempotent response, return.
- Load `Person` and `PersonProfile` for the top 5 IDs.
- For persons who **only** matched via children: load the **parent cards that actually matched** (from `child_best_parent_ids`) into `child_only_cards`, preserving match order; if a person has no evidence IDs, fall back to up to 3 visible parent cards by `created_at desc`.
- For each (person_id, score) in the top 5:
  - **Matched cards:** From `person_cards` take up to 3 best (by score); if none and person is in `child_only_cards`, use those (so the cards shown are the matched evidence, not arbitrary recent cards).
  - Build **headline** from profile’s `current_company` / `current_city`.
  - Build **bio** from profile first/last name, "School: …", "College: …" joined by " · ".
  - Append `PersonSearchResult(id, name, headline, bio, open_to_work, open_to_contact, work_preferred_*, matched_cards)`.
- Return `SearchResponse(search_id=search_rec.id, people=people_list)`.
- If `idempotency_key`: `save_idempotent_response(...)` with status 200 and response body.

---

## Query Parsing (LLM Pipeline)

**Provider:** `ChatProvider.parse_search_filters(query) -> dict`  
**Implementation:** `OpenAICompatibleChatProvider.parse_search_filters` in `src/providers/chat.py`.  
**Prompts:** `src/prompts/search_filters.py`.

### Purpose

Turn the raw user query into a **single JSON** that fits `ParsedConstraintsPayload`: `must` / `should` / `exclude` constraints (e.g. `company_norm`, `team_norm`, `intent_primary`, `domain`, `city`, `time_start`/`time_end`, `offer_salary_inr_per_year`), plus `query_original`, `query_cleaned`, `query_embedding_text`, `search_phrases`, `confidence_score`. This JSON is stored in `Search.filters` and `Search.parsed_constraints_json` and used for SQL filters and for the embedding text.

### Two-step pipeline (cleanup → single extract)

1. **Cleanup (plain text)**  
   - Prompt: `get_cleanup_prompt(query)` → `PROMPT_SEARCH_CLEANUP` with `{{USER_TEXT}}`.  
   - Rules: fix typos/spacing, preserve names/companies/tools/numbers, no added facts, output only cleaned text.  
   - `cleaned_text = (await self._chat([{"role": "user", "content": cleanup_prompt}], max_tokens=500)).strip()`.  
   - If empty, use `query`.

2. **Single extract (JSON)**  
   - Prompt: `get_single_extract_prompt(query, cleaned_text)` → `PROMPT_SEARCH_SINGLE_EXTRACT` with `{{INTENT_ENUM}}`, `{{QUERY_ORIGINAL}}`, `{{QUERY_CLEANED}}`.  
   - Output schema maps directly to DB columns and `ParsedConstraintsPayload`: `must` (company_norm, team_norm, intent_primary, domain, sub_domain, employment_type, seniority_level, city, country, location_text, time_start, time_end, is_current, open_to_work_only, offer_salary_inr_per_year), `should` (skills_or_tools, keywords, intent_secondary), `exclude` (company_norm, keywords), plus search_phrases and query_embedding_text.  
   - `extracted = await self._chat_json(...)` (JSON parsed, with optional `response_format={"type": "json_object"}` and fallback).  
   - Must be a dict; then passed to **validate/normalize** (see [Validate/Normalize step](#validate-normalize-step)).

### Validate/Normalize step

**File:** `src/services/filter_validator.py`  
**Function:** `validate_and_normalize(payload: ParsedConstraintsPayload) -> ParsedConstraintsPayload`

After `ParsedConstraintsPayload.from_llm_dict(filters_raw)`, the payload is run through a **deterministic post-processor** so that LLM quirks do not kill recall or produce malformed filters:

- **MUST → SHOULD (weak constraints):** To avoid over-constraining, excess items are moved from MUST to SHOULD: e.g. at most 2 `intent_primary`, 3 `company_norm`, 3 `team_norm`, 2 `domain` in MUST; rest go to `should.intent_secondary` or `should.keywords`. If `confidence_score` is below a threshold, `domain`/`sub_domain` are demoted to SHOULD (keywords).
- **Normalize tokens:** Company/team/keyword lists are stripped, lowercased where appropriate, and **deduped** (order preserved).
- **Date formats:** `time_start` and `time_end` are normalized to `YYYY-MM-DD`; invalid or unparseable values become `None`. If start &gt; end, they are swapped.
- **Salary conversion:** `offer_salary_inr_per_year` is enforced as ₹/year; values that look like per-month (e.g. &lt; 200k) are multiplied by 12.
- **Intent enum:** Only allowed `intent_primary` values (from `Intent`) are kept; invalid entries are dropped.
- **Dedupes:** All list fields (must, should, exclude, search_phrases) are deduped.

The result is what is stored in `Search.parsed_constraints_json` and used for SQL MUST/EXCLUDE and for embedding text.

### Helper: `_chat_json`

- Calls `_chat` with optional `response_format={"type": "json_object"}`; on failure retries without it.
- Strips markdown/code fences via `_strip_json_from_response`, then `json.loads(raw)`.
- On parse error, raises `ChatServiceError`.

**Note:** The file also defines `PROMPT_SEARCH_EXTRACT_FILTERS` and `PROMPT_SEARCH_VALIDATE_FILTERS` (LLM-based validate with a different schema). The current implementation uses cleanup + single extract + **deterministic** validate/normalize (`validate_and_normalize`), not the LLM validate prompt.

---

## Filter Payload and Request Overrides

**Schemas:** `src/schemas/search.py`. The executed payload is **ParsedConstraintsPayload** (built via `ParsedConstraintsPayload.from_llm_dict(data)`).

### `ParsedConstraintsPayload.from_llm_dict(data)`

- Fills `must` (`ParsedConstraintsMust`), `should` (`ParsedConstraintsShould`), `exclude` (`ParsedConstraintsExclude`) from `data`; uses `_list()` for list fields so missing keys become `[]`.
- Produces: `query_original`, `query_cleaned`, `must`, `should`, `exclude`, `search_phrases`, `query_embedding_text`, `confidence_score`.

### MUST (strict filters — applied in SQL)

- **company_norm, team_norm** → `ExperienceCard.company_norm` / `team_norm` IN (normalized, lowercased lists).
- **intent_primary, domain, sub_domain, employment_type, seniority_level** → `ExperienceCard` columns IN lists.
- **city, country, location_text** → `ExperienceCard.location` ILIKE `%value%` (OR between them).
- **time_start, time_end** → date overlap: card must have both dates and overlap `[time_start, time_end]`, or have a missing start/end (kept but downranked later).
- **is_current** → `ExperienceCard.is_current == must.is_current`.
- **open_to_work_only** → join `PersonProfile` with `open_to_work == True`; can be overridden by `body.open_to_work_only`.
- **offer_salary_inr_per_year** → when set, join `PersonProfile` and filter `work_preferred_salary_min <= offer_salary_inr_per_year OR work_preferred_salary_min IS NULL` (NULL candidates kept but downranked).

### EXCLUDE

- **company_norm** → `NOT ExperienceCard.company_norm IN (...)`.
- **keywords** → `NOT ExperienceCard.search_phrases && exclude keywords` (array overlap).

### SHOULD (preferences — used only for rerank bonus)

- Not applied as SQL filters; used in `_should_bonus()` to add a small score boost per match (see [Ranking, Collapse, and Top N](#ranking-collapse-and-top-n)).

### Request-level overrides (in `run_search`)

- **open_to_work_only:** `body.open_to_work_only` overrides parsed value when not None.
- **Offer salary (₹/year):** `body.salary_max` overrides parsed `must.offer_salary_inr_per_year` when set.
- When **open_to_work_only** is True and `body.preferred_locations` is set: filter `PersonProfile.work_preferred_locations` overlap with that list.
- When **offer_salary_inr_per_year** is set: filter as above; then downrank persons with NULL `work_preferred_salary_min` after taking top 5 by score.

---

## Embedding the Query

**Provider:** `get_embedding_provider()` → `EmbeddingProvider.embed(texts)`.  
**Config:** `embed_api_base_url`, `embed_model`, `embed_dimension` (e.g. 324).  
**Util:** `normalize_embedding(vec, dim)` in `src/utils.py`.

### Flow

1. **Text:** `embedding_text` from payload (or raw query).
2. **API:** `embed_provider.embed([embedding_text])` → POST to `/v1/embeddings`, `input`: list of strings.
3. **Response:** List of vectors; take `vecs[0]` for the single query.
4. **Normalize:** `normalize_embedding(vecs[0], embed_provider.dimension)`:
   - If `len(vec) < dim`: zero-pad to `dim`.
   - If `len(vec) >= dim`: truncate to `dim`.
   - Ensures compatibility with DB `Vector(324)` (or configured `embed_dimension`).

---

## SQL: Base Query and MUST/EXCLUDE Filters

**File:** `src/services/search.py` inside `run_search`.

### Base

- **Table:** `experience_cards`.
- **Conditions:** `experience_card_visibility == True`, `embedding IS NOT NULL`.
- **Distance:** `(experience_cards.embedding <=> CAST(:qvec AS vector))` as `dist` (cosine distance; pgvector).

### MUST filters (all AND)

| Payload field | SQL |
|---------------|-----|
| `must.company_norm` | `company_norm IN (normalized, lowercased list)` |
| `must.team_norm` | `team_norm IN (normalized, lowercased list)` |
| `must.intent_primary` | `intent_primary IN (...)` |
| `must.domain` | `domain IN (...)` |
| `must.sub_domain` | `sub_domain IN (...)` |
| `must.employment_type` | `employment_type IN (...)` |
| `must.seniority_level` | `seniority_level IN (...)` |
| `must.city` / `country` / `location_text` | `location ILIKE %value%` (OR between them) |
| `must.time_start`, `must.time_end` | Overlap: `(start_date IS NOT NULL AND end_date IS NOT NULL AND start_date <= time_end AND end_date >= time_start) OR (start_date IS NULL OR end_date IS NULL)` |
| `must.is_current` | `is_current == must.is_current` |

### EXCLUDE filters

- `company_norm NOT IN (exclude_norms)` from `exclude.company_norm`.
- `NOT search_phrases && norm_terms` for `exclude.keywords`.

### PersonProfile join (open-to-work and/or offer salary)

- When `open_to_work_only` or `offer_salary_inr_per_year` is set: join `PersonProfile` on `person_id`; if open_to_work_only, add `open_to_work == True`.
- If `body.preferred_locations`: `work_preferred_locations && :loc_arr`.
- If `offer_salary_inr_per_year` set: `work_preferred_salary_min IS NULL OR work_preferred_salary_min <= offer_salary_inr_per_year`.

### Execution

- `order_by` distance ascending, `.limit(OVERFETCH_CARDS)` (50).
- `execute_params`: `qvec` (stringified vector).

---

## Child Embedding Search

**Purpose:** Allow matches from **child** experience cards (e.g. project/role breakdowns) when they are closer to the query than any parent card.

**Query (scoring):**

- Select `ExperienceCardChild.person_id` and `MIN(experience_card_children.embedding <=> CAST(:qvec AS vector))` as `dist`.
- Join to `ExperienceCard` on `parent_experience_id` and `experience_card_visibility == True`.
- Where `ExperienceCardChild.embedding IS NOT NULL`.
- Group by `person_id`.

**Query (evidence):**

- Same FROM/JOIN/WHERE as above, but select `person_id`, `parent_experience_id`, child `id`, and distance (no group by).
- Wrap in a CTE; use `ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY dist)` and keep rows with `rn <= MATCHED_CARDS_PER_PERSON` (3).
- Produces one row per “best” child per person, up to 3 per person, ordered by distance.

**Result:**

- **Scoring:** For each person_id, minimum distance → `child_best_sim[person_id] = 1.0 - distance`. Used when collapsing: person’s final score = max(best parent score, child_best_sim).
- **Evidence:** `child_best_parent_ids[person_id]` = ordered list (up to 3) of `parent_experience_id` values that correspond to the matching child rows. Used in Step 11 to load and show the parent card(s) that actually matched, not arbitrary recent cards.

---

## Ranking, Collapse, and Top N

### Per-card score (parent rows)

- **Similarity:** `sim = 1.0 - distance`.
- **Should bonus:** `bonus = min(_should_bonus(card, payload.should), 10) * 0.02` (max +0.2).
- **Card score:** `sim + bonus`.

### `_should_bonus(card, should) -> int`

**File:** `src/services/search.py`. **Argument:** `should` is `ParsedConstraintsShould`.

Counts how many “should” constraints the card matches:

- +1 if `should.intent_secondary` and any of `card.intent_secondary` is in `should.intent_secondary`.
- +1 if `should.skills_or_tools` and any term appears in `card.search_phrases` (case-insensitive) or in `card.search_document` (substring).
- +1 if `should.keywords` and any term appears in `card.search_phrases` or `card.search_document` (substring).

Return value is capped at 10 in the caller (`SHOULD_CAP`), then multiplied by `SHOULD_BOOST = 0.02`.

### Collapse by person

- **person_cards:** `dict[person_id, list[(ExperienceCard, score)]]` from parent rows.
- **Per person:** `best_sim = max(score over their cards)`.
- **Merge with children:** `final_score = max(best_sim, child_best_sim.get(person_id, 0))`.
- Add persons that appear only in `child_best_sim` (no parent rows) with score = child similarity.
- Sort by `final_score` descending; take first **TOP_PEOPLE** (5).

---

## Building the Response

- **Person/Profile:** Loaded for the top 5 IDs.
- **Child-only persons:** If a person has no parent cards in `person_cards`, load the parent cards whose IDs are in `child_best_parent_ids[person_id]` (the parents that matched the child embedding), in that order, into `child_only_cards`; if none, fall back to up to 3 visible parent cards by `created_at desc`.
- For each person in the top 5:
  - **matched_cards:** Best 3 from `person_cards` (by score), or from `child_only_cards` if no parent matches (so child-only matches show the parent that actually matched as evidence).
  - **headline:** `current_company / current_city` from profile.
  - **bio:** Profile first/last name, “School: …” + “College: …” joined by “ · ”.
  - **PersonSearchResult:** id, name (display_name), headline, bio, open_to_work, open_to_contact, work_preferred_locations, work_preferred_salary_min, matched_cards (serialized via `experience_card_to_response`).

**Serializer:** `experience_card_to_response(card)` in `src/serializers.py` maps `ExperienceCard` to `ExperienceCardResponse` (id, user_id, title, domain, company_name, dates, summary, intent_primary, seniority_level, etc.).

---

## Supporting Functions

### `_search_expired(search_rec) -> bool`

- If `search_rec.expires_at` is set: return `expires_at < now`.
- Else: return `created_at < (now - SEARCH_RESULT_EXPIRY_HOURS)`.
- Used for profile view and unlock to reject expired searches.

### `_parse_date(s) -> date | None`

- Parses `YYYY-MM-DD` or `YYYY-MM`; returns None for invalid/missing.
- Used for MUST time range (start_date, end_date).

### `unlock_endpoint(person_id) -> str`

- Returns `f"POST /people/{person_id}/unlock-contact"` for idempotency scope per target person.

### Credits and idempotency

**File:** `src/services/credits.py`.

- **get_balance(db, person_id):** Reads `PersonProfile.balance` (default 0 if no profile).
- **deduct_credits(db, person_id, amount, reason, reference_type, reference_id):** Selects profile with `with_for_update()`, checks balance, decrements, appends `CreditLedger` row, flushes. Returns True/False.
- **get_idempotent_response(db, key, person_id, endpoint):** Looks up `IdempotencyKey` by key, person_id, endpoint; returns row or None.
- **save_idempotent_response(db, key, person_id, endpoint, status, response_body):** Inserts new `IdempotencyKey` with the response.

---

## Profile View and Unlock

### Get profile (for a person in search results)

**Endpoint:** `GET /people/{person_id}?search_id=...` (query param `search_id` required).  
**Handler:** `search_service.get_profile(db, searcher_id, person_id, search_id)` → `get_person_profile`.

**Logic:**

1. Load `Search` by `search_id` and `searcher_id`; 403 if missing.
2. If `_search_expired(search_rec)`: 403 “Search expired”.
3. Load `SearchResult` for (search_id, person_id); 403 if not in results.
4. Load `Person`, `PersonProfile`, visible `ExperienceCard`s for person, and `UnlockContact` for (searcher, person, search).
5. **Contact:** Only included if (open_to_work or open_to_contact) and an unlock record exists; then build `ContactDetailsResponse` from profile (email_visible, email when visible, phone, linkedin_url, other).
6. **Locations/salary:** Only when open_to_work; else empty.
7. Return `PersonProfileResponse` with experience_cards (backward compatibility), card_families (parent + children), bio, and contact (if unlocked).

### Unlock contact

**Endpoint:** `POST /people/{person_id}/unlock-contact` with body `{ "search_id": "..." }` and optional `Idempotency-Key`.  
**Handler:** `search_service.unlock(...)` → `unlock_contact`.

**Logic:**

1. Idempotency: if key present and response exists for `unlock_endpoint(person_id)`, return cached response.
2. Validate search (same as profile: exists, not expired, searcher owns it).
3. Validate person is in search results.
4. Load profile; 404 if missing. If not `open_to_contact`, 403.
5. If unlock already exists for (searcher, person, search), return success + contact (no extra charge).
6. Check balance >= 1; 402 if not.
7. Create `UnlockContact(searcher_id, target_person_id, search_id)`, flush, deduct 1 credit (reason `unlock_contact`, reference unlock id).
8. Return `UnlockContactResponse(unlocked=True, contact=...)`; save idempotent response if key provided.

---

## Discover List and Public Profile

**Discover:** `GET /people` — list people for discover grid.  
**Handler:** `search_service.list_people(db)` → `list_people_for_discover`.

**Public profile:** `GET /people/{person_id}/profile` — full bio + all experience card families (parent → children) for a person detail page. No search_id or credits.  
**Handler:** `search_service.get_public_profile(db, person_id)` → `get_public_profile_impl`.

**Logic (discover list only):**

1. Subquery: distinct `person_id` from `experience_cards` where `experience_card_visibility == True`.
2. Load `Person`, `PersonProfile`, and card rows `(person_id, summary, created_at)` for those IDs (visible cards only), ordered by person_id and created_at desc.
3. Per person: collect up to 5 non-empty `summary` strings.
4. Return `PersonListResponse(people=[PersonListItem(id, display_name, current_location=current_city, experience_summaries=top 5)])`.

No search_id, no credits, no embedding.

---

## Constants and Configuration

**File:** `src/core/constants.py`: `EMBEDDING_DIM = 324`, `SEARCH_RESULT_EXPIRY_HOURS = 24`.  
**File:** `src/core/config.py`: `embed_dimension` (default 324, matches DB migration).  
**File:** `src/services/search.py`:

- `OVERFETCH_CARDS = 50` — limit for parent vector search before collapse.
- `TOP_PEOPLE = 5` — final number of people returned.
- `MATCHED_CARDS_PER_PERSON = 3` — max cards per person in results.
- `SHOULD_BOOST = 0.02`, `SHOULD_CAP = 10` — rerank bonus (defined inside `run_search`).

**Config:** `src/core/config.py` — `search_rate_limit`, `unlock_rate_limit`, `embed_*`, `chat_*`, etc.

---

## Prompts (Full Text and Usage)

**File:** `src/prompts/search_filters.py`.  
The **current** search flow uses two LLM steps: **cleanup** (plain text) and **single extract** (JSON). The single-extract output schema matches `ParsedConstraintsPayload` (company_norm, team_norm, intent_primary, etc.). Template variables are replaced at runtime.

**Intent enum** (injected into single-extract prompt): allowed values for `must.intent_primary` come from `src.prompts.experience_card_enums` (`INTENT_ENUM`): e.g. `work`, `education`, `project`, `business`, `research`, `practice`, `exposure`, `achievement`, `transition`, `learning`, `life_context`, `community`, `finance`, `other`, `mixed`.

---

### 1. Cleanup prompt

**Constant:** `PROMPT_SEARCH_CLEANUP`  
**Helper:** `get_cleanup_prompt(user_text: str) -> str` — replaces `{{USER_TEXT}}` with the raw query.

**Full prompt text:**

```
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

**Usage:** Single user message; response is plain text only (no JSON). Output is used as `cleaned_text` in the single-extract step. If the model returns empty, the original `query` is used as `cleaned_text`.

---

### 2. Single-extract prompt (in use)

**Constant:** `PROMPT_SEARCH_SINGLE_EXTRACT`  
**Helper:** `get_single_extract_prompt(query_original: str, query_cleaned: str) -> str` — replaces `{{INTENT_ENUM}}`, `{{QUERY_ORIGINAL}}`, `{{QUERY_CLEANED}}`.

Output schema matches `ParsedConstraintsPayload`: `must` (company_norm, team_norm, intent_primary, domain, sub_domain, employment_type, seniority_level, location_text, city, country, time_start, time_end, is_current, open_to_work_only, offer_salary_inr_per_year), `should` (skills_or_tools, keywords, intent_secondary), `exclude` (company_norm, keywords), plus search_phrases, query_embedding_text, confidence_score. Rules: MUST only for explicit strict constraints (company/team, city, dates, salary, open to work); everything else in SHOULD. Salary as offer_salary_inr_per_year (₹/year). Time as time_start/time_end when explicit; otherwise leave null. Normalize company/team to lowercase for company_norm/team_norm.

**Usage:** Sent as a single user message after cleanup; response is parsed as JSON via `_chat_json`. Returned as the final dict for `ParsedConstraintsPayload.from_llm_dict`.

---

### 3. Alternative: extract + validate (not used in current flow)

The file also defines **PROMPT_SEARCH_EXTRACT_FILTERS** (`get_extract_prompt`) and **PROMPT_SEARCH_VALIDATE_FILTERS** (`get_validate_prompt`) with a different schema (company_names, intents, domains, max_salary_inr_per_month, etc.). These are not used by `parse_search_filters`; the current flow uses only cleanup + single extract.

---

## Schemas (Full Reference)

**File:** `src/schemas/search.py`.  
All request/response and filter shapes used by the search flow.

---

### Parsed constraints payload (in use — stored in Search.filters / parsed_constraints_json)

The **executed** payload is **ParsedConstraintsPayload**, built from the single-extract LLM output via `ParsedConstraintsPayload.from_llm_dict(data)`. Same dict is stored in `Search.filters` and `Search.parsed_constraints_json`.

#### `ParsedConstraintsMust`

Strict constraints applied as SQL filters. List fields default to `[]`.

| Field | Type | Description |
|-------|------|-------------|
| `company_norm` | `list[str]` | Card `company_norm` IN (lowercased). |
| `team_norm` | `list[str]` | Card `team_norm` IN (lowercased). |
| `intent_primary` | `list[str]` | Card `intent_primary` IN. |
| `domain`, `sub_domain` | `list[str]` | Card domain fields IN. |
| `employment_type`, `seniority_level` | `list[str]` | Card fields IN. |
| `location_text`, `city`, `country` | `Optional[str]` | Card `location` ILIKE. |
| `time_start`, `time_end` | `Optional[str]` | Date range overlap (YYYY-MM-DD). |
| `is_current` | `Optional[bool]` | Card `is_current` must match. |
| `open_to_work_only` | `Optional[bool]` | Join PersonProfile, open_to_work == True. |
| `offer_salary_inr_per_year` | `Optional[float]` | Recruiter offer ₹/year; filter work_preferred_salary_min <= offer or NULL. |

#### `ParsedConstraintsShould`

Preferences used only for rerank bonus (`_should_bonus`): `skills_or_tools`, `keywords`, `intent_secondary` (match in card `search_phrases` or `search_document` / `intent_secondary`).

#### `ParsedConstraintsExclude`

`company_norm` (list), `keywords` (list) — SQL: NOT IN / NOT search_phrases overlap.

#### `ParsedConstraintsPayload`

Top-level: `query_original`, `query_cleaned`, `must`, `should`, `exclude`, `search_phrases`, `query_embedding_text`, `confidence_score`. Filled via `from_llm_dict(data)`.

---

### Legacy filter payload (SearchFilters* — unused prompts)

`SearchFiltersPayload`, `SearchFiltersMust`, `SearchFiltersShould`, `SearchFiltersExclude`, `SearchFiltersLocation`, `SearchFiltersTime` use a different shape (company_names, intents, domains, max_salary_inr_per_month, etc.) and are not used by the current pipeline.

#### `SearchFiltersLocation` (legacy)

| Field | Type | Default | Description |
|-------|------|--------|-------------|
| `city` | `Optional[str]` | `None` | City name for location filter (ILIKE on card). |
| `country` | `Optional[str]` | `None` | Country for location filter (ILIKE on card). |
| `location_text` | `Optional[str]` | `None` | Free-form location string (ILIKE) when city/country not split. |

#### `SearchFiltersTime`

| Field | Type | Default | Description |
|-------|------|--------|-------------|
| `start_date` | `Optional[str]` | `None` | Start of time range (YYYY-MM-DD or YYYY-MM). |
| `end_date` | `Optional[str]` | `None` | End of time range (YYYY-MM-DD or YYYY-MM). |
| `is_ongoing` | `Optional[bool]` | `None` | Whether “current” / ongoing is implied. |
| `time_text` | `Optional[str]` | `None` | Relative or free-form time (e.g. “last 2 years”) when dates not used. |

#### `SearchFiltersMust`

Strict constraints applied as SQL filters. All list fields default to `[]`, nested objects to their defaults.

| Field | Type | Default | Description |
|-------|------|--------|-------------|
| `intents` | `list[str]` | `[]` | Card `intent_primary` must be in this list. |
| `domains` | `list[str]` | `[]` | Card `domain` must be in this list. |
| `sub_domains` | `list[str]` | `[]` | Card `sub_domain` must be in this list. |
| `company_names` | `list[str]` | `[]` | Card `company_norm` (lowercased) must be in this list. |
| `company_types` | `list[str]` | `[]` | Card `company_type` must be in this list. |
| `employment_types` | `list[str]` | `[]` | Card `employment_type` must be in this list. |
| `seniority_levels` | `list[str]` | `[]` | Card `seniority_level` must be in this list. |
| `skills` | `list[str]` | `[]` | Card `search_phrases` must overlap with these (normalized). |
| `tools` | `list[str]` | `[]` | Same as skills (overlap with `search_phrases`). |
| `keywords` | `list[str]` | `[]` | Same as skills/tools (overlap with `search_phrases`). |
| `location` | `SearchFiltersLocation` | `SearchFiltersLocation()` | City/country/location_text for card location ILIKE. |
| `time` | `SearchFiltersTime` | `SearchFiltersTime()` | Date range or time_text for card dates. |
| `min_years_experience` | `Optional[int]` | `None` | Minimum tenure in years (card date range length). |
| `max_salary_inr_per_month` | `Optional[int]` | `None` | Max salary ₹/month (used when open_to_work_only; converted to yearly for profile filter). |
| `open_to_work_only` | `Optional[bool]` | `None` | If true, join PersonProfile and filter open_to_work; can be overridden by request body. |

#### `SearchFiltersShould`

Preferences used only for rerank bonus (not SQL filters).

| Field | Type | Default | Description |
|-------|------|--------|-------------|
| `intents` | `list[str]` | `[]` | Bonus if card `intent_primary` in list. |
| `domains` | `list[str]` | `[]` | Bonus if card `domain` in list. |
| `skills` | `list[str]` | `[]` | Bonus if any term appears in card `search_phrases`. |
| `tools` | `list[str]` | `[]` | Same. |
| `keywords` | `list[str]` | `[]` | Same. |

#### `SearchFiltersExclude`

Terms that must not appear (SQL: NOT IN / NOT overlap).

| Field | Type | Default | Description |
|-------|------|--------|-------------|
| `company_names` | `list[str]` | `[]` | Exclude cards with `company_norm` in this list. |
| `skills` | `list[str]` | `[]` | Exclude cards whose `search_phrases` overlap these. |
| `tools` | `list[str]` | `[]` | Same. |
| `keywords` | `list[str]` | `[]` | Same. |

#### `SearchFiltersPayload`

Top-level payload built from LLM output. Filled via `from_llm_dict(data)`.

| Field | Type | Default | Description |
|-------|------|--------|-------------|
| `query_original` | `str` | `""` | Raw user query. |
| `query_cleaned` | `str` | `""` | Cleaned text from cleanup step. |
| `must` | `SearchFiltersMust` | `SearchFiltersMust()` | Strict filters. |
| `should` | `SearchFiltersShould` | `SearchFiltersShould()` | Preference filters for rerank. |
| `exclude` | `SearchFiltersExclude` | `SearchFiltersExclude()` | Exclusions. |
| `search_phrases` | `list[str]` | `[]` | LLM-generated phrases (not used in current SQL; for reference). |
| `query_embedding_text` | `str` | `""` | Text sent to embedding API for vector search. |
| `confidence_score` | `float` | `0.0` | LLM confidence in extraction [0.0, 1.0]. |

**`from_llm_dict(data)`:** Normalizes a dict from the LLM: ensures `must`/`should`/`exclude` and nested `location`/`time` exist; uses helper `_list(d, key)` so missing keys become `[]`; sets floats and strings to safe defaults.

---

### Request and response (API)

#### `SearchRequest`

Body of `POST /search`.

| Field | Type | Default | Description |
|-------|------|--------|-------------|
| `query` | `str` | required | Natural-language search query. |
| `open_to_work_only` | `Optional[bool]` | `None` | Override parsed value; when True, only people with open_to_work. |
| `preferred_locations` | `Optional[list[str]]` | `None` | When open_to_work_only, filter by profile `work_preferred_locations` (any match). |
| `salary_min` | `Optional[Decimal]` | `None` | Recruiter min (₹/year); for display only. |
| `salary_max` | `Optional[Decimal]` | `None` | Recruiter offer budget (₹/year); overrides parsed `must.offer_salary_inr_per_year`; candidates matched where work_preferred_salary_min <= offer or NULL. |

#### `PersonSearchResult`

One person in the search result list.

| Field | Type | Default | Description |
|-------|------|--------|-------------|
| `id` | `str` | required | Person ID. |
| `name` | `Optional[str]` | `None` | Display name. |
| `headline` | `Optional[str]` | `None` | e.g. current_company / current_city. |
| `bio` | `Optional[str]` | `None` | Short bio (name, school, college). |
| `open_to_work` | `bool` | required | From PersonProfile. |
| `open_to_contact` | `bool` | required | From PersonProfile. |
| `work_preferred_locations` | `list[str]` | `[]` | From PersonProfile. |
| `work_preferred_salary_min` | `Optional[Decimal]` | `None` | Serialized as float in JSON. |
| `matched_cards` | `list[ExperienceCardResponse]` | `[]` | Up to 3 best-matching experience cards. |

#### `SearchResponse`

Response of `POST /search`.

| Field | Type | Description |
|-------|------|-------------|
| `search_id` | `str` | ID of the created Search; required for profile view and unlock. |
| `people` | `list[PersonSearchResult]` | Top people (up to 5). |

#### `PersonProfileResponse`

Full profile when viewing a person from search (`GET /people/{person_id}?search_id=...`).

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Person ID. |
| `display_name` | `Optional[str]` | Display name. |
| `open_to_work` | `bool` | From PersonProfile. |
| `open_to_contact` | `bool` | From PersonProfile. |
| `work_preferred_locations` | `list[str]` | Shown only when open_to_work. |
| `work_preferred_salary_min` | `Optional[Decimal]` | Min salary ₹/year; serialized as float; shown only when open_to_work. |
| `experience_cards` | `list[ExperienceCardResponse]` | All visible experience cards (kept for backward compatibility). |
| `card_families` | `list[CardFamilyResponse]` | Parent cards with children for full experience view. |
| `bio` | `Optional[BioResponse]` | Name, location, school, college, etc. |
| `contact` | `Optional[ContactDetailsResponse]` | Present only if searcher has unlocked contact for this person in this search. |

#### `UnlockContactRequest`

Body of `POST /people/{person_id}/unlock-contact`.

| Field | Type | Description |
|-------|------|-------------|
| `search_id` | `str` | Search that contained this person. |

#### `UnlockContactResponse`

| Field | Type | Description |
|-------|------|-------------|
| `unlocked` | `bool` | Always true on success. |
| `contact` | `ContactDetailsResponse` | email_visible, email (when visible), phone, linkedin_url, other from PersonProfile. |

**Note:** `ContactDetailsResponse` is in `src/schemas/contact.py`; `ExperienceCardResponse` and `CardFamilyResponse` in `src/schemas/builder.py`; `BioResponse` in `src/schemas/bio.py`. They are referenced here for completeness.

---

## Data Flow Summary

```
Client
  POST /search { query, open_to_work_only?, preferred_locations?, salary_max? }
  Optional: Idempotency-Key header
       ↓
Router (rate limit, auth)
       ↓
run_search
  → Idempotency check → return cached if key and stored response
  → Credit check (402 if balance < 1)
  → parse_search_filters(query) [cleanup → single extract]
  → ParsedConstraintsPayload.from_llm_dict(...)
  → embedding_text; request overrides (open_to_work_only, offer_salary_inr_per_year)
  → embed(embedding_text) → query_vec (normalized)
  → If no query_vec: create Search, deduct 1, return empty people
  → SQL: experience_cards + MUST/EXCLUDE + PersonProfile join when open_to_work or offer salary, order by distance, limit 50
  → SQL: experience_card_children min distance per person_id (same MUST/EXCLUDE on parent)
  → Group by person, add should bonus, merge parent + child score, sort, top 5
  → Downrank: by stated salary (if offer set), by date overlap (if time range set)
  → Create Search + SearchResult rows, deduct 1 credit
  → Load Person, PersonProfile; for child-only persons load up to 3 cards
  → Build PersonSearchResult list (matched_cards, headline, bio, …)
  → Optional: save idempotent response
  ← SearchResponse(search_id, people)
       ↓
Client
```

This document covers the search flow step-by-step and every major function in detail. For embedding indexing (how cards get their vectors), see `EXTRACTION_TO_EMBEDDING_PIPELINE.md`.
