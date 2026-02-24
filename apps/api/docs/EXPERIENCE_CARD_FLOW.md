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
8. [Edit flow: fill missing, patch, re-embed](#8-edit-flow-fill-missing-patch-re-embed)
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
│  Children inherit time/location from parent when not explicit.            │
└──────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PARSE & VALIDATE                                                         │
│  parse_llm_response_to_families → V1Family list; inject_metadata.        │
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
┌──────────────────────────────────────────────────────────────────────────┐
│  EMBED                                                                    │
│  build_embedding_inputs (search_document text) → fetch_embedding_vectors  │
│  → assign to card.embedding; flush.                                       │
└──────────────────────────────────────────────────────────────────────────┘
       │
       ▼
Optional: CLARIFY (planner → question writer / apply answer) → merge patch → re-embed on save.
Optional: EDIT (fill missing from text, or PATCH) → rebuild search_document → re-embed.
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
| **ALLOWED_CHILD_TYPES** | `tuple[str, ...]` | skills, tools, metrics, achievements, responsibilities, collaborations, domain_knowledge, exposure, education, certifications |
| **ENTITY_TAXONOMY** | `list[str]` | person, organization, company, school, team, community, place, event, program, domain, industry, product, service, artifact, document, portfolio_item, credential, award, tool, equipment, system, platform, instrument, method, process |

**Intent (full list):** `"work" | "education" | "project" | "business" | "research" | "practice" | "exposure" | "achievement" | "transition" | "learning" | "life_context" | "community" | "finance" | "other" | "mixed"`

**ChildRelationType (full list):** `"describes" | "supports" | "demonstrates" | "results_in" | "learned_from" | "involves" | "part_of"`

**ChildIntent (full list):** `"responsibility" | "capability" | "method" | "outcome" | "learning" | "challenge" | "decision" | "evidence"`

**ALLOWED_CHILD_TYPES (full list):** `("skills", "tools", "metrics", "achievements", "responsibilities", "collaborations", "domain_knowledge", "exposure", "education", "certifications")`

**ENTITY_TAXONOMY (full list):** person, organization, company, school, team, community, place, event, program, domain, industry, product, service, artifact, document, portfolio_item, credential, award, tool, equipment, system, platform, instrument, method, process

Prompt-facing strings are built in `apps/api/src/prompts/experience_card_enums.py`:

- `INTENT_ENUM` = comma-separated Intent values  
- `CHILD_INTENT_ENUM`, `CHILD_RELATION_TYPE_ENUM`, `ENTITY_TYPES`, `ALLOWED_CHILD_TYPES_STR`  

These are injected into prompt templates via `fill_prompt()`.

### 2.2 Database models

**File:** `apps/api/src/db/models.py`

**RawExperience**

- `id`, `person_id`, `raw_text`, `raw_text_original`, `raw_text_cleaned`, `created_at`

**DraftSet**

- `id`, `person_id`, `raw_experience_id`, `run_version`, `extra_metadata`, `created_at`

**ExperienceCard (parent)**

- `id`, `person_id`, `draft_set_id`, `user_id` (synonym)
- Content: `title`, `normalized_role`, `domain`, `sub_domain`, `company_name`, `company_type`, `team`, `start_date`, `end_date`, `is_current`, `location`, `employment_type`, `summary`, `raw_text`, `intent_primary`, `intent_secondary` (ARRAY), `seniority_level`, `confidence_score`, `experience_card_visibility`
- Search/embed: `search_phrases` (ARRAY), `search_document` (Text), `embedding` (Vector(324))
- `created_at`, `updated_at`

**ExperienceCardChild**

- `id`, `parent_experience_id`, `person_id`, `raw_experience_id`, `draft_set_id`
- `child_type` (one of ALLOWED_CHILD_TYPES), `label`, `value` (JSONB dimension container)
- `confidence_score`, `search_phrases`, `search_document`, `embedding` (Vector(324)), `extra`, `created_at`, `updated_at`

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
| **FillFromTextRequest** | `raw_text: str`, `card_type: str = "parent"`, `current_card: dict = {}`, `card_id: Optional[str]`, `child_id: Optional[str]` |
| **ExperienceCardPatch** | All optional: `title`, `normalized_role`, `domain`, `sub_domain`, `company_name`, `company_type`, `start_date`, `end_date`, `is_current`, `location`, `employment_type`, `summary`, `raw_text`, `intent_primary`, `intent_secondary`, `seniority_level`, `confidence_score`, `experience_card_visibility` |
| **ExperienceCardChildPatch** | All optional: `title`, `summary`, `tags`, `time_range`, `company`, `location` |

**Response schemas (output from API):**

| Schema | Fields (returned to client) |
|--------|-----------------------------|
| **DetectExperiencesResponse** | `count: int = 0`, `experiences: list[DetectedExperienceItem]` where each item has `index: int`, `label: str`, `suggested: bool = False` |
| **DraftSetV1Response** | `draft_set_id: str`, `raw_experience_id: str`, `card_families: list[CardFamilyV1Response]` |
| **CardFamilyV1Response** | `parent: dict` (v1 parent card), `children: list[dict]` (v1 child cards) |
| **ClarifyExperienceResponse** | `clarifying_question: Optional[str]`, `filled: dict = {}`, `action: Optional[str]`, `message: Optional[str]`, `options: Optional[list[dict]]`, `focus_parent_id: Optional[str]`, `should_stop: Optional[bool]`, `stop_reason: Optional[str]`, `target_type`, `target_field`, `target_child_type`, `progress: Optional[dict]`, `missing_fields: Optional[dict]`, `asked_history_entry: Optional[dict]`, `canonical_family: Optional[dict]` |
| **FillFromTextResponse** | `filled: dict` (only keys that were extracted) |
| **ExperienceCardResponse** | `id`, `user_id`, `title`, `normalized_role`, `domain`, `sub_domain`, `company_name`, `company_type`, `start_date`, `end_date`, `is_current`, `location`, `employment_type`, `summary`, `raw_text`, `intent_primary`, `intent_secondary`, `seniority_level`, `confidence_score`, `experience_card_visibility`, `created_at`, `updated_at` |
| **ExperienceCardChildResponse** | `id`, `relation_type`, `title`, `context`, `tags`, `headline`, `summary`, `topics`, `time_range`, `role_title`, `company`, `location` |

### 2.4 Pipeline internal models (V1Card, V1Family)

**File:** `apps/api/src/services/experience/experience_card_pipeline.py`

**Nested models (used inside V1Card):**

| Model | Fields |
|-------|--------|
| **TimeInfo** | `text: Optional[str]`, `start: Optional[str]` (YYYY-MM or YYYY-MM-DD), `end: Optional[str]`, `ongoing: Optional[bool]` |
| **LocationInfo** | `text: Optional[str]`, `city: Optional[str]`, `country: Optional[str]`, `is_remote: Optional[bool]` |
| **RoleInfo** | `label: Optional[str]`, `seniority: Optional[str]` |
| **TopicInfo** | `label: str` |
| **EntityInfo** | `type: str` (e.g. company, team, organization), `name: str` |
| **IndexInfo** | `search_phrases: list[str]` |

**V1Card** (Pydantic) — full field list:

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
| Structure | topics | list[TopicInfo] |
| | entities | list[EntityInfo] |
| | actions | list[dict] |
| | outcomes | list[dict] |
| | evidence | list[dict] |
| | tooling | Optional[Any] |
| | index | Optional[IndexInfo] |
| | search_phrases | list[str] |
| | search_document | Optional[str] |
| Intent | intent | Optional[str] |
| | intent_primary | Optional[str] |
| | intent_secondary | list[str] |
| | confidence_score | Optional[float] |

Validators: prompt-style keys are normalized (intent_primary→intent, company_name→company, start_date/end_date→time object, roles from normalized_role, intent_secondary string→list, list normalizers for roles/topics/entities/actions/outcomes/evidence).

**V1Family**: `parent: V1Card`, `children: list[V1Card]`.

**Child dimension container (value)** — JSONB stored in ExperienceCardChild.value; built from V1Card in `card_to_child_fields`. Shape:

```json
{
  "headline": "...",
  "summary": "...",
  "raw_text": "...",
  "time": { "text": "...", "start": "YYYY-MM", "end": "YYYY-MM", "ongoing": false },
  "location": { "text": "...", "city": "...", "country": "...", "is_remote": false },
  "roles": [{ "label": "...", "seniority": "..." }],
  "topics": [{ "label": "..." }],
  "entities": [{ "type": "...", "name": "..." }],
  "actions": [{ "text": "..." }],
  "outcomes": [...],
  "tooling": { ... },
  "evidence": [...],
  "company": "...",
  "team": "...",
  "tags": ["..."],
  "depth": 1,
  "relation_type": "..."
}
```

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
        "company_name": "...",
        "start_date": "2020-01",
        "end_date": "2022-06",
        "summary": "...",
        "raw_text": "verbatim excerpt for this experience only",
        "intent_primary": "work",
        "location": "..." or { "text": "...", "city": "...", "country": "..." },
        "sub_domain": "...",
        "company_type": "...",
        "employment_type": "...",
        "intent_secondary": [],
        "seniority_level": "...",
        "confidence_score": 0.9
      },
      "children": [
        {
          "child_type": "tools",
          "label": "Short label",
          "value": {
            "headline": "...",
            "summary": "...",
            "time": { "start": "2020-01", "end": "2022-06" },
            "location": { "text": "..." },
            "company": "...",
            "topics": [],
            "tooling": {},
            "outcomes": []
          }
        }
      ]
    }
  ]
}
```

Parent: intent_primary must be one of Intent enum. Children: child_type one of ALLOWED_CHILD_TYPES; value must include time and location (inherited from parent when not explicit).

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

Allowed: action ∈ {"ask","autofill","stop"}, target_type ∈ {"parent","child",null}. When action=autofill, autofill_patch is e.g. `{"company_name": "X"}` or `{"time": {"start": "2020-01", "end": "2022-06"}}`.

**Clarify question writer:**

```json
{
  "question": "Which company was this at?",
  "reason_short": "company_name missing"
}
```

**Clarify apply answer:**

```json
{
  "patch": { "company_name": "Acme Corp" },
  "confidence": "high",
  "needs_retry": false,
  "retry_question": null
}
```

For time: patch may have `time: { start, end, ongoing, text }`. For location: `location: { text, city, country }`. If needs_retry is true, retry_question is one short question.

---

## 3. Prompts: placeholders, inputs, and expected output schema

**File:** `apps/api/src/prompts/experience_card.py`  
**Filler:** `fill_prompt(template, **kwargs)` — replaces placeholders; enums are always injected from `experience_card_enums` (INTENT_ENUM, CHILD_INTENT_ENUM, CHILD_RELATION_TYPE_ENUM, ENTITY_TYPES, ALLOWED_CHILD_TYPES_STR).

### 3.1 PROMPT_REWRITE

| Item | Detail |
|------|--------|
| **Placeholders** | `{{USER_TEXT}}` |
| **What is passed** | `user_text=raw_text` (the raw user message) |
| **Expected output** | Plain text only. No JSON. Cleaned, grammatical English; same facts; no commentary. |

**Full prompt text:**

```
You are a careful rewrite + cleanup engine.

