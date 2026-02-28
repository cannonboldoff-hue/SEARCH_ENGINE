# Why Search Matched — Step-by-Step Flow

This document explains how the **why_matched** feature works: the end-to-end pipeline, schemas, prompts, and what goes in and out at each stage.

---

## Overview

When a user runs a search, each result person gets 1–3 short, human-readable reasons explaining **why** they matched. These are either:

1. **LLM-generated** — Produced by an LLM from search evidence (preferred)
2. **Deterministic fallback** — Built from the same evidence when the LLM is unavailable or returns invalid JSON

The output appears as `why_matched: string[]` on each `PersonSearchResult` and is shown in the UI as bullets under "Why [person name]".

---

## Flow Diagram (High-Level)

```
Search results ranked
        ↓
_build_person_why_evidence()  →  people_evidence (raw)
        ↓
build_match_explanation_payload()  →  cleaned payloads (for LLM)
        ↓
get_why_matched_prompt()  →  prompt string
        ↓
chat.chat(prompt)  →  raw LLM response
        ↓
JSON parse → validate_why_matched_output()  →  person_id → reasons
        ↓
fallback_build_why_matched() for any person with no valid reasons
        ↓
why_matched_by_person: dict[str, list[str]]
        ↓
_prepare_pending_search_rows() + _persist_search_results()
(stores why_matched in SearchResult.extra.why_matched)
```

---

## Step 1: Evidence Collection

**Location:** `search_logic.py` → `_build_person_why_evidence()`

**Input:**
- `person_id: str`
- `profile: PersonProfile | None`
- `parent_cards_with_sim: list[tuple[ExperienceCard, float]]` — up to 2 best-matching parent experience cards with similarity scores
- `child_evidence: list[tuple[ExperienceCardChild, str, float]]` — up to 2 best-matching child cards with `(child, parent_id, similarity)`

**Output (raw people_evidence item):**

```json
{
  "person_id": "uuid-string",
  "open_to_work": true,
  "open_to_contact": true,
  "matched_parent_cards": [
    {
      "title": "Backend Engineer",
      "company_name": "Acme Corp",
      "location": "Mumbai",
      "summary": "Built APIs and microservices...",
      "similarity": 0.8523,
      "start_date": "2022-01",
      "end_date": "2024-06"
    }
  ],
  "matched_child_cards": [
    {
      "child_type": "skills",
      "titles": ["Python", "Go", "PostgreSQL"],
      "descriptions": ["...", "..."],
      "raw_text": "verbatim excerpt from child value",
      "similarity": 0.7891
    }
  ]
}
```

**Notes:**
- Parent cards: up to 2, with similarity scores. Parent cards have no stored `search_document` or `search_phrases`; text is derived via `build_parent_search_document()` when needed.
- Child cards come from `_child_display_fields()` in `why_matched_helpers.py`, which reads `value.items[]` (title, description) and `value.raw_text` from each child.

---

## Step 2: Payload Cleanup and Deduplication

**Location:** `why_matched_helpers.py` → `build_match_explanation_payload()`

**Input:**
- `query_context: dict` — `{ "query_original", "query_cleaned", "must", "should" }`
- `people_evidence_raw: list[dict]` — output from Step 1

**Output (cleaned payload per person, for LLM prompt):**

```json
{
  "person_id": "uuid-string",
  "query_context": {
    "query_original": "backend engineer Python Mumbai",
    "query_cleaned": "backend engineer python mumbai",
    "must": {
      "location_text": "Mumbai",
      "domain": ["technology"],
      "intent_primary": ["backend"]
    },
    "should": {
      "skills_or_tools": ["Python", "Go"],
      "keywords": ["APIs"]
    }
  },
  "evidence": {
    "headline": "Backend Engineer",
    "summary": "Built APIs and microservices...",
    "domain": "Engineering",
    "company": "Acme Corp",
    "location": "Mumbai",
    "time": "2022-01–2024-06",
    "outcomes": ["child title 1", "child description 1", "child title 2", ...],
    "child_evidence": [
      {
        "child_type": "skills",
        "titles": ["Python", "Go"],
        "descriptions": ["..."]
      }
    ]
  }
}
```

**Note on query_context placement:** The Step 2 per-person payload includes
`query_context` for intermediate processing. When building the final LLM prompt
in Step 3, `query_context` is de-duplicated to a single top-level key shared
across all people, and each person entry contains only `person_id` and `evidence`.
The Step 3 LLM input shape reflects this final structure.

