## CONXA: Human Search Layer for AI

**Tagline:** CONXA: Human Search Layer for AI. **Find accurate humans with prompts, not keywords.**

This repository contains the full CONXA stack:

- **Backend (`conxa-api`)**: FastAPI + Postgres + pgvector + LLM providers for:
  - Turning messy human narratives into **structured experience graphs** (experience cards + child evidence).
  - Running **trust-weighted, hybrid (vector + lexical) person search** over that graph.
  - Generating **why-matched explanations** grounded in stored evidence.
  - Managing **auth, credits, contact unlocks, and idempotent API behavior**.
- **Frontend (`conxa-web`)**: Next.js 16 app for:
  - The public / marketing surface.
  - The **builder** where humans describe experiences in free text/voice and turn them into structured cards.
  - The **search UI** where recruiters/teams search for humans using prompts, not filters.
  - Profile viewing, card browsing, unlocked contacts, credits, and onboarding.

This document gives a **code-accurate, end-to-end overview** of the whole codebase so that a new engineer
or AI agent can work autonomously inside CONXA without jumping between many separate docs.

For deeper implementation detail, this README references the following focused docs:

- `apps/api/docs/SEARCH_FLOW.md` – detailed search pipeline documentation.
- `apps/api/docs/EXPERIENCE_CARD_FLOW.md` – full experience card pipeline.
- `BUILDER_CHAT_TO_EMBEDDING.md` – builder chat to embedding flow notes.
- `WHY_MATCHED_QUICK_GUIDE.md` – short reference for why-matched behavior.
- `PRODUCTION_AUDIT.md` – production readiness and operational checklist.

---

## 1. Product Overview

### 1.1 Vision

Traditional people search (e.g. job platforms, social networks) is built around:

- **Keyword filters** (title, skills, location).
- **Rigid schemas** (job titles, companies, degrees).
- **Manual curation** of profiles.

CONXA instead builds a **human search layer for AI**:

- Users describe **experiences in free-form language or voice**.
- The system uses LLMs to construct a **structured graph of experience cards** from that messy input.
- Recruiters and collaborators express **intent in natural language prompts**, not in filter UIs.
- A **hybrid search engine** (embeddings + lexical + constraints) finds the best matching humans.
- Every result comes with **short, evidence-backed “why-matched” reasons**, not opaque scores.

### 1.2 Core Ideas

- **Prompts, not keywords**: Natural language queries drive search; filters are inferred and normalized.
- **Experience graph**: Work, projects, education, and other experiences are decomposed into:
  - **Parent experience cards** (jobs/roles/projects).
  - **Child evidence nodes** (skills, tools, metrics, outcomes, responsibilities, etc.).
- **Hybrid ranking**:
  - Semantic vector search over parent and child embeddings.
  - Lexical FTS search for robustness and recall.
  - Hard constraints from normalized filters (company, intent, domain, time, location, etc.).
- **Explainability from day one**:
  - `why_matched` explanations are generated **inline** with deterministic fallback.
  - Explanations are backed only by stored evidence; no hallucinated facts.
- **Trust & economics**:
  - **Credits** gate heavy operations (search and contact unlock).
  - **Idempotency** avoids double-charging on retries.

---

## 2. Repository Layout

Top-level layout (see `dir` output at repo root):

- `apps/`
  - `api/` – FastAPI backend (`conxa-api`).
  - `web/` – Next.js frontend (`conxa-web`).
- `.cursor/` – Editor/AI configuration for Cursor.
- `.dockerignore`, `.gitignore` – Build / VCS hygiene.
- `package.json`, `pnpm-lock.yaml` – Monorepo root config for the web app and tooling.
- `render.yaml` – Render.com deployment blueprint.
- `BUILDER_CHAT_TO_EMBEDDING.md` – Builder chat to embedding flow.
- `PRODUCTION_AUDIT.md` – Production-readiness checklist and notes.
- `WHY_MATCHED_QUICK_GUIDE.md` – Short reference for why-matched behavior.
- `README.md` – This file.

### 2.1 Backend (`apps/api`)

Key files and directories under `apps/api/src`:

- `main.py` – FastAPI app factory and router registration.
- `core/`
  - `config.py` – Environment-driven settings (`Settings` / `get_settings()`).
  - `auth.py` – JWT auth helpers.
  - `constants.py` – Global constants (embedding dimension; searches never expire).
  - `limiter.py` – Rate-limiting configuration (SlowAPI-based).
- `db/`
  - `session.py` – Async SQLAlchemy session factory.
  - `models.py` – Main DB models: people, profiles, experience cards, search artifacts, etc.
- `domain.py` – Domain-wide enums and literals (intent types, child relation types, etc).
- `providers/`
  - `chat.py` – LLM chat provider abstraction (cleanup, extract, why-matched).
  - `embedding.py` – Embedding provider abstraction.
  - `email.py`, `otp.py` – External integrations (SendGrid, Twilio OTP).
- `schemas/`
  - `auth.py`, `profile.py`, `search.py`, `builder.py`, `credits.py`, `contact.py`, `discover.py`, `bio.py` – Pydantic schemas for requests/responses.
  - `__init__.py` – Re-exports common schemas.
