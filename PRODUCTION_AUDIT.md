# Production Audit (Search_Engine / CONXA)

Scanned on **2026-02-21** (local workspace `c:\Users\Lenovo\Desktop\Search_Engine`).

This document lists issues that are **not production-ready** (security, reliability, deploy correctness) and what to do about them.

## Executive Summary

**Critical**: `apps/api/.env` contains real, live-looking secrets (LLM keys, SendGrid key, DB URL with password).  
**Critical**: Render API service builds with `dockerContext: ./apps/api` but there is **no** `apps/api/.dockerignore`, so `.env` is sent as build context.  
**High**: API CORS defaults to `"*"` while `allow_credentials=True` in middleware.  
**High**: Web stores JWT access token in `localStorage` (XSS = account takeover risk).

## Critical (fix before any production exposure)

### 1) Secrets present in `apps/api/.env`

- **Where**: `apps/api/.env`
- **Why it’s bad**: this file contains credentials (API keys, SendGrid key, and a Postgres URL with username/password). If this repo/workspace is shared, backed up, or accidentally committed, these secrets are compromised.
- **What to do**
  - **Rotate/revoke** all secrets found in `apps/api/.env` (Groq/LLM key, embedding key, Sarvam key, SendGrid key, DB password, JWT secret).
  - Delete `apps/api/.env` locally (keep only `apps/api/.env.example`) and use environment variables instead.
  - If this file was ever committed (even once), scrub git history (e.g. `git filter-repo`) and rotate again.

### 2) `.env` leaks into Render Docker build context for the API service

- **Where**: `render.yaml` uses `dockerContext: ./apps/api` for `conxa-api`; there is **no** `apps/api/.dockerignore`.
- **Why it’s bad**: Docker sends the entire build context to the builder. Even if your `Dockerfile` doesn’t `COPY .env`, it is still transmitted/stored as part of the context.
- **What to do**
  - Add `apps/api/.dockerignore` at minimum containing:
    - `.env`
    - `.env.*`
    - `__pycache__/`, `.venv/`, `venv/`
    - `*.log`
  - Consider also excluding `docs/` and other non-runtime files from the API image build context.

## High (strongly recommended before production)

### 3) CORS is effectively “allow all origins”

- **Where**
  - `apps/api/src/core/config.py` sets `cors_origins: str = "*"`
  - `apps/api/src/main.py` applies `CORSMiddleware` with `allow_credentials=True`
- **Why it’s bad**
  - In production, wildcard origins + credentials is a common security footgun.
  - Even if you don’t use cookies, “allow all origins” increases risk of unintended cross-origin access.
- **What to do**
  - Set `CORS_ORIGINS` (or whatever env var maps to `Settings.cors_origins`) to your real web origin(s), e.g. `https://conxa-web.onrender.com`.
  - If you’re only using `Authorization: Bearer ...` headers (no cookies), consider `allow_credentials=False`.

### 4) Access token stored in `localStorage`

- **Where**
  - `apps/web/src/contexts/auth-context.tsx` reads/writes the auth token via `localStorage`
  - `apps/web/src/lib/api.ts` attaches it as `Authorization: Bearer ...`
- **Why it’s bad**: any XSS bug (now or later) can read `localStorage` and steal the token. That’s typically a full account takeover.
- **What to do**
  - Prefer an `HttpOnly`, `Secure`, `SameSite` cookie session over `localStorage` for auth.
  - Add a Content Security Policy (CSP) and tighten it over time.
  - Keep JWT lifetime short and support rotation/refresh if you stay with tokens.

### 5) Rate limiting keying and proxy/IP correctness

- **Where**: `apps/api/src/core/limiter.py` uses `get_remote_address(request)` when unauthenticated.
- **Risk**: behind Render/reverse proxies, the “remote address” may not be the real client IP unless proxy headers are handled.
- **What to do**
  - Run Uvicorn with proxy header support (e.g. `--proxy-headers`) and validate the correct client IP behavior.
  - For multi-instance deployments, plan a shared store (Redis) for rate-limit state (SlowAPI defaults are not shared across instances).

## Medium (production polish / reliability)

### 6) API container runs as root

- **Where**: `apps/api/Dockerfile`
- **Why**: running as root increases blast radius if the container is compromised.
- **What to do**: create a non-root user in the image and `USER` it (similar to what your web Dockerfile already does).

### 7) Migrations run automatically on every start

- **Where**: `apps/api/Dockerfile` CMD runs `alembic upgrade head && uvicorn ...`
- **Risk**: if you scale to multiple instances, concurrent migrations can race or fail.
- **What to do**: run migrations as a separate release step/job, or ensure only one instance runs them.

### 8) Unpinned Python dependencies

- **Where**: `apps/api/pyproject.toml` uses `>=` ranges.
- **Risk**: builds can change over time (supply chain/reproducibility).
- **What to do**: add a lock (e.g. `uv lock`, `pip-tools`, or pinned versions) and use it in CI/build.

### 9) FastAPI interactive docs likely enabled in production

- **Where**: `apps/api/src/main.py` does not disable docs.
- **Risk**: exposes schema and convenient testing surface publicly.
- **What to do**: disable `/docs` and `/redoc` (or protect them) in production environments.

## Low (cleanup / maintainability)

### 10) Stray root `node_modules` file

- **Where**: `node_modules` at repo root is a **file**, not a directory.
- **Why**: can confuse tooling and automation that expects a folder.
- **What to do**: delete/rename it (and rely on `.gitignore` to ignore real `node_modules/` folders).

### 11) Build artifacts exist in the workspace

- **Where**: `apps/web/.next/` exists locally.
- **Why**: not a production issue by itself, but it’s noise; ensure it’s not committed and not shipped.
- **What to do**: keep it ignored (already covered by `.gitignore`) and consider cleaning before packaging.

## Render-specific checklist

- Ensure these env vars are set on `conxa-api` in Render (either in `render.yaml` or Dashboard):
  - `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`, `SENDGRID_FROM_NAME`
  - `EMAIL_VERIFY_URL_BASE` (must be your deployed web URL, not `https://localhost:3000/...`)
  - `CORS_ORIGINS` (web origin(s))
  - Any chat/embed provider keys you actually use (`CHAT_API_KEY`, `EMBED_API_KEY`, etc.)
- Confirm that `NEXT_PUBLIC_API_BASE_URL` on `conxa-web` points to the API’s external URL (your `render.yaml` already wires this via `RENDER_EXTERNAL_URL`).