Goal: Rewrite the user's message into clear, grammatically correct English AND
clean it to make structured extraction reliable.

STRICT RULES:
1) Do NOT add new facts. Do NOT guess missing details. Do NOT change meaning.
2) Keep all proper nouns, names, company names, tools, and numbers EXACTLY as written.
3) Preserve ordering and intent. Lists must remain lists.
4) Expand abbreviations ONLY when unambiguous.
5) Remove filler, repetition, and obvious typos.
6) Output ONLY the rewritten, cleaned text. No commentary. No JSON.

User message:
{{USER_TEXT}}
```

### 3.2 PROMPT_DETECT_EXPERIENCES

| Item | Detail |
|------|--------|
| **Placeholders** | `{{CLEANED_TEXT}}` |
| **What is passed** | `cleaned_text=<output of rewrite_raw_text>` |
| **Expected output** | Valid JSON only. Shape: `{ "count": number, "experiences": [ { "index": number, "label": string, "suggested": boolean }, ... ] }`. Exactly one experience must have `suggested: true`. |

**Full prompt text:**

```
You are an experience detection engine.

Read the cleaned text below and identify every DISTINCT experience block (job, role, project, company, or time-bound work experience).

Rules:
- Each distinct role, company, or project = one experience. Split on: different employers, "then", "after that", "also", "another role", different time ranges.
- Return ONLY valid JSON. No markdown, no commentary.

