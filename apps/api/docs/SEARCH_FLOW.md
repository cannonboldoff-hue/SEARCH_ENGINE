# Search Flow Documentation (Code-Accurate)

This document describes the current implementation in `apps/api` as of February 15, 2026.

Scope:
- `POST /search` end-to-end pipeline
- ranking, fallback, and explainability behavior
- persistence and credit charging rules
- related endpoints: profile view, unlock contact, discover, public profile

## 1) Quick Navigation

| Area | File | Key functions |
|---|---|---|
| Search routes | `apps/api/src/routers/search.py` | `search`, `get_person`, `unlock_contact`, `list_people`, `get_person_public_profile` |
| Search service | `apps/api/src/services/search.py` | `run_search`, `_apply_card_filters`, `_collapse_and_rank_persons`, `_generate_llm_why_matched` |
| Chat parsing | `apps/api/src/providers/chat.py` | `parse_search_filters`, `_chat_json`, `_chat` |
| Filter post-processing | `apps/api/src/services/filter_validator.py` | `validate_and_normalize` |
| Search prompts | `apps/api/src/prompts/search_filters.py` | `PROMPT_SEARCH_CLEANUP`, `PROMPT_SEARCH_SINGLE_EXTRACT` |
| Explainability prompt | `apps/api/src/prompts/search_why_matched.py` | `get_why_matched_prompt` |
| Schemas | `apps/api/src/schemas/search.py` | `SearchRequest`, `ParsedConstraintsPayload`, `SearchResponse` |
| DB models | `apps/api/src/db/models.py` | `Search`, `SearchResult`, `IdempotencyKey`, `UnlockContact`, `PersonProfile` |
| Credits + idempotency helpers | `apps/api/src/services/credits.py` | `get_balance`, `deduct_credits`, `get_idempotent_response`, `save_idempotent_response` |
| Constants/config | `apps/api/src/core/constants.py`, `apps/api/src/core/config.py` | `SEARCH_RESULT_EXPIRY_HOURS`, rate limits, model config |
| Frontend consumption | `apps/web/src/components/search/person-result-card.tsx` | `why_matched` display + fallback text |

## 2) API Surface

### 2.1 `POST /search`

- Route: `POST /search`
- Auth: required (`current_user` dependency)
- Rate limit: `search_rate_limit` (default `10/minute`)
- Optional header: `Idempotency-Key`
- Body: `SearchRequest`
- Response: `SearchResponse`

### 2.2 Related endpoints

- `GET /people/{person_id}?search_id=...`
  - search-session-gated profile for a person in that search result set
- `POST /people/{person_id}/unlock-contact`
  - unlocks contact details for a person in that search session
- `GET /people`
  - discover list (people with at least one visible parent card)
- `GET /people/{person_id}/profile`
  - public-profile style data (bio + card families), no search session needed

## 3) End-to-End: `run_search`

File: `apps/api/src/services/search.py`

High-level sequence:

1. Reserve/read idempotency key
2. Balance pre-check
3. Parse query into constraints (LLM) with deterministic fallback
4. Normalize constraints
5. Apply request-level overrides
6. Embed query text
7. Build lexical bonus map
8. Retrieve vector candidates with fallback tiers
9. Collapse card-level matches to person-level scores
10. Rerank ties (salary/date preference)
11. Build explainability (`why_matched`)
12. Build response list
13. Persist search + results + idempotency response + debit credit

### 3.1 Step 0: Idempotency reservation (`_reserve_idempotency_key_or_return`)

Behavior when `Idempotency-Key` is provided:

- If session currently has an open transaction, commit first.
- Insert `IdempotencyKey(key, person_id, endpoint, response_status=None, response_body=None)` inside its own transaction.
- If insert hits unique constraint (`IntegrityError`):
  - Load existing row via `get_idempotent_response(...)`.
  - If `response_body` is already stored, return it immediately as `SearchResponse`.
  - If row exists but response is not yet written, return `409 Request in progress`.

If no key is provided, search proceeds normally with no idempotency short-circuit.

### 3.2 Step 1: Credit pre-check

- `balance = await get_balance(db, searcher_id)`
- If `balance < 1`, throw `HTTP 402 Insufficient credits`.

