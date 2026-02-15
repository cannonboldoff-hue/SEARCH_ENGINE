"""Search, profile view, and contact unlock business logic.

Pipeline: parse query → embed → hybrid candidates (vector + lexical) → MUST/EXCLUDE filters
(with fallback tiers if results < MIN_RESULTS) → collapse by person with top-K blended scoring
→ penalties (missing date, location mismatch) → explainability → persist in one transaction.
"""

import asyncio
import json
import logging
import math
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, text, delete
from sqlalchemy.exc import IntegrityError

from src.core import SEARCH_RESULT_EXPIRY_HOURS
from src.db.models import (
    Person,
    PersonProfile,
    ExperienceCard,
    ExperienceCardChild,
    IdempotencyKey,
    Search,
    SearchResult,
    UnlockContact,
)
from src.schemas import (
    SearchRequest,
    SearchResponse,
    PersonSearchResult,
    PersonProfileResponse,
    PersonListItem,
    PersonListResponse,
    PersonPublicProfileResponse,
    CardFamilyResponse,
    BioResponse,
    ContactDetailsResponse,
    UnlockContactResponse,
)
from src.schemas.search import ParsedConstraintsPayload, ParsedConstraintsShould, ParsedConstraintsMust
from src.services.credits import get_balance, deduct_credits, get_idempotent_response, save_idempotent_response
from src.services.filter_validator import validate_and_normalize
from src.providers import get_chat_provider, get_embedding_provider, ChatServiceError, EmbeddingServiceError
from src.prompts.search_why_matched import get_why_matched_prompt
from src.serializers import experience_card_to_response, experience_card_child_to_response
from src.utils import normalize_embedding

logger = logging.getLogger(__name__)
SEARCH_ENDPOINT = "POST /search"


@dataclass(frozen=True)
class _FilterContext:
    """Bundle of filter parameters for MUST/EXCLUDE and optional PersonProfile join."""
    apply_company_team: bool
    company_norms: list[str]
    team_norms: list[str]
    must: ParsedConstraintsMust
    apply_location: bool
    apply_time: bool
    time_start: object
    time_end: object
    exclude_norms: list[str]
    norm_terms_exclude: list[str]
    open_to_work_only: bool
    offer_salary_inr_per_year: float | None
    body: SearchRequest


@dataclass(frozen=True)
class _SearchConstraints:
    """Precomputed MUST/EXCLUDE and query-level flags reused across fallback tiers."""
    must: ParsedConstraintsMust
    company_norms: list[str]
    team_norms: list[str]
    exclude_norms: list[str]
    norm_terms_exclude: list[str]
    time_start: object
    time_end: object
    query_has_time: bool
    query_has_location: bool


@dataclass(frozen=True)
class _CandidateFetchResult:
    """Result bundle from vector candidate fetch with fallback relaxations."""
    fallback_tier: int
    rows: list[Any]
    child_rows: list[Any]
    child_evidence_rows: list[Any]
    all_person_ids: set[str]


@dataclass
class _PendingSearchRow:
    """Pending DB row data for SearchResult, before/after why_matched generation."""
    person_id: str
    rank: int
    score: float
    matched_parent_ids: list[str]
    matched_child_ids: list[str]
    fallback_why: list[str]
    why_matched: list[str] | None = None


def unlock_endpoint(person_id: str) -> str:
    """Idempotency endpoint for unlock-contact (per target person)."""
    return f"POST /people/{person_id}/unlock-contact"


async def _reserve_idempotency_key_or_return(
    db: AsyncSession,
    key: str | None,
    person_id: str,
    endpoint: str,
) -> SearchResponse | None:
    """Reserve an idempotency key; return stored response if already completed."""
    if not key:
        return None
    if db.in_transaction():
        await db.commit()
    try:
        async with db.begin():
            db.add(
                IdempotencyKey(
                    key=key,
                    person_id=person_id,
                    endpoint=endpoint,
                    response_status=None,
                    response_body=None,
                )
            )
            await db.flush()
        return None
    except IntegrityError:
        await db.rollback()
        existing = await get_idempotent_response(db, key, person_id, endpoint)
        if existing and existing.response_body:
            return SearchResponse(**existing.response_body)
        raise HTTPException(status_code=409, detail="Request in progress")


async def _update_idempotency_response(
    db: AsyncSession,
    key: str | None,
    person_id: str,
    endpoint: str,
    response_status: int,
    response_body: dict[str, Any],
) -> None:
    """Update a pre-reserved idempotency row with final response payload."""
    if not key:
        return
    result = await db.execute(
        select(IdempotencyKey)
        .where(
            IdempotencyKey.key == key,
            IdempotencyKey.person_id == person_id,
            IdempotencyKey.endpoint == endpoint,
        )
        .with_for_update()
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = IdempotencyKey(
            key=key,
            person_id=person_id,
            endpoint=endpoint,
        )
        db.add(row)
    row.response_status = response_status
    row.response_body = response_body
    await db.flush()


async def _release_idempotency_key_on_failure(
    db: AsyncSession,
    key: str | None,
    person_id: str,
    endpoint: str,
) -> None:
    """Delete unfinished idempotency reservation so retries can proceed."""
    if not key:
        return
    await db.rollback()
    async with db.begin():
        await db.execute(
            delete(IdempotencyKey).where(
                IdempotencyKey.key == key,
                IdempotencyKey.person_id == person_id,
                IdempotencyKey.endpoint == endpoint,
                IdempotencyKey.response_body.is_(None),
            )
        )


async def _validate_search_session(
    db: AsyncSession,
    searcher_id: str,
    search_id: str,
    person_id: str | None = None,
) -> tuple[Search, SearchResult | None]:
    """Validate search exists, belongs to searcher, not expired. If person_id given, also require person in results. Returns (search_rec, search_result or None)."""
    s_result = await db.execute(
        select(Search).where(
            Search.id == search_id,
            Search.searcher_id == searcher_id,
        )
    )
    search_rec = s_result.scalar_one_or_none()
    if not search_rec:
        raise HTTPException(status_code=403, detail="Invalid search_id")
    if _search_expired(search_rec):
        raise HTTPException(status_code=403, detail="Search expired")
    if person_id is None:
        return search_rec, None
    r_result = await db.execute(
        select(SearchResult).where(
            SearchResult.search_id == search_id,
            SearchResult.person_id == person_id,
        )
    )
    if not r_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Person not in this search result")
    return search_rec, None


def _search_expired(search_rec: Search) -> bool:
    now = datetime.now(timezone.utc)
    if getattr(search_rec, "expires_at", None):
        return search_rec.expires_at < now
    cutoff = now - timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS)
    return not search_rec.created_at or search_rec.created_at < cutoff


OVERFETCH_CARDS = 50
TOP_PEOPLE = 5
MATCHED_CARDS_PER_PERSON = 3
# Minimum unique persons to avoid fallback; if below, relax MUST in order: time → location → company/team
MIN_RESULTS = 15
# Top-K cards per person (parents + children) for blended collapse score
TOP_K_CARDS = 5
# Equal-score bucket threshold for tie-aware reordering
SCORE_EPSILON_ABS = 1e-6
# Optional fuzzy location match threshold used in in-memory location checks
LOCATION_FUZZY_THRESHOLD = 0.85
ACCENT_FOLD_FROM = "áàâäãåéèêëíìîïóòôöõúùûüñçÁÀÂÄÃÅÉÈÊËÍÌÎÏÓÒÔÖÕÚÙÛÜÑÇ"
ACCENT_FOLD_TO = "aaaaaaeeeeiiiiooooouuuuncAAAAAAEEEEIIIIOOOOOUUUUNC"
# Similarity from cosine distance: sim = 1 / (1 + distance); robust for small distances
def _safe_distance(value: object, default: float = 1.0) -> float:
    """Coerce distance into a finite non-negative float for stable scoring."""
    if value is None:
        return default
    try:
        d = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(d):
        return default
    return max(0.0, d)


def _similarity_from_distance(d: object) -> float:
    safe_d = _safe_distance(d, default=1.0)
    sim = 1.0 / (1.0 + safe_d)
    return sim if math.isfinite(sim) else 0.0

# Collapse scoring weights (tunable): parent_best, child_best, avg of top-3 card scores
WEIGHT_PARENT_BEST = 0.65
WEIGHT_CHILD_BEST = 0.25
WEIGHT_AVG_TOP3 = 0.10
# Bonuses and penalties (capped)
LEXICAL_BONUS_MAX = 0.25
SHOULD_BOOST = 0.02
SHOULD_CAP = 10
SHOULD_BONUS_MAX = 0.25
MISSING_DATE_PENALTY = 0.12  # when query has time window and card has no dates
LOCATION_MISMATCH_PENALTY = 0.10  # when query specifies location and card differs
# Fallback tier stored in Search.extra: 0=strict, 1=time soft, 2=location soft, 3=company/team soft
FALLBACK_TIER_STRICT = 0
FALLBACK_TIER_TIME_SOFT = 1
FALLBACK_TIER_LOCATION_SOFT = 2
FALLBACK_TIER_COMPANY_TEAM_SOFT = 3


