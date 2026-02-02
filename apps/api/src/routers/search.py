from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, and_, or_
from sqlalchemy.orm import selectinload

from src.db.models import (
    Person,
    VisibilitySettings,
    ContactDetails,
    ExperienceCard,
    Search,
    SearchResult,
    UnlockContact,
)
from src.dependencies import get_current_user, get_db
from src.schemas import (
    SearchRequest,
    SearchResponse,
    PersonSearchResult,
    PersonProfileResponse,
    ExperienceCardResponse,
    ContactDetailsResponse,
    UnlockContactResponse,
)
from src.credits import get_balance, deduct_credits, get_idempotent_response, save_idempotent_response
from src.providers import get_chat_provider, get_embedding_provider
from src.limiter import limiter

router = APIRouter(tags=["search"])

SEARCH_RESULT_EXPIRY_HOURS = 24


def _card_to_response(c: ExperienceCard) -> ExperienceCardResponse:
    return ExperienceCardResponse(
        id=c.id,
        person_id=c.person_id,
        raw_experience_id=c.raw_experience_id,
        status=c.status,
        title=c.title,
        context=c.context,
        constraints=c.constraints,
        decisions=c.decisions,
        outcome=c.outcome,
        tags=c.tags or [],
        company=c.company,
        team=c.team,
        role_title=c.role_title,
        time_range=c.time_range,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.post("/search", response_model=SearchResponse)
@limiter.limit("10/minute")
async def search(
    request: Request,
    body: SearchRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    endpoint = "POST /search"
    if idempotency_key:
        existing = await get_idempotent_response(db, idempotency_key, current_user.id, endpoint)
        if existing and existing.response_body:
            return SearchResponse(**existing.response_body)

    balance = await get_balance(db, current_user.id)
    if balance < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    chat = get_chat_provider()
    parsed = await chat.parse_search_query(body.query)
    embed_provider = get_embedding_provider()
    query_embedding = await embed_provider.embed([parsed.semantic_text or body.query])
    if not query_embedding:
        query_embedding = await embed_provider.embed([body.query])
    qvec = query_embedding[0] if query_embedding else None

    # Build filter: people with APPROVED cards; optionally open_to_work, locations, salary
    open_to_work_only = body.open_to_work_only if body.open_to_work_only is not None else parsed.open_to_work_only

    card_subq = (
        select(ExperienceCard.person_id)
        .where(ExperienceCard.status == ExperienceCard.APPROVED)
        .where(ExperienceCard.embedding.isnot(None))
        .distinct()
    )
    person_ids_with_cards = await db.execute(card_subq)
    pid_list = [r[0] for r in person_ids_with_cards.fetchall()]
    if not pid_list:
        search_rec = Search(searcher_id=current_user.id, query_text=body.query, filters={
            "company": parsed.company,
            "team": parsed.team,
            "open_to_work_only": open_to_work_only,
        })
        db.add(search_rec)
        await db.flush()
        await deduct_credits(db, current_user.id, 1, "search", "search_id", search_rec.id)
        people_list = []
        resp = SearchResponse(search_id=search_rec.id, people=people_list)
        if idempotency_key:
            await save_idempotent_response(
                db, idempotency_key, current_user.id, endpoint,
                200, resp.model_dump(),
            )
        return resp

    qvec_str = "[" + ",".join(str(round(x, 6)) for x in qvec) + "]" if qvec else None
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

    # Apply visibility filter: if open_to_work_only, filter to only those with open_to_work=True
    if open_to_work_only:
        vis_result = await db.execute(
            select(VisibilitySettings.person_id).where(VisibilitySettings.open_to_work == True)
        )
        open_ids = {r[0] for r in vis_result.fetchall()}
        ranked = [(pid, score) for pid, score in ranked if pid in open_ids]

    # Optional: filter by preferred_locations (work_preferred_locations overlap)
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
                if locs and any(l and l.strip().lower() in loc_set for l in locs):
                    filtered.append((pid, score))
            ranked = filtered

    # Optional: salary range filter (work_preferred_salary)
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
        searcher_id=current_user.id,
        query_text=body.query,
        filters={
            "company": parsed.company,
            "team": parsed.team,
            "open_to_work_only": open_to_work_only,
        },
    )
    db.add(search_rec)
    await db.flush()
    await deduct_credits(db, current_user.id, 1, "search", "search_id", search_rec.id)

    for rank, (person_id, score) in enumerate(ranked, 1):
        sr = SearchResult(search_id=search_rec.id, person_id=person_id, rank=rank, score=Decimal(str(score)))
        db.add(sr)

    # Load people for response
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
        await save_idempotent_response(
            db, idempotency_key, current_user.id, endpoint,
            200, resp.model_dump(),
        )
    return resp


@router.get("/people/{person_id}", response_model=PersonProfileResponse)
async def get_person(
    person_id: str,
    search_id: str | None = Query(None, alias="search_id"),
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate search_id: must belong to current_user and not expired
    show_contact = False
    if search_id:
        s_result = await db.execute(
            select(Search).where(
                Search.id == search_id,
                Search.searcher_id == current_user.id,
            )
        )
        search_rec = s_result.scalar_one_or_none()
        if search_rec:
            cutoff = datetime.utcnow() - timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS)
            if search_rec.created_at and search_rec.created_at >= cutoff:
                r_result = await db.execute(
                    select(SearchResult).where(
                        SearchResult.search_id == search_id,
                        SearchResult.person_id == person_id,
                    )
                )
                if r_result.scalar_one_or_none():
                    show_contact = False  # only show contact if unlocked
                    pass  # free to view profile
                else:
                    raise HTTPException(status_code=403, detail="Person not in this search result")
            else:
                raise HTTPException(status_code=403, detail="Search expired")
        else:
            raise HTTPException(status_code=403, detail="Invalid search_id")
    else:
        raise HTTPException(status_code=400, detail="search_id required to view profile")

    # Load person
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
    if show_contact:
        c_result = await db.execute(select(ContactDetails).where(ContactDetails.person_id == person_id))
        c = c_result.scalar_one_or_none()
        if c:
            contact = ContactDetailsResponse(
                email_visible=c.email_visible,
                phone=c.phone,
                linkedin_url=c.linkedin_url,
                other=c.other,
            )
    # Check if current_user has unlocked this person's contact in this search
    unlock_result = await db.execute(
        select(UnlockContact).where(
            UnlockContact.searcher_id == current_user.id,
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
        work_preferred_locations=vis.work_preferred_locations or [] if vis else [],
        work_preferred_salary_min=vis.work_preferred_salary_min if vis else None,
        work_preferred_salary_max=vis.work_preferred_salary_max if vis else None,
        contact_preferred_salary_min=vis.contact_preferred_salary_min if vis else None,
        contact_preferred_salary_max=vis.contact_preferred_salary_max if vis else None,
        experience_cards=[_card_to_response(c) for c in cards],
        contact=contact,
    )


@router.post("/people/{person_id}/unlock-contact", response_model=UnlockContactResponse)
@limiter.limit("20/minute")
async def unlock_contact(
    request: Request,
    person_id: str,
    search_id: str = Query(..., alias="search_id"),
  idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
  current_user: Person = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
):
    endpoint = "POST /people/{person_id}/unlock-contact"
    if idempotency_key:
        existing = await get_idempotent_response(db, idempotency_key, current_user.id, endpoint)
        if existing and existing.response_body:
            await db.commit()
            return UnlockContactResponse(**existing.response_body)

    # Validate search_id and that person is in results
    s_result = await db.execute(
        select(Search).where(
            Search.id == search_id,
            Search.searcher_id == current_user.id,
        )
    )
    search_rec = s_result.scalar_one_or_none()
    if not search_rec:
        raise HTTPException(status_code=403, detail="Invalid search_id")
    cutoff = datetime.utcnow() - timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS)
    if search_rec.created_at and search_rec.created_at < cutoff:
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

    # Already unlocked?
    u_result = await db.execute(
        select(UnlockContact).where(
            UnlockContact.searcher_id == current_user.id,
            UnlockContact.target_person_id == person_id,
            UnlockContact.search_id == search_id,
        )
    )
    if u_result.scalar_one_or_none():
        c_result = await db.execute(select(ContactDetails).where(ContactDetails.person_id == person_id))
        c = c_result.scalar_one_or_none()
        contact = ContactDetailsResponse(
            email_visible=c.email_visible if c else True,
            phone=c.phone if c else None,
            linkedin_url=c.linkedin_url if c else None,
            other=c.other if c else None,
        )
        return UnlockContactResponse(unlocked=True, contact=contact)

    balance = await get_balance(db, current_user.id)
    if balance < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    unlock = UnlockContact(
        searcher_id=current_user.id,
        target_person_id=person_id,
        search_id=search_id,
    )
    db.add(unlock)
    await db.flush()
    await deduct_credits(db, current_user.id, 1, "unlock_contact", "unlock_id", unlock.id)

    c_result = await db.execute(select(ContactDetails).where(ContactDetails.person_id == person_id))
    c = c_result.scalar_one_or_none()
    contact = ContactDetailsResponse(
        email_visible=c.email_visible if c else True,
        phone=c.phone if c else None,
        linkedin_url=c.linkedin_url if c else None,
        other=c.other if c else None,
    )
    await db.commit()

    resp = UnlockContactResponse(unlocked=True, contact=contact)
    if idempotency_key:
        await save_idempotent_response(
            db, idempotency_key, current_user.id, endpoint,
            200, resp.model_dump(),
        )
        await db.commit()
    return resp