Note: this is a pre-check only. Actual debit is done later during persistence.

### 3.3 Step 2: Parse query with chat provider

- Provider: `chat = get_chat_provider()`
- Parse: `filters_raw = await chat.parse_search_filters(body.query)`

`parse_search_filters` runs:

1. `PROMPT_SEARCH_CLEANUP` (plain text cleanup)
2. `PROMPT_SEARCH_SINGLE_EXTRACT` (strict JSON schema extraction)

If parser fails (`ChatServiceError`), the service falls back to:

```json
{
  "query_original": "<raw query>",
  "query_cleaned": "<raw query>",
  "query_embedding_text": "<raw query>"
}
```

Search still continues.

### 3.4 Step 3: Deterministic normalize/validate

- `payload = ParsedConstraintsPayload.from_llm_dict(filters_raw)`
- `payload = validate_and_normalize(payload)`
- `filters_dict = payload.model_dump(mode="json")`

`validate_and_normalize` currently enforces:

- list dedupe and token cleanup
- valid `intent_primary` only (must be in `Intent` enum)
- recall protection demotions from MUST to SHOULD:
  - cap MUST counts (intent/company/team/domain)
  - push overflow into SHOULD (`intent_secondary` or `keywords`)
- low-confidence handling:
  - if `confidence_score < 0.5`, demote `sub_domain` and extra `domain` into SHOULD keywords
- date normalization to `YYYY-MM-DD` (accepts `YYYY-MM-DD`, `YYYY-MM`, `YYYY`)
- date swap if start > end
- salary normalization to INR/year
  - heuristic: values under `200000` treated as monthly and multiplied by 12
- exclude + search phrase dedupe/normalization

Validation pseudocode (date parsing + bounds checking):

```python
MIN_YEAR = 1900
MAX_YEAR = utc_today().year + 1

def parse_date_ymd(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()
    if matches(s, r"^\d{4}-\d{2}-\d{2}$"):
        d = date_from_format(s, "%Y-%m-%d")
    elif matches(s, r"^\d{4}-\d{2}$"):
        d = date_from_format(s, "%Y-%m")      # normalize to first day of month
    elif matches(s, r"^\d{4}$"):
        d = date(int(s), 1, 1)                # normalize to Jan 1
    else:
        raise ValidationError("Invalid date format")
    if d.year < MIN_YEAR or d.year > MAX_YEAR:
        raise ValidationError("Date out of bounds")
    return d

time_start = parse_date_ymd(must.time_start)
time_end = parse_date_ymd(must.time_end)
if time_start and time_end and time_start > time_end:
    time_start, time_end = time_end, time_start
```

Code note:
- Current code enforces format parse + start/end swap.
- Explicit year bounds are a recommended hardening check (not currently enforced in code).

### 3.5 Step 4: Request-body overrides

- `open_to_work_only`:
  - uses `body.open_to_work_only` if provided
  - otherwise uses parsed `must.open_to_work_only` (default false)
- `offer_salary_inr_per_year`:
  - uses `body.salary_max` first (assumed INR/year)
  - else uses parsed `must.offer_salary_inr_per_year`

Important:
- `salary_min` from `SearchRequest` is not used in SQL filtering/ranking in this flow.

Validation pseudocode (salary range `min <= max`):

```python
if body.salary_min is not None and body.salary_max is not None:
    if body.salary_min > body.salary_max:
        raise HTTPException(422, detail="salary_min must be <= salary_max")
```

Code note:
- `salary_max` is used as `offer_salary_inr_per_year` when present.
- `salary_min` is currently accepted but not used in retrieval/ranking SQL.

### 3.6 Step 5: Embed query text

Embedding text priority:

1. `payload.query_embedding_text`
2. `payload.query_original`
3. `body.query`

Execution:

- `embed_provider = get_embedding_provider()`
- `vecs = await embed_provider.embed([embedding_text])`
- `query_vec = normalize_embedding(vecs[0], embed_provider.dimension)`

Failure handling:

- Embedding provider/config/runtime failure -> `HTTP 503`.
- Empty normalized vector -> `_create_empty_search_response(...)`.

`_create_empty_search_response` behavior:

- creates `Search` row (with parsed filters + expiry)
- writes idempotency response if key was provided
- returns `SearchResponse(search_id=..., people=[])`
- does not deduct credits

### 3.7 Step 6: Lexical bonus map (`_lexical_candidates`)

Builds a text query (`query_ts`) from:

- all `payload.search_phrases`
- up to first 5 `payload.should.keywords`
- fallback to cleaned/raw query (trimmed to 200 chars) if needed

FTS queries:

- parents: `experience_cards.search_document` (visible cards only)
- children: `experience_card_children.search_document` joined to visible parent cards

Scoring:

- per source uses `ts_rank_cd(...)`
- per person keeps max rank observed
- normalize by global max rank
- map to bonus in `[0, LEXICAL_BONUS_MAX]`

If lexical query fails, search continues without lexical bonus.

### 3.8 Step 7: Candidate retrieval + fallback tiers

The service loops from `fallback_tier = 0` until:

- unique matched people >= `MIN_RESULTS` (`15`), or
- tier reaches `FALLBACK_TIER_COMPANY_TEAM_SOFT` (`3`)

Per iteration it runs three queries:

1. Parent vector candidates
  - `ExperienceCard.embedding.cosine_distance(query_vec)` as `dist`
  - visible + embedding not null
  - ordered by distance, limited by `OVERFETCH_CARDS` (`50`)
2. Child min-distance per person
  - min child distance grouped by child person
3. Child evidence rows
  - row_number window per person ordered by child distance
  - keeps top `MATCHED_CARDS_PER_PERSON` (`3`) child rows per person

All three queries reuse `_apply_card_filters(...)`.

### 3.9 Filter semantics (`_apply_card_filters`)

Always-eligible fields when present:

- `intent_primary`, `domain`, `sub_domain`, `employment_type`, `seniority_level`, `is_current`

Tier-dependent fields:

- company/team filters only when `apply_company_team == True`
- location filters only when `apply_location == True`
- time overlap filters only when `apply_time == True`

Location filter:

- if any of `city`, `country`, `location_text` is set:
  - OR-combined `ExperienceCard.location ILIKE '%term%'`

Location normalization details:

- Current behavior:
  - case-insensitive substring match via `ILIKE`
  - no accent/diacritic normalization
  - no fuzzy threshold (exact substring only)
- If accent-insensitive matching is enabled (recommended):
  - normalize both query/card strings with Unicode NFKD + diacritic strip, or DB-side `unaccent(lower(...))`
- If fuzzy matching is enabled (optional):
  - use trigram/phonetic similarity in addition to substring
  - recommended threshold: `similarity >= 0.35`

Time filter:

- requires at least one card date bound (`start_date` or `end_date`)
- overlap logic with nullable bounds:
  - if query has `time_end`: card start must be null or <= query end
  - if query has `time_start`: card end must be null or >= query start

Exclude filter (never relaxed):

- company exclusion: `NOT company_norm IN (...)`
- keyword exclusion: `NOT search_phrases && exclude_keywords`

PersonProfile join is added only when needed:

- if `open_to_work_only` OR salary filter exists:
  - join `PersonProfile` on `ExperienceCard.person_id == PersonProfile.person_id`

Join-side constraints:

- if `open_to_work_only == True`:
  - `PersonProfile.open_to_work == True`
  - if request has `preferred_locations`, require overlap with `PersonProfile.work_preferred_locations`
- if salary filter exists:
  - keep rows where `work_preferred_salary_min IS NULL` OR `<= offer_salary_inr_per_year`

### 3.10 Tier relaxation policy

- Tier 0 (`strict`): apply company/team + time + location
- Tier 1 (`time soft`): drop time filter
- Tier 2 (`location soft`): drop time + location filters
- Tier 3 (`company/team soft`): drop time + location + company/team filters

Intent/domain/employment/seniority/exclude are not tier-relaxed by this mechanism.

### 3.11 Step 8: Collapse and score persons (`_collapse_and_rank_persons`)

Similarity conversion:

- `sim = 1 / (1 + distance)`

Validation pseudocode (distance/similarity NaN/inf handling):

