"""Search, profile view, and contact unlock business logic."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

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
from src.services.credits import get_balance, deduct_credits, get_idempotent_response, save_idempotent_response
from src.providers import get_chat_provider, ChatServiceError
from src.serializers import experience_card_to_response, experience_card_child_to_response

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

    open_to_work_only = body.open_to_work_only if body.open_to_work_only is not None else parsed.open_to_work_only

    query_text = (parsed.semantic_text or body.query or "").strip()
    card_query = select(ExperienceCard).where(ExperienceCard.experience_card_visibility == True)
    if parsed.company:
        card_query = card_query.where(func.lower(ExperienceCard.company_name) == parsed.company.strip().lower())
    if query_text:
        like_pattern = f"%{query_text}%"
        card_query = card_query.where(
            or_(
                ExperienceCard.title.ilike(like_pattern),
                ExperienceCard.normalized_role.ilike(like_pattern),
                ExperienceCard.summary.ilike(like_pattern),
                ExperienceCard.raw_text.ilike(like_pattern),
                ExperienceCard.domain.ilike(like_pattern),
                ExperienceCard.sub_domain.ilike(like_pattern),
                ExperienceCard.company_name.ilike(like_pattern),
                ExperienceCard.company_type.ilike(like_pattern),
                ExperienceCard.location.ilike(like_pattern),
                ExperienceCard.employment_type.ilike(like_pattern),
                ExperienceCard.intent_primary.ilike(like_pattern),
                ExperienceCard.seniority_level.ilike(like_pattern),
            )
        )
    card_query = card_query.order_by(
        ExperienceCard.confidence_score.desc().nullslast(),
        ExperienceCard.created_at.desc(),
    )
    cards_result = await db.execute(card_query)
    cards = list(cards_result.scalars().all())
    ranked = []
    seen = set()
    for card in cards:
        if card.user_id in seen:
            continue
        seen.add(card.user_id)
        score = float(card.confidence_score) if card.confidence_score is not None else 0.0
        ranked.append((str(card.user_id), score))
    pid_list = [pid for pid, _ in ranked]

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

    vis_map = {}
    match_ids = None
    if pid_list:
        async def get_vis():
            r = await db.execute(
                select(PersonProfile).where(PersonProfile.person_id.in_(pid_list))
            )
            return {str(v.person_id): v for v in r.scalars().all()}

        async def get_company_match():
            if not parsed.company:
                return None
            r = await db.execute(
                select(ExperienceCard.user_id)
                .where(ExperienceCard.experience_card_visibility == True)
                .where(func.lower(ExperienceCard.company_name) == parsed.company.strip().lower())
                .distinct()
            )
            return {r[0] for r in r.fetchall()}

        vis_map, match_ids = await asyncio.gather(get_vis(), get_company_match())

    # Exclude "Hide Contact": anyone with both open_to_work=False and open_to_contact=False does not appear in search
    ranked = [
        (pid, score)
        for pid, score in ranked
        if not (pid in vis_map and not vis_map[pid].open_to_work and not vis_map[pid].open_to_contact)
    ]

    if open_to_work_only:
        ranked = [
            (pid, score)
            for pid, score in ranked
            if pid in vis_map and vis_map[pid].open_to_work
        ]

    if match_ids is not None:
        ranked = [(pid, score) for pid, score in ranked if pid in match_ids]

    if body.preferred_locations:
        loc_set = set(x.strip().lower() for x in body.preferred_locations if x)
        if loc_set:
            filtered = []
            for pid, score in ranked:
                vis = vis_map.get(pid)
                locs = vis.work_preferred_locations if vis else None
                if locs and any(loc and loc.strip().lower() in loc_set for loc in locs):
                    filtered.append((pid, score))
            ranked = filtered

    if body.salary_min is not None or body.salary_max is not None:
        filtered = []
        for pid, score in ranked:
            vis = vis_map.get(pid)
            if not vis:
                filtered.append((pid, score))
                continue
            w_min = vis.work_preferred_salary_min  # candidate's minimum salary needed
            if body.salary_max is not None and w_min is not None and float(body.salary_max) < float(w_min):
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

    people_map = {}
    if ranked:
        people_result = await db.execute(select(Person).where(Person.id.in_([pid for pid, _ in ranked])))
        people_map = {str(p.id): p for p in people_result.scalars().all()}

    people_list = []
    for pid, _ in ranked:
        person = people_map.get(pid)
        vis = vis_map.get(pid)
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

    return PersonProfileResponse(
        id=person.id,
        display_name=person.display_name,
        open_to_work=open_to_work,
        open_to_contact=open_to_contact,
        work_preferred_locations=locs,
        work_preferred_salary_min=sal_min,
        experience_cards=[experience_card_to_response(c) for c in cards],
        contact=contact,
    )


def _contact_response(p: PersonProfile | None) -> ContactDetailsResponse:
    return ContactDetailsResponse(
        email_visible=p.email_visible if p else True,
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

    profile_result, u_result = await asyncio.gather(
        db.execute(select(PersonProfile).where(PersonProfile.person_id == person_id)),
        db.execute(
            select(UnlockContact).where(
                UnlockContact.searcher_id == searcher_id,
                UnlockContact.target_person_id == person_id,
                UnlockContact.search_id == search_id,
            )
        ),
    )
    profile = profile_result.scalar_one_or_none()
    if not profile or not (profile.open_to_work or profile.open_to_contact):
        raise HTTPException(status_code=400, detail="Person is not open to work or open to contact")

    if u_result.scalar_one_or_none():
        return UnlockContactResponse(unlocked=True, contact=_contact_response(profile))

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

    resp = UnlockContactResponse(unlocked=True, contact=_contact_response(profile))
    if idempotency_key:
        await save_idempotent_response(db, idempotency_key, searcher_id, endpoint, 200, resp.model_dump())
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
