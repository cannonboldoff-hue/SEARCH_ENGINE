# Search Engine — Backend (API)

Step-by-step documentation of the FastAPI backend: every module and function, in order of use.

---

## Table of Contents

1. [Overview](#overview)
2. [Application entry](#application-entry-mainpy)
3. [Configuration](#configuration-configpy)
4. [Constants](#constants-constantspy)
5. [Database](#database)
6. [Auth (passwords & JWT)](#auth-authpy)
7. [Dependencies](#dependencies-dependenciespy)
8. [Credits & idempotency](#credits-creditspy)
9. [Schemas (request/response models)](#schemas-schemaspy)
10. [Serializers](#serializers-serializerspy)
11. [Utils](#utils-utilspy)
12. [Rate limiter](#rate-limiter-limiterpy)
13. [Providers (chat & embedding)](#providers)
14. [Services (business logic)](#services)
15. [Routers (HTTP endpoints)](#routers)
16. [Migrations (Alembic)](#migrations-alembic)

---

## Overview

The backend is a **FastAPI** app that provides:

- **Auth**: signup/login with JWT; password hashing with bcrypt.
- **Profile (“me”)**: person, visibility settings, bio, credits, contact details.
- **Builder**: raw experiences → LLM draft cards → experience cards (with pgvector embeddings).
- **Search**: semantic search over approved experience cards; view profile; unlock contact (credits).

Tech: **PostgreSQL** (async via asyncpg), **pgvector** for embeddings, **Alembic** for migrations, **SlowAPI** for rate limiting.

---

## Application entry (`main.py`)

| Step | What happens |
|------|----------------|
| 1 | **`lifespan(_app)`** — Async context manager for app startup/shutdown. Currently only `yield`s (no startup logic). |
| 2 | **`FastAPI(...)`** — App created with title, description, version, lifespan. |
| 3 | **`app.state.limiter = limiter`** — Attach SlowAPI limiter for rate-limited routes. |
| 4 | **`app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)`** — Return 429 when rate limit exceeded. |
| 5 | **CORS** — `get_settings().cors_origins` is split by comma; if empty, `["*"]`. Middleware allows credentials, all methods/headers. **Production:** set `CORS_ORIGINS` to your web app URL(s), e.g. `https://search-engine-web-3aqy.onrender.com` — browsers reject `*` when credentials are used. |
| 6 | **Routers** — `auth_router`, `me_router`, `contact_router`, `builder_router`, `search_router` are included. |
| 7 | **`GET /health`** — Returns `{"status": "ok"}` (no auth). |

---

## Configuration (`config.py`)

| Function / item | Purpose |
|-----------------|--------|
| **`Settings`** (Pydantic `BaseSettings`) | Loads from env / `.env`. Fields: `database_url`, `jwt_secret`, `jwt_algorithm`, `jwt_expire_minutes`, `chat_api_base_url`, `chat_api_key`, `chat_model`, `embed_api_base_url`, `embed_api_key`, `embed_model`, `openai_api_key`, `search_rate_limit`, `unlock_rate_limit`, `cors_origins`. `extra = "ignore"` so unknown env vars don’t error. |
| **`get_settings()`** | Returns cached `Settings()` (via `@lru_cache`). Single instance for the process. |

---

## Constants (`constants.py`)

| Constant | Meaning |
|----------|--------|
| **`EMBEDDING_DIM`** | `384` — Vector size for DB and for `normalize_embedding`. |
| **`SEARCH_RESULT_EXPIRY_HOURS`** | `24` — Search results (and profile view / unlock) are valid for this many hours. |

---

## Database

### Session (`db/session.py`)

| Step | What happens |
|------|----------------|
| 1 | **URL** — `get_settings().database_url`; if it doesn’t contain `asyncpg`, `postgres://` or `postgresql://` is replaced with `postgresql+asyncpg://`. |
| 2 | **Engine** — `create_async_engine(database_url, poolclass=NullPool if "render.com" in url else None, echo=SQL_ECHO)`. |
| 3 | **Session factory** — `async_sessionmaker(engine, AsyncSession, expire_on_commit=False, autoflush=False)`. |
| 4 | **`Base`** — SQLAlchemy `declarative_base()` for models. |

### Models (`db/models.py`)

| Helper / model | Purpose |
|----------------|--------|
| **`uuid4_str()`** | Returns `str(uuid.uuid4())` for primary keys. |
| **`Person`** | `people`: id, email, hashed_password, display_name, created_at, updated_at. Relations: visibility_settings, contact_details, credit_wallet, bio, raw_experiences, experience_cards, searches_made. |
| **`Bio`** | `bios`: person_id (FK CASCADE), first_name, last_name, date_of_birth, current_city, profile_photo_url, school, college, current_company, past_companies (JSON). |
| **`VisibilitySettings`** | `visibility_settings`: person_id (FK CASCADE), open_to_work, work_preferred_locations (ARRAY), work_preferred_salary_min/max, open_to_contact, contact_preferred_salary_min/max. |
| **`ContactDetails`** | `contact_details`: person_id (FK CASCADE), email_visible, phone, linkedin_url, other. |
| **`CreditWallet`** | `credit_wallets`: person_id (FK CASCADE), balance (default 1000). |
| **`CreditLedger`** | `credit_ledger`: person_id, amount (+/-), reason, reference_type, reference_id, balance_after, created_at. |
| **`IdempotencyKey`** | `idempotency_keys`: key, person_id, endpoint, response_status, response_body (JSON). Unique on (key, person_id, endpoint). |
| **`RawExperience`** | `raw_experiences`: person_id (FK CASCADE), raw_text. |
| **`ExperienceCard`** | `experience_cards`: person_id, raw_experience_id (FK SET NULL), status (DRAFT/APPROVED/HIDDEN), human_edited, locked, title, context, constraints, decisions, outcome, tags (ARRAY), company, team, role_title, time_range, **embedding** (Vector(384)), created_at, updated_at. |
| **`Search`** | `searches`: searcher_id (FK), query_text, filters (JSON), created_at. |
| **`SearchResult`** | `search_results`: search_id, person_id, rank, score. Unique (search_id, person_id). |
| **`UnlockContact`** | `unlock_contacts`: searcher_id, target_person_id, search_id. Unique (searcher_id, target_person_id, search_id). |

---

## Auth (`auth.py`)

Password hashing and JWT creation/validation (no DB here).

| Function | Step-by-step |
|----------|--------------|
| **`verify_password(plain, hashed)`** | Encode `plain` to UTF-8, truncate to 72 bytes (bcrypt limit), call `bcrypt.checkpw` against `hashed`. Return True/False; on any exception return False. |
| **`hash_password(password)`** | Encode password, truncate to 72 bytes, `bcrypt.hashpw(..., bcrypt.gensalt())`, decode to str and return. |
| **`create_access_token(subject)`** | Build payload `{"sub": subject, "exp": now + jwt_expire_minutes}`; encode with `jwt_secret` and `jwt_algorithm`; return token string. |
| **`decode_access_token(token)`** | Decode JWT with same secret/algorithm; return `payload["sub"]` as str or `None` on error/expiry. |

---

## Dependencies (`dependencies.py`)

| Dependency | Step-by-step |
|------------|----------------|
| **`get_db()`** | Async generator: yield an `AsyncSession` from `async_session()`. On success `await session.commit()`; on exception `await session.rollback()` then re-raise. |
| **`get_current_user(credentials, db)`** | 1) If no Bearer credentials → 401 "Not authenticated". 2) Decode token with `decode_access_token(credentials.credentials)`; if no subject → 401 "Invalid or expired token". 3) Load `Person` by id; if missing → 401 "User not found". 4) Return `Person`. |

`security = HTTPBearer(auto_error=False)` so missing header doesn’t auto-raise.

---

## Credits (`credits.py`)

Credit balance, deductions, and idempotency storage.

| Function | Step-by-step |
|----------|--------------|
| **`get_balance(db, person_id)`** | Select `CreditWallet` for person_id; return `wallet.balance` or 0 if no row. |
| **`deduct_credits(db, person_id, amount, reason, reference_type, reference_id)`** | 1) Select wallet with `with_for_update()`. 2) If no wallet or balance < amount → return False. 3) Decrement `wallet.balance`; create `CreditLedger` row (amount negative, reason, reference_*, balance_after). 4) Add wallet and ledger, flush; return True. |
| **`get_idempotent_response(db, key, person_id, endpoint)`** | Select one `IdempotencyKey` where (key, person_id, endpoint) match; return row or None. |
| **`save_idempotent_response(db, key, person_id, endpoint, response_status, response_body)`** | Create `IdempotencyKey` with given fields; add and flush. |

---

## Schemas (`schemas.py`)

Pydantic models for request/response. Summary:

- **Auth**: `SignupRequest`, `LoginRequest`, `TokenResponse`.
- **Me**: `PersonResponse`, `PatchMeRequest`, `VisibilitySettingsResponse`, `PatchVisibilityRequest`, `BioResponse`, `BioCreateUpdate`, `PastCompanyItem`.
- **Contact**: `ContactDetailsResponse`, `PatchContactRequest`.
- **Credits**: `CreditsResponse`, `LedgerEntryResponse`.
- **Builder**: `RawExperienceCreate`, `RawExperienceResponse`, `ExperienceCardCreate`, `ExperienceCardPatch`, `ExperienceCardResponse`, `DraftSetV1Response`, `CardFamilyV1Response`.
- **Search**: `SearchRequest`, `PersonSearchResult`, `SearchResponse`, `PersonProfileResponse`, `UnlockContactResponse`.

All used by routers and services for validation and serialization.

---

## Serializers (`serializers.py`)

| Function | Purpose |
|----------|--------|
| **`experience_card_to_response(card)`** | Maps `ExperienceCard` ORM instance to `ExperienceCardResponse`: id, person_id, raw_experience_id, status, human_edited, locked, title, context, constraints, decisions, outcome, tags, company, team, role_title, time_range, created_at, updated_at. Uses `getattr(card, "human_edited", False)` etc. for optional attributes. |

---

## Utils (`utils.py`)

| Function | Step-by-step |
|----------|--------------|
| **`normalize_embedding(vec, dim=EMBEDDING_DIM)`** | If `len(vec) < dim`: return `vec[:dim]` zero-padded to length `dim`. Else return `vec[:dim]`. Used so vectors match DB `Vector(384)`. |

---

## Rate limiter (`limiter.py`)

| Item | Purpose |
|------|--------|
| **`limiter`** | `Limiter(key_func=get_remote_address)` from SlowAPI. Used as decorator on search and unlock-contact routes; limits come from config (`search_rate_limit`, `unlock_rate_limit`). |

---

## Providers

### Chat (`providers/chat.py`)

| Class / function | Step-by-step |
|------------------|--------------|
| **`ChatServiceError`** | Exception for LLM/API errors or invalid output. |
| **`ParsedQuery`** | Pydantic: company, team, open_to_work_only, semantic_text. |
| **`ChatProvider`** (abstract) | `parse_search_query(query)`, `chat(user_message, max_tokens)`. |
| **`OpenAICompatibleChatProvider`** | 1) **`__init__(base_url, api_key, model)`**: normalize base_url to end with `/v1`. 2) **`_chat(messages, max_tokens)`**: POST to `{base_url}/chat/completions` with model, messages, max_tokens, temperature=0.2; return `data["choices"][0]["message"]["content"].strip()`; on HTTP/request/KeyError raise `ChatServiceError`. 3) **`parse_search_query(query)`**: Build prompt asking for JSON with company, team, open_to_work_only, semantic_text; call `_chat`, strip markdown code block if present, parse JSON; return `ParsedQuery(...)`. |
| **`OpenAIChatProvider`** | Subclass using `openai_api_key` and `chat_model` from settings; base_url `https://api.openai.com/v1`. |
| **`get_chat_provider()`** | If `openai_api_key` set and no `chat_api_base_url` → `OpenAIChatProvider()`. Else if `chat_api_base_url` → `OpenAICompatibleChatProvider(...)`. Else raise RuntimeError. |

### Embedding (`providers/embedding.py`)

| Class / function | Step-by-step |
|------------------|--------------|
| **`EmbeddingServiceError`** | Exception for embedding API errors. |
| **`EmbeddingProvider`** (abstract) | `dimension` property; `embed(texts: list[str]) -> list[list[float]]`. |
| **`OpenAICompatibleEmbeddingProvider`** | 1) **`__init__(base_url, api_key, model, dimension=384)`**: normalize base_url to `/v1`. 2) **`embed(texts)`**: POST to `{base_url}/embeddings` with model and input=texts; return list of embeddings ordered by index; on error raise `EmbeddingServiceError`. |
| **`get_embedding_provider()`** | If `embed_api_base_url` set → return `OpenAICompatibleEmbeddingProvider(..., dimension=384)`. Else raise RuntimeError. |

### Experience Card v1 prompts (`prompts/experience_card_v1.py`)

Copy-paste prompts for a universal Experience Card v1 pipeline (messy text → atoms → parent card → child cards → validated JSON). Align with `domain_schemas.ExperienceCardV1Schema`; do not assume the user is in tech.

| Prompt | Purpose |
|--------|---------|
| **`PROMPT_ATOMIZER`** | Split user message into atomic experiences (atom_id, raw_text_span, suggested_intent, why). Placeholder: `{{USER_TEXT}}`. |
| **`PROMPT_PARENT_AND_CHILDREN`** | From one atom produce one parent + 0–10 children in one call. Placeholders: `{{ATOM_TEXT}}`, `{{PERSON_ID}}`. |
| **`PROMPT_VALIDATOR`** | Validate and correct parent + children. Placeholder: `{{PARENT_AND_CHILDREN_JSON}}`. |

Use `fill_prompt(template, user_text=..., atom_text=..., person_id=..., parent_and_children_json=...)` to substitute placeholders. Pipeline order: atomizer → parent+children → validator.

---

## Services

### Auth (`services/auth.py`)

| Function | Step-by-step |
|----------|--------------|
| **`signup(db, body)`** | 1) Select Person by email; if exists → 400 "Email already registered". 2) Create Person (email, hashed_password from `hash_password(body.password)`, display_name). 3) Add Person, flush. 4) Create VisibilitySettings, ContactDetails, CreditWallet(balance=1000), CreditLedger(amount=1000, reason="signup"); add all, flush. 5) Refresh person; create JWT with `create_access_token(person.id)`; return TokenResponse. |
| **`login(db, body)`** | 1) Select Person by email. 2) If no person or `verify_password(body.password, person.hashed_password)` is False → 401 "Invalid email or password". 3) Return TokenResponse(access_token=create_access_token(person.id)). |
| **`AuthService`** | Facade with `signup` and `login` static methods. `auth_service` is the singleton used by the router. |

