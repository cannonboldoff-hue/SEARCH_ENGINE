"""Search pipeline business logic.

Pipeline: parse query -> embed -> hybrid candidates (vector + lexical) -> MUST/EXCLUDE filters
(with fallback tiers if results < MIN_RESULTS) -> collapse by person with top-K blended scoring
-> penalties (missing date, location mismatch) -> explainability (fallback inline, LLM async) -> persist.
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, text

from src.core import SEARCH_RESULT_EXPIRY_HOURS
from src.db.models import (
    Person,
    PersonProfile,
    ExperienceCard,
    ExperienceCardChild,
    Search,
    SearchResult,
)
from src.db.session import async_session
from src.schemas import (
    SearchRequest,
    SearchResponse,
    PersonSearchResult,
    CardFamilyResponse,
    SavedSearchItem,
    SavedSearchesResponse,
)
from src.schemas.search import (
    ParsedConstraintsPayload,
    ParsedConstraintsShould,
    ParsedConstraintsMust,
)
from src.services.credits import (
    get_balance,
    deduct_credits,
    get_idempotent_response,
    save_idempotent_response,
)
from src.services.filter_validator import validate_and_normalize
from src.providers import (
    get_chat_provider,
    get_embedding_provider,
    ChatServiceError,
    EmbeddingServiceError,
)
from src.prompts.search_why_matched import get_why_matched_prompt
from src.serializers import experience_card_to_response, experience_card_child_to_response
from src.utils import normalize_embedding, strip_json_from_response

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
class _PendingSearchRow:
    """Prepared SearchResult payload before why_matched resolution."""
    person_id: str
    rank: int
    score: float
    matched_parent_ids: list[str]
    matched_child_ids: list[str]
    fallback_why: list[str]


@dataclass(frozen=True)
class _SearchConstraintTerms:
    """Normalized terms and flags derived from parsed MUST/EXCLUDE constraints."""
    time_start: object
    time_end: object
    query_has_time: bool
    query_has_location: bool
    company_norms: list[str]
    team_norms: list[str]
    exclude_company_norms: list[str]
    exclude_keyword_terms: list[str]




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
    """Return whether a search record is expired using explicit or derived expiry."""
    now = datetime.now(timezone.utc)
    if getattr(search_rec, "expires_at", None):
        return search_rec.expires_at < now
    cutoff = now - timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS)
    return not search_rec.created_at or search_rec.created_at < cutoff


OVERFETCH_CARDS = 10
TOP_PEOPLE = 6
TOP_PEOPLE_STORED = 24  # Store up to 24 for load-more pagination (4 pages of 6)
MATCHED_CARDS_PER_PERSON = 3
# Minimum unique persons to avoid fallback; if below, relax MUST in order: time -> location -> company/team
MIN_RESULTS = 15
# Top-K cards per person (parents + children) for blended collapse score
TOP_K_CARDS = 5
# Similarity from cosine distance: sim = 1 / (1 + distance); robust for small distances
def _similarity_from_distance(d: float) -> float:
    """Map a distance value to a bounded similarity score in (0, 1]."""
    return 1.0 / (1.0 + float(d)) if d is not None else 0.0

# Collapse scoring weights (tunable): parent_best, child_best, avg of top-3 card scores
WEIGHT_PARENT_BEST = 0.55
WEIGHT_CHILD_BEST = 0.30
WEIGHT_AVG_TOP3 = 0.15
# Bonuses and penalties (capped)
LEXICAL_BONUS_MAX = 0.25
SHOULD_BOOST = 0.05
SHOULD_CAP = 10
SHOULD_BONUS_MAX = 0.25
MISSING_DATE_PENALTY = 0.15  # when query has time window and card has no dates
LOCATION_MISMATCH_PENALTY = 0.15  # when query specifies location and card differs
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
    """True if card has both dates and [card_start, card_end] overlaps [query_start, query_end]."""
    if card_start is None or card_end is None or query_start is None or query_end is None:
        return False
    return card_start <= query_end and card_end >= query_start


def _text_contains_any(haystack: str, terms: list[str]) -> bool:
    """True if any term (lower) appears in haystack (lower)."""
    if not terms or not (haystack or "").strip():
        return False
    h = haystack.lower()
    return any((t or "").strip().lower() in h for t in terms if (t or "").strip())


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
    """Build 3-6 evidence bullets from search_phrases and snippets of search_document."""
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


def _compact_text(value: Any, max_len: int = 180) -> str | None:
    """Normalize whitespace and trim text for prompt payloads."""
    if value is None:
        return None
    txt = " ".join(str(value).split()).strip()
    if not txt:
        return None
    return txt[:max_len]


def _compact_text_list(values: list[Any] | None, max_len: int, max_items: int) -> list[str]:
    """Compact list entries while preserving order."""
    out: list[str] = []
    for value in (values or [])[:max_items]:
        compacted = _compact_text(value, max_len)
        if compacted:
            out.append(compacted)
    return out


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
            "search_phrases": _compact_text_list(getattr(card, "search_phrases", None), 80, 5),
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
            "tags": _compact_text_list(getattr(child, "tags", None), 50, 6),
            "search_phrases": _compact_text_list(getattr(child, "search_phrases", None), 80, 5),
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
        logger.warning("why_matched LLM call failed, using deterministic fallback: %s", e)
        return {}
    try:
        parsed = json.loads(strip_json_from_response(raw))
    except (TypeError, ValueError, json.JSONDecodeError) as e:
        logger.warning("why_matched LLM JSON parse failed, using deterministic fallback: %s", e)
        return {}

    people = parsed.get("people")
    if not isinstance(people, list):
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
    return out


async def _update_why_matched_async(
    search_id: str,
    payload: ParsedConstraintsPayload,
    people_evidence: list[dict[str, Any]],
    person_ids: list[str],
) -> None:
    """Best-effort async refresh of why_matched in SearchResult.extra."""
    if not people_evidence or not person_ids:
        return
    try:
        chat = get_chat_provider()
    except Exception as e:
        logger.warning("why_matched async skipped (chat provider unavailable): %s", e)
        return

    llm_why_by_person = await _generate_llm_why_matched(chat, payload, people_evidence)
    if not llm_why_by_person:
        return

    unique_person_ids = list(dict.fromkeys([str(pid) for pid in person_ids if pid]))
    if not unique_person_ids:
        return

    try:
        async with async_session() as bg_db:
            result_rows: list[SearchResult] = []
            for attempt in range(4):
                result = await bg_db.execute(
                    select(SearchResult).where(
                        SearchResult.search_id == search_id,
                        SearchResult.person_id.in_(unique_person_ids),
                    )
                )
                result_rows = result.scalars().all()
                if result_rows:
                    break
                await bg_db.rollback()
                await asyncio.sleep(0.15 * (attempt + 1))
            if not result_rows:
                return

            for row in result_rows:
                pid = str(row.person_id)
                lines = llm_why_by_person.get(pid)
                if not lines:
                    continue
                extra = dict(row.extra or {})
                extra["why_matched"] = lines
                row.extra = extra
            await bg_db.commit()
    except Exception as e:
        logger.exception("why_matched async persist failed: %s", e)


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
        loc_conds = [ExperienceCard.location.ilike(f"%{t}%") for t in (ctx.must.city, ctx.must.country, ctx.must.location_text) if t]
        if loc_conds:
            stmt = stmt.where(or_(*loc_conds))
    if ctx.apply_time and ctx.time_start and ctx.time_end:
        # Tier 0: require at least one date bound and actual overlap (no "missing date pass-through")
        at_least_one_bound = or_(
            ExperienceCard.start_date.isnot(None),
            ExperienceCard.end_date.isnot(None),
        )
        overlap = and_(
            or_(ExperienceCard.start_date.is_(None), ExperienceCard.start_date <= ctx.time_end),
            or_(ExperienceCard.end_date.is_(None), ExperienceCard.end_date >= ctx.time_start),
        )
        stmt = stmt.where(at_least_one_bound).where(overlap)
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
            loc_arr = [x.strip() for x in ctx.body.preferred_locations if x]
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
    """Create Search record, deduct credit, return empty SearchResponse; optionally set extra fallback_tier."""
    search_rec = await _create_search_record(
        db=db,
        searcher_id=searcher_id,
        query_text=body.query,
        filters_dict=filters_dict,
        fallback_tier=fallback_tier,
    )
    await _deduct_search_credit_or_raise(db, searcher_id, search_rec.id)
    resp = SearchResponse(search_id=search_rec.id, people=[])
    if idempotency_key:
        await save_idempotent_response(
            db,
            idempotency_key,
            searcher_id,
            SEARCH_ENDPOINT,
            200,
            resp.model_dump(mode="json"),
        )
    return resp


async def _create_search_record(
    db: AsyncSession,
    searcher_id: str,
    query_text: str | None,
    filters_dict: dict[str, Any],
    fallback_tier: int | None,
) -> Search:
    """Insert Search row and return the flushed ORM object."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS)
    search_rec = Search(
        searcher_id=searcher_id,
        query_text=query_text,
        parsed_constraints_json=filters_dict,
        filters=filters_dict,
        extra={"fallback_tier": fallback_tier} if fallback_tier is not None else None,
        expires_at=expires_at,
    )
    db.add(search_rec)
    await db.flush()
    return search_rec