Output format:
{
  "count": <number of distinct experiences found, 0 if none>,
  "experiences": [
    { "index": 1, "label": "<short label, e.g. 'Razorpay, backend, 2 years'>", "suggested": false },
    { "index": 2, "label": "<short label>", "suggested": true }
  ]
}

- "label" must be a short one-line summary (company/role/duration) so the user can choose.
- Set "suggested": true for exactly ONE experience: the one that is most structured or has the most detail...
Cleaned text:
{{CLEANED_TEXT}}

Return valid JSON only:
```

### 3.3 PROMPT_EXTRACT_SINGLE_CARDS

| Item | Detail |
|------|--------|
| **Placeholders** | `{{USER_TEXT}}`, `{{EXPERIENCE_INDEX}}`, `{{EXPERIENCE_COUNT}}`, `{{INTENT_ENUM}}`, `{{ALLOWED_CHILD_TYPES}}` |
| **What is passed** | `user_text=raw_text_cleaned`, `experience_index=idx` (1-based), `experience_count=total`, plus enum strings from experience_card_enums |
| **Expected output** | Valid JSON. Shape: `{ "parents": [ { "parent": { ... }, "children": [ ... ] } ] }` with exactly one family. **parent** keys include: title, normalized_role, domain, company_name, start_date, end_date, summary, intent_primary (from INTENT_ENUM), raw_text (excerpt for this experience), etc. **children** each have: child_type (one of ALLOWED_CHILD_TYPES), label, value (object with headline, summary, raw_text, time, location, company, topics, tooling, outcomes, etc.). Dates as YYYY-MM-DD or YYYY-MM. Children inherit time/location from parent when not explicit. |

**Full prompt text:**

```
You are a structured data extraction system.

The cleaned text below contains MULTIPLE distinct experience blocks. Your task is to extract ONLY ONE of them.

CRITICAL: Extract ONLY the experience at position {{EXPERIENCE_INDEX}} (1 = first experience in the text, 2 = second, etc.). There are {{EXPERIENCE_COUNT}} distinct experiences total. Ignore all others.

Return exactly ONE parent and its child dimension cards. Use the schema below (parent with all keys, children with allowed child_type). Output format:

{
  "parents": [
    {
      "parent": { ... single parent with all required keys ... },
      "children": [ ... ]
    }
  ]
}

- parent: all required keys (title, normalized_role, domain, company_name, start_date, end_date, summary, intent_primary, etc.). intent_primary MUST be one of: {{INTENT_ENUM}}
- children: YOU MUST EXTRACT CHILD DIMENSION CARDS when the experience mentions them. Allowed child_type: {{ALLOWED_CHILD_TYPES}}. Create one child per dimension present. Each child must have child_type, value (headline, summary, raw_text, time, location, company, topics, tooling, outcomes, etc.). Do NOT output multiple children with the same child_type—merge into one per type. MANDATORY INHERIT FROM PARENT: every child's value MUST include time and location (and company when parent has it); copy from parent when user did not state different.
- raw_text in parent must be a verbatim excerpt from the cleaned text for THIS experience only.
- Do NOT invent facts. Use null for missing fields.
- Dates: start_date, end_date, time.start/time.end MUST be YYYY-MM-DD or YYYY-MM only.

Cleaned text:
{{USER_TEXT}}

Extract ONLY the {{EXPERIENCE_INDEX}}-th experience (of {{EXPERIENCE_COUNT}}). Return valid JSON only:
```

### 3.4 PROMPT_FILL_MISSING_FIELDS

| Item | Detail |
|------|--------|
| **Placeholders** | `{{ALLOWED_KEYS}}`, `{{CURRENT_CARD_JSON}}`, `{{CLEANED_TEXT}}` |
| **What is passed** | `allowed_keys=FILL_MISSING_PARENT_KEYS` or `FILL_MISSING_CHILD_KEYS`, `current_card_json=json.dumps(current_card)`, `cleaned_text=<output of rewrite>` |
| **Expected output** | Single JSON object. Only keys that were missing in current_card and could be filled from text. No array, no markdown. Dates as YYYY-MM-DD or YYYY-MM. intent_secondary as string or array; tags as comma-separated string. |

**Allowed keys (parent):** `title, summary, normalized_role, domain, sub_domain, company_name, company_type, location, employment_type, start_date, end_date, is_current, intent_primary, intent_secondary_str, seniority_level, confidence_score`

**Allowed keys (child):** `title, summary, tagsStr, time_range, company, location`

**Full prompt text:**

```
You are a fill-missing-fields extractor. You do NOT create full cards.