### Me (`services/me.py`)

| Function | Step-by-step |
|----------|--------------|
| **`_past_companies_to_items(past)`** | Convert list of dicts to list of `PastCompanyItem` (company_name, role, years). |
| **`_person_response(person)`** | Return PersonResponse(id, email, display_name, created_at). |
| **`get_profile(person)`** | Return _person_response(person). |
| **`update_profile(db, person, body)`** | If body.display_name is not None, set person.display_name; return _person_response(person). |
| **`get_visibility(db, person_id)`** | Load VisibilitySettings; if missing → 404; else return VisibilitySettingsResponse with all visibility fields. |
| **`patch_visibility(db, person_id, body)`** | Load or create VisibilitySettings; apply each non-None field from body (open_to_work, work_preferred_locations, salary fields, open_to_contact, contact salary fields); return VisibilitySettingsResponse. |
| **`get_bio_response(db, person)`** | Load Bio and ContactDetails for person; build BioResponse (including email from Person, linkedin/phone from Contact); set complete=True if bio has school and person has email. |
| **`update_bio(db, person, body)`** | Load or create Bio; apply every non-None field from body; if body.email set, update person.email; if first/last name set, set person.display_name from name parts; if linkedin_url/phone set, ensure ContactDetails exists and update; return BioResponse. |
| **`get_credits(db, person_id)`** | Load CreditWallet; return CreditsResponse(balance=wallet.balance or 0). |
| **`get_credits_ledger(db, person_id)`** | Select CreditLedger for person_id order by created_at desc; return list of LedgerEntryResponse. |
| **`_contact_response(c)`** | Map ContactDetails or None to ContactDetailsResponse (email_visible, phone, linkedin_url, other). |
| **`get_contact_response(db, person_id)`** | Load ContactDetails; return _contact_response(contact). |
| **`update_contact(db, person_id, body)`** | Load or create ContactDetails; apply email_visible, phone, linkedin_url, other from body; return _contact_response(contact). |
| **`MeService`** | Facade wrapping all above. `me_service` used by me and contact routers. |