def _parse_date(s: str | None):
    """Parse YYYY-MM-DD or YYYY-MM to date; return None if invalid or missing."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _card_dates_overlap_query(
    card_start: object, card_end: object, query_start: object, query_end: object
) -> bool:
    """True when card interval overlaps query interval with open-ended bounds allowed."""
    if card_start is None and card_end is None:
        return False
    if query_start is not None and card_end is not None and card_end < query_start:
        return False
    if query_end is not None and card_start is not None and card_start > query_end:
        return False
    return True


def _text_contains_any(haystack: str, terms: list[str]) -> bool:
    """True if any term (lower) appears in haystack (lower)."""
    if not terms or not (haystack or "").strip():
        return False
    h = haystack.lower()
    return any((t or "").strip().lower() in h for t in terms if (t or "").strip())


def _normalize_for_match(value: object) -> str:
    """Lowercase + accent-strip + whitespace normalize for fuzzy matching."""
    if value is None:
        return ""
    txt = " ".join(str(value).split()).strip().lower()
    if not txt:
        return ""
    return "".join(ch for ch in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(ch))


def _location_term_variants(*values: object) -> list[str]:
    """
    Build deduped location terms:
    - original stripped tokens for DB substring lookup
    - accent-folded variants to improve cross-accent matching
    """
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        raw = " ".join(str(value).split()).strip()
        if not raw:
            continue
        folded = _normalize_for_match(raw)
        for candidate in (raw, folded):
            if not candidate:
                continue
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(candidate)
    return out


def _location_fold_sql(expr):
    """SQL-side accent/case fold for location text (no extension required)."""
    return func.translate(func.lower(func.coalesce(expr, "")), ACCENT_FOLD_FROM, ACCENT_FOLD_TO)


def _location_text_matches(query_terms: list[str], candidate_text: str | None) -> bool:
    """
    Accent-insensitive location check with optional fuzzy fallback.
    Intended for in-memory rerank penalties, not heavy SQL filtering.
    """
    if not query_terms:
        return False
    candidate_norm = _normalize_for_match(candidate_text)
    if not candidate_norm:
        return False
    for term in query_terms:
        term_norm = _normalize_for_match(term)
        if not term_norm:
            continue
        if term_norm in candidate_norm:
            return True
        if SequenceMatcher(None, term_norm, candidate_norm).ratio() >= LOCATION_FUZZY_THRESHOLD:
            return True
    return False


def _chat_error_kind(err: Exception) -> str:
    """Classify chat failures for structured logging/metrics."""
    msg = str(err).lower()
    if "timeout" in msg or "connection error" in msg or "service unavailable" in msg:
        return "timeout_or_network"
    if "invalid json" in msg:
        return "invalid_json"
    if "rate limit" in msg or "rate limited" in msg:
        return "rate_limited"
    return "provider_or_other"


def _emit_metric_counter(name: str, **tags: object) -> None:
    """
    Lightweight metric hook.
    Current implementation emits structured logs; wire this to a metrics backend when available.
    """
    tag_str = " ".join(f"{k}={v}" for k, v in sorted(tags.items()))
    logger.info("metric=%s %s", name, tag_str)


def _reorder_within_equal_score_groups(
    ranked: list[tuple[str, float]],
    secondary_key: Any,
) -> list[tuple[str, float]]:
    """
    Reorder only near-equal score groups using an absolute epsilon.
    Keeps global score ordering intact while allowing deterministic tie-breakers.
    """
    if not ranked:
        return ranked
    out: list[tuple[str, float]] = []
    current_group: list[tuple[str, float]] = [ranked[0]]
    group_anchor_score = ranked[0][1]

    for item in ranked[1:]:
        score = item[1]
        if abs(score - group_anchor_score) <= SCORE_EPSILON_ABS:
            current_group.append(item)
            continue
        out.extend(sorted(current_group, key=secondary_key))
        current_group = [item]
        group_anchor_score = score

    out.extend(sorted(current_group, key=secondary_key))
    return out


def _should_bonus(card: ExperienceCard, should: ParsedConstraintsShould) -> int:
    """Count how many should-constraints this card matches (for rerank boost). Matches in search_phrases and search_document."""
    phrases = (card.search_phrases or []) if hasattr(card, "search_phrases") else []
    doc_text = (getattr(card, "search_document", None) or "") or ""
    hits = _should_bonus_from_phrases(phrases, doc_text, should)
    if should.intent_secondary and getattr(card, "intent_secondary", None):
        if any(i in (card.intent_secondary or []) for i in should.intent_secondary):
            hits += 1
    return hits


def _should_bonus_from_phrases(phrases: list, doc_text: str, should: ParsedConstraintsShould) -> int:
    """Count should-hits from search_phrases and search_document (works for parent or child)."""
    hits = 0
    phrases_lower = [p.lower() for p in (phrases or []) if p]
    doc_text = (doc_text or "") or ""
    skills_or_tools = [t.strip().lower() for t in (should.skills_or_tools or []) if (t or "").strip()]
    if skills_or_tools and (any(any(t in p for p in phrases_lower) for t in skills_or_tools) or _text_contains_any(doc_text, skills_or_tools)):
        hits += 1
    keywords = [t.strip().lower() for t in (should.keywords or []) if (t or "").strip()]
    if keywords and (any(any(t in p for p in phrases_lower) for t in keywords) or _text_contains_any(doc_text, keywords)):
        hits += 1
    return hits


def _card_families_from_parents_and_children(
    parents: list[ExperienceCard],
    children_list: list[ExperienceCardChild],
) -> list[CardFamilyResponse]:
    """Build CardFamilyResponse list from parent cards and their children (grouped by parent_experience_id)."""
    by_parent: dict[str, list[ExperienceCardChild]] = defaultdict(list)
    for ch in children_list:
        by_parent[str(ch.parent_experience_id)].append(ch)
    return [
        CardFamilyResponse(
            parent=experience_card_to_response(card),
            children=[experience_card_child_to_response(ch) for ch in by_parent.get(str(card.id), [])],
        )
        for card in parents
    ]


def _build_why_matched_bullets(
    parent_cards_with_sim: list[tuple[Any, float]],
    child_evidence: list[tuple[Any, str, float]],
    max_bullets: int = 6,
) -> list[str]:
    """Build 3–6 evidence bullets from search_phrases and snippets of search_document."""
    bullets: list[str] = []
    seen: set[str] = set()

    def add_from_phrases(phrases: list | None, doc: str | None, prefix: str = ""):
        for p in (phrases or [])[:3]:
            if p and p.strip() and p.strip() not in seen:
                seen.add(p.strip())
                bullets.append((prefix + p.strip())[:120])
                if len(bullets) >= max_bullets:
                    return
        if doc and len(bullets) < max_bullets:
            snippet = (doc or "").strip()[:100]
            if snippet and snippet not in seen:
                seen.add(snippet)
                bullets.append((prefix + snippet).strip()[:120])

    for card, _ in (parent_cards_with_sim or [])[:2]:
        phrases = getattr(card, "search_phrases", None) or []
        doc = getattr(card, "search_document", None) or ""
        add_from_phrases(phrases, doc)
    for child_row, _parent_id, _ in (child_evidence or [])[:2]:
        phrases = getattr(child_row, "search_phrases", None) or []
        doc = getattr(child_row, "search_document", None) or ""
        add_from_phrases(phrases, doc)
    return bullets[:max_bullets]


def _strip_json_from_response(raw: str) -> str:
    """Strip markdown/code fences from an LLM response and return JSON text."""
    s = (raw or "").strip()
    if "```" not in s:
        return s
    for part in s.split("```"):
        p = part.strip()
        if p.lower().startswith("json"):
            p = p[4:].strip()
        if p.startswith("{"):
            return p
    return s


def _compact_text(value: Any, max_len: int = 180) -> str | None:
    """Normalize whitespace and trim text for prompt payloads."""
    if value is None:
        return None
    txt = " ".join(str(value).split()).strip()
    if not txt:
        return None
    return txt[:max_len]


def _build_person_why_evidence(
    person_id: str,
    profile: PersonProfile | None,
    parent_cards_with_sim: list[tuple[Any, float]],
    child_evidence: list[tuple[Any, str, float]],
) -> dict[str, Any]:
    """Build compact person-level evidence payload for LLM explanation."""
    parent_cards: list[dict[str, Any]] = []
    for card, sim in (parent_cards_with_sim or [])[:2]:
        parent_cards.append({
            "title": _compact_text(getattr(card, "title", None), 120),
            "company_name": _compact_text(getattr(card, "company_name", None), 90),
            "location": _compact_text(getattr(card, "location", None), 80),
            "summary": _compact_text(getattr(card, "summary", None), 200),
            "search_phrases": [
                _compact_text(p, 80)
                for p in (getattr(card, "search_phrases", None) or [])[:5]
                if _compact_text(p, 80)
            ],
            "similarity": round(float(sim), 4),
            "start_date": str(getattr(card, "start_date", None)) if getattr(card, "start_date", None) is not None else None,
            "end_date": str(getattr(card, "end_date", None)) if getattr(card, "end_date", None) is not None else None,
        })

    child_cards: list[dict[str, Any]] = []
    for child, _parent_id, sim in (child_evidence or [])[:2]:
        child_cards.append({
            "title": _compact_text(getattr(child, "title", None), 120),
            "headline": _compact_text(getattr(child, "headline", None), 160),
            "summary": _compact_text(getattr(child, "summary", None), 180),
            "context": _compact_text(getattr(child, "context", None), 180),
            "tags": [
                _compact_text(t, 50)
                for t in (getattr(child, "tags", None) or [])[:6]
                if _compact_text(t, 50)
            ],
            "search_phrases": [
                _compact_text(p, 80)
                for p in (getattr(child, "search_phrases", None) or [])[:5]
                if _compact_text(p, 80)
            ],
            "similarity": round(float(sim), 4),
        })

    return {
        "person_id": person_id,
        "open_to_work": bool(profile.open_to_work) if profile else False,
        "open_to_contact": bool(profile.open_to_contact) if profile else False,
        "matched_parent_cards": parent_cards,
        "matched_child_cards": child_cards,
    }


def _sanitize_why_matched_lines(raw_lines: Any, max_items: int = 3) -> list[str]:
    """Normalize and bound LLM reason lines."""
    if not isinstance(raw_lines, (list, tuple)):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for line in raw_lines:
        txt = _compact_text(line, 120)
        if not txt:
            continue
        key = txt.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(txt)
        if len(out) >= max_items:
            break
    return out


async def _generate_llm_why_matched(
    chat: Any,
    payload: ParsedConstraintsPayload,
    people_evidence: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Generate person-level why_matched lines from LLM in one batched call."""
    if not people_evidence:
        return {}
    prompt = get_why_matched_prompt(
        query_original=payload.query_original,
        query_cleaned=payload.query_cleaned,
        must=payload.must.model_dump(mode="json"),
        should=payload.should.model_dump(mode="json"),
        people_evidence=people_evidence,
    )
    try:
        raw = await chat.chat(prompt, max_tokens=1200, temperature=0.1)
    except ChatServiceError as e:
        err_kind = _chat_error_kind(e)
        logger.warning(
            "why_matched LLM call failed (%s), using deterministic fallback: %s",
            err_kind,
            e,
        )
        _emit_metric_counter(
            "search.llm.why.timeout_or_http_error",
            endpoint=SEARCH_ENDPOINT,
            fallback_used=True,
            error_kind=err_kind,
        )
        return {}
    try:
        parsed = json.loads(_strip_json_from_response(raw))
    except (TypeError, ValueError, json.JSONDecodeError) as e:
        logger.warning("why_matched LLM JSON parse failed, using deterministic fallback: %s", e)
        _emit_metric_counter(
            "search.llm.why.invalid_json",
            endpoint=SEARCH_ENDPOINT,
            fallback_used=True,
        )
        return {}

    people = parsed.get("people")
    if not isinstance(people, list):
        logger.warning("why_matched LLM returned non-list people payload; using deterministic fallback")
        _emit_metric_counter(
            "search.llm.why.invalid_json",
            endpoint=SEARCH_ENDPOINT,
            fallback_used=True,
            error_kind="invalid_schema",
        )
        return {}
    out: dict[str, list[str]] = {}
    for item in people:
        if not isinstance(item, dict):
            continue
        person_id = str(item.get("person_id") or "").strip()
        if not person_id:
            continue
        lines = _sanitize_why_matched_lines(item.get("why_matched"))
        if lines:
            out[person_id] = lines
        else:
            logger.info(
                "why_matched sanitization produced no usable lines for person_id=%s; using deterministic fallback",
                person_id,
            )
            _emit_metric_counter(
                "search.llm.why.sanitized_empty_person",
                endpoint=SEARCH_ENDPOINT,
                person_id=person_id,
                fallback_used=True,
            )
    return out


