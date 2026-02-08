# Extraction Data Process: Messy Text → Embedding

This document describes the full pipeline that turns **messy, informal, or incomplete user text** into **structured experience cards** and **vector embeddings** for search. Each stage is documented with **input schema**, **output schema**, and behavior.

---

## Pipeline Overview

```
┌─────────────────┐     ┌──────────┐     ┌─────────┐     ┌──────────┐     ┌─────────┐     ┌────────┐
│  Messy raw text │ ──► │ Rewrite  │ ──► │ Extract │ ──► │ Validate │ ──► │ Persist │ ──► │ Embed  │
│  (API input)    │     │ (LLM)    │     │ (LLM)   │     │ (LLM)    │     │ (DB)    │     │ (API)  │
└─────────────────┘     └──────────┘     └─────────┘     └──────────┘     └─────────┘     └────────┘
       │                       │                │                │                │              │
       ▼                       ▼                ▼                ▼                ▼              ▼
  RawExperienceCreate    cleaned text    V1Family[]      V1Family[]    ExperienceCard   vector[384]
                                        (parent+children)               ExperienceCardChild
```

**Entry point:** `run_draft_v1_pipeline(db, person_id, body: RawExperienceCreate)`  
**Code:** `src/services/experience_card_pipeline.py`, `src/providers/embedding.py`, `src/prompts/experience_card.py`

---

## Stage 0: API Input

User submits free-form text (e.g. pasted resume, bullet points, notes).

### Input schema (HTTP request body)

| Field      | Type   | Required | Description                    |
|-----------|--------|----------|--------------------------------|
| `raw_text`| string | Yes      | Raw, possibly messy user text |

**Pydantic model:** `RawExperienceCreate` (in `src/schemas/builder.py`)

```json
{
  "raw_text": "worked at acme 2020-22. did python, ml. then joined beta inc. built search. also did some open source on the side."
}
```

### Output (conceptually)

Same string is passed to **Stage 1: Rewrite**. No schema change yet.

---

## Stage 1: Rewrite (Cleanup)

**Purpose:** Normalize grammar, remove filler and repetition, fix obvious typos—**without adding or guessing facts**. Output is clean English suitable for structured extraction.

**Function:** `rewrite_raw_text(raw_text: str) -> str`  
**Prompt:** `PROMPT_REWRITE` in `src/prompts/experience_card.py`  
**Provider:** Chat LLM via `get_chat_provider().chat(prompt, max_tokens=2048)`

### Input

| Name       | Type   | Description        |
|------------|--------|--------------------|
| `raw_text` | string | Original user text |

### Output