### Search (`services/search.py`)

| Function | Step-by-step |
|----------|--------------|
| **`unlock_endpoint(person_id)`** | Return idempotency endpoint string: `"POST /people/{person_id}/unlock-contact"`. |
| **`_search_expired(search_rec)`** | True if search created_at is older than now minus SEARCH_RESULT_EXPIRY_HOURS. |
| **`run_search(db, searcher_id, body, idempotency_key)`** | 1) If idempotency_key: get existing idempotent response for POST /search; if found, return SearchResponse from stored body. 2) Check balance; if < 1 → 402. 3) Chat: parse_search_query(body.query) → ParsedQuery (company, team, open_to_work_only, semantic_text). 4) Embedding: embed(semantic_text or query) → query vector; normalize. 5) Get list of person_ids that have at least one APPROVED card with non-null embedding. 6) If no such persons: create Search record, deduct 1 credit, return empty people; optionally save idempotent response. 7) Else: raw SQL pgvector — `ec.embedding <=> :qvec`, group by person_id, MIN(1 - distance), order by score DESC, limit 50. 8) If open_to_work_only: filter to persons in VisibilitySettings.open_to_work. 9) If parsed company/team: filter to persons with matching (case-insensitive) card company/team. 10) If body.preferred_locations: keep only persons whose work_preferred_locations intersect. 11) If body.salary_min/max: filter by work_preferred_salary range overlap. 12) Take top 20. 13) Create Search record; deduct 1 credit; create SearchResult rows (rank, score); build PersonSearchResult list (load Person + VisibilitySettings for each); return SearchResponse; optionally save idempotent response. |
| **`get_person_profile(db, searcher_id, person_id, search_id)`** | 1) Load Search by id and searcher_id; if missing → 403 "Invalid search_id"; if expired → 403 "Search expired". 2) Load SearchResult for (search_id, person_id); if missing → 403 "Person not in this search result". 3) Load Person; if missing → 404. 4) Load VisibilitySettings. 5) Load APPROVED ExperienceCards for person, order by created_at desc. 6) If UnlockContact exists for (searcher, person, search), load ContactDetails and set contact in response; else contact=None. 7) Return PersonProfileResponse (id, display_name, visibility fields, experience_cards via serializer, contact). |
| **`unlock_contact(db, searcher_id, person_id, search_id, idempotency_key)`** | 1) If idempotency_key: get existing response for unlock endpoint; if found return it. 2) Validate search (same as get_person_profile); validate SearchResult; ensure person open_to_contact. 3) If UnlockContact already exists: load ContactDetails and return UnlockContactResponse(unlocked=True, contact). 4) Check balance; if < 1 → 402. 5) Create UnlockContact row; flush; deduct 1 credit (reason=unlock_contact, reference_id=unlock.id). 6) Load ContactDetails; return UnlockContactResponse; optionally save idempotent response. |
| **`SearchService`** | Facade: search → run_search, get_profile → get_person_profile, unlock → unlock_contact. |

