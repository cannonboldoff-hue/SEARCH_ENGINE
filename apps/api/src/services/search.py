"""Search, profile view, and contact unlock business logic."""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_

from src.core import SEARCH_RESULT_EXPIRY_HOURS
from src.db.models import (
    Person,
    PersonProfile,
    ExperienceCard,
    ExperienceCardChild,
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
from src.schemas.search import ParsedConstraintsPayload, ParsedConstraintsShould
from src.services.credits import get_balance, deduct_credits, get_idempotent_response, save_idempotent_response
from src.services.filter_validator import validate_and_normalize
from src.providers import get_chat_provider, get_embedding_provider, ChatServiceError, EmbeddingServiceError
from src.serializers import experience_card_to_response, experience_card_child_to_response
from src.utils import normalize_embedding

logger = logging.getLogger(__name__)
SEARCH_ENDPOINT = "POST /search"


def unlock_endpoint(person_id: str) -> str:
    """Idempotency endpoint for unlock-contact (per target person)."""
    return f"POST /people/{person_id}/unlock-contact"


def _search_expired(search_rec: Search) -> bool:
    now = datetime.now(timezone.utc)
    if getattr(search_rec, "expires_at", None):
        return search_rec.expires_at < now
    cutoff = now - timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS)
    return not search_rec.created_at or search_rec.created_at < cutoff


OVERFETCH_CARDS = 50
TOP_PEOPLE = 5
MATCHED_CARDS_PER_PERSON = 3


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
    hits = 0
    if should.intent_secondary and card.intent_secondary:
        if any(i in (card.intent_secondary or []) for i in should.intent_secondary):
            hits += 1
    phrases = (card.search_phrases or []) if hasattr(card, "search_phrases") else []
    phrases_lower = [p.lower() for p in phrases if p]
    doc_text = (getattr(card, "search_document", None) or "") or ""
    skills_or_tools = [t.strip().lower() for t in (should.skills_or_tools or []) if (t or "").strip()]
    if skills_or_tools and (any(any(t in p for p in phrases_lower) for t in skills_or_tools) or _text_contains_any(doc_text, skills_or_tools)):
        hits += 1
    keywords = [t.strip().lower() for t in (should.keywords or []) if (t or "").strip()]
    if keywords and (any(any(t in p for p in phrases_lower) for t in keywords) or _text_contains_any(doc_text, keywords)):
        hits += 1
    return hits