Input:
1) Cleaned text (user-provided snippet).
2) Current card as JSON. Some fields are empty ("" or null). Only those are "missing".

Task: From the cleaned text, extract values ONLY for fields that are currently missing or empty in the current card. Do NOT overwrite or change fields that already have a value.

Allowed keys for this card type (return ONLY these keys when you have a value; omit any key you cannot infer):
{{ALLOWED_KEYS}}

Rules:
- Return a single JSON object. No markdown, no commentary, no array wrapper.
- Include only keys you can fill from the text. Omit keys that are already set in current_card or that you cannot infer.
- Dates: MUST use YYYY-MM-DD or YYYY-MM only (e.g. 2020-01). Do NOT use month names.
- For intent_secondary use a comma-separated string or array of strings.
- For tags use a comma-separated string.

Current card (missing/empty fields should be filled from text below):
{{CURRENT_CARD_JSON}}

Cleaned text:
{{CLEANED_TEXT}}

Return valid JSON only:
```

### 3.5 PROMPT_CLARIFY_PLANNER

| Item | Detail |
|------|--------|
| **Placeholders** | `{{CANONICAL_CARD_JSON}}`, `{{CLEANED_TEXT}}`, `{{ASKED_HISTORY_JSON}}`, `{{MAX_PARENT}}`, `{{MAX_CHILD}}`, `{{PARENT_ASKED_COUNT}}`, `{{CHILD_ASKED_COUNT}}` |
| **What is passed** | `canonical_card_json=json.dumps(canonical_family)`, `cleaned_text=...`, `asked_history_json=json.dumps(asked_history)`, `max_parent`, `max_child`, `parent_asked_count`, `child_asked_count` |
| **Expected output** | One JSON object: `{ "action": "ask"|"autofill"|"stop", "target_type": "parent"|"child"|null, "target_field": string|null, "target_child_type": string|null, "reason": string, "confidence": "high"|"medium"|"low", "autofill_patch": object|null }`. When action=autofill, autofill_patch contains only the target field(s). |

**Allowed parent target_field:** headline, role, summary, company_name, team, time, location, domain, sub_domain, intent_primary  
**Allowed target_child_type:** metrics, tools, achievements, responsibilities, collaborations, domain_knowledge, exposure, education, certifications

**Full prompt text:**

```
You are a clarification planner for experience cards. This is POST-EXTRACTION: we already have an extracted card. You decide the NEXT step only: ask one TARGETED field question, autofill from text, or stop.

Inputs: Cleaned experience text; current card family (canonical JSON); asked history; limits (max parent/child questions). Good enough parent = has headline or role, summary, and at least one of: company_name, time, location.

Output: ONE JSON object only. No markdown, no commentary.
Allowed action: "ask" | "autofill" | "stop"
Allowed target_type: "parent" | "child" | null
Allowed parent target_field: headline, role, summary, company_name, team, time, location, domain, sub_domain, intent_primary
Allowed target_child_type (when target_type=child): metrics, tools, achievements, responsibilities, collaborations, domain_knowledge, exposure, education, certifications

Rules: Only field-targeted actions. Ask at most ONE thing at a time. Prefer parent until good enough. AUTOFILL only when text EXPLICITLY provides the value; do not autofill time from duration only. Never repeat asked fields or overwrite filled fields.

Output format (JSON only):
{
  "action": "ask|autofill|stop",
  "target_type": "parent|child|null",
  "target_field": "...|null",
  "target_child_type": "...|null",
  "reason": "short reason",
  "confidence": "high|medium|low",
  "autofill_patch": null
}
When action=autofill, autofill_patch must only update the target field (e.g. {"company_name": "ABC Inc"} or {"time": {"start": "2020-01", "end": "2022-06"}}).

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
| **Placeholders** | `{{VALIDATED_PLAN_JSON}}`, `{{CARD_CONTEXT_JSON}}` |
| **What is passed** | `validated_plan_json=json.dumps({ action, target_type, target_field, target_child_type, reason })`, `card_context_json=json.dumps(canonical_family.parent or {})` |
| **Expected output** | JSON: `{ "question": string, "reason_short": string }`. One short, field-specific question; no onboarding/discovery phrasing. |

**Full prompt text:**

```
You write exactly ONE short, natural clarification question for a SPECIFIC field on an experience card.

Phase: POST_EXTRACTION. We already have an extracted experience. You are ONLY asking for one missing field.

You are given the validated plan: target_type (parent or child), target_field (e.g. company_name, time, location), and optionally target_child_type for child cards.

STRICT RULES:
- Ask exactly one question. Be specific to the target_field ONLY.
- Sound human and curious. Do NOT sound like a form.
- FORBIDDEN: "What's something cool you've built", "Tell me more about your experience", "What did you work on?", "Can you share more?", "What would you like to add?", "Describe your experience", "Tell me about a...", "What's one experience...".
- Do not ask for things already present in the card context. Keep it short (one sentence).

Good examples: company_name → "What was the name of the company?"; time → "Roughly when did you do this?"; location → "Where was this based—city or country?"; metrics → "What was the main metric here?"

Output: JSON only. No markdown, no commentary.
{
  "question": "Your one short, field-specific question?",
  "reason_short": "Why this question (one phrase)"
}

Validated plan:
{{VALIDATED_PLAN_JSON}}

Minimal card context (for reference only; do not ask for what is already set):
{{CARD_CONTEXT_JSON}}

Return valid JSON only:
```

