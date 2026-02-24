# Search Flow Documentation (Code-Accurate, AI-Readable)

This document reflects the current implementation in `apps/api` and is intended for both humans and AI agents. Every section is precise and traceable to source code.

**Last updated:** February 2026.

---

## 1) Key Facts (Summary)

- **Search orchestration:** `apps/api/src/services/search/search_logic.py` contains the full pipeline. `apps/api/src/services/search/search.py` is a facade only (delegates to `run_search`, `load_search_more`, `list_searches`, `delete_search`, and profile/unlock services).
- **Result count:** The number of people returned and charged for is `num_cards` (1–24). Resolution order: `body.num_cards` → `payload.num_cards` (LLM) → `_extract_num_cards_from_query(query)` → `DEFAULT_NUM_CARDS` (6). Stored ranking keeps up to `TOP_PEOPLE_STORED` (24) for "load more."
- **Credits:** Non-empty search deducts `num_cards` credits (1 per card shown). **Empty search deducts 0 credits** (Search row is still created; no debit). Load-more deducts 1 credit per batch unless `skip_credits=True` (e.g. viewing from history).
- **Idempotency:** Replay-only. If `Idempotency-Key` is sent and a row exists with `response_body`, that response is returned immediately. No reservation row; no explicit "in progress" path. Same pattern for unlock-contact (per-endpoint key).
- **similarity_percent:** Derived from final blended score (clamped to [0, 1] then mapped to 0–100), not raw vector similarity. See `_score_to_similarity_percent(score)`.
- **why_matched:** Generated **inline** (LLM first, deterministic fallback if LLM fails). Response and past searches use the same initial value. An async task runs only when inline LLM did not produce results, to refresh `SearchResult.extra.why_matched` in the background.

---

## 2) Quick Navigation (Files and Functions)

| Area | File | Key Functions / Notes |
|------|------|------------------------|
| Search routes | `apps/api/src/routers/search.py` | `search`, `search_more`, `get_person`, `unlock_contact`, `list_people`, `list_saved_searches`, `delete_saved_search`, `list_unlocked_cards`, `get_person_public_profile` |
| Search facade | `apps/api/src/services/search/search.py` | `SearchService.search`, `get_search_more`, `get_profile`, `unlock`, `list_people`, `list_unlocked_cards`, `list_saved_searches`, `list_search_history`, `delete_saved_search`, `get_public_profile` |
| Search pipeline | `apps/api/src/services/search/search_logic.py` | `run_search`, `load_search_more`, `list_searches`, `delete_search`, `_validate_search_session`, `_apply_card_filters`, `_collapse_and_rank_persons`, `_generate_llm_why_matched`, `_create_empty_search_response`, `_fetch_candidates_with_fallback`, `_prepare_pending_search_rows`, `_persist_search_results` |
| Filter normalization | `apps/api/src/services/search/filter_validator.py` | `validate_and_normalize` (MUST caps, demotions, date/salary normalization) |
| Profile view | `apps/api/src/services/search/search_profile_view.py` | `get_person_profile`, `list_people_for_discover`, `get_public_profile_impl`, `list_unlocked_cards_for_searcher` |
| Unlock flow | `apps/api/src/services/search/search_contact_unlock.py` | `unlock_contact`, `unlock_endpoint(person_id)` for idempotency key |
| Chat parsing | `apps/api/src/providers/chat.py` | `parse_search_filters` (cleanup → single extract), `_chat_json`, `_chat` |
| Why-matched helpers | `apps/api/src/services/search/why_matched_helpers.py` | `build_match_explanation_payload`, `validate_why_matched_output`, `fallback_build_why_matched`, `clean_why_reason` |
| Prompts | `apps/api/src/prompts/search_filters.py` | `PROMPT_SEARCH_CLEANUP`, `PROMPT_SEARCH_SINGLE_EXTRACT`, `get_cleanup_prompt`, `get_single_extract_prompt` |
| Prompts | `apps/api/src/prompts/search_why_matched.py` | `get_why_matched_prompt` |
| Prompts | `apps/api/src/prompts/experience_card_enums.py` | `INTENT_ENUM` (from `src.domain.Intent`) |
| Schemas | `apps/api/src/schemas/search.py` | `SearchRequest`, `SearchResponse`, `PersonSearchResult`, `ParsedConstraintsPayload`, `ParsedConstraintsMust`, `ParsedConstraintsShould`, `ParsedConstraintsExclude`, `SavedSearchItem`, `SavedSearchesResponse`, `UnlockContactRequest`, `UnlockContactResponse`, `PersonProfileResponse` |
| Credits & idempotency | `apps/api/src/services/credits.py` | `get_balance`, `deduct_credits`, `add_credits`, `get_idempotent_response`, `save_idempotent_response` |
| Core config | `apps/api/src/core/constants.py` | `SEARCH_RESULT_EXPIRY_HOURS`, `EMBEDDING_DIM` |
| DB models | `apps/api/src/db/models.py` | `Search`, `SearchResult`, `IdempotencyKey`, `UnlockContact`, `PersonProfile`, `Person`, `ExperienceCard`, `ExperienceCardChild` |
| Frontend result card | `apps/web/src/components/search/person-result-card.tsx` | Consumes `similarity_percent`, `why_matched` (up to 3 items), `matched_cards`; fallback text: "Matched your search intent and profile signals." |