async def run_search(
    db: AsyncSession,
    searcher_id: str,
    body: SearchRequest,
    idempotency_key: str | None,
) -> SearchResponse:
    """Production hybrid search.

    Flow:
    1. Parse constraints → store in Search.parsed_constraints_json
    2. Embed query_embedding_text
    3. Candidate generation (vector): top K parents (experience_cards.embedding), top K children (experience_card_children.embedding)
    4. Apply MUST filters: company_norm, team_norm, experience_card_visibility=true, time overlap (NULL-safe), location, open_to_work_only → person_profiles.open_to_work, offer_salary_inr_per_year → work_preferred_salary_min <= offer OR NULL
    5. Rerank: base = vector score, small boosts for should.skills_or_tools / should.keywords in search_phrases/search_document
    6. Group by person (best evidence cards first), store results in search_results
    """
    if idempotency_key:
        existing = await get_idempotent_response(db, idempotency_key, searcher_id, SEARCH_ENDPOINT)
        if existing and existing.response_body:
            return SearchResponse(**existing.response_body)

    balance = await get_balance(db, searcher_id)
    if balance < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    chat = get_chat_provider()
    try:
        filters_raw = await chat.parse_search_filters(body.query)
    except ChatServiceError as e:
        logger.warning("Search query parse failed, using raw-query fallback: %s", e)
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
    exclude = payload.exclude

    # Embedding text: from filters pipeline, else raw query
    embedding_text = (payload.query_embedding_text or payload.query_original or body.query or "").strip()
    if not embedding_text:
        embedding_text = body.query or ""

    # Request-level overrides (body wins over parsed)
    open_to_work_only = body.open_to_work_only if body.open_to_work_only is not None else (must.open_to_work_only or False)
    # Recruiter offer budget (₹/year): from body.salary_max or from parsed offer_salary_inr_per_year.
    # We match candidates where work_preferred_salary_min <= offer_salary_inr_per_year; NULL = keep but downrank.
    offer_salary_inr_per_year: float | None = None
    if body.salary_max is not None:
        offer_salary_inr_per_year = float(body.salary_max)
    elif must.offer_salary_inr_per_year is not None:
        offer_salary_inr_per_year = must.offer_salary_inr_per_year

    # 2) Embed query for vector similarity
    try:
        embed_provider = get_embedding_provider()
        texts = [embedding_text] if embedding_text else [body.query or ""]
        vecs = await embed_provider.embed(texts)
        query_vec = normalize_embedding(vecs[0], embed_provider.dimension) if vecs else []
    except (EmbeddingServiceError, RuntimeError) as e:
        logger.warning("Search embedding failed (503): %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail=str(e))

    if not query_vec:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS)
        search_rec = Search(
            searcher_id=searcher_id,
            query_text=body.query,
            parsed_constraints_json=filters_dict,
            filters=filters_dict,
            expires_at=expires_at,
        )
        db.add(search_rec)
        await db.flush()
        if not await deduct_credits(db, searcher_id, 1, "search", "search_id", search_rec.id):
            raise HTTPException(status_code=402, detail="Insufficient credits")
        resp = SearchResponse(search_id=search_rec.id, people=[])
        if idempotency_key:
            await save_idempotent_response(db, idempotency_key, searcher_id, SEARCH_ENDPOINT, 200, resp.model_dump(mode="json"))
        return resp

    # Build base query: visible cards with embedding. Use pgvector's native cosine_distance for proper bind handling.
    dist_expr = ExperienceCard.embedding.cosine_distance(query_vec).label("dist")
    stmt_with_dist = (
        select(ExperienceCard, dist_expr)
        .where(ExperienceCard.experience_card_visibility == True)
        .where(ExperienceCard.embedding.isnot(None))
    )

    # MUST filters (strict): company_norm, team_norm, intent_primary, domain, sub_domain, employment_type, seniority_level, location, time, is_current, open_to_work_only, offer_salary_inr_per_year.
    company_norms = [c.strip().lower() for c in (must.company_norm or []) if (c or "").strip()]
    if company_norms:
        stmt_with_dist = stmt_with_dist.where(ExperienceCard.company_norm.in_(company_norms))
    team_norms = [t.strip().lower() for t in (must.team_norm or []) if (t or "").strip()]
    if team_norms:
        stmt_with_dist = stmt_with_dist.where(ExperienceCard.team_norm.in_(team_norms))
    if must.intent_primary:
        stmt_with_dist = stmt_with_dist.where(ExperienceCard.intent_primary.in_(must.intent_primary))
    if must.domain:
        stmt_with_dist = stmt_with_dist.where(ExperienceCard.domain.in_(must.domain))
    if must.sub_domain:
        stmt_with_dist = stmt_with_dist.where(ExperienceCard.sub_domain.in_(must.sub_domain))
    if must.employment_type:
        stmt_with_dist = stmt_with_dist.where(ExperienceCard.employment_type.in_(must.employment_type))
    if must.seniority_level:
        stmt_with_dist = stmt_with_dist.where(ExperienceCard.seniority_level.in_(must.seniority_level))
    if must.city or must.country or must.location_text:
        loc_conds = []
        if must.city:
            loc_conds.append(ExperienceCard.location.ilike(f"%{must.city}%"))
        if must.country:
            loc_conds.append(ExperienceCard.location.ilike(f"%{must.country}%"))
        if must.location_text:
            loc_conds.append(ExperienceCard.location.ilike(f"%{must.location_text}%"))
        if loc_conds:
            stmt_with_dist = stmt_with_dist.where(or_(*loc_conds))
    _start = _parse_date(must.time_start)
    _end = _parse_date(must.time_end)
    if _start and _end:
        # Overlap-safe: keep cards where (both dates known AND overlap) OR any date missing (keep but downrank later).
        both_known_and_overlap = and_(
            ExperienceCard.start_date.isnot(None),
            ExperienceCard.end_date.isnot(None),
            ExperienceCard.start_date <= _end,
            ExperienceCard.end_date >= _start,
        )
        has_missing_date = or_(
            ExperienceCard.start_date.is_(None),
            ExperienceCard.end_date.is_(None),
        )
        stmt_with_dist = stmt_with_dist.where(or_(both_known_and_overlap, has_missing_date))
    if must.is_current is not None:
        stmt_with_dist = stmt_with_dist.where(ExperienceCard.is_current == must.is_current)

    # EXCLUDE filters
    exclude_norms = [c.strip().lower() for c in (exclude.company_norm or []) if (c or "").strip()]
    if exclude_norms:
        stmt_with_dist = stmt_with_dist.where(~ExperienceCard.company_norm.in_(exclude_norms))
    if exclude.keywords:
        norm_terms = [t.strip().lower() for t in exclude.keywords if (t or "").strip()]
        if norm_terms:
            stmt_with_dist = stmt_with_dist.where(~ExperienceCard.search_phrases.overlap(norm_terms))

    # Join PersonProfile when filtering by open_to_work, location, or salary (offer budget).
    if open_to_work_only or offer_salary_inr_per_year is not None:
        join_conds = [ExperienceCard.person_id == PersonProfile.person_id]
        if open_to_work_only:
            join_conds.append(PersonProfile.open_to_work == True)
        stmt_with_dist = stmt_with_dist.join(PersonProfile, and_(*join_conds))
        if open_to_work_only and body.preferred_locations:
            loc_arr = [x.strip() for x in body.preferred_locations if x]
            if loc_arr:
                stmt_with_dist = stmt_with_dist.where(
                    PersonProfile.work_preferred_locations.overlap(loc_arr)
                )
        # Salary: candidate's work_preferred_salary_min (₹/year) <= recruiter's offer_salary_inr_per_year; NULL = keep but downrank later.
        if offer_salary_inr_per_year is not None:
            stmt_with_dist = stmt_with_dist.where(
                or_(
                    PersonProfile.work_preferred_salary_min.is_(None),
                    PersonProfile.work_preferred_salary_min <= offer_salary_inr_per_year,
                )
            )

    stmt_with_dist = stmt_with_dist.order_by(ExperienceCard.embedding.cosine_distance(query_vec)).limit(OVERFETCH_CARDS)
    rows = (await db.execute(stmt_with_dist)).all()

    # Child embedding search: best distance per person, with same MUST filters on parent card (visibility, company_norm, team_norm, time, location, open_to_work, salary)
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
    if company_norms:
        child_dist_stmt = child_dist_stmt.where(ExperienceCard.company_norm.in_(company_norms))
    if team_norms:
        child_dist_stmt = child_dist_stmt.where(ExperienceCard.team_norm.in_(team_norms))
    if must.intent_primary:
        child_dist_stmt = child_dist_stmt.where(ExperienceCard.intent_primary.in_(must.intent_primary))
    if must.domain:
        child_dist_stmt = child_dist_stmt.where(ExperienceCard.domain.in_(must.domain))
    if must.sub_domain:
        child_dist_stmt = child_dist_stmt.where(ExperienceCard.sub_domain.in_(must.sub_domain))
    if must.employment_type:
        child_dist_stmt = child_dist_stmt.where(ExperienceCard.employment_type.in_(must.employment_type))
    if must.seniority_level:
        child_dist_stmt = child_dist_stmt.where(ExperienceCard.seniority_level.in_(must.seniority_level))
    if must.city or must.country or must.location_text:
        loc_conds = []
        if must.city:
            loc_conds.append(ExperienceCard.location.ilike(f"%{must.city}%"))
        if must.country:
            loc_conds.append(ExperienceCard.location.ilike(f"%{must.country}%"))
        if must.location_text:
            loc_conds.append(ExperienceCard.location.ilike(f"%{must.location_text}%"))
        if loc_conds:
            child_dist_stmt = child_dist_stmt.where(or_(*loc_conds))
    if _start and _end:
        both_known_and_overlap = and_(
            ExperienceCard.start_date.isnot(None),
            ExperienceCard.end_date.isnot(None),
            ExperienceCard.start_date <= _end,
            ExperienceCard.end_date >= _start,
        )
        has_missing_date = or_(
            ExperienceCard.start_date.is_(None),
            ExperienceCard.end_date.is_(None),
        )
        child_dist_stmt = child_dist_stmt.where(or_(both_known_and_overlap, has_missing_date))
    if must.is_current is not None:
        child_dist_stmt = child_dist_stmt.where(ExperienceCard.is_current == must.is_current)
    if exclude_norms:
        child_dist_stmt = child_dist_stmt.where(~ExperienceCard.company_norm.in_(exclude_norms))
    if exclude.keywords:
        norm_terms = [t.strip().lower() for t in exclude.keywords if (t or "").strip()]
        if norm_terms:
            child_dist_stmt = child_dist_stmt.where(~ExperienceCard.search_phrases.overlap(norm_terms))
    if open_to_work_only or offer_salary_inr_per_year is not None:
        join_conds = [ExperienceCardChild.person_id == PersonProfile.person_id]
        if open_to_work_only:
            join_conds.append(PersonProfile.open_to_work == True)
        child_dist_stmt = child_dist_stmt.join(PersonProfile, and_(*join_conds))
        if open_to_work_only and body.preferred_locations:
            loc_arr = [x.strip() for x in body.preferred_locations if x]
            if loc_arr:
                child_dist_stmt = child_dist_stmt.where(
                    PersonProfile.work_preferred_locations.overlap(loc_arr)
                )
        if offer_salary_inr_per_year is not None:
            child_dist_stmt = child_dist_stmt.where(
                or_(
                    PersonProfile.work_preferred_salary_min.is_(None),
                    PersonProfile.work_preferred_salary_min <= offer_salary_inr_per_year,
                )
            )
    # Child search: (1) best similarity per person for scoring, (2) best 1–3 (child, parent) per person for evidence
    child_dist_stmt = child_dist_stmt.group_by(ExperienceCardChild.person_id)
    child_rows = (await db.execute(child_dist_stmt)).all()
    child_best_sim: dict[str, float] = {}
    for row in child_rows:
        pid = str(row.person_id)
        dist = float(row.dist) if row.dist is not None else 1.0
        child_best_sim[pid] = max(child_best_sim.get(pid, 0.0), 1.0 - dist)

    # Evidence query: per person, top 1–3 (parent_experience_id, child_id) by distance for matched cards in response
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
    if company_norms:
        child_evidence_stmt = child_evidence_stmt.where(ExperienceCard.company_norm.in_(company_norms))
    if team_norms:
        child_evidence_stmt = child_evidence_stmt.where(ExperienceCard.team_norm.in_(team_norms))
    if must.intent_primary:
        child_evidence_stmt = child_evidence_stmt.where(ExperienceCard.intent_primary.in_(must.intent_primary))
    if must.domain:
        child_evidence_stmt = child_evidence_stmt.where(ExperienceCard.domain.in_(must.domain))
    if must.sub_domain:
        child_evidence_stmt = child_evidence_stmt.where(ExperienceCard.sub_domain.in_(must.sub_domain))
    if must.employment_type:
        child_evidence_stmt = child_evidence_stmt.where(ExperienceCard.employment_type.in_(must.employment_type))
    if must.seniority_level:
        child_evidence_stmt = child_evidence_stmt.where(ExperienceCard.seniority_level.in_(must.seniority_level))
    if must.city or must.country or must.location_text:
        loc_conds = []
        if must.city:
            loc_conds.append(ExperienceCard.location.ilike(f"%{must.city}%"))
        if must.country:
            loc_conds.append(ExperienceCard.location.ilike(f"%{must.country}%"))
        if must.location_text:
            loc_conds.append(ExperienceCard.location.ilike(f"%{must.location_text}%"))
        if loc_conds:
            child_evidence_stmt = child_evidence_stmt.where(or_(*loc_conds))
    if _start and _end:
        both_known_and_overlap = and_(
            ExperienceCard.start_date.isnot(None),
            ExperienceCard.end_date.isnot(None),
            ExperienceCard.start_date <= _end,
            ExperienceCard.end_date >= _start,
        )
        has_missing_date = or_(
            ExperienceCard.start_date.is_(None),
            ExperienceCard.end_date.is_(None),
        )
        child_evidence_stmt = child_evidence_stmt.where(or_(both_known_and_overlap, has_missing_date))
    if must.is_current is not None:
        child_evidence_stmt = child_evidence_stmt.where(ExperienceCard.is_current == must.is_current)
    if exclude_norms:
        child_evidence_stmt = child_evidence_stmt.where(~ExperienceCard.company_norm.in_(exclude_norms))
    if exclude.keywords:
        norm_terms = [t.strip().lower() for t in exclude.keywords if (t or "").strip()]
        if norm_terms:
            child_evidence_stmt = child_evidence_stmt.where(~ExperienceCard.search_phrases.overlap(norm_terms))
    if open_to_work_only or offer_salary_inr_per_year is not None:
        join_conds = [ExperienceCardChild.person_id == PersonProfile.person_id]
        if open_to_work_only:
            join_conds.append(PersonProfile.open_to_work == True)
        child_evidence_stmt = child_evidence_stmt.join(PersonProfile, and_(*join_conds))
        if open_to_work_only and body.preferred_locations:
            loc_arr = [x.strip() for x in body.preferred_locations if x]
            if loc_arr:
                child_evidence_stmt = child_evidence_stmt.where(
                    PersonProfile.work_preferred_locations.overlap(loc_arr)
                )
        if offer_salary_inr_per_year is not None:
            child_evidence_stmt = child_evidence_stmt.where(
                or_(
                    PersonProfile.work_preferred_salary_min.is_(None),
                    PersonProfile.work_preferred_salary_min <= offer_salary_inr_per_year,
                )
            )
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
    child_evidence_rows = (await db.execute(top_children_stmt)).all()

    # Per person: ordered list of parent_experience_ids that actually matched (for loading cards in Step 11)
    child_best_parent_ids: dict[str, list[str]] = {}
    for row in child_evidence_rows:
        pid = str(row.person_id)
        parent_id = str(row.parent_experience_id)
        if pid not in child_best_parent_ids:
            child_best_parent_ids[pid] = []
        if parent_id not in child_best_parent_ids[pid] and len(child_best_parent_ids[pid]) < MATCHED_CARDS_PER_PERSON:
            child_best_parent_ids[pid].append(parent_id)

    # rows are (ExperienceCard, distance); similarity = 1 - distance; add should bonus for rerank
    SHOULD_BOOST = 0.02
    SHOULD_CAP = 10
    person_cards: dict[str, list[tuple[ExperienceCard, float]]] = defaultdict(list)
    for row in rows:
        card = row[0]
        dist = float(row[1]) if row[1] is not None else 1.0
        sim = 1.0 - dist
        bonus = min(_should_bonus(card, payload.should), SHOULD_CAP) * SHOULD_BOOST
        person_cards[str(card.person_id)].append((card, sim + bonus))

    # Collapse by person_id: best (parent) score, then merge with child best sim
    person_best: list[tuple[str, float]] = []
    for pid, card_list in person_cards.items():
        best_sim = max(sim for _, sim in card_list)
        child_sim = child_best_sim.get(pid, 0.0)
        person_best.append((pid, max(best_sim, child_sim)))
    # Include persons that only matched via children (no parent rows)
    for pid, child_sim in child_best_sim.items():
        if pid not in person_cards:
            person_best.append((pid, child_sim))
    person_best.sort(key=lambda x: -x[1])
    top_20 = person_best[:TOP_PEOPLE]

    if not top_20:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS)
        search_rec = Search(
            searcher_id=searcher_id,
            query_text=body.query,
            parsed_constraints_json=filters_dict,
            filters=filters_dict,
            expires_at=expires_at,
        )
        db.add(search_rec)
        await db.flush()
        if not await deduct_credits(db, searcher_id, 1, "search", "search_id", search_rec.id):
            raise HTTPException(status_code=402, detail="Insufficient credits")
        resp = SearchResponse(search_id=search_rec.id, people=[])
        if idempotency_key:
            await save_idempotent_response(db, idempotency_key, searcher_id, SEARCH_ENDPOINT, 200, resp.model_dump(mode="json"))
        return resp

    pid_list = [p[0] for p in top_20]
    people_result = await db.execute(select(Person).where(Person.id.in_(pid_list)))
    people_map = {str(p.id): p for p in people_result.scalars().all()}
    profiles_result = await db.execute(select(PersonProfile).where(PersonProfile.person_id.in_(pid_list)))
    vis_map = {str(p.person_id): p for p in profiles_result.scalars().all()}
    # When recruiter set offer salary: downrank candidates with unknown (NULL) work_preferred_salary_min.
    if offer_salary_inr_per_year is not None:
        def _salary_rank_key(item: tuple[str, float]) -> tuple[float, int]:
            pid, score = item
            vis = vis_map.get(pid)
            has_stated_min = vis and vis.work_preferred_salary_min is not None
            return (-score, 0 if has_stated_min else 1)  # same score → stated min first
        top_20 = sorted(top_20, key=_salary_rank_key)

    # When query has date range: downrank persons whose matched cards have missing start/end (don't drop them).
    if _start and _end:
        def _date_rank_key(item: tuple[str, float]) -> tuple[float, int]:
            pid, score = item
            cards_with_sim = person_cards.get(pid, [])
            has_full_date_overlap = any(
                _card_dates_overlap_query(c.start_date, c.end_date, _start, _end)
                for c, _ in cards_with_sim
            )
            return (-score, 0 if has_full_date_overlap else 1)  # same score → full date overlap first
        top_20 = sorted(top_20, key=_date_rank_key)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS)
    search_rec = Search(
        searcher_id=searcher_id,
        query_text=body.query,
        parsed_constraints_json=filters_dict,
        filters=filters_dict,
        expires_at=expires_at,
    )
    db.add(search_rec)
    await db.flush()
    if not await deduct_credits(db, searcher_id, 1, "search", "search_id", search_rec.id):
        raise HTTPException(status_code=402, detail="Insufficient credits")

    for rank, (person_id, score) in enumerate(top_20, 1):
        sr = SearchResult(search_id=search_rec.id, person_id=person_id, rank=rank, score=Decimal(str(score)))
        db.add(sr)

    # Load cards for persons who only matched via child embedding: use the parent(s) that actually matched
    child_only_pids = [p for p in pid_list if p not in person_cards]
    child_only_cards: dict[str, list[ExperienceCard]] = {}
    if child_only_pids:
        # Prefer parents from child_best_parent_ids (the ones that matched the child embedding)
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
        # Fallback: any child-only person not in child_best_parent_ids gets latest 3 by created_at
        for pid in child_only_pids:
            if pid not in child_only_cards or not child_only_cards[pid]:
                fallback_stmt = (
                    select(ExperienceCard)
                    .where(
                        ExperienceCard.person_id == pid,
                        ExperienceCard.experience_card_visibility == True,
                    )
                    .order_by(ExperienceCard.created_at.desc())
                    .limit(MATCHED_CARDS_PER_PERSON)
                )
                fallback_rows = (await db.execute(fallback_stmt)).scalars().all()
                child_only_cards[pid] = [c for c in fallback_rows]

    people_list = []
    for pid, score in top_20:
        person = people_map.get(pid)
        vis = vis_map.get(pid)
        # 1–3 best matching cards: from person_cards (parent matches) or child_only_cards
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
                open_to_work=vis.open_to_work if vis else False,
                open_to_contact=vis.open_to_contact if vis else False,
                work_preferred_locations=vis.work_preferred_locations or [] if vis else [],
                work_preferred_salary_min=vis.work_preferred_salary_min if vis else None,
                matched_cards=[experience_card_to_response(c) for c in best_cards],
            )
        )

    resp = SearchResponse(search_id=search_rec.id, people=people_list)
    if idempotency_key:
        await save_idempotent_response(db, idempotency_key, searcher_id, SEARCH_ENDPOINT, 200, resp.model_dump(mode="json"))
    return resp