### 3.7 PROMPT_CLARIFY_APPLY_ANSWER

| Item | Detail |
|------|--------|
| **Placeholders** | `{{VALIDATED_PLAN_JSON}}`, `{{USER_ANSWER}}`, `{{CANONICAL_CARD_JSON}}` |
| **What is passed** | `validated_plan_json=...`, `user_answer=<last user message text>`, `canonical_card_json=json.dumps(canonical_family)` |
| **Expected output** | JSON: `{ "patch": object, "confidence": "high"|"medium"|"low", "needs_retry": boolean, "retry_question": string|null }`. Patch updates only the target field (and nested time/location if applicable). If needs_retry is true, retry_question is one short question. |

**Full prompt text:**

```
You convert the user's answer into a small patch for the experience card. You ONLY update the target field (and tightly related nested fields like time.start/time.end or location.city/country).

Inputs: Validated plan (target_type, target_field or target_child_type); user's answer (raw text); current canonical card (for context).

Rules:
- Output a patch that ONLY modifies the target field. For time: patch may include time.start, time.end, time.ongoing, time.text. For location: location.city, location.country, location.text.
- No hallucinations. Use the user's words when uncertain.
- If the answer is unclear or unusable, set needs_retry=true and provide a short retry_question.
- Preserve original wording when appropriate.
- Dates: MUST use YYYY-MM or YYYY-MM-DD only (e.g. 2020-01). Do NOT use month names; convert "Jan 2020" to 2020-01.

Output: JSON only. No markdown, no commentary.
{
  "patch": { ... only target field updates ... },
  "confidence": "high|medium|low",
  "needs_retry": false,
  "retry_question": null
}
When needs_retry is true, retry_question should be one short question. Patch may be empty in that case.

Validated plan:
{{VALIDATED_PLAN_JSON}}

User answer:
{{USER_ANSWER}}

Current canonical card (relevant part):
{{CANONICAL_CARD_JSON}}

Return valid JSON only:
```

---

## 4. Function inputs and outputs

Each row: function name, **inputs** (parameter → type/source), **output** (type and shape).

### 4.1 Public pipeline API (experience_card_pipeline.py)

| Function | Inputs | Output |
|----------|--------|--------|
| **rewrite_raw_text** | `raw_text: str` (user message) | `str` — cleaned English text. Raises HTTPException 400 if empty; PipelineError on LLM failure. |
| **detect_experiences** | `raw_text: str` | `dict` — `{ "count": int, "experiences": [ { "index": int, "label": str, "suggested": bool }, ... ] }`. On parse failure returns `{"count": 0, "experiences": []}`. |
| **run_draft_v1_single** | `db: AsyncSession`, `person_id: str`, `raw_text: str`, `experience_index: int`, `experience_count: int` | `tuple[str, str, list[dict]]` — `(draft_set_id, raw_experience_id, card_families)`. Each family: `{ "parent": dict, "children": list[dict] }` (serialize_card_for_response shape). Raises HTTPException 400 if empty raw_text; ChatServiceError/PipelineError on failure. |
| **fill_missing_fields_from_text** | `raw_text: str`, `current_card: dict`, `card_type: str` ("parent" \| "child") | `dict` — only keys that were filled (e.g. title, company_name, start_date). Empty dict on parse failure or empty response. |
| **clarify_experience_interactive** | `raw_text: str`, `current_card: dict`, `card_type: str`, `conversation_history: list[dict]`, optional: `card_family`, `asked_history_structured`, `last_question_target`, `max_parent`, `max_child`, `card_families`, `focus_parent_id`, `detected_experiences` | `dict` — ClarifyExperienceResponse-like: `clarifying_question`, `filled`, `should_stop`, `stop_reason`, `target_type`, `target_field`, `target_child_type`, `progress`, `missing_fields`, `asked_history_entry`, `canonical_family`; or `action: "choose_focus"`, `message`, `options` when multiple experiences and no focus. |

### 4.2 Parsing and persistence (experience_card_pipeline.py)

| Function | Inputs | Output |
|----------|--------|--------|
| **parse_llm_response_to_families** | `response_text: str` (LLM reply), `stage: PipelineStage` | `list[V1Family]`. Raises PipelineError if no valid JSON or no valid families. |
| **inject_metadata_into_family** | `family: V1Family`, `person_id: str` | `V1Family` (mutated in place; ids, person_id, created_at, updated_at, parent_id, depth set). |
| **persist_families** | `db: AsyncSession`, `families: list[V1Family]`, `person_id: str`, `raw_experience_id: str`, `draft_set_id: str` | `tuple[list[ExperienceCard], list[ExperienceCardChild]]`. Raises PipelineError on DB failure. |
| **card_to_experience_card_fields** | `card: V1Card`, `person_id`, `raw_experience_id`, `draft_set_id` | `dict` — kwargs for ExperienceCard constructor (user_id, raw_text, title, normalized_role, domain, company_name, start_date, end_date, summary, search_document, etc.). |
| **card_to_child_fields** | `card: V1Card`, `person_id`, `raw_experience_id`, `draft_set_id`, `parent_id` | `dict` — kwargs for ExperienceCardChild constructor (parent_experience_id, child_type, label, value, search_document, embedding=None, etc.). |
| **serialize_card_for_response** | `card: ExperienceCard | ExperienceCardChild` | `dict` — API response shape (id, title, context, tags, headline, summary, time_range, company, location, etc.). |

### 4.3 Embedding (experience_card_embedding.py)