**Evidence fields:** `domain` in evidence comes from `must.domain` (first value when present), not from parent card. `outcomes` are child item titles and descriptions only.

**Deduplication rules:**
- Text snippets are deduplicated across parent and child evidence.
- Substring overlaps are dropped.
- String lengths capped: `EVIDENCE_SNIPPET_MAX_LEN=150`, `EVIDENCE_STRING_MAX_LEN=200`.
- Up to 2 parents, 2 children, 6 outcomes. Outcomes are built from child item titles and
  descriptions (item.title, item.description) only; parent summary is in evidence.summary. No child summary field exists.

---

## Step 3: Prompt Construction

**Location:** `prompts/search_why_matched.py` → `get_why_matched_prompt()`

**Input:**
- `query_original: str`
- `query_cleaned: str`
- `must: dict` — ParsedConstraintsMust (model_dump)
- `should: dict` — ParsedConstraintsShould (model_dump)
- `people_evidence: list[dict]` — cleaned payload from Step 2

**Prompt structure:**

The prompt instructs the LLM to:
1. Use only the evidence provided.
2. Compress and summarize (no raw copy-paste).
3. Return strict JSON with the exact output schema.

**Input JSON sent to LLM:**

```json
{
  "query_context": {
    "query_original": "...",
    "query_cleaned": "...",
    "must": { ... },
    "should": { ... }
  },
  "people": [
    {
      "person_id": "uuid",
      "evidence": {
        "headline": "...",
        "summary": "...",
        "company": "...",
        "location": "...",
        "time": "...",
        "outcomes": ["...", "..."],
        "child_evidence": [
          {
            "child_type": "skills",
            "titles": ["..."],
            "descriptions": ["..."]
          }
        ]
      }
    }
  ]
}
```

**Prompt rules (summarized):**
- 1–3 reasons per person
- Each reason ≤ 150 characters
- No field labels (e.g. "headline:", "summary:")
- No markdown, bullets, or prose
- Prioritize: hard filters → skills/tools → domain → outcomes → context
- Deduplicate parent/child overlap
- Prefer normalized facts when both raw and normalized exist

---

## Step 4: LLM Call

**Location:** `search_logic.py` → `_generate_llm_why_matched()`

**Input to LLM:**
- Full prompt string from Step 3

**LLM params:**
- `max_tokens=1200`
- `temperature=0.1`

**Expected output schema (LLM must return):**

```json
{
  "people": [
    {
      "person_id": "uuid-string",
      "why_matched": [
        "Quant research in crypto using Python and backtesting",
        "Mumbai studio partnerships with ₹15L sales in 2 months"
      ]
    }
  ]
}
```

---

## Step 5: Parse and Validate LLM Response

**Location:** `why_matched_helpers.py` → `validate_why_matched_output()`, `clean_why_reason()`

**Input:**
- Parsed JSON from LLM (after `strip_json_from_response()`)

**Validation and cleanup:**
1. **clean_why_reason()** for each reason string:
   - Strip generic prefixes: "why this card was shown:", "matched because", etc.
   - Max length: 150 chars (`WHY_REASON_MAX_LEN`)
   - Max words: 15 (`WHY_REASON_MAX_WORDS`)
   - Reject junk: repeated words, all-caps spam, markdown artifacts
2. **validate_why_matched_output()**:
   - Max 3 reasons per person (`WHY_REASON_MAX_ITEMS`)
   - Deduplicate by normalized string
   - Count persons that needed fallback (no valid reasons)

**Output:**
- `(validated: dict[str, list[str]], fallback_count: int)`
- `validated` maps `person_id` → list of 1–3 cleaned reason strings

---

## Step 6: Fallback for Missing Reasons

**Location:** `why_matched_helpers.py` → `fallback_build_why_matched()`

**When used:**
- LLM failed (exception, parse error)
- LLM returned no valid reasons for a person
- Person not in validated output

**Input:**
- `person_evidence: dict` — cleaned payload from Step 2 (per person)
- `query_context: dict` — query context

**Logic (priority order):**
1. Explicit filters: location, company, time from `must` + evidence
2. Skills/tools overlap
3. Outcomes (from evidence.outcomes; child item titles + descriptions)
4. Domain/headline
5. Child evidence titles and descriptions

**Output:**
- `list[str]` — 1–3 grounded reasons, same length/word limits as LLM output

**Post-processing:** When using full fallback (LLM not run), `boost_query_matching_reasons()` ensures at least one reason mentions outcomes that directly match query terms (e.g. "200+ products sold" for query "Sold 100+ products").

---

## Step 7: Final Output and Persistence