---

## 3) API Surface

### 3.1 `POST /search`

- **Auth:** Required.
- **Rate limit:** `search_rate_limit` from settings (default e.g. 10/minute).
- **Optional header:** `Idempotency-Key`.
- **Request body:** `SearchRequest` (`query`, `open_to_work_only`, `preferred_locations`, `salary_min`, `salary_max`, `num_cards`).
- **Response:** `SearchResponse` (`search_id`, `people`, `num_cards`).

### 3.2 Other search-related endpoints

- **GET /people** — Discover list (people with at least one visible parent card).
- **GET /people/{person_id}** — Profile for a person; optional `search_id` query. When `search_id` is present, session and person-in-results are validated.
- **GET /people/{person_id}/profile** — Public-style profile (auth still required by router); no search session.
- **POST /people/{person_id}/unlock-contact** — Unlock contact; body can include `search_id`; idempotency key is per-endpoint (e.g. `POST /people/{person_id}/unlock-contact`).
- **GET /search/{search_id}/more** — Load more results; query params: `offset`, `limit` (default 6, max 24), `history` (when true, no credit deduction).
- **GET /me/searches** — List saved/search history (newest first, with `result_count`).
- **DELETE /me/searches/{search_id}** — Delete a saved search (204).
- **GET /me/unlocked-cards** — List people whose contact was unlocked by current user.

---

## 4) End-to-End `run_search` (Exact Order)

File: `apps/api/src/services/search/search_logic.py`. Function: `run_search(db, searcher_id, body, idempotency_key)`.

1. **Idempotency:** If `idempotency_key` is set, call `get_idempotent_response(db, key, searcher_id, "POST /search")`. If row exists and has `response_body`, return `SearchResponse(**existing.response_body)`.
2. **Parse:** `payload = await _parse_search_payload(chat, body.query)` (see §5). Build `filters_dict = payload.model_dump(mode="json")`.
3. **num_cards:** If `body.num_cards is not None` → `num_cards = max(1, min(TOP_PEOPLE_STORED, body.num_cards))`. Else: from `payload.num_cards`, else `_extract_num_cards_from_query(raw_query)`, else `DEFAULT_NUM_CARDS`. Clamp to `[1, TOP_PEOPLE_STORED]`.
4. **Credit pre-check:** If `get_balance(db, searcher_id) < num_cards` → raise `HTTP 402` (Insufficient credits).
5. **Query prep:** `embedding_text = _build_embedding_text(payload, body)` (payload.query_embedding_text || query_original || body.query). Resolve `open_to_work_only` and `offer_salary_inr_per_year` from body/must. Build `query_ts` for lexical (search_phrases + first 5 should keywords, else cleaned/raw query trimmed to 200 chars).
6. **Parallel:** Start `_embed_query_vector(body.query, embedding_text)` and `_lexical_candidates(db, query_ts)`. Await both; on embedding exception, re-raise (503 path); on lexical exception, continue with empty lexical map.
7. **Empty vector:** If `query_vec` is empty → `_create_empty_search_response(...)` (creates Search row, **no credit deduction**, returns `people=[], num_cards=num_cards`), then save idempotency if key present, return.
8. **Constraint terms:** `_collect_constraint_terms(must, exclude.company_norm, exclude.keywords)` → `_SearchConstraintTerms` (time_start, time_end, query_has_time, query_has_location, company_norms, team_norms, exclude_company_norms, exclude_keyword_terms).
9. **Candidates:** `_fetch_candidates_with_fallback(...)` with increasing fallback tier until unique person count ≥ `MIN_RESULTS` or tier reaches `FALLBACK_TIER_COMPANY_TEAM_SOFT`. Returns `(fallback_tier, rows, child_rows, child_evidence_rows)`.
10. **Rank:** `_collapse_and_rank_persons(rows, child_rows, child_evidence_rows, payload, lexical_scores, fallback_tier, query_has_time, query_has_location, must)` → person_cards, child_sims_by_person, child_best_parent_ids, person_best (sorted by score). Keep `ranked_people_full = person_best[:TOP_PEOPLE_STORED]`.
11. **Empty ranked list:** If no ranked people → `_create_empty_search_response(..., fallback_tier=fallback_tier, num_cards=num_cards)` (no deduction), save idempotency if key, return.
12. **Load data:** `_load_people_profiles_and_children(db, person_ids_full, child_evidence_rows)` → people_map, vis_map, children_by_id.
13. **Tiebreakers:** `_apply_post_rank_tiebreakers(ranked_people_full, vis_map, person_cards, offer_salary_inr_per_year, time_start, time_end)` (salary-aware and/or date-overlap-aware sort).
14. **Persistence (search):** `_create_search_record(db, searcher_id, body.query, filters_dict, fallback_tier)` → insert `Search`; then `_deduct_search_credits_or_raise(db, searcher_id, search_rec.id, num_cards)`.
15. **Child-only cards (parallel):** Start `_load_child_only_cards(...)` for people matched only via child embeddings (for display).
16. **Pending rows:** `_prepare_pending_search_rows(ranked_people_full, person_cards, child_sims_by_person, child_best_parent_ids, children_by_id, vis_map, payload)` → similarity_by_person, pending_search_rows, llm_people_evidence. Only first `num_cards` are persisted and used for response.
17. **why_matched (inline):** For first `num_cards` evidence, try `_generate_llm_why_matched(chat, payload, llm_evidence_to_persist)`. On success, use result; on failure, use deterministic fallback from `_prepare_pending_search_rows` (fallback_why per row).
18. **Persist results:** `_persist_search_results(db, search_rec.id, pending_to_persist, llm_why_by_person)` → inserts `SearchResult` rows with rank, score, extra (matched_parent_ids, matched_child_ids, why_matched). Returns why_matched_by_person for response.
19. **Async why_matched:** If inline LLM did not run or failed (`llm_evidence_to_persist` non-empty and `llm_why_by_person` empty), start `asyncio.create_task(_update_why_matched_async(...))` to refresh `SearchResult.extra.why_matched` in background (best-effort).
20. **Child-only:** Await child_only_task; build `_build_search_people_list(ranked_people_initial, people_map, vis_map, person_cards, child_only_cards, similarity_by_person, why_matched_by_person)`.
21. **Response:** `SearchResponse(search_id=search_rec.id, people=people_list, num_cards=num_cards)`. If idempotency_key, `save_idempotent_response(...)`. Return.