| Function | Inputs | Output |
|----------|--------|--------|
| **build_embedding_inputs** | `parents: list[ExperienceCard]`, `children: list[ExperienceCardChild]` | `list[EmbeddingInput]` — each has `.text: str` (search_document or built), `.target: ExperienceCard | ExperienceCardChild`. Order: all parents, then all children. |
| **fetch_embedding_vectors** | `texts: list[str]` | `list[list[float]]` — normalized vectors, same order as texts. Raises EmbeddingServiceError on provider failure. |
| **embed_experience_cards** | `db: AsyncSession`, `parents: list[ExperienceCard]`, `children: list[ExperienceCardChild]` | `None`. Mutates each card’s `.embedding`; calls `db.flush()`. Raises PipelineError on dimension mismatch or provider failure. |

### 4.4 Clarify helpers (experience_clarify.py vs experience_card_pipeline.py)

| Function | Inputs | Output |
|----------|--------|--------|
| **normalize_card_family_for_clarify** | `card_family: dict` (parent + children, any shape) | `dict` — `{ "parent": {...}, "children": [...] }` canonical (time/location as objects, headline/role/summary normalized). |
| **validate_clarify_plan** | `plan: ClarifyPlan | None`, `canonical_family: dict`, `asked_history: list`, `parent_asked_count`, `child_asked_count`, `max_parent`, `max_child` | `tuple[ClarifyPlan, bool]` — (validated_plan, used_fallback). |
| **merge_patch_into_card_family** | `canonical_family: dict`, `patch: dict`, `plan: ClarifyPlan` | `dict` — updated canonical family (mutates and returns). |
| **_plan_next_clarify_step_llm** | `cleaned_text`, `canonical_family`, `asked_history`, counts, `max_parent`, `max_child` | `Optional[ClarifyPlan]` — from PROMPT_CLARIFY_PLANNER; None on parse/LLM failure. |
| **_generate_clarify_question_llm** | `plan: ClarifyPlan`, `canonical_family: dict` | `Optional[str]` — question text; None on failure. |
| **_apply_clarify_answer_patch_llm** | `plan: ClarifyPlan`, `user_answer: str`, `canonical_family: dict` | `tuple[Optional[dict], bool, Optional[str]]` — (patch, needs_retry, retry_question). |

### 4.5 Card service (experience_card.py)

| Function | Inputs | Output |
|----------|--------|--------|
| **apply_card_patch** | `card: ExperienceCard`, `body: ExperienceCardPatch` | `None`. Mutates card in place; sets `card.search_document = build_parent_search_document(card)`. |
| **apply_child_patch** | `child: ExperienceCardChild`, `body: ExperienceCardChildPatch` | `None`. Mutates child.label and child.value; sets `child.search_document = build_child_search_document_from_value(...)`. |

### 4.6 Search document (experience_card_search_document.py)

| Function | Inputs | Output |
|----------|--------|--------|
| **build_parent_search_document** | `card: ExperienceCard` | `str` — concatenation of title, normalized_role, domain, company_name, location, summary, etc. |
| **build_child_search_document_from_value** | `label: str | None`, `value: dict` | `str | None` — from headline, summary, company, location text, time text, tags; None if empty. |
| **get_child_search_document** | `child: ExperienceCardChild` | `str` — `child.search_document` if set, else build_child_search_document_from_value(child.label, child.value). |

---

## 5. Function map: who calls whom

### 5.1 Entry points (routers)

**File:** `apps/api/src/routers/builder.py`

- `POST /experience-cards/detect-experiences` → `detect_experiences(raw_text)`  
- `POST /experience-cards/draft-v1-single` → `run_draft_v1_single(db, person_id, raw_text, experience_index, experience_count)`  
- `POST /experience-cards/clarify-experience` → `clarify_experience_interactive(...)`  
- Fill-from-text and PATCH endpoints call `fill_missing_fields_from_text` or `apply_card_patch`/`apply_child_patch` and optionally `embed_experience_cards` after update.

### 5.2 Pipeline (experience_card_pipeline.py)

- **rewrite_raw_text(raw_text)**  
  - Uses rewrite cache (SHA-256 key).  
  - Fills PROMPT_REWRITE → `get_chat_provider().chat()` → returns cleaned text.  
  - Called by: detect_experiences, run_draft_v1_single, clarify flow, fill_missing_fields_from_text.

- **detect_experiences(raw_text)**  
  - Calls rewrite_raw_text, then PROMPT_DETECT_EXPERIENCES → chat → parse JSON → returns `{ count, experiences }`.

- **run_draft_v1_single(db, person_id, raw_text, experience_index, experience_count)**  
  - rewrite_raw_text  
  - Create RawExperience + DraftSet  
  - PROMPT_EXTRACT_SINGLE_CARDS → chat → **parse_llm_response_to_families**(response, EXTRACT)  
  - **inject_metadata_into_family** for each family  
  - **persist_families**(db, families, person_id, raw_experience_id, draft_set_id)  
  - **embed_experience_cards**(db, parents, children)  
  - **serialize_card_for_response** per card → returns (draft_set_id, raw_experience_id, card_families)

- **parse_llm_response_to_families(response_text, stage)**  
  - _strip_json_fence, _extract_json_from_text  
  - Normalize to list of families (supports "families", "parents", or single "parent")  
  - For each family: **_normalize_child_dict_for_v1_card** for each child, **_inherit_parent_context_into_children**  
  - Validate as V1Family; raises PipelineError on failure

- **persist_families**  
  - For each family: **card_to_experience_card_fields**(parent) → ExperienceCard; **card_to_child_fields**(child) → ExperienceCardChild; db.add, flush, refresh  
  - Returns (list[ExperienceCard], list[ExperienceCardChild])