- `routers/`
  - `auth.py` – Login, signup, verify email, token refresh, etc.
  - `builder.py` – Experience builder endpoints.
  - `search.py` – Search + related person and history endpoints.
  - `profile.py` – Profile reading/updating endpoints.
  - `contact.py` – Contact and unlock related endpoints.
  - `__init__.py` – Assembles `ROUTERS` list for inclusion into `FastAPI`.
- `services/`
  - `auth.py` – Auth-related business logic.
  - `credits.py` – Credit accounting and idempotent operations.
  - `profile.py` – Profile queries and updates.
  - `experience/` – Pipeline (`pipeline.py`), clarify (`clarify.py`), search document (`search_document.py`), embedding (`embedding.py`), CRUD (`crud.py`), child value (`child_value.py`).
  - `search/` – Search orchestration and search-related business logic.
- `prompts/`
  - `experience_card.py`, `experience_card_enums.py` – Builder prompts.
  - `search_filters.py` – Search filter cleanup and extraction prompts.
  - `search_why_matched.py` – Why-matched explanation prompts.
- `serializers.py` – Adapters from SQLAlchemy models to schemas.
- `utils.py` – Shared helpers (embedding normalization, LLM JSON parsing, etc).
- `dependencies.py` – FastAPI dependency wiring.

### 2.2 Frontend (`apps/web`)

Key files and directories under `apps/web/src`:

- `app/`
  - `layout.tsx` – Root layout (providers, global UI).
  - `globals.css` – Tailwind and global styles.
  - `page.tsx` – Landing page + public hero.
  - `login/page.tsx` – Login screen.
  - `signup/page.tsx` – Signup screen.
  - `verify-email/page.tsx` – Email verification page.
  - `(authenticated)/layout.tsx` – Authenticated layout.
  - `(authenticated)/home/page.tsx` – Main home surface after onboarding.
  - `(authenticated)/builder/page.tsx` – Experience builder.
  - `(authenticated)/cards/page.tsx` – Card browsing.
  - `(authenticated)/searches/page.tsx` – Search history.
  - `(authenticated)/people/[id]/page.tsx` – Person profile view.
  - `(authenticated)/profile/page.tsx` – User’s own profile.
  - `(authenticated)/credits/page.tsx` – Credits management view.
  - `(authenticated)/unlocked/page.tsx` – Unlocked contacts.
  - `(authenticated)/explore/page.tsx` – Discover / explore people.
  - `(authenticated)/onboarding/bio/page.tsx` – Onboarding step for bio.
  - `(authenticated)/settings/page.tsx` – Settings surface.
- `components/`
  - `hero/` – Landing hero components (`search-hero`, `hero-3d-scene`, `hero-bg`, `index.ts`).
  - `search/` – Search form, results list, and `person-result-card.tsx`.
  - `builder/` – Builder chat, forms, card family display, voice input.
  - `profile/` – Profile and experience card views.
  - `auth/` – `AuthLayout` and related auth UI.
  - `feedback/` – Loading and error components.
  - `ui/` – Reusable UI primitives (button, input, card, textarea, label, etc.).
  - `app-nav.tsx`, `credits-badge.tsx`, `back-link.tsx`, `tilt-card.tsx`, etc.
- `contexts/`
  - `auth-context.tsx` – Auth state and helpers.
  - `search-context.tsx` – Search state and caching.
  - `sidebar-width-context.tsx` – Layout state.
- `hooks/`
  - `use-credits.ts`, `use-bio.ts`, `use-profile-v1.ts`, `use-experience-cards*.ts`, `use-profile-photo.ts`, etc.
  - `use-media-query.ts`, `use-visibility.ts`, `use-card-mutations.ts`, `use-card-forms.ts`.
- `lib/`
  - `api.ts` – REST client for the backend.
  - `auth-flow.ts` – Post-auth routing and onboarding logic.
  - `bio-schema.ts`, `schemas.ts` – Zod schemas for forms.
  - `constants.ts`, `utils.ts`, `india-cities.ts`, `voice-transcribe.ts`.
- `types/`
  - `index.ts` – Shared TS types including `PersonSearchResult` and others.

---

## 3. Backend: Tech Stack and Settings

### 3.1 Tech Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **ORM**: SQLAlchemy 2.x (async) + Alembic for migrations.
- **Database**: Postgres with `pgvector` extension for vector search.
- **HTTP server**: Uvicorn.
- **Rate limiting**: SlowAPI (see `core/limiter.py` and SlowAPI’s `RateLimitExceeded`).
- **LLM / Embedding providers**:
  - OpenAI-compatible chat APIs for query parsing, experience extraction, and why-matched.
  - OpenAI-compatible embedding APIs for experience and search embeddings.
- **Auth**:
  - JWT-based session tokens (`core/auth.py`).
  - Email verification (SendGrid) and OTP flows (Twilio).
- **Settings management**: `pydantic-settings`.

### 3.2 Settings (`core/config.py`)

Configuration is defined in `Settings` and loaded from `apps/api/.env`:

- **Database & auth**
  - `database_url` – Postgres DSN (default `postgresql://localhost/conxa`).
  - `jwt_secret`, `jwt_algorithm`, `jwt_expire_minutes`.
- **LLM chat**
  - `chat_api_base_url`, `chat_api_key`, `chat_model`.
- **Embeddings**
  - `embed_api_base_url`, `embed_api_key`, `embed_model`, `embed_dimension` (must match DB `EMBEDDING_DIM`).
  - `openai_api_key` – convenient single-key field if using OpenAI for both.