### Experience card (`services/experience_card.py`)

| Function | Step-by-step |
|----------|--------------|
| **`_card_searchable_text(card)`** | Concatenate title, context, company, team, role_title, time_range, tags into one string for embedding. |
| **`create_raw_experience(db, person_id, body)`** | Create RawExperience(person_id, raw_text=body.raw_text); add, refresh; return raw. |
| **`create_experience_card(db, person_id, body)`** | Create ExperienceCard (person_id, raw_experience_id, status=DRAFT, title, context, constraints, decisions, outcome, tags, company, team, role_title, time_range); add, refresh; return card. |
| **`get_card_for_user(db, card_id, person_id)`** | Select ExperienceCard where id=card_id and person_id=person_id; return one or None. |
| **`apply_card_patch(card, body)`** | For each non-None field in ExperienceCardPatch (title, context, constraints, decisions, outcome, tags, company, team, role_title, time_range, locked), set on card; if any content field was set, set card.human_edited = True. |
| **`approve_experience_card(db, card)`** | Set card.status = APPROVED; build searchable text; call embedding provider.embed([text]); normalize vector and set card.embedding; return card. Raises EmbeddingServiceError if embed fails. |
| **`list_my_cards(db, person_id, status_filter)`** | Select ExperienceCard for person_id; if status_filter given filter by it, else exclude HIDDEN; order by created_at desc; return list. |
| **`ExperienceCardService`** | Facade: create_raw, create_card, get_card, approve, list_cards. `experience_card_service` used by builder router. |