---

## 5) Parse and Normalize (Detail)

### 5.1 Chat parse (`parse_search_filters`)

- **File:** `apps/api/src/providers/chat.py`.
- **Steps:**
  1. **Cleanup:** `get_cleanup_prompt(query)` → `PROMPT_SEARCH_CLEANUP` with `{{USER_TEXT}}` = raw query. Call `_chat` (no JSON mode); strip response. If empty, use raw query as cleaned.
  2. **Single extract:** `get_single_extract_prompt(query, cleaned_text)` → `PROMPT_SEARCH_SINGLE_EXTRACT` with `{{INTENT_ENUM}}`, `{{QUERY_ORIGINAL}}`, `{{QUERY_CLEANED}}`. Call `_chat_json` → parse JSON (strip code fences if needed). Must return a dict; otherwise `ChatServiceError`.

- **Fallback on ChatServiceError (in run_search):** Build `filters_raw = { "query_original": raw_query, "query_cleaned": raw_query, "query_embedding_text": raw_query }`. Then `validate_and_normalize(ParsedConstraintsPayload.from_llm_dict(filters_raw))`.

### 5.2 Filter validator (`validate_and_normalize`)

- **File:** `apps/api/src/services/search/filter_validator.py`.
- **Input:** `ParsedConstraintsPayload` (from `ParsedConstraintsPayload.from_llm_dict(filters_raw)`).
- **Behavior:**
  - **Dedupe and normalize lists:** company_norm, team_norm (lowercase, dedupe); intent_primary validated against `Intent` enum; domain, sub_domain, employment_type, seniority_level deduped; exclude company/keywords deduped; skills_or_tools, keywords, search_phrases deduped.
  - **MUST caps (recall protection):** intent_primary → keep at most `MAX_MUST_INTENT_PRIMARY` (2), rest → should.intent_secondary. company_norm → at most `MAX_MUST_COMPANY_NORM` (3), rest → should.keywords. team_norm → at most `MAX_MUST_TEAM_NORM` (3), rest → should.keywords. domain → at most `MAX_MUST_DOMAIN` (2); if `confidence_score < WEAK_CONFIDENCE_THRESHOLD` (0.5), domain overflow + sub_domain → should.keywords, sub_domain cleared.
  - **Dates:** time_start, time_end normalized to YYYY-MM-DD (accepts YYYY-MM, YYYY); year clamped to [MIN_ALLOWED_YEAR, current_year + MAX_ALLOWED_YEAR_OFFSET]. If time_start > time_end, swap.
  - **Salary:** offer_salary_inr_per_year normalized to INR/year; values < 200k treated as monthly and multiplied by 12.
  - **num_cards:** Preserved; if set, clamped to 1–24.