| Name   | Type   | Description                          |
|--------|--------|--------------------------------------|
| return | string | Single cleaned text; whitespace normalized (`" ".join(...).split())` |

### Rules (from prompt)

- Do **not** add new facts or guess missing details.
- Keep proper nouns, company names, tools, numbers **exactly** as written.
- Preserve ordering and intent; lists stay lists.
- Expand abbreviations only when unambiguous.
- Remove filler, repetition, obvious typos.
- Output **only** the rewritten text (no JSON, no commentary).

### Persistence after rewrite

Before continuing, the pipeline creates:

- **RawExperience:** `raw_text`, `raw_text_original`, `raw_text_cleaned` (all set; `raw_text_cleaned` = rewrite output).
- **DraftSet:** linked to `raw_experience_id`, `person_id`, `run_version`.

---

## Stage 2: Extract (LLM → structured cards)

**Purpose:** From the **cleaned text**, extract **all** experience blocks in one pass as **parent cards + child dimension cards**, conforming to Schema V1.

**Function:** `chat.chat(extract_prompt, max_tokens=8192)` then `parse_llm_response_to_families(response_text, stage=EXTRACT)`  
**Prompt:** `PROMPT_EXTRACT_ALL_CARDS` (filled with `user_text`, `person_id`)

### Input

| Name          | Type   | Description                    |
|---------------|--------|--------------------------------|
| `user_text`   | string | Cleaned text from Stage 1      |
| `person_id`   | string | UUID of the person (metadata)  |

### LLM output format (expected JSON)

The LLM must return **only** valid JSON. Accepted shapes:

1. `{ "families": [ { "parent": {...}, "children": [...] }, ... ] }`
2. `{ "parents": [ { "parent": {...}, "children": [...] }, ... ] }` (legacy)
3. `[ { "parent": {...}, "children": [...] }, ... ]`
4. Single family: `{ "parent": {...}, "children": [...] }`

### Output schema (after parsing + Pydantic validation)

**Parsing:** `_strip_json_fence()` removes markdown code fences; `_extract_json_from_text()` finds first valid JSON object/array; then `V1Family` validation.

**Validated type:** `list[V1Family]` where each family is:

| Type         | Description |
|--------------|-------------|
| `V1Family`   | `parent: V1Card`, `children: list[V1Card]` |
| `V1Card`     | See below |

**V1Card (parent or child)** — main fields used downstream:

| Field        | Type                    | Description |
|-------------|-------------------------|-------------|
| `id`        | string \| None          | UUID; generated if missing |
| `headline`  | string \| None          | Short title |
| `title`     | string \| None          | |
| `summary`   | string \| None          | |
| `raw_text`  | string \| None          | Verbatim excerpt from cleaned text |
| `time`      | TimeInfo \| str \| None | `text`, `start`, `end`, `ongoing` |
| `location`  | LocationInfo \| str \| None | `text`, `city`, `country` |
| `roles`     | list[RoleInfo]         | `label`, `seniority` |
| `topics`    | list[TopicInfo]        | `label` |
| `entities`  | list[EntityInfo]       | `type`, `name` (company, team, organization) |
| `actions`   | list[dict]             | |
| `outcomes`  | list[dict]             | |
| `evidence`  | list[dict]             | |
| `tooling`   | any \| None            | |
| `company`   | string \| None         | |
| `organization` | string \| None      | |
| `team`      | string \| None         | |
| `index`     | IndexInfo \| None      | `search_phrases: list[str]` |
| `intent`    | string \| None         | Must be one of `Intent` (see domain) |
| `child_type`| string \| None         | Only for children; one of `ALLOWED_CHILD_TYPES` |
| `parent_id` | string \| None         | Set in metadata injection |
| `depth`     | int \| None            | 0 = parent, 1 = child |
| `relation_type` | string \| None     | One of `ChildRelationType` |

**Nested types:**

- **TimeInfo:** `text`, `start`, `end`, `ongoing`
- **LocationInfo:** `text`, `city`, `country`
- **RoleInfo:** `label`, `seniority`
- **TopicInfo:** `label`
- **EntityInfo:** `type`, `name`
- **IndexInfo:** `search_phrases`

**Intent enum (parent):** `work`, `education`, `project`, `business`, `research`, `practice`, `exposure`, `achievement`, `transition`, `learning`, `life_context`, `community`, `finance`, `other`, `mixed` (from `src/domain.py`).

**Allowed child_type:** From `src/domain.py` → `ALLOWED_CHILD_TYPES` (e.g. skills, tools, outcomes, etc.); one child per `child_type` per parent (merge into one child’s `value`).

After extraction, **metadata injection** runs: `inject_metadata_into_family(family, person_id)` sets `person_id`, `created_by`, `created_at`, `updated_at`, `parent_id`, `depth`, and UUIDs for parent/children.

---

## Stage 3: Validate (optional enrichment + schema gate)

**Purpose:** Validate, normalize, de-duplicate, remove hallucinated content, enforce schema and parent-split rules.

**Function:** `fill_prompt(PROMPT_VALIDATE_ALL_CARDS, parent_and_children_json=...)` then `parse_llm_response_to_families(validate_response, stage=VALIDATE)`  
**Prompt:** `PROMPT_VALIDATE_ALL_CARDS`

### Input

| Name                     | Type   | Description |
|--------------------------|--------|-------------|
| `raw_text_original`      | string | Original user text |
| `raw_text_cleaned`       | string | Rewritten text from Stage 1 |
| `parent_and_children_json` | string | JSON of `{ "raw_text_original", "raw_text_cleaned", "families": [ { "parent", "children" }, ... ] }` (extraction output) |

### Output schema

Same as Stage 2: **list[V1Family]** (re-validated with same `V1Family` / `V1Card` Pydantic models). If validation LLM fails or returns invalid JSON, the pipeline **falls back to extraction output** and re-injects metadata.

---

## Stage 4: Persist (DB write)

**Purpose:** Map each validated `V1Family` to DB rows: one **ExperienceCard** (parent) and zero or more **ExperienceCardChild** per family. No embeddings yet.

**Function:** `persist_families(db, families, person_id, raw_experience_id, draft_set_id)`  
**Helpers:** `card_to_experience_card_fields()`, `card_to_child_fields()`

### Input

| Name                | Type   | Description |
|---------------------|--------|-------------|
| `db`                | AsyncSession | DB session |
| `families`          | list[V1Family] | Validated families |
| `person_id`         | string | Person UUID |
| `raw_experience_id` | string | RawExperience.id |
| `draft_set_id`      | string | DraftSet.id |

### Mapping: V1Card → ExperienceCard (parent)

Fields derived from `V1Card` via helpers (e.g. `extract_time_fields`, `extract_location_fields`, `extract_company`, `extract_team`, `extract_role_info`, `extract_search_phrases`, `normalize_card_title`):

| DB column (ExperienceCard) | Source / logic |
|----------------------------|----------------|
| `user_id` / `person_id`    | `person_id` |
| `raw_text`                 | `card.raw_text` (strip) |
| `title`                    | `normalize_card_title(card)` (headline → title → summary first line → raw_text first line → "Experience") |
| `normalized_role`          | First role’s `label` |
| `company_name`             | `card.company` or `card.organization` or first entity with type company/organization |
| `start_date`, `end_date`   | Parsed from `time.start` / `time.end` (ISO date) |
| `is_current`                | `time.ongoing` |
| `location`                  | `location.text` or `location.city` |
| `summary`                   | `card.summary` (truncated 10000) |
| `intent_primary`            | `card.intent` |
| `seniority_level`           | First role’s `seniority` |
| `search_phrases`            | `card.index.search_phrases` (up to 50) |
| `search_document`           | Concatenation of: headline/title, summary, role, company, location text, tags (used later for embedding) |
| `embedding`                 | `None` (set in Stage 5) |

### Mapping: V1Card → ExperienceCardChild

| DB column (ExperienceCardChild) | Source / logic |
|----------------------------------|----------------|
| `parent_experience_id`          | Parent’s `ExperienceCard.id` |
| `person_id`, `raw_experience_id`, `draft_set_id` | From args |
| `child_type`                     | `card.child_type` (must be in `ALLOWED_CHILD_TYPES`) |
| `label`                          | `normalize_card_title(card)` |
| `value`                          | JSONB dimension container: headline, summary, raw_text, time, location, roles, topics, entities, actions, outcomes, tooling, evidence, company, team, tags, depth, relation_type |
| `search_phrases`                 | `card.index.search_phrases` |
| `search_document`               | headline + summary + role + company + team + location + tags |
| `embedding`                     | `None` (set in Stage 5) |

### Output

- **Return:** `(parents: list[ExperienceCard], children: list[ExperienceCardChild])`
- All rows are `db.add()` and `flush`/`refresh`; transaction committed by the caller.

---

## Stage 5: Embed

**Purpose:** Generate one vector per card (parent and child) from its **search document** text, then store normalized vectors in the DB.

**Function:** `embed_cards(db, parents, children)`  
**Provider:** `get_embedding_provider()` → `EmbeddingProvider.embed(texts: list[str]) -> list[list[float]]`  
**Util:** `normalize_embedding(vec, dim=provider.dimension)` for fixed-length vectors.

### Input (to embedding step)

| Name       | Type                          | Description |
|------------|-------------------------------|-------------|
| `parents`  | list[ExperienceCard]          | Persisted parent cards |
| `children` | list[ExperienceCardChild]     | Persisted child cards |

**Text used for each card:**

- **Parent:** `parent.search_document` if present, else `_experience_card_search_document(parent)` (title, normalized_role, domain, sub_domain, company_name, company_type, location, employment_type, summary, raw_text, intent_primary, intent_secondary, seniority_level, date range, “current”).
- **Child:** `child.search_document` (trimmed); skipped if empty.

Order: all parent documents first, then all child documents. Same order is used to assign vectors back to the same card.

### Embedding API (OpenAI-compatible)

**Provider:** `OpenAICompatibleEmbeddingProvider` in `src/providers/embedding.py`.

**Request:**

- **URL:** `{EMBED_API_BASE_URL}/v1/embeddings`
- **Method:** POST
- **Headers:** `Content-Type: application/json`, optional `Authorization: Bearer {EMBED_API_KEY}`
- **Body schema:**

| Field   | Type         | Description |
|---------|--------------|-------------|
| `model` | string       | From config (`EMBED_MODEL`) |
| `input` | array of strings | List of search-document strings (batch) |

**Response (expected):**

| Field     | Type  | Description |
|-----------|-------|-------------|
| `data`    | array | Each item: `{ "index": number, "embedding": number[] }` |
| Order     | —     | Vectors ordered by `index` before use |

### Output (after embedding)

1. **Vectors:** `list[list[float]]`, one per text (same length as `embed_texts`).
2. **Normalization:** Each vector is passed to `normalize_embedding(vec, dim=provider.dimension)`:
   - If `len(vec) < dim`: zero-pad to `dim`.
   - If `len(vec) >= dim`: truncate to `dim`.
   - Default `dim` from config (e.g. **384** in `src/core/constants.py` and DB `Vector(384)`).
3. **Persistence:** Each parent/child object’s `embedding` column is set to the corresponding normalized vector; then `db.flush()`.

### Embedding schema summary

| Step       | Input                    | Output                         |
|------------|--------------------------|--------------------------------|
| Collect    | Parents + children       | `embed_texts: list[str]`       |
| API call   | `{ "model", "input": embed_texts }` | `data[].embedding`      |
| Normalize  | `vec`, `dim` (e.g. 384)  | `list[float]` length 384       |
| Persist    | Normalized vector        | `ExperienceCard.embedding` / `ExperienceCardChild.embedding` |

---

## End-to-end data flow (schemas)

| Stage    | Input schema / type     | Output schema / type                    |
|----------|-------------------------|------------------------------------------|
| 0        | `RawExperienceCreate`   | — (raw_text passed on)                   |
| 1 Rewrite| `str` (raw_text)        | `str` (cleaned)                          |
| 2 Extract| cleaned `str` + person_id | `list[V1Family]` (parsed + validated)  |
| 3 Validate| raw + cleaned + families JSON | `list[V1Family]` (validated)     |
| 4 Persist| `list[V1Family]`        | `(list[ExperienceCard], list[ExperienceCardChild])` |
| 5 Embed  | Parents + children (ORM instances) | `list[str]` → API → `list[list[float]]` → normalized → DB `Vector(384)` |

---

## Error handling

- **PipelineError:** Raised with `stage` (REWRITE, EXTRACT, VALIDATE, PERSIST, EMBED) and message; optional `cause`.
- **Stage 1:** Empty or missing `raw_text` → HTTP 400. Empty rewrite result or chat failure → PipelineError(REWRITE).
- **Stage 2/3:** Invalid or empty JSON, or no valid families after validation → PipelineError(EXTRACT/VALIDATE). Validation can fall back to extraction output.
- **Stage 4:** DB errors → PipelineError(PERSIST).
- **Stage 5:** Embedding API errors (e.g. timeout, bad status) → `EmbeddingServiceError`; length mismatch (vectors vs cards) → PipelineError(EMBED).

---

## Files reference

| Area        | File(s) |
|------------|---------|
| Pipeline   | `src/services/experience_card_pipeline.py` |
| Prompts    | `src/prompts/experience_card.py`, `src/prompts/experience_card_enums.py` |
| Embedding  | `src/providers/embedding.py` |
| Search doc | `src/services/experience_card.py` (`_experience_card_search_document`) |
| Normalize  | `src/utils.py` (`normalize_embedding`) |
| Config     | `src/core/constants.py` (EMBEDDING_DIM), `src/core/config.py` (embed_*) |
| Schemas    | `src/schemas/builder.py` (RawExperienceCreate, etc.), `src/domain.py` (enums) |
| Models     | `src/db/models.py` (RawExperience, DraftSet, ExperienceCard, ExperienceCardChild) |
