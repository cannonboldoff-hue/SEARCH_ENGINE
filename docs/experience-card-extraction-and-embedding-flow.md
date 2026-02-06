# Experience Card Extraction and Embedding Flow

This document provides a comprehensive step-by-step guide on how experience cards are extracted from raw text and then embedded in storage, from start to end.

---

## Overview

The experience card system transforms unstructured user input into structured, searchable cards through a multi-stage pipeline:

1. **User Input** → Raw text entered in the Builder UI
2. **Text Rewriting** → Normalize messy input into clear English
3. **Atomization** → Split text into discrete atomic experiences
4. **Parent Extraction** → Extract parent card for each atom
5. **Child Generation** → Generate child cards (skills, outcomes, etc.)
6. **Validation** → Validate and correct extracted cards
7. **Persistence** → Store cards as DRAFT in database
8. **Approval** → User approves cards
9. **Embedding** → Generate vector embeddings for searchable cards
10. **Storage** → Update cards with embeddings and APPROVED status

---

## Phase 1: User Input and Initial Processing

### Step 1.1: User Enters Raw Text

**Location:** `apps/web/src/app/(authenticated)/builder/page.tsx`

- User types or pastes unstructured text into a textarea component
- Text can be messy, informal, contain typos, slang, or mixed languages
- Example: *"I worked at Razorpay in the backend team for 2 years. Built APIs that handled millions of requests. Used Python and FastAPI."*

### Step 1.2: Frontend Triggers Extraction

**Location:** `apps/web/src/app/(authenticated)/builder/page.tsx` - `extractDraftV1` function

When user clicks "Update" button:
- Frontend calls `POST /experience-cards/draft-v1` endpoint
- Sends `{ raw_text: string }` in request body
- Sets loading state while processing

---

## Phase 2: API Endpoint Receives Request

### Step 2.1: Request Handler

**Location:** `apps/api/src/routers/builder.py` - `create_draft_cards_v1` endpoint

```python
@router.post("/experience-cards/draft-v1", response_model=DraftSetV1Response)
async def create_draft_cards_v1(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
```

- Validates user authentication
- Extracts `raw_text` from request body
- Calls `run_draft_v1_pipeline(db, current_user.id, body)`

---

## Phase 3: Experience Card v1 Pipeline

### Step 3.1: Create Raw Experience Record

**Location:** `apps/api/src/services/experience_card_v1.py` - `run_draft_v1_pipeline` function

```python
raw = RawExperience(person_id=person_id, raw_text=body.raw_text)
db.add(raw)
await db.flush()
raw_experience_id = str(raw.id)
draft_set_id = raw_experience_id
```

- Creates a `RawExperience` record in `raw_experiences` table
- Stores original user input for auditing/reference
- Generates `raw_experience_id` and `draft_set_id` (same value)

**Database Table:** `raw_experiences`
- `id` (UUID, primary key)
- `person_id` (UUID, foreign key to `people.id`)
- `raw_text` (TEXT, the original user input)
- `created_at` (TIMESTAMP)

### Step 3.2: Text Rewriting (Optional Normalization)

**Location:** `apps/api/src/services/experience_card_v1.py` - `run_draft_v1_pipeline` function

```python
rewrite_prompt = fill_prompt(PROMPT_REWRITE, user_text=body.raw_text)
rewritten = await chat.chat(rewrite_prompt, max_tokens=2048)
rewritten_text = rewritten.strip() or body.raw_text
```

**Purpose:** Normalize messy input into clear English for better extraction

**Process:**
1. Uses LLM (Chat Provider) with `PROMPT_REWRITE` prompt
2. Prompt instructs model to:
   - Fix typos and grammar
   - Expand abbreviations
   - Remove filler and repetition
   - Preserve all proper nouns, names, and numbers exactly
   - NOT add new facts or change meaning
3. If rewrite fails, falls back to original `raw_text`

**Chat Provider:** `apps/api/src/providers/chat.py`
- `get_chat_provider()` returns `OpenAIChatProvider` or `OpenAICompatibleChatProvider`
- Makes HTTP POST to `/v1/chat/completions` endpoint
- Handles retries, rate limiting, and error handling

---

## Phase 4: Atomization

### Step 4.1: Split Text into Atomic Experiences

**Location:** `apps/api/src/services/experience_card_v1.py` - `run_draft_v1_pipeline` function

```python
prompt = fill_prompt(PROMPT_ATOMIZER, user_text=rewritten_text)
response = await chat.chat(prompt, max_tokens=1024)
atoms = _parse_json_array(response)
```

**Purpose:** Break down text into discrete, atomic experiences

**Process:**
1. Uses `PROMPT_ATOMIZER` prompt with rewritten text
2. LLM identifies distinct experiences in the text
3. Returns JSON array of atoms, each containing:
   - `atom_id`: Sequential ID ("a1", "a2", ...)
   - `raw_text_span`: Exact substring(s) from input
   - `suggested_intent`: One of the allowed intent types
   - `why`: Justification for why this is a distinct atom

**Example Output:**
```json
[
  {
    "atom_id": "a1",
    "raw_text_span": "I worked at Razorpay in the backend team for 2 years",
    "suggested_intent": "work",
    "why": "Describes a specific work experience with company and team"
  },
  {
    "atom_id": "a2",
    "raw_text_span": "Built APIs that handled millions of requests",
    "suggested_intent": "achievement",
    "why": "Describes a measurable technical achievement"
  }
]
```