async def _deduct_search_credit_or_raise(db: AsyncSession, searcher_id: str, search_id: str) -> None:
    """Deduct one search credit or raise 402."""
    if not await deduct_credits(db, searcher_id, 1, "search", "search_id", search_id):
        raise HTTPException(status_code=402, detail="Insufficient credits")


def _build_person_headline(profile: PersonProfile | None) -> str | None:
    """Build short headline from current company and city."""
    if not profile:
        return None
    parts = [part for part in (profile.current_company, profile.current_city) if part]
    return " / ".join(parts) if parts else None


def _build_person_bio(profile: PersonProfile | None) -> str | None:
    """Build compact bio summary used in search cards."""
    if not profile:
        return None
    bio_parts: list[str] = []
    full_name = " ".join(part for part in (profile.first_name, profile.last_name) if part).strip()
    if full_name:
        bio_parts.append(full_name)
    if profile.school:
        bio_parts.append(f"School: {profile.school}")
    if profile.college:
        bio_parts.append(f"College: {profile.college}")
    return " | ".join(bio_parts) if bio_parts else None


def _build_search_people_list(
    ranked_people: list[tuple[str, float]],
    people_map: dict[str, Person],
    vis_map: dict[str, PersonProfile],
    person_cards: dict[str, list[tuple[ExperienceCard, float]]],
    child_only_cards: dict[str, list[ExperienceCard]],
    similarity_by_person: dict[str, int],
    why_matched_by_person: dict[str, list[str]],
) -> list[PersonSearchResult]:
    """Build PersonSearchResult list for search response from top-ranked persons and their best cards."""
    people_list = []
    for pid, _score in ranked_people:
        person = people_map.get(pid)
        vis = vis_map.get(pid)
        card_list = person_cards.get(pid, [])
        best_cards = [c for c, _ in card_list[:MATCHED_CARDS_PER_PERSON]]
        if not best_cards and pid in child_only_cards:
            best_cards = child_only_cards[pid][:MATCHED_CARDS_PER_PERSON]
        people_list.append(
            PersonSearchResult(
                id=pid,
                name=person.display_name if person else None,
                headline=_build_person_headline(vis),
                bio=_build_person_bio(vis),
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


def _score_to_similarity_percent(score: float) -> int:
    """Convert blended score to UI-friendly similarity percentage."""
    normalized = max(0.0, min(1.0, float(score)))
    return int(round(normalized * 100))


def _collect_child_best_parent_ids(child_evidence_rows: list) -> dict[str, list[str]]:
    """Track up to MATCHED_CARDS_PER_PERSON distinct best parent IDs per person from child evidence rows."""
    child_best_parent_ids: dict[str, list[str]] = {}
    for row in child_evidence_rows:
        pid = str(row.person_id)
        parent_id = str(row.parent_experience_id)
        if pid not in child_best_parent_ids:
            child_best_parent_ids[pid] = []
        if parent_id in child_best_parent_ids[pid]:
            continue
        if len(child_best_parent_ids[pid]) >= MATCHED_CARDS_PER_PERSON:
            continue
        child_best_parent_ids[pid].append(parent_id)
    return child_best_parent_ids


def _build_parent_card_scores(
    rows: list,
    should: ParsedConstraintsShould,
) -> tuple[dict[str, list[tuple[ExperienceCard, float]]], dict[str, int]]:
    """Build per-person parent-card scores and cumulative should-hit counts."""
    person_cards: dict[str, list[tuple[ExperienceCard, float]]] = defaultdict(list)
    person_should_hits: dict[str, int] = defaultdict(int)

    for card, dist_raw in rows:
        dist = float(dist_raw) if dist_raw is not None else 1.0
        sim = _similarity_from_distance(dist)
        should_hits = min(_should_bonus(card, should), SHOULD_CAP)
        pid = str(card.person_id)

        person_should_hits[pid] += should_hits
        person_cards[pid].append((card, sim + (should_hits * SHOULD_BOOST)))

    for card_rows in person_cards.values():
        card_rows.sort(key=lambda item: -item[1])
    return person_cards, person_should_hits


def _build_child_similarity_maps(
    child_rows: list,
    child_evidence_rows: list,
) -> tuple[dict[str, list[tuple[str, str, float]]], dict[str, float]]:
    """Build child evidence list per person and best child similarity fallback per person."""
    child_best_sim: dict[str, float] = {}
    for row in child_rows:
        pid = str(row.person_id)
        dist = float(row.dist) if row.dist is not None else 1.0
        child_best_sim[pid] = max(child_best_sim.get(pid, 0.0), _similarity_from_distance(dist))

    child_sims_by_person: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
    for row in child_evidence_rows:
        pid = str(row.person_id)
        parent_id = str(row.parent_experience_id)
        child_id = str(row.child_id)
        dist = float(row.dist) if row.dist is not None else 1.0
        child_sims_by_person[pid].append((parent_id, child_id, _similarity_from_distance(dist)))

    for pid, sim in child_best_sim.items():
        if pid not in child_sims_by_person:
            child_sims_by_person[pid].append(("", "", sim))

    for child_rows_for_person in child_sims_by_person.values():
        child_rows_for_person.sort(key=lambda item: -item[2])
    return child_sims_by_person, child_best_sim


def _has_location_match(
    parent_cards: list[tuple[ExperienceCard, float]],
    query_loc_terms: list[str],
) -> bool:
    """Return True when any parent card location contains one of the query location terms."""
    if not parent_cards or not query_loc_terms:
        return False
    for card, _ in parent_cards:
        card_location = (getattr(card, "location", None) or "").lower()
        if any(loc in card_location for loc in query_loc_terms):
            return True
    return False


def _score_person(
    pid: str,
    parent_cards: list[tuple[ExperienceCard, float]],
    child_cards: list[tuple[str, str, float]],
    *,
    child_best_sim: dict[str, float],
    lexical_scores: dict[str, float],
    person_should_hits: dict[str, int],
    fallback_tier: int,
    query_has_time: bool,
    query_has_location: bool,
    query_loc_terms: list[str],
) -> float:
    """Compute final blended score for one person."""
    all_sims = [sim for _, sim in parent_cards]
    all_sims.extend(sim for _, _, sim in child_cards)
    all_sims.sort(reverse=True)
    top_k = all_sims[:TOP_K_CARDS]

    parent_best = max((sim for _, sim in parent_cards), default=0.0)
    child_best = max((sim for _, _, sim in child_cards), default=child_best_sim.get(pid, 0.0))
    if len(top_k) >= 3:
        avg_top3 = sum(top_k[:3]) / 3.0
    elif top_k:
        avg_top3 = sum(top_k) / len(top_k)
    else:
        avg_top3 = 0.0

    base_score = (
        (WEIGHT_PARENT_BEST * parent_best)
        + (WEIGHT_CHILD_BEST * child_best)
        + (WEIGHT_AVG_TOP3 * avg_top3)
    )
    lexical_bonus = lexical_scores.get(pid, 0.0)
    should_bonus = min(person_should_hits.get(pid, 0) * SHOULD_BOOST, SHOULD_BONUS_MAX)

    penalty = 0.0
    if query_has_time and fallback_tier >= FALLBACK_TIER_TIME_SOFT:
        has_any_dated = any(
            getattr(card, "start_date", None) is not None or getattr(card, "end_date", None) is not None
            for card, _ in parent_cards
        )
        if not has_any_dated:
            penalty += MISSING_DATE_PENALTY
    if query_has_location and fallback_tier >= FALLBACK_TIER_LOCATION_SOFT:
        if not _has_location_match(parent_cards, query_loc_terms):
            penalty += LOCATION_MISMATCH_PENALTY

    return max(0.0, base_score + lexical_bonus + should_bonus - penalty)


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
    dict[str, list[tuple[str, str, float]]],
    dict[str, list[str]],
    list[tuple[str, float]],
]:
    """Build person_cards, child evidence, child_best_parent_ids, and sorted person_best (pid, score)."""
    child_best_parent_ids = _collect_child_best_parent_ids(child_evidence_rows)
    person_cards, person_should_hits = _build_parent_card_scores(rows, payload.should)
    child_sims_by_person, child_best_sim = _build_child_similarity_maps(child_rows, child_evidence_rows)

    query_loc_terms = [x.lower() for x in (must.city, must.country, must.location_text) if x]
    person_best: list[tuple[str, float]] = []
    for pid in set(person_cards.keys()) | set(child_best_sim.keys()):
        final_score = _score_person(
            pid,
            person_cards.get(pid, []),
            child_sims_by_person.get(pid, []),
            child_best_sim=child_best_sim,
            lexical_scores=lexical_scores,
            person_should_hits=person_should_hits,
            fallback_tier=fallback_tier,
            query_has_time=query_has_time,
            query_has_location=query_has_location,
            query_loc_terms=query_loc_terms,
        )
        person_best.append((pid, final_score))
    person_best.sort(key=lambda x: -x[1])
    return person_cards, child_sims_by_person, child_best_parent_ids, person_best


def _resolve_open_to_work_only(body: SearchRequest, must: ParsedConstraintsMust) -> bool:
    """Resolve request-level open_to_work_only override."""
    if body.open_to_work_only is not None:
        return body.open_to_work_only
    return bool(must.open_to_work_only)


def _resolve_offer_salary_inr_per_year(body: SearchRequest, must: ParsedConstraintsMust) -> float | None:
    """Pick recruiter offer budget from request override, else parsed constraints."""
    if body.salary_max is not None:
        return float(body.salary_max)
    if must.offer_salary_inr_per_year is not None:
        return must.offer_salary_inr_per_year
    return None


async def _parse_search_payload(chat: Any, raw_query: str | None) -> ParsedConstraintsPayload:
    """Parse query constraints with LLM and apply validation/normalization."""
    try:
        filters_raw = await chat.parse_search_filters(raw_query)
    except ChatServiceError as exc:
        logger.warning("Search query parse failed, using raw-query fallback: %s", exc)
        fallback_query = (raw_query or "").strip()
        filters_raw = {
            "query_original": fallback_query,
            "query_cleaned": fallback_query,
            "query_embedding_text": fallback_query,
        }
    return validate_and_normalize(ParsedConstraintsPayload.from_llm_dict(filters_raw))


async def _embed_query_vector(raw_query: str | None, embedding_text: str) -> list[float]:
    """Embed query text and return normalized vector; raise 503 on provider failure."""
    try:
        embed_provider = get_embedding_provider()
        vector_inputs = [embedding_text or raw_query or ""]
        vectors = await embed_provider.embed(vector_inputs)
        if not vectors:
            return []
        return normalize_embedding(vectors[0], embed_provider.dimension)
    except (EmbeddingServiceError, RuntimeError) as exc:
        logger.warning("Search embedding failed (503): %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail=str(exc))


def _build_embedding_text(payload: ParsedConstraintsPayload, body: SearchRequest) -> str:
    """Build embedding input text from parsed payload with raw-query fallback."""
    return (payload.query_embedding_text or payload.query_original or body.query or "").strip() or (body.query or "")


def _build_query_ts(payload: ParsedConstraintsPayload, body: SearchRequest) -> str:
    """Build lexical tsquery input from parsed search phrases and top keywords."""
    query_ts_parts = list(payload.search_phrases or []) + list((payload.should.keywords or [])[:5])
    parsed_ts = " ".join(str(part).strip() for part in query_ts_parts if str(part).strip())
    return parsed_ts or (payload.query_cleaned or body.query or "")[:200]


def _normalize_lower_terms(values: list[str] | None) -> list[str]:
    """Trim and lowercase term arrays while dropping empty values."""
    return [item.strip().lower() for item in (values or []) if (item or "").strip()]


def _collect_constraint_terms(
    must: ParsedConstraintsMust,
    exclude_company_norm: list[str] | None,
    exclude_keywords: list[str] | None,
) -> _SearchConstraintTerms:
    """Collect normalized MUST/EXCLUDE terms and commonly used query flags."""
    time_start = _parse_date(must.time_start)
    time_end = _parse_date(must.time_end)
    return _SearchConstraintTerms(
        time_start=time_start,
        time_end=time_end,
        query_has_time=time_start is not None and time_end is not None,
        query_has_location=bool(must.city or must.country or must.location_text),
        company_norms=_normalize_lower_terms(must.company_norm),
        team_norms=_normalize_lower_terms(must.team_norm),
        exclude_company_norms=_normalize_lower_terms(exclude_company_norm),
        exclude_keyword_terms=_normalize_lower_terms(exclude_keywords),
    )


def _build_filter_context_for_tier(
    fallback_tier: int,
    body: SearchRequest,
    must: ParsedConstraintsMust,
    company_norms: list[str],
    team_norms: list[str],
    time_start: object,
    time_end: object,
    exclude_norms: list[str],
    norm_terms_exclude: list[str],
    open_to_work_only: bool,
    offer_salary_inr_per_year: float | None,
) -> _FilterContext:
    """Create per-tier filter context used by parent and child candidate queries."""
    return _FilterContext(
        apply_company_team=fallback_tier < FALLBACK_TIER_COMPANY_TEAM_SOFT,
        company_norms=company_norms,
        team_norms=team_norms,
        must=must,
        apply_location=fallback_tier < FALLBACK_TIER_LOCATION_SOFT,
        apply_time=fallback_tier < FALLBACK_TIER_TIME_SOFT,
        time_start=time_start,
        time_end=time_end,
        exclude_norms=exclude_norms,
        norm_terms_exclude=norm_terms_exclude,
        open_to_work_only=open_to_work_only,
        offer_salary_inr_per_year=offer_salary_inr_per_year,
        body=body,
    )


async def _fetch_candidate_rows_for_filter_ctx(
    db: AsyncSession,
    query_vec: list[float],
    filter_ctx: _FilterContext,
) -> tuple[list, list, list]:
    """Fetch parent rows, child aggregate rows, and child evidence rows for one fallback tier."""
    dist_expr = ExperienceCard.embedding.cosine_distance(query_vec).label("dist")
    parent_stmt = (
        select(ExperienceCard, dist_expr)
        .where(ExperienceCard.experience_card_visibility == True)
        .where(ExperienceCard.embedding.isnot(None))
    )
    parent_stmt = _apply_card_filters(parent_stmt, filter_ctx)
    parent_stmt = parent_stmt.order_by(dist_expr).limit(OVERFETCH_CARDS)

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
    ranked_children = (
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
            ranked_children.c.person_id,
            ranked_children.c.parent_experience_id,
            ranked_children.c.child_id,
            ranked_children.c.dist,
        )
        .select_from(ranked_children)
        .where(ranked_children.c.rn <= MATCHED_CARDS_PER_PERSON)
    )

    parent_result, child_dist_result, child_evidence_result = await asyncio.gather(
        db.execute(parent_stmt),
        db.execute(child_dist_stmt),
        db.execute(top_children_stmt),
    )
    return parent_result.all(), child_dist_result.all(), child_evidence_result.all()


async def _fetch_candidates_with_fallback(
    db: AsyncSession,
    query_vec: list[float],
    body: SearchRequest,
    must: ParsedConstraintsMust,
    company_norms: list[str],
    team_norms: list[str],
    time_start: object,
    time_end: object,
    exclude_norms: list[str],
    norm_terms_exclude: list[str],
    open_to_work_only: bool,
    offer_salary_inr_per_year: float | None,
) -> tuple[int, list, list, list]:
    """Run candidate generation while relaxing MUST tiers until enough unique persons are found."""
    fallback_tier = FALLBACK_TIER_STRICT
    while True:
        filter_ctx = _build_filter_context_for_tier(
            fallback_tier=fallback_tier,
            body=body,
            must=must,
            company_norms=company_norms,
            team_norms=team_norms,
            time_start=time_start,
            time_end=time_end,
            exclude_norms=exclude_norms,
            norm_terms_exclude=norm_terms_exclude,
            open_to_work_only=open_to_work_only,
            offer_salary_inr_per_year=offer_salary_inr_per_year,
        )
        rows, child_rows, child_evidence_rows = await _fetch_candidate_rows_for_filter_ctx(db, query_vec, filter_ctx)
        all_person_ids = set(str(r[0].person_id) for r in rows) | set(str(r.person_id) for r in child_rows)
        if len(all_person_ids) >= MIN_RESULTS or fallback_tier >= FALLBACK_TIER_COMPANY_TEAM_SOFT:
            return fallback_tier, rows, child_rows, child_evidence_rows
        fallback_tier += 1
        logger.info(
            "Search fallback: results %s < MIN_RESULTS %s, relaxing to tier %s",
            len(all_person_ids),
            MIN_RESULTS,
            fallback_tier,
        )


async def _load_child_evidence_map(
    db: AsyncSession,
    child_evidence_rows: list,
) -> dict[str, ExperienceCardChild]:
    """Load child objects used for why_matched evidence payloads."""
    child_ids = [str(r.child_id) for r in child_evidence_rows if getattr(r, "child_id", None)]
    if not child_ids:
        return {}
    deduped_child_ids = list(dict.fromkeys(child_ids))
    child_objs = (
        await db.execute(
            select(ExperienceCardChild).where(ExperienceCardChild.id.in_(deduped_child_ids))
        )
    ).scalars().all()
    return {str(c.id): c for c in child_objs}


async def _load_people_profiles_and_children(
    db: AsyncSession,
    person_ids: list[str],
    child_evidence_rows: list,
) -> tuple[dict[str, Person], dict[str, PersonProfile], dict[str, ExperienceCardChild]]:
    """Load Person, PersonProfile, and child-evidence objects for the ranked people set."""
    people_result, profiles_result, children_by_id = await asyncio.gather(
        db.execute(select(Person).where(Person.id.in_(person_ids))),
        db.execute(select(PersonProfile).where(PersonProfile.person_id.in_(person_ids))),
        _load_child_evidence_map(db, child_evidence_rows),
    )
    people_map = {str(person.id): person for person in people_result.scalars().all()}
    profiles_map = {str(profile.person_id): profile for profile in profiles_result.scalars().all()}
    return people_map, profiles_map, children_by_id


def _apply_post_rank_tiebreakers(
    people: list[tuple[str, float]],
    vis_map: dict[str, PersonProfile],
    person_cards: dict[str, list[tuple[ExperienceCard, float]]],
    offer_salary_inr_per_year: float | None,
    time_start: object,
    time_end: object,
) -> list[tuple[str, float]]:
    """Apply deterministic tiebreak sorting for salary and date completeness."""
    ranked = people
    if offer_salary_inr_per_year is not None:
        def _salary_rank_key(item: tuple[str, float]) -> tuple[float, int]:
            pid, score = item
            vis = vis_map.get(pid)
            has_stated_min = vis and vis.work_preferred_salary_min is not None
            return (-score, 0 if has_stated_min else 1)
        ranked = sorted(ranked, key=_salary_rank_key)

    if time_start and time_end:
        def _date_rank_key(item: tuple[str, float]) -> tuple[float, int]:
            pid, score = item
            cards_with_sim = person_cards.get(pid, [])
            has_full_date_overlap = any(
                _card_dates_overlap_query(c.start_date, c.end_date, time_start, time_end)
                for c, _ in cards_with_sim
            )
            return (-score, 0 if has_full_date_overlap else 1)
        ranked = sorted(ranked, key=_date_rank_key)
    return ranked


def _select_matched_parent_ids(
    parent_list: list[tuple[ExperienceCard, float]],
    child_best_parents: list[str],
) -> list[str]:
    """Prefer the parent linked to best child evidence, then fill with best parent matches."""
    if parent_list:
        base_parent_ids = [str(card.id) for card, _ in parent_list[:MATCHED_CARDS_PER_PERSON]]
        if child_best_parents:
            best_child_parent_id = child_best_parents[0]
            others = [parent_id for parent_id in base_parent_ids if parent_id != best_child_parent_id]
            return [best_child_parent_id] + others[: MATCHED_CARDS_PER_PERSON - 1]
        return base_parent_ids
    return child_best_parents[:MATCHED_CARDS_PER_PERSON]


def _prepare_pending_search_rows(
    ranked_people: list[tuple[str, float]],
    person_cards: dict[str, list[tuple[ExperienceCard, float]]],
    child_sims_by_person: dict[str, list[tuple[str, str, float]]],
    child_best_parent_ids: dict[str, list[str]],
    children_by_id: dict[str, ExperienceCardChild],
    vis_map: dict[str, PersonProfile],
) -> tuple[dict[str, int], list[_PendingSearchRow], list[dict[str, Any]]]:
    """Prepare similarity, DB row payloads, and LLM evidence from ranked people."""
    similarity_by_person: dict[str, int] = {}
    pending_search_rows: list[_PendingSearchRow] = []
    llm_people_evidence: list[dict[str, Any]] = []

    for rank, (person_id, score) in enumerate(ranked_people, 1):
        parent_list = person_cards.get(person_id, [])
        child_list = child_sims_by_person.get(person_id, [])
        matched_parent_ids = _select_matched_parent_ids(parent_list, child_best_parent_ids.get(person_id) or [])
        matched_child_ids = [child_id for _parent_id, child_id, _sim in child_list[:MATCHED_CARDS_PER_PERSON] if child_id]
        parent_cards_for_bullets = parent_list[:MATCHED_CARDS_PER_PERSON]
        child_evidence_for_bullets = [
            (children_by_id[child_id], parent_id, sim)
            for parent_id, child_id, sim in child_list[:MATCHED_CARDS_PER_PERSON]
            if child_id and child_id in children_by_id
        ]
        fallback_why = _build_why_matched_bullets(parent_cards_for_bullets, child_evidence_for_bullets, 6)

        llm_people_evidence.append(
            _build_person_why_evidence(
                person_id=person_id,
                profile=vis_map.get(person_id),
                parent_cards_with_sim=parent_cards_for_bullets,
                child_evidence=child_evidence_for_bullets,
            )
        )
        similarity_by_person[person_id] = _score_to_similarity_percent(score)
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


def _persist_search_results(
    db: AsyncSession,
    search_id: Any,
    pending_search_rows: list[_PendingSearchRow],
    llm_why_by_person: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Insert SearchResult rows and return resolved why_matched per person."""
    why_matched_by_person: dict[str, list[str]] = {}
    for row in pending_search_rows:
        why_matched = llm_why_by_person.get(row.person_id) or row.fallback_why
        why_matched_by_person[row.person_id] = why_matched
        db.add(
            SearchResult(
                search_id=search_id,
                person_id=row.person_id,
                rank=row.rank,
                score=Decimal(str(round(row.score, 6))),
                extra={
                    "matched_parent_ids": row.matched_parent_ids,
                    "matched_child_ids": row.matched_child_ids,
                    "why_matched": why_matched,
                },
            )
        )
    return why_matched_by_person


async def _load_child_only_cards(
    db: AsyncSession,
    pid_list: list[str],
    person_cards: dict[str, list[tuple[ExperienceCard, float]]],
    child_best_parent_ids: dict[str, list[str]],
) -> dict[str, list[ExperienceCard]]:
    """Load display cards for people matched only via child embeddings."""
    child_only_pids = [pid for pid in pid_list if pid not in person_cards]
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


async def run_search(
    db: AsyncSession,
    searcher_id: str,
    body: SearchRequest,
    idempotency_key: str | None,
) -> SearchResponse:
    """Production hybrid search.

    Flow:
    1. Parse constraints -> store in Search.parsed_constraints_json
    2. Embed query_embedding_text
    3. Candidate generation (vector): top K parents (experience_cards.embedding), top K children (experience_card_children.embedding)
    4. Apply MUST filters: company_norm, team_norm, experience_card_visibility=true, time overlap (NULL-safe), location, open_to_work_only -> person_profiles.open_to_work, offer_salary_inr_per_year -> work_preferred_salary_min <= offer OR NULL
    5. Rerank: base = vector score, small boosts for should.skills_or_tools / should.keywords in search_phrases/search_document
    6. Group by person (best evidence cards first), store results in search_results
    """
    if idempotency_key:
        existing = await get_idempotent_response(db, idempotency_key, searcher_id, SEARCH_ENDPOINT)
        if existing and existing.response_body:
            return SearchResponse(**existing.response_body)

    if await get_balance(db, searcher_id) < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    chat = get_chat_provider()
    payload = await _parse_search_payload(chat, body.query)
    filters_dict = payload.model_dump(mode="json")
    must = payload.must
    exclude = payload.exclude

    # Query prep
    embedding_text = _build_embedding_text(payload, body)
    open_to_work_only = _resolve_open_to_work_only(body, must)
    offer_salary_inr_per_year = _resolve_offer_salary_inr_per_year(body, must)
    query_ts = _build_query_ts(payload, body)

    # Run embedding + lexical in parallel to reduce tail latency.
    embed_task = asyncio.create_task(_embed_query_vector(body.query, embedding_text))
    lexical_task = asyncio.create_task(_lexical_candidates(db, query_ts))
    embed_exc: Exception | None = None
    try:
        query_vec = await embed_task
    except Exception as exc:
        embed_exc = exc
        query_vec = []

    try:
        lexical_scores = await lexical_task
    except Exception as exc:
        logger.warning("Lexical search task failed, continuing without lexical bonus: %s", exc)
        lexical_scores = {}

    if embed_exc:
        raise embed_exc
    if not query_vec:
        return await _create_empty_search_response(db, searcher_id, body, filters_dict, idempotency_key)

    # Constraint prep
    term_ctx = _collect_constraint_terms(
        must=must,
        exclude_company_norm=exclude.company_norm,
        exclude_keywords=exclude.keywords,
    )

    # Candidate generation with fallback tiers
    fallback_tier, rows, child_rows, child_evidence_rows = await _fetch_candidates_with_fallback(
        db=db,
        query_vec=query_vec,
        body=body,
        must=must,
        company_norms=term_ctx.company_norms,
        team_norms=term_ctx.team_norms,
        time_start=term_ctx.time_start,
        time_end=term_ctx.time_end,
        exclude_norms=term_ctx.exclude_company_norms,
        norm_terms_exclude=term_ctx.exclude_keyword_terms,
        open_to_work_only=open_to_work_only,
        offer_salary_inr_per_year=offer_salary_inr_per_year,
    )

    person_cards, child_sims_by_person, child_best_parent_ids, person_best = _collapse_and_rank_persons(
        rows,
        child_rows,
        child_evidence_rows,
        payload,
        lexical_scores,
        fallback_tier,
        term_ctx.query_has_time,
        term_ctx.query_has_location,
        must,
    )
    ranked_people_full = person_best[:TOP_PEOPLE_STORED]

    if not ranked_people_full:
        return await _create_empty_search_response(
            db,
            searcher_id,
            body,
            filters_dict,
            idempotency_key,
            fallback_tier=fallback_tier,
        )

    person_ids_full = [pid for pid, _score in ranked_people_full]
    people_map, vis_map, children_by_id = await _load_people_profiles_and_children(
        db=db,
        person_ids=person_ids_full,
        child_evidence_rows=child_evidence_rows,
    )

    ranked_people_full = _apply_post_rank_tiebreakers(
        people=ranked_people_full,
        vis_map=vis_map,
        person_cards=person_cards,
        offer_salary_inr_per_year=offer_salary_inr_per_year,
        time_start=term_ctx.time_start,
        time_end=term_ctx.time_end,
    )
    search_rec = await _create_search_record(
        db=db,
        searcher_id=searcher_id,
        query_text=body.query,
        filters_dict=filters_dict,
        fallback_tier=fallback_tier,
    )
    await _deduct_search_credit_or_raise(db, searcher_id, search_rec.id)

    similarity_by_person, pending_search_rows, llm_people_evidence = _prepare_pending_search_rows(
        ranked_people=ranked_people_full,
        person_cards=person_cards,
        child_sims_by_person=child_sims_by_person,
        child_best_parent_ids=child_best_parent_ids,
        children_by_id=children_by_id,
        vis_map=vis_map,
    )

    why_matched_by_person = _persist_search_results(
        db=db,
        search_id=search_rec.id,
        pending_search_rows=pending_search_rows,
        llm_why_by_person={},
    )
    if llm_people_evidence:
        asyncio.create_task(
            _update_why_matched_async(
                search_id=str(search_rec.id),
                payload=payload,
                people_evidence=llm_people_evidence,
                person_ids=[row.person_id for row in pending_search_rows],
            )
        )

    child_only_cards = await _load_child_only_cards(
        db=db,
        pid_list=person_ids_full,
        person_cards=person_cards,
        child_best_parent_ids=child_best_parent_ids,
    )

    ranked_people_initial = ranked_people_full[:TOP_PEOPLE]
    people_list = _build_search_people_list(
        ranked_people_initial,
        people_map,
        vis_map,
        person_cards,
        child_only_cards,
        similarity_by_person,
        why_matched_by_person,
    )
    resp = SearchResponse(search_id=search_rec.id, people=people_list)
    if idempotency_key:
        await save_idempotent_response(
            db,
            idempotency_key,
            searcher_id,
            SEARCH_ENDPOINT,
            200,
            resp.model_dump(mode="json"),
        )
    return resp


LOAD_MORE_LIMIT = 6


async def load_search_more(
    db: AsyncSession,
    searcher_id: str,
    search_id: str,
    offset: int,
    limit: int = LOAD_MORE_LIMIT,
    skip_credits: bool = False,
) -> list[PersonSearchResult]:
    """Fetch the next batch of search results (by rank). When skip_credits=True (viewing from saved history), no credit deduction."""
    search_rec, _ = await _validate_search_session(db, searcher_id, search_id)

    stmt = (
        select(SearchResult)
        .where(SearchResult.search_id == search_id)
        .order_by(SearchResult.rank.asc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    if not rows:
        return []

    if not skip_credits:
        if await get_balance(db, searcher_id) < 1:
            raise HTTPException(status_code=402, detail="Insufficient credits")
        if not await deduct_credits(db, searcher_id, 1, "search_more", "search_id", search_id):
            raise HTTPException(status_code=402, detail="Insufficient credits")

    person_ids = [str(r.person_id) for r in rows]

    people_stmt = select(Person).where(Person.id.in_(person_ids))
    people_result = await db.execute(people_stmt)
    people_map = {str(p.id): p for p in people_result.scalars().all()}

    profiles_stmt = select(PersonProfile).where(PersonProfile.person_id.in_(person_ids))
    profiles_result = await db.execute(profiles_stmt)
    vis_map = {str(p.person_id): p for p in profiles_result.scalars().all()}

    card_ids: list[str] = []
    for r in rows:
        extra = r.extra or {}
        card_ids.extend(extra.get("matched_parent_ids") or [])
    card_ids = list(dict.fromkeys(card_ids))

    cards_by_id: dict[str, ExperienceCard] = {}
    if card_ids:
        cards_stmt = select(ExperienceCard).where(ExperienceCard.id.in_(card_ids))
        cards_result = await db.execute(cards_stmt)
        cards_by_id = {str(c.id): c for c in cards_result.scalars().all()}

    out: list[PersonSearchResult] = []
    for r in rows:
        pid = str(r.person_id)
        person = people_map.get(pid)
        vis = vis_map.get(pid)
        extra = r.extra or {}
        matched_ids = extra.get("matched_parent_ids") or []
        why_matched = extra.get("why_matched") or []
        best_cards = [cards_by_id[cid] for cid in matched_ids if cid in cards_by_id][:MATCHED_CARDS_PER_PERSON]
        raw_score = float(r.score) if r.score is not None else 0.0
        similarity = _score_to_similarity_percent(raw_score)

        out.append(
            PersonSearchResult(
                id=pid,
                name=person.display_name if person else None,
                headline=_build_person_headline(vis),
                bio=_build_person_bio(vis),
                similarity_percent=similarity,
                why_matched=why_matched,
                open_to_work=vis.open_to_work if vis else False,
                open_to_contact=vis.open_to_contact if vis else False,
                work_preferred_locations=vis.work_preferred_locations or [] if vis else [],
                work_preferred_salary_min=vis.work_preferred_salary_min if vis else None,
                matched_cards=[experience_card_to_response(c) for c in best_cards],
            )
        )
    return out


async def list_searches(
    db: AsyncSession,
    searcher_id: str,
    limit: int = 50,
) -> SavedSearchesResponse:
    """List recent searches for the searcher (including expired), newest first, with result count."""
    now = datetime.now(timezone.utc)

    stmt = (
        select(
            Search.id,
            Search.query_text,
            Search.created_at,
            Search.expires_at,
            func.count(SearchResult.id).label("result_count"),
        )
        .select_from(Search)
        .outerjoin(SearchResult, SearchResult.search_id == Search.id)
        .where(Search.searcher_id == searcher_id)
        .group_by(Search.id, Search.query_text, Search.created_at, Search.expires_at)
        .order_by(Search.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    out: list[SavedSearchItem] = []
    for (sid, query_text, created_at, expires_at, cnt) in rows:
        expired = bool(expires_at and expires_at < now)
        out.append(
            SavedSearchItem(
                id=str(sid),
                query_text=query_text or "",
                created_at=created_at.isoformat() if created_at else "",
                expires_at=expires_at.isoformat() if expires_at else "",
                expired=expired,
                result_count=int(cnt or 0),
            )
        )
    return SavedSearchesResponse(searches=out)

