# Search Flow Documentation (Code-Accurate)

This document reflects the current implementation in `apps/api` as of February 15, 2026.

## 1) Key Updates

- Search orchestration now lives in `apps/api/src/services/search_logic.py`; `apps/api/src/services/search.py` is a facade only.
- `TOP_PEOPLE` is now `6`.
- Search idempotency is replay-only (no reservation row, no explicit 409 "in progress" path).
- Empty search responses are still charged 1 credit.
- `similarity_percent` is derived from final blended ranking score (clamped to 0-100), not pure vector similarity.

## 2) Quick Navigation

| Area | File | Key Functions |
|---|---|---|
| Search routes | `apps/api/src/routers/search.py` | `search`, `get_person`, `unlock_contact`, `list_people`, `get_person_public_profile` |
| Search facade | `apps/api/src/services/search.py` | `SearchService.search/get_profile/unlock/list_people/get_public_profile` |
| Search pipeline | `apps/api/src/services/search_logic.py` | `run_search`, `_apply_card_filters`, `_collapse_and_rank_persons`, `_generate_llm_why_matched` |
| Profile view flows | `apps/api/src/services/search_profile_view.py` | `get_person_profile`, `list_people_for_discover`, `get_public_profile_impl` |
| Unlock flow | `apps/api/src/services/search_contact_unlock.py` | `unlock_contact` |
| Chat parsing | `apps/api/src/providers/chat.py` | `parse_search_filters`, `_chat_json`, `_chat` |
| Filter normalization | `apps/api/src/services/filter_validator.py` | `validate_and_normalize` |
| Schemas | `apps/api/src/schemas/search.py` | `SearchRequest`, `ParsedConstraintsPayload`, `SearchResponse` |
| Credits + idempotency | `apps/api/src/services/credits.py` | `get_balance`, `deduct_credits`, `get_idempotent_response`, `save_idempotent_response` |
| Models | `apps/api/src/db/models.py` | `Search`, `SearchResult`, `IdempotencyKey`, `UnlockContact`, `PersonProfile` |
| Frontend result card | `apps/web/src/components/search/person-result-card.tsx` | consumes `similarity_percent`, `why_matched`, `matched_cards` |

## 3) API Surface

### 3.1 `POST /search`

- Auth: required
- Rate limit: `search_rate_limit` (default `10/minute`)
- Optional header: `Idempotency-Key`
- Request: `SearchRequest`
- Response: `SearchResponse`

### 3.2 Related endpoints

- `GET /people/{person_id}?search_id=...`
  - search-session-gated profile view
- `POST /people/{person_id}/unlock-contact`
  - unlock contact for a person within a valid search session
- `GET /people`
  - discover list (people with at least one visible parent card)
- `GET /people/{person_id}/profile`
  - public-profile style response (still auth-protected by router)

## 4) End-to-End `run_search`

File: `apps/api/src/services/search_logic.py`

Execution order:

1. Optional idempotency replay check
2. Credit pre-check (`balance >= 1`)
3. Parse query via LLM and deterministic normalize/validate
4. Resolve request overrides (`open_to_work_only`, `salary_max`)
5. Embed query text
6. If embedding is empty: create empty search response (charged)
7. Build lexical query and lexical bonus map
8. Build normalized constraint term context
9. Fetch vector candidates with fallback tiers
10. Collapse card-level results to person-level blended scores
11. Keep top `TOP_PEOPLE` (`6`)
12. If empty ranked list: create empty search response (charged)
13. Load people/profiles/child evidence objects
14. Apply post-rank tiebreak sorting
15. Create `Search` row and deduct 1 credit
16. Prepare pending `SearchResult` rows and LLM evidence payload
17. Generate `why_matched` via one batched LLM call (fallback to deterministic bullets)
18. Insert `SearchResult` rows
19. Fill child-only matched-card display fallback
20. Build API response payload
21. Persist idempotency response payload when key exists

### 4.1 Idempotency behavior (`POST /search`)

Current behavior is replay-only:

- On request start, code checks `idempotency_keys` for `(key, person_id, endpoint)`.
- If a row exists and has `response_body`, response is returned immediately.
- There is no "reservation" write before work starts.
- There is no explicit "request in progress" response path.

Implementation note:
- `save_idempotent_response(...)` inserts a new row at the end of successful processing.
- Because rows are inserted, not updated, concurrent same-key first requests can race on unique index `(key, person_id, endpoint)`.

### 4.2 Parse and normalize

- Parser call: `chat.parse_search_filters(body.query)`
- On `ChatServiceError`, fallback payload is built from raw query:
  - `query_original`, `query_cleaned`, `query_embedding_text`
- Parsed payload is normalized by `validate_and_normalize(...)`

Normalization includes:
- dedupe and cleanup of lists/tokens
- enum validation for `intent_primary`
- MUST caps and demotions to SHOULD (recall protection)
- confidence-based demotion for weaker constraints
- date normalization (`YYYY-MM-DD`, `YYYY-MM`, `YYYY` accepted)
- date swap if start > end
- salary normalization to INR/year