- **Rate limiting**
  - `search_rate_limit`, `unlock_rate_limit`.
  - `auth_login_rate_limit`, `auth_signup_rate_limit`, `auth_verify_rate_limit`.
- **OTP & email verification**
  - Twilio: `twilio_account_sid`, `twilio_auth_token`, `twilio_verify_service_sid`.
  - SendGrid: `sendgrid_api_key`, `sendgrid_from_email`, `sendgrid_from_name`.
  - `email_verify_url_base`, `email_verify_expire_minutes`, `email_verification_required`.
- **CORS**
  - `cors_origins` – comma-separated origins (`*` by default).
  - `cors_origins_list` – derived property used in FastAPI CORS middleware.
- **Profile photos**
  - `profile_photos_upload_dir` – directory path for profile photo uploads.

`get_settings()` is cached via `lru_cache` and used in `main.py` and other modules.

### 3.3 FastAPI App Setup (`main.py`)

- `app = FastAPI(title="CONXA API", description="Trust-weighted, AI-structured search for people by experience.", ...)`.
- Integrates rate limiting: `app.state.limiter = limiter` and a handler for `RateLimitExceeded`.
- Configures CORS with `get_settings().cors_origins_list`.
- Includes routers from `src.routers.ROUTERS`.
- Exposes a simple `/health` endpoint returning `{"status": "ok"}`.

---

## 4. Backend Data Model

The **data model** is defined primarily in `apps/api/src/db/models.py`. Key entities:

### 4.1 Person & Profile

- **Person**
  - Core identity row: `id`, `user_id` (owner), creation timestamps.
  - Linked to `PersonProfile`, `ExperienceCard`, `ExperienceCardChild`, and `SearchResult`.
- **PersonProfile**
  - Human-visible profile:
    - `first_name`, `last_name`, `profile_photo`, `profile_photo_url`, `profile_photo_media_type`
    - Bio: `school`, `college`, `current_company`, `past_companies`, `current_city`
    - `open_to_work`, `open_to_contact`
    - `work_preferred_locations` (array of strings)
    - `work_preferred_salary_min` (numeric, INR/year)
  - Tied into search filters via:
    - open-to-work constraint.
    - salary range checks.
    - preferred locations.

### 4.2 Experience Graph

The experience graph is built around **parent experience cards** and **child evidence** nodes.

- **RawExperience**
  - Stores raw messy text as entered by the user (normalized and original).
  - One raw experience can correspond to multiple parent experiences via detection.
- **DraftSet**
  - Grouping entity for a builder run.
  - Associates a set of card families (parent + children) with a single `RawExperience`.
  - Tracks run version and metadata.
- **ExperienceCard** (parent)
  - Represents a single coherent experience (job, project, education, etc.).
  - Fields include:
    - `title`, `normalized_role`, `domain`, `sub_domain`, `company_name`, `company_type`, `team`.
    - `start_date`, `end_date`, `is_current`.
    - `location` (city/country/free text).
    - `employment_type`, `seniority_level`, `intent_primary`, `intent_secondary`, `confidence_score`.
    - `summary`, `raw_text`.
  - Search:
    - `embedding` (pgvector, dimension = `EMBEDDING_DIM` / `embed_dimension`).
    - Search document text is **derived at embed/query time** via `build_parent_search_document(card)` in `search_document.py`; no stored column.
  - Visibility controls:
    - `experience_card_visibility` – controls whether a card is considered in search/discover.
- **ExperienceCardChild** (child evidence)
  - Child entries under a parent experience:
    - `parent_experience_id`, `person_id`, `raw_experience_id`, `draft_set_id`.
    - `child_type` – one of `ALLOWED_CHILD_TYPES`:
      - e.g. `skills`, `tools`, `metrics`, `achievements`, `responsibilities`, `collaborations`, `domain_knowledge`, `exposure`, `education`, `certifications`.
    - `value` (JSONB dimension container: `{ raw_text, items: [{ title, description }] }`).
    - `embedding`, `confidence_score`, `extra`.
  - Child label is derived from `value.headline` or `value.items[0].title`; search document from `get_child_search_document()`.
  - Children participate directly in search: embeddings and lexical FTS (derived from value at query time).

The typed models feeding the pipeline are defined in `services/experience/pipeline.py`:

- `Card`, `Family`, and related helpers (`TimeInfo`, `LocationInfo`, `RoleInfo`, etc.).
- These provide a stable schema between prompts, pipeline stages, and DB persistence.

### 4.3 Search Artifacts

- **Search**
  - Represents a single search session:
    - `id`, `searcher_id`, `query_text`, `parsed_constraints_json`, `filters`, `created_at`, `expires_at`.
    - `extra` includes `fallback_tier` (0–3) documenting how strict/soft filters were.
  - Links to `SearchResult` rows via `id`.
- **SearchResult**
  - Per-person row in a given search:
    - `search_id`, `person_id`, `rank`, `score`, timestamps.
    - `extra`:
      - `matched_parent_ids` – parent cards that contributed.
      - `matched_child_ids` – child cards that contributed.
      - `why_matched` – list of explanation strings.
- **IdempotencyKey**
  - Tracks request idempotency and cached responses:
    - `key`, `searcher_id`, `endpoint` (e.g. `"POST /search"`).
    - `response_body` (JSON) for replay.
