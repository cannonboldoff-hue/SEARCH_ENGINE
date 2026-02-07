# Scripts

## seed_db.py

Seeds the database with detailed, realistic experience data:

- **100 users** with mixed backgrounds:
  - ~40% **tech** (software engineers, data scientists, product managers, DevOps, etc.)
  - ~35% **non-tech** (teachers, nurses, designers, researchers, etc.)
  - ~25% **business** (analysts, consultants, sales, marketing, etc.)
- **5–8 parent experience cards per user** (~650 total parent cards)
- **2–4 child experience cards per parent** (~2,000 total child cards)
- **Messy, realistic raw text** for each experience (like real user input with typos, informal language, detailed stories)
- **Child card types** include: skills, tools, metrics, achievements, responsibilities, collaborations, domain knowledge, exposure, education, certifications
- Each user gets: `Person`, `Bio`, `VisibilitySettings`, `ContactDetails`, `CreditWallet`, and signup `CreditLedger`

**Requirements:**

- Database is running and migrations are applied.
- From project root or `apps/api`, `src` must be importable (e.g. run from `apps/api`).

**Run from `apps/api`:**

```bash
# With uv (if installed)
uv run python scripts/seed_db.py

# Or with system Python (ensure deps are installed, e.g. pip install -e .)
python scripts/seed_db.py
```

**Seed user password (all 100 users):** `SeedPassword123!`

**Example logins:**

- `seed.user1.tech@example.com` (tech background)
- `seed.user25.non_tech@example.com` (non-tech background)
- `seed.user50.business@example.com` (business background)
- … up to `seed.user100.<background>@example.com`

**Data Structure:**

Each **parent experience card** has:
- Detailed, messy `raw_text` (realistic user input)
- Company, role, dates, location, domain
- Search phrases and summary

Each **child experience card** contains:
- Specific details about skills, tools, achievements, etc.
- Structured `value` field with relevant data
- Search phrases for discoverability
- Confidence scores and metadata

This creates a rich dataset perfect for testing search, filtering, and experience card relationships.

---

## seed_db_llm.py (LLM-generated, unique data)

Uses your configured chat LLM to generate **unique, non-templated** people and experiences. Each run and each person is different; no fixed templates.

- **Configurable number of users** (default 10)
- **3–6 experience cards per user** (configurable), each with long **messy raw text** (150–400 words) and **2–4 child cards** (skills, tools, achievements, etc.)
- **Backgrounds:** tech, non_tech, business (random per user)
- **Same DB shape:** Person, Bio, VisibilitySettings, ContactDetails, CreditWallet, CreditLedger, ExperienceCard, ExperienceCardChild

**Requirements:**

- **LLM configured:** set `OPENAI_API_KEY` or `CHAT_API_BASE_URL` (and optionally `CHAT_API_KEY`, `CHAT_MODEL`) in `apps/api/.env`
- Database running and migrations applied
- Run from `apps/api` so `src` is importable

**Run from `apps/api`:**

```bash
# Default: 10 users, 3–6 cards each, 3s delay between LLM calls
python scripts/seed_db_llm.py

# More users, more cards, higher creativity
python scripts/seed_db_llm.py --users 20 --cards-min 4 --cards-max 7 --temperature 0.9

# Slower (avoid rate limits)
python scripts/seed_db_llm.py --users 50 --delay 3
```

**Options:**

| Option | Default | Description |
|--------|--------|-------------|
| `--users` | 10 | Number of users to generate |
| `--cards-min` | 3 | Min experience cards per user |
| `--cards-max` | 6 | Max experience cards per user |
| `--delay` | 3.0 | Seconds between LLM calls (use 5+ if you get 429 rate limits) |
| `--temperature` | 0.85 | LLM temperature (higher = more varied) |

**Seed password:** `SeedPassword123!`  
**Example logins:** `seed.llm.user1.tech@example.com`, `seed.llm.user2.non_tech@example.com`, …