---

## Routers

### Auth (`routers/auth.py`)

- **POST /auth/signup** — Body: SignupRequest. Depends: get_db. Calls `auth_service.signup(db, body)`; returns TokenResponse.
- **POST /auth/login** — Body: LoginRequest. Depends: get_db. Calls `auth_service.login(db, body)`; returns TokenResponse.

### Me (`routers/me.py`)

All require `get_current_user` (JWT). Prefix `/me`.

- **GET /me** — Returns PersonResponse via `me_service.get_me(current_user)`.
- **PATCH /me** — Body: PatchMeRequest. `me_service.patch_me(db, current_user, body)`.
- **GET /me/visibility** — `me_service.get_visibility(db, current_user.id)`.
- **PATCH /me/visibility** — Body: PatchVisibilityRequest. `me_service.patch_visibility(db, current_user.id, body)`.
- **GET /me/bio** — `me_service.get_bio(db, current_user)`.
- **PUT /me/bio** — Body: BioCreateUpdate. `me_service.put_bio(db, current_user, body)`.
- **GET /me/credits** — `me_service.get_credits(db, current_user.id)`.
- **GET /me/credits/ledger** — `me_service.get_credits_ledger(db, current_user.id)`.

### Contact (`routers/contact.py`)

Prefix `/me` (mounted with me). Requires `get_current_user`.