```python
import math

def safe_distance(raw_dist: object) -> float:
    if raw_dist is None:
        return 1.0
    try:
        d = float(raw_dist)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(d):
        return 1.0
    return max(0.0, d)

def safe_similarity(raw_dist: object) -> float:
    d = safe_distance(raw_dist)
    sim = 1.0 / (1.0 + d)
    return sim if math.isfinite(sim) else 0.0
```

Code note:
- Current code handles `None` distances.
- Explicit `NaN`/`inf` guards are a recommended hardening step.

Inputs used:

- parent rows with distance
- child rows (best distance per person)
- child evidence rows
- lexical bonus map
- parsed SHOULD signals
- fallback tier + query_has_time/query_has_location

Scoring components per person:

- `parent_best`
- `child_best`
- `avg_top3` across top similarities from parent+child evidence
- `lex_bonus` from lexical map
- SHOULD bonus (two places):
  - card-level boost is added into each parent sim before aggregation
  - person-level aggregate bonus from summed should-hits, capped at `SHOULD_BONUS_MAX`
- penalties (tier-aware):
  - missing-date penalty when query has time and tier has relaxed time
  - location-mismatch penalty when query has location and tier has relaxed location

Formula:

- `base = 0.65*parent_best + 0.25*child_best + 0.10*avg_top3`
- `final = max(0, base + lex_bonus + should_bonus - penalties)`

Output:

- parent cards with per-card score by person
- child best similarity by person
- child evidence tuples by person
- ordered best parent ids inferred from child evidence
- sorted person list `(person_id, final_score desc)`

Then `top_20 = person_best[:TOP_PEOPLE]` where `TOP_PEOPLE = 5`.

### 3.12 Step 9: Post-rank reordering (tie-aware keys)

After loading `Person` + `PersonProfile` for top candidates:

- If salary filter is active:
  - sorting key: `(-score, has_stated_salary_min_first)`
- If query has explicit time bounds:
  - sorting key: `(-score, has_date_overlap_first)`

`-score` remains first key, so score ordering is preserved.

Tie-breaking epsilon definition:

- Recommended absolute epsilon: `SCORE_EPSILON_ABS = 1e-6`
- Treat two scores as equal when `abs(score_a - score_b) <= SCORE_EPSILON_ABS`
- Apply secondary keys (salary/date) only within those equal-score groups

Code note:
- Current implementation uses exact float ordering (`-score`) with no explicit epsilon bucket.

### 3.13 Step 10: Build matched IDs, explainability, and UI similarity

For each ranked person:

- decide `matched_parent_ids` (favor parent inferred from best child evidence when present)
- collect top `matched_child_ids`
- build deterministic fallback bullets from parent/child `search_phrases` and snippets
- build compact LLM evidence payload via `_build_person_why_evidence`
- compute `similarity_percent` from pure semantic similarity only (`_semantic_similarity_by_person`)

Important:

- UI similarity is based on vector similarity only.
- Final ranking score includes lexical/should/penalty adjustments.

### 3.14 Step 11: LLM explainability (`_generate_llm_why_matched`)

Single batched LLM call for all top people:

- prompt: `get_why_matched_prompt(...)`
- call: `chat.chat(prompt, max_tokens=1200, temperature=0.1)`
- expected JSON:

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

Sanitization:

- max 3 lines/person
- case-insensitive dedupe
- trim + normalize whitespace
- max 120 chars/line

Fallback behavior:

- if LLM call or parse fails, deterministic bullets are used.

Failure modes (explicit):

- Timeout / network / provider HTTP errors:
  - surfaced as `ChatServiceError` from chat provider
  - behavior: deterministic fallback bullets
  - log expectation: warning with error class and provider status if available
- Invalid JSON:
  - `json.loads(...)` failure after fence stripping
  - behavior: deterministic fallback bullets
  - log expectation: warning with parse error type
- Sanitization failure (schema-like but unusable lines):
  - response JSON may parse, but all lines may be dropped by sanitization (empty/dup/too noisy)
  - behavior: per-person fallback to deterministic bullets where sanitized output is empty
  - log/metrics expectation: counter for sanitized-empty persons

Metrics/logging expectations (recommended):

- Counters:
  - `search.llm.parse.timeout_or_http_error`
  - `search.llm.parse.invalid_json`
  - `search.llm.why.timeout_or_http_error`
  - `search.llm.why.invalid_json`
  - `search.llm.why.sanitized_empty_person`
