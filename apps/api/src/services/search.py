"""Search, profile view, and contact unlock business logic."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func

from src.constants import SEARCH_RESULT_EXPIRY_HOURS
from src.db.models import (
    Person,
    VisibilitySettings,
    ContactDetails,
    ExperienceCard,
    Search,
    SearchResult,
    UnlockContact,
)
from src.schemas import (
    SearchRequest,
    SearchResponse,
    PersonSearchResult,
    PersonProfileResponse,
    ContactDetailsResponse,
    UnlockContactResponse,
)
from src.credits import get_balance, deduct_credits, get_idempotent_response, save_idempotent_response
from src.providers import get_chat_provider, get_embedding_provider, ChatServiceError, EmbeddingServiceError
from src.serializers import experience_card_to_response
from src.utils import normalize_embedding

SEARCH_ENDPOINT = "POST /search"


def unlock_endpoint(person_id: str) -> str:
    """Idempotency endpoint for unlock-contact (per target person)."""
    return f"POST /people/{person_id}/unlock-contact"


def _search_expired(search_rec: Search) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS)
    return not search_rec.created_at or search_rec.created_at < cutoff


async def run_search(
    db: AsyncSession,
    searcher_id: str,
    body: SearchRequest,
    idempotency_key: str | None,
) -> SearchResponse:
    """Execute semantic search and return results. Raises HTTPException on validation/credit/API errors."""
    if idempotency_key:
        existing = await get_idempotent_response(db, idempotency_key, searcher_id, SEARCH_ENDPOINT)
        if existing and existing.response_body:
            return SearchResponse(**existing.response_body)

    balance = await get_balance(db, searcher_id)
    if balance < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    chat = get_chat_provider()
    try:
        parsed = await chat.parse_search_query(body.query)
    except ChatServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))

    embed_provider = get_embedding_provider()
    try:
        query_embedding = await embed_provider.embed([parsed.semantic_text or body.query])
    except EmbeddingServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not query_embedding:
        raise HTTPException(
            status_code=503,
            detail="Embedding model returned no vector. Ensure the embedding service is running.",
        )
    qvec = normalize_embedding(query_embedding[0])

    open_to_work_only = body.open_to_work_only if body.open_to_work_only is not None else parsed.open_to_work_only

    card_subq = (
        select(ExperienceCard.person_id)
        .where(ExperienceCard.status == ExperienceCard.APPROVED)
        .where(ExperienceCard.embedding.isnot(None))
        .distinct()
    )
    person_ids_result = await db.execute(card_subq)
    pid_list = [r[0] for r in person_ids_result.fetchall()]

    if not pid_list:
        search_rec = Search(
            searcher_id=searcher_id,
            query_text=body.query,
            filters={"company": parsed.company, "team": parsed.team, "open_to_work_only": open_to_work_only},
        )
        db.add(search_rec)
        await db.flush()
        if not await deduct_credits(db, searcher_id, 1, "search", "search_id", search_rec.id):
            raise HTTPException(status_code=402, detail="Insufficient credits")
        resp = SearchResponse(search_id=search_rec.id, people=[])
        if idempotency_key:
            await save_idempotent_response(db, idempotency_key, searcher_id, SEARCH_ENDPOINT, 200, resp.model_dump())
        return resp

    qvec_str = "[" + ",".join(str(round(x, 6)) for x in qvec) + "]"
    ranked = []
    if qvec_str:
        sql = text("""
        SELECT ec.person_id, MIN(1 - (ec.embedding <=> CAST(:qvec AS vector))) as score
        FROM experience_cards ec
        WHERE ec.status = 'APPROVED' AND ec.embedding IS NOT NULL
        GROUP BY ec.person_id
        ORDER BY score DESC NULLS LAST
        LIMIT 50
        """)
        result = await db.execute(sql, {"qvec": qvec_str})
        rows = result.fetchall()
        ranked = [(str(r[0]), float(r[1]) if r[1] is not None else 0.0) for r in rows]
    if not ranked:
        ranked = [(str(pid), 0.0) for pid in pid_list[:50]]

    if open_to_work_only:
        vis_result = await db.execute(
            select(VisibilitySettings.person_id).where(VisibilitySettings.open_to_work == True)
        )
        open_ids = {r[0] for r in vis_result.fetchall()}
        ranked = [(pid, score) for pid, score in ranked if pid in open_ids]

    if parsed.company or parsed.team:
        card_filter = (
            select(ExperienceCard.person_id)
            .where(ExperienceCard.status == ExperienceCard.APPROVED)
            .distinct()
        )
        if parsed.company:
            card_filter = card_filter.where(
                func.lower(ExperienceCard.company) == parsed.company.strip().lower()
            )
        if parsed.team:
            card_filter = card_filter.where(
                func.lower(ExperienceCard.team) == parsed.team.strip().lower()
            )
        match_result = await db.execute(card_filter)
        match_ids = {r[0] for r in match_result.fetchall()}
        ranked = [(pid, score) for pid, score in ranked if pid in match_ids]

    if body.preferred_locations:
        loc_set = set(x.strip().lower() for x in body.preferred_locations if x)
        if loc_set:
            filtered = []
            for pid, score in ranked:
                v = await db.execute(
                    select(VisibilitySettings.work_preferred_locations).where(
                        VisibilitySettings.person_id == pid
                    )
                )
                locs = v.scalar_one_or_none()
                if locs and any(loc and loc.strip().lower() in loc_set for loc in locs):
                    filtered.append((pid, score))
            ranked = filtered

    if body.salary_min is not None or body.salary_max is not None:
        filtered = []
        for pid, score in ranked:
            v = await db.execute(
                select(
                    VisibilitySettings.work_preferred_salary_min,
                    VisibilitySettings.work_preferred_salary_max,
                ).where(VisibilitySettings.person_id == pid)
            )
            row = v.fetchone()
            if not row:
                filtered.append((pid, score))
                continue
            w_min, w_max = row[0], row[1]
            if body.salary_min is not None and w_max is not None and float(w_max) < float(body.salary_min):
                continue
            if body.salary_max is not None and w_min is not None and float(w_min) > float(body.salary_max):
                continue
            filtered.append((pid, score))
        ranked = filtered

    ranked = ranked[:20]

    search_rec = Search(
        searcher_id=searcher_id,
        query_text=body.query,
        filters={"company": parsed.company, "team": parsed.team, "open_to_work_only": open_to_work_only},
    )
    db.add(search_rec)
    await db.flush()
    if not await deduct_credits(db, searcher_id, 1, "search", "search_id", search_rec.id):
        raise HTTPException(status_code=402, detail="Insufficient credits")

    for rank, (person_id, score) in enumerate(ranked, 1):
        sr = SearchResult(search_id=search_rec.id, person_id=person_id, rank=rank, score=Decimal(str(score)))
        db.add(sr)

    people_list = []
    for pid, _ in ranked:
        p_result = await db.execute(select(Person).where(Person.id == pid))
        person = p_result.scalar_one_or_none()
        v_result = await db.execute(select(VisibilitySettings).where(VisibilitySettings.person_id == pid))
        vis = v_result.scalar_one_or_none()
        people_list.append(
            PersonSearchResult(
                id=pid,
                display_name=person.display_name if person else None,
                open_to_work=vis.open_to_work if vis else False,
                open_to_contact=vis.open_to_contact if vis else False,
            )
        )

    resp = SearchResponse(search_id=search_rec.id, people=people_list)
    if idempotency_key:
        await save_idempotent_response(db, idempotency_key, searcher_id, SEARCH_ENDPOINT, 200, resp.model_dump())
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

    p_result = await db.execute(select(Person).where(Person.id == person_id))
    person = p_result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    v_result = await db.execute(select(VisibilitySettings).where(VisibilitySettings.person_id == person_id))
    vis = v_result.scalar_one_or_none()

    cards_result = await db.execute(
        select(ExperienceCard).where(
            ExperienceCard.person_id == person_id,
            ExperienceCard.status == ExperienceCard.APPROVED,
        ).order_by(ExperienceCard.created_at.desc())
    )
    cards = cards_result.scalars().all()

    contact = None
    unlock_result = await db.execute(
        select(UnlockContact).where(
            UnlockContact.searcher_id == searcher_id,
            UnlockContact.target_person_id == person_id,
            UnlockContact.search_id == search_id,
        )
    )
    if unlock_result.scalar_one_or_none():
        c_result = await db.execute(select(ContactDetails).where(ContactDetails.person_id == person_id))
        c = c_result.scalar_one_or_none()
        if c:
            contact = ContactDetailsResponse(
                email_visible=c.email_visible,
                phone=c.phone,
                linkedin_url=c.linkedin_url,
                other=c.other,
            )

    return PersonProfileResponse(
        id=person.id,
        display_name=person.display_name,
        open_to_work=vis.open_to_work if vis else False,
        open_to_contact=vis.open_to_contact if vis else False,
        work_preferred_locations=(vis.work_preferred_locations or []) if vis else [],
        work_preferred_salary_min=vis.work_preferred_salary_min if vis else None,
        work_preferred_salary_max=vis.work_preferred_salary_max if vis else None,
        contact_preferred_salary_min=vis.contact_preferred_salary_min if vis else None,
        contact_preferred_salary_max=vis.contact_preferred_salary_max if vis else None,
        experience_cards=[experience_card_to_response(c) for c in cards],
        contact=contact,
    )


def _contact_response(c: ContactDetails | None) -> ContactDetailsResponse:
    return ContactDetailsResponse(
        email_visible=c.email_visible if c else True,
        phone=c.phone if c else None,
        linkedin_url=c.linkedin_url if c else None,
        other=c.other if c else None,
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

    v_result = await db.execute(select(VisibilitySettings).where(VisibilitySettings.person_id == person_id))
    vis = v_result.scalar_one_or_none()
    if not vis or not vis.open_to_contact:
        raise HTTPException(status_code=400, detail="Person is not open to contact")

    u_result = await db.execute(
        select(UnlockContact).where(
            UnlockContact.searcher_id == searcher_id,
            UnlockContact.target_person_id == person_id,
            UnlockContact.search_id == search_id,
        )
    )
    if u_result.scalar_one_or_none():
        c_result = await db.execute(select(ContactDetails).where(ContactDetails.person_id == person_id))
        c = c_result.scalar_one_or_none()
        return UnlockContactResponse(unlocked=True, contact=_contact_response(c))

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

    c_result = await db.execute(select(ContactDetails).where(ContactDetails.person_id == person_id))
    c = c_result.scalar_one_or_none()
    resp = UnlockContactResponse(unlocked=True, contact=_contact_response(c))
    if idempotency_key:
        await save_idempotent_response(db, idempotency_key, searcher_id, endpoint, 200, resp.model_dump())
    return resp


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


search_service = SearchService()