async def _lexical_candidates(
    db: AsyncSession,
    query_ts: str,
    limit_per_table: int = 100,
) -> dict[str, float]:
    """
    Full-text search on experience_cards and experience_card_children.search_document.
    Returns person_id -> lexical score in [0, 1]; caller caps to LEXICAL_BONUS_MAX.
    Uses plainto_tsquery for safety; empty query_ts returns {}.
    """
    query_ts = (query_ts or "").strip()
    if not query_ts:
        return {}
    # Avoid SQL injection: use bound param for tsquery; Postgres plainto_tsquery('english', :q)
    person_scores: dict[str, float] = defaultdict(float)
    try:
        # Parents: person_id, rank
        stmt_parents = text("""
            SELECT ec.person_id, ts_rank_cd(to_tsvector('english', COALESCE(ec.search_document, '')), plainto_tsquery('english', :q)) AS r
            FROM experience_cards ec
            WHERE ec.experience_card_visibility = true
              AND to_tsvector('english', COALESCE(ec.search_document, '')) @@ plainto_tsquery('english', :q)
            ORDER BY r DESC
            LIMIT :lim
        """)
        rp = await db.execute(stmt_parents, {"q": query_ts, "lim": limit_per_table})
        for row in rp.all():
            pid = str(row.person_id)
            person_scores[pid] = max(person_scores[pid], float(row.r or 0))
        # Children: person_id, rank
        stmt_children = text("""
            SELECT ecc.person_id, ts_rank_cd(to_tsvector('english', COALESCE(ecc.search_document, '')), plainto_tsquery('english', :q)) AS r
            FROM experience_card_children ecc
            JOIN experience_cards ec ON ec.id = ecc.parent_experience_id AND ec.experience_card_visibility = true
            WHERE to_tsvector('english', COALESCE(ecc.search_document, '')) @@ plainto_tsquery('english', :q)
            ORDER BY r DESC
            LIMIT :lim
        """)
        rc = await db.execute(stmt_children, {"q": query_ts, "lim": limit_per_table})
        for row in rc.all():
            pid = str(row.person_id)
            person_scores[pid] = max(person_scores[pid], float(row.r or 0))
    except Exception as e:
        logger.warning("Lexical search failed, continuing without lexical bonus: %s", e)
        return {}
    # Normalize: ts_rank_cd can be small; map to 0..1 then cap to LEXICAL_BONUS_MAX for bonus
    if not person_scores:
        return {}
    max_r = max(person_scores.values())
    if max_r <= 0:
        return {}
    return {pid: min(LEXICAL_BONUS_MAX, (s / max_r) * LEXICAL_BONUS_MAX) for pid, s in person_scores.items()}


def _apply_card_filters(stmt, ctx: _FilterContext):
    """Apply MUST/EXCLUDE filters and optional PersonProfile join to a statement with ExperienceCard in scope."""
    if ctx.apply_company_team and ctx.company_norms:
        stmt = stmt.where(ExperienceCard.company_norm.in_(ctx.company_norms))
    if ctx.apply_company_team and ctx.team_norms:
        stmt = stmt.where(ExperienceCard.team_norm.in_(ctx.team_norms))
    if ctx.must.intent_primary:
        stmt = stmt.where(ExperienceCard.intent_primary.in_(ctx.must.intent_primary))
    if ctx.must.domain:
        stmt = stmt.where(ExperienceCard.domain.in_(ctx.must.domain))
    if ctx.must.sub_domain:
        stmt = stmt.where(ExperienceCard.sub_domain.in_(ctx.must.sub_domain))
    if ctx.must.employment_type:
        stmt = stmt.where(ExperienceCard.employment_type.in_(ctx.must.employment_type))
    if ctx.must.seniority_level:
        stmt = stmt.where(ExperienceCard.seniority_level.in_(ctx.must.seniority_level))
    if ctx.apply_location and (ctx.must.city or ctx.must.country or ctx.must.location_text):
        loc_terms = _location_term_variants(ctx.must.city, ctx.must.country, ctx.must.location_text)
        loc_norm_terms: list[str] = []
        loc_seen: set[str] = set()
        for t in loc_terms:
            norm = _normalize_for_match(t)
            if not norm or norm in loc_seen:
                continue
            loc_seen.add(norm)
            loc_norm_terms.append(norm)
        loc_conds = [
            _location_fold_sql(ExperienceCard.location).like(f"%{norm}%")
            for norm in loc_norm_terms
        ]
        if loc_conds:
            stmt = stmt.where(or_(*loc_conds))
    if ctx.apply_time and (ctx.time_start is not None or ctx.time_end is not None):
        # Tier 0: require at least one card date bound and interval overlap with query bounds.
        at_least_one_bound = or_(
            ExperienceCard.start_date.isnot(None),
            ExperienceCard.end_date.isnot(None),
        )
        overlap_clauses = []
        if ctx.time_end is not None:
            overlap_clauses.append(
                or_(ExperienceCard.start_date.is_(None), ExperienceCard.start_date <= ctx.time_end)
            )
        if ctx.time_start is not None:
            overlap_clauses.append(
                or_(ExperienceCard.end_date.is_(None), ExperienceCard.end_date >= ctx.time_start)
            )
        stmt = stmt.where(at_least_one_bound)
        if overlap_clauses:
            stmt = stmt.where(and_(*overlap_clauses))
    if ctx.must.is_current is not None:
        stmt = stmt.where(ExperienceCard.is_current == ctx.must.is_current)
    if ctx.exclude_norms:
        stmt = stmt.where(~ExperienceCard.company_norm.in_(ctx.exclude_norms))
    if ctx.norm_terms_exclude:
        stmt = stmt.where(~ExperienceCard.search_phrases.overlap(ctx.norm_terms_exclude))
    if ctx.open_to_work_only or ctx.offer_salary_inr_per_year is not None:
        join_conds = [ExperienceCard.person_id == PersonProfile.person_id]
        if ctx.open_to_work_only:
            join_conds.append(PersonProfile.open_to_work == True)
        stmt = stmt.join(PersonProfile, and_(*join_conds))
        if ctx.open_to_work_only and ctx.body.preferred_locations:
            loc_arr = _location_term_variants(*ctx.body.preferred_locations)
            if loc_arr:
                stmt = stmt.where(PersonProfile.work_preferred_locations.overlap(loc_arr))
        if ctx.offer_salary_inr_per_year is not None:
            stmt = stmt.where(
                or_(
                    PersonProfile.work_preferred_salary_min.is_(None),
                    PersonProfile.work_preferred_salary_min <= ctx.offer_salary_inr_per_year,
                )
            )
    return stmt


