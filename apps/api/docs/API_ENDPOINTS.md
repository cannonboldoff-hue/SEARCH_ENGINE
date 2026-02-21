# API Endpoints Reference

Overview of all CONXA API endpoints, grouped by area. Base URL is your API origin (e.g. `http://localhost:8000`). Auth-required endpoints expect a valid JWT in the `Authorization: Bearer <token>` header unless noted.

---

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | Health check. Returns `{"status": "ok"}`. |

---

## Auth (`/auth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/signup` | No | Register a new user. Body: `SignupRequest`. Returns `SignupResponse`. Rate limited. |
| `POST` | `/auth/login` | No | Log in. Body: `LoginRequest`. Returns `TokenResponse` (access token). Rate limited. |
| `POST` | `/auth/verify-email` | No | Verify email with token. Body: `VerifyEmailRequest`. Returns `VerifyEmailResponse`. Rate limited. |
| `POST` | `/auth/verify-email/resend` | No | Resend verification email. Body: `ResendVerificationRequest`. Returns `ResendVerificationResponse`. Rate limited. |

---

## Profile & Contact (`/me`)

*Profile and contact routers share the `/me` prefix; all require authentication.*

### Profile

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/me` | Get current user profile. Returns `PersonResponse`. |
| `PATCH` | `/me` | Update current user profile. Body: `PatchProfileRequest`. Returns `PersonResponse`. |
| `GET` | `/me/profile-v1` | Current user profile in domain v1 schema (`PersonSchema`). |
| `GET` | `/me/visibility` | Get visibility settings. Returns `VisibilitySettingsResponse`. |
| `PATCH` | `/me/visibility` | Update visibility settings. Body: `PatchVisibilityRequest`. Returns `VisibilitySettingsResponse`. |
| `GET` | `/me/bio` | Get current user bio. Returns `BioResponse`. |
| `PUT` | `/me/bio` | Create or replace bio. Body: `BioCreateUpdate`. Returns `BioResponse`. |
| `POST` | `/me/bio/photo` | Upload profile photo (multipart file). Returns `{ "profile_photo_url": "..." }` with signed token for `<img>`. |
| `GET` | `/me/bio/photo` | Serve profile photo. Use `?t=TOKEN` (from upload response) for unauthenticated image load; otherwise requires auth. |
| `GET` | `/me/credits` | Get current user credits. Returns `CreditsResponse`. |
| `POST` | `/me/credits/purchase` | Purchase credits. Body: `PurchaseCreditsRequest`. Returns `CreditsResponse`. |
| `GET` | `/me/credits/ledger` | Get credits transaction history. Returns list of `LedgerEntryResponse`. |
| `GET` | `/me/experience-cards` | List current user's experience cards. Returns list of `ExperienceCardResponse`. |
| `GET` | `/me/experience-card-families` | List saved experience cards with children grouped by parent. Returns list of `CardFamilyResponse`. |
| `GET` | `/me/experience-cards-v1` | List current user's experience cards in domain v1 schema (`ExperienceCardV1Schema`). |

### Contact

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/me/contact` | Get current user contact details. Returns `ContactDetailsResponse`. |
| `PATCH` | `/me/contact` | Update contact details. Body: `PatchContactRequest`. Returns `ContactDetailsResponse`. |

---

## Search

*All search endpoints require authentication. No path prefix.*

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/people` | List people for discover grid: name, location, top 5 experience titles. Returns `PersonListResponse`. |
| `GET` | `/me/searches` | List search history for current user with result counts. Query: `limit` (1–200, default 50). Returns `SavedSearchesResponse`. |
| `GET` | `/me/unlocked-cards` | List all unique people whose contact details were unlocked by current user. Returns `UnlockedCardsResponse`. |
| `GET` | `/people/{person_id}/profile` | Public profile for person detail: full bio + all experience card families (parent → children). Returns `PersonPublicProfileResponse`. |
| `POST` | `/search` | Run search. Body: `SearchRequest`. Optional header: `Idempotency-Key`. Returns `SearchResponse`. Rate limited. |
| `GET` | `/search/{search_id}/more` | Fetch more search results. Query: `offset` (default 0), `limit` (1–24, default 6), `history` (true = no credit deduction). Returns `SearchMoreResponse`. |
| `GET` | `/people/{person_id}` | Get person profile in search context. Query: optional `search_id`. Returns `PersonProfileResponse`. |
| `POST` | `/people/{person_id}/unlock-contact` | Unlock contact details for a person. Body: `UnlockContactRequest` (e.g. `search_id`). Optional header: `Idempotency-Key`. Returns `UnlockContactResponse`. Rate limited. |

---

## Builder (experience cards)

*All builder endpoints require authentication. No path prefix.*

### Raw experiences & text

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/experiences/raw` | Create a raw experience (store free-text). Body: `RawExperienceCreate`. Returns `RawExperienceResponse`. |
| `POST` | `/experiences/rewrite` | Rewrite messy input into clear English for extraction. No persistence. Body: `RawExperienceCreate`. Returns `RewriteTextResponse`. |
| `POST` | `/experiences/translate` | Translate multilingual input to English (e.g. Sarvam Translate). Body: `RawExperienceCreate`. Returns `TranslateTextResponse`. |
| `WS` | `/experiences/transcribe/stream` | WebSocket: stream audio chunks for STT; receive transcript events. Query: `token` (JWT), optional `language_code`/`lang`. Client messages: `audio_chunk`, `flush`, `stop`. |

### Experience card pipeline

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/experience-cards/detect-experiences` | Analyze text and return count + list of distinct experiences for user to choose. Body: `RawExperienceCreate`. Returns `DetectExperiencesResponse`. |
| `POST` | `/experience-cards/draft-v1-single` | Extract and draft one experience by index (1-based). Body: `DraftSingleRequest`. Returns `DraftSetV1Response`. |
| `POST` | `/experience-cards/fill-missing-from-text` | Rewrite + fill only missing fields from text; optionally persist when `card_id`/`child_id` provided. Body: `FillFromTextRequest`. Returns `FillFromTextResponse`. |
| `POST` | `/experience-cards/clarify-experience` | Interactive clarification (planner → validate → Q&A); optionally persist when filled. Body: `ClarifyExperienceRequest`. Returns `ClarifyExperienceResponse`. |

### Experience cards CRUD

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/experience-cards` | Create experience card. Body: `ExperienceCardCreate`. Returns `ExperienceCardResponse`. |
| `PATCH` | `/experience-cards/{card_id}` | Update experience card. Body: `ExperienceCardPatch`. Returns `ExperienceCardResponse`. |
| `DELETE` | `/experience-cards/{card_id}` | Delete experience card (and its children). Returns deleted `ExperienceCardResponse`. |
| `PATCH` | `/experience-card-children/{child_id}` | Update experience card child. Body: `ExperienceCardChildPatch`. Returns `ExperienceCardChildResponse`. |
| `DELETE` | `/experience-card-children/{child_id}` | Delete experience card child. Returns deleted `ExperienceCardChildResponse`. |

---

## Summary by tag

- **auth** — signup, login, email verification (all under `/auth`).
- **profile** — current user, visibility, bio, photo, credits, experience cards (under `/me`).
- **contact** — get/patch contact (under `/me`).
- **search** — people list, searches, unlock, search run and more (root paths).
- **builder** — raw experiences, rewrite/translate/transcribe, detect/draft/fill/clarify, card and child CRUD (root paths).

For request/response schemas and field details, see the OpenAPI docs at `/docs` (Swagger UI) or `/redoc` when the API is running.