- **card_to_experience_card_fields** / **card_to_child_fields**  
  - Use **extract_time_fields**, **extract_location_fields**, **extract_company**, **extract_team**, **extract_role_info**, **extract_search_phrases**, **normalize_card_title**  
  - Build search_document (or use card.search_document) and other columns

### 5.3 Embedding (experience_card_embedding.py)

- **embed_experience_cards(db, parents, children)**  
  - **build_embedding_inputs**(parents, children) → list of (text, target)  
  - **fetch_embedding_vectors**(texts) → normalized vectors  
  - Assign each vector to target.embedding; db.flush()

- **build_embedding_inputs**  
  - Parent: `parent.search_document or build_parent_search_document(parent)` (from experience_card_search_document)  
  - Child: `get_child_search_document(child)` (stored or build_child_search_document_from_value)

### 5.4 Clarify (experience_card_pipeline + experience_clarify.py)

- **clarify_experience_interactive(raw_text, current_card, card_type, conversation_history, …)**  
  - If multiple detected experiences and no focus → return choose_focus (no LLM).  
  - If raw_text empty → return fixed opening question.  
  - **normalize_card_family_for_clarify**(card_family) → canonical shape (experience_clarify)  
  - **_run_clarify_flow**(raw_text, card_family, conversation_history, …)

- **_run_clarify_flow**  
  - Build asked_history and counts  
  - If last message is user: **_apply_clarify_answer_patch_llm**(plan, user_answer, canonical) → merge patch via **merge_patch_into_card_family** + **normalize_after_patch**  
  - **rewrite_raw_text**(raw_text)  
  - Loop: **_plan_next_clarify_step_llm**(cleaned_text, canonical, asked_history, …) → **validate_clarify_plan**(raw_plan, …) (experience_clarify)  
  - If action **stop**: return filled (canonical_parent_to_flat_response) and should_stop  
  - If action **autofill**: merge autofill_patch, normalize_after_patch, continue loop  
  - If action **ask**: **_generate_clarify_question_llm**(plan, canonical) → return clarifying_question and asked_history_entry  

All merge/validation/fallback logic (merge_patch_into_card_family, validate_clarify_plan, fallback_clarify_plan, is_parent_good_enough, compute_missing_fields) lives in **experience_clarify.py**; LLM calls live in **experience_card_pipeline.py**.

### 5.5 Edit / fill (experience_card_pipeline.py)

- **fill_missing_fields_from_text(raw_text, current_card, card_type)**  
  - rewrite_raw_text → PROMPT_FILL_MISSING_FIELDS → chat → parse JSON, normalize keys (e.g. intent_secondary_str, tagsStr, dates)  
  - Returns dict of filled fields only (caller merges into form / card).

Card/child updates (apply_card_patch, apply_child_patch) are in **experience_card.py**; they update DB and **build_parent_search_document** / **build_child_search_document_from_value** so search_document stays in sync. Re-embed after patch is done in the router via **embed_experience_cards**.

---

## 6. Messy text → embedding pipeline (step-by-step)

1. **User input**  
   Raw string (e.g. from Builder Chat or edit form).

2. **Rewrite**  
   `rewrite_raw_text(raw_text)` → PROMPT_REWRITE → cleaned text. Cached by input hash.

3. **Detect (optional for single-experience)**  
   `detect_experiences(raw_text)` uses cleaned text → PROMPT_DETECT_EXPERIENCES → `{ count, experiences }`. Frontend can show choices; user may send `experience_index` + `experience_count` to draft-v1-single.

4. **Extract one experience**  
   `run_draft_v1_single(..., raw_text, experience_index, experience_count)`  
   - Rewrite (cache hit if same text).  
   - Create RawExperience (store raw + cleaned), DraftSet.  
   - PROMPT_EXTRACT_SINGLE_CARDS with cleaned text and index/count and enums (INTENT_ENUM, ALLOWED_CHILD_TYPES).  
   - LLM returns one parent + children; each child has `child_type` in ALLOWED_CHILD_TYPES and `value` (headline, summary, time, location, company, …); children inherit parent time/location/company when not explicit.

5. **Parse and validate**  
   `parse_llm_response_to_families(extract_response, EXTRACT)`  
   - Strip fences, extract JSON, normalize "parents"/"families"/single parent.  
   - _normalize_child_dict_for_v1_card (value → top-level headline/title/summary/time/location/…)  
   - _inherit_parent_context_into_children  
   - Validate as V1Family list.

6. **Metadata**  
   `inject_metadata_into_family(family, person_id)` — ids, person_id, created_at, updated_at, parent_id, depth, relation_type.

7. **Persistence**  
   `persist_families(db, families, person_id, raw_experience_id, draft_set_id)`  
   - card_to_experience_card_fields → ExperienceCard rows  
   - card_to_child_fields → ExperienceCardChild rows (child_type, label, value dimension container, search_document)  
   - DB flush/refresh.

8. **Embedding**  
   `embed_experience_cards(db, parents, children)`  
   - build_embedding_inputs: text = search_document (parent from build_parent_search_document if needed; child from get_child_search_document).  
   - fetch_embedding_vectors(texts) → normalize to provider dimension (e.g. 324).  
   - Assign to parent.embedding / child.embedding; flush.

9. **Response**  
   serialize_card_for_response for each parent and child → card_families in DraftSetV1Response.

---

## 7. Clarify flow (Q&A and autofill)

Clarify runs **after** extraction when the app has a card family and optionally conversation history. It either asks one targeted question, autofills from cleaned text, or stops when the card is “good enough.”

