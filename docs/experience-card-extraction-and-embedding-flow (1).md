# Intent-Based People Search — Schema v1 (LOCKED) + Extraction & Indexing Flow (Implementation)

This document defines the **final v1 data schema** for an intent-based people search engine that converts messy human text into structured, searchable **Experience Cards (Parent + Children)** across **tech and non-tech domains**, and the **3-step ingestion flow** to extract, validate, and embed the data.

This version is **locked for implementation**. Future changes should be **additive** (v1.1, v2), not structural rewrites.

---

## 1. Core Design Principles

1. **Experience ≠ Status**  
   What someone *has done* is separate from what they *are doing now*.

2. **Intent-first, not keyword-first**  
   Search operates on normalized intent + evidence, not raw text.

3. **One Parent = One Intent Block**  
   Never mix multiple dominant intents into a single parent card.

4. **Children add proof, depth, and ranking power**  
   Parent answers *what*; children answer *how / with what / how much / exposure / scope*.

5. **Industry-agnostic by default**  
   Same schema supports quant, sales, photography, mining, ops, founders.

6. **Preserve raw inputs + version extraction runs**  
   Store **raw_text_original**, **raw_text_cleaned**, and version each extraction run with **draft_set_id**.

---

## 2. Entity Overview

**Core**
- users
- experience_cards (Parent)
- experience_child_cards (Children)
- skills (global)
- tools (global)
- experience_intents (ranking layer)
- user_current_status (NOT experience)

**Ingestion & Versioning (required for implementation)**
- raw_experiences  → **raw_experience_id = raw text version**
- draft_sets       → **draft_set_id = extraction run**

---

## 3. Users

```sql
users (
    id UUID PRIMARY KEY,
    name TEXT,
    headline TEXT,
    created_at TIMESTAMP
)
```

---

## 4. Raw Inputs & Extraction Runs (Implementation Layer)

### 4.1 raw_experiences (raw text version)
Store the original user text and a cleaned variant. This is the stable source-of-truth for re-processing.

```sql
raw_experiences (
    id UUID PRIMARY KEY,                 -- raw_experience_id
    user_id UUID REFERENCES users(id),

    raw_text_original TEXT NOT NULL,
    raw_text_cleaned  TEXT NOT NULL,

    source TEXT,                         -- optional: "builder_tab", "import", "profile_edit"
    content_hash TEXT,                   -- optional: dedupe / change detection
    created_at TIMESTAMP
)
```

### 4.2 draft_sets (extraction run)
Every extraction attempt gets its own run id. Do not couple this to raw_experience_id.

```sql
draft_sets (
    id UUID PRIMARY KEY,                 -- draft_set_id
    raw_experience_id UUID REFERENCES raw_experiences(id),

    extractor_version TEXT,              -- prompt/schema version (e.g., "v1.0.0")
    model_name TEXT,                     -- optional
    status TEXT,                         -- DRAFT | VALIDATED | FAILED
    created_at TIMESTAMP
)
```

---

## 5. Experience Cards (Parent — Core Unit)

Parents and children have **different fields** by design:
- **Parents** = the “intent block” + core context (role/company/time/location/summary/intents)
- **Children** = atomic evidence (skills/tools/metrics/exposure/scope/etc.)