- **Output:** New `ParsedConstraintsPayload` with normalized must/should/exclude and num_cards.

---

## 6) Request Overrides

- **open_to_work_only:** Use `body.open_to_work_only` if not None; else parsed `must.open_to_work_only`.
- **offer_salary_inr_per_year:** Use `body.salary_max` if not None; else parsed `must.offer_salary_inr_per_year`.
- **salary_min:** Validated in schema (`salary_min <= salary_max`). Not used in SQL or ranking; display/UX only.
- **num_cards:** Request body overrides parsing; then payload.num_cards; then `_extract_num_cards_from_query`; then `DEFAULT_NUM_CARDS`. Clamped to [1, TOP_PEOPLE_STORED].

---

## 7) Embedding and Lexical

- **Embedding text priority:** payload.query_embedding_text → payload.query_original → body.query. Empty after strip → empty vector path.
- **Embedding failure:** Raises HTTP 503 (from `_embed_query_vector`).
- **Lexical:** `_lexical_candidates(db, query_ts)` runs FTS on `experience_cards.search_document` and `experience_card_children.search_document` (joined to visible parents). Query from search_phrases + first 5 should keywords, else cleaned/raw trimmed to 200 chars. Per-person score normalized and capped to `LEXICAL_BONUS_MAX`. On exception, returns {} and search continues without lexical bonus.

---

## 8) Candidate Retrieval and Fallback Tiers

- **Loop:** Start at `FALLBACK_TIER_STRICT` (0); fetch candidates for current tier; if unique person count ≥ `MIN_RESULTS` or tier ≥ `FALLBACK_TIER_COMPANY_TEAM_SOFT`, stop; else tier += 1.
- **Per tier:** `_fetch_candidate_rows_for_filter_ctx(db, query_vec, filter_ctx)` runs three queries:
  1. Parent candidates: `ExperienceCard` with visibility, non-null embedding, `_apply_card_filters`, order by cosine distance, limit `OVERFETCH_CARDS`.
  2. Child min distance per person: `ExperienceCardChild` joined to visible parents, same filters, group by person_id, min(distance).
  3. Child evidence: same join + filters, row_number() partition by person_id order by dist, keep rows where rn ≤ `MATCHED_CARDS_PER_PERSON`.
- **Tier semantics:**
  - Tier 0: apply_company_team=True, apply_location=True, apply_time=True.
  - Tier 1: apply_time=False (time relaxed).
  - Tier 2: apply_time=False, apply_location=False.
  - Tier 3: apply_company_team=False as well (company/team relaxed).
- **Always applied (not tier-relaxed):** intent_primary, domain, sub_domain, employment_type, seniority_level, is_current, exclude (company_norm, keywords). PersonProfile join (open_to_work_only, preferred_locations, offer_salary_inr_per_year) when relevant.

---

## 9) `_apply_card_filters` Semantics

- **Company/team:** Applied only when `ctx.apply_company_team`; `ExperienceCard.company_norm.in_(company_norms)` and/or `team_norm.in_(team_norms)`.
- **Location:** Applied only when `ctx.apply_location`; OR of ILIKE on location for city, country, location_text.
- **Time:** Applied only when `ctx.apply_time` and both time_start and time_end present; card must have at least one of start_date/end_date; overlap condition: (start_date ≤ query_end or null) and (end_date ≥ query_start or null).
- **Exclude:** Always applied when present: `~company_norm.in_(exclude_norms)`, `~search_phrases.overlap(norm_terms_exclude)`.
- **PersonProfile join:** When open_to_work_only or offer_salary_inr_per_year: join PersonProfile, open_to_work=True if open_to_work_only; optional work_preferred_locations overlap with body.preferred_locations; salary: work_preferred_salary_min IS NULL or work_preferred_salary_min ≤ offer_salary_inr_per_year.

---

## 10) Person Scoring and Ranking