- **UnlockContact**
  - Records contact unlock events:
    - `searcher_id`, `person_id`, `search_id` (optional).
    - Billing and idempotent unlock behavior is anchored here.

### 4.4 Credits and Accounting

Credits are modeled via `services/credits.py` and associated schemas:

- Balances are stored per user (see `schemas/credits.py` and `db/models.py`).
- Key operations:
  - `get_balance(db, user_id)`
  - `add_credits(db, user_id, amount)`
  - `deduct_credits(db, user_id, amount)`
  - `get_idempotent_response(...)` / `save_idempotent_response(...)`.
- Billing semantics for search:
  - Empty search (no results) → **0 credits**.
  - Non-empty search → **`num_cards` credits** (one per person shown).
  - Load-more → configured per-batch credits (typically 1 per additional slice).
  - Contact unlock → 1 credit per successful unlock (idempotent per person + search_id).

---

## 5. Experience Builder: From Messy Text to Embeddings

The experience builder flow is fully detailed in `apps/api/docs/EXPERIENCE_CARD_FLOW.md`. Here is the end-to-end overview.

### 5.1 High-Level Stages

1. **User input**:
   - Messy free-text description of experience (typed or via voice transcription).
2. **Rewrite** (`PROMPT_REWRITE`):
   - Clean, grammatical English.
   - No new facts; names and numbers preserved.
   - Cached by SHA-256 of input so repeated runs are cheap.
3. **Detect experiences** (`PROMPT_DETECT_EXPERIENCES`):
   - Count + labels for distinct experiences in the text.
   - Exactly one experience is marked `suggested` for extraction.
4. **Extract single experience** (`PROMPT_EXTRACT_SINGLE_CARDS`):
   - Selects one experience (by index) and produces:
     - A **parent experience card**.
     - Zero or more **child cards** (skills, tools, metrics, etc.).
   - Children inherit time/location/company context from parent as needed.
5. **Parse and validate**:
   - `parse_llm_response_to_families` turns LLM JSON into `V1Family` models.
   - `inject_metadata` adds IDs, run version, etc.
6. **Persist**:
   - `RawExperience` and `DraftSet` records are stored.
   - Families are turned into `ExperienceCard` + `ExperienceCardChild` rows.
7. **Embedding and indexing**:
   - `build_embedding_inputs` constructs `search_document` plus embedding text.
   - Embeddings are fetched and normalized, and stored into each card.

Clarify and edit flows operate above this pipeline to iteratively improve cards.

### 5.2 Clarify Flow

Clarify is handled in `services/experience/clarify.py` and related modules:

- Given:
  - Raw text.
  - A current partial card (parent or child).
  - Card family context and conversation history.
- The clarify flow:
  - Chooses a **target field** or child to clarify.
  - Asks a concrete **clarifying question**.
  - Suggests structured options when appropriate.
  - Produces a **patch** to the card or child.

The frontend uses `ClarifyExperienceRequest` and `ClarifyExperienceResponse`:

- `ClarifyExperienceRequest` includes:
  - `raw_text`, `card_type`, `current_card`, `card_family`, `card_families`.
  - Conversation state: `conversation_history`, `asked_history`, `last_question_target`.
  - Limits: `max_parent_questions`, `max_child_questions`.
- `ClarifyExperienceResponse` includes:
  - `clarifying_question`, `filled` (newly inferred fields).
  - `action`, `message`, `options`, `progress`, `missing_fields`.
  - Target metadata (`target_type`, `target_field`, `target_child_type`).

### 5.3 Edit and Patch Flow

Editing an existing card is supported via:

- `ExperienceCardPatch` (parent).
- `ExperienceCardChildPatch` (child).

The edit flow:

1. User edits fields directly in the UI **or** uses “fill from text”.
2. Backend applies patch to existing `ExperienceCard` / `ExperienceCardChild` via `apply_card_patch` / `apply_child_patch` (crud.py).
3. Search text is derived at embed time via `build_parent_search_document` / `get_child_search_document`.
4. Embeddings are recomputed for affected cards only via `embed_experience_cards`.

This design keeps:

- **Search state** always in sync with the latest structured representation (text derived from card fields).
- **Explainability** aligned with visible text, since both are derived from the same cards.

---

## 6. Search: Prompts to People

The search pipeline is described in deep detail in `apps/api/docs/SEARCH_FLOW.md`. Below is the conceptual overview tied to key code units.

### 6.1 High-Level Flow

File: `services/search/search_logic.py`, function: `run_search(db, searcher_id, body, idempotency_key)`.

1. **Idempotency check**:
   - If an `Idempotency-Key` header is present:
     - Look up an existing `IdempotencyKey` row (endpoint `"POST /search"`).
     - If a completed `response_body` exists, **return it immediately**.
2. **Parse filters from prompt**:
   - `parse_search_filters` in `providers/chat.py`:
     - Cleanup prompt (`PROMPT_SEARCH_CLEANUP`).
     - Single extract (`PROMPT_SEARCH_SINGLE_EXTRACT`).
   - Result mapped into `ParsedConstraintsPayload`, then normalized via `filter_validator.validate_and_normalize`.