- **GET /me/contact** — `me_service.get_contact(db, current_user.id)`.
- **PATCH /me/contact** — Body: PatchContactRequest. `me_service.patch_contact(db, current_user.id, body)`.

### Builder (`routers/builder.py`)

All require `get_current_user` and `get_db`. Tags: builder.

- **POST /experiences/raw** — Body: RawExperienceCreate. Creates raw experience; returns RawExperienceResponse.
- **POST /experience-cards/draft-v1** — Body: RawExperienceCreate. Runs Experience Card v1 pipeline (atomize → parent extract → child gen → validate); on ChatServiceError → 503. Returns DraftSetV1Response (draft_set_id, raw_experience_id, card_families: list of { parent, children }).
- **POST /experience-cards** — Body: ExperienceCardCreate. Creates card; returns ExperienceCardResponse (via serializer).
- **PATCH /experience-cards/{card_id}** — Body: ExperienceCardPatch. Load card for user; 404 if not found; apply_card_patch(card, body); return serialized card.
- **POST /experience-cards/{card_id}/approve** — Load card; 404 if not found; approve (compute embedding); on EmbeddingServiceError → 503; return serialized card.
- **POST /experience-cards/{card_id}/hide** — Load card; 404 if not found; set status=HIDDEN; return serialized card.
- **GET /me/experience-cards** — Query: status (optional). If status not in DRAFT/APPROVED/HIDDEN → 400. List cards via service; return list of ExperienceCardResponse.

### Search (`routers/search.py`)

Require `get_current_user` and `get_db`.

- **POST /search** — Rate-limited by `search_rate_limit`. Header: Idempotency-Key (optional). Body: SearchRequest. Calls `search_service.search(db, current_user.id, body, idempotency_key)`.
- **GET /people/{person_id}** — Query: search_id (required). If missing → 400. `search_service.get_profile(db, current_user.id, person_id, search_id)`.
- **POST /people/{person_id}/unlock-contact** — Rate-limited by `unlock_rate_limit`. Query: search_id. Header: Idempotency-Key (optional). `search_service.unlock(db, current_user.id, person_id, search_id, idempotency_key)`.

---

## Migrations (Alembic)

- **`alembic/env.py`** — Inserts `apps/api` into sys.path. Reads `database_url` from settings; replaces `postgres://` with `postgresql://` for sync engine. Sets `config.sqlalchemy.url`. Imports `Base` and `db.models` so all tables are in metadata. **Offline**: configure with url and target_metadata, run_migrations in a transaction. **Online**: create sync engine with NullPool, connect, configure, run_migrations.
- **Versions** — `001_initial.py`: vector extension, people, visibility_settings, contact_details, credit_wallets, credit_ledger, idempotency_keys, raw_experiences, experience_cards (with vector(384)), searches, search_results, unlock_contacts. Later revisions add idempotency composite unique, bio/card flags, etc.

---

## Request flow summary

1. **Signup/Login** → auth router → auth service → DB (Person, wallet, ledger) / verify password → JWT in response.
2. **Authenticated request** → Bearer token → dependencies.get_current_user → decode JWT → load Person → inject into route.
3. **Search** → validate body → (optional) idempotency → credits check → chat parse query → embed query → pgvector similarity → filters (open_to_work, company/team, locations, salary) → create Search + SearchResult → deduct credit → return people.
4. **View profile** → validate search_id + searcher + not expired → ensure person in results → load person, visibility, approved cards; if unlock already done, include contact.
5. **Unlock contact** → same search validation → open_to_contact check → if already unlocked return cached; else deduct credit, create UnlockContact, return contact details.
6. **Builder: draft cards** → POST /experience-cards/draft-v1 runs v1 pipeline (atomize → parent → children → validate); cards persisted as DRAFT. **Approve card** → set APPROVED → embed card text → save embedding on card.

This README documents each backend step and function as implemented in the codebase.