- **Similarity from distance:** `sim = 1 / (1 + distance)`.
- **Per-card SHOULD boost:** Card similarity becomes `sim + should_hits * SHOULD_BOOST` (should_hits capped by SHOULD_CAP). Person-level should bonus: `min(total_should_hits * SHOULD_BOOST, SHOULD_BONUS_MAX)`.
- **Blended base:** `base = WEIGHT_PARENT_BEST * parent_best + WEIGHT_CHILD_BEST * child_best + WEIGHT_AVG_TOP3 * avg_top3` (parent_best = max parent sim; child_best = max child sim; avg_top3 = avg of top 3 sims across parent+child, up to TOP_K_CARDS).
- **Final score:** `final = max(0, base + lexical_bonus + should_bonus - penalties)`. Penalties: if query has time and tier ≥ time_soft, missing date on all parent cards → MISSING_DATE_PENALTY; if query has location and tier ≥ location_soft and no parent card location match → LOCATION_MISMATCH_PENALTY.
- **similarity_percent:** `_score_to_similarity_percent(score)` clamps score to [0, 1], then `round(score * 100)`.

---

## 11) Constants (Exact Values from search_logic.py)

```text
SEARCH_ENDPOINT = "POST /search"
OVERFETCH_CARDS = 10
DEFAULT_NUM_CARDS = 6
TOP_PEOPLE_STORED = 24
MATCHED_CARDS_PER_PERSON = 3
MIN_RESULTS = 15
TOP_K_CARDS = 5
LOAD_MORE_LIMIT = 6

WEIGHT_PARENT_BEST = 0.55
WEIGHT_CHILD_BEST = 0.30
WEIGHT_AVG_TOP3 = 0.15
LEXICAL_BONUS_MAX = 0.25
SHOULD_BOOST = 0.05
SHOULD_CAP = 10
SHOULD_BONUS_MAX = 0.25
MISSING_DATE_PENALTY = 0.15
LOCATION_MISMATCH_PENALTY = 0.15

FALLBACK_TIER_STRICT = 0
FALLBACK_TIER_TIME_SOFT = 1
FALLBACK_TIER_LOCATION_SOFT = 2
FALLBACK_TIER_COMPANY_TEAM_SOFT = 3
```

**filter_validator.py:** MAX_MUST_INTENT_PRIMARY=2, MAX_MUST_COMPANY_NORM=3, MAX_MUST_TEAM_NORM=3, MAX_MUST_DOMAIN=2, WEAK_CONFIDENCE_THRESHOLD=0.5, MIN_ALLOWED_YEAR=1900, MAX_ALLOWED_YEAR_OFFSET=1.

**why_matched_helpers.py:** WHY_REASON_MAX_LEN=150, WHY_REASON_MAX_WORDS=15, WHY_REASON_MAX_ITEMS=3, EVIDENCE_SNIPPET_MAX_LEN=150, EVIDENCE_STRING_MAX_LEN=200.

**core/constants.py:** SEARCH_RESULT_EXPIRY_HOURS=24, EMBEDDING_DIM=324.

---

## 12) Post-Rank Tiebreakers

- If `offer_salary_inr_per_year` is set: sort by (-score, has_stated_salary_min_first).
- If query has full time range (time_start and time_end): sort by (-score, has_full_date_overlap_first).

---

## 13) why_matched Pipeline (Inline + Async)

- **Evidence:** Per person, `_build_person_why_evidence` builds parent_cards (title, company_name, location, summary, search_phrases, similarity, start_date, end_date) and child_cards (title, headline, summary, context, tags, search_phrases, similarity). Then `build_match_explanation_payload(query_context, people_evidence_raw)` in why_matched_helpers produces cleaned, deduped payloads for the LLM.
- **Inline:** `_generate_llm_why_matched(chat, payload, people_evidence)` builds prompt via `get_why_matched_prompt(...)`, calls `chat.chat(prompt, max_tokens=1200, temperature=0.1)`, parses JSON, runs `validate_why_matched_output(parsed)` (clean_why_reason, max 3 lines, dedupe). For any person with no valid reasons, `fallback_build_why_matched(person_evidence, query_context)` is used; if still empty, generic `["Matched your search intent and profile signals."]`.
- **Persist:** SearchResult rows get `extra.why_matched` from inline LLM result or fallback. Async task only when inline LLM was not used or failed; it sleeps 1s, gets new session, calls `_generate_llm_why_matched`, then updates SearchResult.extra.why_matched in DB (best-effort).

---

## 14) Session Validation and Expiry

- **Used by:** profile view (when search_id given), unlock-contact (when search_id given), load_search_more.
- **Function:** `_validate_search_session(db, searcher_id, search_id, person_id=None)`. Search must exist, searcher_id must match. If person_id given, person must appear in search_results for that search. If expired → HTTP 403.
- **Expiry:** `_search_expired(search_rec)`: primary `search.expires_at < now_utc`; fallback `created_at + SEARCH_RESULT_EXPIRY_HOURS` (24h).

---