async def get_person_profile(
    db: AsyncSession,
    searcher_id: str,
    person_id: str,
    search_id: str,
) -> PersonProfileResponse:
    """Load profile for a person in a valid search result. Raises HTTPException if invalid/expired."""
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

    r_result = await db.execute(
        select(SearchResult).where(
            SearchResult.search_id == search_id,
            SearchResult.person_id == person_id,
        )
    )
    if not r_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Person not in this search result")

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
        by_parent: dict[str, list] = {}
        for ch in children_list:
            pid = str(ch.parent_experience_id)
            by_parent.setdefault(pid, []).append(ch)
        card_families = [
            CardFamilyResponse(
                parent=experience_card_to_response(card),
                children=[experience_card_child_to_response(ch) for ch in by_parent.get(str(card.id), [])],
            )
            for card in cards
        ]

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

    r_result = await db.execute(
        select(SearchResult).where(
            SearchResult.search_id == search_id,
            SearchResult.person_id == person_id,
        )
    )
    if not r_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Person not in this search result")

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
    by_parent: dict[str, list] = {}
    for ch in children_list:
        pid = str(ch.parent_experience_id)
        by_parent.setdefault(pid, []).append(ch)

    card_families = [
        CardFamilyResponse(
            parent=experience_card_to_response(card),
            children=[experience_card_child_to_response(ch) for ch in by_parent.get(str(card.id), [])],
        )
        for card in parents
    ]
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