async def _create_empty_search_response(
    db: AsyncSession,
    searcher_id: str,
    body: SearchRequest,
    filters_dict: dict,
    idempotency_key: str | None,
    *,
    fallback_tier: int | None = None,
) -> SearchResponse:
    """Create Search record and return empty SearchResponse without charging credits."""
    if db.in_transaction():
        await db.commit()
    async with db.begin():
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS)
        search_rec = Search(
            searcher_id=searcher_id,
            query_text=body.query,
            parsed_constraints_json=filters_dict,
            filters=filters_dict,
            extra={"fallback_tier": fallback_tier} if fallback_tier is not None else None,
            expires_at=expires_at,
        )
        db.add(search_rec)
        await db.flush()
        resp = SearchResponse(search_id=search_rec.id, people=[])
        await _update_idempotency_response(
            db,
            idempotency_key,
            searcher_id,
            SEARCH_ENDPOINT,
            200,
            resp.model_dump(mode="json"),
        )
        return resp


def _build_search_people_list(
    top_20: list[tuple[str, float]],
    people_map: dict[str, Person],
    vis_map: dict[str, PersonProfile],
    person_cards: dict[str, list[tuple[ExperienceCard, float]]],
    child_only_cards: dict[str, list[ExperienceCard]],
    similarity_by_person: dict[str, int],
    why_matched_by_person: dict[str, list[str]],
) -> list[PersonSearchResult]:
    """Build PersonSearchResult list for search response from top-ranked persons and their best cards."""
    people_list = []
    for pid, _score in top_20:
        person = people_map.get(pid)
        vis = vis_map.get(pid)
        card_list = person_cards.get(pid, [])
        card_list.sort(key=lambda x: -x[1])
        best_cards = [c for c, _ in card_list[:MATCHED_CARDS_PER_PERSON]]
        if not best_cards and pid in child_only_cards:
            best_cards = child_only_cards[pid][:MATCHED_CARDS_PER_PERSON]
        headline = None
        if vis and (vis.current_company or vis.current_city):
            headline = " / ".join(x for x in (vis.current_company, vis.current_city) if x)
        bio_parts = []
        if vis:
            if vis.first_name or vis.last_name:
                bio_parts.append(" ".join(x for x in (vis.first_name, vis.last_name) if x))
            if vis.school:
                bio_parts.append(f"School: {vis.school}")
            if vis.college:
                bio_parts.append(f"College: {vis.college}")
        bio = " · ".join(bio_parts) if bio_parts else None
        people_list.append(
            PersonSearchResult(
                id=pid,
                name=person.display_name if person else None,
                headline=headline,
                bio=bio,
                similarity_percent=similarity_by_person.get(pid),
                why_matched=why_matched_by_person.get(pid, []),
                open_to_work=vis.open_to_work if vis else False,
                open_to_contact=vis.open_to_contact if vis else False,
                work_preferred_locations=vis.work_preferred_locations or [] if vis else [],
                work_preferred_salary_min=vis.work_preferred_salary_min if vis else None,
                matched_cards=[experience_card_to_response(c) for c in best_cards],
            )
        )
    return people_list


def _score_to_similarity_percent(semantic_similarity: float) -> int:
    """Convert semantic similarity to UI-friendly percentage."""
    try:
        s = float(semantic_similarity)
    except (TypeError, ValueError):
        s = 0.0
    if not math.isfinite(s):
        s = 0.0
    normalized = max(0.0, min(1.0, s))
    return int(round(normalized * 100))


def _semantic_similarity_by_person(rows: list, child_rows: list) -> dict[str, float]:
    """Best pure vector similarity per person (no boosts/penalties)."""
    parent_best: dict[str, float] = {}
    for row in rows:
        card = row[0]
        dist = _safe_distance(row[1], default=1.0)
        pid = str(card.person_id)
        parent_best[pid] = max(parent_best.get(pid, 0.0), _similarity_from_distance(dist))

    child_best: dict[str, float] = {}
    for row in child_rows:
        pid = str(row.person_id)
        dist = _safe_distance(row.dist, default=1.0)
        child_best[pid] = max(child_best.get(pid, 0.0), _similarity_from_distance(dist))

    return {
        pid: max(parent_best.get(pid, 0.0), child_best.get(pid, 0.0))
        for pid in (set(parent_best) | set(child_best))
    }


def _collapse_and_rank_persons(
    rows: list,
    child_rows: list,
    child_evidence_rows: list,
    payload: ParsedConstraintsPayload,
    lexical_scores: dict[str, float],
    fallback_tier: int,
    query_has_time: bool,
    query_has_location: bool,
    must: ParsedConstraintsMust,
) -> tuple[
    dict[str, list[tuple[ExperienceCard, float]]],
    dict[str, float],
    dict[str, list[tuple[str, str, float]]],
    dict[str, list[str]],
    list[tuple[str, float]],
]:
    """Build person_cards, child scores, child_best_parent_ids, and sorted person_best (pid, score) from vector + lexical results."""
    child_best_parent_ids: dict[str, list[str]] = {}
    for row in child_evidence_rows:
        pid = str(row.person_id)
        parent_id = str(row.parent_experience_id)
        if pid not in child_best_parent_ids:
            child_best_parent_ids[pid] = []
        if parent_id not in child_best_parent_ids[pid] and len(child_best_parent_ids[pid]) < MATCHED_CARDS_PER_PERSON:
            child_best_parent_ids[pid].append(parent_id)

    person_cards: dict[str, list[tuple[ExperienceCard, float]]] = defaultdict(list)
    for row in rows:
        card = row[0]
        dist = _safe_distance(row[1], default=1.0)
        sim = _similarity_from_distance(dist)
        bonus = min(_should_bonus(card, payload.should), SHOULD_CAP) * SHOULD_BOOST
        person_cards[str(card.person_id)].append((card, sim + bonus))

    child_best_sim: dict[str, float] = {}
    for row in child_rows:
        pid = str(row.person_id)
        dist = _safe_distance(row.dist, default=1.0)
        child_best_sim[pid] = max(child_best_sim.get(pid, 0.0), _similarity_from_distance(dist))

    child_sims_by_person: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
    for row in child_evidence_rows:
        pid = str(row.person_id)
        parent_id = str(row.parent_experience_id)
        child_id = str(row.child_id)
        dist = _safe_distance(row.dist, default=1.0)
        child_sims_by_person[pid].append((parent_id, child_id, _similarity_from_distance(dist)))
    for pid, sim in child_best_sim.items():
        if pid not in child_sims_by_person:
            child_sims_by_person[pid].append(("", "", sim))

    person_best: list[tuple[str, float]] = []
    for pid in set(person_cards.keys()) | set(child_best_sim.keys()):
        parent_list = person_cards.get(pid, [])
        child_list = child_sims_by_person.get(pid, [])
        all_sims: list[float] = [s for _, s in parent_list]
        for _pid, _cid, s in child_list:
            all_sims.append(s)
        all_sims.sort(reverse=True)
        top_k = all_sims[:TOP_K_CARDS]
        parent_best = max((s for c, s in parent_list), default=0.0)
        child_best = max((s for _, _, s in child_list), default=0.0) if child_list else child_best_sim.get(pid, 0.0)
        avg_top3 = sum(top_k[:3]) / 3.0 if len(top_k) >= 3 else (sum(top_k) / len(top_k) if top_k else 0.0)
        base = WEIGHT_PARENT_BEST * parent_best + WEIGHT_CHILD_BEST * child_best + WEIGHT_AVG_TOP3 * avg_top3
        lex_bonus = lexical_scores.get(pid, 0.0)
        should_hits = sum(min(_should_bonus(c, payload.should), SHOULD_CAP) for c, _ in parent_list)
        should_bonus_val = min(should_hits * SHOULD_BOOST, SHOULD_BONUS_MAX)
        penalty = 0.0
        if query_has_time and fallback_tier >= FALLBACK_TIER_TIME_SOFT:
            has_any_dated = any(
                getattr(c, "start_date", None) is not None or getattr(c, "end_date", None) is not None
                for c, _ in parent_list
            )
            if not has_any_dated:
                penalty += MISSING_DATE_PENALTY
        if query_has_location and fallback_tier >= FALLBACK_TIER_LOCATION_SOFT:
            query_loc_terms = _location_term_variants(must.city, must.country, must.location_text)
            has_match = any(
                _location_text_matches(query_loc_terms, getattr(c, "location", None))
                for c, _ in parent_list
            ) if parent_list else False
            if not has_match:
                penalty += LOCATION_MISMATCH_PENALTY
        final_score = base + lex_bonus + should_bonus_val - penalty
        person_best.append((pid, max(0.0, final_score)))
    person_best.sort(key=lambda x: -x[1])
    return person_cards, child_best_sim, child_sims_by_person, child_best_parent_ids, person_best