## 15) Related Endpoint Flows (Concise)

- **GET /people/{person_id}?search_id=...:** `get_person_profile`; if search_id, validates session and person in results; loads person, profile, visible cards, unlock row; contact only if (open_to_work or open_to_contact) and unlocked; work_preferred_locations/salary_min only when open_to_work.
- **POST /people/{person_id}/unlock-contact:** Idempotency per `unlock_endpoint(person_id)`. Validate session + person if search_id. Reject if not open_to_work and not open_to_contact (403). If already unlocked for (searcher, target, search_id), return success without charge. Else credit check, create UnlockContact, deduct 1, save idempotency response.
- **GET /people:** `list_people_for_discover` — people with ≥1 visible parent card; returns id, display_name, current_location (PersonProfile.current_city), up to 5 latest non-empty parent summaries.
- **GET /people/{person_id}/profile:** `get_public_profile_impl` — no search session; returns id, display_name, bio, card_families.
- **GET /search/{search_id}/more:** `load_search_more`; validates session; fetches SearchResult by rank, offset, limit; if not skip_credits, deducts 1 credit per batch; builds PersonSearchResult from stored extra (matched_parent_ids, why_matched) and loads Person, PersonProfile, ExperienceCard.

---

## 16) Prompt Contracts (Input → Output)

### 16.1 Cleanup (`PROMPT_SEARCH_CLEANUP`)

- **Input:** `{{USER_TEXT}}` = raw query.
- **Output:** Plain text only (cleaned query). No JSON, no markdown. Empty → code uses raw query.

### 16.2 Single extract (`PROMPT_SEARCH_SINGLE_EXTRACT`)

- **Input:** `{{INTENT_ENUM}}` (from experience_card_enums), `{{QUERY_ORIGINAL}}`, `{{QUERY_CLEANED}}`.
- **Output:** Single JSON object with keys: query_original, query_cleaned, must (company_norm, team_norm, intent_primary, domain, sub_domain, employment_type, seniority_level, location_text, city, country, time_start, time_end, is_current, open_to_work_only, offer_salary_inr_per_year), should (skills_or_tools, keywords, intent_secondary), exclude (company_norm, keywords), search_phrases, query_embedding_text, confidence_score, **num_cards** (integer 1–24 or null). Provider strips code fences and parses JSON; run_search maps via `ParsedConstraintsPayload.from_llm_dict` then `validate_and_normalize`.

### 16.3 Why-matched (`get_why_matched_prompt`)

- **Input:** query_context (query_original, query_cleaned, must, should), people array of { person_id, evidence } (evidence from build_match_explanation_payload: headline, summary, skills, company, location, time, child_evidence, etc.).
- **Output:** JSON `{ "people": [ { "person_id": "uuid", "why_matched": ["string", "string", "string"] } ] }`. Max 3 reasons per person, ≤120 chars, no field labels or markdown. Sanitization in validate_why_matched_output and clean_why_reason (strip generic prefixes, max length/words, reject junk).

### 16.4 Full prompt text (runtime strings)

Source: `apps/api/src/prompts/search_filters.py` and `apps/api/src/prompts/search_why_matched.py`.

**PROMPT_SEARCH_CLEANUP** (placeholder `{{USER_TEXT}}` = raw user query):

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

**PROMPT_SEARCH_SINGLE_EXTRACT** (placeholders: `{{INTENT_ENUM}}`, `{{QUERY_ORIGINAL}}`, `{{QUERY_CLEANED}}`).  
`INTENT_ENUM` from `src.domain.Intent`: `work, education, project, business, research, practice, exposure, achievement, transition, learning, life_context, community, finance, other, mixed`.

```text
You are a structured search-query parser for CONXA (intent-based people search).

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
```

**get_why_matched_prompt** (payload = `{"query_context": {...}, "people": [{ "person_id": "...", "evidence": {...} }, ...]}`):

