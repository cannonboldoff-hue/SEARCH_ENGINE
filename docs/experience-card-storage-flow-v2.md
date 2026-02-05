# Experience Card Storage Flow (Corrected v2)

This document describes how **experience cards** move from the Builder UI to persisted storage, and how they transition from **draft** → **approved**.

> Goal of this doc: be **internally consistent**, safe to operate, and explicit about where the system has *draft preview* vs *persisted data* semantics.

---

## Glossary

- **Raw Experience**: the unstructured text a user types in the Builder.
- **Card Family**: `{ parent, children[] }` produced from one atomized segment of Raw Experience.
- **Draft**: a stored card that is editable/reviewable and not yet searchable.
- **Approved**: a stored card that is searchable (embedding computed and saved).
- **Draft Set**: a grouping token for “one run” of draft generation.

---

## Data Model (conceptual)

### `raw_experiences`
Stores the user’s raw Builder input so that generated cards can reference the source text.

Minimum fields:
- `id`
- `person_id`
- `raw_text`
- `created_at`

### `experience_cards`
Stores each card, regardless of whether it is draft or approved.

Minimum fields:
- `id` (server-generated)
- `person_id`
- `raw_experience_id`
- `status` ∈ { `DRAFT`, `APPROVED`, `HIDDEN` }
- `title`
- `context`
- `tags[]`
- `time_range` (optional)
- `role_title` (optional)
- `company` (optional)
- `team` (optional)
- `embedding` (nullable; present only after approval)

> Important: **Never treat LLM-provided identifiers as DB ids.**
> The DB/service should generate `experience_cards.id`, and API responses return those ids to the client.

---

## Status State Machine

- `DRAFT` → `APPROVED` (on “Save Cards”)
- `APPROVED` → `HIDDEN` (user hides a card; implementation may vary)
- Optional: `DRAFT` → `HIDDEN` (discard a draft without approving)

**Embedding rule**
- `embedding` MUST be `NULL` when `status = DRAFT`
- `embedding` MUST be present when `status = APPROVED` (unless your system supports a retry state; see “Reliability”)

---

## Endpoints (Builder Flow)

### 1) Draft generation (preview)

**POST** `/experience-cards/draft-v1`  
Body: `{ "raw_text": "<user text>" }`

Returns (shape):
```json
{
  "draft_set_id": "<uuid>",
  "raw_experience_id": "<uuid-or-int>",
  "card_families": [
    {
      "parent": { "id": "...", "title": "...", "context": "...", "tags": [...] },
      "children": [{ "id": "...", "title": "...", "context": "...", "tags": [...] }]
    }
  ]
}
```

#### What this endpoint should do

1. **Authenticate** user and resolve `person_id`
2. **Create** a `raw_experiences` row and flush to get `raw_experience_id`
3. Run the **Draft V1 pipeline**:
   - atomize the raw text
   - extract a parent card for each atom
   - generate children cards for each parent
   - validate/clean each card
4. **Persist the cards as `DRAFT`** (if this is your chosen architecture) so the UI can approve them later by id.

> If you do **not** want drafts persisted on Update, then this endpoint must return **preview-only cards**
> and you need a separate “commit” endpoint that creates the DB rows on Save. Don’t mix the two models.

#### Error behavior (recommended)
- Chat rate limit → 429
- Chat provider/service failure → 503
- Invalid JSON from model → 502/500 (pick one; document it)

---

### 2) Approve cards (Save Cards)

There are two sane patterns. Pick one and keep it consistent.

#### Pattern A (recommended): commit the entire draft set in one request

**POST** `/draft-sets/{draft_set_id}/commit`  
Body: optional `{ "card_ids": ["..."] }` if you allow partial selection.

Server responsibilities:
- Validate ownership (`person_id`)
- Transition selected cards `DRAFT` → `APPROVED`
- Compute embeddings (batch if possible)
- Return the updated cards

Why this is better:
- One network call
- Easier to make transactional
- Easier to retry safely

#### Pattern B (legacy / simple): approve per card

**POST** `/experience-cards/{card_id}/approve`

Server responsibilities:
- Validate ownership (`person_id`)
- Set `status = APPROVED`
- Compute and store `embedding`
- Return the updated card

If you use this pattern, document:
- Whether the frontend uses `Promise.all` (parallel) or sequential calls
- How partial failures are handled (some approved, some not)
- Whether approve is **idempotent** (calling approve twice should not break anything)

---

## Draft V1 Pipeline (high level)

For each request to `/experience-cards/draft-v1`:

1. **Create Raw Experience row**
2. **Atomize** the raw text into segments (atoms)
3. For each atom:
   - **Parent extraction** (create one “parent” card object)
   - **Child generation** (create 0..N “child” card objects)
   - **Validation/cleanup** (truncate fields, normalize tags, etc.)
4. **Persist** cards as `DRAFT` linked to `raw_experience_id`

### Mapping rules (corrected)

When converting model output → `experience_cards` rows:

- `title`:
  - use the model headline/title, truncate to max length
- `context`:
  - use the model summary/context; fall back to atom raw span if missing
- `company`:
  - use only if the model extracted an organization/company
  - **do not** store `location_city` into `company`
- `time_range`:
  - keep only normalized text (or a structured range if you support it)
- `tags`:
  - normalize to an array of strings, cap the count (e.g., 50)
- `embedding`:
  - always `NULL` at draft time

---

## Frontend Builder Flow

1. User types raw experience text in the left panel.
2. User clicks **Update**:
   - UI calls `POST /experience-cards/draft-v1`
   - UI renders returned `card_families` on the right
3. User reviews and optionally edits (depending on features):
   - Expand/collapse families
   - Remove unwanted children
   - Edit title/context (if supported)
4. User clicks **Save Cards**:
   - Pattern A: call `/draft-sets/{draft_set_id}/commit`
   - Pattern B: call `/experience-cards/{id}/approve` for each card id

---

## Listing / Retrieval

**GET** `/experience-cards`

Recommended query behavior:
- Default: return cards where `status != HIDDEN`
- If `status=<value>` is provided: return only that status

Correct logical form:
- If `status_filter` is present: `status == status_filter`
- Else: `status != HIDDEN`

---

## Transactions & Consistency (important)

Avoid relying on vague statements like “the DB commits when the request ends” unless you have verified your session lifecycle.

Recommended documentation phrasing:
- “The API uses an `AsyncSession`. Changes are committed **after successful request handling** (either in request middleware or in a DB dependency teardown). On exceptions, the session is rolled back.”

If you persist drafts on Update:
- be explicit about draft lifecycle:
  - do you **replace** prior drafts for the same `draft_set_id`?
  - do you keep all drafts forever?
  - is there a cleanup job for old drafts?

---

## Reliability notes (embedding)

Embedding can fail after status transitions unless you protect the sequence.

Recommended safe behavior:
- Either compute embedding first, then set status `APPROVED` only after embedding success
- Or introduce an intermediate state like `APPROVING` / `EMBEDDING_FAILED` and retry

Also document:
- embedding provider
- vector dimension
- whether vectors are normalized
- whether approvals are retried

---

## Security & Integrity rules

- Enforce `ExperienceCard.person_id == current_user.id` on all mutations and reads
- Never trust client-provided ids other than as opaque references
- If you accept edits on save, validate length caps server-side

---

## What changed vs the old doc

This v2 doc fixes these common mistakes:

- Does **not** assume the LLM’s `id` becomes the DB primary key
- Does **not** map `company ← location_city`
- Uses correct filter logic for list queries
- Separates “draft preview” vs “draft persisted” as an explicit architectural choice
- Documents safe transaction and embedding semantics without making unverified claims