3. **Resolve `num_cards` and credits pre-check**:
   - Priority:
     1. `body.num_cards` in request.
     2. Parsed `payload.num_cards`.
     3. `_extract_num_cards_from_query(body.query)` (regex).
     4. `DEFAULT_NUM_CARDS`.
   - Clamp to `[1, TOP_PEOPLE_STORED]`.
   - Ensure `get_balance(searcher_id) >= num_cards`, else HTTP 402 (insufficient credits).
4. **Build semantic and lexical queries**:
   - **Embedding text**:
     - `payload.query_embedding_text` → `payload.query_original` → `body.query`.
   - **Lexical TS query**:
     - Use `search_phrases` and key keywords; fallback to cleaned/raw query truncated to 200 chars.
5. **Parallel embedding and lexical**:
   - `_embed_query_vector` to get a dense vector.
   - `_lexical_candidates` to get lexical scores from FTS over `search_document`.
   - On lexical error, continue without lexical bonuses.
6. **Early empty-vector short-circuit**:
   - If no embedding is produced (e.g. empty/invalid text):
     - Create an **empty Search response** (0 credits, no people).
7. **Constraint terms and fallback tiers**:
   - Compute `_SearchConstraintTerms` from MUST/EXCLUDE:
     - Time range, location flags, company_norms, team_norms.
   - Use a **tiered fallback strategy**:
     - Tier 0: All relevant constraints enforced.
     - Tier 1: Time softened.
     - Tier 2: Time + location softened.
     - Tier 3: Company/team softened (broadest match).
   - Query success condition: at least `MIN_RESULTS` distinct people or hitting max tier.
8. **Candidate retrieval**:
   - For each tier:
     - Fetch:
       - Parent candidates (`ExperienceCard`) via vector distance + filters.
       - Child min distance by person (`ExperienceCardChild`).
       - Child evidence rows used for explanations.
9. **Collapse and rank persons**:
   - Combine parent/child similarity, lexical scores, and should-boosts into a single `score`.
   - Keep top `TOP_PEOPLE_STORED` results in `ranked_people_full`.
   - If empty → create empty response (0 credits).
10. **Load person and profile data**:
    - `_load_people_profiles_and_children` loads:
      - `Person`, `PersonProfile`, visible `ExperienceCard`s, and relevant children.
11. **Post-rank tiebreakers**:
    - Adjust ordering based on:
      - Salary constraints (prefer people with stated salary when relevant).
      - Time overlap (prefer experiences overlapping requested time range).
12. **Persist search & deduct credits**:
    - Insert `Search` record with parsed filters and fallback tier.
    - Deduct `num_cards` credits using `deduct_credits`, raising if insufficient.
13. **Prepare pending results and why-matched evidence**:
    - `_prepare_pending_search_rows`:
      - Builds `pending_search_rows` for top `num_cards` people.
      - Prepares LLN evidence (parent + child cards) for each person.
14. **Inline why-matched generation**:
    - `_generate_llm_why_matched`:
      - Builds a JSON payload using `why_matched_helpers.build_match_explanation_payload`.
      - Uses `get_why_matched_prompt` with strict JSON output requirements.
      - Validates and cleans reasons via `validate_why_matched_output` and `clean_why_reason`.
    - Fallback:
      - If inline LLM fails or returns empty for a person:
        - Use `fallback_build_why_matched` to create deterministic, grounded reasons.
15. **Persist SearchResult rows**:
    - `_persist_search_results`:
      - Writes `SearchResult` rows with:
        - `rank`, `score`, `matched_parent_ids`, `matched_child_ids`, and `why_matched`.
16. **Async why-matched backfill (best-effort)**:
    - If inline LLM could not run:
      - Schedule `_update_why_matched_async` as a background task.
      - It will recompute reasons later and patch `SearchResult.extra.why_matched`.
17. **Build response payload**:
    - `_build_search_people_list`:
      - Materializes `PersonSearchResult` items including:
        - Person basics, `similarity_percent`, `why_matched`, `open_to_work`, `work_preferred_locations`, `work_preferred_salary_min`.
        - `matched_cards` – top matched parent cards.
    - `SearchResponse` is returned and, if idempotency key is set, saved for future replays.

### 6.2 Search-Related Endpoints

Implemented in `routers/search.py` + `services/search/*`:

- `POST /search`
  - Accepts `SearchRequest` (query, open_to_work_only, preferred_locations, salary range, num_cards).
  - Returns `SearchResponse` (`search_id`, `people`, `num_cards`).
  - Auth required; rate limited by `search_rate_limit`.
  - Optional `Idempotency-Key` header.
- `GET /search/{search_id}/more`
  - Returns additional slices of `PersonSearchResult` for an existing search.
  - Uses stored `SearchResult` rows; may deduct credits unless `history=true`.
- `GET /people`
  - Discover list of people with at least one visible parent card.
- `GET /people/{person_id}`
  - Person profile; optional `search_id` ties it to a search session.
  - Validates that the person appears in the search results (when `search_id` supplied).
- `GET /people/{person_id}/profile`
  - Public-style profile (still auth-protected at router level).
- `POST /people/{person_id}/unlock-contact`
  - Unlocks contact details for a person.
  - Can be bound to a `search_id`; idempotent per endpoint.
- `GET /me/searches`
  - Lists saved searches and history with result counts.
- `DELETE /me/searches/{search_id}`
  - Deletes a saved search.
- `GET /me/unlocked-cards`
  - Lists people whose contact has been unlocked by current user.