- Include tags: `endpoint`, `model`, `provider`, `fallback_used`.

### 3.15 Step 12: Child-only matched card handling

If a person is ranked via child embeddings but has no parent card in `person_cards`:

- try to load parent cards inferred from child evidence (ordered, up to 3)
- if still none, fallback to latest visible parent cards for that person

This guarantees stable `matched_cards` output where possible.

### 3.16 Step 13: Build response list (`_build_search_people_list`)

For each top person:

- `id`, `name`, `headline`, `bio`
- `similarity_percent`
- `why_matched`
- `open_to_work`, `open_to_contact`
- `work_preferred_locations`, `work_preferred_salary_min`
- up to 3 `matched_cards`

Response:

- `SearchResponse(search_id=<search_rec.id>, people=[...])`

### 3.17 Step 14: Persist search, debit credits, write idempotency response

Persistence transaction:

1. Create `Search`:
  - `query_text = body.query`
  - `parsed_constraints_json = filters_dict`
  - `filters = filters_dict`
  - `extra = {"fallback_tier": fallback_tier}`
  - `expires_at = now + SEARCH_RESULT_EXPIRY_HOURS`
2. Debit 1 credit:
  - `deduct_credits(..., reason="search", reference_type="search_id", reference_id=search_rec.id)`
3. Insert one `SearchResult` per ranked person:
  - `rank`, rounded `score`, and `extra` (`matched_parent_ids`, `matched_child_ids`, `why_matched`)
4. Update reserved idempotency row with final HTTP 200 response payload.

If credit debit fails at this stage, request fails with `402`.

Credit rule summary:

- charged only when non-empty ranked results reach this persistence stage
- not charged for empty-vector path or empty-result path that returns through `_create_empty_search_response`

Transaction semantics clarification:

- Credit deduction happens in this persistence transaction (post-fetch/post-rank), not at Step 1.
- Step 1 is a pre-check only (`get_balance`) and does not lock or deduct.
- Credit deduction does not happen in Step 10 (`Build matched IDs...`); it happens here in Step 14.
- If concurrent spend reduces balance between Step 1 and Step 14, `deduct_credits(...)` returns false and this transaction fails with `402`.

Rollback behavior:

- Any exception inside Step 14 transaction rolls back all writes in that block:
  - `Search` insert
  - credit debit + ledger write
  - all `SearchResult` inserts
  - idempotency response update
- If a reserved idempotency key exists and the request fails, `run_search(...)` calls `_release_idempotency_key_on_failure(...)` to delete unfinished reservation rows (`response_body IS NULL`) so retries can proceed.

## 4) Session Validation and Expiry

Used by profile/unlock flows (`_validate_search_session`):

- `search_id` must exist and belong to caller
- search must not be expired
- optional `person_id` must exist in `SearchResult` for that `search_id`

Expiry check (`_search_expired`):

- primary: compare `search.expires_at` with current UTC time
- fallback (legacy safety): compare `created_at` with `SEARCH_RESULT_EXPIRY_HOURS`

Default expiry window:

- `SEARCH_RESULT_EXPIRY_HOURS = 24`

## 5) Related Endpoint Flows

### 5.1 `GET /people/{person_id}?search_id=...`

Function: `get_person_profile(...)`

- rejects missing `search_id` with `400`
- validates search session + membership
- loads person/profile/visible cards/unlock row in parallel
- contact visibility:
  - returned only when target is open (`open_to_work` or `open_to_contact`)
  - and requester has unlocked contact for that search
- salary/location visibility:
  - returned only when target is `open_to_work`
  - otherwise returns masked values (`[]`, `null`)
- returns both legacy `experience_cards` and structured `card_families`, plus `bio`

### 5.2 `POST /people/{person_id}/unlock-contact`

Function: `unlock_contact(...)`

- endpoint-specific idempotency key namespace:
  - `POST /people/{person_id}/unlock-contact`
- validates search session + person membership
- rejects target if neither `open_to_work` nor `open_to_contact` (`403`)
- if already unlocked for `(searcher, target, search_id)`, returns success without charging
- else:
  - pre-check balance
  - create `UnlockContact` row
  - deduct 1 credit (`reason="unlock_contact"`)
