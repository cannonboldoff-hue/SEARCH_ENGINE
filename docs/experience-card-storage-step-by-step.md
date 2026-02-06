# Experience Card Storage — Step-by-Step (Detailed)

This document describes **in detail** how experience cards are stored from the moment the user enters raw text in the Builder until cards are saved and searchable. Every step is tied to actual files and behavior in the codebase.

---

## Table of Contents

1. [Overview](#overview)
2. [Data model](#data-model)
3. [Phase 1: User input and draft request](#phase-1-user-input-and-draft-request)
4. [Phase 2: API receives draft request](#phase-2-api-receives-draft-request)
5. [Phase 3: V1 pipeline — first storage (DRAFT)](#phase-3-v1-pipeline--first-storage-draft)
6. [Phase 4: Frontend displays drafts and user saves](#phase-4-frontend-displays-drafts-and-user-saves)
7. [Phase 5: Commit — second storage (APPROVED + embedding)](#phase-5-commit--second-storage-approved--embedding)
8. [Phase 6: Reading stored cards](#phase-6-reading-stored-cards)
9. [Summary table and diagram](#summary-table-and-diagram)

---

## Overview

Experience cards reach storage in two main ways:

| Path | When | Result |
|------|------|--------|
| **V1 pipeline (Builder)** | User types raw text → clicks **Update** → then **Save Cards** | Multiple cards (parent + children per “atom”) stored as DRAFT, then APPROVED with embeddings |
| **Direct create** | `POST /experience-cards` with a single card payload | One card created in DRAFT (no pipeline) |

This document focuses on the **V1 pipeline**, which is what the Builder UI uses.

**Storage happens in two stages:**

1. **First storage:** When the user clicks **Update**, the API runs the draft-v1 pipeline and **persists** one `RawExperience` row and multiple `ExperienceCard` rows with **status = DRAFT** (no embedding).
2. **Second storage:** When the user clicks **Save Cards**, the frontend calls **commit** for that draft set; the API **updates** those same cards to **status = APPROVED** and computes and stores **embeddings**.

---

## Data model

### Tables involved

| Table | Purpose |
|-------|--------|
| **`raw_experiences`** | One row per “Update” submit; stores the exact text the user typed. Columns: `id`, `person_id`, `raw_text`, `created_at`. |
| **`experience_cards`** | One row per card (parent or child). Columns include: `id`, `person_id`, `raw_experience_id`, `status` (DRAFT / APPROVED / HIDDEN), `title`, `context`, `tags`, `company`, `team`, `role_title`, `time_range`, `location`, `embedding` (nullable). |

**File:** `apps/api/src/db/models.py` — `RawExperience`, `ExperienceCard`.

### Status and embedding rules

- **DRAFT:** Card is editable/reviewable; **embedding is NULL**; not used in search.
- **APPROVED:** Card is searchable; **embedding must be set** (vector computed from card text).
- **HIDDEN:** Card is hidden from profile/search (e.g. user hid it).

**Draft set identity:** In this codebase, **one raw experience = one draft set**. The `draft_set_id` returned to the frontend is the same as `raw_experience_id`. Commit uses `raw_experience_id` to find all DRAFT cards for that run.

---

## Phase 1: User input and draft request

### Step 1.1 — User lands on Builder and types raw text

- **File:** `apps/web/src/app/(authenticated)/builder/page.tsx`
- User is on the Builder page (authenticated).
- User types or pastes **raw experience text** into the textarea (e.g. “I worked at Razorpay in the backend team for 2 years…”).
- React state holds this in **`rawText`** (updated on every change).

### Step 1.2 — User clicks “Update”

- **File:** `apps/web/src/app/(authenticated)/builder/page.tsx`
- Clicking **Update** triggers **`extractDraftV1`** (useCallback).
- If `rawText` is empty, it clears `draftSetId` and `cardFamilies` and returns.
- Otherwise it sets **`isUpdating(true)`** and sends the request.

### Step 1.3 — Frontend sends POST to create drafts

- **File:** `apps/web/src/app/(authenticated)/builder/page.tsx` (inside `extractDraftV1`)
- **Request:**
  - **Method:** `POST`
  - **URL:** `/experience-cards/draft-v1` (relative to API base, e.g. `NEXT_PUBLIC_API_BASE_URL`)
  - **Body:** `{ "raw_text": "<user's raw text>" }`
- **File:** `apps/web/src/lib/api.ts` — `api<T>(path, { method: "POST", body })`:
  - Sets `Content-Type: application/json`
  - Adds `Authorization: Bearer <token>` from `localStorage.getItem("token")`
  - Fetches `API_BASE + path`
  - Throws on non-2xx; returns parsed JSON

### Step 1.4 — Frontend receives response and updates state

- **Response type:** `DraftSetV1Response` — `{ draft_set_id, raw_experience_id, card_families }`
- **File:** `apps/web/src/app/(authenticated)/builder/page.tsx`
- On success:
  - `setDraftSetId(result.draft_set_id ?? null)`
  - `setCardFamilies(result.card_families ?? [])`
- `isUpdating` is set to `false` in `finally`.
- On error, the catch block runs (e.g. logs and leaves state unchanged).

---

## Phase 2: API receives draft request

### Step 2.1 — Request hits FastAPI and dependencies run

- **File:** `apps/api/src/main.py` — Builder routes are mounted via `ROUTERS` (no global prefix).
- **File:** `apps/api/src/routers/builder.py`
- **Route:** `POST /experience-cards/draft-v1`, handler **`create_draft_cards_v1`**.

**Dependencies (run in order):**

1. **`get_current_user`** (`apps/api/src/dependencies.py`):
   - Reads `Authorization: Bearer <token>`
   - Decodes JWT via `decode_access_token(token)` → `user_id`
   - Loads **Person** from DB by `user_id`; if missing or invalid → **401**
2. **`get_db`** (`apps/api/src/dependencies.py`):
   - Yields an **AsyncSession** (async SQLAlchemy session)
   - On **success:** when the request handler finishes, **`await session.commit()`** is run
   - On **exception:** **`await session.rollback()`** then re-raise

### Step 2.2 — Request body parsed

- Body is parsed as **`RawExperienceCreate`** (Pydantic): field **`raw_text: str`**.
- **File:** `apps/api/src/schemas.py` (where `RawExperienceCreate` is defined).

### Step 2.3 — Handler calls the V1 pipeline

- **File:** `apps/api/src/routers/builder.py`
- **Code:**  
  `draft_set_id, raw_experience_id, card_families = await run_draft_v1_pipeline(db, current_user.id, body)`
- **Exceptions:** `ChatRateLimitError` → **429**; `ChatServiceError` → **503**.

### Step 2.4 — Response returned

- **Response model:** `DraftSetV1Response` with:
  - `draft_set_id: str`
  - `raw_experience_id: str` (same value as `draft_set_id` in current implementation)
  - `card_families: list[CardFamilyV1Response]` — each has `parent` and `children` (card objects with `id`, `title`, `context`, `tags`, etc.)
- After the handler returns, **`get_db`** commits the session → all DB changes from the pipeline are committed in **one transaction**.

---

## Phase 3: V1 pipeline — first storage (DRAFT)

**File:** `apps/api/src/services/experience_card_pipeline.py` — **`run_draft_v1_pipeline(db, person_id, body)`**

This is where the **first** database writes for experience cards happen.

### Step 3.1 — Create RawExperience row

- **Code:**  
  `raw = RawExperience(person_id=person_id, raw_text=body.raw_text)`  
  `db.add(raw)`  
  `await db.flush()`
- **Effect:** One row inserted into **`raw_experiences`** with server-generated `id`, `person_id`, `raw_text`, `created_at`.
- **Variables:** `raw_experience_id = str(raw.id)`, `draft_set_id = raw_experience_id` (used in response and later for commit).

### Step 3.2 — Atomize raw text (LLM)

- **Prompt:** **`PROMPT_EXTRACT_ALL_CARDS`** from `apps/api/src/prompts/experience_card.py`, filled with cleaned text and `person_id`.
- **Code:** `response = await chat.chat(prompt, max_tokens=1024)` then **`_parse_json_array(response)`**.
- **Result:** List of **atoms** (e.g. each with `atom_id`, `raw_text_span`, `suggested_intent`, `why`).
- **If list is empty:** function returns `(draft_set_id, raw_experience_id, [])` — no cards are created; commit still happens (only `raw_experiences` row).

**No DB write in this step** — only in-memory atoms.

### Step 3.3 — For each atom: parent + children extraction (LLM, one prompt)

- **Input:** `raw_span = atom.get("raw_text_span") or atom.get("raw_text") or ""` (skip if empty).
- **Prompt:** **`PROMPT_PARENT_AND_CHILDREN`** with `atom_text=raw_span`, `person_id=person_id`.
- **Code:** `response = await chat.chat(prompt, max_tokens=4096)` then **`_parse_json_object(response)`** → **`{ "parent": {...}, "children": [...] }`**.
- **Metadata:** **`_inject_parent_metadata(parent, person_id)`** ensures parent has `id` (UUID if missing), `person_id`, `created_by`, timestamps, `parent_id=None`, `depth=0`, `relation_type=None`. Each child is passed through **`_inject_child_metadata(child, parent_id)`** (id, parent_id, depth=1, timestamps).  
  Note: These ids are used only for in-pipeline linking. The **persisted** cards get **new server-generated ids** in the persist step.

### Step 3.4 — For each atom: validation (LLM)

- **Input:** `combined = {"parent": parent, "children": children}`.
- **Prompt:** **`PROMPT_VALIDATOR`** with `parent_and_children_json=json.dumps(combined)`.
- **Code:** `response = await chat.chat(prompt, max_tokens=4096)` then **`_parse_json_object(response)`** → **validated**.
- **Use:** `v_parent = validated.get("parent") or parent`, `v_children = validated.get("children") or children`; build **`family = {"parent": v_parent, "children": v_children}`**.

### Step 3.5 — For each atom: persist family to DB (first storage)


- **Function:** **`_persist_v1_family(db, person_id, raw_experience_id, family)`** in `experience_card_pipeline.py`.

**For the parent:**

1. **`_v1_card_to_experience_card_fields(parent, person_id, raw_experience_id)`** builds a dict of **ExperienceCard**-compatible fields:
   - **Not** including `id` — the DB will generate it (UUID).
   - Includes: `person_id`, `raw_experience_id`, `status=ExperienceCard.DRAFT`, `human_edited=False`, `locked=False`
   - `title` ← headline (truncated 500), `context` ← summary or raw_text (truncated 10000)
   - `constraints`, `decisions`, `outcome` ← None
   - `tags` ← from v1 “topics” (labels), max 50
   - `company` ← from model’s company/organization **only** (not location city)
   - `location` ← from model’s location (city/text/name)
   - `team` ← None; `role_title` from roles; `time_range` from time text
   - `embedding` ← None
2. **`parent_ec = ExperienceCard(**parent_kw)`**, **`db.add(parent_ec)`**, **`await db.flush()`**, **`await db.refresh(parent_ec)`** so `parent_ec.id` is available.

**For each child:**

1. Same **`_v1_card_to_experience_card_fields(child, ...)`** (no `id` in kwargs).
2. **`ec = ExperienceCard(**kwargs)`**, **`db.add(ec)`**, append to list, then **`await db.flush()`** and **`await db.refresh(ec)`** for each.

**Result:** One **parent** row and N **children** rows in **`experience_cards`**, all with **status = DRAFT**, **embedding = NULL**, linked to the same **`raw_experience_id`**. All ids are **server-generated** (UUID).

### Step 3.6 — Build response payload for this family

- **`_draft_card_to_family_item(card)`** converts a persisted **ExperienceCard** (parent or child) to the API response shape: `id`, `title`, `context`, `tags`, `headline`, `summary`, `topics`, `time_range`, `role_title`, `company`, `location`.
- **`card_families.append({ "parent": _draft_card_to_family_item(parent_ec), "children": [_draft_card_to_family_item(c) for c in child_ecs] })`**

So the frontend receives the **actual DB ids** in the response.

### Step 3.7 — Pipeline return and transaction commit

- After all atoms are processed, **`run_draft_v1_pipeline`** returns **`(draft_set_id, raw_experience_id, card_families)`**.
- The router builds **`DraftSetV1Response`** and returns it.
- When the request handler exits successfully, **`get_db`** runs **`await session.commit()`** → the **`raw_experiences`** row and all **`experience_cards`** rows (DRAFT) are **committed** in one transaction.

---

## Phase 4: Frontend displays drafts and user saves

### Step 4.1 — Builder renders card families

- **File:** `apps/web/src/app/(authenticated)/builder/page.tsx`
- **State:** `cardFamilies` is a list of families; each has `parent` and `children` (with `id`, `title`, `context`, `tags`, etc.).
- The right panel renders these families (expand/collapse, delete, edit if implemented). The **ids** are the same as **`experience_cards.id`** in the DB.

### Step 4.2 — User clicks “Save Cards”

- This opens **SaveCardsModal** (e.g. **`setSaveModalOpen(true)`**).
- **File:** `apps/web/src/components/builder/save-cards-modal.tsx` — modal with “Confirm Save” and “Cancel”.

### Step 4.3 — User confirms: frontend calls commit

- **File:** `apps/web/src/app/(authenticated)/builder/page.tsx` — **`handleSaveCards`**:
  - **`setSaveError(null)`**, **`setIsSavingAll(true)`**
  - If **`draftSetId`** is set:
    - **Request:**  
      **POST** `/draft-sets/{draftSetId}/commit`  
      **Body:** `{}`
    - Uses **`api<ExperienceCard[]>(...)`** (same auth and API base as before).
  - On success: **`setSaveModalOpen(false)`**, **`setDraftSetId(null)`**, **`setCardFamilies(null)`**, **`queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY })`**, **`router.push("/home")`**
  - On error: **`setSaveError(...)`**, still invalidates queries, **`setIsSavingAll(false)`** in `finally`

So storage is **committed in one shot** per draft set (Pattern A), not per-card approve.

---

## Phase 5: Commit — second storage (APPROVED + embedding)

### Step 5.1 — Commit route and dependencies

- **File:** `apps/api/src/routers/builder.py`
- **Route:** **POST** `/draft-sets/{draft_set_id}/commit`
- **Handler:** **`commit_draft_set(draft_set_id, body, current_user, db)`**
- **Dependencies:** Same **`get_current_user`** and **`get_db`** (commit on success, rollback on exception).
- **Body:** Optional **`CommitDraftSetRequest`** (e.g. `card_ids: list[str] | None` for partial selection). Frontend currently sends `{}`, so all drafts in the set are committed.

### Step 5.2 — Load DRAFT cards for this draft set

- **Code:**  
  `cards = await experience_card_service.list_drafts_by_raw_experience(db, current_user.id, draft_set_id, card_ids=(body.card_ids if body else None))`
- **File:** `apps/api/src/services/experience_card.py` — **`list_draft_cards_by_raw_experience`**:
  - Query: **`ExperienceCard`** where **`person_id == current_user.id`**, **`raw_experience_id == raw_experience_id`** (here `draft_set_id` is the `raw_experience_id`), **`status == DRAFT`**
  - If **`card_ids`** is provided, filter by **`ExperienceCard.id.in_(card_ids)`**
  - Order by **`created_at`** ascending.
- If **no cards** are found → **404** “No draft cards found for this draft set.”

### Step 5.3 — Approve batch (status + embedding)

- **Code:**  
  `cards = await experience_card_service.approve_batch(db, cards)`  
  (wrapped in try/except for **EmbeddingServiceError** → **503**)
- **File:** `apps/api/src/services/experience_card.py` — **`approve_cards_batch`**:
  1. Build **searchable text** for each card: **`_card_searchable_text(card)`** concatenates `title`, `context`, `company`, `team`, `role_title`, `time_range`, `location`, and `tags`.
  2. **`get_embedding_provider().embed(texts)`** — one vector per card (e.g. 384-dim).
  3. If **`len(vectors) != len(cards)`** → raise **EmbeddingServiceError**.
  4. For each card and vector: **`card.status = ExperienceCard.APPROVED`**, **`card.embedding = normalize_embedding(vec)`**.
  5. Return the same **card** objects (modified in place).

No explicit **`db.add`** — cards are already in the session; SQLAlchemy tracks the changes.

### Step 5.4 — Response and commit

- **Return:** **`[experience_card_to_response(c) for c in cards]`** → list of **ExperienceCardResponse**.
- When the handler finishes, **`get_db`** commits → **UPDATE** on **`experience_cards`** for each row: **`status = 'APPROVED'`** and **`embedding`** set. This is the **second storage step** (update of existing rows).

---

## Phase 6: Reading stored cards

When the app needs the user’s saved cards (e.g. home, profile, or Builder “saved” list):

### Step 6.1 — Frontend request

- **Hook:** **`useExperienceCards()`** from `apps/web/src/hooks/use-experience-cards.ts` (or similar).
- **Query key:** e.g. **`["experience-cards"]`** (or **`EXPERIENCE_CARDS_QUERY_KEY`**).
- **Request:** **GET** `/me/experience-cards` (optional **`?status=DRAFT`** or **`APPROVED`** or **`HIDDEN`**).

### Step 6.2 — API list endpoint

- **File:** `apps/api/src/routers/me.py` — **GET** `/me/experience-cards` (me router typically has prefix **`/me`**).
- **Handler:** **`list_my_experience_cards`**:
  - **`experience_card_service.list_cards(db, current_user.id, status_filter)`**
- **File:** `apps/api/src/services/experience_card.py` — **`list_my_cards`**:
  - **Select** **ExperienceCard** where **`person_id == person_id`**
  - If **`status_filter`** is set: **`status == status_filter`**
  - Else: **`status != HIDDEN`**
  - Order by **`created_at.desc()`**
- **Return:** **`[experience_card_to_response(c) for c in cards]`**

**No write** — read-only from **`experience_cards`**.

---

## Summary table and diagram

### When and where storage happens

| Step | What is stored | Table(s) | When |
|------|-----------------|----------|------|
| 3.1  | Raw user text  | **raw_experiences** | Start of **run_draft_v1_pipeline**; one row per “Update”. |
| 3.6  | Draft cards (parent + children) | **experience_cards** | **`_persist_v1_family`** after each atom’s validate; **status = DRAFT**, **embedding = NULL**. |
| 2.4 / 3.8 | Transaction commit | Both | End of **POST /experience-cards/draft-v1** request (**get_db** commit). |
| 5.3–5.4 | Approved cards (status + embedding) | **experience_cards** | **POST /draft-sets/{id}/commit** → **approve_batch** → **UPDATE** same rows. |

### End-to-end flow (simplified)

```text
[User types raw text in Builder]
        ↓
[Click "Update"]
        ↓
[Frontend] POST /experience-cards/draft-v1 { raw_text }
        ↓
[API] get_current_user, get_db
        ↓
[API] run_draft_v1_pipeline
  → INSERT raw_experiences (raw text)
  → Atomize (LLM) → for each atom:
      → Parent + children (LLM, one prompt) → Validate (LLM)
      → _persist_v1_family → INSERT experience_cards (DRAFT, no embedding)
  → Return draft_set_id, raw_experience_id, card_families
        ↓
[API] get_db commit → raw_experiences + experience_cards (DRAFT) persisted
        ↓
[Frontend] Renders families; user clicks "Save Cards" → Confirm
        ↓
[Frontend] POST /draft-sets/{draft_set_id}/commit { }
        ↓
[API] list_drafts_by_raw_experience(person_id, draft_set_id)
        ↓
[API] approve_batch → _card_searchable_text, embed(), status=APPROVED, embedding=...
        ↓
[API] get_db commit → UPDATE experience_cards (same rows)
        ↓
[Frontend] invalidateQueries → GET /me/experience-cards → show saved cards; redirect to /home
```

---

## Optional: Direct create (no V1 pipeline)

- **Endpoint:** **POST** `/experience-cards` with body **ExperienceCardCreate** (e.g. `raw_experience_id`, `title`, `context`, …).
- **File:** `apps/api/src/routers/builder.py` → **`experience_card_service.create_card(db, current_user.id, body)`**
- **File:** `apps/api/src/services/experience_card.py` — **`create_experience_card`**: one **ExperienceCard** with **status = DRAFT**, no embedding, **db.add(card)**, flush, refresh. Same request-scoped commit via **get_db**. No atomizer/parent/child/validator.

---

## Key files reference

| Layer | File | Relevant pieces |
|-------|------|------------------|
| **DB** | `apps/api/src/db/models.py` | `RawExperience`, `ExperienceCard` (status, embedding) |
| **API routes** | `apps/api/src/routers/builder.py` | `POST /experience-cards/draft-v1`, `POST /draft-sets/{id}/commit` |
| **Pipeline** | `apps/api/src/services/experience_card_pipeline.py` | `run_draft_v1_pipeline`, `_persist_v1_family`, `_v1_card_to_experience_card_fields` |
| **Card service** | `apps/api/src/services/experience_card.py` | `list_draft_cards_by_raw_experience`, `approve_cards_batch`, `list_my_cards` |
| **Prompts** | `apps/api/src/prompts/experience_card.py` | PROMPT_REWRITE, PROMPT_CLEANUP, PROMPT_EXTRACT_ALL_CARDS, PROMPT_VALIDATE_ALL_CARDS |
| **Auth/DB** | `apps/api/src/dependencies.py` | `get_current_user`, `get_db` (commit/rollback) |
| **Frontend** | `apps/web/src/app/(authenticated)/builder/page.tsx` | `extractDraftV1`, `handleSaveCards`, state (rawText, draftSetId, cardFamilies) |
| **Frontend** | `apps/web/src/components/builder/save-cards-modal.tsx` | Save confirmation modal |
| **Frontend** | `apps/web/src/lib/api.ts` | `api<T>()` — auth header, API base, JSON body |

This is the full step-by-step flow of how experience card storage works from start to finish.