def _resolve_search_work_preferences(
    body: SearchRequest,
    must: ParsedConstraintsMust,
) -> tuple[bool, float | None]:
    """Resolve open-to-work and salary filters from request override or parsed MUST."""
    open_to_work_only = (
        body.open_to_work_only
        if body.open_to_work_only is not None
        else (must.open_to_work_only or False)
    )
    if body.salary_max is not None:
        return open_to_work_only, float(body.salary_max)
    return open_to_work_only, must.offer_salary_inr_per_year


def _build_embedding_text(payload: ParsedConstraintsPayload, body: SearchRequest) -> str:
    """Choose embedding text with validated payload preferred over raw query."""
    embedding_text = (
        payload.query_embedding_text
        or payload.query_original
        or body.query
        or ""
    ).strip()
    return embedding_text or (body.query or "")


def _build_query_ts(payload: ParsedConstraintsPayload, body: SearchRequest) -> str:
    """Build lexical tsquery text from phrases + top keywords with cleaned-query fallback."""
    query_ts_parts = list(payload.search_phrases or []) + list((payload.should.keywords or [])[:5])
    return " ".join(str(p).strip() for p in query_ts_parts if str(p).strip()) or (
        payload.query_cleaned or body.query or ""
    )[:200]


def _build_search_constraints(payload: ParsedConstraintsPayload) -> _SearchConstraints:
    """Precompute normalized lists and query flags for fallback search loop."""
    must = payload.must
    exclude = payload.exclude
    time_start = _parse_date(must.time_start)
    time_end = _parse_date(must.time_end)
    return _SearchConstraints(
        must=must,
        company_norms=[c.strip().lower() for c in (must.company_norm or []) if (c or "").strip()],
        team_norms=[t.strip().lower() for t in (must.team_norm or []) if (t or "").strip()],
        exclude_norms=[c.strip().lower() for c in (exclude.company_norm or []) if (c or "").strip()],
        norm_terms_exclude=[t.strip().lower() for t in (exclude.keywords or []) if (t or "").strip()],
        time_start=time_start,
        time_end=time_end,
        query_has_time=(time_start is not None or time_end is not None),
        query_has_location=bool(must.city or must.country or must.location_text),
    )


def _build_candidate_filter_context(
    constraints: _SearchConstraints,
    body: SearchRequest,
    fallback_tier: int,
    open_to_work_only: bool,
    offer_salary_inr_per_year: float | None,
) -> _FilterContext:
    """Build per-tier filter context with tier-specific relaxations."""
    apply_time = fallback_tier < FALLBACK_TIER_TIME_SOFT
    apply_location = fallback_tier < FALLBACK_TIER_LOCATION_SOFT
    apply_company_team = fallback_tier < FALLBACK_TIER_COMPANY_TEAM_SOFT
    return _FilterContext(
        apply_company_team=apply_company_team,
        company_norms=constraints.company_norms,
        team_norms=constraints.team_norms,
        must=constraints.must,
        apply_location=apply_location,
        apply_time=apply_time,
        time_start=constraints.time_start,
        time_end=constraints.time_end,
        exclude_norms=constraints.exclude_norms,
        norm_terms_exclude=constraints.norm_terms_exclude,
        open_to_work_only=open_to_work_only,
        offer_salary_inr_per_year=offer_salary_inr_per_year,
        body=body,
    )


def _build_candidate_statements(query_vec: list[float], filter_ctx: _FilterContext):
    """Build parent, child-best, and child-evidence statements for one fallback tier."""
    dist_expr = ExperienceCard.embedding.cosine_distance(query_vec).label("dist")
    stmt_with_dist = (
        select(ExperienceCard, dist_expr)
        .where(ExperienceCard.experience_card_visibility == True)
        .where(ExperienceCard.embedding.isnot(None))
    )
    stmt_with_dist = _apply_card_filters(stmt_with_dist, filter_ctx)
    stmt_with_dist = stmt_with_dist.order_by(
        ExperienceCard.embedding.cosine_distance(query_vec)
    ).limit(OVERFETCH_CARDS)

    child_dist_stmt = (
        select(
            ExperienceCardChild.person_id,
            func.min(ExperienceCardChild.embedding.cosine_distance(query_vec)).label("dist"),
        )
        .join(
            ExperienceCard,
            and_(
                ExperienceCard.id == ExperienceCardChild.parent_experience_id,
                ExperienceCard.experience_card_visibility == True,
            ),
        )
        .where(ExperienceCardChild.embedding.isnot(None))
    )
    child_dist_stmt = _apply_card_filters(child_dist_stmt, filter_ctx)
    child_dist_stmt = child_dist_stmt.group_by(ExperienceCardChild.person_id)

    child_evidence_stmt = (
        select(
            ExperienceCardChild.person_id,
            ExperienceCardChild.parent_experience_id,
            ExperienceCardChild.id.label("child_id"),
            ExperienceCardChild.embedding.cosine_distance(query_vec).label("dist"),
        )
        .join(
            ExperienceCard,
            and_(
                ExperienceCard.id == ExperienceCardChild.parent_experience_id,
                ExperienceCard.experience_card_visibility == True,
            ),
        )
        .where(ExperienceCardChild.embedding.isnot(None))
    )
    child_evidence_stmt = _apply_card_filters(child_evidence_stmt, filter_ctx)
    child_dists_cte = child_evidence_stmt.cte("child_dists")
    rn = func.row_number().over(
        partition_by=child_dists_cte.c.person_id,
        order_by=child_dists_cte.c.dist,
    ).label("rn")
    ranked = (
        select(
            child_dists_cte.c.person_id,
            child_dists_cte.c.parent_experience_id,
            child_dists_cte.c.child_id,
            child_dists_cte.c.dist,
            rn,
        )
        .select_from(child_dists_cte)
        .subquery("ranked")
    )
    top_children_stmt = (
        select(
            ranked.c.person_id,
            ranked.c.parent_experience_id,
            ranked.c.child_id,
            ranked.c.dist,
        )
        .select_from(ranked)
        .where(ranked.c.rn <= MATCHED_CARDS_PER_PERSON)
    )
    return stmt_with_dist, child_dist_stmt, top_children_stmt


async def _execute_candidate_statements(
    db: AsyncSession,
    parent_stmt: Any,
    child_dist_stmt: Any,
    child_evidence_stmt: Any,
) -> tuple[list[Any], list[Any], list[Any]]:
    """Execute one tier of candidate statements and collect all rows."""
    parent_result = await db.execute(parent_stmt)
    child_dist_result = await db.execute(child_dist_stmt)
    child_evidence_result = await db.execute(child_evidence_stmt)
    return parent_result.all(), child_dist_result.all(), child_evidence_result.all()


async def _fetch_candidates_with_fallback(
    db: AsyncSession,
    query_vec: list[float],
    constraints: _SearchConstraints,
    body: SearchRequest,
    open_to_work_only: bool,
    offer_salary_inr_per_year: float | None,
) -> _CandidateFetchResult:
    """Fetch vector candidates and relax strictness tier-by-tier until enough unique people."""
    fallback_tier = FALLBACK_TIER_STRICT
    rows: list[Any] = []
    child_rows: list[Any] = []
    child_evidence_rows: list[Any] = []
    all_person_ids: set[str] = set()

    while True:
        filter_ctx = _build_candidate_filter_context(
            constraints=constraints,
            body=body,
            fallback_tier=fallback_tier,
            open_to_work_only=open_to_work_only,
            offer_salary_inr_per_year=offer_salary_inr_per_year,
        )
        parent_stmt, child_dist_stmt, child_evidence_stmt = _build_candidate_statements(
            query_vec,
            filter_ctx,
        )
        rows, child_rows, child_evidence_rows = await _execute_candidate_statements(
            db,
            parent_stmt,
            child_dist_stmt,
            child_evidence_stmt,
        )

        all_person_ids = set(str(r[0].person_id) for r in rows) | set(str(r.person_id) for r in child_rows)
        if len(all_person_ids) >= MIN_RESULTS or fallback_tier >= FALLBACK_TIER_COMPANY_TEAM_SOFT:
            break

        fallback_tier += 1
        logger.info(
            "Search fallback: results %s < MIN_RESULTS %s, relaxing to tier %s",
            len(all_person_ids),
            MIN_RESULTS,
            fallback_tier,
        )

    return _CandidateFetchResult(
        fallback_tier=fallback_tier,
        rows=rows,
        child_rows=child_rows,
        child_evidence_rows=child_evidence_rows,
        all_person_ids=all_person_ids,
    )