### 6.3 Session Validation and Expiry

`_validate_search_session` and `_search_expired` enforce:

- **Ownership**:
  - Search must belong to the current user.
  - If validating `person_id`, that person must appear in search results.
- **Expiry**:
  - New searches use `SEARCH_NEVER_EXPIRES` (far-future date); they do not expire until the user deletes them.
  - `Search.expires_at` is checked; expired searches produce HTTP 403 for dependent operations.

---

## 7. Explainability: Why-Matched Reasons

Explanations are generated in `search_logic.py` and helpers in `services/search/why_matched_helpers.py`,
with prompt definitions in `prompts/search_why_matched.py`. Quick behavior overview:

- **Grounded evidence**:
  - Only uses parent and child card evidence already stored in the DB.
  - No external knowledge; no hallucinated credentials or companies.
- **Structured JSON contract**:
  - LLM must output:
    - `{"people": [{"person_id": "...", "why_matched": ["...", "..."]}, ...]}`
  - `validate_why_matched_output` enforces:
    - 1–3 reasons per person.
    - Each reason <= 120 chars and <= configured word limit.
    - No prefixes like `"headline:"` or `"skills:"`.
    - Deduplication of conceptually similar reasons.
- **Fallback behavior**:
  - If LLM fails to respond, or responds with invalid JSON:
    - `fallback_build_why_matched` compresses search evidence deterministically.
    - For extremely weak evidence, uses:
      - `"Matched your search intent and profile signals."`
  - The frontend (`person-result-card.tsx`) further ensures:
    - If `why_matched` is missing or empty, it shows the same generic fallback.

On the frontend, `PersonResultCard` renders:

- Match percent as `similarity_percent` (rounded and clamped to 0–100; `N/A` if missing).
- A short bulleted list of `why_matched` reasons (up to 3).
- A consistent default explanation when reasons are absent.

---

## 8. Frontend: CONXA Web App

### 8.1 Tech Stack and Build

From `apps/web/package.json`:

- **Framework**: Next.js 16 (`"next": "^16.1.6"`).
- **Language**: TypeScript.
- **UI**:
  - Tailwind CSS, `class-variance-authority`, `tailwind-merge`.
  - `lucide-react` for icons.
  - Framer Motion for animation.
- **State & data fetching**:
  - React Query (`@tanstack/react-query`).
  - Custom React contexts (`auth-context`, `search-context`).
- **Forms & validation**:
  - `react-hook-form`, `zod`, `@hookform/resolvers`.

Scripts:

- `pnpm dev` → `next dev`
- `pnpm build` → `next build`
- `pnpm start` → `next start`
- `pnpm lint` → `next lint`

### 8.2 Auth UX

`apps/web/src/app/login/page.tsx` implements the login experience:

- Uses `AuthLayout` with title set to **“CONXA”** and subtitle:
  - `"The Human Search Layer for AI. Search for people using prompts not keywords."`
- Handles:
  - Form validation (email + password via Zod).
  - Error state and “email not verified” guidance.
  - Routing to post-auth path via `getPostAuthPath(onboardingStep)`.
- Uses `useAuth` context to:
  - Call `login(email, password)`.
  - React to `isAuthenticated`, `isAuthLoading`, and `onboardingStep`.

The signup and verify-email flows follow similar patterns, with UI built from `ui` components and `feedback` components.

### 8.3 Search UX

Key components:

- `search/search-form.tsx`:
  - Provides a prompt-centric search input.
  - Can expose advanced toggles (e.g., open-to-work-only) while optimizing for natural language prompts.
- `search/search-results.tsx`:
  - Renders lists of `PersonResultCard` entries.
  - Handles loading, error states, pagination (load-more).
- `search/person-result-card.tsx`:
  - Receives `person: PersonSearchResult` and `searchId`.
  - Shows:
    - Initial avatar letter from `person.name`.
    - Name and headline, plus “Open to contact” badge when relevant.
    - “Match Percent” computed from `similarity_percent`.
    - “Why this person” list from `why_matched` (or fallback).
  - Wraps card in a `Link` to `/people/{person.id}?search_id={searchId}`.

From a user’s perspective:

- Entering a **prompt** (e.g. “backend engineer in Bangalore who led 0→1 launches in fintech”) is enough.
- Results show **people**, not documents, with **clear, concise reasons** for each match.

### 8.4 Builder UX

Key components:

- `builder/chat/builder-chat.tsx` and `builder/chat/experience-clarify-chat.tsx`:
  - Provide conversational interfaces for describing experiences and answering clarify questions.
- `builder/voice/messy-text-voice-input.tsx`:
  - Connects voice transcription (via `voice-transcribe.ts` and backend speech endpoints) to the builder.
- `builder/card/*` (e.g. `card-details.tsx`, `card-family-display.tsx`) + `builder/family/*`:
  - Render card families (parent + children).
  - Expose editing controls, patch forms, and save actions.

The builder is tightly coupled to the backend experience pipeline:

- It sends `DraftSingleRequest`, `ClarifyExperienceRequest`, `FillFromTextRequest`, and patch requests.
- It consumes `DraftSetV1Response`, `ClarifyExperienceResponse`, and card responses.

### 8.5 Authenticated Areas

Using the `(authenticated)` app group, the frontend provides:

- **Home**:
  - Overview of credits, quick links to builder and search.