- stores idempotent response payload if idempotency key was provided

### 5.3 `GET /people`

Function: `list_people_for_discover(...)`

- includes people with at least one visible parent card
- returns:
  - `id`, `display_name`
  - `current_location` from `PersonProfile.current_city`
  - up to 5 latest non-empty parent `summary` values

### 5.4 `GET /people/{person_id}/profile`

Function: `get_public_profile_impl(...)`

- auth is currently required by router dependency
- no `search_id` session check
- returns public-profile style payload:
  - `id`, `display_name`, `bio`, `card_families`

## 6) Active Prompting in Search

Active in runtime search path:

- cleanup prompt: `PROMPT_SEARCH_CLEANUP`
- single extract prompt: `PROMPT_SEARCH_SINGLE_EXTRACT`
- explainability prompt: `get_why_matched_prompt`

Present but not used in current `parse_search_filters` runtime path:

- `PROMPT_SEARCH_EXTRACT_FILTERS`
- `PROMPT_SEARCH_VALIDATE_FILTERS`

## 7) Schema Snapshots

### 7.1 `SearchRequest`

```json
{
  "query": "string",
  "open_to_work_only": "boolean|null",
  "preferred_locations": ["string"],
  "salary_min": "number|null",
  "salary_max": "number|null"
}
```

### 7.2 Parsed constraints (`ParsedConstraintsPayload`)

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

### 7.3 `SearchResponse`

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
      "open_to_work": "boolean",
      "open_to_contact": "boolean",
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

## 8) Constants (Ranking/Fallback)

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

## 9) Failure and Degradation Behavior

- Chat parse failure:
  - search continues with raw-query fallback constraints
- Chat parse timeout/network/provider HTTP failure:
  - captured as `ChatServiceError` and handled via raw-query fallback
- Chat parse invalid JSON:
  - captured as `ChatServiceError` and handled via raw-query fallback
- Explainability LLM failure:
  - deterministic `why_matched` fallback is used
- Explainability sanitization-empty case:
  - person-level fallback to deterministic bullets when sanitized LLM lines are empty
- Lexical search failure:
  - search continues without lexical bonus
- Embedding failure/config issue:
  - request fails with `503`
- Idempotency in-progress collision:
  - returns `409 Request in progress` for same `(key, person, endpoint)` when reserved row has no final response yet

Operational observability expectations:

- Warnings should be emitted for parse failures, explainability call failures, JSON parse failures, and lexical failures.
- Metrics should distinguish timeout/network, HTTP error, invalid JSON, and sanitization-empty outputs.
- Fallback-path counters should be monitored to detect silent quality regressions.

## 10) Known Limitations

- Why only top 5 people:
  - `TOP_PEOPLE = 5` is a latency + payload-size tradeoff.
  - It bounds DB/profile hydration, explainability prompt size, and response rendering cost.
  - This may hide near-threshold candidates when many scores are close.
- Why some MUST constraints cannot be relaxed:
  - Tier relaxation only softens time, location, and company/team.
  - Other MUST constraints (`intent_primary`, `domain`, `sub_domain`, `employment_type`, `seniority_level`) and all EXCLUDE constraints are intentionally not relaxed to avoid semantic drift and unsafe recall expansion.
- Why `salary_min` is not used in filtering:
  - Current retrieval applies only one-sided offer gating (`candidate.work_preferred_salary_min <= offer_salary_inr_per_year`).
  - Recruiter `salary_min` has ambiguous retrieval semantics in this model and can remove valid candidates prematurely.
  - `salary_min` is currently retained for request compatibility and potential future ranking features.

## 11) Maintenance Checklist

When updating search, verify and update this doc with code:

1. `run_search` step order and transaction boundaries.
2. `_apply_card_filters` semantics and fallback tier effects.
3. Ranking formula and constants.
4. `similarity_percent` mapping versus ranking score semantics.
5. Explainability schema/prompt/sanitization path.
6. Credit charging points and idempotency behavior.
7. `SearchRequest` and `SearchResponse` schema changes.
8. Frontend usage in `apps/web/src/components/search/person-result-card.tsx`.
