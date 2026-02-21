# Frontend — How It Works

This document explains how the Discover frontend works **step by step**, including every major function and component.

---

## Table of Contents

1. [Overview & Tech Stack](#1-overview--tech-stack)
2. [Project Structure](#2-project-structure)
3. [App Entry & Layout Flow](#3-app-entry--layout-flow)
4. [Routing & Pages](#4-routing--pages)
5. [Contexts](#5-contexts)
6. [Hooks](#6-hooks)
7. [Lib (API & Utils)](#7-lib-api--utils)
8. [Types](#8-types)
9. [Components](#9-components)
10. [Styling](#10-styling)

---

## 1. Overview & Tech Stack

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS + CSS variables (light/dark)
- **State:** React Query (TanStack Query) for server state; React state for UI
- **Forms:** react-hook-form + Zod validation
- **Animations:** Framer Motion
- **Icons:** Lucide React

The app is a **people-discovery** product: users sign in, build a profile (bio + experience cards), search by natural-language intent, and view/unlock contact for people. Credits govern search and contact unlock.

---

## 2. Project Structure

```
apps/web/
├── src/
│   ├── app/                    # Next.js App Router pages & layouts
│   │   ├── layout.tsx          # Root layout (fonts, providers, AuthProvider)
│   │   ├── page.tsx            # Root redirect (/) → /home or /login
│   │   ├── globals.css         # Global styles, CSS variables, utilities
│   │   ├── login/              # Login page
│   │   ├── signup/             # Signup page
│   │   └── (authenticated)/    # Routes that require a token
│   │       ├── layout.tsx      # Wraps with AppNav; redirects if no token
│   │       ├── home/           # Discover home (search)
│   │       ├── search/         # Redirects to /home
│   │       ├── profile/        # My profile (bio + experience cards)
│   │       ├── builder/        # Experience card builder
│   │       ├── onboarding/bio/ # Create/edit bio
│   │       ├── people/[id]/    # Person profile (from search)
│   │       └── settings/       # Credits, account, logout
│   ├── components/             # Reusable UI
│   ├── contexts/               # React context (auth)
│   ├── hooks/                  # Custom hooks (e.g. useCredits)
│   ├── lib/                    # api(), utils (cn, API_BASE)
│   └── types/                  # Shared TypeScript types
├── package.json
└── README.md (this file)
```

---

## 3. App Entry & Layout Flow

### `src/app/layout.tsx`

- **Purpose:** Root HTML layout for the whole app.
- **What it does:**
  - Loads Google fonts: **Outfit** (sans) and **JetBrains Mono** (mono), exposed as CSS variables `--font-outfit` and `--font-mono`.
  - Sets `<html lang="en" className="dark">` (dark theme by default).
  - Wraps `children` in **Providers** (React Query) and **AuthProvider** (auth context).
- **Exports:** `metadata` (title, description) and default `RootLayout`.

### `src/app/page.tsx` (root `/`)

- **Purpose:** Single entry for `/`; redirects based on auth.
- **Flow:**
  1. Uses `useAuth()` to read `token`.
  2. In `useEffect`: if `token` exists → `router.replace("/home")`; else → `router.replace("/login")`.
  3. While deciding, renders **LoadingScreen**.
- **Functions:**
  - **RootPage:** Client component that performs the redirect and shows loading.

---

## 4. Routing & Pages

### Login — `src/app/login/page.tsx`

- **Purpose:** Sign in with email/password.
- **Flow:**
  1. If user already has token (from context or `localStorage`), redirect to `/home` and show loading.
  2. Otherwise show login form inside **AuthLayout** (title, subtitle, hero background).
  3. Form uses **react-hook-form** with **Zod** schema: `email` (valid email), `password` (required).
  4. On submit → `login(email, password)` from auth context; on success auth context redirects to `/home`; on error, `setError` and show **ErrorMessage**.
- **Functions:**
  - **onSubmit(data):** Clears error, calls `login(data.email, data.password)`, catches errors and sets `error` state.

### Signup — `src/app/signup/page.tsx`

- **Purpose:** Create account (email, password, optional display name).
- **Flow:** Same pattern as login: redirect if token exists; otherwise form with Zod schema (`email`, `password` min 8, optional `display_name`). On submit → `signup({ email, password, displayName })`, then route to `/verify-email?email=...`.
- **Functions:**
  - **onSubmit(data):** Clears error, calls `signup({ email: data.email, password: data.password, displayName: data.display_name || undefined })`, then routes to `/verify-email` with the prefilled email.

### Authenticated layout — `src/app/(authenticated)/layout.tsx`

- **Purpose:** All routes under `(authenticated)` require a valid token.
- **Flow:**
  1. Reads `token` from `useAuth()` and checks `localStorage` for token (for initial load).
  2. If no token → `router.replace("/login")` and show “Loading…”.
  3. If token exists → render **AppNav** and `children` inside `<main>` with mesh background.
- **Functions:**
  - **AuthenticatedLayout:** Wraps children with nav and main container; guards access by token.

### Home (Discover) — `src/app/(authenticated)/home/page.tsx`

- **Purpose:** Main search page: hero, search form, and results.
- **State:** `query`, `openToWorkOnly`, `searchId`, `people`, `error`.
- **Flow:**
  1. Renders **HeroBg**, then headline and description.
  2. **SearchForm** is controlled by `query` / `setQuery`, `openToWorkOnly` / `setOpenToWorkOnly`, `error`, and callbacks `onSuccess` / `onError`.
  3. When search succeeds, **handleSearchSuccess** sets `searchId`, `people`, and clears `error`.
  4. **SearchResults** receives `searchId` and `people` and shows result cards (or empty state).
- **Functions:**
  - **handleSearchSuccess(data):** `setSearchId(data.search_id)`, `setPeople(data.people)`, `setError(null)`.

### Search — `src/app/(authenticated)/search/page.tsx`

- **Purpose:** Redirect only. **redirect("/home")** so `/search` always goes to home.

### Profile — `src/app/(authenticated)/profile/page.tsx`

- **Purpose:** Show current user’s bio and experience cards.
- **Flow:**
  1. Fetches **bio** and **experience cards** via React Query: `api("/me/bio")`, `api("/me/experience-cards")`.
  2. Loading → “Loading profile…”.
  3. Error → “Failed to load profile…”.
  4. Success → Card with “My profile”, links to “Edit Bio” (`/onboarding/bio`) and “Experience builder” (`/builder`), then bio fields and list of experience cards with status badges (APPROVED/DRAFT, human_edited, locked).
- **Functions:** No custom handlers; uses `useQuery` and renders data.

### Builder — `src/app/(authenticated)/builder/page.tsx`

- **Purpose:** Turn raw experience text into structured “experience cards” (parent + children) via the v1 pipeline; save/approve all.
- **Main state:** `rawText`, `cardFamilies`, `expandedFamilies`, `saveModalOpen`, `deletedId`, `isUpdating`, `saveError`, `isSavingAll`.
- **Flow:**
  1. **useQuery** loads saved experience cards from `api("/me/experience-cards")`.
  2. User types in textarea; “Update” calls **extractDraftV1**: POST `/experience-cards/draft-v1` with `raw_text`; response gives `card_families` (parent + children per family). Cards are persisted as DRAFT on the backend.
  3. **handleSaveCards** approves all cards in `cardFamilies` via POST `/experience-cards/:id/approve` for each, then closes modal, invalidates queries, and `router.push("/home")`; on error sets `saveError`.
  4. Saved cards list: delete (DELETE `/experience-cards/:id`). **CardTypeIcon** picks icon from tags/title (research, startup, quant, open-source, default).
- **Functions:**
  - **extractDraftV1():** POST draft-v1, set `cardFamilies`, expand all family IDs in `expandedFamilies`.
  - **handleSaveCards():** Approve all card IDs in `cardFamilies`, then redirect or set error.
  - **v1CardTopics(card):** Returns topic labels from v1 card for display.

### Onboarding Bio — `src/app/(authenticated)/onboarding/bio/page.tsx`

- **Purpose:** Create or edit user bio (name, DOB, city, education, work, contact, past companies).
- **Flow:**
  1. **useQuery** loads `api("/me/bio")` and fills form with **setValue** in `useEffect` when `bio` is loaded (including `past_companies`).
  2. **useFieldArray** for `past_companies` (append/remove rows).
  3. Validation: **bioSchema** (Zod) — required first/last name, DOB (YYYY-MM-DD), city, school, email; optional college, LinkedIn URL (regex), phone, past companies.
  4. **putBio** mutation: PUT `/me/bio` with form data; on success invalidates `["bio"]` and `router.push("/home")`; on error sets `serverError`.
- **Functions:**
  - **onSubmit(data):** Clears server error, calls `putBio.mutate` with normalized payload (filter empty past companies, trim optional strings).

### Person profile — `src/app/(authenticated)/people/[id]/page.tsx`

- **Purpose:** View a person’s profile from search results; optionally unlock contact (1 credit).
- **Flow:**
  1. Reads `personId` from `params.id` and `searchId` from `searchParams.get("search_id")`. If no `searchId`, shows message and “Back to Discover”.
  2. **useQuery** fetches `api(`/people/${personId}?search_id=...`)` → **PersonProfile** (display name, open_to_work/contact, experience cards, contact if unlocked).
  3. **unlockMutation:** POST with **apiWithIdempotency** to `/people/:id/unlock-contact?search_id=...` (idempotency key per request); on success invalidates person query so contact appears.
  4. Renders profile card, experience cards, and contact section: if unlocked show details; else if open_to_contact show “Unlock contact (1 credit)” button; else “Not open to contact”.
- **Functions:**
  - **unlockMutation.mutate():** Sends idempotent unlock request; refetches profile on success.

### Settings — `src/app/(authenticated)/settings/page.tsx`

- **Purpose:** Show credits balance, account (email, display name), and logout.
- **Flow:** Uses **useAuth()** for `user` and `logout`, **useCredits()** for balance. Renders cards for credits, account, and sign-out button.
- **Functions:** No custom logic; presentational with context/hook data.

---

## 5. Contexts

### Auth — `src/contexts/auth.tsx`

- **Purpose:** Hold token and user, and expose login, signup, logout, setOnboardingStep.
- **State:** `token` (from `localStorage` on init), `user` (from `/me` when token exists).

**Functions:**

- **startSession(accessToken, step?):** Stores token (and optional onboarding step) in `localStorage`, sets `isAuthLoading` while `/me` loads.
- **clearSession():** Clears token and onboarding step from `localStorage`, resets auth state.
- **useEffect (on mount/hydration):** Reads token from `localStorage`, sets token state; if token exists, fetches `/me` and sets user, or clears token on error.
- **login(email, password):** POST `/auth/login` with `{ email, password }` → `access_token`. Stores the token and redirects to `/home`.
- **signup(payload):** POST `/auth/signup` with `{ email, password, display_name }` → `{ access_token?: string, email_verification_required: boolean }`. It stores `pending_onboarding_step="bio"` and the signup page routes to `/verify-email?email=...`.
- **logout():** Clears session and redirects to `/login`.
- **useAuth():** Returns context value; throws if used outside **AuthProvider**.

---

## 6. Hooks

### `src/hooks/use-credits.ts`

- **useCredits():** Returns result of **useQuery** with `queryKey: ["credits"]` and `queryFn: () => api<{ balance: number }>("/me/credits")`. Used by **CreditsBadge** and **SearchForm** (and Settings) to show balance.

### `src/hooks/index.ts`

- Re-exports **useCredits** for clean imports.

---

## 7. Lib (API & Utils)

### `src/lib/api.ts`

- **normalizeErrorDetail(detail):** If `detail` is string, return it. If array of objects with `msg`, returns first `msg` or joins all messages. Otherwise `null`. Used to turn API error `detail` into a single message string.
- **getToken():** Returns `localStorage.getItem("token")` in browser; `null` on server.
- **api\<T\>(path, options):**  
  - Builds URL from `API_BASE + path`. Adds `Content-Type: application/json` and, if token exists, `Authorization: Bearer <token>`.  
  - Sends fetch with optional `body` (JSON.stringify).  
  - If URL doesn’t start with `http`, throws (remind to set `NEXT_PUBLIC_API_BASE_URL`).  
  - On network error, throws friendly message.  
  - If `!res.ok`, reads JSON error, uses **normalizeErrorDetail** or fallback, throws Error.  
  - If status 204, returns `undefined as T`; else `res.json()`.
- **apiWithIdempotency\<T\>(path, idempotencyKey, options):** Adds header `Idempotency-Key: idempotencyKey` and calls **api(path, { ...options, headers })**. Used for search and unlock-contact to avoid duplicate charges.

### `src/lib/utils.ts`

- **cn(...inputs):** Merges class names with `twMerge(clsx(inputs))` (Tailwind-friendly).
- **API_BASE:** `process.env.NEXT_PUBLIC_API_BASE_URL` trimmed, or `"http://localhost:8000"` when hostname is `localhost` in browser; else `""`.

---

## 8. Types

### `src/types/index.ts`

- **PersonSearchResult:** `id`, `display_name`, `open_to_work`, `open_to_contact`.
- **SearchResponse:** `search_id`, `people: PersonSearchResult[]`.
- **ExperienceCard:** id, person_id, raw_experience_id, status, human_edited, locked, title, context, constraints, decisions, outcome, tags, company, team, role_title, time_range, created_at, updated_at.
- **ContactDetails:** email_visible, phone, linkedin_url, other.
- **PersonProfile:** id, display_name, open_to_work, open_to_contact, work_preferred_*, experience_cards, contact.
- **CardFamilyV1Response:** parent (ExperienceCardV1), children (ExperienceCardV1[]).
- **DraftSetV1Response:** draft_set_id, raw_experience_id, card_families: CardFamilyV1Response[].
- **BioResponse:** first_name, last_name, date_of_birth, current_city, profile_photo_url, school, college, current_company, past_companies, email, linkedin_url, phone, complete.

---

## 9. Components

### Layout & shared

- **Providers** (`providers.tsx`): Wraps children in **QueryClientProvider** with a **QueryClient** that has `defaultOptions.queries.staleTime: 60_000`.
- **AuthLayout** (`auth-layout.tsx`): Full-screen centered layout with **HeroBg**, **DepthGrid**, and motion wrapper; accepts `title`, `subtitle`, `children`.
- **LoadingScreen** (`loading-screen.tsx`): Full-screen centered div with optional `message` (default “Loading…”), `animate-pulse`.
- **ErrorMessage** (`error-message.tsx`): Renders `message` in a destructive-styled box (`text-destructive`, `bg-destructive/10`).

### AppNav — `src/components/app-nav.tsx`

- **Purpose:** Sticky top nav: logo “Discover”, main links (Discover, Profile, Experience), **CreditsBadge**, user dropdown (Edit Bio, Settings, Log out).
- **State:** `dropdownOpen`; `dropdownRef` for click-outside.
- **useEffect:** Listens `mousedown`; if click outside `dropdownRef`, sets `dropdownOpen` to false.
- **primaryNav / menuItems:** Link configs with href, label, icon. Active state by **pathname**.
- **Functions:** No named handlers beyond `setDropdownOpen` and `logout` in dropdown.

### CreditsBadge — `src/components/credits-badge.tsx`

- **Purpose:** Shows current credit balance. Uses **useCredits()** and displays `credits?.balance ?? "—"` with Coins icon and “credits” label.

### HeroBg & DepthGrid — `src/components/hero-bg.tsx`

- **HeroBg():** Absolute full-size layer with class `mesh-bg` and two blurred radial-gradient “orbs” (CSS only) for depth. Used on login, signup, and top of Discover.
- **DepthGrid():** Full-size grid overlay (opacity 0.03) for subtle depth on auth pages.

### Search — `src/components/search/`

- **SearchForm** (`search-form.tsx`):  
  - Props: `query`, `setQuery`, `openToWorkOnly`, `setOpenToWorkOnly`, `error`, `onSuccess`, `onError`.  
  - **searchMutation:** POST `/search` via **apiWithIdempotency** with body `{ query, open_to_work_only }`; on success calls `onSuccess(data)`, on error `onError(e.message)`.  
  - **handleSearch(e):** preventDefault; if `query.trim()` empty return; else `searchMutation.mutate(query.trim())`.  
  - Renders input, “Open to work only” checkbox, submit button, credit hint and balance from **useCredits()**.

- **SearchResults** (`search-results.tsx`):  
  - Props: `searchId`, `people`.  
  - If `searchId` is set, shows “Results” and either list of **PersonResultCard** or “No matches” message. Uses **AnimatePresence** and **motion.div** for enter/exit.

- **PersonResultCard** (`person-result-card.tsx`):  
  - Props: `person`, `searchId`, `index`.  
  - Renders a **Link** to `/people/[id]?search_id=...` with person name, “Open to work” / “Open to contact” badges, and “View profile →”. **motion.li** with stagger delay by `index`.

### UI primitives — `src/components/ui/`

- **Button:** **cva** (class-variance-authority) for variants: default, destructive, outline, secondary, ghost, link; sizes: default, sm, lg, icon. Forwards ref and spreads props; uses **cn** for className.
- **Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter:** Simple divs/p with consistent padding and typography; **cn** for className.
- **Input:** Forwarded `<input>` with Tailwind styles (border, ring, placeholder, disabled).
- **Label:** Forwarded `<label>` with `text-sm font-medium`, peer-disabled styles.
- **Textarea:** Forwarded `<textarea>` with same ring/placeholder/disabled pattern and min-height.

---

## 10. Styling

### `src/app/globals.css`

- **@layer base:**  
  - **:root** — Light theme CSS variables (background, foreground, card, primary, secondary, muted, accent, destructive, border, input, ring, radius, glow, mesh-1/2/3).  
  - **.dark** — Same set for dark theme (used by default on `<html>`).
- **body:** `bg-background text-foreground antialiased`.
- **.perspective-card / .perspective-card-inner:** 3D perspective for cards.
- **.hover-lift:** On hover, translateY and translateZ and stronger shadow.
- **.mesh-bg:** Radial gradients using `--mesh-1`, `--mesh-2`, `--mesh-3` for background.
- **.glass:** Semi-transparent card with backdrop blur and border.
- **.glow-ring:** Border + soft glow using `--glow`.
- **html:** `scroll-behavior: smooth`.

---

## Quick reference: data flow

1. **Auth:** Token in `localStorage` + AuthContext. Login sets token and redirects to `/home`. Signup does not create a session immediately; it marks pending onboarding and routes to `/verify-email`, then login starts the session.
2. **Search:** Home page → SearchForm POST `/search` (idempotent) → SearchResponse → SearchResults + PersonResultCard links to `/people/[id]?search_id=...`.
3. **Profile:** GET `/me/bio` and `/me/experience-cards`; profile page shows them; builder and onboarding/bio mutate and invalidate these.
4. **Builder:** POST `/experience-cards/detect-experiences` then POST `/experience-cards/draft-v1-single` → one card family (parent + children); approve via POST `/experience-cards/:id/approve`; hide via POST on card id.
5. **Person profile:** GET `/people/:id?search_id=...`; unlock contact via POST with idempotency key; balance from `/me/credits`.

All API calls use **lib/api.ts** with Bearer token and **API_BASE** from **lib/utils.ts**.