- **Builder**:
  - Primary interaction surface for creating/updating experience cards.
- **Cards**:
  - List and manage all cards and card families.
- **Searches**:
  - Browse past searches; reopen or load more.
- **People**:
  - Full profile view for an individual (`expandable-experience-card` and profile sections).
- **Profile**:
  - Manage own profile and visibility (`visibility-section`, onboarding flows).
- **Credits**:
  - Show current credit balance; link to top-up paths or admin flows.
- **Unlocked**:
  - List of unlocked contacts and their profiles.
- **Explore**:
  - Browse discovered people without a specific search query.

---

## 9. Auth, Identity, and Credits

### 9.1 Auth Flow (Backend)

In `routers/auth.py` and `services/auth.py`:

- Signup:
  - Creates user and associated `Person` / `PersonProfile`.
  - Optionally triggers email verification if `email_verification_required`.
- Login:
  - Validates credentials (bcrypt).
  - Checks email verification if enabled.
  - Issues JWT with configured expiration.
- Verify email:
  - Uses SendGrid and token-based verification.
- OTP:
  - Twilio Verify is used for OTP-based flows where enabled.

### 9.2 Auth Flow (Frontend)

In `contexts/auth-context.tsx`:

- Keeps:
  - `isAuthenticated`, `isAuthLoading`, `onboardingStep`, `user`.
- Exposes:
  - `login`, `logout`, `signup`, `refreshToken`, etc.
- Integrated with:
  - `useRouter` and `auth-flow.ts` for routing after auth.

### 9.3 Credits and Billing

Frontend:

- `use-credits.ts`:
  - Fetches and caches credit balances.
  - Used by `credits-badge.tsx` and credits pages.

Backend:

- `services/credits.py`:
  - Implements credit modifications and idempotence.
  - Tied into:
    - Search pipeline (pre-check and deduction).
    - Unlock contact logic.

Credits are meant to:

- Bound the computational cost of:
  - Search (vector + lexical + LLM explainability).
  - Contact unlocks (safeguarding contact details).
- Provide a simple, extensible billing primitive for future plans.

---

## 10. External Providers and Integrations

### 10.1 Chat and Embeddings

File: `providers/chat.py`, `providers/embedding.py`.

- **Chat**:
  - Wrapper over an OpenAI-compatible API (JSON mode when available).
  - Exposes:
    - Cleanup, single-extract, why-matched calls.
  - Raises `ChatServiceError` with context when the provider fails.
- **Embeddings**:
  - Wrapper for text embeddings.
  - Returns lists of floats which are:
    - Normalized via `normalize_embedding`.
    - Stored in `ExperienceCard.embedding` and `ExperienceCardChild.embedding`.

### 10.2 Email and OTP

- `providers/email.py`:
  - SendGrid integration for:
    - Email verification links.
    - Future notifications.
- `providers/otp.py`:
  - Twilio Verify integration for:
    - OTP sending and validation.
  - Configured via `otp_*` settings and Twilio credentials.

---

## 11. APIs, Schemas, and Contracts

Schemas in `apps/api/src/schemas` define the contracts between frontend and backend.
Key schema groups:

- `auth.py` – Auth and email verification.
- `builder.py` – Experience builder, clarify, fill-from-text, and card responses.
- `search.py` – Search requests/responses and person search result.
- `profile.py` – Profile update and read models.
- `contact.py` – Contact details and unlock responses.
- `credits.py` – Credit balances and transactions.
- `discover.py` – Explore/discover responses.
- `bio.py` – Bio editing and onboarding.

The codebase strives to:

- Keep schemas explicitly documented (see `SEARCH_FLOW.md` §17).
- Ensure that **prompts and schemas are aligned**—prompts instruct LLMs to produce JSON matching schema fields.

---

## 12. Running CONXA Locally

### 12.1 Prerequisites

- Python 3.11+
- Node.js (for Next.js 16; check `package.json` engine if configured).
- Postgres with `pgvector` extension.
- `pnpm` for Javascript dependencies (or `npm`/`yarn` if adapted).

### 12.2 Backend Setup (`apps/api`)

From repo root:

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -U pip
pip install -e .
```

Or, if no editable install is set up, install using `pyproject.toml` dependencies:

```bash
pip install fastapi uvicorn[standard] sqlalchemy alembic asyncpg psycopg2-binary pgvector \
  python-jose[cryptography] bcrypt "pydantic[email]" pydantic-settings httpx websockets openai \
  slowapi json-repair python-multipart
```

Configure `apps/api/.env` using `core/config.py` as a reference:

- Set at least:
  - `database_url`
  - `jwt_secret`
  - `chat_api_key`, `embed_api_key` (or `openai_api_key`)

Run migrations (assuming Alembic is configured under `apps/api`):

```bash
alembic upgrade head
```

Run the API:

```bash
uvicorn src.main:app --reload
```

### 12.3 Frontend Setup (`apps/web`)

From repo root:

```bash
cd apps/web
pnpm install   # or npm install / yarn
pnpm dev       # Next.js dev server
```

Configure environment variables (e.g., `.env.local`) for:

- Backend API base URL.
- Public keys or config (if any) used by `lib/api.ts` or `auth-context`.

The app will usually run at `http://localhost:3000` by default.

---

## 13. Deployment and Render Blueprint