- **Canonical shape:** `normalize_card_family_for_clarify(card_family)` produces a single nested structure (parent with time/location objects, children with child_type and value) used by planner and answer applier.

- **Planner (LLM):** PROMPT_CLARIFY_PLANNER with cleaned text, canonical card, asked_history, and limits (max parent/child questions). Output: `action` (ask | autofill | stop), `target_type` (parent | child), `target_field` or `target_child_type`, and optionally `autofill_patch`.

- **Validation:** `validate_clarify_plan(plan, canonical_family, asked_history, …)` in experience_clarify enforces: parent good enough for stop, no duplicate asks, allowed target fields (PARENT_TARGET_FIELDS, CHILD_TARGET_FIELDS), and that autofill only touches the target. Invalid plans are replaced by `fallback_clarify_plan`.

- **Ask path:** PROMPT_CLARIFY_QUESTION_WRITER(validated_plan, card_context) → one short question; if generic onboarding phrase (GENERIC_QUESTION_PATTERNS), fallback to _fallback_question_for_plan.

- **Apply answer path:** When the last message is from the user, PROMPT_CLARIFY_APPLY_ANSWER(plan, user_answer, canonical_card) → patch; `merge_patch_into_card_family` + `normalize_after_patch` update canonical; if needs_retry, return retry_question.

- **Stop:** When action is stop (and validated), return `filled` (flat parent via canonical_parent_to_flat_response) and `should_stop=True`.

- **choose_focus:** If multiple experiences were detected and no focus_parent_id, clarify_experience_interactive returns action=choose_focus and options (from detect-experiences labels); no LLM. User then sends focus (e.g. experience index) and can call draft-v1-single for that index.

Relationship: prompts (CLARIFY_PLANNER, QUESTION_WRITER, APPLY_ANSWER) are in experience_card.py; orchestration and LLM calls in experience_card_pipeline; rules and merge in experience_clarify.

---

## 8. Edit flow: fill missing, patch, re-embed

- **Fill missing from text (no full re-extract)**  
  Used when the user pastes additional messy text and the form already has a card.  
  - `fill_missing_fields_from_text(raw_text, current_card, card_type)`  
  - rewrite_raw_text → PROMPT_FILL_MISSING_FIELDS with current_card and allowed_keys (parent vs child).  
  - Returns a dict of only filled fields; frontend (or backend) merges into current_card.  
  - If card_id/child_id is set, router may merge and PATCH the DB card, then re-embed.

- **PATCH card or child**  
  - Parent: `apply_card_patch(card, body)` (experience_card.py) — applies ExperienceCardPatch fields, then `card.search_document = build_parent_search_document(card)`.  
  - Child: `apply_child_patch(child, body)` — updates label and value (dimension container), then `child.search_document = build_child_search_document_from_value(child.label, value)`.  
  - Router then calls `embed_experience_cards(db, parents, children)` so embedding matches updated search_document.

So: **schema** for edit is ExperienceCardPatch / ExperienceCardChildPatch; **search_document** is rebuilt in experience_card.py; **embedding** is refreshed by builder router using experience_card_embedding.

---

## 9. Search document and embedding text

**File:** `apps/api/src/services/experience/experience_card_search_document.py`

- **build_parent_search_document(card: ExperienceCard)**  
  Concatenates: title, normalized_role, domain, sub_domain, company_name, company_type, location, employment_type, summary, raw_text, intent_primary, intent_secondary, seniority_level, date range, "current" if is_current.  
  Used for: embedding input when parent.search_document is missing; after apply_card_patch to keep search_document in sync.

- **build_child_search_document_from_value(label, value)**  
  From child’s label and value (dimension container): headline, summary, company, location text, time text, tags.  
  Used for: embedding when child has no stored search_document; after apply_child_patch.

- **get_child_search_document(child)**  
  Returns stored child.search_document or build_child_search_document_from_value(child.label, child.value).

Embedding pipeline uses these same texts: **build_embedding_inputs** (in experience_card_embedding) uses build_parent_search_document and get_child_search_document so that the same string is used for the vector and (where applicable) stored in search_document. So **schema** of what gets embedded is defined by these builder functions; **prompts** (extract/fill/clarify) do not define embedding text directly—they produce cards that are then mapped to DB rows and to search_document by pipeline and experience_card logic.

---

## 10. Key files index

| Purpose | File |
|--------|------|
| Domain enums and types | `apps/api/src/domain.py` |
| Prompt templates and fill_prompt | `apps/api/src/prompts/experience_card.py` |
| Prompt enum strings from domain | `apps/api/src/prompts/experience_card_enums.py` |
| Pipeline: rewrite, detect, extract, parse, persist, clarify | `apps/api/src/services/experience/experience_card_pipeline.py` |
| Clarify rules, canonical shape, validate plan, merge patch | `apps/api/src/services/experience/experience_clarify.py` |
| Search document text for parent/child | `apps/api/src/services/experience/experience_card_search_document.py` |
| Embedding: build inputs, fetch vectors, assign | `apps/api/src/services/experience/experience_card_embedding.py` |
| Card CRUD, apply_card_patch, apply_child_patch | `apps/api/src/services/experience/experience_card.py` |
| Builder API routes | `apps/api/src/routers/builder.py` |
| Builder request/response schemas | `apps/api/src/schemas/builder.py` |
| DB models (RawExperience, DraftSet, ExperienceCard, ExperienceCardChild) | `apps/api/src/db/models.py` |
| Pipeline errors and stage enum | `apps/api/src/services/experience/pipeline_errors.py` |

This document and the code it references define the full experience card flow from messy text to stored, embedded, and editable cards. Use it to trace schema, prompts, and function relationships for any change or debugging task.
