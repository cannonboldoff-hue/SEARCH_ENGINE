# Experience Card Storage Flow — Step-by-Step

This document describes in detail how **experience cards** are created, stored, and persisted in the Search Engine app, from the moment the user enters raw text in the Builder until cards are saved in the database.

---

## Overview

Experience cards can reach storage in two ways:

1. **V1 pipeline (main flow)** — User writes raw experience text → API runs the draft-v1 pipeline (atomize → parent extract → child gen → validate) → cards are **persisted as DRAFT** → User clicks “Save Cards” → each card is **approved** (status → APPROVED, embedding computed and stored).
2. **Direct create** — API receives a single card payload via `POST /experience-cards` and creates one card in DRAFT.

The rest of this doc focuses on the **V1 pipeline flow**, which is what the Builder UI uses.

---

## 1. User Input (Frontend — Builder Page)

**File:** `apps/web/src/app/(authenticated)/builder/page.tsx`

1. User lands on the Builder page and types or pastes **raw experience text** into the textarea (e.g. “I worked at Razorpay in the backend team for 2 years…”).
2. State is held in React: `rawText` is updated on every change.
3. User clicks **“Update”**. This triggers `extractDraftV1`.

---

## 2. Request: Create Draft Cards (Frontend → API)

**File:** `apps/web/src/app/(authenticated)/builder/page.tsx`

1. `extractDraftV1` is called (useCallback).
2. It sends a **POST** request to the API:
   - **URL:** `/experience-cards/draft-v1`
   - **Body:** `{ raw_text: rawText }` (Pydantic schema: `RawExperienceCreate`).
3. The request is made via `api<DraftSetV1Response>(...)` from `@/lib/api`, which:
   - Uses `API_BASE` (e.g. `NEXT_PUBLIC_API_BASE_URL`) + path.
   - Sends `Authorization: Bearer <token>` from `localStorage.getItem("token")`.
   - Sends `Content-Type: application/json`.

---

## 3. API Router: Draft V1 Endpoint

**File:** `apps/api/src/routers/builder.py`

1. Route: **POST `/experience-cards/draft-v1`** (no router prefix; mounted at app root).
2. Dependencies run:
   - **`get_current_user`** — Validates Bearer token, loads `Person` from DB, returns 401 if invalid.
   - **`get_db`** — Yields an async SQLAlchemy `AsyncSession`; on success the session is **committed** when the request ends.
3. Request body is parsed as **`RawExperienceCreate`** (`raw_text: str`).
4. Handler calls:
   ```text
   draft_set_id, raw_experience_id, card_families = await run_draft_v1_pipeline(db, current_user.id, body)
   ```
5. Response: **`DraftSetV1Response`** with `draft_set_id`, `raw_experience_id`, and `card_families` (each family has `parent` and `children` dicts).

On **ChatRateLimitError** → 429; on **ChatServiceError** → 503.

---

## 4. V1 Pipeline: Where Cards Are First Stored (DRAFT)

**File:** `apps/api/src/services/experience_card_pipeline.py`

`run_draft_v1_pipeline(db, person_id, body)` does the following in order.

### 4.1 Create Raw Experience Row

1. Instantiate **`RawExperience`** with `person_id` and `raw_text=body.raw_text`.
2. `db.add(raw)` and `await db.flush()` so `raw.id` is available.
3. Store `raw_experience_id = raw.id` for linking all cards from this run.
4. Generate a **`draft_set_id`** (UUID) for this draft run (used in response only).

**DB table:** `raw_experiences`  
**Columns used:** `id`, `person_id`, `raw_text`, `created_at` (server default).

---

### 4.2 Atomize

1. Build prompt with **`PROMPT_EXTRACT_ALL_CARDS`** (from `src/prompts/experience_card.py`), filling in the user’s raw text.
2. Call **chat provider** (`get_chat_provider()`) with `chat.chat(prompt, max_tokens=1024)`.
3. Parse the LLM response as JSON array (**`_parse_json_array`**); each element is an **atom** (e.g. one experience segment).
4. If the result is empty, return `(draft_set_id, raw_experience_id, [])` — no DB writes for cards.

No DB write in this step; only in-memory atoms.

---

### 4.3 Per-Atom: Parent + Children in One Call

For each atom:

1. Get `raw_span` from the atom (`raw_text_span` or `raw_text`).
2. Build prompt with **`PROMPT_PARENT_AND_CHILDREN`** and `atom_text=raw_span`, `person_id=person_id`.
3. Call `chat.chat(prompt, max_tokens=4096)` and parse response as JSON object (**`_parse_json_object`**) → **combined** with `parent` and `children`.
4. **`_inject_parent_metadata(parent, person_id)`**: ensures `id` (UUID if missing), `person_id`, `created_by`, `created_at`, `updated_at`, `parent_id=None`, `depth=0`, `relation_type=None`.
5. **`_inject_child_metadata(child, parent_id)`** for each child: ensures `id`, `parent_id`, `depth=1`, `created_at`, `updated_at`.