### 4.3 Request overrides

- `open_to_work_only`:
  - use `body.open_to_work_only` when provided
  - else use parsed `must.open_to_work_only`
- offer salary (`offer_salary_inr_per_year`):
  - use `body.salary_max` when provided
  - else use parsed `must.offer_salary_inr_per_year`

`salary_min`:
- validated in schema (`salary_min <= salary_max`)
- not used in SQL filtering or ranking

### 4.4 Embedding and empty-vector path

- Embedding text priority:
  1. `payload.query_embedding_text`
  2. `payload.query_original`
  3. `body.query`
- Embedding provider failures raise `HTTP 503`.
- If embedded vector list is empty after normalization, `_create_empty_search_response(...)` is used.

Important:
- `_create_empty_search_response(...)` creates a `Search` row, deducts 1 credit, and returns `people=[]`.

### 4.5 Lexical bonus map

`_lexical_candidates(...)`:

- Runs Postgres FTS (`plainto_tsquery`) on:
  - `experience_cards.search_document` (visible parents)
  - `experience_card_children.search_document` joined to visible parents
- Query text built from:
  - all `search_phrases`
  - up to first 5 SHOULD keywords
  - fallback to cleaned/raw query (trimmed to 200 chars)
- Per-person lexical score is normalized and capped to `[0, LEXICAL_BONUS_MAX]`.
- On failure, lexical bonus is skipped.

### 4.6 Candidate retrieval with fallback tiers

The search loop increases fallback tier until either:

- unique matched people >= `MIN_RESULTS` (`15`), or
- tier reaches `FALLBACK_TIER_COMPANY_TEAM_SOFT` (`3`)

Per tier, three queries run:

1. Parent candidates (`ExperienceCard.embedding.cosine_distance(query_vec)`), `limit OVERFETCH_CARDS`
2. Child best distance per person (`min(...)`)
3. Child evidence rows with `row_number` window; keep top `MATCHED_CARDS_PER_PERSON` (`3`) per person

### 4.7 `_apply_card_filters` semantics

Always-applied when present:
- `intent_primary`, `domain`, `sub_domain`, `employment_type`, `seniority_level`, `is_current`

Tier-controlled:
- `company_norm`, `team_norm` -> only when `apply_company_team`
- location (`city`, `country`, `location_text`) -> only when `apply_location`
- time overlap -> only when `apply_time`

Time filter details:
- only applied when both `time_start` and `time_end` are present
- requires card has at least one date bound (`start_date` or `end_date`)
- overlap logic allows null on one side but still requires overlap against query window

Exclude filters (never relaxed by tier logic):
- `NOT company_norm IN (...)`
- `NOT search_phrases && exclude_keywords`

PersonProfile join:
- applied only when `open_to_work_only` or salary offer filter exists
- `open_to_work_only` enforces `PersonProfile.open_to_work = true`
- optional preferred location overlap uses `PersonProfile.work_preferred_locations`
- salary offer filter keeps rows where:
  - `work_preferred_salary_min IS NULL`, or
  - `work_preferred_salary_min <= offer_salary_inr_per_year`

### 4.8 Tier relaxation policy

- Tier 0: strict (company/team + location + time all active)
- Tier 1: time relaxed
- Tier 2: time + location relaxed
- Tier 3: time + location + company/team relaxed

Not tier-relaxed:
- `intent_primary`, `domain`, `sub_domain`, `employment_type`, `seniority_level`, `is_current`, exclude filters

### 4.9 Person scoring and ranking

Core similarity transform:
- `sim = 1 / (1 + distance)`

Per-person blended score:
- `base = 0.65*parent_best + 0.25*child_best + 0.10*avg_top3`
- `final = max(0, base + lexical_bonus + should_bonus - penalties)`

Where:
- SHOULD boosts are applied in two places:
  - card-level: `sim + should_hits * SHOULD_BOOST`
  - person-level aggregate: `min(total_should_hits * SHOULD_BOOST, SHOULD_BONUS_MAX)`
- penalties are tier-aware:
  - missing date penalty when query has time and time got relaxed
  - location mismatch penalty when query has location and location got relaxed

### 4.10 Post-rank tiebreakers

After initial ranking, optional deterministic sorts run:

- salary-aware sort if offer salary exists:
  - key: `(-score, has_stated_salary_min_first)`
- date-overlap-aware sort if query has full time range:
  - key: `(-score, has_full_date_overlap_first)`

### 4.11 Similarity and explainability

`similarity_percent`:
- computed by `_score_to_similarity_percent(score)`
- clamps final blended score to `[0,1]`, then maps to `0-100`

`why_matched` pipeline:
- deterministic fallback bullets are generated first (up to 6 lines)
- one batched LLM call attempts higher-quality reasons
- LLM reasons are sanitized:
  - max 3 lines per person
  - dedupe
  - compacted and length-bounded