```text
You are a grounded match-explanation engine.

TASK
Generate short, clear reasons explaining why each person matched a search query.

You MUST use only the evidence provided in the input.
You MUST compress and summarize noisy evidence into clean reasons.
Do NOT copy raw labels/headlines verbatim when they are repetitive, duplicated, or poorly formatted.

OUTPUT (STRICT)
Return ONLY valid JSON with this exact schema:
{
  "people": [
    {
      "person_id": "string",
      "why_matched": ["string", "string", "string"]
    }
  ]
}

GLOBAL RULES (STRICT)
1) Return 1-3 reasons per person.
2) Each reason must be <= 120 characters.
3) Each reason must be a clean human-readable phrase/sentence fragment.
4) Do NOT invent facts not present in the input.
5) Do NOT include markdown, bullet symbols, comments, or prose outside JSON.
6) Do NOT include field names (e.g., "headline:", "summary:", "skills:") in the output.
7) Do NOT copy long raw text; summarize it.
8) Do NOT repeat the same fact across multiple reasons.
9) If evidence is weak/noisy, return 1 cautious reason using only clearly supported facts.

WHAT TO PRIORITIZE IN REASONS
Prefer the strongest overlaps with the query, in this order:
1) Hard constraints / explicit filters (role, company, team, location, time, availability, salary)
2) Skills / tools / methods
3) Domain / type of work
4) Outcomes / metrics / achievements
5) Supporting context (responsibilities, collaborations, exposure)

DEDUPLICATION RULES
- If the same concept appears in parent and child evidence, mention it only once.
- If labels/headlines repeat words (e.g., "Sales Manager Sales Manager"), rewrite cleanly.
- Ignore duplicate or near-duplicate evidence snippets.

NORMALIZATION RULES
- Prefer normalized facts when both raw + normalized forms exist.
- Keep currency/metrics concise (e.g., "₹15L sales in 2 months").
- Keep time/location concise (e.g., "Mumbai", "3 years", "2022-2024").
- If multiple facts are available, choose the most search-relevant ones.

STYLE RULES
- Be specific, not generic.
- Good: "Quant research in crypto using Python and backtesting"
- Good: "Mumbai studio partnerships with ₹15L sales in 2 months"
- Good: "Ops + automation work with vendor/process ownership"
- Bad: "Why this card was shown: ..."
- Bad: "Sales Manager Sales Manager..."
- Bad: "Matched because of experience"

ROBUSTNESS RULES
- Some evidence may be incomplete, duplicated, or noisy.
- Some fields may be missing.
- Some people may match mostly via parent evidence, others via child evidence.
Handle all cases gracefully and still return valid JSON.

INPUT JSON
{payload_json}
```

---

## 17) Schemas (Full Definitions)

Source: `apps/api/src/schemas/search.py`. Related types: `ExperienceCardResponse`, `CardFamilyResponse`, `BioResponse`, `ContactDetailsResponse` from other schema modules.

### 17.1 SearchRequest (POST /search body)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query | string | yes | Raw search query text. |
| open_to_work_only | boolean | no | Override parsed open_to_work_only when set. |
| preferred_locations | list[string] | no | Preferred locations when open_to_work_only; used for PersonProfile.work_preferred_locations overlap. |
| salary_min | number (Decimal) | no | Recruiter min (INR/year); display/UX only; not used in SQL or ranking. |
| salary_max | number (Decimal) | no | Recruiter offer budget INR/year; candidates matched where work_preferred_salary_min <= salary_max (or NULL). |
| num_cards | integer | no | Result count (1–24); if set, overrides query parsing; else from payload or default 6. |

**Validation:** `salary_min <= salary_max` when both set. `num_cards` if present must be 1–1000 (runtime clamps to 1–24).

**Example:**

```json
{
  "query": "backend engineer in Bangalore open to work",
  "open_to_work_only": true,
  "preferred_locations": ["Bangalore", "Remote"],
  "salary_min": null,
  "salary_max": 2400000,
  "num_cards": 6
}
```

### 17.2 ParsedConstraintsPayload (LLM extraction → validate_and_normalize)

Stored as `Search.parsed_constraints_json` / `Search.filters`. Built via `ParsedConstraintsPayload.from_llm_dict(filters_raw)` then `validate_and_normalize(...)`.

**ParsedConstraintsMust:** company_norm, team_norm (list[str]); intent_primary, domain, sub_domain, employment_type, seniority_level (list[str]); location_text, city, country, time_start, time_end (str \| null); is_current, open_to_work_only (bool \| null); offer_salary_inr_per_year (float \| null). After validation: max 3 company_norm, max 3 team_norm, max 2 intent_primary, max 2 domain in MUST; rest demoted to should.

**ParsedConstraintsShould:** skills_or_tools, keywords, intent_secondary (list[str]).

**ParsedConstraintsExclude:** company_norm, keywords (list[str]).

**ParsedConstraintsPayload (root):** query_original, query_cleaned (str); must, should, exclude (above); search_phrases (list[str]); query_embedding_text (str); confidence_score (float 0–1); num_cards (int \| null, 1–24).

**Example (after normalization):**