**Location:** `search_logic.py` → `_persist_search_results()`, `_build_search_people_list()`

**Final structure:**
- `why_matched_by_person: dict[str, list[str]]` — `person_id` → 1–3 reason strings

**If no reasons at all (rare):**
- Generic: `["Matched your search intent and profile signals."]`

**Persisted:**
- `SearchResult.extra.why_matched: string[]` — stored in DB for past searches

**API response schema (`PersonSearchResult`):**

```json
{
  "id": "person-uuid",
  "name": "Jane Doe",
  "headline": "Backend Engineer",
  "similarity_percent": 85,
  "why_matched": [
    "Backend experience at Acme Corp in Mumbai",
    "Python and Go for APIs"
  ],
  "open_to_work": true,
  "open_to_contact": true,
  "matched_cards": [ ... ]
}
```

---

## Schemas Reference

### ParsedConstraintsMust (query filters)

| Field | Type | Description |
|-------|------|-------------|
| company_norm | list[str] | Normalized company names |
| team_norm | list[str] | Normalized team names |
| intent_primary | list[str] | Primary intents (e.g. backend) |
| domain | list[str] | Domains (e.g. technology) |
| sub_domain | list[str] | Sub-domains |
| employment_type | list[str] | Full-time, contract, etc. |
| seniority_level | list[str] | Seniority levels |
| location_text | str \| null | Location text |
| city | str \| null | City |
| country | str \| null | Country |
| time_start | str \| null | Start date filter |
| time_end | str \| null | End date filter |
| is_current | bool \| null | Must be current role |
| open_to_work_only | bool \| null | Must be open to work |
| offer_salary_inr_per_year | float \| null | Min salary (INR/year) |

### ParsedConstraintsShould (soft preferences)

| Field | Type | Description |
|-------|------|-------------|
| skills_or_tools | list[str] | Skills/tools to boost |
| keywords | list[str] | Keywords to boost |
| intent_secondary | list[str] | Secondary intents |

### PersonSearchResult (API response)

| Field | Type | Description |
|-------|------|-------------|
| id | str | Person ID |
| name | str \| null | Display name |
| headline | str \| null | Headline (e.g. current company / city) |
| bio | str \| null | Compact bio summary |
| similarity_percent | int \| null | Match score 0–100 |
| why_matched | list[str] | 1–3 reason strings |
| open_to_work | bool | Open to work flag |
| open_to_contact | bool | Open to contact flag |
| work_preferred_locations | list[str] | Shown when open_to_work |
| work_preferred_salary_min | number \| null | INR/year; shown when open_to_work |
| matched_cards | list[ExperienceCardResponse] | 1–3 best-matching parent experience cards (serialized via `experience_card_to_response`). When a person matches via child embedding, the parent card(s) containing that child are shown. |

### matched_cards item shape (parent only)

`matched_cards` contains only parent `ExperienceCard` objects. Each entry:
```json
{
  "id": "card-uuid",
  "title": "Backend Engineer",
  "company_name": "Acme Corp",
  "summary": "Built APIs and microservices...",
  "start_date": "2022-01",
  "end_date": "2024-06",
  "is_current": false,
  "domain": "...",
  "location": "..."
}
```

---

## Constants

| Constant | Value | Location |
|----------|-------|----------|
| WHY_REASON_MAX_LEN | 150 | why_matched_helpers.py |
| WHY_REASON_MAX_WORDS | 15 | why_matched_helpers.py |
| WHY_REASON_MAX_ITEMS | 3 | why_matched_helpers.py |
| EVIDENCE_SNIPPET_MAX_LEN | 150 | why_matched_helpers.py |
| EVIDENCE_STRING_MAX_LEN | 200 | why_matched_helpers.py |

---

## Async Refresh

If the inline LLM call does not run or fails:
- `_update_why_matched_async()` is scheduled.
- After ~1s, it re-calls `_generate_llm_why_matched()`.
- It updates `SearchResult.extra.why_matched` in the DB.
- Past searches can show improved reasons on next load.

---

## Files Involved

| File | Role |
|------|------|
| `search_logic.py` | Evidence building, LLM orchestration, persistence |
| `why_matched_helpers.py` | Payload cleanup, validation, fallback, `boost_query_matching_reasons` |
| `prompts/search_why_matched.py` | Prompt template |
| `schemas/search.py` | PersonSearchResult, ParsedConstraints* |
| `serializers.py` | `experience_card_to_response` for matched_cards |
| `person-result-card.tsx` | UI display of why_matched |