The repo includes `render.yaml` for deploying CONXA to Render:

- Typically defines:
  - Web service for FastAPI backend.
  - Web service for Next.js frontend (or static export).
  - Postgres database instance with `pgvector`.
- Check `render.yaml` for:
  - Environment variables needed in production.
  - Health checks and scaling configuration.
  - Build and start commands for both services.

Deployment notes and production considerations are summarized in `PRODUCTION_AUDIT.md`:

- Secrets and key rotation (JWT, provider API keys).
- Rate limiting thresholds.
- CORS configuration.
- Observability (logging, metrics, tracing where configured).

---

## 14. Design Principles and Invariants

### 14.1 Prompt-First, Schema-Backed

- All LLM calls are designed around **explicit schemas**.
- Prompts in `prompts/*` include **strict JSON schema** definitions and rules:
  - No extra commentary.
  - No missing keys—always include every field with `null`/`[]` as needed.
- Backend code:
  - Treats LLM output as **untrusted**.
  - Normalizes, validates, and repairs JSON when possible (`json-repair`).

### 14.2 Grounded Explainability

- No explanation or display text should:
  - Invent facts not present in DB.
  - Leak sensitive contact info.
- All `why_matched` content is derived from:
  - `ExperienceCard` + `ExperienceCardChild` fields.
  - Search constraints (intent, domain, time, location, etc.).

### 14.3 Credits and Idempotency

- Search and contact unlock flows must:
  - Charge credits exactly once per **logical user action**, even on retries.
  - Use `IdempotencyKey` records and endpoint strings (`"POST /search"`, unlock endpoints) consistently.
- Any new credit-using endpoint should:
  - Integrate with `services/credits.py`.
  - Consider idempotency for network retries and client errors.

### 14.4 Backward-Compatible Experience Graph

- `domain.py` defines:
  - `Intent`
  - `ChildIntent`
  - `ChildRelationType`
  - `ALLOWED_CHILD_TYPES`
  - `ENTITY_TAXONOMY`
- Changes to these enums require:
  - Updating prompts in `experience_card_enums.py` and `experience_card.py`.
  - Considering DB migrations and existing data.

---

## 15. Extending CONXA

### 15.1 Adding New Experience Types or Child Evidence

To add a new child type (e.g., `publications`):

1. Update `ALLOWED_CHILD_TYPES` in `domain.py`.
2. Reflect the new type in:
   - `experience_card_enums.py` prompt helpers.
   - Experience extraction prompts in `experience_card.py`.
3. Update:
   - `ExperienceCardChild` semantics (if special handling is needed).
   - Builder UI to render/edit the new child type.
4. Consider:
   - Search implications (do we want to index/control this dimension?).
   - why-matched evidence mapping.

### 15.2 New Search Constraints

To add new structured constraints (e.g., remote-only, time zone, specific metrics):

1. Extend `ParsedConstraintsPayload` and related Pydantic models in `schemas/search.py`.
2. Update:
   - `PROMPT_SEARCH_SINGLE_EXTRACT` in `search_filters.py` to expose new fields.
   - `filter_validator.py` to normalize and cap new fields.
3. Extend search logic:
   - `filter_context` and `_apply_card_filters` for new constraints.
   - Ranking logic if the constraint should affect scores.
4. Update frontend search UI and `SearchRequest` typing where appropriate.

### 15.3 Customizing Explainability

To adjust explainability style:

1. Modify `get_why_matched_prompt` in `search_why_matched.py`:
   - Change style or priority rules (e.g., emphasize achievements more).
2. Update `WHY_MATCHED_QUICK_GUIDE.md` to reflect any new guidelines.
3. Ensure `validate_why_matched_output` remains aligned with the prompt contract.

---

## 16. Troubleshooting and Debugging

### 16.1 Common Failure Modes

- **Search returns no results**:
  - Check `fallback_tier` in `Search.extra`.
  - Confirm that embeddings exist for experience cards.
  - Verify that filters (company, location, time) are not over-constraining.
- **Explainability failures**:
  - Look for `ChatServiceError` logs around why-matched.
  - Verify prompt length and payload size.
  - Fallback reasons should still be present even when LLM fails.
- **Credit issues**:
  - Ensure `get_balance` returns expected value.
  - Check `IdempotencyKey` table for repeated keys.
- **Auth issues**:
  - Confirm JWT secret/algorithm match frontend verification.
  - Check email verification config and rate limits.

### 16.2 Observability Hooks

- Backend:
  - Logging via `logging.getLogger(__name__)` in core services.
  - Structured error messages for Chat/Embedding providers.
  - HTTP exceptions with clear `detail` strings for clients.
- Frontend:
  - `ErrorMessage`, `PageError`, `PageLoading`, `LoadingScreen` components.
  - Error boundaries around data-fetching components.

---

## 17. Summary

CONXA implements a **human search layer for AI**:

- Humans describe their experiences in natural language; the system builds a structured, searchable graph of experience cards.
- Searchers use **prompts, not keyword filters**, to find the right humans.
- A hybrid search pipeline, backed by vector + lexical search and strict constraints, returns **ranked people with clear, grounded explanations**.
- Credits, idempotency, and production-oriented patterns make the system **robust and ready to scale**.

Use this README, along with the deeper docs in `apps/api/docs` and root Markdown files, as your **primary map** when extending or operating CONXA.

