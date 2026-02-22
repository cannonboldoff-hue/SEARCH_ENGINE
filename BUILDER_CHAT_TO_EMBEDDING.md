# Builder Chat → Experience Card Storage & Embedding (Full Detail)

This document lists **every function**, **every LLM call**, **every prompt**, and **every schema** involved in the flow from Builder Chat to stored experience cards with embeddings.

---

## Table of contents

1. [High-level flow](#high-level-flow)
2. [Frontend: Builder Chat – functions & types](#1-frontend-builder-chat--functions--types)
3. [API routes & request/response schemas](#2-api-routes--requestresponse-schemas)
4. [Pipeline: every function](#3-pipeline-every-function)
5. [Every LLM call & prompt](#4-every-llm-call--prompt)
6. [Pydantic & domain schemas](#5-pydantic--domain-schemas)
7. [Embedding & storage](#6-embedding--storage)

---

## High-level flow

```
Builder Chat (builder-chat.tsx)
  → POST /experience-cards/clarify-experience (opening question)
  → POST /experience-cards/detect-experiences (count + labels)
  → POST /experience-cards/draft-v1-single (extract one → persist → embed)
  → POST /experience-cards/clarify-experience (optional Q&A or fill)
       ↓
run_draft_v1_single: rewrite → extract (LLM) → validate (LLM) → persist_families → embed_cards
       ↓
DB: experience_cards.search_document, .embedding; experience_card_children.search_document, .embedding
```

---

## 1. Frontend: Builder Chat – functions & types

**File:** `apps/web/src/components/builder/builder-chat.tsx`

### Types (exported or local)

| Type | Definition | Use |
|------|------------|-----|
| `ChatMessage` | `{ id: string; role: "assistant" \| "user"; content: string; card?: CardFamilyV1Response }` | One message in the chat. |
| `Stage` | `"awaiting_experience" \| "awaiting_choice" \| "extracting" \| "clarifying" \| "card_ready" \| "idle"` | Chat state machine. |
| `BuilderChatProps` | `{ translateRawText: (text: string) => Promise<string>; onCardsSaved?: () => void }` | Props for `BuilderChat`. |

### Functions (in order of use)

| Function | Signature | Purpose |
|----------|-----------|---------|
| `buildSummaryFromParent` | `(parent: Record<string, unknown>) => string` | Builds a short summary from parent’s title, company_name, start_date, end_date, summary for display. |
| `BuilderChat` | `(props: BuilderChatProps) => JSX.Element` | Main chat component; holds state (messages, stage, currentCardFamily, clarifyHistory, etc.) and effects/handlers. |
| `addMessage` | `(msg: Omit<ChatMessage, "id">) => void` | Appends a message with generated `id` to `messages`. |
| `cleanupAudio` | `() => void` | Disconnects ScriptProcessor, source, closes AudioContext, stops media tracks (voice). |
| `stopRecording` | `() => void` | Sends WebSocket `{ type: "stop" }`, closes WS, runs cleanupAudio, clears liveTranscript; appends transcript to input if any. |
| `startRecording` | `() => Promise<void>` | Gets mic, creates AudioContext + ScriptProcessor, opens transcribe WebSocket, sends PCM; sets isRecording. |
| `toggleRecording` | `() => void` | Calls stopRecording if recording else startRecording. |
| `extractSingle` | `(experienceIndex: number, experienceCount: number, text: string) => Promise<{ summary: string; family: CardFamilyV1Response } \| null>` | Translates `text`, then `POST /experience-cards/draft-v1-single` with `raw_text`, `experience_index`, `experience_count`; sets currentCardFamily and clarifyHistory; returns summary + first family or null. |
| `askClarify` | `(currentCard: Record<string, unknown>, history: { role: string; content: string }[]) => Promise<{ clarifying_question?: string \| null; filled?: Record<string, unknown> }>` | Translates currentExperienceText, then `POST /experience-cards/clarify-experience` with raw_text, current_card, card_type `"parent"`, conversation_history; returns response. |
| `mergeFilledIntoCard` | `(filled: Record<string, unknown>) => void` | Merges `filled` into `currentCardFamily.parent` in state. |
| `sendMessage` | `() => Promise<void>` | Main handler: reads input/liveTranscript, adds user message; by stage: (1) awaiting_experience → detect-experiences → extract or await choice, (2) awaiting_choice → extractSingle for chosen index, (3) clarifying → askClarify, merge or finish; invalidates queries and calls onCardsSaved when card is ready. |

### API calls made from Builder Chat

| Method + path | Body (relevant) | Response type |
|---------------|------------------|---------------|
| `POST /experience-cards/clarify-experience` | `raw_text`, `current_card`, `card_type`, `conversation_history` | `{ clarifying_question?: string \| null; filled?: Record<string, unknown> }` |
| `POST /experience-cards/detect-experiences` | `{ raw_text }` | `DetectExperiencesResponse` |
| `POST /experience-cards/draft-v1-single` | `{ raw_text, experience_index, experience_count }` | `DraftSetV1Response` |

### Frontend types (from `apps/web/src/types/index.ts`)

| Type | Fields |
|------|--------|
| `CardFamilyV1Response` | `parent: ExperienceCardV1; children: ExperienceCardV1[]` |
| `DraftSetV1Response` | `draft_set_id: string; raw_experience_id: string; card_families: CardFamilyV1Response[]` |
| `DetectExperiencesResponse` | `count: number; experiences: DetectedExperienceItem[]` |
| `DetectedExperienceItem` | `index: number; label: string; suggested?: boolean` |
| `ExperienceCardV1` | From `@/lib/schemas` (nested fields for parent/child v1 shape). |

---

## 2. API routes & request/response schemas

**File:** `apps/api/src/routers/builder.py`  
**Schemas:** `apps/api/src/schemas/builder.py`

### Endpoints used by Builder Chat

| Method + path | Handler | Request body (Pydantic) | Response (Pydantic) |
|---------------|---------|------------------------|---------------------|
| `POST /experience-cards/detect-experiences` | `detect_experiences_endpoint` | `RawExperienceCreate` | `DetectExperiencesResponse` |
| `POST /experience-cards/draft-v1-single` | `create_draft_single_experience` | `DraftSingleRequest` | `DraftSetV1Response` |
| `POST /experience-cards/clarify-experience` | `clarify_experience` | `ClarifyExperienceRequest` | `ClarifyExperienceResponse` |

### Request/response schemas (Pydantic)

**RawExperienceCreate**  
- `raw_text: str`

**DetectExperiencesResponse**  
- `count: int = 0`  
- `experiences: list[DetectedExperienceItem] = []`

**DetectedExperienceItem**  
- `index: int`  
- `label: str`  
- `suggested: bool = False`

**DraftSingleRequest**  
- `raw_text: str`  
- `experience_index: int = 1`  
- `experience_count: int = 1`

**DraftSetV1Response**  
- `draft_set_id: str`  
- `raw_experience_id: str`  
- `card_families: list[CardFamilyV1Response]`

**CardFamilyV1Response**  
- `parent: dict` (v1 parent)  
- `children: list[dict] = []` (v1 children)

**ClarifyExperienceRequest**  
- `raw_text: str`  
- `card_type: str = "parent"`  // `"parent"` \| `"child"`  
- `current_card: dict = {}`  
- `conversation_history: list[ClarifyMessage] = []`  
- `card_id: Optional[str] = None`  
- `child_id: Optional[str] = None`

**ClarifyMessage**  
- `role: str`  // `"assistant"` \| `"user"`  
- `content: str`

**ClarifyExperienceResponse**  
- `clarifying_question: Optional[str] = None`  
- `filled: dict = {}`

**ExperienceCardCreate** (used elsewhere; listed for completeness)  
- All optional: title, normalized_role, domain, sub_domain, company_name, company_type, start_date, end_date, is_current, location, employment_type, summary, raw_text, intent_primary, intent_secondary, seniority_level, confidence_score, experience_card_visibility

**ExperienceCardPatch**  
- Same keys as create, all optional.

**ExperienceCardResponse**  
- id, user_id, title, normalized_role, domain, sub_domain, company_name, company_type, start_date, end_date, is_current, location, employment_type, summary, raw_text, intent_primary, intent_secondary, seniority_level, confidence_score, experience_card_visibility, created_at, updated_at

**ExperienceCardChildPatch**  
- title, summary, tags, time_range, company, location (all optional)

**ExperienceCardChildResponse**  
- id, relation_type, title, context, tags, headline, summary, topics, time_range, role_title, company, location

---

## 3. Pipeline: every function

**File:** `apps/api/src/services/experience_card_pipeline.py`

### Parsing & validation

| Function | Signature | Purpose |
|----------|-----------|---------|
| `_strip_json_fence` | `(text: str) -> str` | Removes leading/trailing markdown code fences (```) from LLM response. |
| `_extract_json_from_text` | `(text: str) -> str` | Finds first `{` or `[` and returns substring that parses as JSON (brace-counting fallback). Raises `ValueError` if no valid JSON. |
| `_normalize_child_dict_for_v1_card` | `(child_dict: dict) -> dict` | Maps prompt-style child (`child_type`, `label`, `value: { headline, summary, ... }`) to V1Card-compatible top-level headline/title/summary/time/location/roles/topics/entities/tooling/outcomes/evidence/company/team/intent/relation_type/depth/index. |
| `parse_llm_response_to_families` | `(response_text: str, stage: PipelineStage) -> list[V1Family]` | Strips fence, extracts JSON, normalizes to list of family dicts (handles `families`, `parents`, single `parent`, or array); normalizes children with `_normalize_child_dict_for_v1_card`; validates each as `V1Family`. Raises `PipelineError` on empty or invalid. |

### Metadata & field extraction

| Function | Signature | Purpose |
|----------|-----------|---------|
| `inject_metadata_into_family` | `(family: V1Family, person_id: str) -> V1Family` | Sets parent/child ids (uuid4 if missing), person_id, created_by, created_at, updated_at, parent_id, depth (0/1), relation_type. |
| `_month_name_to_number` | `(text: str) -> Optional[int]` | Maps month name (e.g. "jan", "january") to 1–12. |
| `parse_date_field` | `(value: Optional[str]) -> Optional[date]` | Parses ISO, month+year, year-only, etc. into `date`. |
| `_extract_dates_from_text` | `(text: str) -> tuple[Optional[date], Optional[date]]` | Extracts up to two dates from a time-range string. |
| `extract_time_fields` | `(card: V1Card) -> tuple[Optional[str], Optional[date], Optional[date], Optional[bool]]` | Returns (time_text, start_date, end_date, is_ongoing) from card.time / start_date / end_date / time_text / is_current. |
| `extract_location_fields` | `(card: V1Card) -> tuple[Optional[str], Optional[str], Optional[str]]` | Returns (location_text, city, country) from card.location. |
| `extract_company` | `(card: V1Card) -> Optional[str]` | card.company or company_name or organization, or first entity with type company/organization. |
| `extract_team` | `(card: V1Card) -> Optional[str]` | card.team or first entity type "team". |
| `extract_role_info` | `(card: V1Card) -> tuple[Optional[str], Optional[str]]` | (role_title, seniority) from card.roles[0] or normalized_role/seniority_level. |
| `extract_search_phrases` | `(card: V1Card) -> list[str]` | Deduplicated list from card.index.search_phrases and card.search_phrases (max 50). |
| `normalize_card_title` | `(card: V1Card, fallback_text: Optional[str] = None) -> str` | Title from headline → title → first line of summary → raw_text → fallback → "Experience". |

### Persistence

| Function | Signature | Purpose |
|----------|-----------|---------|
| `card_to_experience_card_fields` | `(card: V1Card, *, person_id, raw_experience_id, draft_set_id) -> dict` | Builds ExperienceCard column dict: user_id, raw_text, title, normalized_role, domain, sub_domain, company_name, company_type, start_date, end_date, is_current, location, employment_type, summary, intent_primary, intent_secondary, seniority_level, confidence_score, experience_card_visibility, search_phrases, **search_document** (headline/title + summary + role + company + location + tags). |
| `card_to_child_fields` | `(card: V1Card, *, person_id, raw_experience_id, draft_set_id, parent_id) -> dict` | Builds ExperienceCardChild column dict: parent_experience_id, person_id, raw_experience_id, draft_set_id, child_type, label, value (dimension container), confidence_score, search_phrases, **search_document** (headline + summary + role + company + team + location + tags), embedding=None. |
| `persist_families` | `async (db, families, *, person_id, raw_experience_id, draft_set_id) -> tuple[list[ExperienceCard], list[ExperienceCardChild]]` | For each family: card_to_experience_card_fields → ExperienceCard; for each child card_to_child_fields → ExperienceCardChild; db.add, flush, refresh. Raises PipelineError on DB failure. |

### Embedding

| Function | Signature | Purpose |
|----------|-----------|---------|
| `embed_cards` | `async (db, parents, children) -> None` | Collects doc = parent.search_document or _experience_card_search_document(parent), and child.search_document; batches embed_texts; get_embedding_provider().embed(embed_texts); normalize_embedding per vector; assigns to obj.embedding; db.flush(). Raises PipelineError on mismatch or EmbeddingServiceError. |

### Serialization

| Function | Signature | Purpose |
|----------|-----------|---------|
| `serialize_card_for_response` | `(card: ExperienceCard | ExperienceCardChild) -> dict` | Converts DB card to API response shape (id, title, context, tags, etc.). |

### Helper (fill/clarify)

| Function | Signature | Purpose |
|----------|-----------|---------|
| `fill_missing_fields_from_text` | `async (raw_text, current_card, card_type) -> dict` | rewrite_raw_text → PROMPT_FILL_MISSING_FIELDS → chat.chat → parse JSON; normalizes intent_secondary_str, tagsStr, dates; returns filled dict. |
| `_parse_date_field_for_clarify` | `(val: Any) -> Optional[str]` | parse_date_field → ISO string or None. |
| `clarify_experience_interactive` | `async (raw_text, current_card, card_type, conversation_history) -> dict` | If raw_text empty: return fixed opening question. Else: rewrite_raw_text → PROMPT_CLARIFY_EXPERIENCE (with current_card, allowed_keys, conversation_history) → chat.chat → return clarifying_question and/or filled (with key normalization). |
| `rewrite_raw_text` | `async (raw_text: str) -> str` | Uses PROMPT_REWRITE; get_chat_provider().chat(prompt, max_tokens=2048); normalizes whitespace. Raises HTTPException 400 if empty, PipelineError on empty result or ChatServiceError. |
| `detect_experiences` | `async (raw_text: str) -> dict` | rewrite_raw_text → PROMPT_DETECT_EXPERIENCES → chat.chat → parse JSON to {"count", "experiences": [{index, label, suggested}]}. Normalizes indices; ensures one suggested. Returns {"count": 0, "experiences": []} on parse failure. |
| `next_draft_run_version` | `async (db, raw_experience_id, person_id) -> int` | MAX(draft_sets.run_version) + 1 for that raw_experience + person. |
| `run_draft_v1_single` | `async (db, person_id, raw_text, experience_index, experience_count) -> tuple[str, str, list[dict]]` | Single-experience pipeline: rewrite → RawExperience + DraftSet → extract (PROMPT_EXTRACT_SINGLE_CARDS) → validate (PROMPT_VALIDATE_ALL_CARDS) → persist_families → embed_cards → serialize. Returns (draft_set_id, raw_experience_id, card_families) with at most one family. |

### Normalizers (used by V1Card)

| Function | Signature | Purpose |
|----------|-----------|---------|
| `_normalize_roles` | `(raw: Any) -> list[dict]` | List of {label, seniority} from role items (dict or string). |
| `_normalize_topics` | `(raw: Any) -> list[dict]` | List of {label} from topic items. |
| `_normalize_entities` | `(raw: Any) -> list[dict]` | List of {type, name} from entity items. |
| `_normalize_event_like_list` | `(raw: Any) -> list[dict]` | Actions/outcomes/evidence as list of dicts (or {text}). |

---

## 4. Every LLM call & prompt

**Provider:** `get_chat_provider()` → `OpenAICompatibleChatProvider` in `apps/api/src/providers/chat.py`.  
**Method:** `chat.chat(prompt: str, max_tokens=...)` → single user message, returns assistant reply string.

**Prompt filler:** `fill_prompt(template, **kwargs)` in `apps/api/src/prompts/experience_card.py` — replaces `{{USER_TEXT}}`, `{{PERSON_ID}}`, `{{CLEANED_TEXT}}`, `{{EXPERIENCE_INDEX}}`, `{{EXPERIENCE_COUNT}}`, `{{INTENT_ENUM}}`, `{{ALLOWED_CHILD_TYPES}}`, `{{PARENT_AND_CHILDREN_JSON}}`, `{{RAW_TEXT_ORIGINAL}}`, `{{RAW_TEXT_CLEANED}}`, `{{CURRENT_CARD_JSON}}`, `{{ALLOWED_KEYS}}`, `{{CONVERSATION_HISTORY}}`.

### LLM call 1: Rewrite

- **Where:** `rewrite_raw_text(raw_text)`  
- **Prompt:** `PROMPT_REWRITE`  
- **Filled:** `user_text=raw_text`  
- **Invocation:** `chat.chat(prompt, max_tokens=2048)`  
- **Output:** Cleaned English text (no JSON).

**PROMPT_REWRITE** (full):

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

---

### LLM call 2: Detect experiences

- **Where:** `detect_experiences(raw_text)` (after rewrite).  
- **Prompt:** `PROMPT_DETECT_EXPERIENCES`  
- **Filled:** `cleaned_text=cleaned` (output of rewrite).  
- **Invocation:** `chat.chat(prompt, max_tokens=1024)`  
- **Output:** JSON `{ "count": N, "experiences": [ { "index", "label", "suggested" }, ... ] }`.

**PROMPT_DETECT_EXPERIENCES** (full):

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

---

### LLM call 3: Extract single experience

- **Where:** `run_draft_v1_single` → extract step.  
- **Prompt:** `PROMPT_EXTRACT_SINGLE_CARDS`  
- **Filled:** `user_text=raw_text_cleaned`, `experience_index=idx`, `experience_count=total`, plus enums from `experience_card_enums` (INTENT_ENUM, ALLOWED_CHILD_TYPES).  
- **Invocation:** `chat.chat(extract_prompt, max_tokens=8192)`  
- **Output:** JSON with one family: `{ "parents": [ { "parent": {...}, "children": [...] } ] }`. Parsed by `parse_llm_response_to_families(..., stage=EXTRACT)`.

**PROMPT_EXTRACT_SINGLE_CARDS** (full):

```
You are a structured data extraction system.

The cleaned text below contains MULTIPLE distinct experience blocks. Your task is to extract ONLY ONE of them.

CRITICAL: Extract ONLY the experience at position {{EXPERIENCE_INDEX}} (1 = first experience in the text, 2 = second, etc.). There are {{EXPERIENCE_COUNT}} distinct experiences total. Ignore all others.

Return exactly ONE parent and its child dimension cards. Use the SAME schema as the full extract (parent with all keys, children with allowed child_type). Output format:

{
  "parents": [
    {
      "parent": { ... single parent with all required keys ... },
      "children": [ ... ]
    }
  ]
}

- parent: same keys as in the full extraction (title, normalized_role, domain, company_name, start_date, end_date, summary, intent_primary, etc.). intent_primary MUST be one of: {{INTENT_ENUM}}
- children: YOU MUST EXTRACT CHILD DIMENSION CARDS when the experience mentions them. Allowed child_type: {{ALLOWED_CHILD_TYPES}}. Create one child per dimension present...
- raw_text in parent must be a verbatim excerpt from the cleaned text for THIS experience only.
- Do NOT invent facts. Use null for missing fields.

Cleaned text:
{{USER_TEXT}}

Extract ONLY the {{EXPERIENCE_INDEX}}-th experience (of {{EXPERIENCE_COUNT}}). Return valid JSON only:
```

---

### LLM call 4: Validate all cards

- **Where:** `run_draft_v1_single` → validate step.  
- **Prompt:** `PROMPT_VALIDATE_ALL_CARDS`  
- **Filled:** `raw_text_original`, `raw_text_cleaned`, `parent_and_children_json=json.dumps(validate_payload)` (extracted families), plus INTENT_ENUM, ALLOWED_CHILD_TYPES.  
- **Invocation:** `chat.chat(validate_prompt, max_tokens=8192)`  
- **Output:** JSON with validated parents/children; parsed by `parse_llm_response_to_families(..., stage=VALIDATE)`. On failure, extraction output is used.

**PROMPT_VALIDATE_ALL_CARDS** (summary): Validates, normalizes, de-duplicates; hallucination removal; schema enforcement (intent_primary, child_type, confidence_score, dates); parent split check; child quality; search_document presence. Output: `{ "raw_text_original", "raw_text_cleaned", "parents": [ { "parent", "children" } ] }`.

---

### Opening question (clarify with empty input) — no LLM

- **Where:** `clarify_experience_interactive(raw_text="", ...)` when user has not shared anything.  
- **Behavior:** Returns a fixed clarifying question (no LLM call): *"What's one experience you'd like to add? Tell me in your own words."*

---

### LLM call 6: Clarify experience (Q&A or fill)

- **Where:** `clarify_experience_interactive(raw_text, current_card, card_type, conversation_history)` when raw_text non-empty.  
- **Prompt:** `PROMPT_CLARIFY_EXPERIENCE`  
- **Filled:** `cleaned_text` (rewrite of raw_text), `current_card_json`, `allowed_keys` (FILL_MISSING_PARENT_KEYS or FILL_MISSING_CHILD_KEYS), `conversation_history` (string of "role: content" lines).  
- **Invocation:** `chat.chat(prompt, max_tokens=1024)`  
- **Output:** JSON either `{"clarifying_question": "..."}` or `{"filled": { ... }}` (or both empty). Keys normalized (intent_secondary_str, tagsStr, dates to ISO).

**PROMPT_CLARIFY_EXPERIENCE** (summary): Friendly conversation to understand experience; ask one short natural question OR return filled fields for empty keys only; same key names as allowed_keys; dates YYYY-MM-DD; return only one of clarifying_question or filled.

**Allowed keys (parent):**  
`title, summary, normalized_role, domain, sub_domain, company_name, company_type, location, employment_type, start_date, end_date, is_current, intent_primary, intent_secondary_str, seniority_level, confidence_score`

**Allowed keys (child):**  
`title, summary, tagsStr, time_range, company, location`

---

### LLM call 7: Fill missing fields (edit form – not used by Builder Chat flow above)

- **Where:** `fill_missing_fields_from_text(raw_text, current_card, card_type)`.  
- **Prompt:** `PROMPT_FILL_MISSING_FIELDS`  
- **Filled:** `cleaned_text`, `current_card_json`, `allowed_keys`.  
- **Invocation:** `chat.chat(prompt, max_tokens=2048)`  
- **Output:** JSON object of only filled fields (merge into form).

---

## 5. Pydantic & domain schemas

### Domain enums (`apps/api/src/domain.py`)

- **Intent:** `Literal["work","education","project","business","research","practice","exposure","achievement","transition","learning","life_context","community","finance","other","mixed"]`
- **ChildRelationType:** `Literal["describes","supports","demonstrates","results_in","learned_from","involves","part_of"]`
- **ChildIntent:** `Literal["responsibility","capability","method","outcome","learning","challenge","decision","evidence"]`
- **ALLOWED_CHILD_TYPES:** `("skills","tools","metrics","achievements","responsibilities","collaborations","domain_knowledge","exposure","education","certifications")`
- **ENTITY_TAXONOMY:** list of entity types (person, organization, company, school, team, …).

### Prompt enums (`apps/api/src/prompts/experience_card_enums.py`)

- **INTENT_ENUM** = ", ".join(Intent)
- **CHILD_INTENT_ENUM**, **CHILD_RELATION_TYPE_ENUM**, **ENTITY_TYPES**, **ALLOWED_CHILD_TYPES_STR** — same for prompts.

### Pipeline Pydantic models (`experience_card_pipeline.py`)

**TimeInfo:** text, start, end, ongoing (all optional).  
**LocationInfo:** text, city, country (optional).  
**RoleInfo:** label, seniority (optional).  
**TopicInfo:** label: str.  
**EntityInfo:** type: str, name: str.  
**IndexInfo:** search_phrases: list[str].

**V1Card:** Base card from LLM. Fields include: id, headline, title, label, summary, raw_text, time, location, time_text, start_date, end_date, is_current, city, country, roles, topics, entities, actions, outcomes, evidence, tooling, company, company_name, organization, team, normalized_role, seniority_level, domain, sub_domain, company_type, employment_type, index, search_phrases, search_document, intent, intent_primary, intent_secondary, confidence_score; person_id, created_by, created_at, updated_at, parent_id, depth, relation_type, child_type. Has validators to normalize prompt-style and legacy keys (intent ↔ intent_primary, company ↔ company_name, roles from normalized_role, time from start/end/time_text/is_current, index from search_phrases, and list normalizers for roles/topics/entities/actions/outcomes/evidence).

**V1Family:** parent: V1Card, children: list[V1Card].

**V1ExtractorResponse:** families: list[V1Family] (extra="allow" for parents wrapper).

**PipelineStage:** REWRITE, EXTRACT, VALIDATE, PERSIST, EMBED.

**PipelineError:** stage, message, cause.

---

## 6. Embedding & storage

### Embedding

- **Function:** `embed_cards(db, parents, children)` in `experience_card_pipeline.py`.
- **Text source:** Parent: `parent.search_document or _experience_card_search_document(parent)` (`experience_card.py`: title, normalized_role, domain, sub_domain, company_name, company_type, location, employment_type, summary, raw_text, intent_primary, intent_secondary, seniority_level, date range, "current"). Child: `child.search_document` (trimmed); skip if empty.
- **Provider:** `get_embedding_provider()` → `OpenAICompatibleEmbeddingProvider` (`apps/api/src/providers/embedding.py`): POST to `{EMBED_API_BASE_URL}/v1/embeddings`, body `{"model": embed_model, "input": texts}`; returns list of embeddings by index.
- **Normalize:** `normalize_embedding(vec, dim=provider.dimension)` in `src/utils.py` — truncate or zero-pad to `dim` (default 324).
- **Config:** `apps/api/src/core/config.py`: embed_api_base_url, embed_api_key, embed_model (default "text-embedding-3-large"), embed_dimension (default 324).

### Storage (DB)

- **experience_cards:** search_document (Text), embedding (Vector(324)); plus title, normalized_role, company_name, summary, dates, intent_primary, etc.
- **experience_card_children:** search_document (Text), embedding (Vector(324)); plus parent_experience_id, person_id, child_type, label, value (JSONB).

---

## 7. Full prompt texts (reference)

**PROMPT_EXTRACT_SINGLE_CARDS** (used by run_draft_v1_single): Extract ONE experience by index; same parent/child schema as above; output `{"parents": [{ "parent", "children" }]}` with one family. Placeholders: {{USER_TEXT}}, {{EXPERIENCE_INDEX}}, {{EXPERIENCE_COUNT}}, {{INTENT_ENUM}}, {{ALLOWED_CHILD_TYPES}}.

**PROMPT_VALIDATE_ALL_CARDS:** Inputs raw_text_original, raw_text_cleaned, extracted_json; hallucination removal; schema enforcement; parent split check; child quality; search_document required. Output JSON with raw_text_original, raw_text_cleaned, parents.

**PROMPT_FILL_MISSING_FIELDS:** Fill only missing/empty fields from cleaned text; allowed keys; current card JSON; return single JSON object, no commentary.

**PROMPT_CLARIFY_EXPERIENCE:** Conversation to understand experience; ask one natural question OR return filled (same keys as allowed); never both; only fill empty fields; dates YYYY-MM-DD. Placeholders: {{ALLOWED_KEYS}}, {{CURRENT_CARD_JSON}}, {{CLEANED_TEXT}}, {{CONVERSATION_HISTORY}}.

All prompts live in `apps/api/src/prompts/experience_card.py`; `fill_prompt()` applies the replacements listed in section 4.

---

## Key files

| Purpose | File |
|--------|------|
| Chat UI | `apps/web/src/components/builder/builder-chat.tsx` |
| Frontend types | `apps/web/src/types/index.ts`, `apps/web/src/lib/schemas.ts` |
| Builder routes | `apps/api/src/routers/builder.py` |
| Builder schemas | `apps/api/src/schemas/builder.py` |
| Pipeline | `apps/api/src/services/experience_card_pipeline.py` |
| Experience card service | `apps/api/src/services/experience_card.py` |
| Prompts | `apps/api/src/prompts/experience_card.py` |
| Prompt enums | `apps/api/src/prompts/experience_card_enums.py` |
| Domain | `apps/api/src/domain.py` |
| Chat provider | `apps/api/src/providers/chat.py` |
| Embedding provider | `apps/api/src/providers/embedding.py` |
| Config | `apps/api/src/core/config.py` |
| Utils | `apps/api/src/utils.py` |
| DB models | `apps/api/src/db/models.py` |