```sql
experience_cards (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),

    -- Versioning
    raw_experience_id UUID REFERENCES raw_experiences(id), -- convenient pointer (also reachable via draft_set)
    draft_set_id UUID REFERENCES draft_sets(id),           -- extraction run that created/updated this card

    -- Parent identity
    title TEXT,                       -- human readable
    normalized_role TEXT,             -- canonical role name (e.g., "quantitative analyst")

    domain TEXT,                      -- finance, sales, photography, engineering
    sub_domain TEXT,                  -- quantitative_research, b2b_sales

    company_name TEXT,
    company_type TEXT,                -- hedge_fund, startup, agency, freelance

    employment_type TEXT,             -- full_time, contract, freelance

    -- Time (structured + display)
    start_date DATE,
    end_date DATE,
    is_current BOOLEAN,               -- aka is_ongoing
    time_text TEXT,                   -- original phrasing: "2 months", "2021–2024", "Summer 2022"

    -- Location (structured + display)
    location_text TEXT,               -- original phrasing / display
    city TEXT,                        -- nullable
    country TEXT,                     -- nullable

    seniority_level TEXT,             -- intern, junior, mid, senior, lead, founder

    summary TEXT,                     -- clean model-generated summary
    raw_text_span_original TEXT,      -- best-effort slice from raw_text_original (optional)
    raw_text_span_cleaned  TEXT,      -- best-effort slice from raw_text_cleaned  (optional)

    -- Intent
    intent_primary TEXT,              -- analysis, revenue, collaboration, leadership
    intent_secondary TEXT[],          -- markets, scale, operations

    confidence_score FLOAT,           -- 0–1 extraction confidence
    visibility BOOLEAN DEFAULT TRUE,

    -- Search + Embeddings (store rich data)
    search_phrases TEXT[],            -- 5–15 short phrases used for keyword fallback & UI
    search_document TEXT,             -- canonical text used for embedding + retrieval
    embedding VECTOR,                 -- e.g. pgvector vector(1536) (type varies by DB)

    extra JSONB,                      -- additive: store any rich structured fields not covered above

    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

**Rules**
- One parent card = one dominant intent.
- Unlimited parent cards per user.
- Parent cards are a primary search surface **and** an aggregation target for child matches.

---

## 6. Experience Child Cards (Depth & Evidence)

Children are atomic evidence. They **do not** repeat every parent field; instead, they reference the parent and contain granular proof.

```sql
experience_child_cards (
    id UUID PRIMARY KEY,
    parent_experience_id UUID REFERENCES experience_cards(id),

    child_type TEXT,                  -- skill | tool | metric | exposure | scope | responsibility | achievement | experience | domain_knowledge
    label TEXT,                       -- human readable label

    value TEXT,                       -- raw value ("₹15L", "3 years")
    normalized_value TEXT,            -- canonical value ("1500000_inr", "python")

    unit TEXT,                        -- INR, %, users, years
    time_period TEXT,                 -- "2 months", "2021–2024" (child-level time)

    confidence_score FLOAT,

    -- Search + Embeddings (embed children too)
    search_phrases TEXT[],            -- optional; useful for UI + fallback matching
    search_document TEXT,             -- include parent context + child detail
    embedding VECTOR,                 -- vector for child card (same dimension as parent)

    extra JSONB,                      -- additive: store richer evidence fields if needed

    created_at TIMESTAMP
)
```

### Allowed `child_type` (v1 locked)

- skill
- tool
- metric
- exposure
- scope
- responsibility
- achievement
- experience
- domain_knowledge

---

## 7. Global Skills

```sql
skills (
    id UUID PRIMARY KEY,
    name TEXT,
    normalized_name TEXT,
    category TEXT,        -- technical, soft, creative, operational
    domain TEXT
)
```

---

## 8. Global Tools

```sql
tools (
    id UUID PRIMARY KEY,
    name TEXT,
    normalized_name TEXT,
    tool_type TEXT,       -- software, hardware, platform
    domain TEXT
)
```

Child cards may internally reference these entities after normalization (via `normalized_value` + optional join tables if needed).

---

## 9. Experience Intents (Search & Ranking Layer)

```sql
experience_intents (
    id UUID PRIMARY KEY,
    experience_id UUID REFERENCES experience_cards(id),

    intent_type TEXT,     -- growth, revenue, research, markets, leadership
    strength FLOAT        -- 0–1
)
```

Used for:
- intent-based search
- ranking
- similarity matching

---

## 10. Current User Status (NOT Experience)

```sql
user_current_status (
    user_id UUID REFERENCES users(id),

    status_type TEXT,     -- education, employment, break
    current_state TEXT,   -- student, employed, self-employed

    confidence_score FLOAT,
    updated_at TIMESTAMP
)
```

**Rule:** This table must NEVER be joined into experience extraction.

---

## 11. Canonical Examples

### 11.1 Quant Example
- Parent: Quantitative Researcher (Finance → Quant)  
- Children:
  - experience → 3 years
  - skill → Python
  - skill → Statistical Modeling
  - exposure → Fund Managers
  - domain_knowledge → Capital Markets

### 11.2 Photography Collaboration Example
- Parent: Sales & Operations (Photography)  
- Children:
  - metric → ₹15L in 2 months
  - achievement → Studio collaborations
  - scope → Mumbai
  - responsibility → Admin panel management

---

## 12. 3-Step Ingestion Flow (No Atomization)

Atomization was removed because it breaks context (company/time leaks across atoms). We extract **all cards in one pass**.

### Step 1 — Cleanup (deterministic, no LLM)
**Input:** messy user text  
**Output:** raw_experience record

Actions:
1. Store `raw_text_original` verbatim.
2. Create `raw_text_cleaned` (trim, normalize whitespace, keep punctuation).
3. Create `raw_experience_id`.

### Step 2 — Extraction (one LLM pass)
**Input:** raw_text_cleaned (+ optional known profile fields like name)  
**Output:** a full set of **parents + children** for the run

Extractor must output:
- Parent cards with: role/company/domain/time/location/intents/summary/confidence
- Children for each parent: metrics/skills/tools/exposure/scope/etc.
- `search_phrases` for each parent and child (5–15)
- `raw_text_span_cleaned` for each parent (best-effort)

Persist:
- Create `draft_set_id` for this run.
- Insert cards as **DRAFT** linked to `draft_set_id` and `raw_experience_id`.

### Step 3 — Validation (one pass)
**Input:** extracted objects  
**Output:** validated + normalized objects

Validation tasks:
- Enforce “one parent = one intent block”.
- Parse/normalize:
  - dates (`start_date`, `end_date`, `is_current`)
  - location (`city`, `country`) from `location_text` when possible
  - numeric normalization for metrics (₹, %, years, users)
  - skill/tool canonicalization (`normalized_value`)
- If repair is needed, do a **single repair call** (still Step 3) and re-validate.

Mark `draft_sets.status = VALIDATED` when successful.

---

## 13. Embedding & Search Document Rules (Embed EVERYTHING)

### 13.1 Parent `search_document` (must include child evidence)
To “embed everything present” while keeping separate schemas, build parent `search_document` as:

- Parent core: title, role, domain/sub_domain, company/company_type, employment_type, seniority
- Time/location: time_text + (city/country if available)
- Summary + intents
- **Roll-up children**: for each child, append:
  - `child_type: label | value | normalized_value | unit | time_period`

This ensures parent embedding captures evidence even if child vectors are not used.

### 13.2 Child `search_document` (must include parent context)
Child embeddings must include enough context to be meaningful:

- Parent context: company_name, normalized_role, domain/sub_domain, time_text, city/country
- Child detail: child_type, label, value, normalized_value, unit, time_period

### 13.3 Store search_phrases
Store the extractor-generated phrases on both parent and child:
- used for keyword fallback
- used to explain why a result matched
- used to power “suggested searches” UI

---

## 14. Retrieval Behavior (How matches roll up)

Search can run on:
- parents only, or
- parents + children (recommended)

When searching children:
1. Retrieve top child matches.
2. Bubble matches to parent cards via `parent_experience_id`.
3. Aggregate to `user_id` and rank by:
   - child similarity score
   - parent similarity score (optional)
   - intent_strength
   - confidence_score
   - recency (optional)

Return:
- **people** + the **specific parent/child evidence** that matched.

---

## 15. Hard Rules (Do Not Break)

1. Do NOT merge multiple intents into one parent.
2. Do NOT store tools/skills as raw text only (always keep `normalized_value` when possible).
3. Do NOT downgrade experience because of student status.
4. Do NOT require company names to create experience cards.
5. Do NOT delete low-confidence cards — down-rank them.

---

## 16. What Is Explicitly Out of Scope (v1)

- Verification / proof uploads
- Social graph
- Endorsements
- Salary data
- Education history beyond current status

---

## 17. Versioning

- This document = **Schema v1 (LOCKED)**
- Changes must be backward compatible
- Extensions go into v1.1+ (additive columns/tables only)

---

**This schema is production-safe, LLM-compatible, search-optimized, and domain-agnostic.**