Parent has a stable `id` used for children and for DB.

---

### 4.4 Per-Atom: Validation

1. Build **`combined = {"parent": parent, "children": children}`**.
2. Prompt with **`PROMPT_VALIDATOR`** and `parent_and_children_json=json.dumps(combined)`.
3. Call `chat.chat(prompt, max_tokens=4096)` and parse as JSON object → **validated**.
4. Use `validated.get("parent")` and `validated.get("children")` (fallback to current parent/children).
5. Build **`family = {"parent": v_parent, "children": v_children}`**; persist via **`_persist_v1_family`** and append to `card_families`.

---

### 4.5 Per-Atom: Persist Family to DB (First Storage of Cards)

1. **`_persist_v1_family(db, person_id, raw_experience_id, family)`** is called.
2. For the **parent** and each **child** in the family:
   - **`_v1_card_to_experience_card_fields(card, person_id, raw_experience_id)`** maps the v1 card dict to **`ExperienceCard`**-compatible fields:
     - `id` ← card’s `id` (so frontend can call approve by this id)
     - `person_id`, `raw_experience_id`
     - `status` = **`ExperienceCard.DRAFT`**
     - `human_edited=False`, `locked=False`
     - `title` ← headline (truncated 500), `context` ← summary or raw_text (truncated 10000)
     - `constraints`, `decisions`, `outcome` ← None
     - `tags` ← from v1 topics (labels), max 50
     - `company` ← from location city; `team` ← None; `role_title` ← from roles; `time_range` ← from time text
     - `embedding` ← None (filled only on approve)
   - **`ExperienceCard(**kwargs)`** is created and **`db.add(ec)`**.
3. **`await db.flush()`** so rows are written and IDs/constraints are applied (no commit yet; commit happens when the request ends via `get_db`).

**DB table:** `experience_cards`  
**Status at this point:** `DRAFT`. Each row has `person_id`, `raw_experience_id`, and the mapped title/context/tags/company/role_title/time_range. No embedding yet.

---

### 4.6 Pipeline Return

1. After all atoms are processed, **`run_draft_v1_pipeline`** returns `(draft_set_id, raw_experience_id, card_families)`.
2. The router builds **`DraftSetV1Response`** and returns it to the frontend.
3. When the request handler finishes, **`get_db`** commits the session → **`RawExperience`** and all new **`ExperienceCard`** rows are committed in one transaction.

---

## 5. Frontend After Draft: Display and “Save Cards”

**File:** `apps/web/src/app/(authenticated)/builder/page.tsx`

1. Frontend receives **`DraftSetV1Response`** and sets:
   - `setCardFamilies(result.card_families ?? [])`
   - Expands families by default (parent ids in `expandedFamilies`).
2. The right panel renders **card families**: each family has a **parent** (v1 card with `id`, headline, summary, topics, etc.) and **children** (each with `id`, headline, relation_type, etc.). These ids are the same as the **`experience_cards.id`** values now stored in the DB.
3. User can expand/collapse and review. When satisfied, user clicks **“Save Cards”**.
4. **SaveCardsModal** opens; on confirm, **`handleSaveCards`** runs.

---

## 6. Request: Approve Each Card (Save Cards)

**File:** `apps/web/src/app/(authenticated)/builder/page.tsx`

1. **`handleSaveCards`** builds the list of all card ids from the current `cardFamilies`:
   - For each family: `parent.id` (if present) and every `child.id` from `family.children`.
2. It calls **`POST /experience-cards/{id}/approve`** for **each** of these ids (e.g. `Promise.all(allIds.map(id => api(.../approve)))`).
3. No request body; card is identified by path parameter `id`.

---

## 7. API Router: Approve Endpoint

**File:** `apps/api/src/routers/builder.py`

1. Route: **POST `/experience-cards/{card_id}/approve`**.
2. **`get_experience_card_or_404`** (dependency):
   - Resolves **`card_id`** from path and **`current_user`** from auth.
   - Calls **`experience_card_service.get_card(db, card_id, current_user.id)`** which runs a **`select(ExperienceCard).where(ExperienceCard.id == card_id, ExperienceCard.person_id == person_id)`**.
   - If no row → **404 “Card not found”**.
   - Otherwise the **`ExperienceCard`** instance is injected into the handler.
3. Handler calls:
   ```text
   card = await experience_card_service.approve(db, card)
   ```
4. On **EmbeddingServiceError** → 503.
5. Response: **`experience_card_to_response(card)`** → **`ExperienceCardResponse`**.

