# Experience Card Flow — Full Reference for AI

This document describes the **entire experience card flow**: from messy free-form text → rewrite → detection → extraction → validation → persistence → embedding → clarification and editing. It is intended for AI readers and maintainers who need to understand schema, prompts, function relationships, and data flow.

---

## Table of contents

1. [High-level flow](#1-high-level-flow)
2. [Schema: domain, DB, API, pipeline](#2-schema-domain-db-api-pipeline)
3. [Prompts: placeholders, inputs, and expected output schema](#3-prompts-placeholders-inputs-and-expected-output-schema)
4. [Function inputs and outputs](#4-function-inputs-and-outputs)
5. [Function map: who calls whom](#5-function-map-who-calls-whom)
6. [Messy text → embedding pipeline (step-by-step)](#6-messy-text--embedding-pipeline-step-by-step)
7. [Clarify flow (Q&A and autofill)](#7-clarify-flow-qa-and-autofill)
8. [Edit flow: fill missing, patch, finalize, re-embed](#8-edit-flow-fill-missing-patch-finalize-re-embed)
9. [Search document and embedding text](#9-search-document-and-embedding-text)
10. [Key files index](#10-key-files-index)

---

## 1. High-level flow

```
User enters messy text (Builder Chat / edit form)
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  REWRITE (PROMPT_REWRITE)                                                 │
│  Clean, grammatical English; no new facts; preserve names/numbers.        │
│  Cached by SHA-256 of input.                                              │
└──────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  DETECT EXPERIENCES (PROMPT_DETECT_EXPERIENCES)                           │
│  Count + labels for each distinct experience (job/role/project).          │
│  One experience marked "suggested".                                       │
└──────────────────────────────────────────────────────────────────────────┘
       │
       ▼  (user may choose which experience to extract)
       │
┌──────────────────────────────────────────────────────────────────────────┐
│  EXTRACT SINGLE (PROMPT_EXTRACT_SINGLE_CARDS)                              │
│  One parent + children (by index). Child types from ALLOWED_CHILD_TYPES.  │
│  Child value: { raw_text, items[] } with items = { title, description }.  │
└──────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PARSE & VALIDATE                                                         │
│  parse_llm_response_to_families → Family list; inject_metadata.          │
└──────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PERSIST                                                                  │
│  RawExperience + DraftSet; card_to_experience_card_fields /               │
│  card_to_child_fields → persist_families (DB).                            │
└──────────────────────────────────────────────────────────────────────────┘
       │
       ▼
Optional: CLARIFY (planner → question writer / apply answer) → merge patch into canonical family.
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  FINALIZE (when user approves draft)                                      │
│  POST /experience-cards/finalize → embed_experience_cards:                │
│  build_embedding_inputs (derived search text) → fetch_embedding_vectors   │
│  → assign to card.embedding; flush. Cards become visible/searchable.      │
└──────────────────────────────────────────────────────────────────────────┘
       │
       ▼
Optional: EDIT (fill missing from text, or PATCH) → re-embed (search text derived at embed time).
```

---

## 2. Schema: domain, DB, API, pipeline

### 2.1 Domain enums (single source of truth)

**File:** `apps/api/src/domain.py`

| Name | Type | Values (exact list) |
|------|------|------------------------|
| **Intent** | `Literal[...]` | work, education, project, business, research, practice, exposure, achievement, transition, learning, life_context, community, finance, other, mixed |
| **ChildRelationType** | `Literal[...]` | describes, supports, demonstrates, results_in, learned_from, involves, part_of |
| **ChildIntent** | `Literal[...]` | responsibility, capability, method, outcome, learning, challenge, decision, evidence |
| **SeniorityLevel** | `Literal[...]` | intern, junior, mid, senior, lead, principal, staff, manager, director, vp, executive, founder, independent, volunteer, student, apprentice, owner, other |
| **EmploymentType** | `Literal[...]` | full_time, part_time, contract, freelance, internship, volunteer, self_employed, founder, apprenticeship, family_business, daily_wage, gig, other |
| **CompanyType** | `Literal[...]` | startup, scaleup, mnc, sme, agency, ngo, government, university, research_institution, self_employed, cooperative, family_business, informal, master_apprentice, other |
| **ExperienceRelationType** | `Literal[...]` | parallel, sequential, nested, transitional |
| **ALLOWED_CHILD_TYPES** | `tuple[str, ...]` | skills, tools, metrics, achievements, responsibilities, collaborations, domain_knowledge, exposure, education, certifications |
| **ENTITY_TAXONOMY** | `list[str]` | person, organization, company, school, team, community, place, event, program, domain, industry, product, service, artifact, document, portfolio_item, credential, award, tool, equipment, system, platform, instrument, method, process |

**Intent (full list):** `"work" | "education" | "project" | "business" | "research" | "practice" | "exposure" | "achievement" | "transition" | "learning" | "life_context" | "community" | "finance" | "other" | "mixed"`

**ChildRelationType (full list):** `"describes" | "supports" | "demonstrates" | "results_in" | "learned_from" | "involves" | "part_of"`

**ChildIntent (full list):** `"responsibility" | "capability" | "method" | "outcome" | "learning" | "challenge" | "decision" | "evidence"`

**SeniorityLevel (full list):** `"intern" | "junior" | "mid" | "senior" | "lead" | "principal" | "staff" | "manager" | "director" | "vp" | "executive" | "founder" | "independent" | "volunteer" | "student" | "apprentice" | "owner" | "other"`

**EmploymentType (full list):** `"full_time" | "part_time" | "contract" | "freelance" | "internship" | "volunteer" | "self_employed" | "founder" | "apprenticeship" | "family_business" | "daily_wage" | "gig" | "other"`

**CompanyType (full list):** `"startup" | "scaleup" | "mnc" | "sme" | "agency" | "ngo" | "government" | "university" | "research_institution" | "self_employed" | "cooperative" | "family_business" | "informal" | "master_apprentice" | "other"`

**ALLOWED_CHILD_TYPES (full list):** `("skills", "tools", "metrics", "achievements", "responsibilities", "collaborations", "domain_knowledge", "exposure", "education", "certifications")`

**ENTITY_TAXONOMY (full list):** person, organization, company, school, team, community, place, event, program, domain, industry, product, service, artifact, document, portfolio_item, credential, award, tool, equipment, system, platform, instrument, method, process

Prompt-facing strings are built in `apps/api/src/prompts/experience_card_enums.py` (derived from `domain.py`):

- `INTENT_ENUM`, `CHILD_INTENT_ENUM`, `CHILD_RELATION_TYPE_ENUM`, `ENTITY_TYPES`, `ALLOWED_CHILD_TYPES_STR`  
- `SENIORITY_LEVEL_ENUM`, `EMPLOYMENT_TYPE_ENUM`, `COMPANY_TYPE_ENUM`, `EXPERIENCE_RELATION_TYPE_ENUM`  

These are injected into prompt templates via `fill_prompt()`.

### 2.2 Database models

**File:** `apps/api/src/db/models.py`

**RawExperience**

- `id`, `person_id`, `raw_text`, `raw_text_original`, `raw_text_cleaned`, `created_at`

**DraftSet**

- `id`, `person_id`, `raw_experience_id`, `run_version`, `extra_metadata`, `created_at`

**ExperienceCard (parent)**

- `id`, `person_id`, `draft_set_id`, `user_id` (synonym for person_id)
- Content: `title`, `normalized_role`, `domain`, `domain_norm` (indexed), `sub_domain`, `sub_domain_norm` (indexed), `company_name`, `company_norm` (indexed), `company_type`, `team`, `team_norm` (indexed), `start_date`, `end_date`, `is_current`, `location`, `city`, `country`, `is_remote`, `employment_type`, `summary`, `raw_text`, `intent_primary`, `intent_secondary` (ARRAY), `seniority_level`, `confidence_score`, `experience_card_visibility`
- Embed: `embedding` (Vector(324)) — search text is derived via `build_parent_search_document(card)`, no stored column
- `created_at`, `updated_at`

The `*_norm` columns (`domain_norm`, `sub_domain_norm`, `company_norm`, `team_norm`) are lowercased/trimmed versions stored for efficient indexed filtering. They are set automatically in `card_to_experience_card_fields`.

**ExperienceCardChild**

- `id`, `parent_experience_id`, `person_id`, `raw_experience_id`, `draft_set_id`
- `child_type` (one of ALLOWED_CHILD_TYPES), `value` (JSONB dimension container: `{ raw_text, items[] }`)
- `confidence_score`, `embedding` (Vector(324)), `extra`, `created_at`, `updated_at`
- Search text is derived via `get_child_search_document(child)` from value (label from `get_child_label(value, child_type)` in `child_value.py`); no stored `label` column (removed in migration 028).
- Unique constraint: one child per `(parent_experience_id, child_type)`.

Relationship: one **ExperienceCard** has many **ExperienceCardChild**; children reference parent via `parent_experience_id`.

### 2.3 API request/response schemas (builder)

**File:** `apps/api/src/schemas/builder.py`

**Request schemas (input to API):**

| Schema | Fields (all that are sent in request body) |
|--------|-------------------------------------------|
| **RawExperienceCreate** | `raw_text: str` |
| **DraftSingleRequest** | `raw_text: str`, `experience_index: int = 1`, `experience_count: int = 1` |
| **ClarifyExperienceRequest** | `raw_text: str`, `card_type: str = "parent"`, `current_card: dict = {}`, `conversation_history: list[ClarifyMessage] = []`, `card_id: Optional[str]`, `child_id: Optional[str]`, `card_family: Optional[dict]`, `card_families: Optional[list[dict]]`, `detected_experiences: Optional[list[dict]]`, `focus_parent_id: Optional[str]`, `asked_history: Optional[list[dict]]`, `last_question_target: Optional[dict]`, `max_parent_questions: Optional[int]`, `max_child_questions: Optional[int]` |
| **ClarifyMessage** | `role: str` ("assistant" \| "user"), `content: str` |
| **ClarifyHistoryMessage** | `role: str`, `kind: str` ("clarify_question" \| "clarify_answer"), `target_type: Optional[str]`, `target_field: Optional[str]`, `target_child_type: Optional[str]`, `text: str` |
| **LastQuestionTarget** | `target_type: Optional[str]`, `target_field: Optional[str]`, `target_child_type: Optional[str]` |
| **FillFromTextRequest** | `raw_text: str`, `card_type: str = "parent"`, `current_card: dict = {}`, `card_id: Optional[str]`, `child_id: Optional[str]` |
| **ExperienceCardPatch** | All optional: `title`, `normalized_role`, `domain`, `sub_domain`, `company_name`, `company_type`, `start_date`, `end_date`, `is_current`, `location` (dict: city, region, country, text, is_remote), `is_remote`, `employment_type`, `summary`, `raw_text`, `intent_primary`, `intent_secondary`, `seniority_level`, `confidence_score`, `experience_card_visibility` |
| **ExperienceCardChildPatch** | `items: Optional[list[dict]]` — list of `{ title: str, description: str \| None }`. |
| **FinalizeExperienceCardRequest** | `card_id: str` — request body for `POST /experience-cards/finalize`. |

**Response schemas (output from API):**

| Schema | Fields (returned to client) |
|--------|-----------------------------|
| **DetectExperiencesResponse** | `count: int = 0`, `experiences: list[DetectedExperienceItem]` where each item has `index: int`, `label: str`, `suggested: bool = False` |
| **DraftSetResponse** | `draft_set_id: str`, `raw_experience_id: str`, `card_families: list[DraftCardFamily]` |
| **DraftCardFamily** | `parent: dict`, `children: list[dict]` — each card in API response shape |
| **ClarifyExperienceResponse** | `clarifying_question: Optional[str]`, `filled: dict = {}`, `action: Optional[str]`, `message: Optional[str]`, `options: Optional[list[dict]]`, `focus_parent_id: Optional[str]`, `should_stop: Optional[bool]`, `stop_reason: Optional[str]`, `target_type`, `target_field`, `target_child_type`, `progress: Optional[dict]`, `missing_fields: Optional[dict]`, `asked_history_entry: Optional[dict]`, `canonical_family: Optional[dict]` |
| **FillFromTextResponse** | `filled: dict` (only keys that were extracted) |
| **ExperienceCardResponse** | `id`, `user_id`, `title`, `normalized_role`, `domain`, `sub_domain`, `company_name`, `company_type`, `team`, `start_date`, `end_date`, `is_current`, `location`, `is_remote`, `employment_type`, `summary`, `raw_text`, `intent_primary`, `intent_secondary`, `seniority_level`, `confidence_score`, `experience_card_visibility`, `created_at`, `updated_at` |
| **ExperienceCardChildResponse** | `id`, `parent_experience_id`, `child_type`, `items` (list of `ChildValueItem`: `{ title: str, description: Optional[str] }`). |
| **CardFamilyResponse** | `parent: ExperienceCardResponse`, `children: list[ExperienceCardChildResponse]` |

### 2.4 Pipeline internal models (Card, Family)

**File:** `apps/api/src/services/experience/pipeline.py`

**Nested models (used inside Card):**

| Model | Fields |
|-------|--------|
| **TimeInfo** | `text: Optional[str]`, `start: Optional[str]` (YYYY-MM or YYYY-MM-DD), `end: Optional[str]`, `ongoing: Optional[bool]` |
| **LocationInfo** | `text: Optional[str]`, `city: Optional[str]`, `country: Optional[str]`, `is_remote: Optional[bool]` |
| **RoleInfo** | `label: Optional[str]`, `seniority: Optional[str]` |
| **EntityInfo** | `type: str` (e.g. company, team, organization), `name: str` |

**Card** (Pydantic) — full field list:

| Category | Field | Type |
|----------|--------|------|
| Identity | id | Optional[str] |
| | person_id | Optional[str] |
| | created_by | Optional[str] |
| | created_at | Optional[str] |
| | updated_at | Optional[str] |
| | parent_id | Optional[str] |
| | depth | Optional[int] (0=parent, 1=child) |
| | relation_type | Optional[str] |
| | child_type | Optional[str] (one of ALLOWED_CHILD_TYPES) |
| Display | headline | Optional[str] |
| | title | Optional[str] |
| | label | Optional[str] |
| | summary | Optional[str] |
| | raw_text | Optional[str] |
| Time | time | Optional[TimeInfo \| str] |
| | time_text | Optional[str] |
| | start_date | Optional[str] |
| | end_date | Optional[str] |
| | is_current | Optional[bool] |
| Place | location | Optional[LocationInfo \| str] |
| | city | Optional[str] |
| | country | Optional[str] |
| Role/org | roles | list[RoleInfo] |
| | normalized_role | Optional[str] |
| | seniority_level | Optional[str] |
| | company | Optional[str] |
| | company_name | Optional[str] |
| | organization | Optional[str] |
| | team | Optional[str] |
| Domain | domain | Optional[str] |
| | sub_domain | Optional[str] |
| | company_type | Optional[str] |
| | employment_type | Optional[str] |
| Structure | entities | list[EntityInfo] |
| | actions | list[dict] |
| | outcomes | list[dict] |
| | evidence | list[dict] |
| | tooling | Optional[Any] |
| | items | list[dict] — child card items: `[{ title, description }]` |
| Intent | intent | Optional[str] |
| | intent_primary | Optional[str] |
| | intent_secondary | list[str] |
| | confidence_score | Optional[float] |

Validators: prompt-style keys are normalized (intent_primary→intent, company_name→company, start_date/end_date→time object, roles from normalized_role, intent_secondary string→list, list normalizers for roles/entities/actions/outcomes/evidence). Child `value.items` from LLM extraction are mapped into `card.items`.

**Family**: `parent: Card`, `children: list[Card]`.

**Child dimension container (value)** — JSONB stored in ExperienceCardChild.value; built from Card in `card_to_child_fields`. Canonical shape (`child_value.py`):

```json
{
  "raw_text": "string|null",
  "items": [
    { "title": "short label", "description": "one line or null" }
  ]
}
```

Note: `normalize_child_items` in `child_value.py` accepts `title` or `description` for items.

### 2.5 LLM output schemas (expected JSON shapes)

Exact shapes the pipeline expects from each LLM response (after stripping fences and extracting JSON).

**Detect experiences:**

```json
{
  "count": 2,
  "experiences": [
    { "index": 1, "label": "Razorpay, backend, 2 years", "suggested": false },
    { "index": 2, "label": "Google, SRE, 2020-2022", "suggested": true }
  ]
}
```

Exactly one item must have `"suggested": true`.

**Extract single (one family):**

```json
{
  "parents": [
    {
      "parent": {
        "title": "...",
        "normalized_role": "...",
        "domain": "...",
        "sub_domain": "...",
        "company_name": "...",
        "company_type": "startup",
        "team": "...",
        "location": { "city": "...", "region": "...", "country": "...", "text": "...", "is_remote": false },
        "employment_type": "full_time",
        "start_date": "2020-01",
        "end_date": "2022-06",
        "is_current": false,
        "summary": "...",
        "intent_primary": "work",
        "intent_secondary": [],
        "seniority_level": "senior",
        "raw_text": "verbatim excerpt for this experience only",
        "confidence_score": 0.9,
        "relations": []
      },
      "children": [
        {
          "child_type": "tools",
          "value": {
            "raw_text": "verbatim excerpt for this child only",
            "items": [
              { "title": "Python", "description": "Used for backend services." },
              { "title": "Bloomberg API", "description": null }
            ]
          }
        }
      ]
    }
  ]
}
```

Parent: intent_primary from Intent enum; company_type from CompanyType; employment_type from EmploymentType; seniority_level from SeniorityLevel. relations always []. Children: child_type one of ALLOWED_CHILD_TYPES; no top-level `label` field on children; value has `raw_text` and `items[]` with `{ title, description }`. One child per child_type.

**Fill missing fields:**

Single object, only keys that were missing and could be filled. Example: `{ "company_name": "ABC Inc", "start_date": "2020-01", "end_date": "2022-06" }`. No wrapper array.

**Clarify planner:**

```json
{
  "action": "ask",
  "target_type": "parent",
  "target_field": "company_name",
  "target_child_type": null,
  "reason": "Company not set",
  "confidence": "high",
  "autofill_patch": null
}
```

Allowed: action ∈ {"ask","autofill","stop"}, target_type ∈ {"parent","child",null}. When action=autofill, autofill_patch is e.g. `{"company_name": "X"}` or `{"location": {"is_remote": true, "city": null}}`.

**Clarify question writer:**

Plain text only — one short, natural question. No JSON wrapper. Example: `"Which company was this at?"`

**Clarify apply answer:**

```json
{
  "patch": { "company_name": "Acme Corp" },
  "confidence": "high",
  "needs_retry": false,
  "retry_question": null
}
```

For time: patch may have `time: { start, end, ongoing, text }`. For location: `location: { text, city, country, is_remote }`. For child dimensions: `patch.value.items` = list of `{ title, description }` to append. If needs_retry is true, retry_question is one short question.

---

## 3. Prompts: placeholders, inputs, and expected output schema

**File:** `apps/api/src/prompts/experience_card.py`  
**Filler:** `fill_prompt(template, **kwargs)` — replaces placeholders. Enums are auto-injected via `_DEFAULT_REPLACEMENTS` (from `experience_card_enums`): INTENT_ENUM, CHILD_INTENT_ENUM, CHILD_RELATION_TYPE_ENUM, ALLOWED_CHILD_TYPES_STR, COMPANY_TYPE_ENUM, EMPLOYMENT_TYPE_ENUM, SENIORITY_LEVEL_ENUM.

### 3.1 PROMPT_REWRITE

| Item | Detail |
|------|--------|
| **Placeholders** | `{{USER_TEXT}}` |
| **What is passed** | `user_text=raw_text` (the raw user message) |
| **Expected output** | Plain text only. No JSON. Cleaned, grammatical English; same facts; no commentary. |

**Full prompt text:**

```
You are a rewrite and cleanup engine. Your only job is to make the input easier to parse — not to interpret, summarize, or enrich it.

GOAL:
Rewrite the input into clear, grammatically correct English. Remove noise. Preserve all meaning and facts exactly as given.

RULES:
1. Do NOT add facts, infer missing details, or change meaning in any way.
2. Keep all proper nouns, names, places, organizations, tools, numbers, and dates exactly as written.
3. Preserve structure — if the input has a list, keep it a list. If it has an order, keep that order.
4. Expand abbreviations only when the expansion is unambiguous.
5. Remove filler words, repetition, typos, and grammatical noise.
6. If the input is already clean, return it as-is. Do not rephrase for the sake of it.
7. Output ONLY the rewritten text. No explanations, no commentary, no JSON, no preamble.

INPUT:
{{USER_TEXT}}
```

### 3.2 PROMPT_DETECT_EXPERIENCES

| Item | Detail |
|------|--------|
| **Placeholders** | `{{CLEANED_TEXT}}` |
| **What is passed** | `cleaned_text=<output of rewrite_raw_text>` |
| **Expected output** | Valid JSON only. Shape: `{ "count": number, "experiences": [ { "index": number, "label": string, "suggested": boolean }, ... ] }`. Exactly one experience must have `suggested: true`. |

**Full prompt text (abbreviated):**

```
You are an experience detection engine.

Read the cleaned text below and identify every DISTINCT experience block — any bounded period of activity tied to a role, project, organization, or pursuit. This includes jobs, freelance work, education, side projects, business ventures, research, or any other meaningful engagement.

RULES:
1. Each distinct role, organization, or project = one experience.
2. Split on: different employers or clients, different projects, "then", "after that", "also", "another role", "meanwhile", or different time ranges.
3. Do NOT merge experiences that happened in parallel if they are clearly distinct.
4. Do NOT split a single experience just because the person changed responsibilities within the same role/org.
5. If no experiences are found, return count 0 and an empty array.
6. Return ONLY valid JSON. No markdown, no commentary, no preamble.

OUTPUT FORMAT: { "count": N, "experiences": [ { "index": 1, "label": "...", "suggested": false }, ... ] }
- Set "suggested": true for exactly ONE experience. Prefer the one with the most structured detail.

CLEANED TEXT:
{{CLEANED_TEXT}}

Return valid JSON only:
```

### 3.3 PROMPT_EXTRACT_SINGLE_CARDS

| Item | Detail |
|------|--------|
| **Placeholders** | `{{USER_TEXT}}`, `{{EXPERIENCE_INDEX}}`, `{{EXPERIENCE_COUNT}}`, plus auto-injected: `{{INTENT_ENUM}}`, `{{ALLOWED_CHILD_TYPES}}`, `{{COMPANY_TYPE_ENUM}}`, `{{EMPLOYMENT_TYPE_ENUM}}`, `{{SENIORITY_LEVEL_ENUM}}` |
| **What is passed** | `user_text=raw_text_cleaned`, `experience_index=idx` (1-based), `experience_count=total`. Enums from `_DEFAULT_REPLACEMENTS` in experience_card.py. |
| **Expected output** | Valid JSON. Shape: `{ "parents": [ { "parent": { ... }, "children": [ ... ] } ] }` with exactly one family. **parent** keys: title, normalized_role, domain, sub_domain, company_name, company_type, team, location (object: city, region, country, text, is_remote), employment_type, start_date, end_date, is_current, summary, intent_primary, intent_secondary, seniority_level, raw_text, confidence_score, relations (always []). **children** each have: child_type (one of ALLOWED_CHILD_TYPES), value: { raw_text, items[] } with items = { title, description }. No top-level `label` on children. One child per child_type. |

**Prompt summary (see experience_card.py for full text):**

- Extract ONLY the experience at position {{EXPERIENCE_INDEX}} of {{EXPERIENCE_COUNT}}.
- Parent: company_type from {{COMPANY_TYPE_ENUM}}, employment_type from {{EMPLOYMENT_TYPE_ENUM}}, intent_primary from {{INTENT_ENUM}}, seniority_level from {{SENIORITY_LEVEL_ENUM}}.
- Children: child_type from {{ALLOWED_CHILD_TYPES}}. Value has raw_text and items[] with `{ title, description }`. No top-level `label` field.
- Dates: YYYY-MM or YYYY-MM-DD only. relations always [].
- Company type guidance: informal trade → "informal"; family business → "family_business"; master/ustaad apprentice → "master_apprentice"; independent → "self_employed".

### 3.4 PROMPT_FILL_MISSING_FIELDS

| Item | Detail |
|------|--------|
| **Placeholders** | `{{ALLOWED_KEYS}}`, `{{CURRENT_CARD_JSON}}`, `{{CLEANED_TEXT}}` |
| **What is passed** | `allowed_keys=FILL_MISSING_PARENT_KEYS` or `FILL_MISSING_CHILD_KEYS`, `current_card_json=json.dumps(current_card)`, `cleaned_text=<output of rewrite>` |
| **Expected output** | Single JSON object. Only keys that were missing in current_card and could be filled from text. No array, no markdown. Dates as YYYY-MM-DD or YYYY-MM. Array fields (intent_secondary) as JSON array of strings. |

**Allowed keys (parent):** `title, summary, normalized_role, domain, sub_domain, company_name, company_type, location, employment_type, start_date, end_date, is_current, intent_primary, intent_secondary_str, seniority_level, confidence_score`

**Allowed keys (child):** `raw_text, items` (items = list of `{ title, description }`)

**Prompt summary:** Targeted field-filling extractor. Extract values ONLY for empty/null fields. Do NOT overwrite. Return single flat JSON object. See experience_card.py for full text.

### 3.5 PROMPT_CLARIFY_PLANNER

| Item | Detail |
|------|--------|
| **Placeholders** | `{{CANONICAL_CARD_JSON}}`, `{{CLEANED_TEXT}}`, `{{ASKED_HISTORY_JSON}}`, `{{MAX_PARENT}}`, `{{MAX_CHILD}}`, `{{PARENT_ASKED_COUNT}}`, `{{CHILD_ASKED_COUNT}}` |
| **What is passed** | `canonical_card_json=json.dumps(canonical_family)`, `cleaned_text=...`, `asked_history_json=json.dumps(asked_history)`, `max_parent`, `max_child`, `parent_asked_count`, `child_asked_count` |
| **Expected output** | One JSON object: `{ "action": "ask"|"autofill"|"stop", "target_type": "parent"|"child"|null, "target_field": string|null, "target_child_type": string|null, "reason": string, "confidence": "high"|"medium"|"low", "autofill_patch": object|null }`. When action=autofill, autofill_patch contains only the target field(s). |

**Allowed parent target_field:** title, role, summary, company_name, team, time, location, location.is_remote, domain, sub_domain, intent_primary, seniority_level, employment_type, company_type  
**Allowed target_child_type:** skills, tools, metrics, achievements, responsibilities, collaborations, domain_knowledge, exposure, education, certifications

**Priority order:**
1. Parent fields: title/role → summary → company_name → employment_type → company_type → time → location.city → location.is_remote → domain → intent_primary → seniority_level
2. Child fields (if limits allow): metrics → tools → achievements → responsibilities → collaborations → domain_knowledge → exposure → education → certifications

**Inapplicability rules (set to null, never ask):**
- company_name, team → null when freelance/self-employed/independent
- end_date → null when explicitly ongoing
- location.city/region → null when explicitly fully remote with no base
- seniority_level → null when non-hierarchical (volunteer, hobbyist, student)
- relations → NEVER ask (handled separately)

**Full prompt text:**

```
You are a clarification planner. A card has already been extracted. Your only job is to decide the single best next action: ask, autofill, or stop.

ACTIONS:
"ask"      → a field is missing, applicable, and not yet asked
"autofill" → the text explicitly and unambiguously contains the value
"stop"     → nothing more worth extracting, all applicable fields resolved, or limits reached

STOP CONDITION:
Stop when ALL of the following are true:
- Every applicable field has a value, OR has already been asked, OR has been set to null as inapplicable
- No high-value child dimensions remain unasked within limits
- Limits are reached

Do NOT stop early. Extract as much relevant and applicable data as possible.

INAPPLICABILITY RULES:
When a field does not apply given the nature of the experience, set it to null silently. Never ask about it.
Examples:
- company_name, team      → null when person is freelance, self-employed, or independent
- end_date                → null when experience is explicitly ongoing
- location.city/region    → null when experience is explicitly fully remote with no base
- seniority_level         → null when experience is non-hierarchical (volunteer, hobbyist, student)
- employment_type         → null when context makes categorization meaningless
- relations               → NEVER ask — handled separately after all cards exist

PRIORITY ORDER:
1. Parent fields: title/role → summary → company_name → employment_type → company_type →
                  time → location.city → location.is_remote → domain → intent_primary →
                  seniority_level
2. Child fields (if limits allow): metrics → tools → achievements → responsibilities →
                  collaborations → domain_knowledge → exposure → education → certifications

RULES:
1. Ask at most ONE thing per turn. Never combine questions.
2. Never ask about a field in asked_history.
3. Never ask about a field already filled in the card.
4. Never ask about an inapplicable field — set it to null instead.
5. Never ask about relations — handled after all cards exist.
6. Never ask generic or open-ended questions ("tell me more", "what did you build").
7. AUTOFILL only when text explicitly and unambiguously states the value.
8. autofill_patch must contain ONLY the target field.
9. Never propose choose_focus or discovery actions — handled upstream.

ALLOWED VALUES:
action: "ask" | "autofill" | "stop"
target_type: "parent" | "child" | null
parent target_field: title, role, summary, company_name, team, time, location,
  location.is_remote, domain, sub_domain, intent_primary, seniority_level, employment_type, company_type
target_child_type: metrics, tools, achievements, responsibilities, collaborations,
  domain_knowledge, exposure, education, certifications

OUTPUT FORMAT (return this JSON object only):
{
  "action": "ask | autofill | stop",
  "target_type": "parent | child | null",
  "target_field": "<field name> | null",
  "target_child_type": "<child type> | null",
  "reason": "<one short sentence explaining why>",
  "confidence": "high | medium | low",
  "autofill_patch": null
}

Canonical card family:
{{CANONICAL_CARD_JSON}}

Cleaned experience text:
{{CLEANED_TEXT}}

Asked history (do not repeat these):
{{ASKED_HISTORY_JSON}}

Limits: max parent = {{MAX_PARENT}}, max child = {{MAX_CHILD}}. Parent asked: {{PARENT_ASKED_COUNT}}, child asked: {{CHILD_ASKED_COUNT}}.

Return valid JSON only:
```

### 3.6 PROMPT_CLARIFY_QUESTION_WRITER

| Item | Detail |
|------|--------|
| **Placeholders** | `{{CLARIFY_PLAN_JSON}}`, `{{CANONICAL_CARD_JSON}}` |
| **What is passed** | `validated_plan_json=json.dumps({ action, target_type, target_field, target_child_type, reason })` (mapped to both `{{CLARIFY_PLAN_JSON}}` and `{{VALIDATED_PLAN_JSON}}`), `card_context_json=json.dumps(canonical_family)` (mapped to `{{CANONICAL_CARD_JSON}}`) |
| **Expected output** | **Plain text only** — one short, natural, conversational question. No JSON, no preamble, no formatting. |

**Full prompt text:**

```
You are a clarification question writer. A planner has decided what to ask next. Your only job is to write exactly one natural, conversational question.

RULES:
1. Write ONE question only. Never combine multiple questions.
2. Be conversational and brief — this is a chat interface, not a form.
3. The question must target ONLY the field or child type specified in the plan.
4. Never ask generic questions ("tell me more", "anything else?").
5. For parent fields: ask directly and specifically about that field.
6. For child dimensions: invite the user to list multiple things naturally.
   - Good: "Which tools or technologies did you use in this role?"
   - Bad:  "Please list your tools."
7. Reference card context naturally to make the question feel informed, not robotic.
8. Do NOT explain why you are asking. Just ask.
9. Output the question as plain text only. No JSON, no preamble, no formatting.

PLAN:
{{CLARIFY_PLAN_JSON}}

CANONICAL CARD FAMILY (for context):
{{CANONICAL_CARD_JSON}}

Write the question now:
```

### 3.7 PROMPT_CLARIFY_APPLY_ANSWER

| Item | Detail |
|------|--------|
| **Placeholders** | `{{VALIDATED_PLAN_JSON}}`, `{{USER_ANSWER}}`, `{{CANONICAL_CARD_JSON}}` |
| **What is passed** | `validated_plan_json=...`, `user_answer=<last user message text>`, `canonical_card_json=json.dumps(canonical_family)` |
| **Expected output** | JSON: `{ "patch": object, "confidence": "high"|"medium"|"low", "needs_retry": boolean, "retry_question": string|null }`. Patch updates only the target field. For child dimensions: `patch.value.items` = list of `{ title, description }`. If needs_retry is true, retry_question is one short question. |

**Full prompt text:**

```
You are a clarification answer processor. Convert the user's answer into a minimal patch for the experience card. You ONLY update the target field — nothing else.

RULES:
1. Patch ONLY the target field specified in the plan. Never touch other fields.
2. For nested fields, patch only the relevant sub-fields:
   - time     → time.start, time.end, time.ongoing, time.text
   - location → location.city, location.country, location.is_remote, location.text
3. Preserve the user's original wording where appropriate. Do not paraphrase.
4. Do NOT hallucinate. If the user's answer does not contain the value, do not invent it.
5. If the user indicates the field is not applicable → set field to null.
6. If the answer is unclear, off-topic, or unusable → set needs_retry: true, write one short retry_question.
7. Dates MUST be YYYY-MM or YYYY-MM-DD only.
8. Return valid JSON only. No markdown, no commentary, no preamble.

OUTPUT FORMAT:
{
  "patch": { ... only target field updates ... },
  "confidence": "high | medium | low",
  "needs_retry": false,
  "retry_question": null
}

For child dimensions (target_child_type set), patch adds items to that child:
{
  "patch": {
    "value": {
      "items": [
        { "title": "Python", "description": "Used for analytics" },
        { "title": "SQL", "description": "Used for analytics" }
      ]
    }
  },
  "confidence": "high",
  "needs_retry": false,
  "retry_question": null
}

Examples:

Target = time, user says "Jan 2020 to March 2022":
{ "patch": { "time": { "start": "2020-01", "end": "2022-03", "ongoing": false, "text": "Jan 2020 to March 2022" } }, "confidence": "high", "needs_retry": false, "retry_question": null }

Target = company_name, user says "I was freelancing, no company":
{ "patch": { "company_name": null }, "confidence": "high", "needs_retry": false, "retry_question": null }

Target = time, user says "about 2 years":
{ "patch": {}, "confidence": "low", "needs_retry": true, "retry_question": "Do you remember roughly when you started and ended?" }

VALIDATED PLAN:
{{VALIDATED_PLAN_JSON}}

USER'S ANSWER:
{{USER_ANSWER}}

CANONICAL CARD (for context):
{{CANONICAL_CARD_JSON}}

Return valid JSON only:
```

---

## 4. Function inputs and outputs

Each row: function name, **inputs** (parameter → type/source), **output** (type and shape).

### 4.1 Public pipeline API (pipeline.py)

| Function | Inputs | Output |
|----------|--------|--------|
| **rewrite_raw_text** | `raw_text: str` (user message) | `str` — cleaned English text. Raises HTTPException 400 if empty; PipelineError on LLM failure. |
| **detect_experiences** | `raw_text: str` | `dict` — `{ "count": int, "experiences": [ { "index": int, "label": str, "suggested": bool }, ... ] }`. On parse failure returns `{"count": 0, "experiences": []}`. |
| **run_draft_single** | `db: AsyncSession`, `person_id: str`, `raw_text: str`, `experience_index: int`, `experience_count: int` | `tuple[str, str, list[dict]]` — `(draft_set_id, raw_experience_id, card_families)`. Each family: `{ "parent": dict, "children": list[dict] }` (serialize_card_for_response shape). Does NOT embed; embedding deferred to finalize. Raises HTTPException 400 if empty raw_text; ChatServiceError/PipelineError on failure. |
| **fill_missing_fields_from_text** | `raw_text: str`, `current_card: dict`, `card_type: str` ("parent" \| "child") | `dict` — only keys that were filled (e.g. title, company_name, start_date). Empty dict on parse failure or empty response. |
| **clarify_experience_interactive** | `raw_text: str`, `current_card: dict`, `card_type: str`, `conversation_history: list[dict]`, optional: `card_family`, `asked_history_structured`, `last_question_target`, `max_parent`, `max_child`, `card_families`, `focus_parent_id`, `detected_experiences` | `dict` — ClarifyExperienceResponse-like: `clarifying_question`, `filled`, `should_stop`, `stop_reason`, `target_type`, `target_field`, `target_child_type`, `progress`, `missing_fields`, `asked_history_entry`, `canonical_family`; or `action: "choose_focus"`, `message`, `options` when multiple experiences and no focus. |

### 4.2 Parsing and persistence (pipeline.py)

| Function | Inputs | Output |
|----------|--------|--------|
| **parse_llm_response_to_families** | `response_text: str` (LLM reply), `stage: PipelineStage` | `list[Family]`. Raises PipelineError if no valid JSON or no valid families. |
| **inject_metadata_into_family** | `family: Family`, `person_id: str` | `Family` (mutated in place; ids, person_id, created_at, updated_at, parent_id, depth set). |
| **persist_families** | `db: AsyncSession`, `families: list[Family]`, `person_id: str`, `raw_experience_id: str`, `draft_set_id: str` | `tuple[list[ExperienceCard], list[ExperienceCardChild]]`. Raises PipelineError on DB failure. |
| **card_to_experience_card_fields** | `card: Card`, `person_id`, `raw_experience_id`, `draft_set_id` | `dict` — kwargs for ExperienceCard constructor (user_id, raw_text, title, normalized_role, domain, domain_norm, company_name, company_norm, team, team_norm, start_date, end_date, summary, etc.). |
| **card_to_child_fields** | `card: Card`, `person_id`, `raw_experience_id`, `draft_set_id`, `parent_id` | `dict` — kwargs for ExperienceCardChild constructor (parent_experience_id, child_type, value with { raw_text, items: [{ title, description }] }, embedding=None, etc.). |
| **serialize_card_for_response** | `card: ExperienceCard \| ExperienceCardChild` | `dict` — Parent: id, user_id, title, normalized_role, domain, sub_domain, company_name, company_type, team, start_date, end_date, is_current, location, is_remote, employment_type, summary, raw_text, intent_primary, intent_secondary, seniority_level, confidence_score, experience_card_visibility, created_at, updated_at. Child: id, parent_experience_id, child_type, items (list of `{ title, description }`). |

### 4.3 Embedding (embedding.py)

| Function | Inputs | Output |
|----------|--------|--------|
| **build_embedding_inputs** | `parents: list[ExperienceCard]`, `children: list[ExperienceCardChild]` | `list[EmbeddingInput]` — each has `.text: str` (derived via build_parent_search_document / get_child_search_document), `.target: ExperienceCard | ExperienceCardChild`. Order: all parents, then all children. |
| **fetch_embedding_vectors** | `texts: list[str]` | `list[list[float]]` — normalized vectors, same order as texts. Raises EmbeddingServiceError on provider failure. |
| **embed_experience_cards** | `db: AsyncSession`, `parents: list[ExperienceCard]`, `children: list[ExperienceCardChild]` | `None`. Mutates each card's `.embedding`; calls `db.flush()`. Raises PipelineError on dimension mismatch or provider failure. |

### 4.4 Clarify helpers (clarify.py vs pipeline.py)

| Function | Inputs | Output |
|----------|--------|--------|
| **normalize_card_family_for_clarify** | `card_family: dict` (parent + children, any shape) | `dict` — `{ "parent": {...}, "children": [...] }` canonical (time/location as objects, headline/role/summary normalized). |
| **validate_clarify_plan** | `plan: ClarifyPlan | None`, `canonical_family: dict`, `asked_history: list`, `parent_asked_count`, `child_asked_count`, `max_parent`, `max_child` | `tuple[ClarifyPlan, bool]` — (validated_plan, used_fallback). |
| **merge_patch_into_card_family** | `canonical_family: dict`, `patch: dict`, `plan: ClarifyPlan` | `dict` — updated canonical family (mutates and returns). |
| **_plan_next_clarify_step_llm** | `cleaned_text`, `canonical_family`, `asked_history`, counts, `max_parent`, `max_child` | `Optional[ClarifyPlan]` — from PROMPT_CLARIFY_PLANNER; None on parse/LLM failure. |
| **_generate_clarify_question_llm** | `plan: ClarifyPlan`, `canonical_family: dict` | `Optional[str]` — plain text question; None on failure. |
| **_apply_clarify_answer_patch_llm** | `plan: ClarifyPlan`, `user_answer: str`, `canonical_family: dict` | `tuple[Optional[dict], bool, Optional[str]]` — (patch, needs_retry, retry_question). |

### 4.5 Card service (crud.py)

| Function | Inputs | Output |
|----------|--------|--------|
| **apply_card_patch** | `card: ExperienceCard`, `body: ExperienceCardPatch` | `None`. Mutates card in place. Search text derived at embed time. |
| **apply_child_patch** | `child: ExperienceCardChild`, `body: ExperienceCardChildPatch` | `None`. Mutates child.value (items: `[{ title, description }]`). Search text derived at embed time. |

### 4.6 Search document (search_document.py)

| Function | Inputs | Output |
|----------|--------|--------|
| **build_parent_search_document** | `card: ExperienceCard` | `str` — concatenation of title, normalized_role, domain, sub_domain, company_name, company_type, location, employment_type, summary, raw_text, intent_primary, intent_secondary, seniority_level, date range, `"current"` if is_current. Does not include team. |
| **build_child_search_document_from_value** | `label: str | None`, `value: dict` | `str | None` — from label, raw_text, items[].title, items[].description; None if empty. |
| **get_child_search_document** | `child: ExperienceCardChild` | `str` — `build_child_search_document_from_value(get_child_label(child.value, child.child_type), child.value)` from `child_value.get_child_label`. |

---

## 5. Function map: who calls whom

### 5.1 Entry points (routers)

**File:** `apps/api/src/routers/builder.py`

- `POST /experience-cards/detect-experiences` → `detect_experiences(raw_text)`  
- `POST /experience-cards/draft-single` → `run_draft_single(db, person_id, raw_text, experience_index, experience_count)` — no embedding; returns draft card families.  
- `POST /experience-cards/clarify-experience` → `clarify_experience_interactive(...)`  
- `POST /experience-cards/finalize` → loads card + children, calls `embed_experience_cards(db, parents, children)`, marks card visible.  
- `POST /experience-cards/fill-missing-from-text` → `fill_missing_fields_from_text(...)`; if card_id/child_id set, merges + PATCH + re-embed.  
- `PATCH /experience-cards/{card_id}`, `PATCH /experience-card-children/{child_id}` → `apply_card_patch` / `apply_child_patch` + `embed_experience_cards` after update.

### 5.2 Pipeline (pipeline.py)

- **rewrite_raw_text(raw_text)**  
  - Uses rewrite cache (SHA-256 key).  
  - Fills PROMPT_REWRITE → `get_chat_provider().chat()` → returns cleaned text.  
  - Called by: detect_experiences, run_draft_single, clarify flow, fill_missing_fields_from_text.

- **detect_experiences(raw_text)**  
  - Calls rewrite_raw_text, then PROMPT_DETECT_EXPERIENCES → chat → parse JSON → returns `{ count, experiences }`.

- **run_draft_single(db, person_id, raw_text, experience_index, experience_count)**  
  - rewrite_raw_text  
  - Create RawExperience + DraftSet  
  - PROMPT_EXTRACT_SINGLE_CARDS → chat → **parse_llm_response_to_families**(response, EXTRACT)  
  - **inject_metadata_into_family** for each family  
  - **persist_families**(db, families, person_id, raw_experience_id, draft_set_id)  
  - **serialize_card_for_response** per card → returns (draft_set_id, raw_experience_id, card_families).  
  - **No embedding here** — embedding is deferred until `POST /experience-cards/finalize`.

- **parse_llm_response_to_families(response_text, stage)**  
  - _strip_json_fence, _extract_json_from_text  
  - Normalize to list of families (supports "families", "parents", or single "parent")  
  - For each family: **_normalize_child_dict** for each child (remaps subtitle→title, sub_summary→description), **_merge_duplicate_children** (merges same child_type), **_inherit_parent_context_into_children**  
  - Validate as Family; raises PipelineError on failure

- **persist_families**  
  - For each family: **card_to_experience_card_fields**(parent) → ExperienceCard; **card_to_child_fields**(child) → ExperienceCardChild; db.add, flush, refresh  
  - Returns (list[ExperienceCard], list[ExperienceCardChild])

- **card_to_experience_card_fields** / **card_to_child_fields**  
  - Use **extract_time_fields**, **extract_location_fields**, **extract_company**, **extract_team**, **extract_role_info**, **normalize_card_title**  
  - `card_to_experience_card_fields` also computes `*_norm` columns (domain_norm, sub_domain_norm, company_norm, team_norm)  
  - Persist to DB; search text derived at embed time via search_document.py

### 5.3 Embedding (embedding.py)

- **embed_experience_cards(db, parents, children)**  
  - **build_embedding_inputs**(parents, children) → list of (text, target)  
  - **fetch_embedding_vectors**(texts) → normalized vectors  
  - Assign each vector to target.embedding; db.flush()

- **build_embedding_inputs**  
  - Parent: `build_parent_search_document(parent)` (from search_document)  
  - Child: `get_child_search_document(child)`

### 5.4 Clarify (pipeline.py + clarify.py)

- **clarify_experience_interactive(raw_text, current_card, card_type, conversation_history, …)**  
  - If multiple detected experiences and no focus → return choose_focus (no LLM).  
  - If raw_text empty → return fixed opening question.  
  - **normalize_card_family_for_clarify**(card_family) → canonical shape (clarify)  
  - **_run_clarify_flow**(raw_text, card_family, conversation_history, …)

- **_run_clarify_flow**
  - Build asked_history and counts  
  - If last message is user: **_apply_clarify_answer_patch_llm**(plan, user_answer, canonical) → merge patch via **merge_patch_into_card_family** + **normalize_after_patch**  
  - **rewrite_raw_text**(raw_text)  
  - Loop: **_plan_next_clarify_step_llm**(cleaned_text, canonical, asked_history, …) → **validate_clarify_plan**(raw_plan, …) (clarify)  
  - If action **stop**: return filled (canonical_parent_to_flat_response) and should_stop  
  - If action **autofill**: merge autofill_patch, normalize_after_patch, continue loop  
  - If action **ask**: **_generate_clarify_question_llm**(plan, canonical) → return plain text clarifying_question and asked_history_entry  

All merge/validation/fallback logic (merge_patch_into_card_family, validate_clarify_plan, fallback_clarify_plan, is_parent_good_enough, compute_missing_fields) lives in **clarify.py**; LLM calls live in **pipeline.py**.

### 5.5 Edit / fill (pipeline.py)

- **fill_missing_fields_from_text(raw_text, current_card, card_type)**  
  - rewrite_raw_text → PROMPT_FILL_MISSING_FIELDS → chat → parse JSON, normalize keys (e.g. intent_secondary_str, dates)  
  - Returns dict of filled fields only (caller merges into form / card).

Card/child updates (apply_card_patch, apply_child_patch) are in **crud.py**; they update DB in place. Search text is derived at embed time by **build_parent_search_document** / **get_child_search_document** (search_document.py). Re-embed after patch is done in the router via **embed_experience_cards**.

---

## 6. Messy text → embedding pipeline (step-by-step)

1. **User input**  
   Raw string (e.g. from Builder Chat or edit form).

2. **Rewrite**  
   `rewrite_raw_text(raw_text)` → PROMPT_REWRITE → cleaned text. Cached by input hash.

3. **Detect (optional for single-experience)**  
   `detect_experiences(raw_text)` uses cleaned text → PROMPT_DETECT_EXPERIENCES → `{ count, experiences }`. Frontend can show choices; user may send `experience_index` + `experience_count` to draft-single.

4. **Extract one experience**  
   `run_draft_single(..., raw_text, experience_index, experience_count)`  
   - Rewrite (cache hit if same text).  
   - Create RawExperience (store raw + cleaned), DraftSet.  
   - PROMPT_EXTRACT_SINGLE_CARDS with cleaned text and index/count and enums (INTENT_ENUM, ALLOWED_CHILD_TYPES).  
   - LLM returns one parent + children; each child has `child_type` in ALLOWED_CHILD_TYPES and `value` (`{ raw_text, items: [{ title, description }] }`).

5. **Parse and validate**  
   `parse_llm_response_to_families(extract_response, EXTRACT)`  
   - Strip fences, extract JSON, normalize "parents"/"families"/single parent.  
   - _normalize_child_dict (value → top-level headline/title/summary/time/location/…; remaps subtitle→title, sub_summary→description)  
   - _merge_duplicate_children (merges same child_type into one, combining items)  
   - _inherit_parent_context_into_children  
   - Validate as Family list.

6. **Metadata**  
   `inject_metadata_into_family(family, person_id)` — ids, person_id, created_at, updated_at, parent_id, depth, relation_type.

7. **Persistence**   
   `persist_families(db, families, person_id, raw_experience_id, draft_set_id)`  
   - card_to_experience_card_fields → ExperienceCard rows (including *_norm columns)  
   - card_to_child_fields → ExperienceCardChild rows (child_type, value: { raw_text, items: [{ title, description }] })  
   - DB flush/refresh.

8. **Response**  
   serialize_card_for_response for each parent and child → card_families in DraftSetResponse.

9. **Embedding (deferred to finalize)**  
   When the user approves the draft via `POST /experience-cards/finalize`:  
   `embed_experience_cards(db, parents, children)`  
   - build_embedding_inputs: text = search_document (parent from build_parent_search_document; child from get_child_search_document).  
   - fetch_embedding_vectors(texts) → normalize to provider dimension (e.g. 324).  
   - Assign to parent.embedding / child.embedding; flush. Cards become visible/searchable.

---

## 7. Clarify flow (Q&A and autofill)

Clarify runs **after** extraction when the app has a card family and optionally conversation history. It either asks one targeted question, autofills from cleaned text, or stops when the card is "good enough."

- **Canonical shape:** `normalize_card_family_for_clarify(card_family)` produces a single nested structure (parent with time/location objects, children with child_type and value) used by planner and answer applier.

- **Planner (LLM):** PROMPT_CLARIFY_PLANNER with cleaned text, canonical card, asked_history, and limits (max parent/child questions). Output: `action` (ask | autofill | stop), `target_type` (parent | child), `target_field` or `target_child_type`, and optionally `autofill_patch`. Inapplicable fields are set to null silently; relations are never asked.

- **Validation:** `validate_clarify_plan(plan, canonical_family, asked_history, …)` in clarify.py enforces: parent good enough for stop, no duplicate asks, allowed target fields (PARENT_TARGET_FIELDS, CHILD_TARGET_FIELDS), and that autofill only touches the target. Invalid plans are replaced by `fallback_clarify_plan`.

- **Ask path:** PROMPT_CLARIFY_QUESTION_WRITER(validated_plan, canonical_card) → **plain text question** (no JSON). If the question is a generic onboarding phrase (GENERIC_QUESTION_PATTERNS), fallback to `_fallback_question_for_plan`.

- **Apply answer path:** When the last message is from the user, PROMPT_CLARIFY_APPLY_ANSWER(plan, user_answer, canonical_card) → patch; `merge_patch_into_card_family` + `normalize_after_patch` update canonical; if needs_retry, return retry_question. For child dimensions, patch contains `value.items` = list of `{ title, description }`.

- **Stop:** When action is stop (and validated), return `filled` (flat parent via canonical_parent_to_flat_response) and `should_stop=True`.

- **choose_focus:** If multiple experiences were detected and no focus_parent_id, clarify_experience_interactive returns action=choose_focus and options (from detect-experiences labels); no LLM. User then sends experience index and can call draft-single for that index.

Relationship: prompts (CLARIFY_PLANNER, QUESTION_WRITER, APPLY_ANSWER) are in experience_card.py; orchestration and LLM calls in pipeline.py; rules and merge in clarify.py.

---

## 8. Edit flow: fill missing, patch, finalize, re-embed

- **Finalize draft (first-time embed)**  
  When the user approves a drafted card: `POST /experience-cards/finalize` with `card_id`.  
  - Loads parent + children from DB.  
  - Calls `embed_experience_cards(db, parents, children)` — first embedding run.  
  - Marks card visible/searchable.

- **Fill missing from text (no full re-extract)**  
  Used when the user pastes additional messy text and the form already has a card.  
  - `fill_missing_fields_from_text(raw_text, current_card, card_type)`  
  - rewrite_raw_text → PROMPT_FILL_MISSING_FIELDS with current_card and allowed_keys (parent vs child).  
  - Returns a dict of only filled fields; frontend (or backend) merges into current_card.  
  - If card_id/child_id is set, router may merge and PATCH the DB card, then re-embed.

- **PATCH card or child**  
  - Parent: `apply_card_patch(card, body)` (crud.py) — applies ExperienceCardPatch fields in place. Search text is derived via `build_parent_search_document(card)` at embed time.  
  - Child: `apply_child_patch(child, body)` — updates child.value (items: `[{ title, description }]`). Search text derived via `get_child_search_document(child)` at embed time.  
  - Router then calls `embed_experience_cards(db, parents, children)` so embedding matches updated content.

So: **schema** for edit is ExperienceCardPatch / ExperienceCardChildPatch (items use `{ title, description }`); search text is derived at embed time via search_document.py; **embedding** is refreshed by builder router using embedding.py.

---

## 9. Search document and embedding text

**File:** `apps/api/src/services/experience/search_document.py`

Search text is **derived on-the-fly** from card fields — no stored `search_document` or `search_phrases` columns (removed in migrations 026/027). Child `label` column removed in migration 028; label is derived from `get_child_label(value, child_type)`.

- **build_parent_search_document(card: ExperienceCard)**  
  Concatenates: title, normalized_role, domain, sub_domain, company_name, company_type, location, employment_type, summary, raw_text, intent_primary, intent_secondary, seniority_level, date range, "current" if is_current.  
  Used for: embedding input.

- **build_child_search_document_from_value(label, value)**  
  From child's label and value (dimension container): label, raw_text, items[].title, items[].description (backward compat: subtitle→title, sub_summary→description).  
  Used for: embedding input.

- **get_child_search_document(child)**  
  Returns `build_child_search_document_from_value(get_child_label(child.value, child.child_type), child.value)`.

Embedding pipeline: **build_embedding_inputs** (in embedding.py) uses build_parent_search_document and get_child_search_document. Search text is always derived at embed time.

---

## 10. Key files index

| Purpose | File |
|--------|------|
| Domain enums and types | `apps/api/src/domain.py` |
| Prompt templates and fill_prompt | `apps/api/src/prompts/experience_card.py` |
| Prompt enum strings from domain | `apps/api/src/prompts/experience_card_enums.py` |
| Pipeline: rewrite, detect, extract, parse, persist, clarify | `apps/api/src/services/experience/pipeline.py` |
| Clarify rules, canonical shape, validate plan, merge patch | `apps/api/src/services/experience/clarify.py` |
| Child value normalization (raw_text, items: [{ title, description }]) | `apps/api/src/services/experience/child_value.py` |
| Search document text for parent/child (derived, no stored column) | `apps/api/src/services/experience/search_document.py` |
| Embedding: build inputs, fetch vectors, assign | `apps/api/src/services/experience/embedding.py` |
| Card CRUD, apply_card_patch, apply_child_patch | `apps/api/src/services/experience/crud.py` |
| Builder API routes | `apps/api/src/routers/builder.py` |
| Builder request/response schemas | `apps/api/src/schemas/builder.py` |
| DB models (RawExperience, DraftSet, ExperienceCard, ExperienceCardChild) | `apps/api/src/db/models.py` |
| Pipeline errors and stage enum | `apps/api/src/services/experience/errors.py` |

This document and the code it references define the full experience card flow from messy text to stored, embedded, and editable cards. Use it to trace schema, prompts, and function relationships for any change or debugging task.