**Parsing:** `_parse_json_array` function handles:
- Stripping markdown code fences (```json)
- Best-effort JSON parsing if direct parse fails
- Returns list of atom dictionaries

---

## Phase 5: Parent and Child Card Extraction

### Step 5.1: Extract Parent and Children for Each Atom

**Location:** `apps/api/src/services/experience_card_v1.py` - `run_draft_v1_pipeline` function

For each atom:

```python
prompt = fill_prompt(
    PROMPT_PARENT_AND_CHILDREN,
    atom_text=atom_text,
    person_id=person_id,
)
response = await chat.chat(prompt, max_tokens=4096)
combined = _parse_json_object(response)
```

**Purpose:** Extract structured parent card and 0-10 child cards from each atom

**Process:**
1. Uses `PROMPT_PARENT_AND_CHILDREN` prompt
2. Prompt instructs model to:
   - Extract ONE parent card following `ExperienceCardParentV1Schema`
   - Extract 0-10 child cards following `ExperienceCardChildV1Schema`
   - Normalize typos, slang, abbreviations
   - Extract structured fields: headline, summary, time, location, roles, topics, entities, tooling, outcomes, etc.
   - NOT hallucinate or infer information not in raw text

**Parent Card Fields:**
- `id`, `person_id`, `created_by`, `version`
- `headline` (≤120 chars), `summary`, `raw_text`
- `intent`: One of allowed intents (work, education, project, achievement, etc.)
- `time`: { start, end, ongoing, text, confidence }
- `location`: { city, region, country, text, confidence }
- `roles`: [{ label, seniority, confidence }]
- `topics`: [{ label, raw, confidence }]
- `entities`: [{ type, name, entity_id, confidence }]
- `tooling`: { tools: [...], processes: [...], raw }
- `outcomes`: [{ type, label, value_text, metric, confidence }]
- `privacy`: { visibility, sensitive }
- `quality`: { overall_confidence, claim_state, needs_clarification, clarifying_question }
- `index`: { search_phrases: [...], embedding_ref: null }
- `parent_id`: null, `depth`: 0, `relation_type`: null

**Child Card Fields:**
- Same as parent, plus:
- `parent_id`: "parent" (literal string), `depth`: 1
- `relation_type`: Required, one of (component_of, skill_applied, method_used, tool_used, artifact_created, challenge_faced, decision_made, outcome_detail, learning_from, example_of)
- `intent`: Restricted to child intents only (responsibility, outcome, skill_application, method_used, challenge, decision, learning, artifact_created)

**Metadata Injection:**
```python
parent = _inject_parent_metadata(parent, person_id)
parent_id = parent["id"]
children = [_inject_child_metadata(c, parent_id) for c in children]
```

- `_inject_parent_metadata`: Adds `id`, `person_id`, `created_by`, `created_at`, `updated_at`, `parent_id=None`, `depth=0`, `relation_type=None`
- `_inject_child_metadata`: Adds `id`, `parent_id`, `depth=1`, timestamps

### Step 5.2: Validation

**Location:** `apps/api/src/services/experience_card_v1.py` - `run_draft_v1_pipeline` function

```python
combined = {"parent": parent, "children": children}
prompt = fill_prompt(
    PROMPT_VALIDATOR,
    parent_and_children_json=json.dumps(combined),
)
response = await chat.chat(prompt, max_tokens=4096)
validated = _parse_json_object(response)
```

**Purpose:** Validate, correct, and refine extracted cards

**Process:**
1. Uses `PROMPT_VALIDATOR` prompt with parent+children JSON
2. Validator:
   - Checks schema validity (all required fields present)
   - Removes hallucinations (information not in raw_text)
   - Normalizes language (verbs, topics, entities)
   - Ensures proper classification (intent, relation_type)
   - Prunes children that restate parent or add no value
   - Validates dates, locations, confidence levels
   - Generates search phrases (5-15 diverse phrases)
   - Checks privacy settings

**Output:** Corrected parent and children cards ready for persistence

---

## Phase 5.3: Detailed Field Extraction Guide

This section explains **what fields are extracted** from raw text and **how** they are extracted.

### Fields Extracted by PROMPT_PARENT_AND_CHILDREN

The `PROMPT_PARENT_AND_CHILDREN` prompt instructs the LLM to extract the following structured fields from each atom:

#### Core Content Fields

**1. `headline` (string, ≤120 chars)**
- **What:** Concise descriptor of the outcome or responsibility
- **How:** LLM generates a professional, factual headline
- **Example:** "Reduced API latency by 40% through caching layer redesign"
- **Rules:** NEVER use filler headlines like "Worked at a company"

**2. `summary` (string)**
- **What:** 1-3 sentence professional rewrite capturing full atom meaning
- **How:** LLM normalizes the raw text into clear, professional language
- **Example:** "Designed and implemented a distributed caching system using Redis that reduced API response times by 40% and improved system scalability."

**3. `raw_text` (string)**
- **What:** The ORIGINAL atom text, verbatim (before normalization)
- **How:** Copied directly from atom's `raw_text_span` or `cleaned_text`
- **Purpose:** Preserves original user input for reference

**4. `intent` (enum)**
- **What:** Classification of the experience type
- **How:** LLM selects best match from allowed values
- **Allowed Values (Parent):**
  - `education`, `work`, `project`, `achievement`, `certification`
  - `responsibility`, `skill_application`, `method_used`, `artifact_created`
  - `challenge`, `decision`, `learning`, `life_event`, `relocation`
  - `volunteering`, `community`, `finance`, `other`, `mixed`
- **Allowed Values (Child):** Restricted to child intents only:
  - `responsibility`, `outcome`, `skill_application`, `method_used`
  - `challenge`, `decision`, `learning`, `artifact_created`

#### Temporal Fields

**5. `time` (object)**
- **What:** Time period information
- **How:** LLM extracts ONLY explicitly stated dates/times
- **Structure:**
  ```json
  {
    "start": "YYYY-MM" or null,      // e.g., "2022-01"
    "end": "YYYY-MM" or null,         // e.g., "2024-12"
    "ongoing": bool or null,          // true if still ongoing
    "text": "free-text timespan",    // e.g., "last year", "2 years"
    "confidence": "high"|"medium"|"low"
  }
  ```
- **Rules:**
  - If user says "last year" → put in `text`, set `confidence="low"`
  - Do NOT guess specific dates
  - Prefer `text` field for vague time references

#### Location Fields

**6. `location` (object)**
- **What:** Geographic location information
- **How:** LLM extracts ONLY explicitly stated locations
- **Structure:**
  ```json
  {
    "city": "string" or null,         // e.g., "Bangalore"
    "region": "string" or null,      // e.g., "Karnataka"
    "country": "string" or null,      // e.g., "India"
    "text": "free-text" or null,      // e.g., "Bangalore, India"
    "confidence": "high"|"medium"|"low"
  }
  ```
- **Rules:**
  - Extract city/place from location object (separate from company)
  - Do NOT use location for company name
  - Split properly: city vs region vs country

#### Role Fields

**7. `roles` (array of objects)**
- **What:** Job roles or positions
- **How:** LLM extracts ONLY if user explicitly names a role
- **Structure:**
  ```json
  [
    {
      "label": "string",              // e.g., "Senior Software Engineer"
      "seniority": "string" or null,  // e.g., "Senior", "Lead"
      "confidence": "high"|"medium"|"low"
    }
  ]
  ```
- **Rules:**
  - Do NOT infer roles from company industry
  - Extract only explicitly stated roles

#### Action Fields

**8. `actions` (array of objects)**
- **What:** Verbs/actions performed
- **How:** LLM normalizes verbs to professional base form
- **Structure:**
  ```json
  [
    {
      "verb": "normalized_verb",      // e.g., "managed", "built", "designed"
      "verb_raw": "original_verb",    // e.g., "ran" → verb="managed", verb_raw="ran"
      "confidence": "high"|"medium"|"low"
    }
  ]
  ```
- **Rules:**
  - Normalize to base professional form
  - Keep `verb_raw` as user's original word

#### Topic Fields

**9. `topics` (array of objects)**
- **What:** Skills, technologies, domains, subjects
- **How:** LLM normalizes to standard professional terms
- **Structure:**
  ```json
  [
    {
      "label": "normalized_topic",    // e.g., "machine learning"
      "raw": "original_phrasing",     // e.g., "ML"
      "confidence": "high"|"medium"|"low"
    }
  ]
  ```
- **Rules:**
  - Normalize topic labels to standard terms
  - Eliminate low-signal topics ("stuff", "things", "work")
  - Keep `raw` for original phrasing

#### Entity Fields

**10. `entities` (array of objects)**
- **What:** Named entities (companies, schools, products, projects, etc.)
- **How:** LLM extracts entities with proper type classification
- **Structure:**
  ```json
  [
    {
      "type": "entity_type",           // See EntityType enum below
      "name": "string",                // e.g., "Razorpay", "FastAPI"
      "entity_id": null,               // Reserved for future linking
      "confidence": "high"|"medium"|"low"
    }
  ]
  ```
- **Entity Types (from taxonomy):**
  - `person`, `organization`, `company`, `school`, `team`, `community`
  - `place`, `event`, `program`, `domain`, `industry`
  - `product`, `service`, `artifact`, `document`, `portfolio_item`
  - `credential`, `award`, `tool`, `equipment`, `system`, `platform`
  - `instrument`, `method`, `process`

#### Tooling Fields

**11. `tooling` (object)**
- **What:** Tools, software, equipment, and processes used
- **How:** LLM extracts ONLY explicitly named tools/processes
- **Structure:**
  ```json
  {
    "tools": [
      {
        "name": "string",              // e.g., "Python", "Redis"
        "type": "tool_type",            // See ToolType enum below
        "confidence": "high"|"medium"|"low"
      }
    ],
    "processes": [
      {
        "name": "string",              // e.g., "Agile", "CI/CD"
        "confidence": "high"|"medium"|"low"
      }
    ],
    "raw": "original text" or null
  }
  ```
- **Tool Types:**
  - `software`, `equipment`, `system`, `platform`, `instrument`, `other`
- **Rules:**
  - Extract ONLY if user explicitly names them
  - NEVER guess tools from context

#### Outcome Fields

**12. `outcomes` (array of objects)**
- **What:** Measurable results and achievements
- **How:** LLM extracts measurable results only when stated
- **Structure:**
  ```json
  [
    {
      "type": "string",                // e.g., "performance", "revenue", "efficiency"
      "label": "string",               // e.g., "Reduced latency"
      "value_text": "string" or null,  // e.g., "by 40%"
      "metric": {
        "name": "string" or null,      // e.g., "latency"
        "value": float or null,        // e.g., 40.0
        "unit": "string" or null       // e.g., "percent", "ms"
      },
      "confidence": "high"|"medium"|"low"
    }
  ]
  ```
- **Rules:**
  - Extract measurable results only when stated
  - If metric claimed but no number given → set `value=null`, keep `label`

#### Evidence Fields

**13. `evidence` (array of objects)**
- **What:** URLs, file references, or supporting documents
- **How:** LLM extracts ONLY if user provides URLs or file references
- **Structure:**
  ```json
  [
    {
      "type": "evidence_type",        // "link", "file", "reference"
      "url": "string" or null,
      "note": "string" or null,
      "visibility": "visibility"       // "private", "profile_only", "searchable"
    }
  ]
  ```
- **Rules:**
  - Empty array unless user provides URLs or file references

#### Privacy Fields

**14. `privacy` (object)**
- **What:** Privacy and sensitivity settings
- **How:** LLM determines based on content
- **Structure:**
  ```json
  {
    "visibility": "visibility",        // "private", "profile_only", "searchable"
    "sensitive": bool                 // true if personal/medical/legal content
  }
  ```
- **Rules:**
  - Default: `visibility="searchable"`, `sensitive=false`
  - If text mentions medical/legal/personal → set `sensitive=true`, `visibility="private"`

#### Quality Fields

**15. `quality` (object)**
- **What:** Quality assessment and clarification needs
- **How:** LLM assesses confidence and missing information
- **Structure:**
  ```json
  {
    "overall_confidence": "high"|"medium"|"low",
    "claim_state": "self_claim",      // Default for user-submitted text
    "needs_clarification": bool,
    "clarifying_question": "string" or null
  }
  ```
- **Rules:**
  - Set `needs_clarification=true` if critical info missing
  - Provide ONE concise clarifying question if needed

#### Index Fields

**16. `index` (object)**
- **What:** Search phrases and embedding reference
- **How:** LLM generates diverse search phrases
- **Structure:**
  ```json
  {
    "search_phrases": [               // 5-15 diverse phrases
      "Python API development",
      "FastAPI backend engineering",
      "REST API design",
      ...
    ],
    "embedding_ref": null             // Reserved for future use
  }
  ```
- **Rules:**
  - Generate 5-15 concise, diverse search phrases
  - Include synonyms, related terms, specific and general phrases
  - Remove overly generic phrases

#### Child-Specific Fields

**17. `relation_type` (enum, child cards only)**
- **What:** Relationship between child and parent
- **How:** LLM selects appropriate relation type
- **Allowed Values:**
  - `component_of`, `skill_applied`, `method_used`, `tool_used`
  - `artifact_created`, `challenge_faced`, `decision_made`
  - `outcome_detail`, `learning_from`, `example_of`

**18. Rich JSON Fields (child cards only)**
- **What:** Full structured data stored as JSON
- **Stored As:** Raw JSON in database columns
- **Fields:**
  - `tooling`: Full tooling object
  - `entities`: Full entities array
  - `actions`: Full actions array
  - `outcomes`: Full outcomes array
  - `topics`: Full topics array
  - `evidence`: Full evidence array

---

## Phase 6: Persistence to Database (DRAFT Status)

### Step 6.1: Map V1 Schema to Database Models

**Location:** `apps/api/src/services/experience_card_v1.py` - `_persist_v1_family` function

**Parent Card Mapping:**
```python
parent_kw = _v1_card_to_experience_card_fields(parent, person_id, raw_experience_id)
parent_ec = ExperienceCard(**parent_kw)
```

**Function:** `_v1_card_to_experience_card_fields`
- Maps V1 schema fields to `ExperienceCard` database model
- Extracts `time.text` or constructs from `start`/`end`
- Extracts `location.city` or `location.text`
- Extracts first role's `label` as `role_title`
- Extracts `topics[].label` as `tags` array
- Extracts `company` or `organization` (NOT from location)
- Sets `status = ExperienceCard.DRAFT`
- Sets `embedding = None` (no embedding for drafts)

**Child Card Mapping:**
```python
kwargs = _v1_child_card_to_fields(
    card,
    person_id=person_id,
    raw_experience_id=raw_experience_id,
    parent_id=parent_ec.id,
)
ec = ExperienceCardChild(**kwargs)
```

**Function:** `_v1_child_card_to_fields`
- Similar to parent mapping
- Sets `parent_id`, `depth=1`, `relation_type`
- Stores rich fields as JSON: `tooling`, `entities`, `actions`, `outcomes`, `topics`, `evidence`
- Sets `status = ExperienceCard.DRAFT`
- Sets `embedding = None`

### Step 6.2: Database Insert

**Location:** `apps/api/src/services/experience_card_v1.py` - `_persist_v1_family` function

```python
db.add(parent_ec)
await db.flush()
await db.refresh(parent_ec)

for card in children:
    kwargs = _v1_child_card_to_fields(...)
    ec = ExperienceCardChild(**kwargs)
    db.add(ec)
    child_ecs.append(ec)

if child_ecs:
    await db.flush()
    for ec in child_ecs:
        await db.refresh(ec)
```

**Process:**
1. Add parent `ExperienceCard` to session
2. Flush to get database-generated `id`
3. Refresh to load the ID
4. For each child:
   - Map child data to `ExperienceCardChild` fields
   - Set `parent_id` to parent's ID
   - Add to session
5. Flush all children
6. Refresh each child to get IDs

**Database Tables:**

### Complete Database Schema

#### Table: `raw_experiences`

Stores the original unstructured user input.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Auto-generated unique identifier |
| `person_id` | UUID | FOREIGN KEY → `people.id`, NOT NULL, ON DELETE CASCADE | Owner of the raw experience |
| `raw_text` | TEXT | NOT NULL | Original user input text |
| `created_at` | TIMESTAMP WITH TIME ZONE | DEFAULT NOW() | Creation timestamp |

**Indexes:** None (queries typically filter by `person_id`)

---

#### Table: `experience_cards` (Parent Cards)

Stores parent experience cards extracted from raw text.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Auto-generated unique identifier |
| `person_id` | UUID | FOREIGN KEY → `people.id`, NOT NULL, ON DELETE CASCADE | Owner of the card |
| `raw_experience_id` | UUID | FOREIGN KEY → `raw_experiences.id`, NULLABLE, ON DELETE SET NULL | Source raw experience |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'DRAFT', INDEX | Status: 'DRAFT', 'APPROVED', 'HIDDEN' |
| `human_edited` | BOOLEAN | NOT NULL, DEFAULT FALSE | Whether card was manually edited |
| `locked` | BOOLEAN | NOT NULL, DEFAULT FALSE | Whether card is locked from editing |
| `title` | VARCHAR(500) | NULLABLE | Card headline/title (from `headline`) |
| `context` | TEXT | NULLABLE | Card summary/description (from `summary` or `raw_text`) |
| `constraints` | TEXT | NULLABLE | Constraints or limitations (not extracted, user-editable) |
| `decisions` | TEXT | NULLABLE | Key decisions made (not extracted, user-editable) |
| `outcome` | TEXT | NULLABLE | Outcome or result (not extracted, user-editable) |
| `tags` | ARRAY(VARCHAR) | DEFAULT [], NOT NULL | Array of topic tags (from `topics[].label`) |
| `company` | VARCHAR(255) | NULLABLE | Company name (from `company` or `organization`, NOT from location) |
| `team` | VARCHAR(255) | NULLABLE | Team/department name (not extracted, user-editable) |
| `role_title` | VARCHAR(255) | NULLABLE | Job role title (from `roles[0].label`) |
| `time_range` | VARCHAR(100) | NULLABLE | Time period as text (from `time.text` or constructed from `start`/`end`) |
| `location` | VARCHAR(255) | NULLABLE | Location as text (from `location.city` or `location.text`) |
| `embedding` | VECTOR(384) | NULLABLE | Normalized embedding vector (NULL for DRAFT, populated on APPROVE) |
| `created_at` | TIMESTAMP WITH TIME ZONE | DEFAULT NOW(), NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP WITH TIME ZONE | ON UPDATE NOW(), NULLABLE | Last update timestamp |

**Indexes:**
- `status` (for filtering by status)

**Relationships:**
- Belongs to `Person` (via `person_id`)
- Optionally belongs to `RawExperience` (via `raw_experience_id`)

---

#### Table: `experience_card_children` (Child Cards)

Stores child experience cards linked to parent cards.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Auto-generated unique identifier |
| `parent_id` | UUID | FOREIGN KEY → `experience_cards.id`, NOT NULL, ON DELETE CASCADE | Parent card reference |
| `person_id` | UUID | FOREIGN KEY → `people.id`, NOT NULL, ON DELETE CASCADE | Owner of the card |
| `raw_experience_id` | UUID | FOREIGN KEY → `raw_experiences.id`, NULLABLE, ON DELETE SET NULL | Source raw experience |
| `depth` | INTEGER | NOT NULL, DEFAULT 1 | Hierarchy depth (always 1 for children) |
| `relation_type` | VARCHAR(50) | NULLABLE | Relationship type (component_of, skill_applied, etc.) |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'DRAFT', INDEX | Status: 'DRAFT', 'APPROVED', 'HIDDEN' |
| `human_edited` | BOOLEAN | NOT NULL, DEFAULT FALSE | Whether card was manually edited |
| `locked` | BOOLEAN | NOT NULL, DEFAULT FALSE | Whether card is locked from editing |
| `title` | VARCHAR(500) | NULLABLE | Card headline/title (from `headline`) |
| `context` | TEXT | NULLABLE | Card summary/description (from `summary` or `raw_text`) |
| `constraints` | TEXT | NULLABLE | Constraints or limitations (not extracted, user-editable) |
| `decisions` | TEXT | NULLABLE | Key decisions made (not extracted, user-editable) |
| `outcome` | TEXT | NULLABLE | Outcome or result (not extracted, user-editable) |
| `tags` | ARRAY(VARCHAR) | DEFAULT [], NOT NULL | Array of topic tags (from `topics[].label`) |
| `company` | VARCHAR(255) | NULLABLE | Company name (from `company` or `organization`) |
| `team` | VARCHAR(255) | NULLABLE | Team/department name (not extracted, user-editable) |
| `role_title` | VARCHAR(255) | NULLABLE | Job role title (from `roles[0].label`) |
| `time_range` | VARCHAR(100) | NULLABLE | Time period as text (from `time.text` or constructed) |
| `location` | VARCHAR(255) | NULLABLE | Location as text (from `location.city` or `location.text`) |
| `tooling` | JSON | NULLABLE | Full tooling object (tools, processes, raw) |
| `entities` | JSON | NULLABLE | Full entities array (type, name, entity_id, confidence) |
| `actions` | JSON | NULLABLE | Full actions array (verb, verb_raw, confidence) |
| `outcomes` | JSON | NULLABLE | Full outcomes array (type, label, value_text, metric, confidence) |
| `topics` | JSON | NULLABLE | Full topics array (label, raw, confidence) |
| `evidence` | JSON | NULLABLE | Full evidence array (type, url, note, visibility) |
| `embedding` | VECTOR(384) | NULLABLE | Embedding vector (typically NULL, children not embedded) |
| `created_at` | TIMESTAMP WITH TIME ZONE | DEFAULT NOW(), NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP WITH TIME ZONE | ON UPDATE NOW(), NULLABLE | Last update timestamp |

**Indexes:**
- `status` (for filtering by status)

**Relationships:**
- Belongs to `ExperienceCard` (via `parent_id`)
- Belongs to `Person` (via `person_id`)
- Optionally belongs to `RawExperience` (via `raw_experience_id`)

---

### Field Mapping: V1 Schema → Database Columns

This section explains how fields extracted by the LLM (V1 schema) are mapped to database columns.

#### Parent Card Mapping (`_v1_card_to_experience_card_fields`)

| V1 Schema Field | Extraction Source | Database Column | Mapping Logic |
|----------------|-------------------|-----------------|---------------|
| `headline` | LLM extracted | `title` | Direct copy, truncated to 500 chars |
| `summary` or `raw_text` | LLM extracted | `context` | Prefer `summary`, fallback to `raw_text`, truncated to 10000 chars |
| `topics[].label` | LLM extracted | `tags[]` | Extract all `label` values, max 50 tags |
| `company` or `organization` | LLM extracted | `company` | Prefer `company`, fallback to `organization`, truncated to 255 chars, NOT from location |
| `location.city` or `location.text` | LLM extracted | `location` | Prefer `city`, fallback to `text` or `name`, truncated to 255 chars |
| `roles[0].label` | LLM extracted | `role_title` | First role's label, truncated to 255 chars |
| `time.text` or `time.start`/`end` | LLM extracted | `time_range` | Prefer `text`, else construct "start-end", truncated to 100 chars |
| `person_id` | System | `person_id` | From authenticated user |
| `raw_experience_id` | System | `raw_experience_id` | From created RawExperience |
| - | System | `status` | Always `'DRAFT'` initially |
| - | System | `human_edited` | Always `False` initially |
| - | System | `locked` | Always `False` initially |
| - | System | `embedding` | Always `NULL` for drafts |
| - | System | `constraints` | Always `NULL` (user-editable) |
| - | System | `decisions` | Always `NULL` (user-editable) |
| - | System | `outcome` | Always `NULL` (user-editable) |
| - | System | `team` | Always `NULL` (user-editable) |

**Fields NOT Stored in Parent Cards:**
- `intent` (not stored, used only for classification)
- `language` (not stored)
- `time` object details (only `time_range` text stored)
- `location` object details (only `location` text stored)
- `roles` array (only first role's label stored as `role_title`)
- `actions` array (not stored in parent)
- `entities` array (not stored in parent)
- `tooling` object (not stored in parent)
- `outcomes` array (not stored in parent)
- `evidence` array (not stored in parent)
- `privacy` object (not stored)
- `quality` object (not stored)
- `index` object (not stored)

#### Child Card Mapping (`_v1_child_card_to_fields`)

| V1 Schema Field | Extraction Source | Database Column | Mapping Logic |
|----------------|-------------------|-----------------|---------------|
| `headline` | LLM extracted | `title` | Direct copy, truncated to 500 chars |
| `summary` or `raw_text` | LLM extracted | `context` | Prefer `summary`, fallback to `raw_text`, truncated to 10000 chars |
| `topics[].label` | LLM extracted | `tags[]` | Extract all `label` values, max 50 tags |
| `company` or `organization` | LLM extracted | `company` | Prefer `company`, fallback to `organization`, truncated to 255 chars |
| `location.city` or `location.text` | LLM extracted | `location` | Prefer `city`, fallback to `text` or `name`, truncated to 255 chars |
| `roles[0].label` | LLM extracted | `role_title` | First role's label, truncated to 255 chars |
| `time.text` or `time.start`/`end` | LLM extracted | `time_range` | Prefer `text`, else construct "start-end", truncated to 100 chars |
| `depth` | LLM extracted | `depth` | Always `1` for children |
| `relation_type` | LLM extracted | `relation_type` | Direct copy, truncated to 50 chars |
| `tooling` | LLM extracted | `tooling` | Full JSON object stored as-is |
| `entities` | LLM extracted | `entities` | Full JSON array stored as-is |
| `actions` | LLM extracted | `actions` | Full JSON array stored as-is |
| `outcomes` | LLM extracted | `outcomes` | Full JSON array stored as-is |
| `topics` | LLM extracted | `topics` | Full JSON array stored as-is (in addition to `tags[]`) |
| `evidence` | LLM extracted | `evidence` | Full JSON array stored as-is |
| `parent_id` | System | `parent_id` | From parent card's `id` |
| `person_id` | System | `person_id` | From authenticated user |
| `raw_experience_id` | System | `raw_experience_id` | From created RawExperience |
| - | System | `status` | Always `'DRAFT'` initially |
| - | System | `human_edited` | Always `False` initially |
| - | System | `locked` | Always `False` initially |
| - | System | `embedding` | Always `NULL` (children typically not embedded) |
| - | System | `constraints` | Always `NULL` (user-editable) |
| - | System | `decisions` | Always `NULL` (user-editable) |
| - | System | `outcome` | Always `NULL` (user-editable) |
| - | System | `team` | Always `NULL` (user-editable) |

**Key Differences from Parent Cards:**
- Child cards store **full JSON objects** for rich fields (`tooling`, `entities`, `actions`, `outcomes`, `topics`, `evidence`)
- Child cards have `parent_id` and `relation_type` fields
- Child cards have `depth = 1`
- Child cards typically have `embedding = NULL` (not used for search)

**Fields NOT Stored in Child Cards:**
- `intent` (not stored, used only for classification)
- `language` (not stored)
- `time` object details (only `time_range` text stored)
- `location` object details (only `location` text stored)
- `roles` array (only first role's label stored as `role_title`)
- `privacy` object (not stored)
- `quality` object (not stored)
- `index` object (not stored)

### Step 6.3: Response to Frontend

**Location:** `apps/api/src/services/experience_card_v1.py` - `run_draft_v1_pipeline` function

```python
card_families.append({
    "parent": _draft_card_to_family_item(parent_ec),
    "children": [_draft_card_to_family_item(c) for c in child_ecs],
})
```

**Function:** `_draft_card_to_family_item`
- Serializes database model to API response format
- Maps `title` → `headline`, `context` → `summary`
- Maps `tags[]` → `topics: [{label: t}]`
- Returns simplified card representation

**Final Response:**
```python
return draft_set_id, raw_experience_id, card_families
```

**API Response:** `DraftSetV1Response`
- `draft_set_id`: UUID string
- `raw_experience_id`: UUID string
- `card_families`: Array of `{parent: {...}, children: [...]}`

---

## Phase 7: Frontend Display and User Review

### Step 7.1: Display Draft Cards

**Location:** `apps/web/src/app/(authenticated)/builder/page.tsx`

- Frontend receives `DraftSetV1Response`
- Displays parent cards with child cards nested underneath
- Shows card details: title, context, tags, time range, company, location, etc.
- User can edit, delete, or approve cards

### Step 7.2: User Clicks "Save Cards"

**Location:** `apps/web/src/app/(authenticated)/builder/page.tsx` - `handleSaveCards` function

```typescript
await api<ExperienceCard[]>("/draft-sets/" + draftSetId + "/commit", {
  method: "POST",
  body: {},
});
```

- Sends `POST /draft-sets/{draft_set_id}/commit` request
- Optional: can include `card_ids` in body to commit only selected cards

---

## Phase 8: Approval and Embedding Generation

### Step 8.1: API Endpoint - Commit Draft Set

**Location:** `apps/api/src/routers/builder.py` - `commit_draft_set` endpoint

```python
@router.post("/draft-sets/{draft_set_id}/commit", response_model=list[ExperienceCardResponse])
async def commit_draft_set(
    draft_set_id: str,
    body: CommitDraftSetRequest | None = None,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
```

**Process:**
1. Validates user authentication
2. Fetches draft cards:
   ```python
   cards = await experience_card_service.list_drafts_by_raw_experience(
       db, current_user.id, draft_set_id, card_ids=(body.card_ids if body else None)
   )
   ```
3. Approves cards in batch:
   ```python
   cards = await experience_card_service.approve_batch(db, cards)
   ```

### Step 8.2: Build Searchable Text for Each Card

**Location:** `apps/api/src/services/experience_card.py` - `approve_cards_batch` function

```python
texts = [_card_searchable_text(c) for c in cards]
```

**Function:** `_card_searchable_text`
```python
def _card_searchable_text(card: ExperienceCard) -> str:
    parts = [
        card.title or "",
        card.context or "",
        card.company or "",
        card.team or "",
        card.role_title or "",
        card.time_range or "",
        card.location or "",
        " ".join(card.tags or []),
    ]
    return " ".join(filter(None, parts))
```

**Purpose:** Concatenate all searchable fields into a single text string for embedding

**Example:**
- Title: "Built high-performance APIs"
- Context: "Designed and implemented REST APIs using FastAPI"
- Company: "Razorpay"
- Team: "Backend"
- Role: "Senior Software Engineer"
- Time: "2022-2024"
- Location: "Bangalore"
- Tags: ["Python", "FastAPI", "API Design"]

**Searchable Text:**
```
Built high-performance APIs Designed and implemented REST APIs using FastAPI Razorpay Backend Senior Software Engineer 2022-2024 Bangalore Python FastAPI API Design
```

### Step 8.3: Generate Embeddings

**Location:** `apps/api/src/services/experience_card.py` - `approve_cards_batch` function

```python
embed_provider = get_embedding_provider()
vectors = await embed_provider.embed(texts)
```

**Embedding Provider:** `apps/api/src/providers/embedding.py`

**Function:** `get_embedding_provider()`
- Returns `OpenAICompatibleEmbeddingProvider`
- Configured via environment variables:
  - `EMBED_API_BASE_URL`: Base URL for embedding API
  - `EMBED_API_KEY`: API key (optional)
  - `EMBED_MODEL`: Model name

**Process:**
1. Makes HTTP POST to `{base_url}/v1/embeddings`
2. Request body:
   ```json
   {
     "model": "embedding-model-name",
     "input": ["text1", "text2", ...]
   }
   ```
3. Response:
   ```json
   {
     "data": [
       {"index": 0, "embedding": [0.123, -0.456, ...]},
       {"index": 1, "embedding": [0.789, -0.012, ...]}
     ]
   }
   ```
4. Extracts embeddings, sorted by index
5. Returns list of vectors (each vector is list of floats)

**Vector Dimensions:**
- Default: 384 dimensions (for bge-base model)
- Stored as PostgreSQL `Vector(384)` type using pgvector extension

**Error Handling:**
- Raises `EmbeddingServiceError` on HTTP errors, timeouts, or invalid responses
- Validates that number of vectors matches number of input texts

### Step 8.4: Normalize and Store Embeddings

**Location:** `apps/api/src/services/experience_card.py` - `approve_cards_batch` function

```python
if len(vectors) != len(cards):
    raise EmbeddingServiceError("Embedding model returned wrong number of vectors.")

for card, vec in zip(cards, vectors):
    card.status = ExperienceCard.APPROVED
    card.embedding = normalize_embedding(vec)
```

**Function:** `normalize_embedding` (from `src.utils`)
- Normalizes vector to unit length (L2 normalization)
- Ensures consistent vector magnitudes for similarity search
- Formula: `vec_normalized = vec / ||vec||`

**Process:**
1. For each card and its corresponding vector:
   - Set `card.status = ExperienceCard.APPROVED`
   - Set `card.embedding = normalize_embedding(vec)`
2. Cards are modified in-place (already in SQLAlchemy session)
3. No explicit `db.add()` needed - SQLAlchemy tracks changes

### Step 8.5: Database Update (Commit)

**Location:** Automatic via SQLAlchemy session commit

When the request handler finishes:
- `get_db` dependency commits the transaction
- SQLAlchemy executes UPDATE statements for each card

**SQL Update (conceptual):**
```sql
UPDATE experience_cards
SET 
    status = 'APPROVED',
    embedding = '[0.123, -0.456, ...]'::vector(384),
    updated_at = NOW()
WHERE id IN (card_id_1, card_id_2, ...);
```

**Database State:**
- `status` changed from `'DRAFT'` to `'APPROVED'`
- `embedding` column updated with normalized vector
- `updated_at` timestamp updated

**Note:** Child cards (`experience_card_children`) are NOT embedded separately. Only parent cards get embeddings for search.

---

## Phase 9: Final Storage State

### Step 9.1: Database Tables After Approval

**`raw_experiences` table:**
- Contains original user input
- Referenced by `experience_cards.raw_experience_id`

**`experience_cards` table:**
- Parent cards with:
  - `status = 'APPROVED'`
  - `embedding` = normalized 384-dim vector
  - All extracted fields populated
  - Ready for semantic search

**`experience_card_children` table:**
- Child cards with:
  - `status = 'APPROVED'`
  - `embedding = NULL` (children are not embedded)
  - Rich JSON fields stored (`tooling`, `entities`, `actions`, `outcomes`, `topics`, `evidence`)
  - Linked to parent via `parent_id`

### Step 9.2: Search Capability

**Vector Search:**
- Parent cards can be searched using cosine similarity on `embedding` column
- Example query:
  ```sql
  SELECT id, title, context, 
         1 - (embedding <=> query_embedding::vector) AS similarity
  FROM experience_cards
  WHERE status = 'APPROVED'
  ORDER BY embedding <=> query_embedding::vector
  LIMIT 10;
  ```

**Searchable Fields:**
- Title, context, company, team, role_title, time_range, location, tags
- All concatenated into searchable text before embedding

---

## Summary: What We Extract and Store

### Extraction Summary

**From Raw Text, We Extract:**

1. **Core Content:**
   - Headline (concise descriptor)
   - Summary (professional rewrite)
   - Raw text (original preserved)
   - Intent (classification)

2. **Temporal Information:**
   - Start date (YYYY-MM format)
   - End date (YYYY-MM format)
   - Ongoing status
   - Free-text time range

3. **Location Information:**
   - City
   - Region
   - Country
   - Free-text location

4. **Professional Context:**
   - Job roles (with seniority)
   - Company/organization name
   - Team/department (user-editable, not extracted)

5. **Skills & Topics:**
   - Normalized topic labels
   - Original topic phrasing
   - Confidence levels

6. **Actions & Verbs:**
   - Normalized professional verbs
   - Original verb phrasing
   - Confidence levels

7. **Entities:**
   - Named entities (companies, products, projects, etc.)
   - Entity types (from taxonomy)
   - Confidence levels

8. **Tooling:**
   - Tools (software, equipment, systems)
   - Processes (methodologies, workflows)
   - Tool types and confidence

9. **Outcomes:**
   - Measurable results
   - Metrics (value, unit)
   - Outcome types

10. **Evidence:**
    - URLs, files, references
    - Evidence types
    - Visibility settings

11. **Metadata:**
    - Privacy settings
    - Quality assessment
    - Search phrases (5-15 per card)
    - Clarification needs

12. **Child Cards:**
    - Relation types (how child relates to parent)
    - Child-specific intents
    - Full rich JSON data

### Storage Summary

**What Gets Stored in Database:**

#### Parent Cards (`experience_cards`):
- ✅ `title` (from headline)
- ✅ `context` (from summary/raw_text)
- ✅ `tags[]` (from topics[].label)
- ✅ `company` (from company/organization, NOT location)
- ✅ `location` (from location.city/text)
- ✅ `role_title` (from roles[0].label)
- ✅ `time_range` (from time.text or constructed)
- ✅ `status` (DRAFT → APPROVED)
- ✅ `embedding` (384-dim vector, generated on approval)
- ❌ Rich JSON fields NOT stored (simplified to columns)

#### Child Cards (`experience_card_children`):
- ✅ All parent card fields (same mapping)
- ✅ `parent_id` (links to parent)
- ✅ `relation_type` (how child relates to parent)
- ✅ `depth` (always 1)
- ✅ `tooling` (full JSON object)
- ✅ `entities` (full JSON array)
- ✅ `actions` (full JSON array)
- ✅ `outcomes` (full JSON array)
- ✅ `topics` (full JSON array, in addition to tags[])
- ✅ `evidence` (full JSON array)
- ❌ `embedding` typically NULL (children not embedded)

#### Raw Experiences (`raw_experiences`):
- ✅ `raw_text` (original user input)
- ✅ `person_id` (owner)
- ✅ `created_at` (timestamp)

### Extraction Methods Summary

| Field Category | Extraction Method | LLM Prompt | Post-Processing |
|---------------|-------------------|------------|-----------------|
| Text normalization | LLM rewrite | `PROMPT_REWRITE` | Fallback to original if fails |
| Atom splitting | LLM classification | `PROMPT_ATOMIZER` | JSON parsing with best-effort |
| Core fields | LLM extraction | `PROMPT_PARENT_AND_CHILDREN` | Schema validation |
| Rich fields | LLM extraction | `PROMPT_PARENT_AND_CHILDREN` | Stored as JSON (children only) |
| Validation | LLM correction | `PROMPT_VALIDATOR` | Schema fixes, hallucination removal |
| Embeddings | Embedding API | N/A (uses searchable text) | L2 normalization |

### Key Design Decisions

1. **Parent Cards: Simplified Storage**
   - Store only essential fields as columns
   - Rich JSON data not stored (to keep schema simple)
   - Fast queries on common fields

2. **Child Cards: Rich Storage**
   - Store full JSON objects for rich fields
   - Preserves all extracted structure
   - Enables future rich queries

3. **Embeddings: Parent Cards Only**
   - Only parent cards get embeddings
   - Children linked via `parent_id`
   - Reduces storage and computation

4. **Company vs Location Separation**
   - Company extracted from `company`/`organization` fields
   - Location extracted from `location` object
   - Never mix the two (prevents errors)

5. **Time Range: Text Preferred**
   - Prefer `time.text` over structured dates
   - Handles vague references ("last year", "2 years")
   - Constructs "start-end" if only dates available

6. **Tags: Normalized Topics**
   - Extract from `topics[].label`
   - Normalized to standard terms
   - Max 50 tags per card

---

## Summary Flow Diagram

```
User Input (Raw Text)
    ↓
[Frontend] POST /experience-cards/draft-v1
    ↓
[API] Create RawExperience record
    ↓
[LLM] Rewrite text (normalize)
    ↓
[LLM] Atomize (split into atoms)
    ↓
For each atom:
    ↓
    [LLM] Extract parent + children
    ↓
    [LLM] Validate and correct
    ↓
    [DB] Insert ExperienceCard (DRAFT, embedding=NULL)
    ↓
    [DB] Insert ExperienceCardChild records (DRAFT, embedding=NULL)
    ↓
[API] Return draft_set_id + card_families
    ↓
[Frontend] Display cards for review
    ↓
User clicks "Save Cards"
    ↓
[Frontend] POST /draft-sets/{draft_set_id}/commit
    ↓
[API] Fetch draft cards
    ↓
[API] Build searchable text for each card
    ↓
[Embedding API] Generate vectors (384-dim)
    ↓
[API] Normalize vectors
    ↓
[API] Update cards: status=APPROVED, embedding=vector
    ↓
[DB] Commit transaction (UPDATE experience_cards)
    ↓
✅ Cards stored with embeddings, ready for search
```

---

## Key Files Reference

### Frontend
- `apps/web/src/app/(authenticated)/builder/page.tsx` - Builder UI component

### Backend API
- `apps/api/src/routers/builder.py` - API endpoints
- `apps/api/src/services/experience_card_v1.py` - V1 pipeline logic
- `apps/api/src/services/experience_card.py` - Card service and approval logic
- `apps/api/src/providers/chat.py` - LLM chat provider
- `apps/api/src/providers/embedding.py` - Embedding provider
- `apps/api/src/prompts/experience_card_v1.py` - LLM prompts

### Database Models
- `apps/api/src/db/models.py` - SQLAlchemy models (RawExperience, ExperienceCard, ExperienceCardChild)

### Schemas
- `apps/api/src/domain_schemas.py` - Pydantic schemas for V1 cards

---

## Important Notes

1. **Draft vs Approved:**
   - Draft cards have `status='DRAFT'` and `embedding=NULL`
   - Approved cards have `status='APPROVED'` and `embedding=<vector>`
   - Only approved cards are searchable

2. **Embedding Generation:**
   - Embeddings are generated ONLY when cards are approved
   - Searchable text includes: title, context, company, team, role_title, time_range, location, tags
   - Vectors are normalized (L2 normalization) before storage

3. **Child Cards:**
   - Child cards are NOT embedded separately
   - They store rich JSON data (tooling, entities, actions, outcomes, topics, evidence)
   - Linked to parent via `parent_id` foreign key

4. **Error Handling:**
   - LLM failures raise `ChatServiceError` or `ChatRateLimitError`
   - Embedding failures raise `EmbeddingServiceError`
   - All errors propagate to API layer and return appropriate HTTP status codes

5. **Database Transactions:**
   - Each API request uses a single database transaction
   - Changes are committed when request handler completes
   - If any step fails, entire transaction rolls back