Session is committed when the request ends (**`get_db`**).

---

## 8. Approve Logic: Status + Embedding (Second Storage Step)

**File:** `apps/api/src/services/experience_card.py`

1. **`approve_experience_card(db, card)`** (used by `experience_card_service.approve`):
   - Sets **`card.status = ExperienceCard.APPROVED`**.
   - Builds searchable text with **`_card_searchable_text(card)`**: concatenates `title`, `context`, `company`, `team`, `role_title`, `time_range`, and `tags`.
   - Calls **`get_embedding_provider().embed([text])`** to get a vector (e.g. 384-dim for bge-base).
   - **`normalize_embedding(vectors[0])`** and assigns to **`card.embedding`**.
   - Returns the same **`card`** instance (modified in place).
2. No explicit `db.add`; the card was already loaded in the session, so SQLAlchemy tracks the change.
3. When the request ends, **commit** flushes the update to **`experience_cards`**: **`status = 'APPROVED'`** and **`embedding`** column updated.

**DB table:** `experience_cards`  
**Columns updated:** `status`, `embedding`. The row was inserted in step 4.6; this is an **UPDATE**.

---

## 9. Frontend After Save

**File:** `apps/web/src/app/(authenticated)/builder/page.tsx`

1. After all **approve** requests succeed:
   - **`queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY })`** so the list of saved cards refetches.
   - **`setSaveModalOpen(false)`** and **`router.push("/home")`**.
2. If any request fails, **`setSaveError(...)`** and cache is still invalidated so UI can show fresh state.

---

## 10. Reading Stored Cards: List My Experience Cards

When the app needs the current user’s saved cards (e.g. Builder “Saved cards” list, or profile):

1. **Frontend:** **`useExperienceCards()`** (from `apps/web/src/hooks/use-experience-cards.ts`) runs a query with key **`["experience-cards"]`** and **`queryFn: () => api<ExperienceCard[]>("/me/experience-cards")`**.
2. **Request:** **GET `/me/experience-cards`** (optional query: `?status=DRAFT|APPROVED|HIDDEN`). The **me** router has **prefix `/me`**.
3. **API:** **`apps/api/src/routers/me.py`** — **`list_my_experience_cards`**:
   - **`experience_card_service.list_cards(db, current_user.id, status_filter)`** runs **`select(ExperienceCard).where(person_id=..., status != HIDDEN or status = status_filter).order_by(created_at.desc())`**.
   - Returns **`[experience_card_to_response(c) for c in cards]`**.
4. **DB:** Reads from **`experience_cards`**; no writes.

---

## Summary: Storage Points

| Step | What is stored | Table(s) | When |
|------|-----------------|----------|------|
| 4.1  | Raw user text  | `raw_experiences` | Start of draft-v1 pipeline; one row per “Update” submit. |
| 4.6  | Draft cards (parent + children) | `experience_cards` | After each atom’s validate; status **DRAFT**, no embedding. |
| 4.7  | Transaction commit | Both | End of **POST /experience-cards/draft-v1** request. |
| 8    | Approved card (status + embedding) | `experience_cards` | **POST /experience-cards/{id}/approve**; UPDATE same row. |

---

## Optional: Direct Create (No V1 Pipeline)

- **Endpoint:** **POST `/experience-cards`** with body **`ExperienceCardCreate`** (e.g. `raw_experience_id`, `title`, `context`, …).
- **Handler:** **`experience_card_service.create_card(db, current_user.id, body)`** in **`apps/api/src/services/experience_card.py`**.
- **Logic:** One **`ExperienceCard`** is created with **`status=ExperienceCard.DRAFT`**, no embedding, and **`db.add(card)`** then **flush/refresh**.
- **Commit:** Same request-scoped commit from **`get_db`**. No atomizer/parent/child/validator; single card only.

---

## Data Flow Diagram (Conceptual)

```text
[User types raw text]
        ↓
[Click "Update"] → POST /experience-cards/draft-v1 { raw_text }
        ↓
[API] RawExperience row INSERT → raw_experiences
        ↓
[API] Atomize → Parent extract → Child gen → Validate (per atom)
        ↓
[API] _persist_v1_family → ExperienceCard INSERT (DRAFT) → experience_cards
        ↓
[API] Response: draft_set_id, raw_experience_id, card_families
        ↓
[Frontend] Renders families; user clicks "Save Cards"
        ↓
[Frontend] For each card id: POST /experience-cards/{id}/approve
        ↓
[API] Load card by id + person_id → approve → status=APPROVED, embedding=...
        ↓
[API] UPDATE experience_cards (same row)
        ↓
[Frontend] invalidateQueries → GET /me/experience-cards → list saved cards
```

This is the full step-by-step flow of how experience cards are stored from start to finish.