- if LLM fails or output is unusable, fallback bullets are used

### 4.12 Persistence order

On non-empty ranked results:

1. Insert `Search` (`query_text`, parsed filters, `extra.fallback_tier`, `expires_at`)
2. Deduct 1 credit (`reason="search"`, `reference_type="search_id"`)
3. Insert `SearchResult` rows with:
  - `rank`, rounded `score`
  - `extra.matched_parent_ids`, `extra.matched_child_ids`, `extra.why_matched`
4. Save idempotency response row if key provided

On empty results (`_create_empty_search_response`):

1. Insert `Search`
2. Deduct 1 credit
3. Return `SearchResponse(search_id=..., people=[])`
4. Save idempotency response row if key provided

Transaction semantics:
- `get_db()` commits once at request end and rolls back on exception.
- `run_search` itself does not start explicit nested transactions.

## 5) Session Validation and Expiry

Used by profile/unlock flows (`_validate_search_session`):

- search must exist and belong to caller
- search must not be expired
- when `person_id` supplied, person must be present in `search_results`

Expiry logic (`_search_expired`):
- primary: `search.expires_at < now_utc`
- fallback: `created_at + SEARCH_RESULT_EXPIRY_HOURS`

Default expiry window:
- `SEARCH_RESULT_EXPIRY_HOURS = 24`

## 6) Related Endpoint Flows

### 6.1 `GET /people/{person_id}?search_id=...`

`get_person_profile(...)`:

- requires `search_id`
- validates search session and person membership
- loads person/profile/visible parent cards/unlock row in parallel
- contact returned only if:
  - person is open (`open_to_work` or `open_to_contact`), and
  - searcher has unlocked this person for this search
- `work_preferred_locations` and `work_preferred_salary_min` are shown only when target is `open_to_work`
- returns both legacy `experience_cards` and structured `card_families`, plus `bio`

### 6.2 `POST /people/{person_id}/unlock-contact`

`unlock_contact(...)`:

- endpoint-scoped idempotency key: `POST /people/{person_id}/unlock-contact`
- idempotency replay check at start (same replay-only behavior)
- validates search session + person membership
- rejects target if neither `open_to_work` nor `open_to_contact` (`403`)
- if already unlocked for `(searcher, target, search_id)`, returns success without charge
- otherwise:
  - pre-check credits
  - create `UnlockContact`
  - deduct 1 credit (`reason="unlock_contact"`)
- saves idempotency response only when this request reaches the save call

### 6.3 `GET /people`

`list_people_for_discover(...)`:

- includes only people with at least one visible parent card
- returns:
  - `id`, `display_name`
  - `current_location` from `PersonProfile.current_city`
  - up to 5 latest non-empty parent `summary` values

### 6.4 `GET /people/{person_id}/profile`

`get_public_profile_impl(...)`:

- router currently requires auth
- no search session required
- returns `id`, `display_name`, `bio`, `card_families`

## 7) Active Prompting

Active in current search runtime:

- cleanup: `PROMPT_SEARCH_CLEANUP`
- extraction: `PROMPT_SEARCH_SINGLE_EXTRACT`
- explainability: `get_why_matched_prompt`

Present in prompt file but not used in current runtime path:

- `PROMPT_SEARCH_EXTRACT_FILTERS`
- `PROMPT_SEARCH_VALIDATE_FILTERS`

## 8) Schema Snapshots

### 8.1 `SearchRequest`

```json
{
  "query": "string",
  "open_to_work_only": "boolean|null",
  "preferred_locations": ["string"],
  "salary_min": "number|null",
  "salary_max": "number|null"
}
```

Validation:
- if both `salary_min` and `salary_max` exist, `salary_min <= salary_max`

### 8.2 Parsed constraints (`ParsedConstraintsPayload`)

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

### 8.3 `SearchResponse`

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

### 8.4 Persisted metadata

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

## 9) Constants (Current)

Source: `apps/api/src/services/search_logic.py`

```text
OVERFETCH_CARDS = 50
TOP_PEOPLE = 6
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

## 10) Failure and Degradation Behavior

- Parse failure (`ChatServiceError`): fallback to raw-query payload
- Explainability LLM failure: deterministic `why_matched` bullets
- Lexical failure: continue without lexical bonus
- Embedding provider/config failure: `HTTP 503`
- Low credits at pre-check or debit point: `HTTP 402`
- Idempotency replay works only when completed response row already exists

## 11) Maintenance Checklist

When search behavior changes, update this doc with code:

1. `run_search` execution order and credit charging points
2. `_apply_card_filters` semantics and fallback tiers
3. ranking formula/constants and `TOP_PEOPLE`
4. `similarity_percent` mapping semantics
5. explainability prompt/schema/sanitization behavior
6. idempotency behavior in `search_logic` and `search_contact_unlock`
7. request/response schema changes in `src/schemas/search.py`
8. frontend result rendering assumptions in `apps/web/src/components/search/person-result-card.tsx`