```json
{
  "query_original": "backend engineer bangalore",
  "query_cleaned": "backend engineer bangalore",
  "must": {
    "company_norm": [],
    "team_norm": [],
    "intent_primary": ["work"],
    "domain": [],
    "sub_domain": [],
    "employment_type": [],
    "seniority_level": [],
    "location_text": "Bangalore",
    "city": "Bangalore",
    "country": null,
    "time_start": null,
    "time_end": null,
    "is_current": null,
    "open_to_work_only": null,
    "offer_salary_inr_per_year": null
  },
  "should": { "skills_or_tools": [], "keywords": ["backend", "engineer"], "intent_secondary": [] },
  "exclude": { "company_norm": [], "keywords": [] },
  "search_phrases": ["backend engineer", "Bangalore"],
  "query_embedding_text": "backend engineer Bangalore",
  "confidence_score": 0.8,
  "num_cards": null
}
```

### 17.3 SearchResponse (POST /search response)

| Field | Type | Description |
|-------|------|-------------|
| search_id | string (UUID) | Search record id. |
| people | list[PersonSearchResult] | Initial slice (length = num_cards). |
| num_cards | integer \| null | Limit applied; credits charged = num_cards when non-empty. |

### 17.4 PersonSearchResult

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Person id. |
| name | string \| null | display_name. |
| headline | string \| null | From profile (e.g. current_company / current_city). |
| bio | string \| null | Compact bio summary. |
| similarity_percent | integer \| null | 0–100 from blended score. |
| why_matched | list[string] | 1–3 reason strings. |
| open_to_work | boolean | From PersonProfile. |
| open_to_contact | boolean | From PersonProfile. |
| work_preferred_locations | list[string] | Shown when open_to_work. |
| work_preferred_salary_min | number \| null | INR/year; serialized as float in JSON. |
| matched_cards | list[ExperienceCardResponse] | 1–3 best matching cards. |

**Example (one person in response):**

```json
{
  "id": "uuid",
  "name": "Jane Doe",
  "headline": "Acme Corp / Bangalore",
  "bio": "Jane Doe | College: IIT",
  "similarity_percent": 78,
  "why_matched": ["Backend experience at Acme", "Python and Go"],
  "open_to_work": true,
  "open_to_contact": true,
  "work_preferred_locations": ["Bangalore", "Remote"],
  "work_preferred_salary_min": 1800000,
  "matched_cards": []
}
```

### 17.5 PersonProfileResponse (GET /people/{person_id})

id (str), display_name (str \| null), open_to_work, open_to_contact (bool), work_preferred_locations (list[str]), work_preferred_salary_min (number \| null), experience_cards (list[ExperienceCardResponse]), card_families (list[CardFamilyResponse]), bio (BioResponse \| null), contact (ContactDetailsResponse \| null, only if unlocked).

### 17.6 SavedSearchItem / SavedSearchesResponse

**SavedSearchItem:** id, query_text, created_at (ISO), expires_at (ISO), expired (bool), result_count (int).  
**SavedSearchesResponse:** searches: list[SavedSearchItem].

### 17.7 UnlockContactRequest / UnlockContactResponse

**UnlockContactRequest:** search_id (str \| null).  
**UnlockContactResponse:** unlocked (bool), contact (ContactDetailsResponse: email_visible, email, phone, linkedin_url, other).

### 17.8 Persisted DB metadata

- **Search.extra:** `{ "fallback_tier": number }` (0–3).
- **SearchResult.extra:** `{ "matched_parent_ids": string[], "matched_child_ids": string[], "why_matched": string[] }`.

---

## 18) Failure and Degradation

- Parse failure (ChatServiceError): fallback to raw-query payload (query_original, query_cleaned, query_embedding_text = raw query).
- Explainability LLM failure: deterministic why_matched from fallback_build_why_matched; async task may refresh later.
- Lexical failure: continue with empty lexical map (no bonus).
- Embedding failure: HTTP 503.
- Insufficient credits (pre-check or deduct): HTTP 402.
- Idempotency: replay only when a completed response row exists; no "in progress" handling.

---

## 19) Maintenance Checklist

When changing search behavior, update this doc and/or code in sync:

1. run_search step order and credit deduction points (empty = 0, non-empty = num_cards).
2. num_cards resolution and TOP_PEOPLE_STORED vs DEFAULT_NUM_CARDS.
3. _apply_card_filters semantics and tier policy (apply_company_team, apply_location, apply_time).
4. Ranking formula and constants (weights, penalties, LEXICAL_BONUS_MAX, SHOULD_*).
5. similarity_percent mapping (_score_to_similarity_percent).
6. why_matched: inline vs async, prompt schema, validate_why_matched_output and fallback_build_why_matched.
7. Idempotency in search and unlock (replay-only, endpoint strings).
8. Schemas in src/schemas/search.py and request/response shapes.
9. Frontend: person-result-card.tsx (similarity_percent, why_matched, matched_cards).
10. Filter validator caps and demotions (MAX_MUST_*, WEAK_CONFIDENCE_THRESHOLD).