async def _load_children_by_evidence(
    db: AsyncSession,
    child_evidence_rows: list[Any],
) -> dict[str, ExperienceCardChild]:
    """Load child card objects needed for explainability bullets."""
    child_ids_from_evidence = [str(r.child_id) for r in child_evidence_rows]
    if not child_ids_from_evidence:
        return {}
    child_objs = (
        await db.execute(
            select(ExperienceCardChild).where(ExperienceCardChild.id.in_(child_ids_from_evidence))
        )
    ).scalars().all()
    return {str(c.id): c for c in child_objs}


async def _load_people_and_profiles(
    db: AsyncSession,
    person_ids: list[str],
) -> tuple[dict[str, Person], dict[str, PersonProfile]]:
    """Load Person and PersonProfile maps for ranked person ids."""
    people_result = await db.execute(select(Person).where(Person.id.in_(person_ids)))
    profiles_result = await db.execute(select(PersonProfile).where(PersonProfile.person_id.in_(person_ids)))
    return (
        {str(p.id): p for p in people_result.scalars().all()},
        {str(p.person_id): p for p in profiles_result.scalars().all()},
    )


def _rerank_top_people(
    top_people: list[tuple[str, float]],
    vis_map: dict[str, PersonProfile],
    person_cards: dict[str, list[tuple[ExperienceCard, float]]],
    offer_salary_inr_per_year: float | None,
    query_has_time: bool,
    time_start: object,
    time_end: object,
) -> list[tuple[str, float]]:
    """Tie-aware reordering by salary completeness and date overlap without changing score groups."""
    ranked = top_people

    if offer_salary_inr_per_year is not None:
        def _salary_rank_key(item: tuple[str, float]) -> int:
            pid, _ = item
            vis = vis_map.get(pid)
            has_stated_min = vis and vis.work_preferred_salary_min is not None
            return 0 if has_stated_min else 1

        ranked = _reorder_within_equal_score_groups(ranked, _salary_rank_key)

    if query_has_time:
        def _date_rank_key(item: tuple[str, float]) -> int:
            pid, _ = item
            cards_with_sim = person_cards.get(pid, [])
            has_time_overlap = any(
                _card_dates_overlap_query(c.start_date, c.end_date, time_start, time_end)
                for c, _ in cards_with_sim
            )
            return 0 if has_time_overlap else 1

        ranked = _reorder_within_equal_score_groups(ranked, _date_rank_key)

    return ranked


def _build_pending_rows_and_evidence(
    top_people: list[tuple[str, float]],
    person_cards: dict[str, list[tuple[ExperienceCard, float]]],
    child_sims_by_person: dict[str, list[tuple[str, str, float]]],
    child_best_parent_ids: dict[str, list[str]],
    children_by_id: dict[str, ExperienceCardChild],
    vis_map: dict[str, PersonProfile],
    semantic_similarity_by_person: dict[str, float],
) -> tuple[dict[str, int], list[_PendingSearchRow], list[dict[str, Any]]]:
    """Build pending SearchResult rows + LLM evidence payload per ranked person."""
    similarity_by_person: dict[str, int] = {}
    pending_search_rows: list[_PendingSearchRow] = []
    llm_people_evidence: list[dict[str, Any]] = []

    for rank, (person_id, score) in enumerate(top_people, 1):
        parent_list = person_cards.get(person_id, [])
        child_list = child_sims_by_person.get(person_id, [])
        child_best_parents = child_best_parent_ids.get(person_id) or []
        best_child_parent_id = child_best_parents[0] if child_best_parents else None

        if parent_list:
            parent_list_sorted = sorted(parent_list, key=lambda x: -x[1])
            base_parent_ids = [str(c.id) for c, _ in parent_list_sorted[:3]]
            if best_child_parent_id:
                others = [p for p in base_parent_ids if p != best_child_parent_id]
                matched_parent_ids = [best_child_parent_id] + others[:2]
            else:
                matched_parent_ids = base_parent_ids
        else:
            matched_parent_ids = child_best_parents[:3]

        matched_child_ids = [cid for _pid, cid, _ in child_list[:3] if cid]
        parent_cards_for_bullets = parent_list[:3]
        child_evidence_for_bullets = [
            (children_by_id[cid], pid, s)
            for pid, cid, s in child_list[:3]
            if cid and cid in children_by_id
        ]
        fallback_why = _build_why_matched_bullets(
            parent_cards_for_bullets,
            child_evidence_for_bullets,
            6,
        )

        llm_people_evidence.append(
            _build_person_why_evidence(
                person_id=person_id,
                profile=vis_map.get(person_id),
                parent_cards_with_sim=parent_cards_for_bullets,
                child_evidence=child_evidence_for_bullets,
            )
        )
        similarity_by_person[person_id] = _score_to_similarity_percent(
            semantic_similarity_by_person.get(person_id, 0.0)
        )
        pending_search_rows.append(
            _PendingSearchRow(
                person_id=person_id,
                rank=rank,
                score=score,
                matched_parent_ids=matched_parent_ids,
                matched_child_ids=matched_child_ids,
                fallback_why=fallback_why,
            )
        )

    return similarity_by_person, pending_search_rows, llm_people_evidence


def _apply_why_matched_overrides(
    pending_search_rows: list[_PendingSearchRow],
    llm_why_by_person: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Attach final why_matched lines to pending rows and return response map."""
    why_matched_by_person: dict[str, list[str]] = {}
    for row in pending_search_rows:
        why_matched = llm_why_by_person.get(row.person_id) or row.fallback_why
        why_matched_by_person[row.person_id] = why_matched
        row.why_matched = why_matched
    return why_matched_by_person


async def _load_child_only_cards(
    db: AsyncSession,
    person_ids: list[str],
    person_cards: dict[str, list[tuple[ExperienceCard, float]]],
    child_best_parent_ids: dict[str, list[str]],
) -> dict[str, list[ExperienceCard]]:
    """Load representative parent cards for people whose rank came only from child matches."""
    child_only_pids = [p for p in person_ids if p not in person_cards]
    child_only_cards: dict[str, list[ExperienceCard]] = {}
    if not child_only_pids:
        return child_only_cards

    parent_ids_to_load: list[str] = []
    pid_to_ordered_parent_ids: dict[str, list[str]] = {}
    for pid in child_only_pids:
        ordered = child_best_parent_ids.get(pid)
        if ordered:
            pid_to_ordered_parent_ids[pid] = ordered
            parent_ids_to_load.extend(ordered)

    if parent_ids_to_load:
        parent_ids_to_load = list(dict.fromkeys(parent_ids_to_load))
        stmt_matched = (
            select(ExperienceCard)
            .where(
                ExperienceCard.id.in_(parent_ids_to_load),
                ExperienceCard.experience_card_visibility == True,
            )
        )
        matched_cards_by_id = {str(c.id): c for c in (await db.execute(stmt_matched)).scalars().all()}
        for pid in child_only_pids:
            ordered_ids = pid_to_ordered_parent_ids.get(pid, [])
            child_only_cards[pid] = []
            for card_id in ordered_ids:
                if card_id in matched_cards_by_id and len(child_only_cards[pid]) < MATCHED_CARDS_PER_PERSON:
                    child_only_cards[pid].append(matched_cards_by_id[card_id])

    fallback_pids = [pid for pid in child_only_pids if pid not in child_only_cards or not child_only_cards[pid]]
    if fallback_pids:
        fallback_stmt = (
            select(ExperienceCard)
            .where(
                ExperienceCard.person_id.in_(fallback_pids),
                ExperienceCard.experience_card_visibility == True,
            )
            .order_by(ExperienceCard.person_id, ExperienceCard.created_at.desc())
        )
        fallback_rows = (await db.execute(fallback_stmt)).scalars().all()
        for card in fallback_rows:
            pid = str(card.person_id)
            if len(child_only_cards.get(pid, [])) < MATCHED_CARDS_PER_PERSON:
                child_only_cards.setdefault(pid, []).append(card)

    return child_only_cards


async def _persist_search_response(
    db: AsyncSession,
    searcher_id: str,
    body: SearchRequest,
    filters_dict: dict[str, Any],
    fallback_tier: int,
    pending_search_rows: list[_PendingSearchRow],
    people_list: list[PersonSearchResult],
    idempotency_key: str | None,
) -> SearchResponse:
    """Persist Search + SearchResult rows in one transaction and save idempotent response."""
    if db.in_transaction():
        await db.commit()
    async with db.begin():
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS)
        search_rec = Search(
            searcher_id=searcher_id,
            query_text=body.query,
            parsed_constraints_json=filters_dict,
            filters=filters_dict,
            extra={"fallback_tier": fallback_tier},
            expires_at=expires_at,
        )
        db.add(search_rec)
        await db.flush()
        if not await deduct_credits(db, searcher_id, 1, "search", "search_id", search_rec.id):
            raise HTTPException(status_code=402, detail="Insufficient credits")

        for row in pending_search_rows:
            db.add(
                SearchResult(
                    search_id=search_rec.id,
                    person_id=row.person_id,
                    rank=row.rank,
                    score=Decimal(str(round(row.score, 6))),
                    extra={
                        "matched_parent_ids": row.matched_parent_ids,
                        "matched_child_ids": row.matched_child_ids,
                        "why_matched": row.why_matched or row.fallback_why,
                    },
                )
            )

        resp = SearchResponse(search_id=search_rec.id, people=people_list)
        await _update_idempotency_response(
            db,
            idempotency_key,
            searcher_id,
            SEARCH_ENDPOINT,
            200,
            resp.model_dump(mode="json"),
        )
        return resp


async def _run_search_impl(
    db: AsyncSession,
    searcher_id: str,
    body: SearchRequest,
    idempotency_key: str | None,
) -> SearchResponse:
    """Production hybrid search."""
    balance = await get_balance(db, searcher_id)
    if balance < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    chat = get_chat_provider()
    try:
        filters_raw = await chat.parse_search_filters(body.query)
    except ChatServiceError as e:
        err_kind = _chat_error_kind(e)
        logger.warning(
            "Search query parse failed (%s), using raw-query fallback: %s",
            err_kind,
            e,
        )
        metric_name = (
            "search.llm.parse.invalid_json"
            if err_kind == "invalid_json"
            else "search.llm.parse.timeout_or_http_error"
        )
        _emit_metric_counter(
            metric_name,
            endpoint=SEARCH_ENDPOINT,
            fallback_used=True,
            error_kind=err_kind,
        )
        raw_q = (body.query or "").strip()
        filters_raw = {
            "query_original": raw_q,
            "query_cleaned": raw_q,
            "query_embedding_text": raw_q,
        }

    payload = ParsedConstraintsPayload.from_llm_dict(filters_raw)
    payload = validate_and_normalize(payload)
    filters_dict = payload.model_dump(mode="json")
    must = payload.must

    embedding_text = _build_embedding_text(payload, body)
    constraints = _build_search_constraints(payload)
    open_to_work_only, offer_salary_inr_per_year = _resolve_search_work_preferences(body, must)

    try:
        embed_provider = get_embedding_provider()
        texts = [embedding_text] if embedding_text else [body.query or ""]
        vecs = await embed_provider.embed(texts)
        query_vec = normalize_embedding(vecs[0], embed_provider.dimension) if vecs else []
    except (EmbeddingServiceError, RuntimeError) as e:
        logger.warning("Search embedding failed (503): %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail=str(e))

    if not query_vec:
        return await _create_empty_search_response(db, searcher_id, body, filters_dict, idempotency_key)

    query_ts = _build_query_ts(payload, body)
    lexical_scores = await _lexical_candidates(db, query_ts)

    candidate_fetch = await _fetch_candidates_with_fallback(
        db=db,
        query_vec=query_vec,
        constraints=constraints,
        body=body,
        open_to_work_only=open_to_work_only,
        offer_salary_inr_per_year=offer_salary_inr_per_year,
    )

    lexical_scores = {
        pid: lexical_scores[pid]
        for pid in candidate_fetch.all_person_ids
        if pid in lexical_scores
    }
    person_cards, _, child_sims_by_person, child_best_parent_ids, person_best = _collapse_and_rank_persons(
        candidate_fetch.rows,
        candidate_fetch.child_rows,
        candidate_fetch.child_evidence_rows,
        payload,
        lexical_scores,
        candidate_fetch.fallback_tier,
        constraints.query_has_time,
        constraints.query_has_location,
        constraints.must,
    )
    top_people = person_best[:TOP_PEOPLE]
    children_by_id = await _load_children_by_evidence(db, candidate_fetch.child_evidence_rows)

    if not top_people:
        return await _create_empty_search_response(
            db,
            searcher_id,
            body,
            filters_dict,
            idempotency_key,
            fallback_tier=candidate_fetch.fallback_tier,
        )

    top_people_ids = [pid for pid, _ in top_people]
    people_map, vis_map = await _load_people_and_profiles(db, top_people_ids)
    top_people = _rerank_top_people(
        top_people=top_people,
        vis_map=vis_map,
        person_cards=person_cards,
        offer_salary_inr_per_year=offer_salary_inr_per_year,
        query_has_time=constraints.query_has_time,
        time_start=constraints.time_start,
        time_end=constraints.time_end,
    )
    top_people_ids = [pid for pid, _ in top_people]

    semantic_similarity_by_person = _semantic_similarity_by_person(
        candidate_fetch.rows,
        candidate_fetch.child_rows,
    )
    similarity_by_person, pending_search_rows, llm_people_evidence = _build_pending_rows_and_evidence(
        top_people=top_people,
        person_cards=person_cards,
        child_sims_by_person=child_sims_by_person,
        child_best_parent_ids=child_best_parent_ids,
        children_by_id=children_by_id,
        vis_map=vis_map,
        semantic_similarity_by_person=semantic_similarity_by_person,
    )

    llm_why_by_person = await _generate_llm_why_matched(chat, payload, llm_people_evidence)
    why_matched_by_person = _apply_why_matched_overrides(pending_search_rows, llm_why_by_person)
    child_only_cards = await _load_child_only_cards(
        db=db,
        person_ids=top_people_ids,
        person_cards=person_cards,
        child_best_parent_ids=child_best_parent_ids,
    )

    people_list = _build_search_people_list(
        top_people,
        people_map,
        vis_map,
        person_cards,
        child_only_cards,
        similarity_by_person,
        why_matched_by_person,
    )

    return await _persist_search_response(
        db=db,
        searcher_id=searcher_id,
        body=body,
        filters_dict=filters_dict,
        fallback_tier=candidate_fetch.fallback_tier,
        pending_search_rows=pending_search_rows,
        people_list=people_list,
        idempotency_key=idempotency_key,
    )


async def run_search(
    db: AsyncSession,
    searcher_id: str,
    body: SearchRequest,
    idempotency_key: str | None,
) -> SearchResponse:
    """Reserve idempotency upfront, then release unfinished reservations on failure."""
    existing_resp = await _reserve_idempotency_key_or_return(
        db, idempotency_key, searcher_id, SEARCH_ENDPOINT
    )
    if existing_resp is not None:
        return existing_resp

    reserved_idempotency = bool(idempotency_key)
    try:
        return await _run_search_impl(db, searcher_id, body, idempotency_key)
    except Exception:
        if reserved_idempotency:
            try:
                await _release_idempotency_key_on_failure(
                    db,
                    idempotency_key,
                    searcher_id,
                    SEARCH_ENDPOINT,
                )
            except Exception:
                logger.exception("Failed to release idempotency key after search failure")
        raise


async def get_person_profile(
    db: AsyncSession,
    searcher_id: str,
    person_id: str,
    search_id: str,
) -> PersonProfileResponse:
    """Load profile for a person in a valid search result. Raises HTTPException if invalid/expired."""
    await _validate_search_session(db, searcher_id, search_id, person_id)

    p_result, profile_result, cards_result, unlock_result = await asyncio.gather(
        db.execute(select(Person).where(Person.id == person_id)),
        db.execute(select(PersonProfile).where(PersonProfile.person_id == person_id)),
        db.execute(
            select(ExperienceCard).where(
                ExperienceCard.user_id == person_id,
                ExperienceCard.experience_card_visibility == True,
            ).order_by(ExperienceCard.created_at.desc())
        ),
        db.execute(
            select(UnlockContact).where(
                UnlockContact.searcher_id == searcher_id,
                UnlockContact.target_person_id == person_id,
                UnlockContact.search_id == search_id,
            )
        ),
    )
    person = p_result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    profile = profile_result.scalar_one_or_none()
    cards = cards_result.scalars().all()

    # Contact only shared when Open to work or Open to contact, and only if searcher has unlocked
    contact = None
    open_to_work = profile.open_to_work if profile else False
    open_to_contact = profile.open_to_contact if profile else False
    if (open_to_work or open_to_contact) and unlock_result.scalar_one_or_none() and profile:
        contact = ContactDetailsResponse(
            email_visible=profile.email_visible,
            email=person.email if profile.email_visible else None,
            phone=profile.phone,
            linkedin_url=profile.linkedin_url,
            other=profile.other,
        )

    # Location and salary only shared when Open to work (not for Open to contact only)
    if open_to_work and profile:
        locs = profile.work_preferred_locations or []
        sal_min = profile.work_preferred_salary_min
    else:
        locs = []
        sal_min = None

    # Build card_families (parent + children) and bio so search profile shows full experience like public profile
    bio_resp = _bio_response_for_public(person, profile)
    card_families: list[CardFamilyResponse] = []
    if cards:
        children_result = await db.execute(
            select(ExperienceCardChild).where(
                ExperienceCardChild.parent_experience_id.in_([c.id for c in cards])
            )
        )
        children_list = children_result.scalars().all()
        card_families = _card_families_from_parents_and_children(cards, children_list)

    return PersonProfileResponse(
        id=person.id,
        display_name=person.display_name,
        open_to_work=open_to_work,
        open_to_contact=open_to_contact,
        work_preferred_locations=locs,
        work_preferred_salary_min=sal_min,
        experience_cards=[experience_card_to_response(c) for c in cards],
        card_families=card_families,
        bio=bio_resp,
        contact=contact,
    )


def _contact_response(p: PersonProfile | None, person: Person | None = None) -> ContactDetailsResponse:
    email_visible = p.email_visible if p else True
    return ContactDetailsResponse(
        email_visible=email_visible,
        email=(person.email if (person and email_visible) else None),
        phone=p.phone if p else None,
        linkedin_url=p.linkedin_url if p else None,
        other=p.other if p else None,
    )


async def unlock_contact(
    db: AsyncSession,
    searcher_id: str,
    person_id: str,
    search_id: str,
    idempotency_key: str | None,
) -> UnlockContactResponse:
    """Unlock contact for a person in a valid search. Raises HTTPException on validation/credit errors."""
    endpoint = unlock_endpoint(person_id)
    if idempotency_key:
        existing = await get_idempotent_response(db, idempotency_key, searcher_id, endpoint)
        if existing and existing.response_body:
            return UnlockContactResponse(**existing.response_body)

    await _validate_search_session(db, searcher_id, search_id, person_id)

    profile_result, person_result, u_result = await asyncio.gather(
        db.execute(select(PersonProfile).where(PersonProfile.person_id == person_id)),
        db.execute(select(Person).where(Person.id == person_id)),
        db.execute(
            select(UnlockContact).where(
                UnlockContact.searcher_id == searcher_id,
                UnlockContact.target_person_id == person_id,
                UnlockContact.search_id == search_id,
            )
        ),
    )
    profile = profile_result.scalar_one_or_none()
    person = person_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Person profile not found")
    if not (profile.open_to_work or profile.open_to_contact):
        raise HTTPException(status_code=403, detail="Person is not open to contact")

    if u_result.scalar_one_or_none():
        return UnlockContactResponse(unlocked=True, contact=_contact_response(profile, person))

    balance = await get_balance(db, searcher_id)
    if balance < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    unlock = UnlockContact(
        searcher_id=searcher_id,
        target_person_id=person_id,
        search_id=search_id,
    )
    db.add(unlock)
    await db.flush()
    if not await deduct_credits(db, searcher_id, 1, "unlock_contact", "unlock_id", unlock.id):
        raise HTTPException(status_code=402, detail="Insufficient credits")

    resp = UnlockContactResponse(unlocked=True, contact=_contact_response(profile, person))
    if idempotency_key:
        await save_idempotent_response(db, idempotency_key, searcher_id, endpoint, 200, resp.model_dump(mode="json"))
    return resp


async def list_people_for_discover(db: AsyncSession) -> PersonListResponse:
    """List people who have at least one visible experience card, with display_name, current_location, top 5 titles."""
    subq = (
        select(ExperienceCard.person_id)
        .where(ExperienceCard.experience_card_visibility == True)
        .distinct()
    )
    people_ids_result = await db.execute(select(Person.id).where(Person.id.in_(subq)))
    person_ids = [str(r[0]) for r in people_ids_result.all()]
    if not person_ids:
        return PersonListResponse(people=[])

    async def get_people():
        r = await db.execute(select(Person).where(Person.id.in_(person_ids)))
        return {str(p.id): p for p in r.scalars().all()}

    async def get_profiles():
        r = await db.execute(select(PersonProfile).where(PersonProfile.person_id.in_(person_ids)))
        return {str(p.person_id): p for p in r.scalars().all()}

    async def get_card_summaries():
        # Only fetch columns needed for discover list (avoids loading embedding, raw_text, search_document)
        r = await db.execute(
            select(ExperienceCard.person_id, ExperienceCard.summary, ExperienceCard.created_at)
            .where(
                ExperienceCard.person_id.in_(person_ids),
                ExperienceCard.experience_card_visibility == True,
            )
            .order_by(ExperienceCard.person_id, ExperienceCard.created_at.desc())
        )
        return r.all()

    people, profiles, card_rows = await asyncio.gather(get_people(), get_profiles(), get_card_summaries())

    summaries_by_person: dict[str, list[str]] = {pid: [] for pid in person_ids}
    for row in card_rows:
        pid = str(row.person_id)
        if len(summaries_by_person[pid]) >= 5:
            continue
        summary = (row.summary or "").strip()
        if summary:
            summaries_by_person[pid].append(summary)

    people_list = [
        PersonListItem(
            id=pid,
            display_name=p.display_name,
            current_location=profiles[pid].current_city if pid in profiles else None,
            experience_summaries=summaries_by_person.get(pid, [])[:5],
        )
        for pid, p in people.items()
    ]
    return PersonListResponse(people=people_list)


def _bio_response_for_public(person: Person, profile: PersonProfile | None) -> BioResponse:
    """Build BioResponse for public profile (no sensitive overrides)."""
    from src.schemas import PastCompanyItem
    past = []
    if profile and profile.past_companies:
        for p in profile.past_companies:
            if isinstance(p, dict):
                past.append(PastCompanyItem(
                    company_name=p.get("company_name", "") or "",
                    role=p.get("role"),
                    years=p.get("years"),
                ))
    return BioResponse(
        first_name=profile.first_name if profile else None,
        last_name=profile.last_name if profile else None,
        date_of_birth=profile.date_of_birth if profile else None,
        current_city=profile.current_city if profile else None,
        profile_photo_url=profile.profile_photo_url if profile else None,
        school=profile.school if profile else None,
        college=profile.college if profile else None,
        current_company=profile.current_company if profile else None,
        past_companies=past or None,
        email=None,
        linkedin_url=profile.linkedin_url if profile else None,
        phone=profile.phone if profile else None,
        complete=bool(profile and (profile.school or "").strip() and (person.email or "").strip()),
    )


async def get_public_profile_impl(db: AsyncSession, person_id: str) -> PersonPublicProfileResponse:
    """Load public profile for person detail page: full bio + all experience card families (parent → children)."""
    p_result = await db.execute(select(Person).where(Person.id == person_id))
    person = p_result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    profile_result, cards_result = await asyncio.gather(
        db.execute(select(PersonProfile).where(PersonProfile.person_id == person_id)),
        db.execute(
            select(ExperienceCard).where(
                ExperienceCard.user_id == person_id,
                ExperienceCard.experience_card_visibility == True,
            ).order_by(ExperienceCard.created_at.desc())
        ),
    )
    profile = profile_result.scalar_one_or_none()
    bio_resp = _bio_response_for_public(person, profile)
    parents = cards_result.scalars().all()
    if not parents:
        return PersonPublicProfileResponse(
            id=person.id,
            display_name=person.display_name,
            bio=bio_resp,
            card_families=[],
        )

    children_result = await db.execute(
        select(ExperienceCardChild).where(
            ExperienceCardChild.parent_experience_id.in_([c.id for c in parents])
        )
    )
    children_list = children_result.scalars().all()
    card_families = _card_families_from_parents_and_children(parents, children_list)
    return PersonPublicProfileResponse(
        id=person.id,
        display_name=person.display_name,
        bio=bio_resp,
        card_families=card_families,
    )


class SearchService:
    """Facade for search operations."""

    @staticmethod
    async def search(db: AsyncSession, searcher_id: str, body: SearchRequest, idempotency_key: str | None) -> SearchResponse:
        return await run_search(db, searcher_id, body, idempotency_key)

    @staticmethod
    async def get_profile(db: AsyncSession, searcher_id: str, person_id: str, search_id: str) -> PersonProfileResponse:
        return await get_person_profile(db, searcher_id, person_id, search_id)

    @staticmethod
    async def unlock(db: AsyncSession, searcher_id: str, person_id: str, search_id: str, idempotency_key: str | None) -> UnlockContactResponse:
        return await unlock_contact(db, searcher_id, person_id, search_id, idempotency_key)

    @staticmethod
    async def list_people(db: AsyncSession) -> PersonListResponse:
        return await list_people_for_discover(db)

    @staticmethod
    async def get_public_profile(db: AsyncSession, person_id: str) -> PersonPublicProfileResponse:
        return await get_public_profile_impl(db, person_id)


search_service = SearchService()
